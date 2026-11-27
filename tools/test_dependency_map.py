#!/usr/bin/env python3
"""Check tools/dependency_map.py on throwaway files: Python imports, GDScript preloads, m. forwarders, callers, touches, and pre-commit."""
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import dependency_map as dm


ROOT = Path(__file__).resolve().parent.parent
RESULTS = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, condition, detail=""):
    RESULTS.append(bool(condition))
    if not condition or VERBOSE:
        print(("PASS " if condition else "FAIL ") + name + ("" if condition else f"  {detail}"))


def run(root, *args):
    return subprocess.run(args, cwd=root, text=True, capture_output=True)


with TemporaryDirectory(prefix="dep-map-test-") as folder:
    root = Path(folder)
    for d in ("viewport", "viewport/tools", "viewport/tests", "worker", "tools", "docs", ".githooks"):
        (root / d).mkdir(parents=True)

    # Python files with AST imports (including relative and from-imports; stdlib ignored)
    (root / "worker/other.py").write_text("def apply(x):\n    return x + 1\n")
    (root / "worker/common.py").write_text(
        "import json\n\ndef apply(x):\n    return x\n\ndef self_call():\n    return apply(0)\n"
    )
    (root / "worker/sub.py").write_text(
        "from common import apply\nimport common as cm\n\n"
        "def run():\n    # common.apply(9)\n    s = 'common.apply(9)'\n"
        "    return apply(1) + cm.apply(2)\n\n"
        "def other_call():\n    from other import apply\n    return apply(3)\n"
    )
    (root / "worker/untyped_py.py").write_text("def f(obj):\n    return obj.apply(1)\n")
    (root / "tools/helper.py").write_text("import os\n\ndef sync():\n    pass\n")
    (root / "tools/cli.py").write_text("from helper import sync\n\nsync()\n")
    (root / "tools/test_cli.py").write_text("import cli\n\ndef test_one():\n    assert cli is not None\n")

    # GDScript files: preload, load, extends, class_name, and main.gd m. forwarders
    (root / "viewport/selection.gd").write_text(
        "extends Node\nfunc clear_sel():\n    pass\nfunc apply():\n    pass\n"
    )
    (root / "viewport/presenter.gd").write_text(
        "extends Node\nfunc show_state():\n    pass\n"
    )
    (root / "viewport/units.gd").write_text(
        "extends RefCounted\nclass_name UnitLib\nfunc fmt():\n    pass\n"
    )
    (root / "viewport/main.gd").write_text(
        'extends Node3D\n'
        'const Selection := preload("res://selection.gd")\n'
        'const Presenter := preload("res://presenter.gd")\n'
        'var sel: Selection = Selection.new()\n'
        'var pres = Presenter.new()\n'
        'var ui = load("res://ui.gd").new(self)\n'
        'var selection: Array:\n'
        '    get: return sel.selection\n'
        'func _show_state() -> void: pres.show_state()\n'
    )
    (root / "viewport/ui.gd").write_text(
        'extends RefCounted\n'
        'func refresh(m):\n'
        '    m.sel.clear_sel()\n'
        '    # m.sel.clear_sel()\n'
        '    var s := "m.sel.clear_sel()"\n'
        '    m._show_state()\n'
        '    var x = m.selection\n'
        '    return UnitLib.fmt()\n'
    )
    (root / "viewport/tools/tool.gd").write_text("extends RefCounted\n")
    (root / "viewport/tools/select_tool.gd").write_text(
        'extends "res://tools/tool.gd"\n'
        'func go():\n'
        '    pass\n'
    )
    (root / "viewport/test_ui.gd").write_text(
        'extends SceneTree\n'
        'const Sel := preload("res://selection.gd")\n'
        'func test():\n'
        '    var s: Sel = Sel.new()\n'
        '    s.clear_sel()\n'
        '    var u\n'
        '    u.clear_sel()\n'
    )

    shutil.copy(ROOT / "tools/dependency_map.py", root / "tools/dependency_map.py")
    shutil.copy(ROOT / ".githooks/pre-commit", root / ".githooks/pre-commit")

    # 1. Dependency graph & rendered map
    files, uses, used_by = dm.build_dependency_graph(root)
    check("Python import resolved", "worker/common.py" in uses["worker/sub.py"], str(uses["worker/sub.py"]))
    check("Python tools import resolved", "tools/helper.py" in uses["tools/cli.py"], str(uses["tools/cli.py"]))
    check("GDScript extends path resolved", "viewport/tools/tool.gd" in uses["viewport/tools/select_tool.gd"])
    check("GDScript class_name reference resolved", "viewport/units.gd" in uses["viewport/ui.gd"], str(uses["viewport/ui.gd"]))
    check("GDScript m.subobj resolved", "viewport/selection.gd" in uses["viewport/ui.gd"], str(uses["viewport/ui.gd"]))
    check("GDScript m.func forwarder resolved", "viewport/presenter.gd" in uses["viewport/ui.gd"], str(uses["viewport/ui.gd"]))
    check("GDScript m.prop forwarder resolved", "viewport/selection.gd" in uses["viewport/ui.gd"], str(uses["viewport/ui.gd"]))
    check("reverse used_by populated", "viewport/ui.gd" in used_by["viewport/presenter.gd"], str(used_by["viewport/presenter.gd"]))
    check("tests excluded from map", "tools/test_cli.py" not in files and "viewport/test_ui.gd" not in files)

    # 2. Generate & --check
    gen = run(root, sys.executable, "tools/dependency_map.py")
    check("generate exits 0", gen.returncode == 0, gen.stderr)
    check("--check passes after generate", run(root, sys.executable, "tools/dependency_map.py", "--check").returncode == 0)

    map_path = root / "docs/dependency-map.md"
    saved = map_path.read_text()
    map_path.write_text(saved + "\nstale\n")
    stale = run(root, sys.executable, "tools/dependency_map.py", "--check")
    check("--check fails when stale", stale.returncode == 1 and "out of date" in stale.stderr, stale.stderr)

    # 3. callers: unique function & shared common name (qualified + unresolved + comment/string filtering)
    callers_unique = run(root, sys.executable, "tools/dependency_map.py", "callers", "viewport/selection.gd:clear_sel")
    check(
        "callers finds resolved code/test call sites, omits comments/strings/def, and flags untyped var",
        callers_unique.returncode == 0
        and "viewport/ui.gd:3:" in callers_unique.stdout
        and "viewport/ui.gd:4:" not in callers_unique.stdout
        and "viewport/ui.gd:5:" not in callers_unique.stdout
        and "viewport/test_ui.gd:5:" in callers_unique.stdout
        and "Unresolved (check by hand):" in callers_unique.stdout
        and "viewport/test_ui.gd:7:" in callers_unique.stdout
        and "viewport/selection.gd:2:" not in callers_unique.stdout
        and "note:" not in callers_unique.stdout,
        callers_unique.stdout + callers_unique.stderr,
    )

    callers_common = run(root, sys.executable, "tools/dependency_map.py", "callers", "worker/common.py:apply")
    check(
        "callers qualifies Python imports, omits shadowed/comment/string calls, and flags untyped",
        callers_common.returncode == 0
        and "defined in 3 files" in callers_common.stdout
        and "worker/common.py:7:" in callers_common.stdout
        and "worker/sub.py:7:" in callers_common.stdout
        and "worker/sub.py:5:" not in callers_common.stdout
        and "worker/sub.py:6:" not in callers_common.stdout
        and "worker/sub.py:11:" not in callers_common.stdout
        and "Unresolved (check by hand):" in callers_common.stdout
        and "worker/untyped_py.py:2:" in callers_common.stdout,
        callers_common.stdout + callers_common.stderr,
    )

    # 4. touches: P45 backtick format, tests on their own, unresolved separate
    touches = run(root, sys.executable, "tools/dependency_map.py", "touches", "viewport/selection.gd:clear_sel")
    check(
        "touches prints Touches, Tests, and Unresolved (check by hand) separately",
        touches.returncode == 0
        and "Touches: viewport/selection.gd (`clear_sel`), viewport/ui.gd (`clear_sel`)" in touches.stdout
        and "Tests: viewport/test_ui.gd (`clear_sel`)" in touches.stdout
        and "Unresolved (check by hand): viewport/test_ui.gd (`clear_sel`:7)" in touches.stdout,
        touches.stdout + touches.stderr,
    )

    touches_py = run(root, sys.executable, "tools/dependency_map.py", "touches", "worker/common.py:apply")
    touches_py_line = next((ln for ln in touches_py.stdout.splitlines() if ln.startswith("Touches:")), "")
    check(
        "touches for Python common.py:apply excludes worker/other.py and viewport/selection.gd",
        touches_py.returncode == 0
        and touches_py_line == "Touches: worker/common.py (`apply`), worker/sub.py (`apply`)"
        and "Unresolved (check by hand): worker/untyped_py.py (`apply`:2)" in touches_py.stdout,
        touches_py.stdout + touches_py.stderr,
    )

    # 5. Pre-commit hook rebuilds and stages docs/dependency-map.md
    run(root, sys.executable, "tools/dependency_map.py")
    run(root, "git", "init")
    run(root, "git", "config", "user.email", "test@example.invalid")
    run(root, "git", "config", "user.name", "Dep Map Test")
    run(root, "git", "add", ".")
    c1 = run(root, "git", "-c", "core.hooksPath=.githooks", "commit", "-m", "init")
    check("pre-commit succeeds on valid repo", c1.returncode == 0, c1.stdout + c1.stderr)

    (root / "worker/sub.py").write_text("def run():\n    return 1\n")
    run(root, "git", "add", "worker/sub.py")
    c2 = run(root, "git", "-c", "core.hooksPath=.githooks", "commit", "-m", "drop common import")
    check(
        "pre-commit rebuilds and stages docs/dependency-map.md",
        c2.returncode == 0
        and "worker/sub.py` — uses: none" in map_path.read_text()
        and run(root, "git", "status", "--porcelain").stdout.strip() == "",
        c2.stdout + c2.stderr + "\n" + run(root, "git", "status", "--porcelain").stdout,
    )

