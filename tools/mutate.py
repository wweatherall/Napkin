#!/usr/bin/env python3
"""Measure which feature tests catch individual AST mutations in worker modules.

Run:    python3 tools/mutate.py [--sample 20] [--lanes 4] [--budget-minutes 8]
Review: python3 tools/mutate.py --list worker/model.py
Export: python3 tools/mutate.py --matrix [--sample 20]

The run needs permission to create detached Git worktrees and start FreeCAD.
Results and coverage stay in scratch. --matrix exports the current source's
recorded results, restricted to the same sample if one is specified.
"""
from __future__ import annotations

import argparse
import ast
from bisect import bisect_left, bisect_right
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tokenize

from test_inventory import FEATURE_SUMMARY_RE, discover_feature_tests, strip_detail

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_SEED = 171
COMPARISONS = {
    ast.Lt: ("<", ">="), ast.GtE: (">=", "<"),
    ast.LtE: ("<=", ">"), ast.Gt: (">", "<="),
    ast.Eq: ("==", "!="), ast.NotEq: ("!=", "=="),
}
ARITHMETIC = {
    ast.Add: ("+", "-"), ast.Sub: ("-", "+"),
    ast.Mult: ("*", "/"), ast.Div: ("/", "*"),
}
RUN_TEST = """
source tools/featuretest.sh
test_runner_for "$1"
[ -n "$TEST_CMD" ] || exit 2
run_test_command $TEST_CMD
"""


@dataclass(frozen=True)
class Mutant:
    file: str
    line: int
    column: int
    operator: str
    function: str
    edits: tuple[tuple[int, int, bytes], ...]

    @property
    def id(self):
        return f"{self.file}:{self.line}:{self.column}:{self.operator}"

    def apply(self, source):
        for start, end, replacement in reversed(self.edits):
            source = source[:start] + replacement + source[end:]
        return source


@dataclass(frozen=True)
class Module:
    source: bytes
    digest: str
    mutants: list[Mutant]


def diagnostic(call):
    if not isinstance(call, ast.Call):
        return False
    target = call.func
    names = []
    while isinstance(target, (ast.Attribute, ast.Call)):
        if isinstance(target, ast.Attribute):
            names.append(target.attr)
            target = target.value
        else:
            target = target.func
    if isinstance(target, ast.Name):
        names.append(target.id)
    return (names in (["print"], ["log"]) or bool({"logger", "logging"} & set(names))
            or (len(names) > 1 and names[-2:] == ["Console", "App"]
                and names[0].startswith("Print")))


