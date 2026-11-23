#!/usr/bin/env python3
"""Checks tools/job.py (the job queue, P24) and integrate.py's cleanup after a merge, on throwaway repositories.
Summary line: JOB TESTS: N passed, M failed."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

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
check("take makes the worktree and branch from main, with a scratch/ folder", os.path.isdir(os.path.join(wt1, "scratch")) and
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

# --- wrong-checkout guard (T102), including both shell entry points before any test starts ---
guard_env = {k: v for k, v in os.environ.items() if k not in
             ("CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID", "CODEX_THREAD_ID", "SHOPSKETCH_ANY_CHECKOUT")}
for checkout in (root, wt1):
    folder = os.path.join(checkout, "tools")
    os.makedirs(folder, exist_ok=True)
    for name in ("job.py", "handoff.py"):
        shutil.copy(os.path.join(HERE, name), folder)
    for name, marker in (("quicktest.sh", "START=$SECONDS"), ("gate.sh", "OUT=$(mktemp")):
        prefix = open(os.path.join(HERE, name)).read().split(marker, 1)[0]
        open(os.path.join(folder, name), "w").write(prefix + "echo tests-started\n")


def guard_check(name, checkout=root, extra=None, refused=False):
    for script in ("quicktest.sh", "gate.sh"):
        result = sh(checkout, "bash", "tools/" + script, env=dict(guard_env, **(extra or {})))
        expected = f"you're in the main checkout; your job H001 is in {wt1}: cd there and run it again\n"
        check(f"{script}: {name}", result.returncode == (1 if refused else 0) and
              result.stdout == (expected if refused else "tests-started\n"),
              (result.returncode, result.stdout, result.stderr))


for key in ("CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID", "CODEX_THREAD_ID"):
    guard_check("refuses the main checkout and names the job's worktree (" + key + ")",
                extra={key: "s1"}, refused=True)
guard_check("runs in a job worktree", checkout=wt1, extra={"CODEX_THREAD_ID": "s1"})
guard_check("runs for a session without a job", extra={"CODEX_THREAD_ID": "integrator"})
guard_check("runs without a detectable session ID")
guard_check("allows the deliberate override", extra={"CODEX_THREAD_ID": "s1", "SHOPSKETCH_ANY_CHECKOUT": "1"})
queue = job.state_path(root)
saved_queue = open(queue).read()
os.remove(queue)
guard_check("runs with a missing queue", extra={"CODEX_THREAD_ID": "s1"})
open(queue, "w").write("not json")
guard_check("runs with a malformed queue", extra={"CODEX_THREAD_ID": "s1"})
open(queue, "w").write('{"jobs": null}')
guard_check("runs with an invalid queue structure", extra={"CODEX_THREAD_ID": "s1"})
os.remove(queue)
os.mkdir(queue)  # opening a directory as JSON fails even when tests run as root
nguard = {"CODEX_THREAD_ID": "s1"}
guard_check("runs with an unreadable queue", extra=nguard)
os.rmdir(queue)
open(queue, "w").write(saved_queue)
for checkout in (root, wt1):
    shutil.rmtree(os.path.join(checkout, "tools"))

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
# Stand-in for the bookkeeping script in this throwaway checkout. Record each invocation outside the tree.
book_runs = os.path.join(base, "bookkeeping-runs")
book_fail = os.path.join(base, "bookkeeping-fails")
os.mkdir(os.path.join(wt1, "tools"))
with open(os.path.join(wt1, "tools", "test_bookkeeping.py"), "w") as f:
    f.write(f"import os, sys\nwith open({book_runs!r}, 'a') as log: log.write('run\\n')\n"
            f"sys.exit(int(os.path.exists({book_fail!r})))\n")
job.handoff.write_list(wt1)
commit(wt1, "answered")
r, out = run(job.done, wt1)
check("done runs the quick test when the latest commit has no pass, and refuses on a failure",
      not r and "QUICK TEST FAILED" in out and "refused" in out, out)
job.QUICKTEST = ["true"]
r, out = run(job.test, wt1)
head = sh(wt1, "git", "rev-parse", "HEAD").stdout.strip()
check("job.py test records a pass for the latest commit", r and state(root)["jobs"]["H001"]["test"]["commit"] == head, out)
# Record a real pass on a sibling tip whose only difference is a handoff edit.
branch = sh(wt1, "git", "branch", "--show-current").stdout.strip()
sh(wt1, "git", "switch", "-qc", "other-pass")
open(hpath, "a").write("\nOther response.\n")
commit(wt1, "other response")
run(job.test, wt1)
sh(wt1, "git", "switch", "-q", branch)
job.QUICKTEST = ["false"]
r, out = run(job.done, wt1)
check("done reruns the quick test for a non-ancestor pass even with only a handoff difference",
      not r and "QUICK TEST FAILED" in out and not os.path.exists(book_runs), out)
job.QUICKTEST = ["true"]
run(job.test, wt1)
open(os.path.join(wt1, "more.txt"), "w").write("x\n"); commit(wt1, "one more")
job.QUICKTEST = ["sh", "-c", "exit 1"]
r, out = run(job.done, wt1)
check("a code change after a pass reruns the quick test",
      not r and "QUICK TEST FAILED" in out and not os.path.exists(book_runs), out)
job.QUICKTEST = ["true"]
_procs = job.processes
job.processes = lambda wt: [(4242, job.HUNG_AFTER + 60, "godot --quicktest")]
r, out = run(job.done, wt1)
job.processes = _procs
check("done refuses while a process from the worktree looks hung, and names it (P40)",
      not r and "pid 4242" in out and "looks hung" in out and state(root)["jobs"]["H001"]["state"] != "done", out)
run(job.test, wt1)
open(os.path.join(wt1, "more.txt"), "a").write("temporary change\n")
commit(wt1, "change code")
sh(wt1, "git", "revert", "--no-edit", "HEAD")
with patch.object(job, "test", return_value=False) as quick:
    r, out = run(job.done, wt1)
check("even a reverted code change requires the quick test", not r and quick.called and not os.path.exists(book_runs), out)
run(job.test, wt1)
passed = sh(wt1, "git", "rev-parse", "HEAD").stdout.strip()

open(hpath, "a").write("\nResponse addendum.\n")
commit(wt1, "append handoff response")
index_path = os.path.join(wt1, job.handoff.HANDOFF)
listed = open(index_path).read()
open(index_path, "w").write(listed.replace("status: answered", "status: open"))
commit(wt1, "stale open list")
with patch.object(job, "test", return_value=False) as quick:
    r, out = run(job.done, wt1)
check("a stale open list refuses reuse", not r and quick.called and "out of date" in out, out)
job.handoff.write_list(wt1)
commit(wt1, "refresh open list")

open(book_fail, "w").close()
with patch.object(job, "test", return_value=False) as quick:
    r, out = run(job.done, wt1)
check("a bookkeeping failure refuses reuse and falls back to the quick test",
      not r and quick.called and "bookkeeping check failed" in out and state(root)["jobs"]["H001"]["state"] != "done", out)
os.remove(book_fail)
job.QUICKTEST = ["false"]  # success below requires skipping the full quick test
r, out = run(job.done, wt1)
j = state(root)["jobs"]["H001"]
check("after handoff-only commits done runs only bookkeeping and names the reused pass",
      r and open(book_runs).read().splitlines() == ["run", "run"] and f"reused the quick-test pass from {passed[:7]}" in out, out)
check("done marks the job done once all is in order", r and j["state"] == "done" and "ready for review: H001" in out, out)
check("done notes a response with no Result line (T91)", "has no line \"Result:" in out, out)
check("done's closing message after a session's one job: ready for a /clear (P37)",
      "ready for a /clear" in out and "take --wait" not in out, out)
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
check("watch stays quiet about an empty queue when no worker is waiting", "queue empty for" not in text, text)
with job.locked(job.state_path(root)) as st:
    st["waiting_workers"]["c-wait"] = {"agent": "codex", "since": far - 10}
lines_empty = []
job.watch(root, once=True, out=lines_empty.append, now=far)
text_empty = "\n".join(lines_empty)
check("watch reports an empty queue only for an agent with a waiting worker",
      "queue empty for Codex: a worker is waiting with nothing Ready (check in with William)" in text_empty
      and "queue empty for Claude" not in text_empty, text_empty)
lines_stale_w = []
job.watch(root, once=True, out=lines_stale_w.append, now=far + job.WORKER_WAIT + job.WATCH_POLL + 1)
check("watch ignores and drops a stale waiting_workers entry (older than WORKER_WAIT + WATCH_POLL)",
      "queue empty for Codex" not in "\n".join(lines_stale_w)
      and "c-wait" not in state(root)["waiting_workers"], (lines_stale_w, state(root)["waiting_workers"]))
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
_cond, _poll = job.conditions, job.WATCH_POLL
looks = iter([{"a": "old event"}, {"a": "old event"}, {"a": "old event", "b": "new event"}])
job.conditions, job.WATCH_POLL = (lambda *a, **k: next(looks)), 0
lines4 = []
job.watch(root, until_new=True, out=lines4.append)
job.conditions, job.WATCH_POLL = _cond, _poll
check("watch --next says nothing about what's already true, prints the first new event and stops (H050)",
      len(lines4) == 1 and lines4[0].endswith("new event"), lines4)

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

# --- one job a session by default (P37); the count still works for any MAX_JOBS (P27's chaining) ---
check("a session takes one job by default (P37)", job.MAX_JOBS == 1, job.MAX_JOBS)
_max_jobs = job.MAX_JOBS
job.MAX_JOBS = 3
base, root = repo()


def finish(jid):
    with job.locked(job.state_path(root)) as st:
        st["jobs"][jid]["state"] = "merged"


r1, _ = run(job.take, root, "claude", "w"); finish(r1)
r2, _ = run(job.take, root, "claude", "w"); finish(r2)
r3, out = run(job.take, root, "claude", "w")
check("take counts a session's jobs", [r1, r2, r3] == ["H001", "H002", "H003"] and "job 3 of 3" in out
      and state(root)["sessions"]["w"] == ["H001", "H002", "H003"], (r1, r2, r3, out))
wt = os.path.realpath(job.worktree_for(root, "H003"))
hp = os.path.join(wt, "docs", "handoff", "H003-third-job.md")
body = open(hp).read()
open(hp, "w").write(body.replace("Status: open", "Status: answered") + "\nResponse: done.\n")
commit(wt, "answered")
job.QUICKTEST = ["true"]
r, out = run(job.done, wt)
check("done's closing message at the 3rd job: tell William you're ready for a /clear",
      r and "ready for a /clear" in out and "take --wait" not in out, out)
r, out = run(job.take, root, "claude", "w")
check("a 4th take by the same session is refused", r is None and "has done 3 jobs" in out, out)
r, out = run(job.take, root, "claude", "w2")
check("another session isn't refused", r == "H006", out)
finish("H006")
r, out = run(job.take, root, "claude", "claude")
r2, out2 = run(job.take, root, "claude", "claude")
check("the fallback session (no real ID) isn't counted", "sessions" not in state(root) or
      "claude" not in state(root)["sessions"], state(root).get("sessions"))
job.MAX_JOBS = _max_jobs
out1 = job.next_step({"sessions": {"w": ["H001"]}}, "w")
check("at the default, done after the first job says ready for a /clear (P37)",
      "ready for a /clear" in out1 and "take --wait" not in out1, out1)

clock = [0.0]
slept = []


def fake_sleep(sec):
    slept.append(sec)
    clock[0] += sec
    if len(slept) == 2:                          # a job turns Ready while it waits
        open(os.path.join(root, "docs", "handoff", "H008-late-job.md"), "w").write(
            entry("H008", "Codex", "open", "tools/z.py.", "T8: late"))
        commit(root, "H008 Ready")


run(job.take, root, "codex", "c1")                    # takes H005: nothing else Ready for Codex
r, out = run(job.take_wait, root, "codex", "c2", wait=60, poll=5, sleep=fake_sleep, clock=lambda: clock[0])
check("take --wait takes a job that turns Ready while it waits", r == "H008" and len(slept) == 2
      and "waiting up to" in out and "took H008" in out, out)
r, out = run(job.take_wait, root, "codex", "c3", wait=60, poll=5, sleep=fake_sleep, clock=lambda: clock[0])
check("take --wait stops at WORKER_WAIT with nothing", r is None and "nothing came in 1 min: stopping" in out, out)
check("... and holds no job while it waits", "c3" not in [j.get("session") for j in state(root)["jobs"].values()])
r, out = run(job.take_wait, root, "claude", "w", wait=60, poll=5, sleep=fake_sleep, clock=lambda: clock[0])
check("take --wait gives up at once when refused (the session's 3 jobs)", r is None and "has done 3" in out
      and "waiting up to" not in out, out)
# --- run: a long command can't hang unseen (P40) ---
msgs = []
check("run passes a command's exit code through", job.run(root, ["sh", "-c", "exit 3"], out=msgs.append) == 3, msgs)
msgs = []
t0 = time.time()
# A duration of this run's own (two worktrees' tests run at once and must not see each other's processes), and
# up to 5 s for the stopped processes to go (a busy machine is slow to reap them).
nap = f"sleep 31.{os.getpid()}"
rc = job.run(root, ["sh", "-c", f"{nap} & {nap}; wait"], limit=1, out=msgs.append)
for _ in range(50):
    left = subprocess.run(["pgrep", "-f", nap], capture_output=True, text=True).stdout.strip()
    if not left: break
    time.sleep(0.1)
check("run stops a command past its limit with every process it started, says HUNG, exits 124",
      rc == 124 and any(m.startswith("HUNG:") for m in msgs) and not left and time.time() - t0 < 20, (rc, msgs, left))
msgs = []
check("run says so when the command can't start", job.run(root, ["/no/such/program"], out=msgs.append) == 127
      and "can't start" in msgs[0], msgs)
# --- --help only prints the help, whatever the command ---
before = json.dumps(state(root), sort_keys=True)
for args in (["take", "--help"], ["done", "-h"], ["return", "H001", "x", "--help"],
             ["reassign", "H001", "--to", "gemini", "--help"]):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = job.main(args)
    check(f"job.py {' '.join(args)} prints the help and changes nothing",
          rc == 0 and "The job queue" in buf.getvalue() and json.dumps(state(root), sort_keys=True) == before, rc)

for w in [l.split()[1] for l in sh(root, "git", "worktree", "list", "--porcelain").stdout.split("\n")
          if l.startswith("worktree ")][1:]:
    sh(root, "git", "worktree", "remove", "--force", w)
shutil.rmtree(base)

# --- live progress streaming from run_quick / job.py test (H088) ---
base, root = repo()
run(job.take, root, "claude", "live1")
wt = os.path.realpath(job.worktree_for(root, "H001"))
os.makedirs(os.path.join(wt, "tools"), exist_ok=True)


def run_job_test_live(worktree, release_on, release_path):
    env = dict(os.environ, RELEASE=release_path)
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "job.py"), "test"],
                         cwd=worktree, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    lines, before_release, alive = [], None, False
    for raw in p.stdout:
        line = raw.rstrip("\r\n")
        lines.append(line)
        if before_release is None and line == release_on:
            alive = p.poll() is None
            before_release = list(lines)
            open(release_path, "w").close()
    rc = p.wait(timeout=15)
    return rc, lines, before_release, alive


qstub = os.path.join(wt, "tools", "quicktest.sh")
release = os.path.join(base, "release-pass")
open(qstub, "w").write("""#!/bin/bash
echo "noise before"
echo "quick: parse started"
for ((i=0; i<100; i++)); do [ -f "$RELEASE" ] && break; sleep 0.05; done
if [ ! -f "$RELEASE" ]; then echo "STUB TIMED OUT"; exit 2; fi
echo "noise middle"
echo "quick: parse passed in 1 s"
echo "features: ok | viewport: QUICK 1 passed, 0 failed"
""")
os.chmod(qstub, 0o755)
rc, lines, before_release, alive = run_job_test_live(wt, "quick: parse started", release)
check("job.py test relays the first progress line before the quick test ends",
      rc == 0 and alive and before_release == ["quick: parse started"], (rc, alive, before_release, lines))
check("job.py test relays progress lines, skips non-progress lines, and prints the pass verdict",
      lines[:2] == ["quick: parse started", "quick: parse passed in 1 s"]
      and "noise before" not in lines and "noise middle" not in lines
      and lines[-1].startswith("quick test passed on ")
      and lines[-1].endswith(": features: ok | viewport: QUICK 1 passed, 0 failed"), lines)

release = os.path.join(base, "release-fail")
open(qstub, "w").write("""#!/bin/bash
echo "noise before fail"
echo "quick: parse started"
for ((i=0; i<100; i++)); do [ -f "$RELEASE" ] && break; sleep 0.05; done
if [ ! -f "$RELEASE" ]; then echo "STUB TIMED OUT"; exit 2; fi
echo "stderr detail" >&2
echo "quick: parse failed in 1 s"
echo "QUICK FAIL: stub broke" >&2
exit 1
""")
os.chmod(qstub, 0o755)
rc, lines, before_release, alive = run_job_test_live(wt, "quick: parse started", release)
check("a failing quick test still streams progress live and prints the failure verdict",
      rc == 1 and alive and before_release == ["quick: parse started"]
      and lines[:2] == ["quick: parse started", "quick: parse failed in 1 s"]
      and "noise before fail" not in lines and "stderr detail" not in lines
      and lines[-1].startswith("QUICK TEST FAILED on ")
      and lines[-1].endswith(": QUICK FAIL: stub broke"), (rc, alive, before_release, lines))

_qt = job.QUICKTEST
pass_stub = os.path.join(base, "pass-stub.sh")
open(pass_stub, "w").write('#!/bin/bash\necho "noise"\necho "quick: parse started"\necho "quick: parse passed in 1 s"\necho "verdict line"\n')
os.chmod(pass_stub, 0o755)
fail_stub = os.path.join(base, "fail-stub.sh")
open(fail_stub, "w").write('#!/bin/bash\necho "noise"\necho "quick: parse started"\necho "quick: parse failed in 1 s"\necho "fail verdict" >&2\nexit 1\n')
os.chmod(fail_stub, 0o755)
try:
    job.QUICKTEST = [pass_stub]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        res_ok = job.run_quick(wt)
    check("run_quick keeps its (ok, [last line]) return value and prints only progress lines",
          res_ok == (True, ["verdict line"])
          and buf.getvalue().splitlines() == ["quick: parse started", "quick: parse passed in 1 s"],
          (res_ok, buf.getvalue()))
    job.QUICKTEST = [fail_stub]
    seen = []
    res_fail = job.run_quick(wt, out=seen.append)
    check("run_quick returns (False, [last line]) on a failing stub and relays progress to out",
          res_fail == (False, ["fail verdict"])
          and seen == ["quick: parse started", "quick: parse failed in 1 s"],
          (res_fail, seen))
    job.QUICKTEST = ["true"]
    res_empty = job.run_quick(wt)
    check("run_quick with empty output still returns (True, [''])", res_empty == (True, [""]), res_empty)
finally:
    job.QUICKTEST = _qt

sh(root, "git", "worktree", "remove", "--force", wt)
shutil.rmtree(base)

# --- job worktrees live in <checkout>-jobs/<id> (H099) ---
base, root = repo()
jobs_dir = os.path.join(os.path.dirname(root), f"{os.path.basename(root)}-jobs")
check("worktree_for puts jobs in <checkout>-jobs/<id>",
      job.worktree_for(root, "H001") == os.path.join(jobs_dir, "h001"),
      job.worktree_for(root, "H001"))
check("fresh fixture repo starts with no -jobs folder", not os.path.exists(jobs_dir))
r, out = run(job.take, root, "claude", "h99-new")
wt_new = os.path.realpath(job.worktree_for(root, "H001"))
check("take makes the -jobs folder when missing and puts the worktree inside it",
      r == "H001" and os.path.isdir(jobs_dir) and os.path.isdir(wt_new)
      and state(root)["jobs"]["H001"]["worktree"] == wt_new, out)
r, out = run(job.merged, root, "claude/h001-first-job")
check("merged removes only the job's worktree and leaves the empty -jobs folder",
      r == "H001" and not os.path.exists(wt_new) and os.path.isdir(jobs_dir) and os.listdir(jobs_dir) == [],
      (r, os.path.exists(wt_new), os.path.isdir(jobs_dir),
       os.listdir(jobs_dir) if os.path.isdir(jobs_dir) else None, out))

old_wt = os.path.join(os.path.dirname(root), f"{os.path.basename(root)}-h003")
sh(root, "git", "worktree", "add", "-q", old_wt, "-b", "claude/h003-third-job", "main")
old_wt = os.path.realpath(old_wt)
new_wt = os.path.realpath(job.worktree_for(root, "H003"))
with job.locked(job.state_path(root)) as st:
    st["jobs"]["H003"] = {
        "state": "returned", "agent": "claude", "session": None,
        "branch": "claude/h003-third-job", "worktree": old_wt,
        "handoff": "H003-third-job.md", "taken": time.time(), "beat": time.time(),
        "returned": time.time(), "notes": "keep old sibling path",
    }
r, out = run(job.take, root, "claude", "h99-old")
check("retaking a job with an old-style recorded worktree keeps that path",
      r == "H003" and state(root)["jobs"]["H003"]["worktree"] == old_wt
      and os.path.isdir(old_wt) and not os.path.exists(new_wt), out)
hp = os.path.join(old_wt, "docs", "handoff", "H003-third-job.md")
body = open(hp).read()
open(hp, "w").write(body.replace("Status: open", "Status: answered") + "\nResponse: done.\n")
commit(old_wt, "answered in old worktree")
_qt = job.QUICKTEST
try:
    job.QUICKTEST = ["true"]
    r_test, out_test = run(job.test, old_wt)
    r_done, out_done = run(job.done, old_wt)
finally:
    job.QUICKTEST = _qt
check("test and done use the old-style recorded worktree, not the new -jobs path",
      r_test is True and r_done is True and state(root)["jobs"]["H003"]["state"] == "done"
      and state(root)["jobs"]["H003"]["worktree"] == old_wt and not os.path.exists(new_wt),
      (r_test, out_test, r_done, out_done))
sh(root, "git", "merge", "-q", "claude/h003-third-job")
r_merged, out_merged = run(job.merged, root, "claude/h003-third-job")
check("merged removes the old-style recorded worktree and leaves -jobs intact",
      r_merged == "H003" and not os.path.exists(old_wt) and not os.path.exists(new_wt)
      and state(root)["jobs"]["H003"]["state"] == "merged" and os.path.isdir(jobs_dir),
      (r_merged, out_merged))
shutil.rmtree(base)

# --- reassign_job and waiting_workers under take --wait (H104) ---
base, root = repo()
jobs_dir = os.path.join(os.path.dirname(root), f"{os.path.basename(root)}-jobs")
now0 = time.time()

# 1. Reassign of a returned job with an old-style worktree and uncommitted work -> moved, session uncounted, resumed by new agent.
r, _ = run(job.take, root, "codex", "codex-s1", now=now0)
check("H104 setup: codex takes H005", r == "H005")
old_wt5 = os.path.join(os.path.dirname(root), f"{os.path.basename(root)}-h005")
sh(root, "git", "worktree", "move", state(root)["jobs"]["H005"]["worktree"], old_wt5)
old_wt5 = os.path.realpath(old_wt5)
with job.locked(job.state_path(root)) as st:
    st["jobs"]["H005"]["worktree"] = old_wt5
open(os.path.join(old_wt5, "wip.txt"), "w").write("uncommitted wip\n")
open(os.path.join(old_wt5, "wip2.txt"), "w").write("second file\n")
run(job.return_job, root, "H005", "needs another pair of eyes", now=now0 + 10)
check("before reassign, old session still counts H005 toward MAX_JOBS",
      state(root)["sessions"]["codex-s1"] == ["H005"])

r_wt, out_wt = run(job.reassign_job, old_wt5, "H005", "gemini", now=now0 + 20)
check("reassign refuses when run inside a job worktree",
      not r_wt and "main checkout" in out_wt and state(root)["jobs"]["H005"]["agent"] == "codex", out_wt)

r_missing, out_missing = run(job.reassign_job, root, "H999", "gemini", now=now0 + 20)
check("reassign refuses a job not in the queue", not r_missing and "isn't in the queue" in out_missing, out_missing)

# Worktree move failure (target already exists): nothing in state changes, error printed.
target5 = os.path.realpath(job.worktree_for(root, "H005"))
os.makedirs(target5, exist_ok=True)
before_fail = json.dumps(state(root), sort_keys=True)
r_exists, out_exists = run(job.reassign_job, root, "H005", "gemini", now=now0 + 20)
check("reassign leaves state unchanged and prints error when target worktree already exists",
      not r_exists and "already exists" in out_exists
      and json.dumps(state(root), sort_keys=True) == before_fail
      and os.path.isdir(old_wt5), out_exists)
os.rmdir(target5)

# Successful reassign of returned H005 from codex to gemini.
r_re, out_re = run(job.reassign_job, root, "H005", "gemini", now=now0 + 30)
j5 = state(root)["jobs"]["H005"]
check("reassign of a returned job moves its worktree into <checkout>-jobs/, updates agent/state/notes/event",
      r_re and j5["agent"] == "gemini" and j5["state"] == "returned" and j5["session"] is None
      and j5["notes"] == "reassigned from codex by the integrator"
      and j5["worktree"] == target5 and os.path.isdir(target5) and not os.path.exists(old_wt5)
      and any(e["kind"] == "reassigned" and e["job"] == "H005" for e in state(root)["events"]), (r_re, out_re, j5))
check("reassign removes the job from the old session's count",
      "H005" not in state(root)["sessions"].get("codex-s1", []), state(root)["sessions"])
check("reassign keeps uncommitted work and reports the uncommitted file count and new path",
      f"H005: 2 files not committed in {target5}" in out_re
      and f"H005 reassigned to gemini: the next gemini worker resumes codex/h005-codex-job in {target5}" in out_re
      and open(os.path.join(target5, "wip.txt")).read() == "uncommitted wip\n", out_re)
watch_re = []
job.watch(root, once=True, out=watch_re.append, now=now0 + 35)
check("watch reports a reassigned job like returned, naming the new agent",
      any("returned: H005 waits for a gemini worker" in l for l in watch_re), watch_re)
r_take, out_take = run(job.take, root, "gemini", "gem-1", now=now0 + 40)
check("take --as <new> resumes the reassigned job's branch in the moved worktree with uncommitted work and notes",
      r_take == "H005" and state(root)["jobs"]["H005"]["worktree"] == target5
      and sh(target5, "git", "branch", "--show-current").stdout.strip() == "codex/h005-codex-job"
      and open(os.path.join(target5, "wip.txt")).read() == "uncommitted wip\n"
      and "reassigned from codex by the integrator" in out_take, out_take)

# 2. Reassign of an in-progress job whose worker beat recently: allowed, prints beat warning.
r_inprog, out_inprog = run(job.reassign_job, root, "H005", "claude", "take over", now=now0 + 40 + 5 * 60)
check("reassign of an in-progress job with recent beat warns to stop the worker and applies custom notes",
      r_inprog and "H005: its worker beat 5 min ago; tell that worker to stop" in out_inprog
      and state(root)["jobs"]["H005"]["agent"] == "claude"
      and state(root)["jobs"]["H005"]["notes"] == "take over"
      and "H005" not in state(root)["sessions"].get("gem-1", []), out_inprog)

# 3. Reassign of a job whose session was never counted (fallback session name): no error.
r_fb, _ = run(job.take, root, "claude", "claude", now=now0 + 400)
# H005 is returned for claude, so claude takes H005 with fallback session "claude" (not in sessions).
check("fallback session takes H005 without being added to sessions",
      r_fb == "H005" and "claude" not in state(root).get("sessions", {}))
r_fb_re, out_fb_re = run(job.reassign_job, root, "H005", "codex", now=now0 + 400 + job.DEADLINE + 60)
check("reassign with uncounted fallback session succeeds with no error and no recent-beat warning when stale",
      r_fb_re and state(root)["jobs"]["H005"]["agent"] == "codex"
      and "tell that worker to stop" not in out_fb_re, out_fb_re)

# 4. Reassign of a waiting job is allowed; reassign of done or merged jobs is refused.
r_w, _ = run(job.take, root, "claude", "s-wait", now=now0 + 500)
wt_w = state(root)["jobs"][r_w]["worktree"]
run(job.wait, wt_w, "question?", now=now0 + 510)
r_w_re, out_w_re = run(job.reassign_job, root, r_w, "gemini", now=now0 + 520)
check("reassign of a waiting job is allowed", r_w_re and state(root)["jobs"][r_w]["agent"] == "gemini", out_w_re)

with job.locked(job.state_path(root)) as st:
    st["jobs"]["H005"]["state"] = "done"
before_done = json.dumps(state(root), sort_keys=True)
r_done, out_done = run(job.reassign_job, root, "H005", "claude", now=now0 + 530)
check("reassign refuses a done job and leaves state unchanged",
      not r_done and "done" in out_done and json.dumps(state(root), sort_keys=True) == before_done, out_done)
with job.locked(job.state_path(root)) as st:
    st["jobs"]["H005"]["state"] = "merged"
before_merged = json.dumps(state(root), sort_keys=True)
r_merged, out_merged = run(job.reassign_job, root, "H005", "claude", now=now0 + 540)
check("reassign refuses a merged job and leaves state unchanged",
      not r_merged and "merged" in out_merged and json.dumps(state(root), sort_keys=True) == before_merged, out_merged)

# 5. CLI dispatch for job.py reassign
cwd0 = os.getcwd(); os.chdir(root)
try:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc_cli = job.main(["reassign", r_w, "--to", "codex", "cli note"])
finally:
    os.chdir(cwd0)
check("job.py reassign CLI parses <id> --to <agent> [notes]",
      rc_cli == 0 and state(root)["jobs"][r_w]["agent"] == "codex"
      and state(root)["jobs"][r_w]["notes"] == "cli note", buf.getvalue())

# 6. take --wait writes waiting_workers under locked, watch fires empty while waiting, and taking a job clears it.
# Make sure nothing is Ready for gemini (H003 is either -> take it first; H001 is returned for codex).
run(job.take, root, "codex", "c-hold1")   # takes returned H001
run(job.take, root, "codex", "c-hold2")   # takes H003 (either)
clock_w = [1000.0]
seen_during_wait = []
lock_calls = [0]
orig_locked = job.locked


@contextlib.contextmanager
def spy_locked(path):
    lock_calls[0] += 1
    with orig_locked(path) as st:
        yield st


def wait_sleep(sec):
    st_now = state(root)
    watch_mid = []
    job.watch(root, once=True, out=watch_mid.append, now=clock_w[0] + 1)
    seen_during_wait.append((dict(st_now["waiting_workers"]), list(watch_mid)))
    clock_w[0] += sec
    if len(seen_during_wait) == 1:
        open(os.path.join(root, "docs", "handoff", "H009-gem-job.md"), "w").write(
            entry("H009", "Gemini", "open", "tools/g.py.", "T9: gemini's"))
        commit(root, "H009 Ready")


with patch.object(job, "locked", spy_locked):
    r_gw, out_gw = run(job.take_wait, root, "gemini", "gem-wait", wait=60, poll=5,
                       sleep=wait_sleep, clock=lambda: clock_w[0])
watch_after = []
job.watch(root, once=True, out=watch_after.append, now=clock_w[0] + 1)
check("take --wait records waiting_workers under locked and watch fires empty while waiting",
      len(seen_during_wait) == 1 and "gem-wait" in seen_during_wait[0][0]
      and seen_during_wait[0][0]["gem-wait"] == {"agent": "gemini", "since": 1000.0}
      and any("queue empty for Gemini: a worker is waiting with nothing Ready (check in with William)" in l
              for l in seen_during_wait[0][1])
      and lock_calls[0] >= 3, (seen_during_wait, lock_calls))
check("after waiting worker takes a job, its waiting_workers entry is gone and no empty event fires",
      r_gw == "H009" and "gem-wait" not in state(root)["waiting_workers"]
      and not any("queue empty for Gemini" in l for l in watch_after), (r_gw, state(root)["waiting_workers"], watch_after))

# Timeout removes waiting_workers entry too.
clock_t = [2000.0]
r_to, out_to = run(job.take_wait, root, "gemini", "gem-timeout", wait=10, poll=5,
                   sleep=lambda s: clock_t.__setitem__(0, clock_t[0] + s), clock=lambda: clock_t[0])
check("take --wait removes waiting_workers entry when it stops at WORKER_WAIT",
      r_to is None and "gem-timeout" not in state(root)["waiting_workers"], (r_to, state(root)["waiting_workers"]))

for w in [l.split()[1] for l in sh(root, "git", "worktree", "list", "--porcelain").stdout.split("\n")
          if l.startswith("worktree ")][1:]:
    sh(root, "git", "worktree", "remove", "--force", w)
shutil.rmtree(base)

print(f"JOB TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
sys.exit(0 if all(RESULTS) else 1)
