#!/usr/bin/env python3
# runner: none
"""Measure every feature test file (and optionally quicktest lanes) into tests/test_inventory.json.

Sources tools/featuretest.sh for test_runner_for / run_test_command and tools/gate.sh for set_test_tmpdir so
runner rules, TESTDIR, TMPDIR, and FreeCAD config handling never drift from the real test scripts.

Usage:
  python3 tools/test_inventory.py            Run feature tests, write tests/test_inventory.json, print report
  python3 tools/test_inventory.py --quick    Also run tools/quicktest.sh --full and include its lane logs
  python3 tools/test_inventory.py --report   Print the report from the saved tests/test_inventory.json
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_JSON = ROOT / "tests" / "test_inventory.json"
DEFAULT_COV_JSON = ROOT / "tests" / "test_coverage.json"
DEFAULT_TRACE_DIR = ROOT / "scratch" / "coverage"

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import line_trace  # noqa: E402

FEATURE_SUMMARY_RE = re.compile(r"^[A-Z][A-Z -]* TESTS:\s*(\d+)\s+passed,\s*(\d+)\s+failed")
CHECK_LINE_RE = re.compile(r"^(?:PASS|FAIL)\s+(.+)$")
QUICK_SUMMARY_RE = re.compile(r"^QUICK\s+(\d+)\s+passed,\s*(\d+)\s+failed\s+in\s+([0-9.]+)\s+s")
QUICK_TIMING_RE = re.compile(r"^QUICK\s+timing\s+\(s\):\s*(.+)$")
QUICK_STEP_RE = re.compile(r"(\S+)\s+([0-9]+(?:\.[0-9]+)?)")
QUICK_LOGS_RE = re.compile(r"\(logs:\s*([^)]+)\)")


def strip_detail(body: str) -> str:
    """Cut a PASS/FAIL check body at the two-space detail separator."""
    return body.split("  ", 1)[0].strip()


def parse_feature_log(text: str) -> tuple[list[str], bool]:
    """Parse PASS/FAIL check names and summary count from a feature test log.

    Returns (sorted_checks, parsed) where parsed is True iff a summary line was found
    and the number of PASS/FAIL lines matches passed + failed.
    """
    checks: list[str] = []
    expected_total: int | None = None
    for line in text.splitlines():
        m_chk = CHECK_LINE_RE.match(line)
        if m_chk:
            checks.append(strip_detail(m_chk.group(1)))
            continue
        if expected_total is None:
            m_sum = FEATURE_SUMMARY_RE.match(line)
            if m_sum:
                expected_total = int(m_sum.group(1)) + int(m_sum.group(2))
    parsed = expected_total is not None and len(checks) == expected_total
    return sorted(checks), parsed


def parse_quick_lane_log(text: str) -> tuple[list[dict[str, object]], float, int | None, bool]:
    """Parse step timings, lane seconds, check count, and parsed status from a quicktest vp*.log.

    Reads the 'QUICK timing (s): <step> <sec> ... | opening fresh models <sec>' line (disambiguating
    repeated step names with #<index>) and the 'QUICK N passed, M failed in T s' summary line.
    """
    raw_steps: list[tuple[str, float]] = []
    saw_timing = False
    check_count: int | None = None
    seconds = 0.0
    for line in text.splitlines():
        if not saw_timing:
            m_tim = QUICK_TIMING_RE.match(line)
            if m_tim:
                saw_timing = True
                left = m_tim.group(1).split("|", 1)[0]
                for step_name, sec_str in QUICK_STEP_RE.findall(left):
                    raw_steps.append((step_name, round(float(sec_str), 3)))
                continue
        if check_count is None:
            m_sum = QUICK_SUMMARY_RE.match(line)
            if m_sum:
                check_count = int(m_sum.group(1)) + int(m_sum.group(2))
                seconds = float(m_sum.group(3))

    counts = Counter(name for name, _ in raw_steps)
    seen: Counter[str] = Counter()
    steps: list[dict[str, object]] = []
    for name, sec in raw_steps:
        if counts[name] > 1:
            seen[name] += 1
            labeled = f"{name}#{seen[name]}"
        else:
            labeled = name
        steps.append({"name": labeled, "seconds": sec})
    steps.sort(key=lambda s: str(s["name"]))
    parsed = saw_timing and len(steps) > 0 and check_count is not None
    return steps, seconds, check_count, parsed


def discover_feature_tests(root: Path = ROOT) -> tuple[list[dict[str, str]], str]:
    """Use featuretest.sh's test_runner_for and gate.sh's set_test_tmpdir to list tests and tmpdir."""
    script = """
set -e
source tools/gate.sh
set_test_tmpdir >/dev/null
printf 'TMPDIR\\t%s\\n' "$TEST_TMPDIR"
source tools/featuretest.sh
for f in worker/test_*.py tools/test_*.py viewport/test_*.gd; do
  [ -f "$f" ] || continue
  test_runner_for "$f"
  [ -z "$TEST_CMD" ] && continue
  printf 'TEST\\t%s\\t%s\\t%s\\n' "$f" "$TEST_NAME" "$TEST_RUNNER"
done
"""
    proc = subprocess.run(
        ["bash", "-c", script],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    tests: list[dict[str, str]] = []
    test_tmpdir = tempfile.gettempdir()
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if parts[0] == "TMPDIR" and len(parts) >= 2:
            test_tmpdir = parts[1]
        elif parts[0] == "TEST" and len(parts) >= 4:
            rel_file, name, runner = parts[1], parts[2], parts[3]
            suite = rel_file.split("/", 1)[0]
            tests.append({
                "file": rel_file,
                "name": name,
                "runner": runner,
                "suite": suite,
            })
    return tests, test_tmpdir


def run_feature_tests(root: Path = ROOT) -> tuple[list[dict], str]:
    """Run all feature tests side by side via featuretest.sh and return file entries + tmpdir."""
    tests, test_tmpdir = discover_feature_tests(root)
    out_dir = Path(tempfile.mkdtemp(prefix="napkin-inventory-", dir=test_tmpdir))
    env = os.environ.copy()
    env["TMPDIR"] = test_tmpdir

    def _run_one(t: dict[str, str]) -> dict:
        testdir = out_dir / t["name"]
        testdir.mkdir(parents=True, exist_ok=True)
        log_path = out_dir / f"{t['name']}.log"
        extra_args = " -v" if (t["suite"] == "tools" and t["file"].endswith(".py")) else ""
        cmd = [
            "bash",
            "-c",
            f'source tools/featuretest.sh; test_runner_for "$1"; TESTDIR="$2" run_test_command $TEST_CMD{extra_args}',
            "_",
            t["file"],
            str(testdir),
        ]
        t0 = time.monotonic()
        with open(log_path, "w", encoding="utf-8") as log_fh:
            proc = subprocess.Popen(cmd, cwd=root, env=env, stdout=log_fh, stderr=subprocess.STDOUT)
            proc.wait()
        elapsed = round(time.monotonic() - t0, 3)
        text = log_path.read_text(encoding="utf-8", errors="replace")
        checks, parsed = parse_feature_log(text)
        return {
            "file": t["file"],
            "suite": t["suite"],
            "runner": t["runner"],
            "seconds": elapsed,
            "checks": checks,
            "parsed": parsed,
        }

    with ThreadPoolExecutor(max_workers=max(1, len(tests))) as pool:
        entries = list(pool.map(_run_one, tests))
    return entries, test_tmpdir


def run_quick_tests(root: Path = ROOT, test_tmpdir: str | None = None) -> list[dict]:
    """Run tools/quicktest.sh --full once and parse its vp*.log lane logs."""
    env = os.environ.copy()
    if test_tmpdir:
        env["TMPDIR"] = test_tmpdir
    proc = subprocess.run(
        ["bash", "tools/quicktest.sh", "--full"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    output = proc.stdout + "\n" + proc.stderr
    matches = QUICK_LOGS_RE.findall(output)
    if not matches:
        raise RuntimeError(f"Could not find quicktest logs directory in output:\n{output}")
    logs_dir = Path(matches[-1].strip())
    if not logs_dir.is_absolute():
        logs_dir = root / logs_dir

    entries: list[dict] = []
    for vp_log in sorted(logs_dir.glob("vp*.log")):
        text = vp_log.read_text(encoding="utf-8", errors="replace")
        steps, seconds, check_count, parsed = parse_quick_lane_log(text)
        lane_name = vp_log.stem  # e.g. vp1, vp2, vp3
        entry: dict = {
            "file": f"quick/{lane_name}",
            "suite": "quick",
            "runner": "godot",
            "seconds": round(seconds, 3),
            "checks": [str(s["name"]) for s in steps],
            "steps": steps,
            "parsed": parsed,
        }
        if check_count is not None:
            entry["check_count"] = check_count
        entries.append(entry)
    return entries


def build_inventory(file_entries: list[dict]) -> dict:
    """Sort file entries and build the top-level inventory dict."""
    sorted_files = []
    checks_flat: list[dict[str, str]] = []
    for entry in sorted(file_entries, key=lambda e: e["file"]):
        sorted_checks = sorted(entry["checks"])
        item: dict = {
            "file": entry["file"],
            "suite": entry["suite"],
            "runner": entry["runner"],
            "seconds": round(float(entry["seconds"]), 3),
            "checks": sorted_checks,
            "parsed": bool(entry["parsed"]),
        }
        if "steps" in entry:
            item["steps"] = sorted(
                [{"name": str(s["name"]), "seconds": round(float(s["seconds"]), 3)} for s in entry["steps"]],
                key=lambda s: str(s["name"]),
            )
        if "check_count" in entry:
            item["check_count"] = int(entry["check_count"])
        sorted_files.append(item)
        for chk in sorted_checks:
            checks_flat.append({"name": chk, "file": entry["file"]})

    checks_flat.sort(key=lambda c: (c["name"], c["file"]))
    return {"files": sorted_files, "checks": checks_flat}


def format_report(inventory: dict) -> str:
    """Format a concise human-readable report from an inventory dict."""
    files = inventory.get("files", [])
    checks = inventory.get("checks", [])

    suite_stats: dict[str, dict[str, float | int]] = {}
    for entry in files:
        s = entry["suite"]
        if s not in suite_stats:
            suite_stats[s] = {"files": 0, "checks": 0, "seconds": 0.0}
        suite_stats[s]["files"] += 1
        suite_stats[s]["checks"] += len(entry["checks"])
        suite_stats[s]["seconds"] += float(entry["seconds"])

    lines: list[str] = []
    lines.append("Totals by suite:")
    for s in sorted(suite_stats):
        st = suite_stats[s]
        lines.append(f"  {s:10s} {st['files']:3d} files, {st['checks']:4d} checks, {st['seconds']:6.2f} s")
    total_seconds = sum(float(e["seconds"]) for e in files)
    lines.append(f"  {'total':10s} {len(files):3d} files, {len(checks):4d} checks, {total_seconds:6.2f} s")

    lines.append("")
    lines.append("10 slowest files:")
    slowest = sorted(files, key=lambda e: (-float(e["seconds"]), e["file"]))[:10]
    for entry in slowest:
        lines.append(
            f"  {float(entry['seconds']):6.2f} s  {entry['file']} ({entry['suite']}, {len(entry['checks'])} checks)"
        )

    unparsed = sorted((e for e in files if not e.get("parsed")), key=lambda e: e["file"])
    lines.append("")
    lines.append(f"Unparsed files ({len(unparsed)}):")
    for entry in unparsed:
        lines.append(f"  {entry['file']} ({entry['suite']}, {len(entry['checks'])} parsed checks)")

    by_name: dict[str, set[str]] = defaultdict(set)
    for chk in checks:
        by_name[chk["name"]].add(chk["file"])
    dups = sorted(
        ((name, sorted(fset)) for name, fset in by_name.items() if len(fset) > 1),
        key=lambda item: (-len(item[1]), item[0]),
    )
    lines.append("")
    lines.append(f"Check names in more than one file ({len(dups)}):")
    for name, fset in dups:
        lines.append(f"  {name} ({len(fset)} files: {', '.join(fset)})")

    return "\n".join(lines)


def _is_non_test_repo_line(file_line: str) -> bool:
    """Return True if 'file:line' refers to a non-test file under worker/ or tools/."""
    rel = file_line.split(":", 1)[0]
    name = Path(rel).name
    return not name.startswith("test_")


def run_coverage_tests(
    root: Path = ROOT,
    trace_dir: Path | None = None,
    mode: str = "line",
) -> tuple[list[dict], list[str]]:
    """Run all worker and tools feature tests under line_trace.py.

    Returns (traced_entries, excluded_viewport_files). Per-test line traces are
    written to trace_dir (default: scratch/coverage/) so H216 can inspect them.
    """
    tests, test_tmpdir = discover_feature_tests(root)
    excluded_viewport = sorted(t["file"] for t in tests if t["suite"] == "viewport")
    py_tests = [t for t in tests if t["suite"] in ("worker", "tools")]

    out_dir = Path(tempfile.mkdtemp(prefix="napkin-cov-", dir=test_tmpdir))
    if trace_dir is None:
        trace_dir = root / "scratch" / "coverage"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_script = str((root / "tools" / "line_trace.py").resolve())

    def _run_one(t: dict[str, str]) -> dict:
        testdir = out_dir / t["name"]
        testdir.mkdir(parents=True, exist_ok=True)
        log_path = out_dir / f"{t['name']}.log"
        trace_path = trace_dir / f"{t['name']}.json"
        if trace_path.exists():
            trace_path.unlink()

        env = os.environ.copy()
        env["TMPDIR"] = test_tmpdir
        env["NAPKIN_TRACE_OUT"] = str(trace_path)
        env["NAPKIN_TRACE_SCRIPT"] = t["file"]
        env["NAPKIN_TRACE_MODE"] = mode
        env["NAPKIN_TRACE_ROOT"] = str(root)
        if t["suite"] == "tools" and t["file"].endswith(".py"):
            env["NAPKIN_TRACE_ARGS"] = json.dumps(["-v"])
        else:
            env.pop("NAPKIN_TRACE_ARGS", None)

        if t["runner"] == "freecadcmd":
            shell_cmd = (
                'source tools/featuretest.sh; test_runner_for "$1"; '
                'TESTDIR="$2" run_test_command "$FC" "$3"'
            )
            cmd = ["bash", "-c", shell_cmd, "_", t["file"], str(testdir), trace_script]
        else:
            cmd = [sys.executable, trace_script]

        t0 = time.monotonic()
        with open(log_path, "w", encoding="utf-8") as log_fh:
            proc = subprocess.Popen(cmd, cwd=root, env=env, stdout=log_fh, stderr=subprocess.STDOUT)
            rc = proc.wait()
        elapsed = round(time.monotonic() - t0, 3)

        text = log_path.read_text(encoding="utf-8", errors="replace")
        checks, parsed = parse_feature_log(text)
        trace_data = json.loads(trace_path.read_text(encoding="utf-8")) if trace_path.exists() else {}
        return {
            "file": t["file"],
            "suite": t["suite"],
            "runner": t["runner"],
            "seconds": elapsed,
            "exit_code": rc,
            "parsed": parsed,
            "check_count": len(checks),
            "line_count": int(trace_data.get("line_count", 0)),
            "lines": list(trace_data.get("lines", [])),
            "functions": sorted(set(trace_data.get("functions", []))),
        }

    with ThreadPoolExecutor(max_workers=max(1, len(py_tests))) as pool:
        entries = list(pool.map(_run_one, py_tests))
    return entries, excluded_viewport


def build_coverage(
    traced_entries: list[dict],
    excluded_viewport: list[str],
    root: Path = ROOT,
    mode: str = "line",
    inventory: dict | None = None,
) -> dict:
    """Build the committed tests/test_coverage.json structure (without line numbers)."""
    line_owners: Counter[str] = Counter()
    all_covered_lines_by_file: dict[str, set[int]] = defaultdict(set)
    all_covered_funcs: set[str] = set()

    for entry in traced_entries:
        for fl in entry.get("lines", []):
            rel, _, ln_str = fl.partition(":")
            if ln_str.isdigit():
                all_covered_lines_by_file[rel].add(int(ln_str))
            if _is_non_test_repo_line(fl):
                line_owners[fl] += 1
        for fn in entry.get("functions", []):
            all_covered_funcs.add(fn)

    files_out: list[dict] = []
    zero_unique_tests: list[str] = []
    for entry in sorted(traced_entries, key=lambda e: e["file"]):
        unique_count = sum(
            1 for fl in entry.get("lines", [])
            if _is_non_test_repo_line(fl) and line_owners[fl] == 1
        )
        if unique_count == 0:
            zero_unique_tests.append(entry["file"])
        files_out.append({
            "file": entry["file"],
            "suite": entry["suite"],
            "runner": entry["runner"],
            "seconds": round(float(entry["seconds"]), 3),
            "parsed": bool(entry.get("parsed", False)),
            "check_count": int(entry.get("check_count", 0)),
            "line_count": int(entry.get("line_count", 0)),
            "unique_line_count": unique_count,
            "functions": sorted(entry.get("functions", [])),
        })

    worker_modules: list[dict] = []
    uncovered_worker_functions: list[str] = []
    worker_dir = root / "worker"
    if worker_dir.is_dir():
        for py_path in sorted(worker_dir.glob("*.py")):
            if py_path.name.startswith("test_"):
                continue
            rel = f"worker/{py_path.name}"
            _, _, all_funcs, exec_lines = line_trace.extract_file_structure(py_path)
            covered_set = all_covered_lines_by_file.get(rel, set()) & exec_lines
            total_lines = len(exec_lines)
            covered_lines = len(covered_set)
            pct = round((100.0 * covered_lines / total_lines), 1) if total_lines else 100.0
            uncovered_fns = sorted(
                fn for fn in all_funcs if f"{rel}:{fn}" not in all_covered_funcs
            )
            for fn in uncovered_fns:
                uncovered_worker_functions.append(f"{rel}:{fn}")
            worker_modules.append({
                "file": rel,
                "covered_lines": covered_lines,
                "total_lines": total_lines,
                "coverage_pct": pct,
                "uncovered_functions": uncovered_fns,
            })

    result: dict = {
        "mode": mode,
        "excluded_suites": ["viewport"] if excluded_viewport else [],
        "excluded_files": sorted(excluded_viewport),
        "files": files_out,
        "worker_modules": worker_modules,
        "uncovered_worker_functions": sorted(uncovered_worker_functions),
        "zero_unique_tests": sorted(zero_unique_tests),
    }

    if inventory is not None:
        untraced_by_file = {
            e["file"]: float(e["seconds"])
            for e in inventory.get("files", [])
            if e.get("suite") in ("worker", "tools")
        }
        traced_total = sum(float(e["seconds"]) for e in files_out)
        untraced_total = sum(untraced_by_file.get(e["file"], 0.0) for e in files_out)
        if untraced_total > 0:
            result["timing"] = {
                "traced_seconds": round(traced_total, 2),
                "untraced_seconds": round(untraced_total, 2),
                "slowdown": round(traced_total / untraced_total, 2),
            }

    return result


def format_coverage_report(coverage: dict) -> str:
    """Format a human-readable coverage report from a test_coverage.json dict."""
    lines: list[str] = []
    mode = coverage.get("mode", "line")
    excluded = coverage.get("excluded_files", [])
    lines.append(f"Coverage mode: {mode} (viewport GDScript excluded: {len(excluded)} files, no GDScript tracer)")

    timing = coverage.get("timing")
    if timing:
        lines.append(
            f"Traced runtime: {timing['traced_seconds']:.2f} s vs untraced {timing['untraced_seconds']:.2f} s "
            f"({timing['slowdown']:.2f}x)"
        )

    lines.append("")
    lines.append("Worker module line coverage:")
    total_cov = 0
    total_exec = 0
    for mod in coverage.get("worker_modules", []):
        total_cov += int(mod["covered_lines"])
        total_exec += int(mod["total_lines"])
        lines.append(
            f"  {mod['file']:28s} {mod['covered_lines']:4d}/{mod['total_lines']:4d} ({mod['coverage_pct']:5.1f}%)"
        )
    overall_pct = (100.0 * total_cov / total_exec) if total_exec else 100.0
    lines.append(f"  {'total':28s} {total_cov:4d}/{total_exec:4d} ({overall_pct:5.1f}%)")

    uncovered = coverage.get("uncovered_worker_functions", [])
    op_handlers = [fn for fn in uncovered if ":op_" in fn or ".op_" in fn]
    lines.append("")
    lines.append(f"Uncovered worker functions ({len(uncovered)}):")
    if op_handlers:
        lines.append(f"  RED FLAG op handlers ({len(op_handlers)}): {', '.join(op_handlers)}")
    for fn in uncovered:
        flag = "  [OP HANDLER]" if fn in op_handlers else ""
        lines.append(f"  {fn}{flag}")

    files = coverage.get("files", [])
    lines.append("")
    lines.append("Unique non-test lines per test file (lines only that test runs):")
    for entry in sorted(files, key=lambda e: (-int(e["unique_line_count"]), e["file"])):
        lines.append(
            f"  {entry['unique_line_count']:5d} unique  ({entry['line_count']:5d} total)  {entry['file']}"
        )

    zero_unique = coverage.get("zero_unique_tests", [])
    lines.append("")
    lines.append(f"Candidate probes with 0 unique non-test lines ({len(zero_unique)}, not cuts):")
    for f in zero_unique:
        lines.append(f"  {f}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and report the Napkin test inventory.")
    parser.add_argument("--quick", action="store_true", help="Also run quicktest.sh --full and include lane logs")
    parser.add_argument("--report", action="store_true", help="Print report from saved JSON without running tests")
    parser.add_argument("--out", default=str(DEFAULT_OUT_JSON), help="Path to inventory JSON")
    parser.add_argument("--coverage", action="store_true", help="Run worker/tools tests under line_trace.py")
    parser.add_argument("--coverage-report", action="store_true", help="Print coverage report from saved JSON")
    parser.add_argument("--coverage-out", default=str(DEFAULT_COV_JSON), help="Path to coverage JSON")
    args = parser.parse_args(argv)

    cov_path = Path(args.coverage_out)
    if args.coverage_report:
        if not cov_path.exists():
            print(f"error: coverage file not found: {cov_path}", file=sys.stderr)
            return 1
        cov = json.loads(cov_path.read_text(encoding="utf-8"))
        print(format_coverage_report(cov))
        return 0

    out_path = Path(args.out)
    if args.coverage:
        inventory = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else None
        traced_entries, excluded_vp = run_coverage_tests(ROOT, DEFAULT_TRACE_DIR)
        cov = build_coverage(traced_entries, excluded_vp, ROOT, mode="line", inventory=inventory)
        cov_path.parent.mkdir(parents=True, exist_ok=True)
        cov_path.write_text(json.dumps(cov, indent=2) + "\n", encoding="utf-8")
        print(format_coverage_report(cov))
        return 0

    if args.report:
        if not out_path.exists():
            print(f"error: inventory file not found: {out_path}", file=sys.stderr)
            return 1
        inventory = json.loads(out_path.read_text(encoding="utf-8"))
        print(format_report(inventory))
        return 0

    entries, test_tmpdir = run_feature_tests(ROOT)
    if args.quick:
        entries.extend(run_quick_tests(ROOT, test_tmpdir))
    inventory = build_inventory(entries)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(format_report(inventory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