class MutationSites(ast.NodeVisitor):
    def __init__(self, file, source):
        self.file = file
        self.source = source
        self.offsets = [0]
        for line in source.splitlines(keepends=True):
            self.offsets.append(self.offsets[-1] + len(line))
        self.tokens = []
        for token in tokenize.tokenize(io.BytesIO(source).readline):
            if token.type not in (tokenize.OP, tokenize.NAME):
                continue
            line, column = token.start
            line_start = self.offsets[line - 1]
            byte_column = len(token.line[:column].encode("utf-8"))
            self.tokens.append((line_start + byte_column, line, byte_column, token.string))
        self.token_starts = [token[0] for token in self.tokens]
        self.scope = []
        self.function = "<module>"
        self.in_function = False
        self.mutants = []

    def span(self, node):
        return (self.offsets[node.lineno - 1] + node.col_offset,
                self.offsets[node.end_lineno - 1] + node.end_col_offset)

    def add(self, line, column, operator, edits):
        self.mutants.append(Mutant(self.file, line, column, operator, self.function, tuple(sorted(edits))))

    def replace(self, node, operator, replacement):
        start, end = self.span(node)
        self.add(node.lineno, node.col_offset, operator, [(start, end, replacement)])

    def operator_token(self, left, right, symbol):
        left_end, right_start = self.span(left)[1], self.span(right)[0]
        start = bisect_left(self.token_starts, left_end)
        end = bisect_left(self.token_starts, right_start)
        for token in self.tokens[start:end]:
            if token[3] == symbol:
                return token
        # Before Python 3.12, tokenize emits one opaque string for a whole f-string.
        # Its AST still gives offsets for each operand in a replacement field.
        gap = b"(" + self.source[left_end:right_start] + b")"
        lines = gap.splitlines(keepends=True)
        for token in tokenize.tokenize(io.BytesIO(gap).readline):
            if token.type in (tokenize.OP, tokenize.NAME) and token.string == symbol:
                line, column = token.start
                offset = left_end - 1 + sum(map(len, lines[:line - 1]))
                offset += len(token.line[:column].encode("utf-8"))
                original_line = bisect_right(self.offsets, offset)
                return offset, original_line, offset - self.offsets[original_line - 1], symbol
        raise ValueError(f"cannot locate {symbol!r} in {self.file}:{left.lineno}")

    def replace_statement(self, node):
        decorators = getattr(node, "decorator_list", ())
        if not decorators:
            self.replace(node, "statement-to-pass", b"pass")
            return
        end = bisect_left(self.token_starts, self.span(decorators[0])[0])
        start, line, column, _ = next(token for token in reversed(self.tokens[:end])
                                      if token[2:] == (node.col_offset, "@"))
        self.add(line, column, "statement-to-pass", [(start, self.span(node)[1], b"pass")])

    def flip(self, left, right, symbols, kind):
        old, new = symbols
        offset, line, column, _ = self.operator_token(left, right, old)
        self.add(line, column, f"{kind}-{old}-to-{new}", [(offset, offset + len(old), new.encode())])

    def visit(self, node):
        if isinstance(node, ast.If) and any(
            isinstance(part, ast.Name) and part.id == "__name__" for part in ast.walk(node.test)
        ):
            return
        if isinstance(node, ast.Expr) and (
            isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
            or diagnostic(node.value)
        ):
            return
        if diagnostic(node):
            return
        if self.in_function and isinstance(node, ast.stmt) and not isinstance(node, ast.Pass):
            self.replace_statement(node)
        super().visit(node)

    def visit_FunctionDef(self, node):
        for name, value in ast.iter_fields(node):
            if name != "body":
                for part in value if isinstance(value, list) else [value]:
                    if isinstance(part, ast.AST):
                        self.visit(part)
        previous = self.function, self.in_function
        self.scope.append(node.name)
        self.function, self.in_function = ".".join(self.scope), True
        for statement in node.body:
            self.visit(statement)
        self.scope.pop()
        self.function, self.in_function = previous

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        in_function = self.in_function
        self.scope.append(node.name)
        self.in_function = False
        self.generic_visit(node)
        self.in_function = in_function
        self.scope.pop()

    def visit_Compare(self, node):
        left = node.left
        for op, right in zip(node.ops, node.comparators):
            if type(op) in COMPARISONS:
                self.flip(left, right, COMPARISONS[type(op)], "compare")
            left = right
        self.generic_visit(node)

    def visit_BinOp(self, node):
        if type(node.op) in ARITHMETIC:
            self.flip(node.left, node.right, ARITHMETIC[type(node.op)], "arithmetic")
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        old, new = ("and", "or") if isinstance(node.op, ast.And) else ("or", "and")
        tokens = [self.operator_token(left, right, old)
                  for left, right in zip(node.values, node.values[1:])]
        edits = [(offset, offset + len(old), new.encode()) for offset, *_ in tokens]
        # Preserve grouping if the new operator has a different precedence.
        for group in [node, *(child for child in node.values if isinstance(child, ast.BoolOp))]:
            start, end = self.span(group)
            edits.extend([(start, start, b"("), (end, end, b")")])
        _, line, column, _ = tokens[0]
        self.add(line, column, f"boolean-{old}-to-{new}", edits)
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        if isinstance(node.op, ast.Not):
            start, end = self.span(node.operand)
            self.replace(node, "drop-not", b"(" + self.source[start:end] + b")")
        elif isinstance(node.op, (ast.UAdd, ast.USub)) and isinstance(node.operand, ast.Constant):
            value = node.operand.value
            if type(value) in (int, float, complex):
                self.increment(node, -value if isinstance(node.op, ast.USub) else value)
                return
        self.generic_visit(node)

    def increment(self, node, value):
        replacement = value + 1
        if replacement != value:
            self.replace(node, "increment-number", repr(replacement).encode())

    def visit_Constant(self, node):
        if isinstance(node.value, bool):
            self.replace(node, "flip-bool", repr(not node.value).encode())
        elif type(node.value) in (int, float, complex):
            self.increment(node, node.value)

    def visit_Return(self, node):
        if node.value is not None and not (
            isinstance(node.value, ast.Constant) and node.value.value is None
        ):
            self.replace(node, "return-none", b"return None")
        self.generic_visit(node)


