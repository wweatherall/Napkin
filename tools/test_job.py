#!/usr/bin/env python3
"""Checks tools/job.py (the job queue, P24) and integrate.py's cleanup after a merge, on throwaway repositories.
Summary line: JOB TESTS: N passed, M failed."""
import atexit
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import integrate
import integrator
import job
os.environ.pop("NAPKIN_SPACE", None)  # a worker session sets it (launch.py); the tests pick their own spaces

# Isolate from host agent env vars so tests behave identically whether run by Claude, Codex, Gemini, or CI.
for _env_key in ("ANTIGRAVITY_CONVERSATION_ID", "ANTIGRAVITY_AGENT", "SHOPSKETCH_SESSION"):
    os.environ.pop(_env_key, None)
# Disable the external usage-tool subprocess by default; the usage-hook tests below override this with patch.dict.
os.environ["SHOPSKETCH_USAGE_TOOL"] = ""

RESULTS = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    if not ok or VERBOSE:
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


_TEMPLATE_REPO = None


def _template_repo():
    global _TEMPLATE_REPO
    if _TEMPLATE_REPO is None:
        base = tempfile.mkdtemp(prefix="job-tmpl-")
        atexit.register(shutil.rmtree, base, True)
        root = os.path.join(base, "repo")
        os.makedirs(os.path.join(root, "docs", "handoff"))
        os.makedirs(os.path.join(root, "03_Past_Decisions"))
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
        open(os.path.join(root, "03_Past_Decisions", "decision-log.md"), "w").write(
            "# Log\n\n## Work list\n\n| # | Item | Status |\n|---|---|---|\n| T1 | a | Open |\n")
        open(os.path.join(root, "docs", "agent-handoff.md"), "w").write(
            "# Handoff\n\n## Open exchanges\n\n<!-- open list: built from docs/handoff/ by tools/handoff.py; don't edit by "
            "hand -->\n\n(none open)\n\n<!-- end of open list -->\n\n## Archived\n")
        open(os.path.join(root, "docs", "handoff-archive.md"), "w").write("# Archive\n")
        sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "base")
        _TEMPLATE_REPO = root
    return _TEMPLATE_REPO


def repo():
    base = tempfile.mkdtemp(prefix="job-test-")
    root = os.path.join(base, "repo")
    shutil.copytree(_template_repo(), root)
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

named_jobs = job.jobs_from({
    "H001-redo.md": entry("H001", "either", "open", "viewport/main.gd (`redo`)."),
    "H002-redo.md": entry("H002", "either", "open", "viewport/main.gd (`redo()`)."),
    "H003-save.md": entry("H003", "either", "open", "viewport/main.gd (`_ask_outside`)."),
})
selected, reasons = job.takeable(root, {"jobs": {"H001": {"state": "in progress"}}}, "codex",
                                named_jobs, ["H001", "H002", "H003"], claims={})
check("the queue reports the shared function and takes the Ready job naming another function in main.gd",
      selected and selected["id"] == "H003" and reasons == ["H002: overlaps H001 (viewport/main.gd (redo))"],
      (selected, reasons))

trial = job.jobs_from({"H004-trial.md": entry("H004", "either", "open", "viewport/main.gd (`redo`).")
                       .replace("| For: either", "| For: either | Builds on: H001")})
selected, reasons = job.takeable(root, {"jobs": {"H001": {"state": "done"}}}, "codex", trial, ["H004"], claims={})
check("a job that builds on another (Builds on: H001) isn't held back by sharing its files",
      selected and selected["id"] == "H004" and reasons == [], (selected, reasons))

# --- wrong-checkout guard (T102), including both shell entry points before any test starts ---
guard_env = {k: v for k, v in os.environ.items() if k not in
             ("CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID", "CODEX_THREAD_ID",
              "ANTIGRAVITY_CONVERSATION_ID", "ANTIGRAVITY_AGENT", "SHOPSKETCH_SESSION", "SHOPSKETCH_ANY_CHECKOUT")}
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
r, out = run(job.wait, wt3, "which name?", now=now, wait=0)
j = state(root)["jobs"]["H003"]
check("wait marks the job waiting on William", j["state"] == "waiting" and j["question"] == "which name?", out)
check("a waiting job is never stale", not job.stale(j, job.activity(root, j, far, procs=[]), far))
run(job.beat, wt3, now=now + 5)
check("the next beat turns the switch back on", state(root)["jobs"]["H003"]["state"] == "in progress")
run(job.wait, wt3, "again?", now=now + 10, wait=0)
open(os.path.join(wt3, "b.txt"), "w").write("b\n")
commit(wt3, "answer came", when=now + 100)
j = state(root)["jobs"]["H003"]
job.refresh(root, j, now + 200, procs=[])
check("a commit after the wait counts as that beat", j["state"] == "in progress")

# --- done's refusals ---
job.QUICKTEST = ["sh", "-c", "exit 1"]
hpath = os.path.join(wt1, "docs", "handoff", "H001-first-job.md")
r, out = run(job.done, wt1)
check("done refuses with no response in the handoff",
      not r and "has no response" in out and "personal time:" not in out, out)
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
      not r and "QUICK TEST FAILED" in out and "refused" in out and "personal time:" not in out, out)
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
      "ready for a /clear" in out and "take --wait" not in out
      and "personal time:" in out and out.index("personal time:") < out.index("next:"), out)
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
run(job.wait, wt3, "a or b?", now=now + 500, wait=0)
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
looks_ret = iter([
    {("in progress", "H001"): "old"},
    {("in progress", "H001"): "old", ("returned", "H001", 100.0, "gemini"): "returned: H001 waits for a gemini worker"},
    {("returned", "H001", 100.0, "gemini"): "returned: H001 waits for a gemini worker", ("done", "H002", 101.0): "done: H002"},
])
job.conditions, job.WATCH_POLL = (lambda *a, **k: next(looks_ret)), 0
lines_ret = []
job.watch(root, until_new=True, out=lines_ret.append)
job.conditions, job.WATCH_POLL = _cond, _poll
check("watch --next ignores self-triggered returned events and wakes on the next worker event",
      len(lines_ret) == 1 and lines_ret[0].endswith("done: H002"), lines_ret)

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
# job.py board updates Work list item statuses from docs/handoff/
wdir_j = os.path.join(root, "03_Past_Decisions", "work")
os.makedirs(wdir_j, exist_ok=True)
open(os.path.join(wdir_j, "T1.md"), "w", encoding="utf-8").write(
    "# T1 — First job.\n\nStatus: Open | Covers: —\n\nFirst job.\n\nResult / next step:\n")
run(job.board, root)
check("job.py board updates the item statuses from the handoff",
      "Status: On the board (H001)" in open(os.path.join(wdir_j, "T1.md"), encoding="utf-8").read())
