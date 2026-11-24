#!/usr/bin/env python3
"""The job queue (P24): a worker takes a job and says done; a dead man's switch flags one gone quiet.

Worker (run in your job's worktree unless it says otherwise):
  python3 tools/job.py take [--as claude|codex|gemini] [--session <name>] [--wait]
                                the first Ready job for you (in the board's order) whose files don't overlap a job
                                in progress: makes ../fretchup-jobs/<id> and <agent>/<id>-<slug> from main, marks it in
                                progress and prints the handoff. A returned job comes first and resumes its branch.
                                One job at a time per session, at most MAX_JOBS per session (P37): then a /clear,
                                which gives a Claude session a new CLAUDE_CODE_SESSION_ID. Run it anywhere in the
                                repository. --wait: nothing Ready? look again every WATCH_POLL until a job is taken
                                (exit 0) or WORKER_WAIT passes (exit 1); holds no job meanwhile. Run it in the
                                background, so the session wakes when it exits.
  python3 tools/job.py guard-checkout
                                refuse tests in the main checkout when this session holds a job elsewhere;
                                SHOPSKETCH_ANY_CHECKOUT=1 allows a deliberate run there (T102)
  python3 tools/job.py beat     "still working": pushes the deadline back. Commits on the job's branch, a quick-test
                                run in its worktree and every job.py command count as beats too.
  python3 tools/job.py run [--limit S] -- <command ...>
                                run a long command (a test) so it can't hang unseen: past HUNG_AFTER (10 min) or
                                --limit seconds it's stopped with every process it started, and it says so (exit 124);
                                else its own exit code. Run it in the background: it always ends, so you're always
                                woken, and a hung test is yours to deal with, not the integrator's (P40)
  python3 tools/job.py check    lists the processes started from your worktree (Godot, freecadcmd, the test
                                scripts) with their age, flags any that look hung, and beats
  python3 tools/job.py test     runs tools/quicktest.sh and records the result for the latest commit
  python3 tools/job.py wait [--scope] "<question>"
                                ask William, or use --scope to ask the integrator about work outside Touches.
                                Run in the background. The switch is paused until an answer or a beat.
                                If it times out, run the same wait command again to keep waiting.
  python3 tools/job.py done     refuses unless the handoff has your response and Status answered, the tree is
                                committed, and the quick test passed. After handoff-only commits it checks the open
                                list and bookkeeping to reuse a clean pass. Otherwise it runs any missing quick test.
                                Then it marks the job done and tells the integrator
Integrator:
  python3 tools/job.py status   the queue as text: jobs in progress, waiting, done, returned; what's Ready
  python3 tools/job.py board    rewrite BOARD.md's job table from docs/handoff/ (in the board's Order line) plus the
                                live state (the commit hook does this on main)
  python3 tools/job.py watch [--once | --next]
                                one line per event (done, stale, waiting, returned, queue empty while a worker waits),
                                and keeps running: run it under your watcher (Monitor). --next: stays quiet about
                                what's true now and stops after the first new event (one wake; run it in the background)
  python3 tools/job.py answer <id> "<text>" [--from integrator|william]
                                deliver an answer through the queue and resume the worker's deadline
                                follow-ups are accepted until the worker reads the answers
  python3 tools/job.py return <id> "<notes>"
                                put a reviewed job back on the queue; the next worker continues its branch
  python3 tools/job.py reassign <id> --to claude|codex|gemini ["<notes>"]
                                hand a returned, in-progress or waiting job to another agent (moves its worktree
                                into <checkout>-jobs/ if needed and drops it from the old session's count)
tools/integrate.py marks a merged job merged and deletes its worktree and branch.

The live state (claims, beats, done) is a JSON file beside the integrator lock in git's common folder
(shopsketch-jobs.json): shared by every worktree, never committed. The jobs themselves are docs/handoff/ entries:
Status "open" is Ready, "queued (after ...)" Queued, "answered" awaiting review; "For" says whose."""
import contextlib
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import handoff

DEADLINE = 30 * 60          # seconds with no beat before a job in progress is stale (P24, tunable)
HUNG_AFTER = 10 * 60        # a process from the worktree older than this looks hung (tunable)
WATCH_POLL = 20             # seconds between watch, take --wait and wait polls (tunable)
MAX_JOBS = 1                # jobs one session takes before it asks William for a /clear (P37, was 3 under P27; tunable)
WORKER_WAIT = 20 * 60       # seconds a worker waits for a job or an answer before timing out (P27, tunable)
QUICKTEST = ["tools/quicktest.sh"]
AGENTS = ("claude", "codex", "gemini")
BOARD = "BOARD.md"
START = "<!-- job table: built by tools/job.py board from docs/handoff/ and the queue; don't edit by hand -->"
END = "<!-- end of job table -->"
ACTIVE = ("in progress", "waiting", "done", "returned")     # a job in one of these holds its files
WORKING = ("in progress", "waiting")                         # ... and in one of these, its session
INTERESTING = re.compile(r"godot|freecad|\.sh\b|python", re.I)
RESPONSE = re.compile(r"^[#*\s]*Response\b", re.M)
USAGE_TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usage.py")


def record_usage(root, event, jid, agent=None, session=None, quiet=True):
    """Notify job-usage passively at a job lifecycle boundary; fail-open so it never blocks a command (T117)."""
    tool = os.environ.get("SHOPSKETCH_USAGE_TOOL", USAGE_TOOL)
    if not tool or not os.path.isfile(tool):
        return
    cmd = [sys.executable, tool, "--repo", root, "snapshot", "--event", event, "--job", jid]
    if agent:
        cmd += ["--agent", agent]
    if session:
        cmd += ["--session", session]
    if quiet:
        cmd.append("--quiet")
    try:
        subprocess.run(cmd, check=False, timeout=5)
    except Exception:
        pass


# ---- git and the state file ----

def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def common_dir(cwd=None):
    cwd = cwd or os.getcwd()
    c = git(cwd, "rev-parse", "--git-common-dir").stdout.strip()
    return os.path.realpath(os.path.join(cwd, c))


