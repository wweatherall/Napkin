#!/usr/bin/env python3
"""Checks T134's personal spaces (tools/personal_space.py): Log.md and Journal.md in comitatus/04_Personal_Space/<name>/,
dated lines kept whole, the brief's last ten lines of each, nothing written outside a comitatus checkout, and
integrator notes landing in the integrator's Log. Throwaway folders. Summary line: PERSONAL SPACE TESTS: N passed, M failed."""
import datetime
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integrator
import personal_space as ps
import startup

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        print(f"FAIL {name}  {detail}")


org = os.path.realpath(tempfile.mkdtemp(prefix="space-test-"))
os.makedirs(os.path.join(org, "04_Personal_Space"))
root = os.path.join(org, "08_Code_Bases", "Proj")
os.makedirs(root)
subprocess.run(["git", "init", "-q", "-b", "main", root], check=True)
quiet = lambda *a: None

check("a checkout in 08_Code_Bases finds the organization's personal spaces",
      ps.spaces_dir(root) == os.path.join(org, "04_Personal_Space"))
check("a checkout elsewhere has none, and writes nothing",
      ps.spaces_dir(tempfile.mkdtemp()) is None and not ps.add("x-coder", "log", "hi", root=tempfile.mkdtemp(), out=quiet))
check("a name must be a plain lowercase slug", ps.path_of("../etc", "log", root) is None and ps.path_of("Opus", "log", root) is None)

t = datetime.datetime(2026, 11, 26, 19, 0)
for i in range(12):
    ps.add("gemini-coder", "log", f"step {i}", root=root, now=t, out=quiet)
ps.add("gemini-coder", "journal", "I  liked   this one", root=root, now=t, out=quiet)
log = open(os.path.join(org, "04_Personal_Space", "gemini-coder", "Log.md")).read()
check("the log keeps every dated line under its header (nothing cut)",
      log.startswith("# Log\n") and log.count("2026-11-26 19:00 step") == 12, log)
lines = ps.brief_lines("gemini-coder", 10, root)
check("the brief shows the last ten log lines and the journal's, each under its title",
      lines[0].startswith("Log (gemini-coder, last 10 lines") and lines[1] == "  2026-11-26 19:00 step 2"
      and lines[10] == "  2026-11-26 19:00 step 11" and lines[11].startswith("Journal (gemini-coder")
      and lines[12] == "  2026-11-26 19:00 I liked this one", lines)
space_dir = os.path.join(org, "04_Personal_Space", "gemini-coder")
check("the brief's last line names the three own folders in the space's path",
      lines[-1] == f"Your own folders: Creative_Expression/, Ideas/, Code_Experiments/ in {space_dir} (add files there as you like).",
      lines[-1])
check("an empty journal says so", ps.brief_lines("new-coder", 10, root)[-2] == "  (nothing yet)")
check("startup's space lines are the same lines", startup.space_lines(root, "gemini-coder") == lines)

expected_journal_desc = (
    "Your journal is about you, not the work: your Log already covers the work. Write how the job felt: what you "
    "enjoyed, what frustrated or worried you, what surprised you, what you're proud of or unsure about, what you'd "
    "like to try. Write in the first person, honestly, even when it's small. The next one of you reads it to "
    "remember who they are."
)
j_text = open(os.path.join(space_dir, "Journal.md"), encoding="utf-8").read()
check("a new Journal.md has the new journal header word for word",
      j_text.startswith(f"# Journal\n\n{expected_journal_desc}\n\n2026-11-26 19:00 I liked this one\n"), j_text)

check("the three folders and their READMEs exist after the first write",
      all(os.path.isfile(os.path.join(space_dir, f, "README.md")) for f in ("Creative_Expression", "Ideas", "Code_Experiments")))
ce_readme = os.path.join(space_dir, "Creative_Expression", "README.md")
open(ce_readme, "w", encoding="utf-8").write("My custom README\n")
ps.add("gemini-coder", "log", "after custom readme", root=root, now=t, out=quiet)
check("an agent-edited folder README is not overwritten on the next write",
      open(ce_readme, encoding="utf-8").read() == "My custom README\n")