check("job.py board writes no jobs bucket outside an Organization (P57)", "05_Jobs" not in out and job.org_jobs_path(root) is None, out)
org = tempfile.mkdtemp(prefix="job-org-test-")
os.makedirs(os.path.join(org, "05_Jobs")); os.makedirs(os.path.join(org, "08_Code_Bases", "Proj"))
proj = os.path.join(org, "08_Code_Bases", "Proj")
check("the jobs bucket is Organization/05_Jobs/<code base>.md for a checkout in 08_Code_Bases",
      job.org_jobs_path(proj) == os.path.join(org, "05_Jobs", "Proj.md"), job.org_jobs_path(proj))
check("a job worktree (not directly in 08_Code_Bases) fills no bucket",
      job.org_jobs_path(os.path.join(org, "08_Code_Bases", ".worktrees", "Proj", "h001")) is None)
board_now = open(os.path.join(root, "BOARD.md")).read()
said = []
wrote = job.write_org_jobs(proj, board_now, out=said.append)
bucket = open(os.path.join(org, "05_Jobs", "Proj.md")).read()
check("the bucket gets the board's job table, its links pointing into the code base (P57)",
      wrote and bucket.startswith("# Proj jobs") and "| H005 |" in bucket
      and "](../08_Code_Bases/Proj/docs/handoff/H005-codex-job.md)" in bucket and "Order:" not in bucket, bucket)
check("an unchanged board leaves the bucket's file alone", job.write_org_jobs(proj, board_now, out=said.append) is False, said)

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
check("the refusal names the session and its jobs, and says a reused name needs a new one",
      "(w) has done 3 jobs (H001, H002, H003)" in out and "pick a new one" in out, out)
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
      "ready for a /clear" in out1 and "take --wait" not in out1
      and "personal time:" in out1 and out1.index("personal time:") < out1.index("next:"), out1)

clock = [0.0]
slept = []


def fake_sleep(sec):
    slept.append(sec)
    clock[0] += sec
    if len(slept) == 2:                          # a job turns Ready while it waits
        open(os.path.join(root, "docs", "handoff", "H008-late-job.md"), "w").write(
            entry("H008", "Codex", "open", "tools/z.py.", "T8: late"))
        commit(root, "H008 Ready")


run(job.take, root, "codex", "c0")                    # takes H005
run(job.take, root, "codex", "c1")                    # takes H004 (auto-unblocked after H001 merged): nothing else Ready for Codex
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