def main_root(cwd=None):
    """The main checkout (the one whose .git is the common folder)."""
    return os.path.dirname(common_dir(cwd))


def toplevel(cwd=None):
    return os.path.realpath(git(cwd or os.getcwd(), "rev-parse", "--show-toplevel").stdout.strip())


def state_path(cwd=None):
    return os.path.join(common_dir(cwd), "shopsketch-jobs.json")


def read_state(path):
    try:
        st = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    st.setdefault("jobs", {})
    st.setdefault("events", [])
    st.setdefault("waiting_workers", {})
    return st


@contextlib.contextmanager
def locked(path):
    """Read, change and write the state under a file lock; written atomically."""
    with open(path + ".lock", "w") as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)
        st = read_state(path)
        yield st
        st["events"] = st["events"][-100:]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, indent=1)
        os.replace(tmp, path)


@contextlib.contextmanager
def state_read(path, readonly=False):
    """Read queue state under locked() when writable; fall back to atomic read_state() when .git is read-only."""
    if readonly:
        yield read_state(path)
        return
    cm = locked(path)
    try:
        st = cm.__enter__()
    except PermissionError:
        yield read_state(path)
        return
    try:
        yield st
    except BaseException:
        if not cm.__exit__(*sys.exc_info()):
            raise
    else:
        try:
            cm.__exit__(None, None, None)
        except PermissionError:
            pass


def hhmm(t):
    return time.strftime("%H:%M", time.localtime(t)) if t else "?"


def event(st, kind, jid, text, now):
    st["events"].append({"at": now, "kind": kind, "job": jid, "text": text})


# ---- the jobs (handoff entries) ----

def handoff_texts(root, ref=None):
    """{file name: text} of docs/handoff/, from a git ref (main) or the working tree."""
    if ref:
        names = git(root, "ls-tree", "--name-only", f"{ref}:{handoff.FOLDER}").stdout.split()
        return {n: git(root, "show", f"{ref}:{handoff.FOLDER}/{n}").stdout for n in names if n.endswith(".md")}
    folder = os.path.join(root, handoff.FOLDER)
    if not os.path.isdir(folder):
        return {}
    return {n: open(os.path.join(folder, n), encoding="utf-8").read() for n in os.listdir(folder) if n.endswith(".md")}


def fields(text):
    meta = next((l for l in text.split("\n") if l.startswith("Author:")), "")
    out = {}
    for part in meta.split(" | "):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def jobs_from(texts):
    """[job dict] for every entry For Claude, Codex or either whose Status is open, queued or answered."""
    out = []
    for name, text in texts.items():
        f = fields(text)
        who = f.get("For", "").lower()
        if who not in AGENTS + ("either",):
            continue
        raw = f.get("Status", "")
        s = raw.lower()
        kind = "ready" if s.startswith("open") else "queued" if s.startswith("queued") else \
            "answered" if s.startswith("answered") else None
        if not kind:
            continue
        head = next((l[4:].strip() for l in text.split("\n") if l.startswith("### ")), name)
        jid = head.split()[0]
        waits = re.search(r"after ([^)]*)", raw)
        out.append({"id": jid, "name": name, "for": who, "kind": kind, "item": head.split("—", 1)[-1].strip(),
                    "waits": waits.group(1).strip() if waits else "", "touches": handoff.touches_named(text),
                    # Builds on: H0NN (a trial that merges that job's branch first, H098): its overlap is intended
                    "builds_on": re.findall(r"H\d+", f.get("Builds on", "")),
                    "slug": name[:-3].split("-", 1)[1] if "-" in name[:-3] else "job"})
    return out


def board_order(board_text):
    """Job IDs from the board's "Order:" line, in order."""
    line = next((l for l in board_text.split("\n") if l.startswith("Order:")), "")
    return re.findall(r"\bH(?:\d+|-new-\d+)\b", line)


def ordered(jobs, order):
    pos = {j: i for i, j in enumerate(order)}
    return sorted(jobs, key=lambda j: (pos.get(j["id"], len(pos)), handoff.order(j["name"])))


def branch_claims(root):
    """{job ID: branch} for branches named after a job (<agent>/<id>-<slug>): the board's old claim rule."""
    out = {}
    for b in git(root, "branch", "-a", "--format=%(refname:short)").stdout.split():
        m = re.search(r"(?:^|/)(h\d+)-", b)
        if m:
            out.setdefault(m.group(1).upper(), b)
    return out


def main_view(root):
    """(jobs, order) as main has them: a worker takes what the integrator committed."""
    jobs = jobs_from(handoff_texts(root, "main"))
    return jobs, board_order(git(root, "show", f"main:{BOARD}").stdout)


def overlap(a, b):
    return sorted(handoff.shared_touches(a, b))


def takeable(root, st, agent, jobs, order, claims=None):
    """(the job to take or None, [reasons others were passed over]). Returned jobs for the agent come first."""
    claims = branch_claims(root) if claims is None else claims
    mine = lambda j: j["for"] in (agent, "either")
    back = [j for j in ordered(jobs, order) if st["jobs"].get(j["id"], {}).get("state") == "returned"
            and st["jobs"][j["id"]].get("agent") == agent]
    if back:
        return back[0], []
    busy = {jid: s for jid, s in st["jobs"].items() if s.get("state") in ACTIVE}
    held = {j["id"]: j["touches"] for j in jobs if j["id"] in busy}
    why = []
    for j in ordered(jobs, order):
        if j["kind"] != "ready" or not mine(j) or j["id"] in busy:
            continue
        if j["id"] in claims and j["id"] not in st["jobs"]:
            why.append(f"{j['id']}: claimed by branch {claims[j['id']]}")
            continue
        if st["jobs"].get(j["id"], {}).get("state") == "merged":
            continue
        clash = {other: overlap(j["touches"], t) for other, t in held.items() if other not in j.get("builds_on", ())}
        clash = {k: v for k, v in clash.items() if v}
        if clash:
            why.append(f"{j['id']}: overlaps " + "; ".join(f"{k} ({', '.join(v)})" for k, v in clash.items()))
            continue
        return j, why
    return None, why


