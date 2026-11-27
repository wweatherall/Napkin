#!/usr/bin/env python3
"""Check tools/architecture_map.py header parsing, grouping, --check, and pre-commit hook."""
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import architecture_map as am


ROOT = Path(__file__).resolve().parent.parent
RESULTS = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, condition, detail=""):
    RESULTS.append(bool(condition))
    if not condition or VERBOSE:
        print(("PASS " if condition else "FAIL ") + name + ("" if condition else f"  {detail}"))


def run(root, *args):
    return subprocess.run(args, cwd=root, text=True, capture_output=True)


with TemporaryDirectory(prefix="arch-map-test-") as folder:
    root = Path(folder)
    for d in ("viewport", "viewport/tools", "viewport/tests", "worker", "tools", ".githooks"):
        (root / d).mkdir(parents=True)

    # Header forms: .gd (plain + @tool), .py (plain + leading # comment), .sh, multi-line & 160-char cut
    (root / "viewport/b.gd").write_text("extends Node\n## First line\n## continues here. Second sentence.\n\nvar x := 1\n")
    (root / "viewport/a.gd").write_text("@tool\nextends Node3D\n## Tool node header\n")
    (root / "viewport/tools/t.gd").write_text("extends RefCounted\n## " + ("x" * 170) + "\n")
    (root / "worker/w.py").write_text("# runner: none\n\"\"\"Worker module.\n\nMore details.\"\"\"\n")
    (root / "tools/s.sh").write_text("#!/bin/bash\n# Shell helper\n# with continuation. Rest.\necho ok\n")
    (root / "tools/DO_SOMETHING.py").write_text("#!/usr/bin/env python3\nimport sys\n")
    (root / "tools/RUN_IT.sh").write_text("#!/bin/bash\nexec echo hi\n")
    # Excluded test files (no headers needed)
    (root / "viewport/test_skip.gd").write_text("extends Node\n")
    (root / "viewport/tests/helper.gd").write_text("extends Node\n")
    (root / "worker/test_skip.py").write_text("x = 1\n")
    (root / "tools/test_skip.py").write_text("x = 1\n")

    body, missing = am.build_map(root)
    check("all header forms parse without missing", missing == [], str(missing))

    lines = [l for l in body.splitlines() if l.strip()]
    expected_order = [
        "- `viewport/a.gd` — Tool node header",
        "- `viewport/b.gd` — First line continues here",
        f"- `viewport/tools/t.gd` — {'x' * 159}…",
        "- `worker/w.py` — Worker module",
        "- `tools/s.sh` — Shell helper with continuation",
        f"- {am.WRAPPER_LINE}",
    ]
    check("grouping, path order, sentence split, 160-char cut, and wrapper line match",
          lines == expected_order, f"got {lines}")

    arch = root / "ARCHITECTURE.md"
    arch.write_text(
        f"# Arch\n\nBefore.\n\n{am.START}\n\nstale\n\n{am.END}\n\nAfter.\n"
    )
    shutil.copy(ROOT / "tools/architecture_map.py", root / "tools/architecture_map.py")
    shutil.copy(ROOT / ".githooks/pre-commit", root / ".githooks/pre-commit")

    stale = run(root, sys.executable, "tools/architecture_map.py", "--check")
    check("--check fails on stale section", stale.returncode == 1 and "out of date" in stale.stderr, stale.stderr)

    rebuilt1 = run(root, sys.executable, "tools/architecture_map.py")
    after1 = arch.read_text()
    rebuilt2 = run(root, sys.executable, "tools/architecture_map.py")
    after2 = arch.read_text()
    check("rebuild is idempotent and preserves surrounding text",
          rebuilt1.returncode == 0 and rebuilt2.returncode == 0 and after1 == after2
          and after1.startswith("# Arch\n\nBefore.\n\n") and after1.endswith("\n\nAfter.\n"),
          after1)

    clean = run(root, sys.executable, "tools/architecture_map.py", "--check")
    check("--check passes after rebuild", clean.returncode == 0, clean.stderr)

    # Hand-written core over 8 KB fails --check and reports bytes over
    saved_arch = arch.read_text()
    arch.write_text(saved_arch + ("\n" + "x" * am.MAX_CORE_BYTES))
    oversize = run(root, sys.executable, "tools/architecture_map.py", "--check")
    check("--check fails when hand-written core exceeds 8 KB",
          oversize.returncode == 1 and "over" in oversize.stderr, oversize.stderr)
    arch.write_text(saved_arch)

    # Missing header fails --check and names the file
    (root / "viewport/no_header.gd").write_text("extends Node\n# just a single hash\nvar y := 2\n")
    bad = run(root, sys.executable, "tools/architecture_map.py", "--check")
    check("--check fails on missing header and names file",
          bad.returncode == 1 and "viewport/no_header.gd" in bad.stderr, bad.stderr)
    (root / "viewport/no_header.gd").unlink()

    # Pre-commit hook in a temp git repo: rebuilds & stages ARCHITECTURE.md, refuses missing header
    run(root, "git", "init")
    run(root, "git", "config", "user.email", "test@example.invalid")
    run(root, "git", "config", "user.name", "Arch Map Test")
    run(root, "git", "add", ".")
    c1 = run(root, "git", "-c", "core.hooksPath=.githooks", "commit", "-m", "init")
    check("pre-commit succeeds on valid headers", c1.returncode == 0, c1.stdout + c1.stderr)

    (root / "worker/w.py").write_text('"""Updated worker module."""\n')
    run(root, "git", "add", "worker/w.py")
    c2 = run(root, "git", "-c", "core.hooksPath=.githooks", "commit", "-m", "update worker")
    check("pre-commit rebuilds and stages ARCHITECTURE.md",
          c2.returncode == 0 and "Updated worker module" in arch.read_text()
          and run(root, "git", "status", "--porcelain").stdout.strip() == "",
          c2.stdout + c2.stderr + "\n" + run(root, "git", "status", "--porcelain").stdout)

    (root / "viewport/missing.gd").write_text("extends Node\nvar z := 3\n")
    run(root, "git", "add", "viewport/missing.gd")
    c3 = run(root, "git", "-c", "core.hooksPath=.githooks", "commit", "-m", "bad commit")
    check("pre-commit refuses file without header and names it",
          c3.returncode != 0 and "viewport/missing.gd" in c3.stderr, c3.stdout + c3.stderr)

# diff(old_text, new_text): added, removed, changed, and no-change
old_map = (
    f"# Arch\n\n{am.START}\n\n"
    "- `viewport/a.gd` — Old A\n"
    "- `viewport/b.gd` — Same B\n"
    "- `worker/old.py` — Old worker\n"
    f"- {am.WRAPPER_LINE}\n\n{am.END}\n"
)
new_map = (
    f"# Arch\n\n{am.START}\n\n"
    "- `viewport/a.gd` — New A\n"
    "- `viewport/b.gd` — Same B\n"
    "- `worker/new.py` — New worker\n"
    f"- {am.WRAPPER_LINE}\n\n{am.END}\n"
)
d = am.diff(old_map, new_map)
check("diff reports added, removed, and changed headers (ignoring wrapper and unchanged)",
      d == {"added": ["worker/new.py"], "removed": ["worker/old.py"], "changed": [("viewport/a.gd", "Old A", "New A")]},
      str(d))
check("diff on identical maps is empty",
      am.diff(old_map, old_map) == {"added": [], "removed": [], "changed": []})

print(f"ARCHITECTURE MAP TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
raise SystemExit(0 if all(RESULTS) else 1)