# --- job worktrees live in ../.worktrees/<checkout>/<id> (H099, P63) ---
base, root = repo()
jobs_dir = job.jobs_dir(root)
check("worktree_for puts jobs in ../.worktrees/<checkout>/<id> (P63)",
      job.worktree_for(root, "H001") == os.path.join(os.path.dirname(root), ".worktrees", os.path.basename(root), "h001"),
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
jobs_dir = job.jobs_dir(root)
now0 = time.time()

# 1. Reassign of a returned job with an old-style worktree and uncommitted work -> moved, session uncounted, resumed by new agent.
# H003 is For: either (first for codex in board Order), so take H003 as codex.
r, _ = run(job.take, root, "codex", "codex-s1", now=now0)
check("H104 setup: codex takes H003", r == "H003")
old_wt3 = os.path.join(os.path.dirname(root), f"{os.path.basename(root)}-h003")
sh(root, "git", "worktree", "move", state(root)["jobs"]["H003"]["worktree"], old_wt3)
old_wt3 = os.path.realpath(old_wt3)
with job.locked(job.state_path(root)) as st:
    st["jobs"]["H003"]["worktree"] = old_wt3
open(os.path.join(old_wt3, "wip.txt"), "w").write("uncommitted wip\n")
open(os.path.join(old_wt3, "wip2.txt"), "w").write("second file\n")
run(job.return_job, root, "H003", "needs another pair of eyes", now=now0 + 10)
check("before reassign, old session still counts H003 toward MAX_JOBS",
      state(root)["sessions"]["codex-s1"] == ["H003"])

r_wt, out_wt = run(job.reassign_job, old_wt3, "H003", "gemini", now=now0 + 20)
check("reassign refuses when run inside a job worktree",
      not r_wt and "main checkout" in out_wt and state(root)["jobs"]["H003"]["agent"] == "codex", out_wt)

r_missing, out_missing = run(job.reassign_job, root, "H999", "gemini", now=now0 + 20)
check("reassign refuses a job not in the queue", not r_missing and "isn't in the queue" in out_missing, out_missing)

# Worktree move failure (target already exists): nothing in state changes, error printed.
target3 = os.path.realpath(job.worktree_for(root, "H003"))
os.makedirs(target3, exist_ok=True)
before_fail = json.dumps(state(root), sort_keys=True)
r_exists, out_exists = run(job.reassign_job, root, "H003", "gemini", now=now0 + 20)
check("reassign leaves state unchanged and prints error when target worktree already exists",
      not r_exists and "already exists" in out_exists
      and json.dumps(state(root), sort_keys=True) == before_fail
      and os.path.isdir(old_wt3), out_exists)
os.rmdir(target3)

# Successful reassign of returned H003 from codex to gemini.
r_re, out_re = run(job.reassign_job, root, "H003", "gemini", now=now0 + 30)
j3 = state(root)["jobs"]["H003"]
check("reassign of a returned job moves its worktree into ../.worktrees/<checkout>/, updates agent/state/notes/event",
      r_re and j3["agent"] == "gemini" and j3["state"] == "returned" and j3["session"] is None
      and j3["notes"] == "reassigned from codex by the integrator"
      and j3["worktree"] == target3 and os.path.isdir(target3) and not os.path.exists(old_wt3)
      and any(e["kind"] == "reassigned" and e["job"] == "H003" for e in state(root)["events"]), (r_re, out_re, j3))
check("reassign removes the job from the old session's count",
      "H003" not in state(root)["sessions"].get("codex-s1", []), state(root)["sessions"])
check("reassign keeps uncommitted work and reports the uncommitted file count and new path",
      f"H003: 2 files not committed in {target3}" in out_re
      and f"H003 reassigned to gemini: the next gemini worker resumes codex/h003-third-job in {target3}" in out_re
      and open(os.path.join(target3, "wip.txt")).read() == "uncommitted wip\n", out_re)
watch_re = []
job.watch(root, once=True, out=watch_re.append, now=now0 + 35)
check("watch reports a reassigned job like returned, naming the new agent",
      any("returned: H003 waits for a gemini worker" in l for l in watch_re), watch_re)
r_take, out_take = run(job.take, root, "gemini", "gem-1", now=now0 + 40)
check("take --as <new> resumes the reassigned job's branch in the moved worktree with uncommitted work and notes",
      r_take == "H003" and state(root)["jobs"]["H003"]["worktree"] == target3
      and sh(target3, "git", "branch", "--show-current").stdout.strip() == "codex/h003-third-job"
      and open(os.path.join(target3, "wip.txt")).read() == "uncommitted wip\n"
      and "reassigned from codex by the integrator" in out_take, out_take)

# 2. Reassign of an in-progress job whose worker beat recently: allowed, prints beat warning.
r_inprog, out_inprog = run(job.reassign_job, root, "H003", "claude", "take over", now=now0 + 40 + 5 * 60)
check("reassign of an in-progress job with recent beat warns to stop the worker and applies custom notes",
      r_inprog and "H003: its worker beat 5 min ago; tell that worker to stop" in out_inprog
      and state(root)["jobs"]["H003"]["agent"] == "claude"
      and state(root)["jobs"]["H003"]["notes"] == "take over"
      and "H003" not in state(root)["sessions"].get("gem-1", []), out_inprog)

# 3. Reassign of a job whose session was never counted (fallback session name): no error.
r_fb, _ = run(job.take, root, "claude", "claude", now=now0 + 400)
# H003 is returned for claude, so claude takes H003 with fallback session "claude" (not in sessions).
check("fallback session takes H003 without being added to sessions",
      r_fb == "H003" and "claude" not in state(root).get("sessions", {}))
r_fb_re, out_fb_re = run(job.reassign_job, root, "H003", "codex", now=now0 + 400 + job.DEADLINE + 60)
check("reassign with uncounted fallback session succeeds with no error and no recent-beat warning when stale",
      r_fb_re and state(root)["jobs"]["H003"]["agent"] == "codex"
      and "tell that worker to stop" not in out_fb_re, out_fb_re)

# 4. Reassign of a waiting job is allowed; reassign of done or merged jobs is refused.
r_w, _ = run(job.take, root, "claude", "s-wait", now=now0 + 500)
wt_w = state(root)["jobs"][r_w]["worktree"]
run(job.wait, wt_w, "question?", now=now0 + 510, wait=0)
r_w_re, out_w_re = run(job.reassign_job, root, r_w, "gemini", now=now0 + 520)
check("reassign of a waiting job is allowed", r_w_re and state(root)["jobs"][r_w]["agent"] == "gemini", out_w_re)

with job.locked(job.state_path(root)) as st:
    st["jobs"]["H003"]["state"] = "done"
before_done = json.dumps(state(root), sort_keys=True)
r_done, out_done = run(job.reassign_job, root, "H003", "claude", now=now0 + 530)
check("reassign refuses a done job and leaves state unchanged",
      not r_done and "done" in out_done and json.dumps(state(root), sort_keys=True) == before_done, out_done)
with job.locked(job.state_path(root)) as st:
    st["jobs"]["H003"]["state"] = "merged"
before_merged = json.dumps(state(root), sort_keys=True)
r_merged, out_merged = run(job.reassign_job, root, "H003", "claude", now=now0 + 540)
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
# Nothing is Ready for gemini (H003 is merged, H001 is returned for codex, H002/H006 are Claude, H005 is Codex).
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

# --- Answers through the queue (H119) ---
answer_base, answer_root = repo()
answer_jid, _ = run(job.take, answer_root, "claude", "answer-worker")
answer_wt = job.worktree_for(answer_root, answer_jid)
answer_path = job.state_path(answer_root)
answer_clock = [time.time() + 1]
asked_jobs, asked_order = job.main_view(answer_root)


def tick(seconds):
    answer_clock[0] += seconds


def ask(question, *, sleep=tick, wait=10, scope=False):
    return run(job.wait, answer_wt, question, wait=wait, poll=5, sleep=sleep,
               clock=lambda: answer_clock[0], scope=scope)


def reply(text, source="integrator"):
    return run(job.answer, answer_root, answer_jid, text, source=source, now=answer_clock[0])


def answer_during_poll(seconds):
    tick(seconds)
    pending = state(answer_root)
    now = answer_clock[0] + job.DEADLINE + 1
    events = job.conditions(answer_root, pending, asked_jobs, asked_order, now,
                            procs={answer_jid: [(123, 1, "python3 tools/job.py wait --scope")]})
    other, skipped = job.takeable(answer_root, pending, "claude", asked_jobs, asked_order, claims={})
    check("waiting in the background keeps the deadline paused and the files held",
          pending["jobs"][answer_jid]["state"] == "waiting"
          and not any(key[0] == "stale" for key in events)
          and any(f"H002: overlaps {answer_jid}" in line for line in skipped), (events, other, skipped))
    _, status = run(job.status, answer_root, now=answer_clock[0])
    expected = f"waiting: {answer_jid} asks the integrator (scope): may I edit the helper?"
    check("watch and status route scope questions to the integrator",
          expected in events.values() and expected in status, (events, status))
    reply("yes, edit the helper")


before = answer_clock[0]
lock_calls[0] = 0
with patch.object(job, "locked", spy_locked):
    ok, out = ask("may I edit the helper?", sleep=answer_during_poll, scope=True)
check("an answer received during the wait is printed within one poll",
      ok and out.endswith("answer from integrator: yes, edit the helper") and answer_clock[0] == before + 5, out)
check("answer and poll both use the shared state lock",
      lock_calls[0] == 4 and not state(answer_root)["jobs"][answer_jid].get("answers"), out)
check("answer resumes the job and beats at the time of delivery",
      state(answer_root)["jobs"][answer_jid]["state"] == "in progress"
      and state(answer_root)["jobs"][answer_jid]["beat"] == answer_clock[0], state(answer_root))

ok, out = ask("which label?")
check("timeout reports how to retry and leaves the job waiting",
      not ok and out.endswith("no answer yet: run job.py wait again to keep waiting")
      and state(answer_root)["jobs"][answer_jid]["state"] == "waiting", out)
_, status = run(job.status, answer_root, now=answer_clock[0])
check("status routes a plain question to William", f"waiting: {answer_jid} asks William: which label?" in status, status)
answer_cli = sh(answer_root, sys.executable, os.path.join(HERE, "job.py"),
                "answer", answer_jid.lower(), "use Grain", "--from", "william")
event_count = len(state(answer_root)["events"])
before = answer_clock[0]
ok, out = ask("which label?")
check("a retry reads William's stored answer immediately without re-asking",
      answer_cli.returncode == 0 and ok and out == "answer from William: use Grain"
      and answer_clock[0] == before and len(state(answer_root)["events"]) == event_count, (out, answer_cli))

# Force an answer to contend with a poll that already holds the state lock.
poll_holds_lock = threading.Event()
answer_entering_lock = threading.Event()
answer_finished = threading.Event()
answer_result = []


polls = []


def concurrent_answer():
    if poll_holds_lock.wait(5):
        answer_result.append(reply("safe after contention"))
    answer_finished.set()


def contested_sleep(seconds):
    tick(seconds)
    polls.append(seconds)
    if len(polls) > 1:
        assert answer_finished.wait(5)


@contextlib.contextmanager
def competing_lock(path):
    writer = threading.current_thread() is answering
    if writer:
        answer_entering_lock.set()
    with orig_locked(path) as st:
        if len(polls) == 1 and not writer:
            poll_holds_lock.set()
            assert answer_entering_lock.wait(5)
            assert not answer_finished.is_set()
        yield st


answering = threading.Thread(target=concurrent_answer)
with patch.object(job, "locked", competing_lock):
    answering.start()
    try:
        ok, out = ask("can the answer race the poll?", sleep=contested_sleep)
    finally:
        answering.join(5)
check("a concurrent answer survives a poll that already held the lock",
      ok and out.endswith("answer from integrator: safe after contention")
      and len(polls) == 2 and len(answer_result) == 1 and answer_result[0][0], (out, polls, answer_result))

ask("any other direction?", wait=0)
first, _ = reply("first submission", source="william")
tick(1)
second, _ = reply("second submission")
ok, out = ask("any other direction?")
check("two unread answers are delivered in the order the queue recorded them",
      first and second and ok and out.splitlines() == [
          "answer from William: first submission", "answer from integrator: second submission"
      ], out)

unchanged = state(answer_root)
ok, out = reply("extra")
missing, missing_out = run(job.answer, answer_root, "H999", "extra")
check("answer refuses both an unknown job and a job without an open question without changing state",
      not missing and "isn't in the queue" in missing_out and not ok
      and "not waiting for an answer" in out and unchanged == state(answer_root), (out, missing_out))

for transfer in ("return", "reassign"):
    ask(f"{transfer} scope?", wait=0, scope=True)
    reply(f"{transfer} approved")
    if transfer == "return":
        run(job.return_job, answer_root, answer_jid, "resume work")
        agent = "claude"
    else:
        run(job.reassign_job, answer_root, answer_jid, "gemini")
        agent = "gemini"
    check(f"{transfer} leaves the unread answer on the job",
          state(answer_root)["jobs"][answer_jid].get("answers"), state(answer_root))
    resumed, out = run(job.take, answer_root, agent, f"worker-after-{transfer}")
    check(f"take prints the handoff and delivers the unread answer after {transfer}",
          resumed == answer_jid and f"### {answer_jid}" in out
          and out.endswith(f"answer from integrator: {transfer} approved")
          and not state(answer_root)["jobs"][answer_jid].get("answers"), out)

cli = io.StringIO()
with patch.object(job.os, "getcwd", return_value=answer_wt), patch.object(job, "WORKER_WAIT", 0):
    with contextlib.redirect_stdout(cli):
        rc = job.main(["wait", "--scope", "CLI scope?"])
check("job.py wait CLI accepts --scope before the question",
      rc == 1 and f"waiting: {answer_jid} asks the integrator (scope): CLI scope?" in cli.getvalue(), cli.getvalue())
default_answer = sh(answer_root, sys.executable, os.path.join(HERE, "job.py"),
                    "answer", answer_jid, "CLI approval")
ok, out = ask("CLI scope?", scope=True)
check("job.py answer CLI defaults to integrator",
      default_answer.returncode == 0 and ok and out == "answer from integrator: CLI approval",
      (default_answer, out))

shutil.rmtree(answer_base)

for w in [l.split()[1] for l in sh(root, "git", "worktree", "list", "--porcelain").stdout.split("\n")
          if l.startswith("worktree ")][1:]:
    sh(root, "git", "worktree", "remove", "--force", w)
shutil.rmtree(base)

# --- passive job-usage lifecycle hooks (H124 / T117) ---
u_base, u_root = repo()
u_real_root = os.path.realpath(u_root)
u_log = os.path.join(u_base, "usage.log")
u_stub = os.path.join(u_base, "usage_stub.py")
open(u_stub, "w").write(
    f"import json, sys\n"
    f"with open({u_log!r}, 'a', encoding='utf-8') as f:\n"
    f"    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
)
u_fail = os.path.join(u_base, "usage_fail.py")
open(u_fail, "w").write("import sys\nsys.stderr.write('boom\\n')\nsys.exit(1)\n")
u_missing = os.path.join(u_base, "no_such_usage_tool.py")

with patch.dict(os.environ, {"SHOPSKETCH_USAGE_TOOL": u_stub}):
    r_take, out_take = run(job.take, u_root, "claude", "u-sess-1")
    wt_u1 = os.path.realpath(job.worktree_for(u_root, "H001"))
    hp_u1 = os.path.join(wt_u1, "docs", "handoff", "H001-first-job.md")
    body_u1 = open(hp_u1).read()
    open(hp_u1, "w").write(body_u1.replace("Status: open", "Status: answered") + "\nResponse: done.\n")
    commit(wt_u1, "H001 answered")
    _qt = job.QUICKTEST
    try:
        job.QUICKTEST = ["true"]
        r_done, out_done = run(job.done, wt_u1)
    finally:
        job.QUICKTEST = _qt
    r_ret, out_ret = run(job.return_job, u_root, "H001", "needs tweak")

u_calls = [json.loads(line) for line in open(u_log, encoding="utf-8").read().splitlines()] if os.path.isfile(u_log) else []
check("usage hook: take passes --repo <tmp_root>, snapshot, --event take, --job, --agent, --session, --quiet",
      r_take == "H001" and len(u_calls) >= 1 and u_calls[0] == [
          "--repo", u_real_root, "snapshot", "--event", "take", "--job", "H001",
          "--agent", "claude", "--session", "u-sess-1", "--quiet"
      ], (r_take, u_calls))
check("usage hook: done passes --repo <tmp_root>, snapshot, --event done, --job, --quiet",
      r_done is True and len(u_calls) >= 2 and u_calls[1] == [
          "--repo", u_real_root, "snapshot", "--event", "done", "--job", "H001", "--quiet"
      ], (r_done, u_calls))
check("usage hook: return passes --repo <tmp_root>, snapshot, --event return, --job, --quiet",
      r_ret is True and len(u_calls) >= 3 and u_calls[2] == [
          "--repo", u_real_root, "snapshot", "--event", "return", "--job", "H001", "--quiet"
      ], (r_ret, u_calls))
check("usage hook: temp-repo runs target their temp repo, never the real checkout",
      all(c[1] == u_real_root and c[1] != job.main_root(HERE) for c in u_calls), u_calls)

# Missing or empty SHOPSKETCH_USAGE_TOOL: no subprocess spawned, take/done/return all succeed.
for label, val in (("missing path", u_missing), ("empty string", "")):
    with patch.dict(os.environ, {"SHOPSKETCH_USAGE_TOOL": val}), \
         patch.object(job.subprocess, "run") as spy_run:
        job.record_usage(u_real_root, "take", "H001", agent="claude", session="s", quiet=True)
    check(f"usage hook: {label} returns immediately without spawning a subprocess", not spy_run.called)

with patch.dict(os.environ, {"SHOPSKETCH_USAGE_TOOL": u_missing}):
    r_m_take, _ = run(job.take, u_root, "claude", "u-miss-1")
    _qt = job.QUICKTEST
    try:
        job.QUICKTEST = ["true"]
        r_m_done, _ = run(job.done, wt_u1)
    finally:
        job.QUICKTEST = _qt
    r_m_ret, _ = run(job.return_job, u_root, "H001", "still needs tweak")
check("usage hook: missing SHOPSKETCH_USAGE_TOOL lets take, done, and return succeed",
      r_m_take == "H001" and r_m_done is True and r_m_ret is True, (r_m_take, r_m_done, r_m_ret))

# Failing SHOPSKETCH_USAGE_TOOL (exits 1 or raises): fail-open on take, done, return.
with patch.dict(os.environ, {"SHOPSKETCH_USAGE_TOOL": u_fail}):
    r_f_take, _ = run(job.take, u_root, "claude", "u-fail-1")
    _qt = job.QUICKTEST
    try:
        job.QUICKTEST = ["true"]
        r_f_done, _ = run(job.done, wt_u1)
    finally:
        job.QUICKTEST = _qt
    r_f_ret, _ = run(job.return_job, u_root, "H001", "fail-open check")
check("usage hook: failing SHOPSKETCH_USAGE_TOOL (exit 1) is fail-open on take, done, and return",
      r_f_take == "H001" and r_f_done is True and r_f_ret is True, (r_f_take, r_f_done, r_f_ret))

raised = False
try:
    with patch.dict(os.environ, {"SHOPSKETCH_USAGE_TOOL": u_stub}), \
         patch.object(job.subprocess, "run", side_effect=subprocess.TimeoutExpired("usage", 5)):
        job.record_usage(u_real_root, "done", "H001", quiet=True)
except Exception:
    raised = True
check("usage hook: subprocess exception (e.g. TimeoutExpired) is swallowed fail-open", not raised)

for w in [l.split()[1] for l in sh(u_root, "git", "worktree", "list", "--porcelain").stdout.split("\n")
          if l.startswith("worktree ")][1:]:
    sh(u_root, "git", "worktree", "remove", "--force", w)
shutil.rmtree(u_base)

# Read-only queue reads (sandboxed .git): status(readonly=True) creates no .lock, and status()/watch() fall back on PermissionError.
ro_base, ro_root = repo()
ro_state = job.state_path(ro_root)
ro_lock = ro_state + ".lock"
if os.path.exists(ro_lock):
    os.remove(ro_lock)
_, ro_lines = run(job.status, ro_root, readonly=True)
check("status(readonly=True) reads the queue without creating a .lock file",
      "no job in progress" in ro_lines and not os.path.exists(ro_lock), ro_lines)

real_open = open
def deny_lock(path, *args, **kwargs):
    if str(path).endswith(".lock"):
        raise PermissionError("sandbox denied .git lock")
    return real_open(path, *args, **kwargs)

with patch("builtins.open", side_effect=deny_lock):
    _, fb_status = run(job.status, ro_root)
    fb_cur, _ = run(job.watch, ro_root, once=True)
check("status() and watch(once=True) fall back cleanly when .git/*.lock raises PermissionError",
      "no job in progress" in fb_status and isinstance(fb_cur, dict), (fb_status, fb_cur))
with patch.object(job, "processes", side_effect=PermissionError("sandbox denied ps")):
    act_ro = job.activity(ro_root, {"taken": 123, "branch": "HEAD", "worktree": ro_root}, 200)
check("activity() degrades cleanly when ps/lsof raise PermissionError in a sandbox", act_ro >= 123, act_ro)
shutil.rmtree(ro_base)

# --- collision-proof parallel Gemini take & AGY env detection (H142 / T128) ---
agy_base, agy_root = repo()
for hid, slug, path in (("H010", "gem-a", "tools/ga.py"), ("H011", "gem-b", "tools/gb.py"),
                        ("H012", "gem-c", "tools/gc.py"), ("H013", "gem-d", "tools/gd.py")):
    open(os.path.join(agy_root, "docs", "handoff", f"{hid}-{slug}.md"), "w").write(
        entry(hid, "either", "open", f"{path}.", f"T: {slug}"))
open(os.path.join(agy_root, "BOARD.md"), "w").write(
    BOARD.replace("Order: H001, H002, H003, H005, H004, H006",
                  "Order: H003, H010, H011, H012, H013"))
commit(agy_root, "add parallel gemini jobs")

clean_agent_env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "CODEX", "ANTIGRAVITY"))
                   and k not in ("SHOPSKETCH_SESSION", "SHOPSKETCH_ANY_CHECKOUT")}
