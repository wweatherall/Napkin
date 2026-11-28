#!/usr/bin/env python3
"""Unit tests for tools/test_inventory.py.
Summary line: TEST INVENTORY TESTS: N passed, M failed."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import test_inventory  # noqa: E402

RESULTS: list[bool] = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(bool(ok))
    if not ok or VERBOSE:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {detail}"))


# 1. Parsing a summary plus PASS/FAIL lines
log_ok = """\
some preamble
PASS first check
PASS second check
FAIL third check  {"got": 1, "want": 2}
SAMPLE TESTS: 2 passed, 1 failed
"""
checks_ok, parsed_ok = test_inventory.parse_feature_log(log_ok)
check("parse_feature_log parses all checks and sets parsed=True",
      parsed_ok is True and checks_ok == ["first check", "second check", "third check"],
      f"parsed={parsed_ok}, checks={checks_ok}")

# 2. Detail text is cut off at the two-space separator
check("strip_detail cuts off two-space detail text",
      test_inventory.strip_detail("my check  runtime=123ms {x: 1}") == "my check",
      test_inventory.strip_detail("my check  runtime=123ms {x: 1}"))

# 3. File whose counts don't add up gets parsed=False
log_mismatch = """\
PASS only one printed
SAMPLE TESTS: 5 passed, 0 failed
"""
checks_mis, parsed_mis = test_inventory.parse_feature_log(log_mismatch)
check("mismatched summary count sets parsed=False",
      parsed_mis is False and checks_mis == ["only one printed"],
      f"parsed={parsed_mis}, checks={checks_mis}")

log_no_summary = """\
PASS check a
PASS check b
"""
checks_ns, parsed_ns = test_inventory.parse_feature_log(log_no_summary)
check("missing summary line sets parsed=False",
      parsed_ns is False and checks_ns == ["check a", "check b"],
      f"parsed={parsed_ns}, checks={checks_ns}")

# 4. Quick lane log parsing
quick_log = """\
QUICK timing (s): rect 1.2 | push 2.3 | opening fresh models 0.5
QUICK 42 passed, 0 failed in 8.4 s
"""
q_checks, q_sec, q_parsed = test_inventory.parse_quick_lane_log(quick_log)
check("parse_quick_lane_log extracts seconds and marks unprinted PASS lines parsed=False",
      q_sec == 8.4 and q_parsed is False and q_checks == [],
      f"sec={q_sec}, parsed={q_parsed}, checks={q_checks}")

quick_log_with_fail = """\
QUICK FAIL [rect] snap to corner  got (1,2)
QUICK 41 passed, 1 failed in 7.5 s
"""
qf_checks, qf_sec, qf_parsed = test_inventory.parse_quick_lane_log(quick_log_with_fail)
check("parse_quick_lane_log strips detail on QUICK FAIL",
      qf_sec == 7.5 and qf_parsed is False and qf_checks == ["[rect] snap to corner"],
      f"sec={qf_sec}, parsed={qf_parsed}, checks={qf_checks}")

# 5. Stable sort: different input order and different seconds produce identical JSON except seconds
entries_a = [
    {"file": "worker/test_b.py", "suite": "worker", "runner": "freecadcmd",
     "seconds": 2.345, "checks": ["zeta", "alpha", "shared"], "parsed": True},
    {"file": "tools/test_a.py", "suite": "tools", "runner": "python3",
     "seconds": 0.123, "checks": ["shared", "beta"], "parsed": False},
]
entries_b = [
    {"file": "tools/test_a.py", "suite": "tools", "runner": "python3",
     "seconds": 0.999, "checks": ["beta", "shared"], "parsed": False},
    {"file": "worker/test_b.py", "suite": "worker", "runner": "freecadcmd",
     "seconds": 5.678, "checks": ["shared", "alpha", "zeta"], "parsed": True},
]
inv_a = test_inventory.build_inventory(entries_a)
inv_b = test_inventory.build_inventory(entries_b)
for e in inv_a["files"]:
    e["seconds"] = 0.0
for e in inv_b["files"]:
    e["seconds"] = 0.0
check("build_inventory sort is stable across runs (differs only in seconds)",
      inv_a == inv_b and [f["file"] for f in inv_a["files"]] == ["tools/test_a.py", "worker/test_b.py"],
      f"a={inv_a} b={inv_b}")

# 6. Report formatting and --report CLI
inv_report = test_inventory.build_inventory(entries_a)
report = test_inventory.format_report(inv_report)
check("format_report includes suite totals, slowest, unparsed, and duplicate check names",
      "Totals by suite:" in report
      and "10 slowest files:" in report
      and "Unparsed files (1):" in report
      and "tools/test_a.py" in report
      and "Check names in more than one file (1):" in report
      and "shared (2 files: tools/test_a.py, worker/test_b.py)" in report,
      report)

with tempfile.TemporaryDirectory() as tmp:
    json_path = Path(tmp) / "inv.json"
    json_path.write_text(json.dumps(inv_report), encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = test_inventory.main(["--report", "--out", str(json_path)])
    check("--report prints saved JSON report and exits 0",
          rc == 0 and "Totals by suite:" in buf.getvalue(),
          buf.getvalue())

passed = sum(1 for r in RESULTS if r)
failed = len(RESULTS) - passed
print(f"TEST INVENTORY TESTS: {passed} passed, {failed} failed")
raise SystemExit(0 if failed == 0 else 1)
