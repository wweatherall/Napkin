#!/usr/bin/env python3
"""Check AST mutations, covering-test lookup, resume, and feature-runner outcomes."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time
from tempfile import TemporaryDirectory

from mutate import (
    Budget, Module, ROOT, classify_test, find_mutants, matrix_row, record_result,
    run_test, sample_mutants, saved_results, trace_index, worker_files, write_matrix,
)

RESULTS = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, condition):
    RESULTS.append(bool(condition))
    if VERBOSE or not condition:
        print(("PASS " if condition else "FAIL ") + name, flush=True)


SOURCE = '''"""not 12 or True"""
def f(a, b, c):
    """not 13 or True"""
    print(a + 14, False)
    logger.warning(b * 15)
    logging.getLogger(__name__).info(c - 16)
    App.Console.PrintMessage(str(17))
    total = (a + b) - (b * c / a)
    valid = a < b <= c > a >= b == c != a
    x = a and b and c
    y = a and (b or c)
    if not valid:
        total = 0
    gap = -2
    skipped = True
    counted = False
    return total

if __name__ == "__main__":
    assert 22 == 23
    print(f(1, 2, 3))
'''.encode()
FILE = "worker/sample.py"
MUTANTS = find_mutants(FILE, SOURCE)
EXPECTED = [
    ("arithmetic-+-to--", "(a + b)", "(a - b)"),
    ("arithmetic---to-+", ") - (", ") + ("),
    ("arithmetic-*-to-/", "b * c", "b / c"),
    ("arithmetic-/-to-*", "c / a", "c * a"),
    ("compare-<-to->=", "a < b", "a >= b"),
    ("compare-<=-to->", "b <= c", "b > c"),
    ("compare->-to-<=", "c > a", "c <= a"),
    ("compare->=-to-<", "a >= b", "a < b"),
    ("compare-==-to-!=", "b == c", "b != c"),
    ("compare-!=-to-==", "c != a", "c == a"),
    ("boolean-and-to-or", "x = a and b and c", "x = (a or b or c)"),
    ("boolean-or-to-and", "(b or c)", "((b and c))"),
    ("drop-not", "if not valid:", "if (valid):"),
    ("increment-number", "total = 0", "total = 1"),
    ("increment-number", "gap = -2", "gap = -1"),
    ("flip-bool", "skipped = True", "skipped = False"),
    ("flip-bool", "counted = False", "counted = True"),
    ("statement-to-pass", "return total", "pass"),
    ("return-none", "return total", "return None"),
]
for operator, before, after in EXPECTED:
    expected = SOURCE.decode().replace(before, after, 1).encode()
    check(f"{operator} can turn {before!r} into {after!r}",
          any(m.apply(SOURCE) == expected for m in MUTANTS if m.operator == operator))

check("docstrings, diagnostics and main guard have no mutations",
      {m.line for m in MUTANTS}.isdisjoint({1, 3, 4, 5, 6, 7, 19, 20, 21, 22}))
check("all ordinary mutations in the fixture compile",
      all(compile(m.apply(SOURCE), FILE, "exec") for m in MUTANTS))
check("all mutation IDs are unique and repeatable",
      len({m.id for m in MUTANTS}) == len(MUTANTS)
      and MUTANTS == find_mutants(FILE, SOURCE))
check("function labels follow class and nested function scopes",
      {m.function for m in find_mutants(FILE, b"class C:\n def f(self):\n  def g():\n   return 1\n")}
      == {"C.f", "C.f.g"})
check("UTF-8 byte offsets and repeated comparison operators select separate sites",
      [m.apply('a = "é" == b == c\n'.encode()).decode()
       for m in find_mutants(FILE, 'a = "é" == b == c\n'.encode())]
      == ['a = "é" != b == c\n', 'a = "é" == b != c\n'])
decorated = b"def f():\n    @(\n        decorate)\n    def g():\n        return 1\n"
check("replacing a decorated statement removes its decorators",
      any(m.apply(decorated) == b"def f():\n    pass\n"
          for m in find_mutants(FILE, decorated)))
formatted = b'f"{a + b}"\n'
check("arithmetic inside an f-string field can be mutated",
      [m.apply(formatted) for m in find_mutants(FILE, formatted)] == [b'f"{a - b}"\n'])
check("sampling selects one stable site from each of four file sections",
      (sample := sample_mutants(MUTANTS, 4)) == sample_mutants(MUTANTS, 4)
      and all(m in MUTANTS[i * len(MUTANTS) // 4:(i + 1) * len(MUTANTS) // 4]
              for i, m in enumerate(sample)))

covering = trace_index([
    {"test": "worker/test_a.py", "lines": [FILE + ":10", FILE + ":11", FILE + ":11"]},
    {"test": "tools/test_b.py", "lines": ["tools/other.py:11", FILE + ":11", "worker/other.py:10"]},
])
check("only tests tracing the exact worker file and line are selected",
      covering == {
          (FILE, 10): ["worker/test_a.py"],
          (FILE, 11): ["tools/test_b.py", "worker/test_a.py"],
          ("worker/other.py", 10): ["tools/test_b.py"],
      } and not covering.get((FILE, 12)))

check("a missing summary kills even with exit status zero",
      classify_test(0, ["Traceback (most recent call last):"])["reason"] == "missing summary")
check("a nonzero exit kills even when the summary reports no failures",
      classify_test(1, ["DEMO TESTS: 1 passed, 0 failed"])["outcome"] == "killed")
check("a FAIL line kills and carries the check name without detail",
      classify_test(0, ["FAIL moved box  expected 1", "DEMO TESTS: 1 passed, 0 failed"]) ==
      {"outcome": "killed", "reason": "failed check", "checks": ["moved box"]})
check("known assertion labels survive FreeCAD's exception formatting",
      classify_test(0, ["Exception while processing file: worker/test_sample.py [moved box]"],
                    ["moved box"])["checks"] == ["moved box"]
      and classify_test(1, ["AssertionError: moved box"], ["moved box"])["checks"] == ["moved box"]
      and not classify_test(0, ["Exception while processing file: worker/test_sample.py [not a check]"],
                            ["moved box"])["checks"])
check("timeout is distinct and retains any check names printed first",
      classify_test(None, ["FAIL moved box"])["outcome"] == "timeout"
      and classify_test(None, ["FAIL moved box"])["checks"] == ["moved box"])

(ROOT / "scratch").mkdir(exist_ok=True)
with TemporaryDirectory(prefix="mutate-test-", dir=ROOT / "scratch") as folder:
    root = Path(folder)
    for name in ("tools", "worker", "scratch", "worker/scenario"):
        (root / name).mkdir()
    (root / "worker" / "scenario" / "helper.py").touch()
    path = root / FILE
    source = b"VALUE = 1 / (2 - 1)\n"
    path.write_bytes(source)
    test = root / "worker/test_sample.py"
    test.write_text(
        '# runner: python3\n'
        'import os\n'
        'from pathlib import Path\n'
        'from sample import VALUE\n'
        'folder = Path(os.environ["TESTDIR"])\n'
        'assert folder.parent.name == "scratch" and os.environ["TMPDIR"] == str(folder)\n'
        'assert not (folder / "model.FCStd").exists()\n'
        '(folder / "model.FCStd").write_text(str(VALUE))\n'
        'print("DEMO TESTS: 1 passed, 0 failed")\n'
    )
    shutil.copyfile(ROOT / "tools/featuretest.sh", root / "tools/featuretest.sh")
    check("mutation inputs exclude tests and worker/scenario", worker_files(root) == [path])
    before = run_test(root, "worker/test_sample.py", 1, Budget())
    check("normal feature runner passes and removes the test's model and directory",
          before["outcome"] == "survived" and not list((root / "scratch").iterdir()))

    mutants = find_mutants(FILE, source)
    crash = next(m for m in mutants if m.apply(source) == b"VALUE = 1 / (2 - 2)\n")
    path.write_bytes(crash.apply(source))
    after = run_test(root, "worker/test_sample.py", 1, Budget())
    check("a mutation that crashes on import is killed through the real feature runner",
          after["outcome"] == "killed" and after["reason"] in ("exit 1", "missing summary")
          and not after["checks"] and not list((root / "scratch").iterdir()))

    test.write_text("# runner: python3\nimport time\ntime.sleep(15)\n")
    timeout = run_test(root, "worker/test_sample.py", 0.2, Budget())
    check("a timed-out test returns its distinct outcome and removes its test files",
          timeout["outcome"] == "timeout" and not list((root / "scratch").iterdir()))

    test.write_text(
        '# runner: python3\n'
        'import os, subprocess, sys, time\n'
        'from pathlib import Path\n'
        'marker = Path(__file__).parent.parent / "scratch" / "child"\n'
        'if len(sys.argv) > 1:\n'
        '    marker.write_text(f"{os.getpid()} {os.getpgrp()}")\n'
        '    print("started", flush=True)\n'
        '    time.sleep(40)\n'
        'else:\n'
        '    child = subprocess.Popen([sys.executable, __file__, "child"], stdout=subprocess.PIPE)\n'
        '    assert child.stdout.readline() == b"started\\n"\n'
        '    print("DEMO TESTS: 1 passed, 0 failed")\n'
    )
    orphan = run_test(root, "worker/test_sample.py", 10, Budget())
    marker = root / "scratch/child"
    child_stopped = False
    if marker.is_file():
        pid, group = map(int, marker.read_text().split())
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                if os.getpgid(pid) != group:
                    child_stopped = True
                    break
            except ProcessLookupError:
                child_stopped = True
                break
            time.sleep(0.05)
        if not child_stopped:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        marker.unlink()
    check("the runner stops an already-started child after its test exits",
          orphan["outcome"] == "survived" and child_stopped)

    module = Module(source, hashlib.sha256(source).hexdigest(), mutants)
    row = {"id": crash.id, "function": crash.function, "operator": crash.operator,
           "digest": module.digest, "tests": [after], "seconds": after["seconds"]}
    journal = root / "scratch/results.jsonl"
    with journal.open("w") as stream:
        record_result(stream, row)
        stream.write('{"id":')
    saved = saved_results(journal, {FILE: module})
    check("resume keeps complete IDs and repairs a partial final row",
          saved == {crash.id: row} and len(journal.read_text().splitlines()) == 1
          and crash not in [mutant for mutant in mutants if mutant.id not in saved])
    check("resume ignores results for changed module content",
          saved_results(journal, {FILE: Module(b"other", "different", mutants)}) == {})

    matrix = root / "kill_matrix.json"
    write_matrix(matrix, [row], {"worker/test_sample.py": 1, "tools/test_a.py": 2})
    data = json.loads(matrix.read_text())
    check("matrix uses sorted test indexes and retains per-test seconds",
          data["tests"] == [
              {"file": "tools/test_a.py", "seconds": 2},
              {"file": "worker/test_sample.py", "seconds": 1},
          ] and data["mutants"][0]["killed"] == [1])
    timeout = {"file": "worker/test_sample.py", **classify_test(None, ["FAIL moved box"])}
    exported = matrix_row(dict(row, tests=[timeout]), {"worker/test_sample.py": 1}, {"moved box": 0})
    check("matrix counts timeouts as kills and indexes failed check names",
          exported["killed"] == exported["timeouts"] == [1] and exported["failures"] == [[1, [0]]])
    check("matrix keeps uncovered and survived mutants distinct",
          matrix_row(dict(row, tests=[]), {}, {})["status"] == "no coverage"
          and matrix_row(dict(row, tests=[before]), {"worker/test_sample.py": 0}, {})["status"]
          == "survived")

counts = Counter(RESULTS)
print(f"MUTATE TESTS: {counts[True]} passed, {counts[False]} failed")
sys.exit(bool(counts[False]))