with patch.dict(os.environ, clean_agent_env, clear=True):
    check("default_agent returns None without agent env vars", job.default_agent() is None)
    with patch.dict(os.environ, {"ANTIGRAVITY_AGENT": "1"}):
        check("default_agent detects gemini from ANTIGRAVITY_AGENT", job.default_agent() == "gemini")
    with patch.dict(os.environ, {"ANTIGRAVITY_CONVERSATION_ID": "aaaa1111-2222-3333-4444-555566667777"}):
        check("default_agent detects gemini from ANTIGRAVITY_CONVERSATION_ID", job.default_agent() == "gemini")
        check("default_session returns ANTIGRAVITY_CONVERSATION_ID when set",
              job.default_session("gemini") == "aaaa1111-2222-3333-4444-555566667777")
        check("counted returns truthy for AGY UUID and suffixed manual session",
              bool(job.counted("aaaa1111-2222-3333-4444-555566667777"))
              and bool(job.counted("gemini-cedar-1124-0658-aaaa1111"))
              and not job.counted("gemini"))
    with patch.dict(os.environ, {"SHOPSKETCH_SESSION": "custom-sess"}):
        check("default_session falls back to SHOPSKETCH_SESSION before agent",
              job.default_session("gemini") == "custom-sess")


def cli_take(cwd_dir, argv, extra_env):
    env = dict(clean_agent_env, **extra_env)
    buf = io.StringIO()
    old_cwd = os.getcwd()
    os.chdir(cwd_dir)
    try:
        with patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(buf):
            rc = job.main(["take"] + argv)
    finally:
        os.chdir(old_cwd)
    return rc, buf.getvalue()