# ---- the dead man's switch ----

def etime(s):
    """ps's elapsed time ([[dd-]hh:]mm:ss) in seconds."""
    days, _, rest = s.strip().rpartition("-")
    parts = [int(p) for p in rest.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return (int(days) if days else 0) * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]


def ancestors():
    out, pid = {os.getpid()}, os.getpid()
    for _ in range(30):
        r = subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
        if not r or int(r) <= 1:
            break
        pid = int(r)
        out.add(pid)
    return out


def processes(worktree):
    """[(pid, age in s, command)] for Godot, FreeCAD, scripts and Python running in (or named with) the worktree."""
    wt = os.path.realpath(worktree)
    inside = lambda p: p == wt or p.startswith(wt + os.sep)
    pids, pid = set(), None
    for line in subprocess.run(["lsof", "-d", "cwd", "-Fpn"], capture_output=True, text=True).stdout.split("\n"):
        if line.startswith("p"):
            pid = int(line[1:])
        elif line.startswith("n") and pid and inside(os.path.realpath(line[1:])):
            pids.add(pid)
    skip, out = ancestors(), []
    for line in subprocess.run(["ps", "-axo", "pid=,etime=,command="], capture_output=True, text=True).stdout.split("\n"):
        bits = line.split(None, 2)
        if len(bits) < 3 or not bits[0].isdigit():
            continue
        p, cmd = int(bits[0]), bits[2]
        if p in skip or not INTERESTING.search(cmd) or not (p in pids or wt + os.sep in cmd or cmd.endswith(wt)):
            continue
        out.append((p, etime(bits[1]), cmd))
    return out


def last_commit(root, branch):
    r = git(root, "log", "-1", "--format=%ct", branch)
    return int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else 0


def activity(root, job, now, procs=None):
    """The job's last sign of life: a beat, a commit on its branch, a test run, or a process still running in its
    worktree (one that doesn't look hung)."""
    times = [job.get("beat", 0), job.get("taken", 0), (job.get("test") or {}).get("at", 0),
             last_commit(root, job.get("branch", "HEAD"))]
    if procs is None and job.get("worktree") and os.path.isdir(job["worktree"]):
        try:
            procs = processes(job["worktree"])
        except PermissionError:
            procs = []
    if any(age < HUNG_AFTER for _, age, _ in procs or []):
        times.append(now)
    return max(times)


def refresh(root, job, now, procs=None):
    """A commit after a wait is a beat: the switch is back on. Returns the job's last activity."""
    waiting = job.get("state") == "waiting"
    # The background wait command is itself a process in the worktree.
    act = activity(root, job, now, [] if waiting else procs)
    if waiting and act > job.get("since", now):
        job["state"] = "in progress"
    return act


def stale(job, act, now):
    return job.get("state") == "in progress" and now - act > DEADLINE


# ---- commands ----

def default_agent():
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return "claude"
    if any(k.startswith("CODEX") for k in os.environ):
        return "codex"
    if os.environ.get("ANTIGRAVITY_AGENT") or os.environ.get("ANTIGRAVITY_CONVERSATION_ID"):
        return "gemini"
    return None


def default_session(agent):
    return (os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("CODEX_SESSION_ID")
            or os.environ.get("CODEX_THREAD_ID") or os.environ.get("ANTIGRAVITY_CONVERSATION_ID")
            or os.environ.get("SHOPSKETCH_SESSION") or agent)


def guard_checkout(cwd, out=print):
    """Read-only, fail-open test guard: never lock the queue or use a shared fallback session."""
    try:
        session = default_session(None)
        if os.environ.get("SHOPSKETCH_ANY_CHECKOUT") == "1" or not session:
            return True
        if toplevel(cwd) != main_root(cwd):
            return True
        conv_id = os.environ.get("ANTIGRAVITY_CONVERSATION_ID")
        suffix = f"-{conv_id[:8]}" if conv_id and session == conv_id else None
        for jid, held in read_state(state_path(cwd))["jobs"].items():
            hs = held.get("session")
            if held.get("state") in WORKING and (hs == session or (suffix and isinstance(hs, str) and hs.endswith(suffix))):
                message = (f"you're in the main checkout; your job {jid} is in {held['worktree']}: "
                           "cd there and run it again")
                break
        else:
            return True
    except Exception:                     # a broken/unreadable queue or git must never prevent testing
        return True
    out(message)
    return False


def worktree_for(root, jid):
    return os.path.join(os.path.dirname(root), f"{os.path.basename(root)}-jobs", jid.lower())


def counted(session):
    """A session's jobs count toward MAX_JOBS only when it has a real ID: the fallback (the agent's name) is shared."""
    return session and session not in AGENTS


def jobs_taken(st, session):
    return list(st.get("sessions", {}).get(session, [])) if counted(session) else []


def take(cwd, agent, session, now=None, out=print):
    return _take(cwd, agent, session, now, out)[0]


