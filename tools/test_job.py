#!/usr/bin/env python3
"""Checks tools/job.py (the job queue, P24) and integrate.py's cleanup after a merge, on throwaway repositories.
Summary line: JOB TESTS: N passed, M failed."""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import integrate
import integrator
import job

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))


def sh(cwd, *args, env=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env)


def entry(hid, who, status, touches, subject="a job"):
    return (f"### {hid} — {subject}\n\nAuthor: Claude (integrator) | Date: 2026-11-22 | Status: {status} | For: {who}\n\n"
            f"Touches: {touches}\n\nRequest: do it.\n")


BOARD = f"""# Work board

Order: H001, H002, H003, H005, H004, H006

## Jobs

{job.START}

(none)

{job.END}

## Notes

- none
"""


def repo():
    base = tempfile.mkdtemp(prefix="job-test-")
    root = os.path.join(base, "repo")
    os.makedirs(os.path.join(root, "docs", "handoff"))
    sh(root, "git", "init", "-q", "-b", "main")
    sh(root, "git", "config", "user.email", "t@example.invalid"); sh(root, "git", "config", "user.name", "t")
    files = {
        "H001-first-job.md": entry("H001", "Claude", "open", "tools/a.py (new), docs/x.md.", "T1: first"),
        "H002-second-job.md": entry("H002", "Claude", "open", "tools/a.py.", "T2: second"),
        "H003-third-job.md": entry("H003", "either", "open", "tools/b.py.", "T3: third"),
        "H004-queued-job.md": entry("H004", "Codex", "queued (after H001)", "tools/d.py.", "T4: queued"),
        "H005-codex-job.md": entry("H005", "Codex", "open", "tools/c.py.", "T5: codex's"),
        "H006-claimed-job.md": entry("H006", "Claude", "open", "tools/e.py.", "T6: claimed by hand"),
        "H007-a-note.md": entry("H007", "the integrator", "open", "nothing.", "where things stand"),
    }
    for n, t in files.items():
        open(os.path.join(root, "docs", "handoff", n), "w").write(t)
    open(os.path.join(root, "BOARD.md"), "w").write(BOARD)
    open(os.path.join(root, "docs", "decision-log.md"), "w").write(
        "# Log\n\n## Work list\n\n| # | Item | Status |\n|---|---|---|\n| T1 | a | Open |\n")
    open(os.path.join(root, "docs", "agent-handoff.md"), "w").write(
        "# Handoff\n\n## Open exchanges\n\n<!-- open list: built from docs/handoff/ by tools/handoff.py; don't edit by "
        "hand -->\n\n(none open)\n\n<!-- end of open list -->\n\n## Archived\n")
    open(os.path.join(root, "docs", "handoff-archive.md"), "w").write("# Archive\n")
    sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "base")
    return base, root


def run(fn, *a, **k):
    out = []
    r = fn(*a, out=out.append, **k)
    return r, "\n".join(out)


def commit(cwd, msg, when=None):
    env = dict(os.environ)
    if when:
        stamp = f"@{int(when)} +0000"
        env.update(GIT_COMMITTER_DATE=stamp, GIT_AUTHOR_DATE=stamp)
    sh(cwd, "git", "add", "-A")
    return sh(cwd, "git", "commit", "-qm", msg, env=env)


def state(root):
    return job.read_state(job.state_path(root))


base, root = repo()
sh(root, "git", "branch", "claude/h006-claimed-job")        # a job claimed the old way, by making its branch

# --- take ---
r, out = run(job.take, root, "claude", "s1")
wt1 = os.path.realpath(job.worktree_for(root, "H001"))
check("take gives the first Ready job in the board's order", r == "H001", out)
check("take makes the worktree and branch from main", os.path.isdir(wt1) and
      sh(wt1, "git", "branch", "--show-current").stdout.strip() == "claude/h001-first-job")
check("take prints the handoff", "Request: do it." in out and "### H001" in out, out)
s = state(root)["jobs"]["H001"]
check("take records who, when, branch and worktree", s["state"] == "in progress" and s["session"] == "s1"
      and s["worktree"] == wt1 and s["taken"] > 0)
r, out = run(job.take, root, "claude", "s1")
check("one job per session: a second take is refused", r is None and "already holds H001" in out, out)
r, out = run(job.take, root, "claude", "s2")
check("a job whose files overlap one in progress is passed over", "H002: overlaps H001 (tools/a.py)" in out, out)
check("... and the next one that doesn't is taken (For: either counts)", r == "H003", out)
r, out = run(job.take, root, "codex", "c1")
check("Codex gets its own job", r == "H005", out)
r, out = run(job.take, root, "codex", "c2")
check("queued jobs aren't taken: nothing Ready for Codex", r is None and "nothing Ready for codex" in out, out)
r, out = run(job.take, root, "claude", "s3")
check("a job with a branch made by hand counts as claimed", r is None and "H006: claimed by branch" in out, out)
check("the state lives in git's common folder, shared by every worktree",
      job.state_path(wt1) == job.state_path(root) and job.state_path(root).endswith(os.path.join(".git", "shopsketch-jobs.json")))