def find_mutants(file, source):
    sites = MutationSites(file, source)
    sites.visit(ast.parse(source, filename=file))
    return sorted(sites.mutants, key=lambda m: (m.line, m.column, m.operator))


def worker_files(root):
    return [path for path in sorted((root / "worker").glob("*.py"))
            if not path.name.startswith("test_") and not path.is_symlink()]


def load_modules(root):
    modules = {}
    for path in worker_files(root):
        file = path.relative_to(root).as_posix()
        source = path.read_bytes()
        modules[file] = Module(source, hashlib.sha256(source).hexdigest(), find_mutants(file, source))
    return modules


def sample_mutants(mutants, count):
    if count is None or count >= len(mutants):
        return mutants
    rng = random.Random(SAMPLE_SEED)
    return [mutants[rng.randrange(i * len(mutants) // count, (i + 1) * len(mutants) // count)]
            for i in range(count)]


def trace_index(traces):
    covering = defaultdict(set)
    for trace in traces:
        for location in trace["lines"]:
            if location.startswith("worker/"):
                file, line = location.rsplit(":", 1)
                covering[file, int(line)].add(trace["test"])
    return {location: sorted(tests) for location, tests in covering.items()}


class StopRun(Exception):
    """A signal or the overall budget ended the run."""


class Budget:
    def __init__(self, minutes=None):
        self.end = math.inf if minutes is None else time.monotonic() + minutes * 60
        self.stopped = threading.Event()

    def check(self):
        if self.stopped.is_set() or time.monotonic() >= self.end:
            raise StopRun


def wait_for_process(command, cwd, env, log, budget, timeout=math.inf):
    budget.check()
    with subprocess.Popen(command, cwd=cwd, env=env, stdout=log,
                          stderr=subprocess.STDOUT, start_new_session=True) as proc:
        end = time.monotonic() + timeout
        try:
            while True:
                budget.check()
                remaining = end - time.monotonic()
                if remaining <= 0:
                    return None
                try:
                    return proc.wait(timeout=min(remaining, 0.2))
                except subprocess.TimeoutExpired:
                    continue
        finally:
            # Children can outlive the shell even when it exits successfully.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def read_traces(root, tests):
    directory = root / "scratch" / "coverage"
    inputs = (worker_files(root) + list((root / "worker" / "scenario").glob("*.py"))
              + [root / test["file"] for test in tests]
              + [root / name for name in ("tools/line_trace.py", "tools/test_inventory.py",
                                          "tools/featuretest.sh", "tests/scenario_fixture.json")])
    newest = max(path.stat().st_mtime_ns for path in inputs)
    traces = []
    for test in tests:
        path = directory / (test["name"] + ".json")
        if not path.is_file() or path.stat().st_mtime_ns < newest:
            return None
        try:
            data = json.loads(path.read_text())
        except (UnicodeError, json.JSONDecodeError):
            return None
        if data.get("test") != test["file"] or data.get("mode") != "line" or "lines" not in data:
            return None
        traces.append(data)
    return traces


def load_coverage(root, budget):
    tests, _ = discover_feature_tests(root)
    tests = [test for test in tests if test["suite"] in ("worker", "tools")]
    traces = read_traces(root, tests)
    if traces is None:
        scratch = root / "scratch"
        report = scratch / "coverage" / "summary.json"
        log_path = scratch / "mutation" / "coverage.log"
        print(f"Refreshing coverage ({log_path.relative_to(root)})", flush=True)
        env = dict(os.environ, TMPDIR=str(scratch))
        with log_path.open("w") as log:
            rc = wait_for_process(
                [sys.executable, "tools/test_inventory.py", "--coverage", "--coverage-out", str(report)],
                root, env, log, budget)
        traces = read_traces(root, tests)
        if rc or traces is None:
            raise RuntimeError(f"coverage did not produce a current trace for every test; see {log_path}")
    incomplete = sorted(trace["test"] for trace in traces if trace.get("children_untraced"))
    if incomplete:
        print(f"Coverage reported untraced child processes in {', '.join(incomplete)}", flush=True)
    return trace_index(traces)


def classify_test(rc, lines, known_checks=()):
    checks = set()
    known_checks = set(known_checks)
    failed_line = False
    summary = None
    for line in lines:
        line = line.rstrip("\r\n")
        if line.startswith("FAIL"):
            failed_line = True
            if line.startswith("FAIL "):
                checks.add(strip_detail(line[5:]))
        # FreeCAD reports a failed assert as a bracketed message and can exit 0.
        # Match against the inventory so arbitrary exception details stay unnamed.
        if line.startswith("Exception while processing file: ") and line.endswith("]"):
            name = line.partition(" [")[2][:-1]
        else:
            name = line.removeprefix("AssertionError: ") if line.startswith("AssertionError: ") else None
        if name in known_checks:
            checks.add(name)
            failed_line = True
        if summary is None:
            summary = FEATURE_SUMMARY_RE.match(line)
    if rc is None:
        outcome, reason = "timeout", "time limit"
    elif failed_line or (summary and int(summary[2])):
        outcome, reason = "killed", "failed check"
    elif rc or summary is None:
        outcome, reason = "killed", f"exit {rc}" if rc else "missing summary"
    else:
        outcome, reason = "survived", ""
    return {"outcome": outcome, "reason": reason, "checks": sorted(checks)}


def run_test(tree, file, seconds, budget, known_checks=()):
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="test-", dir=tree / "scratch") as folder:
        # macOS Qt resolves FreeCAD's application data through CoreFoundation.
        env = dict(os.environ, TESTDIR=folder, TMPDIR=folder,
                   CFFIXED_USER_HOME=folder, XDG_DATA_HOME=folder, XDG_CONFIG_HOME=folder,
                   XDG_CACHE_HOME=folder, PYTHONDONTWRITEBYTECODE="1")
        with tempfile.TemporaryFile(mode="w+t", dir=folder, encoding="utf-8", errors="replace") as log:
            rc = wait_for_process(["bash", "-c", RUN_TEST, "_", file], tree, env, log, budget,
                                  timeout=3 * seconds)
            log.seek(0)
            result = classify_test(rc, log, known_checks)
    return {"file": file, **result, "seconds": round(time.monotonic() - started, 3)}


def git(root, *args):
    proc = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or f"git {args[0]} exited {proc.returncode}")
    return proc.stdout