def _take(cwd, agent, session, now=None, out=print):
    """(job id, None) or (None, "refused" | "empty")."""
    now = now or time.time()
    raw_session = session
    conv_id = os.environ.get("ANTIGRAVITY_CONVERSATION_ID")
    if conv_id and counted(session) and session != conv_id and not session.endswith("-" + conv_id[:8]):
        session = f"{session}-{conv_id[:8]}"
    root = main_root(cwd)
    jobs, order = main_view(root)
    with locked(state_path(cwd)) as st:
        held = [jid for jid, s in st["jobs"].items() if s.get("session") == session and s.get("state") in WORKING]
        if held:
            out(f"refused: this session ({session}) already holds {held[0]}: finish it (job.py done) first")
            return None, "refused"
        n = len(jobs_taken(st, session))
        if n >= MAX_JOBS:
            out(f"refused: this session ({session}) has done {n} jobs ({', '.join(jobs_taken(st, session))}): "
                f"tell William it's ready for a /clear (P27); if you didn't take them, the name was used before: pick a new one")
            return None, "refused"
        job, why = takeable(root, st, agent, jobs, order)
        for w in why:
            out(f"passed over {w}")
        if not job:
            out(f"nothing Ready for {agent}: say so and stop (the integrator is told)")
            return None, "empty"
        prev = st["jobs"].get(job["id"], {})
        if prev.get("state") == "returned":
            branch, wt = prev["branch"], prev.get("worktree") or worktree_for(root, job["id"])
            if not os.path.isdir(wt):
                os.makedirs(os.path.dirname(wt), exist_ok=True)
                r = git(root, "worktree", "add", wt, branch)
                if r.returncode:
                    out(f"refused: couldn't make the worktree: {r.stderr.strip()}")
                    return None, "refused"
        else:
            branch, wt = f"{agent}/{job['id'].lower()}-{job['slug']}", worktree_for(root, job["id"])
            os.makedirs(os.path.dirname(wt), exist_ok=True)
            r = git(root, "worktree", "add", wt, "-b", branch, "main")
            if r.returncode:
                out(f"refused: couldn't make the worktree: {r.stderr.strip()}")
                return None, "refused"
        wt = os.path.realpath(wt)
        os.makedirs(os.path.join(wt, "scratch"), exist_ok=True)     # where the job's logs go (P25); git ignores it
        st["jobs"][job["id"]] = {**{k: prev[k] for k in ("notes", "returned") if k in prev},
                                 "state": "in progress", "agent": agent, "session": session, "branch": branch,
                                 "worktree": wt, "handoff": job["name"], "taken": now, "beat": now}
        answers = prev.get("answers", []) if prev.get("state") == "returned" else []
        st.get("waiting_workers", {}).pop(session, None)
        if raw_session != session:
            st.get("waiting_workers", {}).pop(raw_session, None)
        event(st, "taken", job["id"], f"{agent} ({session}) took {job['id']}", now)
        if counted(session):
            mine = st.setdefault("sessions", {}).setdefault(session, [])
            if job["id"] not in mine:          # a returned job resumed by the same session counts once
                mine.append(job["id"])
            n = len(mine)
    out(f"took {job['id']} ({'resumed, returned' if prev.get('state') == 'returned' else 'new'}): branch {branch}, "
        f"worktree {wt}")
    if prev.get("notes"):
        out(f"the integrator's notes: {prev['notes']}")
    out(f"work in {wt}; run tests and other long commands through `python3 tools/job.py run -- <command>` (in the background: it stops a hung one after 10 min and wakes you; deal with it yourself); when it's done, "
        f"`python3 tools/job.py done`\n")
    if counted(session):
        out(f"job {n} of {MAX_JOBS} for this session (P27)")
    out(open(os.path.join(wt, handoff.FOLDER, job["name"]), encoding="utf-8").read())
    print_answers(answers, out)
    record_usage(root, "take", job["id"], agent=agent, session=session, quiet=True)
    return job["id"], None


def take_wait(cwd, agent, session, wait=None, poll=None, out=print, sleep=time.sleep, clock=time.time):
    """take, looking again every poll seconds while nothing is Ready, for up to wait seconds (P27). Holds no job
    while it looks, so nothing beats or goes stale. Returns the job's id, or None (refused, or timed out)."""
    wait = WORKER_WAIT if wait is None else wait
    poll = WATCH_POLL if poll is None else poll
    start, quiet, registered = clock(), [], False
    try:
        while True:
            said = []
            jid, why = _take(cwd, agent, session, out=out if not quiet else said.append)
            if jid or why == "refused":
                if jid:
                    registered = False         # _take already popped this session under its lock
                for line in said:              # a later look says only what came of it, not "nothing Ready"
                    out(line)
                return jid
            if not quiet:
                out(f"waiting up to {wait // 60} min for a job (looking every {poll} s)")
                sys.stdout.flush()
                quiet.append(1)
            if clock() - start + poll > wait:
                out(f"nothing came in {wait // 60} min: stopping. Tell William the queue is empty for {agent}.")
                return None
            if not registered:
                with locked(state_path(cwd)) as st:
                    st["waiting_workers"][session] = {"agent": agent, "since": start}
                registered = True
            sleep(poll)
    finally:
        if registered:
            with locked(state_path(cwd)) as st:
                st.get("waiting_workers", {}).pop(session, None)


def find_job(st, cwd, jid=None):
    if jid:
        return jid if jid in st["jobs"] else None
    top = toplevel(cwd)
    branch = git(cwd, "branch", "--show-current").stdout.strip()
    for k, j in st["jobs"].items():
        if j.get("state") in ACTIVE and (j.get("worktree") == top or j.get("branch") == branch):
            return k
    return None


def with_job(cwd, jid, out, fn):
    """Run fn(st, id, job) on this worktree's job, under the lock; every such command is a beat."""
    with locked(state_path(cwd)) as st:
        k = find_job(st, cwd, jid)
        if not k:
            out("no job of yours here: run this in your job's worktree (or take one: job.py take)")
            return None
        return fn(st, k, st["jobs"][k])


def beat(cwd, jid=None, now=None, out=print):
    now = now or time.time()

    def go(st, k, j):
        if j.get("state") == "waiting":
            j["state"] = "in progress"
            out(f"{k}: back from waiting")
        j["beat"] = now
        out(f"{k}: beat; deadline {hhmm(now + DEADLINE)}")
        return k
    return with_job(cwd, jid, out, go)


