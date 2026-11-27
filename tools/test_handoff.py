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
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, condition, detail=""):
    RESULTS.append(bool(condition))
    if not condition or VERBOSE:
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

with TemporaryDirectory(prefix="handoff-archive-test-") as folder:
    base = Path(folder)
    root = base / "repo"
    bare = base / "origin.git"
    briefs = root / handoff.FOLDER
    briefs.mkdir(parents=True)
    (root / "tools").mkdir()
    (root / ".githooks").mkdir()
    (root / handoff.HANDOFF).write_text(
        f"# Handoff\n\n## Open exchanges\n\n{handoff.START}\n\n(none open)\n\n{handoff.END}\n\n## Archived\n"
    )
    (root / handoff.ARCHIVE).write_text("# Archive\n")
    (root / "BOARD.md").write_text("# Board\n")
    (root / "other.txt").write_text("v1\n")
    for hid, slug_name in (("H020", "plain"), ("H021", "commit"), ("H022", "push")):
        (briefs / f"{hid}-{slug_name}.md").write_text(
            f"### {hid} — Note {slug_name}\n\nAuthor: Gemini | Date: 2026-11-23 | Status: open | For: the integrator\n\n"
            f"Touches: nothing.\n\nBody for {hid}.\n"
        )
    shutil.copy(ROOT / "tools/handoff.py", root / "tools/handoff.py")
    shutil.copy(ROOT / ".githooks/pre-commit", root / ".githooks/pre-commit")
    run(root, sys.executable, "tools/handoff.py", "list", must_pass=True)
    run(root, "git", "init", "-q", "-b", "main", must_pass=True)
    run(root, "git", "config", "user.email", "t@example.invalid", must_pass=True)
    run(root, "git", "config", "user.name", "Tester", must_pass=True)
    run(root, "git", "add", "-A", must_pass=True)
    run(root, "git", "commit", "-qm", "base", must_pass=True)
    run(base, "git", "init", "-q", "--bare", str(bare), must_pass=True)
    run(root, "git", "remote", "add", "origin", str(bare), must_pass=True)
    run(root, "git", "push", "-q", "origin", "main", must_pass=True)

    # 1. Plain archive moves the entry without committing.
    res = run(root, sys.executable, "tools/handoff.py", "archive", "H020")
    check("plain archive moves entry and leaves git history unchanged",
          res.returncode == 0 and "archived H020" in res.stdout and "committed" not in res.stdout
          and not (briefs / "H020-plain.md").exists()
          and "### H020 — Note plain" in (root / handoff.ARCHIVE).read_text()
          and run(root, "git", "rev-list", "--count", "HEAD").stdout.strip() == "1",
          res.stdout + res.stderr)
    run(root, "git", "add", "-A", must_pass=True)
    run(root, "git", "commit", "-qm", "commit H020", must_pass=True)
    run(root, "git", "push", "-q", "origin", "main", must_pass=True)

    # 2. Refuses --commit when unrelated changes are staged, leaving H021 untouched.
    (root / "other.txt").write_text("v2\n")
    run(root, "git", "add", "other.txt", must_pass=True)
    res = run(root, sys.executable, "tools/handoff.py", "archive", "H021", "--commit")
    check("archive --commit refuses when unrelated files are staged without mutating H021",
          res.returncode != 0 and "staged changes" in (res.stdout + res.stderr)
          and (briefs / "H021-commit.md").exists(), res.stdout + res.stderr)
    run(root, "git", "reset", "-q", "HEAD", "other.txt", must_pass=True)

    # 3. Refuses --commit when BOARD.md is dirty on main, leaving H021 untouched.
    (root / "BOARD.md").write_text("# Board dirty\n")
    res = run(root, sys.executable, "tools/handoff.py", "archive", "H021", "--commit")
    check("archive --commit refuses when BOARD.md is dirty on main without mutating H021",
          res.returncode != 0 and "uncommitted changes" in (res.stdout + res.stderr)
          and (briefs / "H021-commit.md").exists(), res.stdout + res.stderr)
    (root / "BOARD.md").write_text("# Board\n")

    # 4. Refuses --commit when .git is not writable (sandbox simulation), leaving H021 untouched.
    git_dir = root / ".git"
    orig_mode = git_dir.stat().st_mode
    try:
        git_dir.chmod(0o555)
        res = run(root, sys.executable, "tools/handoff.py", "archive", "H021", "--commit")
    finally:
        git_dir.chmod(orig_mode)
    check("archive --commit refuses when .git is unwritable and leaves working tree untouched",
          res.returncode != 0 and "not writable" in (res.stdout + res.stderr)
          and (briefs / "H021-commit.md").exists(), res.stdout + res.stderr)

    # 5. archive --commit succeeds even with an unrelated unstaged file (does not stage other.txt).
    res = run(root, sys.executable, "tools/handoff.py", "archive", "H021", "--commit")
    head_msg = run(root, "git", "log", "-1", "--format=%s").stdout.strip()
    committed_files = set(run(root, "git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").stdout.splitlines())
    check("archive --commit stages and commits only the three archive files",
          res.returncode == 0 and "archived H021" in res.stdout and "committed " in res.stdout
          and head_msg == "Archive H021 — Note commit"
          and committed_files == {handoff.HANDOFF, handoff.ARCHIVE, f"{handoff.FOLDER}/H021-commit.md"}
          and "other.txt" in run(root, "git", "status", "--porcelain").stdout,
          res.stdout + res.stderr + " | " + str(committed_files))
    run(root, "git", "checkout", "--", "other.txt", must_pass=True)

    # 6. Refuses --push off main without mutating H022.
    run(root, "git", "checkout", "-qb", "feature", must_pass=True)
    res = run(root, sys.executable, "tools/handoff.py", "archive", "H022", "--push")
    check("archive --push refuses off main and leaves H022 untouched",
          res.returncode != 0 and "not 'main'" in (res.stdout + res.stderr)
          and (briefs / "H022-push.md").exists(), res.stdout + res.stderr)
    run(root, "git", "checkout", "-q", "main", must_pass=True)

    # 7. archive --push on main archives, commits, and pushes origin/main in one command.
    res = run(root, sys.executable, "tools/handoff.py", "archive", "H022", "--push")
    local_sha = run(root, "git", "rev-parse", "main").stdout.strip()
    remote_sha = run(base, "git", "--git-dir", str(bare), "rev-parse", "main").stdout.strip()
    check("archive --push on main archives, commits and pushes origin/main",
          res.returncode == 0 and "archived H022" in res.stdout and "committed " in res.stdout
          and "pushed main" in res.stdout and local_sha == remote_sha
          and not (briefs / "H022-push.md").exists(),
          res.stdout + res.stderr)

    # 8. Unknown flag exits 2.
    res = run(root, sys.executable, "tools/handoff.py", "archive", "H022", "--bogus")
    check("archive rejects unknown flags with exit 2", res.returncode == 2, res.stdout + res.stderr)