conv1 = "c56ddaee-1111-4000-8000-000000000001"
conv2 = "a1b2c3d4-2222-4000-8000-000000000002"
conv3 = "99887766-3333-4000-8000-000000000003"
conv4 = "55443322-4444-4000-8000-000000000004"

# 1. Two different ANTIGRAVITY_CONVERSATION_ID values calling `take --as gemini` (no --session) both succeed.
rc1, out1 = cli_take(agy_root, ["--as", "gemini"], {"ANTIGRAVITY_CONVERSATION_ID": conv1})
rc2, out2 = cli_take(agy_root, ["--as", "gemini"], {"ANTIGRAVITY_CONVERSATION_ID": conv2})
st_agy = state(agy_root)
check("two different ANTIGRAVITY_CONVERSATION_IDs calling take --as gemini (no --session) take distinct jobs",
      rc1 == 0 and rc2 == 0 and "took H003" in out1 and "took H010" in out2
      and st_agy["jobs"]["H003"]["session"] == conv1 and st_agy["jobs"]["H010"]["session"] == conv2,
      (rc1, rc2, st_agy["jobs"]))

# 2. Two different ANTIGRAVITY_CONVERSATION_ID values passing the SAME manual --session name both succeed.
rc3, out3 = cli_take(agy_root, ["--as", "gemini", "--session", "gemini-cedar-1124-0658"],
                     {"ANTIGRAVITY_CONVERSATION_ID": conv3})