def run(cwd, cmd, limit=None, out=print):
    """Run cmd in its own process group; past limit (HUNG_AFTER) stop the group: the worker is woken either way."""
    limit = limit or HUNG_AFTER
    quiet = lambda s: None
    beat(cwd, None, out=quiet)
    try:
        p = subprocess.Popen(cmd, start_new_session=True)
    except OSError as e:
        out(f"run: can't start {cmd[0]}: {e}")
        return 127
    try:
        rc = p.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        for sig, grace in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
            try:
                os.killpg(p.pid, sig)
            except ProcessLookupError:
                break
            try:
                p.wait(timeout=grace)
                break
            except subprocess.TimeoutExpired:
                continue
        out(f"HUNG: `{' '.join(cmd)[:120]}` ran past {limit // 60} min {limit % 60} s; stopped it and every process "
            "it started. Look at its output or log, fix it, run it again (job.py check lists anything left)")
        rc = 124
    beat(cwd, None, out=quiet)
    return rc


def check(cwd, jid=None, now=None, out=print):
    now = now or time.time()
    top = toplevel(cwd)
    procs = processes(top)
    hung = [p for p in procs if p[1] >= HUNG_AFTER]
    for pid, age, cmd in procs:
        out(f"{'HUNG? ' if age >= HUNG_AFTER else ''}pid {pid}, {age // 60} min {age % 60} s: {cmd[:140]}")
    if not procs:
        out("no processes running from this worktree")
    if hung:
        out(f"{len(hung)} process(es) older than {HUNG_AFTER // 60} min: look at them (kill what's stuck: kill <pid>)")
    beat(cwd, jid, now, out)
    return hung


def print_answers(answers, out):
    for answer in answers:
        out(f"answer from {answer['from']}: {answer['text']}")


def who_is_asked(job):
    return "the integrator (scope)" if job.get("question_kind") == "scope" else "William"


def waiting_line(jid, job):
    return f"waiting: {jid} asks {who_is_asked(job)}: {job.get('question', '')}"


def wait(cwd, question, jid=None, now=None, out=print, *, scope=False, wait=None, poll=None,
         sleep=time.sleep, clock=time.time):
    wait = WORKER_WAIT if wait is None else wait
    poll = WATCH_POLL if poll is None else poll
    start = clock() if now is None else now
    deadline = clock() + wait
    kind = "scope" if scope else "behaviour"

    def register(st, k, j):
        if j.get("state") not in WORKING:
            out(f"refused: {k} is {j.get('state')}")
            return None
        answers = j.pop("answers", [])
        if answers:
            return k, j["taken"], j.get("session"), j.get("since"), answers
        if (j.get("state"), j.get("question"), j.get("question_kind", "behaviour")) != ("waiting", question, kind):
            j.update(state="waiting", question=question, question_kind=kind, since=start, beat=start)
            event(st, "waiting", k, question, start)
        out(waiting_line(k, j))
        return k, j["taken"], j.get("session"), j.get("since"), []

    registered = with_job(cwd, jid, out, register)
    if registered is None:
        return False
    k, taken, session, since, answers = registered
    if answers:
        print_answers(answers, out)
        return True
    sys.stdout.flush()

    path = state_path(cwd)
    while True:
        left = deadline - clock()
        if left > 0:
            sleep(min(poll, left))
        with locked(path) as st:
            j = st["jobs"].get(k, {})
            if (j.get("taken"), j.get("session"), j.get("since")) != (taken, session, since):
                out(f"{k}: this wait has ended")
                return False
            answers = j.pop("answers", [])
            if not answers and j.get("state") != "waiting":
                out(f"{k}: this wait has ended")
                return False
        if answers:
            print_answers(answers, out)
            return True
        if clock() >= deadline:
            out("no answer yet: run job.py wait again to keep waiting")
            return False


def answer(cwd, jid, text, source="integrator", now=None, out=print):
    now = time.time() if now is None else now
    with locked(state_path(cwd)) as st:
        j = st["jobs"].get(jid)
        if j is None:
            out(f"refused: {jid} isn't in the queue")
            return False
        state = j.get("state")
        if state != "waiting" and not (state == "in progress" and j.get("answers")):
            out(f"refused: {jid} is {state}, not waiting for an answer")
            return False
        who = "William" if source == "william" else "integrator"
        j.setdefault("answers", []).append({"from": who, "text": text})
        j.update(state="in progress", beat=now)
        event(st, "answered", jid, text, now)
    out(f"{jid}: answer from {who} recorded")
    return True


PROGRESS_PREFIXES = ("gate: ", "quick: ", "full: ")


def stream_command(cmd, cwd, out=print):
    """Run cmd with stderr merged into stdout, relaying progress lines live and returning (rc, full output)."""
    lines = []
    with subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1) as p:
        for line in p.stdout:
            lines.append(line)
            if line.startswith(PROGRESS_PREFIXES):
                text = line.rstrip("\r\n")
                if out is print:
                    print(text, flush=True)
                else:
                    out(text)
        rc = p.wait()
    return rc, "".join(lines)


def run_quick(top, out=print):
    rc, output = stream_command(QUICKTEST, top, out=out)
    return rc == 0, output.strip().split("\n")[-1:]


def test(cwd, jid=None, out=print):
    top = toplevel(cwd)
    if beat(cwd, jid, out=lambda s: None) is None:
        out("no job of yours here")
        return None
    head = git(top, "rev-parse", "HEAD").stdout.strip()
    clean = not git(top, "status", "--porcelain").stdout.strip()
    ok, tail = run_quick(top, out=out)
    now = time.time()

    def go(st, k, j):
        j["test"] = {"commit": head, "clean": clean, "ok": ok, "at": now}
        j["beat"] = now
        return k
    with_job(cwd, jid, out, go)
    out(("quick test passed" if ok else "QUICK TEST FAILED") + f" on {head[:7]}{'' if clean else ' (uncommitted changes)'}: "
        + " ".join(tail))
    return ok