# --- the switch: beats from commands, commits and test runs ---
now = time.time()
j = state(root)["jobs"]["H001"]
check("a fresh job isn't stale", not job.stale(j, job.activity(root, j, now, procs=[]), now))
later = now + job.DEADLINE + 120
check("30 minutes with no beat: stale", job.stale(j, job.activity(root, j, later, procs=[]), later))
open(os.path.join(wt1, "tools-a.txt"), "w").write("work\n")
commit(wt1, "work", when=later - 60)
check("a commit on the job's branch is a beat", not job.stale(j, job.activity(root, j, later, procs=[]), later))
r, out = run(job.beat, wt1, now=later + job.DEADLINE)
j = state(root)["jobs"]["H001"]
check("job.py beat pushes the deadline back", r == "H001" and j["beat"] == later + job.DEADLINE, out)
far = later + 3 * job.DEADLINE
j["test"] = {"at": far - 10}
check("a test run is a beat", not job.stale(j, job.activity(root, j, far, procs=[]), far))
j["test"] = {}
check("a process still running in the worktree is a beat", not job.stale(j, job.activity(root, j, far, procs=[(1, 5, "Godot")]), far))
check("... but not one that looks hung", job.stale(j, job.activity(root, j, far, procs=[(1, job.HUNG_AFTER, "Godot")]), far))

# check: lists what runs from the worktree and flags the hung
script = os.path.join(wt1, "quicktest.sh")
open(script, "w").write("#!/bin/sh\nsleep 30\n"); os.chmod(script, 0o755)
p = subprocess.Popen(["/bin/sh", script], cwd=wt1, start_new_session=True, stdout=subprocess.DEVNULL)
time.sleep(0.5)
old = job.HUNG_AFTER; job.HUNG_AFTER = 0
r, out = run(job.check, wt1)
job.HUNG_AFTER = old
os.killpg(p.pid, 9); p.wait(); os.remove(script)
check("check lists the worktree's processes and flags one that looks hung", f"HUNG? pid {p.pid}" in out, out)
check("check beats", "H001: beat" in out, out)

# --- wait ---
wt3 = os.path.realpath(job.worktree_for(root, "H003"))
r, out = run(job.wait, wt3, "which name?", now=now)
j = state(root)["jobs"]["H003"]
check("wait marks the job waiting on William", j["state"] == "waiting" and j["question"] == "which name?", out)
check("a waiting job is never stale", not job.stale(j, job.activity(root, j, far, procs=[]), far))
run(job.beat, wt3, now=now + 5)
check("the next beat turns the switch back on", state(root)["jobs"]["H003"]["state"] == "in progress")
run(job.wait, wt3, "again?", now=now + 10)
open(os.path.join(wt3, "b.txt"), "w").write("b\n")
commit(wt3, "answer came", when=now + 100)
j = state(root)["jobs"]["H003"]
job.refresh(root, j, now + 200, procs=[])
check("a commit after the wait counts as that beat", j["state"] == "in progress")

# --- done's refusals ---
job.QUICKTEST = ["sh", "-c", "exit 1"]
hpath = os.path.join(wt1, "docs", "handoff", "H001-first-job.md")
r, out = run(job.done, wt1)
check("done refuses with no response in the handoff", not r and "has no response" in out, out)
open(hpath, "a").write("\nResponse — Claude (worker), 2026-11-22: built it.\n")
r, out = run(job.done, wt1)
check("done refuses unless Status is answered", not r and "Status to answered" in out, out)
body = open(hpath).read()
open(hpath, "w").write(body.replace("Status: open", "Status: answered"))
r, out = run(job.done, wt1)
check("done refuses with uncommitted changes", not r and "uncommitted" in out, out)
commit(wt1, "answered")
r, out = run(job.done, wt1)
check("done runs the quick test when the latest commit has no pass, and refuses on a failure",
      not r and "QUICK TEST FAILED" in out and "refused" in out, out)
job.QUICKTEST = ["true"]
r, out = run(job.test, wt1)
head = sh(wt1, "git", "rev-parse", "HEAD").stdout.strip()
check("job.py test records a pass for the latest commit", r and state(root)["jobs"]["H001"]["test"]["commit"] == head, out)
open(os.path.join(wt1, "more.txt"), "w").write("x\n"); commit(wt1, "one more")
job.QUICKTEST = ["sh", "-c", "exit 1"]
r, out = run(job.done, wt1)
check("a pass on an older commit doesn't count", not r and "no quick-test pass recorded" in out, out)
job.QUICKTEST = ["true"]
r, out = run(job.done, wt1)
j = state(root)["jobs"]["H001"]
check("done marks the job done once all is in order", r and j["state"] == "done" and "ready for review: H001" in out, out)
check("done tells the integrator (an event in the queue)", any(e["kind"] == "done" and e["job"] == "H001"
                                                              for e in state(root)["events"]))