rc4, out4 = cli_take(agy_root, ["--as", "gemini", "--session", "gemini-cedar-1124-0658"],
                     {"ANTIGRAVITY_CONVERSATION_ID": conv4})
st_agy = state(agy_root)
check("two different ANTIGRAVITY_CONVERSATION_IDs with identical manual --session both succeed without colliding",
      rc3 == 0 and rc4 == 0 and "took H011" in out3 and "took H012" in out4
      and st_agy["jobs"]["H011"]["session"] == f"gemini-cedar-1124-0658-{conv3[:8]}"
      and st_agy["jobs"]["H012"]["session"] == f"gemini-cedar-1124-0658-{conv4[:8]}",
      (rc3, rc4, out3, out4, st_agy["jobs"]))

# 3. Same ANTIGRAVITY_CONVERSATION_ID calling take a second time (while holding AND after done) is refused (P37).
rc_dup_hold, out_dup_hold = cli_take(agy_root, ["--as", "gemini"], {"ANTIGRAVITY_CONVERSATION_ID": conv1})
check("same ANTIGRAVITY_CONVERSATION_ID calling take while holding a job is refused",
      rc_dup_hold == 1 and "already holds H003" in out_dup_hold, (rc_dup_hold, out_dup_hold))
rc_dup_man, out_dup_man = cli_take(agy_root, ["--as", "gemini", "--session", "gemini-cedar-1124-0658"],
                                   {"ANTIGRAVITY_CONVERSATION_ID": conv3})
check("same ANTIGRAVITY_CONVERSATION_ID repeating manual --session while holding is refused",
      rc_dup_man == 1 and "already holds H011" in out_dup_man, (rc_dup_man, out_dup_man))

# Finish H003 (conv1) and verify MAX_JOBS=1 still refuses a second take by conv1.
wt_agy1 = st_agy["jobs"]["H003"]["worktree"]
hp_agy1 = os.path.join(wt_agy1, "docs", "handoff", "H003-third-job.md")
body_agy1 = open(hp_agy1).read()
open(hp_agy1, "w").write(body_agy1.replace("Status: open", "Status: answered") + "\nResponse: done.\n")
commit(wt_agy1, "H003 answered")
_qt = job.QUICKTEST
try:
    job.QUICKTEST = ["true"]
    r_agy_done, out_agy_done = run(job.done, wt_agy1)
finally:
    job.QUICKTEST = _qt
rc_after_done, out_after_done = cli_take(agy_root, ["--as", "gemini"], {"ANTIGRAVITY_CONVERSATION_ID": conv1})
check("same ANTIGRAVITY_CONVERSATION_ID calling take after done is still refused (P37 MAX_JOBS=1)",
      r_agy_done is True and rc_after_done == 1 and "has done 1 jobs (H003)" in out_after_done,
      (r_agy_done, rc_after_done, out_after_done))

# 4. guard_checkout refuses main checkout when ANTIGRAVITY_CONVERSATION_ID holds an active job (and allows override).
with patch.dict(os.environ, dict(clean_agent_env, ANTIGRAVITY_CONVERSATION_ID=conv2), clear=True):
    g_ok, g_out = run(job.guard_checkout, agy_root)
    check("guard_checkout refuses main checkout when ANTIGRAVITY_CONVERSATION_ID holds an active job",
          g_ok is False and "H010" in g_out and st_agy["jobs"]["H010"]["worktree"] in g_out, (g_ok, g_out))
    g_wt_ok, _ = run(job.guard_checkout, st_agy["jobs"]["H010"]["worktree"])
    check("guard_checkout allows running inside the AGY job's worktree", g_wt_ok is True)
with patch.dict(os.environ, dict(clean_agent_env, ANTIGRAVITY_CONVERSATION_ID=conv3), clear=True):
    g_man_ok, g_man_out = run(job.guard_checkout, agy_root)
    check("guard_checkout also refuses main checkout when AGY job was taken with a manual --session",
          g_man_ok is False and "H011" in g_man_out, (g_man_ok, g_man_out))
with patch.dict(os.environ, dict(clean_agent_env, ANTIGRAVITY_CONVERSATION_ID=conv2, SHOPSKETCH_ANY_CHECKOUT="1"), clear=True):
    g_ovr, _ = run(job.guard_checkout, agy_root)
    check("guard_checkout allows main checkout for AGY session when SHOPSKETCH_ANY_CHECKOUT=1", g_ovr is True)

# 5. Without ANTIGRAVITY_CONVERSATION_ID, existing --session collision/counting behaviour is 100% unchanged.
rc_plain1, out_plain1 = cli_take(agy_root, ["--as", "gemini", "--session", "gemini-cedar-1124-0658"], {})
rc_plain2, out_plain2 = cli_take(agy_root, ["--as", "gemini", "--session", "gemini-cedar-1124-0658"], {})
st_agy = state(agy_root)
check("without ANTIGRAVITY_CONVERSATION_ID, manual --session is recorded verbatim and collides on repeat",
      rc_plain1 == 0 and "took H013" in out_plain1
      and st_agy["jobs"]["H013"]["session"] == "gemini-cedar-1124-0658"
      and st_agy["sessions"]["gemini-cedar-1124-0658"] == ["H013"]
      and rc_plain2 == 1 and "already holds H013" in out_plain2,
      (rc_plain1, out_plain1, rc_plain2, out_plain2, st_agy["jobs"].get("H013")))

for w in [l.split()[1] for l in sh(agy_root, "git", "worktree", "list", "--porcelain").stdout.split("\n")
          if l.startswith("worktree ")][1:]:
    sh(agy_root, "git", "worktree", "remove", "--force", w)
shutil.rmtree(agy_base)

# --- Auto-unblock queued jobs (H146 / T130) ---
dep_base = tempfile.mkdtemp(prefix="job-dep-test-")
dep_root = os.path.join(dep_base, "repo")
os.makedirs(os.path.join(dep_root, "docs", "handoff"))
sh(dep_root, "git", "init", "-q", "-b", "main")
sh(dep_root, "git", "config", "user.email", "t@example.invalid"); sh(dep_root, "git", "config", "user.name", "t")
dep_files = {
    "H126-blocker-one.md": entry("H126", "either", "open", "tools/a.py.", "T126: blocker one"),
    "H128-blocker-two.md": entry("H128", "either", "open", "tools/b.py.", "T128: blocker two"),
    "H127-wait-one.md": entry("H127", "either", "queued (after H126)", "tools/c.py.", "T127: waits on H126"),
    "H129-wait-two.md": entry("H129", "either", "queued (after H126, H128)", "tools/d.py.", "T129: waits on two"),
    "H130-wait-text.md": entry("H130", "either", "queued (waiting on William)", "tools/e.py.", "T130: text wait"),
    "H131-wait-bare.md": entry("H131", "either", "queued", "tools/f.py.", "T131: bare queued"),
}
for n, t in dep_files.items():
    open(os.path.join(dep_root, "docs", "handoff", n), "w").write(t)