with TemporaryDirectory(prefix="handoff-tidy-test-") as folder:
    root = Path(folder)
    briefs = root / handoff.FOLDER
    briefs.mkdir(parents=True)
    (root / "tools").mkdir()
    (root / ".githooks").mkdir()
    (root / "README.txt").write_text("hi\n")
    shutil.copy(ROOT / "tools/handoff.py", root / "tools/handoff.py")
    shutil.copy(ROOT / ".githooks/pre-commit", root / ".githooks/pre-commit")

    # Build 12 archived entries in docs/handoff-archive.md.
    arch_parts = ["# Archive\n"]
    for n in range(1, 13):
        hid = f"H{n:03d}"
        arch_parts.append(f"### {hid} — Item {n}\n\nAuthor: Codex | Status: resolved\n\nResolution: done {n}.\n")
    (root / handoff.ARCHIVE).write_text("\n".join(arch_parts))
    (root / handoff.HANDOFF).write_text(
        f"# Handoff\n\n- [Readme](../README.txt)\n\n## Open exchanges\n\n{handoff.START}\n\n(none open)\n\n{handoff.END}\n\n"
        "## Archived\n\n- H001 — Item 1. Resolved: done 1.\n\n## Entry template\n\nTemplate.\n"
    )

    # 1. --check fails when Archived is out of date, then tidy fixes it and keeps last 10 + Older: line.
    res = run(root, sys.executable, "tools/handoff.py", "tidy", "--check")
    check("tidy --check fails when Archived is out of date", res.returncode == 1 and "Archived" in res.stdout, res.stdout)
    res = run(root, sys.executable, "tools/handoff.py", "tidy")
    hand_text = (root / handoff.HANDOFF).read_text()
    archived_bullets = [l for l in hand_text.splitlines() if l.startswith("- H")]
    check("tidy keeps last 10 archived entries newest-first with Older summary",
          res.returncode == 0 and len(archived_bullets) == 10
          and archived_bullets[0].startswith("- H012 — Item 12. Resolved: done 12.")
          and archived_bullets[-1].startswith("- H003 — Item 3. Resolved: done 3.")
          and 'Older: docs/handoff-archive.md (12 entries; find one with grep "^### H0NN" docs/handoff-archive.md)' in hand_text
          and "## Entry template" in hand_text,
          hand_text)
    res = run(root, sys.executable, "tools/handoff.py", "tidy", "--check")
    check("tidy --check passes on a tidy file with valid relative links", res.returncode == 0 and not res.stdout, res.stdout)

    # 2. Refuses to cut an archived line whose heading is missing from docs/handoff-archive.md.
    (root / handoff.HANDOFF).write_text(
        hand_text.replace("- H012 — Item 12.", "- H999 — Missing.\n- H012 — Item 12.")
    )
    res = run(root, sys.executable, "tools/handoff.py", "tidy")
    check("tidy refuses to cut an archived entry missing from archive, naming it",
          res.returncode != 0 and "H999" in (res.stdout + res.stderr)
          and "- H999 — Missing." in (root / handoff.HANDOFF).read_text(),
          res.stdout + res.stderr)

    # 3. Rebuilds Archived cleanly even with git merge conflict markers inside Archived.
    (root / handoff.HANDOFF).write_text(
        hand_text.replace(
            "- H012 — Item 12. Resolved: done 12.",
            "<<<<<<< HEAD\n- H012 — Item 12. Resolved: done 12.\n=======\n- H011 — Item 11. Resolved: done 11.\n>>>>>>> branch",
        )
    )
    res = run(root, sys.executable, "tools/handoff.py", "tidy")
    rebuilt = (root / handoff.HANDOFF).read_text()
    check("tidy rebuilds Archived across merge conflict markers",
          res.returncode == 0 and "<<<<<<<" not in rebuilt and ">>>>>>>" not in rebuilt
          and "- H012 — Item 12. Resolved: done 12." in rebuilt,
          rebuilt)

    # 4. Broken relative link is reported with line number and fails tidy --check.
    (root / handoff.HANDOFF).write_text(rebuilt.replace("(../README.txt)", "(../NO_SUCH_FILE.md)"))
    res = run(root, sys.executable, "tools/handoff.py", "tidy", "--check")
    check("tidy --check fails on a broken relative link and prints its line",
          res.returncode == 1 and "NO_SUCH_FILE.md" in res.stdout and f"{handoff.HANDOFF}:3:" in res.stdout,
          res.stdout)

print(f"HANDOFF TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
raise SystemExit(0 if all(RESULTS) else 1)