# 6. diff(old_text, new_text): added, removed, no change, and short-name collision stability
old_dep = (
    "## viewport/\n\n"
    "- `viewport/a.gd` — uses: none — used by: b.gd\n"
    "- `viewport/b.gd` — uses: a.gd, c.gd — used by: none\n"
    "- `viewport/c.gd` — uses: none — used by: b.gd\n"
)
new_dep = (
    "## viewport/\n\n"
    "- `viewport/a.gd` — uses: none — used by: b.gd\n"
    "- `viewport/b.gd` — uses: viewport/a.gd, d.gd — used by: none\n"
    "- `viewport/d.gd` — uses: none — used by: b.gd\n"
    "- `viewport/tools/a.gd` — uses: none — used by: none\n"
)
dd = dm.diff(old_dep, new_dep)
check(
    "diff reports added and removed dependencies and keeps renamed short-name edge stable",
    dd == {
        "added": [("viewport/b.gd", "viewport/d.gd")],
        "removed": [("viewport/b.gd", "viewport/c.gd")],
    },
    str(dd),
)
check("diff on identical dependency maps is empty", dm.diff(old_dep, old_dep) == {"added": [], "removed": []})

print(f"DEPENDENCY MAP TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
if not all(RESULTS):
    raise SystemExit(1)