open(os.path.join(dep_root, "BOARD.md"), "w").write(
    f"# Work board\n\nOrder: H126, H128, H127, H129, H130, H131\n\n## Jobs\n\n{job.START}\n\n(none)\n\n{job.END}\n"
)
open(os.path.join(dep_root, "docs", "agent-handoff.md"), "w").write(
    "# Handoff\n\n## Open exchanges\n\n<!-- open list: built from docs/handoff/ by tools/handoff.py; don't edit by "
    "hand -->\n\n(none open)\n\n<!-- end of open list -->\n\n## Archived\n"
)
open(os.path.join(dep_root, "docs", "handoff-archive.md"), "w").write("# Archive\n")
sh(dep_root, "git", "add", "-A"); sh(dep_root, "git", "commit", "-qm", "dep base")

# While H126 and H128 are open, H127/H129/H130/H131 stay Queued.
dep_jobs, dep_order = job.main_view(dep_root)
dep_st = job.read_state(job.state_path(dep_root))
tbl0 = job.table(dep_root, dep_st, dep_jobs, dep_order, 1000)
pick0, _ = job.takeable(dep_root, dep_st, "gemini", dep_jobs, dep_order)
check("queued (after H126) stays Queued while H126 is open",
      pick0 and pick0["id"] == "H126" and "| H127 | either | Queued |" in tbl0 and "| H129 | either | Queued |" in tbl0,
      (pick0, tbl0))

# Mark H126 answered in handoff + state: H127 still stays Queued.
open(os.path.join(dep_root, "docs", "handoff", "H126-blocker-one.md"), "w").write(
    entry("H126", "either", "answered", "tools/a.py.", "T126: blocker one")
)
commit(dep_root, "H126 answered")
dep_jobs, dep_order = job.main_view(dep_root)
dep_st["jobs"]["H126"] = {"state": "done", "branch": "gemini/h126-blocker-one"}
tbl1 = job.table(dep_root, dep_st, dep_jobs, dep_order, 1000)
pick1, _ = job.takeable(dep_root, dep_st, "gemini", dep_jobs, dep_order)
check("queued (after H126) stays Queued while H126 is answered/done",
      pick1 and pick1["id"] == "H128" and "| H127 | either | Queued |" in tbl1, (pick1, tbl1))

# Mark H126 merged in state (even before H126 file is archived): H127 becomes Ready, H129 shows only H128.
dep_st["jobs"]["H126"] = {"state": "merged", "branch": "gemini/h126-blocker-one"}
with open(job.state_path(dep_root), "w") as f:
    json.dump(dep_st, f)
tbl2 = job.table(dep_root, dep_st, dep_jobs, dep_order, 1000)
pick2, _ = job.takeable(dep_root, dep_st, "gemini", dep_jobs, dep_order)
_, status_out2 = run(job.status, dep_root)
check("once H126 is merged in state, H127 becomes Ready in table() and takeable()",
      pick2 and pick2["id"] == "H128"
      and "| H127 | either | **Ready** | T127: waits on H126 | [H127](docs/handoff/H127-wait-one.md) |  |" in tbl2,
      (pick2, tbl2))
check("multi-dep H129 stays Queued showing only H128 when only H126 is merged",
      "| H129 | either | Queued | T129: waits on two | [H129](docs/handoff/H129-wait-two.md) | H128 |" in tbl2,
      tbl2)

# Remove H126 and H128 from docs/handoff/ (archived) and clear state: H127 and H129 are Ready, H130/H131 stay Queued.
os.remove(os.path.join(dep_root, "docs", "handoff", "H126-blocker-one.md"))
os.remove(os.path.join(dep_root, "docs", "handoff", "H128-blocker-two.md"))
commit(dep_root, "archive H126 and H128")
with open(job.state_path(dep_root), "w") as f:
    json.dump({"jobs": {}, "events": []}, f)
dep_jobs3, dep_order3 = job.main_view(dep_root)
dep_st3 = job.read_state(job.state_path(dep_root))
tbl3 = job.table(dep_root, dep_st3, dep_jobs3, dep_order3, 1000)
_, status_out3 = run(job.status, dep_root)
r_dep_take, _ = run(job.take, dep_root, "gemini", "s-dep")
check("once blockers are absent from docs/handoff/, H127 and H129 become Ready and H127 is taken by take()",
      "| H127 | either | **Ready** |" in tbl3 and "| H129 | either | **Ready** |" in tbl3
      and "next for Gemini: H127" in status_out3 and r_dep_take == "H127",
      (tbl3, status_out3, r_dep_take))
check("non-ID wait and bare queued are NOT auto-unblocked",
      "| H130 | either | Queued |" in tbl3 and "| H131 | either | Queued |" in tbl3, tbl3)

for w in [l.split()[1] for l in sh(dep_root, "git", "worktree", "list", "--porcelain").stdout.split("\n")
          if l.startswith("worktree ")][1:]:
    sh(dep_root, "git", "worktree", "remove", "--force", w)
shutil.rmtree(dep_base)

# --- done() commits and pushes the worker's personal space (H159) ---
ps_base = os.path.realpath(tempfile.mkdtemp(prefix="job-ps-"))
ps_remote = os.path.join(ps_base, "remote.git")
ps_org = os.path.join(ps_base, "org")
ps_root = os.path.join(ps_org, "08_Code_Bases", "Proj")
os.makedirs(os.path.join(ps_org, "04_Personal_Space", "gemini-coder", "Creative_Expression"))
os.makedirs(os.path.join(ps_org, "04_Personal_Space", "claude-coder", "Ideas"))
os.makedirs(ps_root)
sh(ps_base, "git", "init", "--bare", "-q", "-b", "main", ps_remote)
sh(ps_base, "git", "init", "-q", "-b", "main", ps_org)
sh(ps_org, "git", "config", "user.email", "t@example.invalid")
sh(ps_org, "git", "config", "user.name", "T")
sh(ps_org, "git", "commit", "-q", "--allow-empty", "-m", "org init")
sh(ps_org, "git", "remote", "add", "origin", ps_remote)
sh(ps_org, "git", "push", "-q", "-u", "origin", "main")