r, out = run(job.take, root, "claude", "s1")
check("a session whose job is done may take the next", r is None and "already holds" not in out, out)

# --- watch ---
jobs, order = job.main_view(root)
lines = []
with job.locked(job.state_path(root)) as st:
    st["jobs"]["H005"]["beat"] = st["jobs"]["H005"]["taken"] = 0
r = job.watch(root, once=True, out=lines.append, now=far)
text = "\n".join(lines)
check("watch reports a done job", "done: H001 on claude/h001-first-job" in text, text)
check("watch reports a stale job", "stale: H005 (codex)" in text, text)
check("watch reports an empty queue for an agent", "queue empty for Codex" in text and "queue empty for Claude" in text, text)
run(job.wait, wt3, "a or b?", now=now + 500)
lines2 = []
job.watch(root, once=True, out=lines2.append, now=far)
check("watch reports a job waiting on William", any("waiting: H003 asks William: a or b?" in l for l in lines2), lines2)
r, out = run(job.return_job, root, "H001", "the test name is wrong")
lines3 = []
job.watch(root, once=True, out=lines3.append)
check("watch reports a returned job", any("returned: H001" in l for l in lines3), lines3)
k1 = set(job.conditions(root, state(root), jobs, order, time.time(), procs={"H005": []}))
k2 = set(job.conditions(root, state(root), jobs, order, time.time(), procs={"H005": []}))
check("nothing new, no new events (keys are stable between looks)", k1 == k2)

# --- returned resumes ---
sh(root, "git", "worktree", "remove", "--force", wt1)
r, out = run(job.take, root, "claude", "s4")
check("a returned job comes first and resumes its branch", r == "H001" and os.path.isdir(wt1) and
      sh(wt1, "git", "branch", "--show-current").stdout.strip() == "claude/h001-first-job"
      and os.path.isfile(os.path.join(wt1, "more.txt")), out)
check("... with the integrator's notes", "the test name is wrong" in out, out)

# --- the board ---
st = state(root)
text = job.board_text(BOARD, root, st, time.time())
rows = [l for l in text.split("\n") if l.startswith("| H")]
check("board: one row per job, in the Order line's order, notes left out",
      [r.split("|")[1].strip() for r in rows] == ["H001", "H002", "H003", "H005", "H004", "H006"], rows)
row = {r.split("|")[1].strip(): r for r in rows}
check("board: live state shown (in progress, waiting)", "In progress (claude" in row["H001"]
      and "Waiting on William" in row["H003"], rows)
check("board: Ready and Queued from the handoffs' Status, with what a job waits for",
      "**Ready**" in row["H002"] and "Queued" in row["H004"] and row["H004"].rstrip().endswith("| H001 |"), rows)
check("board: a job claimed by a hand-made branch shows the branch", "Claimed: branch claude/h006-claimed-job" in row["H006"], rows)
check("board: the text outside the table is kept", text.startswith("# Work board\n\nOrder:") and "- none" in text)
r, out = run(job.board, root)
check("job.py board rewrites BOARD.md", r and "| H005 |" in open(os.path.join(root, "BOARD.md")).read(), out)

# --- integrate.py cleans up after a merge ---
open(os.path.join(wt1, "docs", "handoff", "H001-first-job.md"), "a").write("\nResponse — again.\n")
commit(wt1, "fixed the test name")
sh(root, "git", "checkout", "-q", "BOARD.md")
integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
buf = io.StringIO()
cwd = os.getcwd(); os.chdir(root)
try:
    with contextlib.redirect_stdout(buf):
        rc = integrate.main(["claude/h001-first-job", "--as", "tester", "--no-gate"])
finally:
    os.chdir(cwd)
log = buf.getvalue()
check("integrate.py merges the job's branch", rc == 0 and "committed" in log, log)
check("... removes its worktree", not os.path.isdir(wt1), log)
check("... deletes its branch", "claude/h001-first-job" not in sh(root, "git", "branch").stdout, log)
check("... and marks the job merged", state(root)["jobs"]["H001"]["state"] == "merged", log)
board_now = sh(root, "git", "show", "HEAD:BOARD.md").stdout
check("... and the merge commit's board is rebuilt (the merged job is gone from it)",
      "| H001 | Claude" not in board_now and "| H002 |" in board_now, board_now)

sh(root, "git", "branch", "small-fixes")
sf = os.path.join(base, "small-fixes-wt"); sh(root, "git", "worktree", "add", "-q", sf, "small-fixes")
r, out = run(job.merged, root, "small-fixes")
check("merged() keeps a standing branch (small-fixes) and its worktree (P22)",
      os.path.isdir(sf) and "small-fixes" in sh(root, "git", "branch").stdout, out)
sh(root, "git", "worktree", "remove", "--force", sf)
for w in (wt3, job.worktree_for(root, "H005")):
    sh(root, "git", "worktree", "remove", "--force", w)
shutil.rmtree(base)
print(f"JOB TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
sys.exit(0 if all(RESULTS) else 1)