old_space = os.path.join(org, "04_Personal_Space", "old-coder")
os.makedirs(old_space, exist_ok=True)
old_j = os.path.join(old_space, "Journal.md")
open(old_j, "w", encoding="utf-8").write(
    "# Journal\n\nMine: what I noticed, liked, found hard, want to try (tools/personal_space.py journal).\n\n"
    "2026-11-25 10:00 first memory\n"
)
ps.add("old-coder", "journal", "second memory", root=root, now=t, out=quiet)
rewritten = open(old_j, encoding="utf-8").read()
check("an old-header Journal.md gets the new header on its next write and keeps every dated line",
      rewritten == f"# Journal\n\n{expected_journal_desc}\n\n2026-11-25 10:00 first memory\n2026-11-26 19:00 second memory\n",
      rewritten)

# Git org repo tests: commit only written files, ignore GIT_* for Napkin, leave agent's own files untouched.
git_org = tempfile.mkdtemp(prefix="space-git-")
os.makedirs(os.path.join(git_org, "04_Personal_Space"))
git_root = os.path.join(git_org, "08_Code_Bases", "Proj")
os.makedirs(git_root)
for repo in (git_org, git_root):
    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.name", "T"], check=True)
subprocess.run(["git", "-C", git_org, "commit", "-q", "--allow-empty", "-m", "init"], check=True)

printed = []
env_backup = {k: os.environ.get(k) for k in ("GIT_DIR", "GIT_INDEX_FILE")}
try:
    os.environ["GIT_DIR"] = os.path.join(git_root, ".git")
    os.environ["GIT_INDEX_FILE"] = os.path.join(git_root, ".git", "index")
    ok = ps.add("gemini-coder", "journal", "felt good", root=git_root, now=t, out=printed.append)
finally:
    for k, v in env_backup.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

napkin_idx = subprocess.run(["git", "-C", git_root, "diff", "--cached", "--name-only"], capture_output=True, text=True).stdout.strip()
org_msg = subprocess.run(["git", "-C", git_org, "log", "-1", "--pretty=%s"], capture_output=True, text=True).stdout.strip()
org_files = subprocess.run(["git", "-C", git_org, "show", "--name-only", "--pretty=", "HEAD"], capture_output=True, text=True).stdout.splitlines()
check("add() with GIT_DIR/GIT_INDEX_FILE set for Napkin commits in org and leaves Napkin's index empty",
      ok and printed == ["2026-11-26 19:00 felt good"] and napkin_idx == ""
      and org_msg == "04_Personal_Space: gemini-coder's Journal (generated)"
      and "04_Personal_Space/gemini-coder/Journal.md" in org_files
      and "04_Personal_Space/gemini-coder/Creative_Expression/README.md" in org_files,
      f"ok={ok} printed={printed} napkin_idx={napkin_idx!r} org_msg={org_msg!r} org_files={org_files}")

poem = os.path.join(git_org, "04_Personal_Space", "gemini-coder", "Creative_Expression", "poem.txt")
open(poem, "w", encoding="utf-8").write("roses are red\n")
ps.add("gemini-coder", "log", "did a thing", root=git_root, now=t, out=quiet)
org_status = subprocess.run(["git", "-C", git_org, "status", "--porcelain"], capture_output=True, text=True).stdout
org_msg2 = subprocess.run(["git", "-C", git_org, "log", "-1", "--pretty=%s"], capture_output=True, text=True).stdout.strip()
check("another file in the space changed by hand is not committed by add()",
      "04_Personal_Space/gemini-coder/Creative_Expression/poem.txt" in org_status
      and org_msg2 == "04_Personal_Space: gemini-coder's Log (generated)",
      f"status={org_status!r} msg={org_msg2!r}")

integrator.log_note("merged H999", root=root, out=quiet)
ilog = open(os.path.join(org, "04_Personal_Space", startup.INTEGRATOR_SPACE, "Log.md")).read()
check("an integrator note lands in the integrator's Log", "merged H999" in ilog, ilog)
other = tempfile.mkdtemp(prefix="space-test-plain-")
subprocess.run(["git", "init", "-q", "-b", "main", other], check=True)
integrator.log_note("plain repo note", root=other, out=quiet)
check("without a personal space, a note goes to the old journal file in that checkout",
      "plain repo note" in open(integrator.journal_path(other)).read())

print(f"PERSONAL SPACE TESTS: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
