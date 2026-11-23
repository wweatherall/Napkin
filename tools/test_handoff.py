#!/usr/bin/env python3
"""Check Touches validation and its pre-commit entry point."""
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import handoff


ROOT = Path(__file__).resolve().parent.parent
RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append(bool(condition))
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else f"  {detail}"))


def run(root, *args, must_pass=False):
    return subprocess.run(args, cwd=root, text=True, capture_output=True, check=must_pass)


def entry(hid, touches, status="open"):
    return f"### {hid} — Fixture\n\nAuthor: Codex | Status: {status} | For: either\n\nTouches: {touches}\n"


with TemporaryDirectory(prefix="handoff-test-") as folder:
    root = Path(folder)
    briefs = root / handoff.FOLDER
    briefs.mkdir(parents=True)
    (root / "tools").mkdir()
    (root / ".githooks").mkdir()
    (root / handoff.HANDOFF).write_text(f"# Handoff\n\n{handoff.START}\n\n{handoff.END}\n")
    (root / handoff.ARCHIVE).write_text(entry("H001", "tools/vanished.py, old.gd"))
    shutil.copy(ROOT / "tools/handoff.py", root / "tools/handoff.py")
    shutil.copy(ROOT / ".githooks/pre-commit", root / ".githooks/pre-commit")

    cli = (sys.executable, "tools/handoff.py", "check")
    clean = run(root, *cli)
    check("all entries clean: archive is ignored and command is silent", clean.returncode == 0 and not clean.stdout)

    (root / "CLAUDE.md").touch()
    (briefs / "H010-ready.md").write_text(entry(
        "H010",
        "CLAUDE.md, tools/handoff.py (don't add it to tools/x.sh). Not presenter.gd's waves.\n"
        "\nRequest: delete example.gd.",
    ))
    (briefs / "H011-queued.md").write_text(entry(
        "H011", "`viewport/ui.gd` (new), a new\n `worker/test_link.py`, tools/",
        "queued (after H010)",
    ))
    findings = run(root, *cli)
    check("known top-level file, folders, excluded prose and marked new paths pass",
          findings.returncode == 0 and not findings.stdout, findings.stdout)

    invalid = briefs / "H012-bad.md"
    bad_touches = "tools/handoff.py, registry.gd, settings.tscn, viewport/tests/*.gd, worker/gone.py"
    invalid.write_text(entry("H012", bad_touches, "queued (after H010)"))
    expected = [
        "H012: Touches: bare file name: registry.gd",
        "H012: Touches: bare file name: settings.tscn",
        "H012: Touches: glob: viewport/tests/*.gd",
        "H012: Touches: path does not exist: worker/gone.py",
    ]
    findings = run(root, *cli)
    check("queued brief reports each malformed path and exits 1",
          findings.returncode == 1 and findings.stdout.splitlines() == expected, findings.stdout)
    selected = run(root, *cli, "H010", "H011")
    check("explicit IDs exclude other briefs", selected.returncode == 0 and not selected.stdout, selected.stdout)

    invalid.write_text(entry("H012", bad_touches, "answered"))
    findings = run(root, *cli)
    selected = run(root, *cli, "H012")
    check("default skips answered briefs and an explicit ID checks them",
          findings.returncode == 0 and not findings.stdout
          and selected.returncode == 1 and selected.stdout.splitlines() == expected, selected.stdout)

    run(root, "git", "init", "-q", "-b", "fixture", must_pass=True)
    run(root, "git", "add", "-A", must_pass=True)
    git_commit = ("git", "-c", "core.hooksPath=.githooks", "-c", "user.email=t@example.invalid",
                  "-c", "user.name=Tester", "commit", "-qm", "fixture")
    baseline = run(root, *git_commit)
    check("hook accepts clean staged open and queued entries", baseline.returncode == 0, baseline.stderr)

    invalid.write_text(entry("H012", bad_touches))
    run(root, "git", "add", str(invalid.relative_to(root)), must_pass=True)
    invalid.write_text(entry("H012", bad_touches, "answered"))
    rejected = run(root, *git_commit)
    check("hook rejects a staged Ready brief even with an answered worktree copy",
          rejected.returncode == 1 and (rejected.stderr + rejected.stdout).splitlines() == expected,
          rejected.stderr + rejected.stdout)

    invalid.write_text(entry("H012", "worker/gone.py (new)"))
    run(root, "git", "add", str(invalid.relative_to(root)), must_pass=True)
    accepted = run(root, *git_commit)
    check("hook accepts the corrected staged Ready brief", accepted.returncode == 0, accepted.stderr)

    invalid.write_text(entry("H012", bad_touches))
    (root / handoff.ARCHIVE).write_text(entry("H002", "again.gd"))
    run(root, "git", "add", handoff.ARCHIVE, must_pass=True)
    accepted = run(root, *git_commit)
    check("hook ignores untouched briefs and archive wording", accepted.returncode == 0, accepted.stderr)

print(f"HANDOFF TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
raise SystemExit(0 if all(RESULTS) else 1)