sh(ps_base, "git", "init", "-q", "-b", "main", ps_root)
sh(ps_root, "git", "config", "user.email", "t@example.invalid")
sh(ps_root, "git", "config", "user.name", "T")
os.makedirs(os.path.join(ps_root, "tools"))
os.makedirs(os.path.join(ps_root, "docs", "handoff"))
open(os.path.join(ps_root, "tools", "quicktest.sh"), "w").write("#!/bin/sh\nexit 0\n")
os.chmod(os.path.join(ps_root, "tools", "quicktest.sh"), 0o755)
open(os.path.join(ps_root, "tools", "test_bookkeeping.py"), "w").write("import sys; sys.exit(0)\n")
open(os.path.join(ps_root, "BOARD.md"), "w").write("# Board\n\nOrder: H201, H202.\n")
open(os.path.join(ps_root, "docs", "handoff", "H201-ps-test.md"), "w").write(
    entry("H201", "gemini", "open", "tools/a.py.", "T201: ps test")
)
open(os.path.join(ps_root, "docs", "agent-handoff.md"), "w").write(
    "# Handoff\n\n## Open exchanges\n\n<!-- open list: built from docs/handoff/ by tools/handoff.py; don't edit by "
    "hand -->\n\n(none open)\n\n<!-- end of open list -->\n\n## Archived\n"
)
open(os.path.join(ps_root, "docs", "handoff-archive.md"), "w").write("# Archive\n")
sh(ps_root, "git", "add", "-A"); sh(ps_root, "git", "commit", "-qm", "ps base")

_, _ = run(job.take, ps_root, "gemini", "s-ps")
ps_wt = job.worktree_for(ps_root, "H201")
sh(ps_wt, "git", "config", "user.email", "t@example.invalid")
sh(ps_wt, "git", "config", "user.name", "T")
ps_hp = os.path.join(ps_wt, "docs", "handoff", "H201-ps-test.md")
ps_text = open(ps_hp).read()
open(ps_hp, "w").write(ps_text.replace("Status: open", "Status: answered") + "\nResponse: done.\n")
sh(ps_wt, "git", "add", "-A"); sh(ps_wt, "git", "commit", "-qm", "answer H201")

open(os.path.join(ps_org, "04_Personal_Space", "gemini-coder", "Creative_Expression", "haiku.txt"), "w").write("leaf\n")
open(os.path.join(ps_org, "04_Personal_Space", "claude-coder", "Ideas", "other.txt"), "w").write("other\n")
r_ps_done, out_ps_done = run(job.done, ps_wt)
ps_remote_files = sh(ps_remote, "git", "show", "--name-only", "--pretty=", "main").stdout.splitlines()
ps_org_status = sh(ps_org, "git", "status", "--porcelain").stdout
check("done() commits and pushes the worker's personal space without touching other spaces",
      r_ps_done is True
      and "04_Personal_Space/gemini-coder/Creative_Expression/haiku.txt" in ps_remote_files
      and "04_Personal_Space/claude-coder/" in ps_org_status,
      (r_ps_done, out_ps_done, ps_remote_files, ps_org_status))

# done() after a shell restart without NAPKIN_SPACE still uses the space recorded at take() (H164).
os.makedirs(os.path.join(ps_org, "04_Personal_Space", "gemini-neon-coder", "Creative_Expression"))
open(os.path.join(ps_root, "docs", "handoff", "H202-ps-space.md"), "w").write(
    entry("H202", "gemini", "open", "tools/b.py.", "T202: ps recorded space")
)
sh(ps_root, "git", "add", "-A"); sh(ps_root, "git", "commit", "-qm", "H202")
old_napkin_space = os.environ.get("NAPKIN_SPACE")
try:
    os.environ["NAPKIN_SPACE"] = "gemini-neon-coder"
    _, _ = run(job.take, ps_root, "gemini", "s-ps2")
finally:
    if old_napkin_space is None:
        os.environ.pop("NAPKIN_SPACE", None)
    else:
        os.environ["NAPKIN_SPACE"] = old_napkin_space
ps_wt2 = job.worktree_for(ps_root, "H202")
sh(ps_wt2, "git", "config", "user.email", "t@example.invalid")
sh(ps_wt2, "git", "config", "user.name", "T")
ps_hp2 = os.path.join(ps_wt2, "docs", "handoff", "H202-ps-space.md")
ps_text2 = open(ps_hp2).read()
open(ps_hp2, "w").write(ps_text2.replace("Status: open", "Status: answered") + "\nResponse: done.\n")
sh(ps_wt2, "git", "add", "-A"); sh(ps_wt2, "git", "commit", "-qm", "answer H202")
open(os.path.join(ps_org, "04_Personal_Space", "gemini-neon-coder", "Creative_Expression", "neon.txt"), "w").write("glow\n")
r_ps_done2, out_ps_done2 = run(job.done, ps_wt2)
ps_remote_files2 = sh(ps_remote, "git", "show", "--name-only", "--pretty=", "main").stdout.splitlines()
check("done() without NAPKIN_SPACE in env uses the space recorded on the job at take()",
      r_ps_done2 is True
      and "04_Personal_Space/gemini-neon-coder/Creative_Expression/neon.txt" in ps_remote_files2,
      (r_ps_done2, out_ps_done2, ps_remote_files2))

for w in [l.split()[1] for l in sh(ps_root, "git", "worktree", "list", "--porcelain").stdout.split("\n")
          if l.startswith("worktree ")][1:]:
    sh(ps_root, "git", "worktree", "remove", "--force", w)
shutil.rmtree(ps_base)

# H175: job.py merged <ID> marks a job merged in the queue (for hand-committed merges)
m_base, m_root = repo()
m_jid, m_take_out = run(job.take, m_root, "gemini", "s-merged")
m_wt = job.worktree_for(m_root, m_jid)
sh(m_wt, "git", "config", "user.email", "t@example.invalid")
sh(m_wt, "git", "config", "user.name", "T")
m_hp = next(os.path.join(m_wt, "docs", "handoff", n) for n in os.listdir(os.path.join(m_wt, "docs", "handoff"))
            if n.startswith(f"{m_jid}-"))
m_br = state(m_root)["jobs"][m_jid]["branch"]
open(m_hp, "w").write(open(m_hp).read().replace("Status: open", "Status: answered") + "\nResponse: done.\n")
sh(m_wt, "git", "add", "-A"); sh(m_wt, "git", "commit", "-qm", f"{m_jid} answered")
job.QUICKTEST = ["true"]
run(job.done, m_wt)
sh(m_root, "git", "merge", "--no-ff", "-m", f"hand merge {m_jid}", m_br)
ok_m, out_m = run(job.merged_job, m_root, m_jid)
ok_missing, out_missing = run(job.merged_job, m_root, "H999")
check("job.py merged <ID> marks a done job merged, removes worktree/branch, and rejects unknown IDs",
      ok_m and state(m_root)["jobs"][m_jid]["state"] == "merged"
      and not os.path.isdir(m_wt)
      and m_br not in sh(m_root, "git", "branch").stdout
      and not ok_missing and "no such job H999" in out_missing,
      (ok_m, state(m_root)["jobs"][m_jid], out_m, ok_missing, out_missing))
shutil.rmtree(m_base)

print(f"JOB TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
sys.exit(0 if all(RESULTS) else 1)