def quick_pass_covers(top, recorded, head, out):
    if not (recorded.get("clean") and recorded.get("ok")):
        return False
    passed = recorded.get("commit")
    if passed == head:
        return True
    if not passed or git(top, "merge-base", "--is-ancestor", passed, head).returncode:
        return False

    # Compare every commit with its parents, so a revert or merge cannot hide a code change.
    changes = subprocess.run(["git", "log", "--format=", "-m", "--root", "--no-renames", "--name-only", "-z",
                              f"{passed}..{head}", "--"], cwd=top, capture_output=True)
    folder = os.fsencode(handoff.FOLDER + "/")
    index = os.fsencode(handoff.HANDOFF)
    if changes.returncode or any(path != index and not path.startswith(folder)
                                 for path in changes.stdout.split(b"\0") if path):
        return False

    # test_bookkeeping.py exercises result handling on fixtures. Check this worktree's open list too.
    try:
        with open(os.path.join(top, handoff.HANDOFF), encoding="utf-8") as f:
            listed = f.read()
        if handoff.with_list(listed, top) != listed:
            out("the handoff open list is out of date")
            return False
    except (OSError, ValueError, SystemExit) as e:
        out(f"could not check the handoff open list: {e}")
        return False
    if subprocess.run([sys.executable, "tools/test_bookkeeping.py"], cwd=top).returncode:
        out("handoff bookkeeping check failed")
        return False
    out(f"reused the quick-test pass from {passed[:7]} for {head[:7]} after checking the handoff")
    return True


def done(cwd, jid=None, now=None, out=print):
    top = toplevel(cwd)
    with locked(state_path(cwd)) as st:
        k = find_job(st, cwd, jid)
        j = st["jobs"].get(k) if k else None
    if not j:
        out("no job of yours here")
        return False
    path = os.path.join(top, handoff.FOLDER, j["handoff"])
    text = open(path, encoding="utf-8").read() if os.path.isfile(path) else ""
    problems = []
    if not RESPONSE.search(text):
        problems.append(f"{handoff.FOLDER}/{j['handoff']} has no response: append yours (branch, commit, tests, "
                        "anything open)")
    if not re.search(r"\| Status: answered\b", text):
        problems.append(f"{handoff.FOLDER}/{j['handoff']}: set its Status to answered")
    if git(top, "status", "--porcelain").stdout.strip():
        problems.append("uncommitted changes: commit them (the quick test must pass on the latest commit)")
    for pid, age, cmd in processes(top):
        if age >= HUNG_AFTER:
            problems.append(f"pid {pid} has run {age // 60} min from this worktree and looks hung: {cmd[:100]} "
                            "(kill it, or let it finish)")
    if problems:
        for p in problems:
            out("refused: " + p)
        beat(cwd, k, out=lambda s: None)
        return False
    head = git(top, "rev-parse", "HEAD").stdout.strip()
    t = j.get("test") or {}
    if not quick_pass_covers(top, t, head, out):
        out(f"no quick-test pass recorded for {head[:7]}: running it")
        if not test(cwd, k, out):
            out("refused: the quick test failed on the latest commit")
            return False
    if not re.search(r"(?m)^[-*]?\s*Result:\s*[0-9a-f]{7,40}\s*;", text):   # integrate.py copies it (T91)
        out(f"note: {handoff.FOLDER}/{j['handoff']} has no line \"Result: <commit>; <tests>; <what changed>\": "
            "the integrator will write the Work list result by hand (add one and commit to save them that)")
    now = now or time.time()

    def go(st, k, j):
        j.update(state="done", done=now, commit=head, beat=now)
        event(st, "done", k, f"{k} done on {j['branch']} ({head[:7]})", now)
        return k
    with_job(cwd, k, out, go)
    out(f"{k} done: the integrator is told. Tell William \"ready for review: {k}\".")
    out(next_step(read_state(state_path(cwd)), j.get("session")))
    record_usage(main_root(cwd), "done", k, quiet=True)
    return True


def next_step(st, session):
    """What done tells the worker to do next (P27)."""
    n = len(jobs_taken(st, session))
    if n >= MAX_JOBS:
        return f"next: this session has done {n} jobs: tell William you're ready for a /clear"
    return ("next: run `python3 tools/job.py take --wait` in the background (run_in_background): it takes the next "
            f"job, or stops after {WORKER_WAIT // 60} min with nothing (then tell William)"
            + (f"; job {n} of {MAX_JOBS} for this session" if counted(session) else ""))


def return_job(cwd, jid, notes, now=None, out=print):
    now = now or time.time()
    with locked(state_path(cwd)) as st:
        j = st["jobs"].get(jid)
        if not j:
            out(f"{jid} isn't in the queue")
            return False
        j.update(state="returned", notes=notes, returned=now, session=None)
        event(st, "returned", jid, notes, now)
    out(f"{jid} returned: the next {j['agent']} worker to take a job resumes {j['branch']}")
    record_usage(main_root(cwd), "return", jid, quiet=True)
    return True


REASSIGNABLE = ("returned", "in progress", "waiting")