def ensure_clean(tree):
    status = git(tree, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise RuntimeError(f"mutation lane left changes in {tree}:\n{status}")


@contextmanager
def lane_tree(root, tree, revision):
    git(root, "worktree", "add", "--detach", str(tree), revision)
    try:
        (tree / "scratch").mkdir()
        yield tree
    finally:
        git(root, "worktree", "remove", "--force", str(tree))


def clear_bytecode(path):
    # Embedded Python writes bytecode even when PYTHONDONTWRITEBYTECODE is set.
    for cached in path.parent.glob(f"__pycache__/{path.stem}.*.pyc"):
        cached.unlink()


def mutation_status(tests):
    if not tests:
        return "no coverage"
    return "killed" if any(test["outcome"] != "survived" for test in tests) else "survived"


def run_mutant(tree, mutant, module, covering_tests, inventory, budget):
    results = []
    elapsed = 0
    if covering_tests:
        started = time.monotonic()
        path = tree / mutant.file
        if path.read_bytes() != module.source:
            raise RuntimeError(f"{mutant.file} differs from the detached revision")
        clear_bytecode(path)
        try:
            path.write_bytes(mutant.apply(module.source))
            results = [run_test(tree, file, inventory[file]["seconds"], budget, inventory[file]["checks"])
                       for file in covering_tests]
        finally:
            path.write_bytes(module.source)
            clear_bytecode(path)
            ensure_clean(tree)
        elapsed = round(time.monotonic() - started, 3)
    return {"id": mutant.id, "function": mutant.function, "operator": mutant.operator,
            "digest": module.digest, "status": mutation_status(results), "tests": results, "seconds": elapsed}


def saved_results(path, modules):
    """Read complete rows and repair a partial last line left by an interrupted write."""
    results = {}
    if path.exists():
        with path.open("r+b") as stream:
            while row := stream.readline():
                if not row.endswith(b"\n"):
                    stream.truncate(stream.tell() - len(row))
                    break
                result = json.loads(row)
                file = result["id"].split(":", 1)[0]
                if file in modules and result["digest"] == modules[file].digest:
                    results[result["id"]] = result
    return results


def record_result(stream, result):
    stream.write(json.dumps(result, separators=(",", ":")) + "\n")
    stream.flush()


def run_mutations(root, directory, modules, pending, journal, coverage, inventory, lanes, budget):
    unknown = {test for mutant in pending for test in coverage.get((mutant.file, mutant.line), ())
               if test not in inventory}
    if unknown:
        raise RuntimeError(f"refresh tests/test_inventory.json for covering tests: {', '.join(sorted(unknown))}")
    revision = git(root, "rev-parse", "HEAD").strip()
    required = git(root, "diff", "--name-only", revision, "--", "worker", "tools/featuretest.sh",
                   "tools/test_*.py", "tests", ":(exclude)tests/kill_matrix.json")
    if required:
        raise RuntimeError(f"commit the mutation inputs before running:\n{required}")
    lock = threading.Lock()
    jobs = iter(pending)
    completed = 0

    def run_lane(tree):
        nonlocal completed
        try:
            while True:
                budget.check()
                with lock:
                    mutant = next(jobs, None)
                if mutant is None:
                    return
                covering = coverage.get((mutant.file, mutant.line), [])
                result = run_mutant(tree, mutant, modules[mutant.file], covering, inventory, budget)
                with lock:
                    record_result(journal, result)
                    completed += 1
                    if completed % 20 == 0:
                        print(f"Recorded {completed}/{len(pending)} mutants this run", flush=True)
        except StopRun:
            return
        except BaseException:
            budget.stopped.set()
            raise

    lane_count = min(lanes, len(pending))
    with ExitStack() as stack:
        trees = []
        for i in range(lane_count):
            budget.check()
            trees.append(stack.enter_context(lane_tree(root, directory / f"tree-{i + 1}", revision)))
        with ThreadPoolExecutor(max_workers=lane_count) as pool:
            futures = [pool.submit(run_lane, tree) for tree in trees]
            for future in futures:
                future.result()
    return completed


def matrix_row(result, test_indexes, check_indexes):
    tests = result["tests"]
    killed = [test_indexes[t["file"]] for t in tests if t["outcome"] != "survived"]
    timeouts = [test_indexes[t["file"]] for t in tests if t["outcome"] == "timeout"]
    survived = [test_indexes[t["file"]] for t in tests if t["outcome"] == "survived"]
    failures = [[test_indexes[t["file"]], [check_indexes[name] for name in t["checks"]]]
                for t in tests if t["checks"]]
    return {"id": result["id"], "function": result["function"], "operator": result["operator"],
            "status": mutation_status(tests), "killed": killed, "timeouts": timeouts,
            "survived": survived, "failures": failures}


def write_matrix(path, results, timings):
    """Use zero-based indexes into tests and checks, with one mutant per line."""
    tests = sorted(timings)
    checks = sorted({name for result in results for test in result["tests"] for name in test["checks"]})
    test_indexes = {test: i for i, test in enumerate(tests)}
    check_indexes = {check: i for i, check in enumerate(checks)}
    rows = [matrix_row(result, test_indexes, check_indexes) for result in results]
    encode = json.JSONEncoder(separators=(",", ":")).encode
    temporary = path.with_suffix(".json.tmp")
    with temporary.open("w") as out:
        out.write('{\n"version":1,\n"tests":[\n')
        out.write(",\n".join(encode({"file": file, "seconds": timings[file]}) for file in tests))
        out.write('\n],\n"checks":' + encode(checks) + ',\n"mutants":[\n')
        out.write(",\n".join(map(encode, rows)))
        out.write("\n]\n}\n")
    temporary.replace(path)


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def positive_minutes(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be positive and finite")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--list", metavar="worker/file.py", help="list mutation IDs and functions")
    modes.add_argument("--matrix", action="store_true", help="export saved results")
    parser.add_argument("--sample", type=positive_int, metavar="K", help="select K mutants per file")
    parser.add_argument("--lanes", type=positive_int, default=4, metavar="N")
    parser.add_argument("--budget-minutes", type=positive_minutes, metavar="N")
    args = parser.parse_args(argv)
    if args.list:
        path = (ROOT / args.list).resolve()
        if path not in worker_files(ROOT):
            parser.error("--list requires a non-test module directly inside worker/")
        file = path.relative_to(ROOT).as_posix()
        for mutant in find_mutants(file, path.read_bytes()):
            print(mutant.id, mutant.function, sep="\t")
        return 0

    budget = Budget(args.budget_minutes)
    directory = ROOT / "scratch" / "mutation"
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with (directory / "run.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("another mutation run or export is active") from None
            return run_or_export(args, directory, budget)
    except StopRun:
        print("Mutation run stopped. Finished mutants were saved.", flush=True)
        return 0
    except (OSError, RuntimeError, ValueError) as err:
        print(f"mutate: {err}", file=sys.stderr)
        return 1


def run_or_export(args, directory, budget):
    modules = load_modules(ROOT)
    selected = [mutant for module in modules.values()
                for mutant in sample_mutants(module.mutants, args.sample)]
    journal = directory / "results.jsonl"
    saved = saved_results(journal, modules)
    feature_tests = json.loads((ROOT / "tests" / "test_inventory.json").read_text())["files"]
    inventory = {test["file"]: test for test in feature_tests if test["suite"] in ("worker", "tools")}
    if args.matrix:
        results = [saved[mutant.id] for mutant in selected if mutant.id in saved]
        if not results:
            raise RuntimeError("no saved results for the current selection")
        path = ROOT / "tests" / "kill_matrix.json"
        write_matrix(path, results, {file: test["seconds"] for file, test in inventory.items()})
        print(f"Wrote {len(results)}/{len(selected)} mutants to {path.relative_to(ROOT)}")
        return 0

    pending = [mutant for mutant in selected if mutant.id not in saved]
    print(f"{len(selected)} selected, {len(selected) - len(pending)} already recorded, "
          f"{len(pending)} pending", flush=True)
    if not pending:
        return 0
    previous_handlers = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[sig] = signal.signal(sig, lambda *_: budget.stopped.set())
    try:
        coverage = load_coverage(ROOT, budget)
        with journal.open("a") as stream:
            completed = run_mutations(ROOT, directory, modules, pending, stream, coverage,
                                      inventory, args.lanes, budget)
        print(f"Recorded {completed}; {len(pending) - completed} remain.", flush=True)
    finally:
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
    return 0


if __name__ == "__main__":
    sys.exit(main())