def reassign_job(cwd, jid, to_agent, notes=None, now=None, out=print):
    """Hand a returned, in-progress or waiting job to another agent; the integrator runs this from the main checkout."""
    agent = (to_agent or "").lower()
    if agent not in AGENTS:
        out(f"refused: unknown agent {to_agent!r} (expected one of {', '.join(AGENTS)})")
        return False
    root = main_root(cwd)
    if toplevel(cwd) != root:
        out("refused: run reassign in the main checkout, not a job worktree")
        return False
    now = now or time.time()
    beat_warn = None
    with locked(state_path(cwd)) as st:
        j = st["jobs"].get(jid)
        if not j:
            out(f"{jid} isn't in the queue")
            return False
        state = j.get("state")
        if state not in REASSIGNABLE:
            out(f"refused: {jid} is {state} (can reassign only returned, in progress or waiting jobs)")
            return False
        if state == "in progress":
            act = activity(root, j, now)
            if not stale(j, act, now):
                mins = max(0, int((now - act) // 60))
                beat_warn = f"{jid}: its worker beat {mins} min ago; tell that worker to stop"
        jobs_dir = os.path.realpath(os.path.dirname(worktree_for(root, jid)))
        target = os.path.realpath(worktree_for(root, jid))
        wt = j.get("worktree")
        if wt:
            wt_real = os.path.realpath(wt)
            if not wt_real.startswith(jobs_dir + os.sep):
                if os.path.isdir(wt_real):
                    if os.path.exists(target):   # git worktree move into an existing folder nests the worktree inside it (exit 0)
                        out(f"refused: couldn't move worktree {wt_real} to {target}: target already exists")
                        return False
                    os.makedirs(jobs_dir, exist_ok=True)
                    r = git(root, "worktree", "move", wt_real, target)
                    if r.returncode != 0:
                        err = r.stderr.strip() or r.stdout.strip() or f"exit {r.returncode}"
                        out(f"refused: couldn't move worktree {wt_real} to {target}: {err}")
                        return False
                    wt = os.path.realpath(target)
                else:
                    wt = target
            else:
                wt = wt_real
        else:
            wt = target
        old_agent = j.get("agent")
        note = notes if notes else f"reassigned from {old_agent} by the integrator"
        for sess_jobs in st.get("sessions", {}).values():
            while jid in sess_jobs:
                sess_jobs.remove(jid)
        j.update(state="returned", agent=agent, session=None, notes=note, returned=now, worktree=wt)
        event(st, "reassigned", jid, note, now)
        branch = j.get("branch")
    if beat_warn:
        out(beat_warn)
    if wt and os.path.isdir(wt):
        dirty = [l for l in git(wt, "status", "--porcelain").stdout.splitlines() if l.strip()]
        if dirty:
            out(f"{jid}: {len(dirty)} files not committed in {wt}")
    out(f"{jid} reassigned to {agent}: the next {agent} worker resumes {branch} in {wt}")
    return True


STANDING = {"main", "small-fixes", "codex/small-fixes"}   # never removed: the light path's branches (P22) stay


def merged(root, branch, now=None, out=print):
    """After integrate.py merged a branch: the job is merged; its worktree and branch go (not a standing branch's)."""
    if branch in STANDING:
        out(f"kept {branch} and its worktree: a standing branch (P22)")
        return None
    now = now or time.time()
    path = state_path(root)
    with locked(path) as st:
        k = next((k for k, j in st["jobs"].items() if j.get("branch") == branch), None)
        if k:
            st["jobs"][k].update(state="merged", merged=now)
            event(st, "merged", k, branch, now)
        wt = st["jobs"][k].get("worktree") if k else None
    if not wt:
        for block in git(root, "worktree", "list", "--porcelain").stdout.split("\n\n"):
            if f"branch refs/heads/{branch}" in block:
                wt = block.split("\n")[0].split(" ", 1)[1]
    if wt and os.path.isdir(wt):
        r = git(root, "worktree", "remove", wt)
        out(f"removed the worktree {wt}" if r.returncode == 0 else
            f"left the worktree {wt}: {r.stderr.strip()} (remove it by hand when it's safe)")
    r = git(root, "branch", "-d", branch)
    out(f"deleted the branch {branch}" if r.returncode == 0 else f"kept the branch {branch}: {r.stderr.strip()}")
    return k


# ---- what the integrator sees ----

def live_label(job, act, now):
    s = job.get("state")
    who = job.get("agent", "?")
    if s == "in progress":
        if stale(job, act, now):
            return f"**Stale** ({who}, no beat since {hhmm(act)})"
        return f"In progress ({who} since {hhmm(job.get('taken'))})"
    if s == "waiting":
        return f"Waiting on {who_is_asked(job)} ({who}): {job.get('question', '')}"
    if s == "done":
        return f"**Done**: for review ({who})"
    if s == "returned":
        return f"Returned: **Ready** for {who.capitalize()} (resumes {job.get('branch')})"
    return None


def active_waiting(st, now):
    """Drop stale waiting_workers entries (older than WORKER_WAIT + WATCH_POLL) and return waiting agents."""
    waiting = st.setdefault("waiting_workers", {})
    limit = WORKER_WAIT + WATCH_POLL
    for s in [s for s, info in waiting.items()
              if not isinstance(info, dict) or now - info.get("since", 0) > limit]:
        del waiting[s]
    return {info.get("agent") for info in waiting.values() if info.get("agent")}


def conditions(root, st, jobs, order, now, procs=None):
    """{key: line} for everything the integrator should hear about now. A key changes when the event is new."""
    out = {}
    for k, j in st["jobs"].items():
        s = j.get("state")
        if s == "done":
            out[("done", k, j.get("done"))] = f"done: {k} on {j.get('branch')}: review it (tools/integrate.py)"
        elif s == "returned":
            out[("returned", k, j.get("returned"), j.get("agent"))] = f"returned: {k} waits for a {j.get('agent')} worker"
        elif s in WORKING:
            act = refresh(root, j, now, (procs or {}).get(k))
            if j["state"] == "waiting":
                out[("waiting", k, j.get("since"))] = waiting_line(k, j)
            elif stale(j, act, now):
                out[("stale", k, act)] = (f"stale: {k} ({j.get('agent')}) no beat since {hhmm(act)}: check "
                                          f"{j.get('branch')} in {j.get('worktree')}")
    claims = branch_claims(root)
    waiting_agents = active_waiting(st, now)
    for agent in AGENTS:
        if agent not in waiting_agents:
            continue
        job, _ = takeable(root, st, agent, jobs, order, claims)
        if not job:
            out[("empty", agent)] = (f"queue empty for {agent.capitalize()}: a worker is waiting with nothing Ready "
                                     "(check in with William)")
    return out


def watch(cwd, once=False, out=print, now=None, until_new=False):
    """until_new: say nothing about what's true now, wait for the first new event, print it and stop: one wake for
    a watcher run in the background (Bash run_in_background), no timer (H050)."""
    root = main_root(cwd)
    seen = None if until_new else set()
    while True:
        t = now or time.time()
        jobs, order = main_view(root)
        with state_read(state_path(cwd)) as st:
            cur = conditions(root, st, jobs, order, t)
        new = [line for key, line in cur.items() if seen is not None and key not in seen]
        for line in new:
            out(f"{hhmm(t)} {line}")
        sys.stdout.flush()
        seen = set(cur)
        if once or (until_new and new):
            return cur
        time.sleep(WATCH_POLL)


def status(cwd, out=print, now=None, readonly=False):
    now = now or time.time()
    root = main_root(cwd)
    jobs, order = main_view(root)
    with state_read(state_path(cwd), readonly=readonly) as st:
        live = [(k, j) for k, j in st["jobs"].items() if j.get("state") in ACTIVE]
        for k, j in live:
            act = refresh(root, j, now)
            left = DEADLINE - (now - act)
            extra = f"; deadline in {int(left // 60)} min" if j.get("state") == "in progress" and left > 0 else ""
            label = waiting_line(k, j) if j.get("state") == "waiting" else f"{k}: {live_label(j, act, now)}"
            out(f"{label}; {j.get('branch')}; last sign of life {hhmm(act)}{extra}")
        if not live:
            out("no job in progress")
        for agent in AGENTS:
            job, why = takeable(root, st, agent, jobs, order)
            out(f"next for {agent.capitalize()}: " + (f"{job['id']} ({job['item']})" if job else "nothing Ready")
                + (f" [passed over: {'; '.join(why)}]" if why else ""))


def table(root, st, jobs, order, now):
    rows = ["| Job | For | Status | Item | Handoff | Waits for |", "|---|---|---|---|---|---|"]
    claims = branch_claims(root)
    for j in ordered(jobs, order):
        s = {"ready": "**Ready**", "queued": "Queued", "answered": "Answered: for review"}[j["kind"]]
        live = st["jobs"].get(j["id"])
        if live and live.get("state") in ACTIVE:
            s = live_label(live, activity(root, live, now, procs=[]), now)
        elif j["id"] in claims and j["kind"] == "ready" and not live:
            s = f"Claimed: branch {claims[j['id']]}"
        who = "either" if j["for"] == "either" else j["for"].capitalize()
        item = j["item"].replace("|", "/")
        rows.append(f"| {j['id']} | {who} | {s} | {item} | [{j['id']}]({handoff.FOLDER}/{j['name']}) | {j['waits']} |")
    return "\n".join(rows)


def board_text(text, root, st, now):
    if START not in text or END not in text:
        raise SystemExit(f"{BOARD} has no job-table markers ({START} ... {END})")
    jobs = jobs_from(handoff_texts(root))
    a, b = text.index(START) + len(START), text.index(END)
    return text[:a] + "\n\n" + table(root, st, jobs, board_order(text), now) + "\n\n" + text[b:]


def board(cwd, now=None, out=print):
    now = now or time.time()
    top = toplevel(cwd)
    path = os.path.join(top, BOARD)
    text = open(path, encoding="utf-8").read()
    st = read_state(state_path(cwd))
    new = board_text(text, top, st, now)
    if new != text:
        open(path, "w", encoding="utf-8").write(new)
        out(f"rebuilt the job table in {BOARD}")
    return new != text


def main(argv):
    cwd = os.getcwd()
    cmd = argv[0] if argv else "status"
    if "-h" in argv or "--help" in argv:                 # help only: never take, finish or return a job by accident
        print(__doc__)
        return 0
    opt = lambda name: argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None
    if cmd == "guard-checkout":
        return 0 if guard_checkout(cwd) else 1
    if cmd == "take":
        agent = (opt("--as") or default_agent() or "").lower()
        if agent not in AGENTS:
            print("say who you are: job.py take --as claude|codex|gemini")
            return 2
        session = opt("--session") or default_session(agent)
        if "--wait" in argv:
            return 0 if take_wait(cwd, agent, session) else 1
        return 0 if take(cwd, agent, session) else 1
    if cmd == "beat":
        return 0 if beat(cwd, opt("--job")) else 1
    if cmd == "check":
        check(cwd, opt("--job"))
        return 0
    if cmd == "run" and "--" in argv and argv.index("--") + 1 < len(argv):
        lim = opt("--limit")
        return run(cwd, argv[argv.index("--") + 1:], int(lim) if lim else None)
    if cmd == "test":
        return 0 if test(cwd, opt("--job")) else 1
    if cmd == "wait":
        args = argv[1:]
        scope = args[:1] == ["--scope"]
        if scope:
            args = args[1:]
        if len(args) != 1 and not (len(args) == 3 and args[1] == "--job"):
            print('usage: job.py wait [--scope] "<question>"')
            return 2
        return 0 if wait(cwd, args[0], args[2] if len(args) == 3 else None, scope=scope) else 1
    if cmd == "answer":
        source = argv[4] if len(argv) == 5 and argv[3] == "--from" else "integrator" if len(argv) == 3 else None
        if source not in ("integrator", "william"):
            print('usage: job.py answer <id> "<text>" [--from integrator|william]')
            return 2
        return 0 if answer(cwd, argv[1].upper(), argv[2], source) else 1
    if cmd == "done":
        return 0 if done(cwd, opt("--job")) else 1
    if cmd == "status":
        status(cwd)
        return 0
    if cmd == "board":
        board(cwd)
        return 0
    if cmd == "watch":
        watch(cwd, once="--once" in argv, until_new="--next" in argv)
        return 0
    if cmd == "return" and len(argv) >= 3:
        return 0 if return_job(cwd, argv[1].upper(), argv[2]) else 1
    if cmd == "reassign":
        to = (opt("--to") or "").lower()
        pos, i = [], 1
        while i < len(argv):
            if argv[i] == "--to":
                i += 2
            else:
                pos.append(argv[i])
                i += 1
        if to not in AGENTS or not (1 <= len(pos) <= 2):
            print('usage: job.py reassign <id> --to claude|codex|gemini ["<notes>"]')
            return 2
        return 0 if reassign_job(cwd, pos[0].upper(), to, pos[1] if len(pos) > 1 else None) else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
