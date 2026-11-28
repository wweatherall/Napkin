#!/usr/bin/env python3
"""The job queue (P24): a worker takes a job and says done; a dead man's switch flags one gone quiet.

Worker (run in your job's worktree unless it says otherwise):
  python3 tools/job.py take [--as claude|codex|gemini] [--session <name>] [--wait]
                                the first Ready job for you (in the board's order) whose files don't overlap a job
                                in progress: makes ../.worktrees/<checkout>/<id> (P63) and <agent>/<id>-<slug> from main, marks it in
                                progress and prints the handoff. A returned job comes first and resumes its branch.
                                One job at a time per session, at most MAX_JOBS per session (P37): then a /clear,
                                which gives a Claude session a new CLAUDE_CODE_SESSION_ID. Run it anywhere in the
                                repository. --wait: nothing Ready? look again every WATCH_POLL until a job is taken
                                (exit 0) or WORKER_WAIT passes (exit 1); holds no job meanwhile. Run it in the
                                background, so the session wakes when it exits.
  python3 tools/job.py guard-checkout
                                refuse tests in the main checkout when this session holds a job elsewhere;
                                NAPKIN_ANY_CHECKOUT=1 allows a deliberate run there (T102)
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
                                live state (the commit hook does this on main); a checkout at
                                comitatus/08_Code_Bases/<name> also copies the table to comitatus/05_Jobs/<name>.md (P57)
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
                                into ../.worktrees/<checkout>/ if needed and drops it from the old session's count)
  python3 tools/job.py merged <id>
                                mark a job merged in the queue (for any merge finished outside integrate.py)
tools/integrate.py marks a merged job merged and deletes its worktree and branch.

The live state (claims, beats, done) is a JSON file beside the integrator lock in git's common folder
(napkin-jobs.json): shared by every worktree, never committed. The jobs themselves are docs/handoff/ entries:
Status "open" is Ready, "queued (after ...)" Queued, "answered" awaiting review; "For" says whose."""
import contextlib
import datetime
import fcntl
import glob
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import handoff

DEADLINE = 30 * 60          # seconds with no beat before a job in progress is stale (P24, tunable)
HUNG_AFTER = 10 * 60        # a process from the worktree older than this looks hung (tunable)
LAUNCH_TIMEOUT = 10 * 60    # seconds a launched worker has to take its job before the hopper wakes (H185)
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
TAKEN = ("in progress", "waiting", "done")                  # a launched worker has taken its job (not "returned":
                                                            # a resumed returned job is still returned until it's taken)
INTERESTING = re.compile(r"godot|freecad|\.sh\b|python", re.I)
RESPONSE = re.compile(r"^[#*\s]*Response\b", re.M)


def record_journal(root, line):
    """Fail-open: append a one-line breadcrumb to the rolling 20-line integrator journal."""
    try:
        import integrator
        integrator.log_note(line, root=root, out=lambda *_: None)
    except Exception:
        pass


def save_personal_space(root, agent, space=None):
    """Fail-open: commit and push the worker's personal space at the end of a job."""
    if not space and agent not in AGENTS:
        return
    try:
        import launch
        default_space = launch.space_of(agent)
    except Exception:
        default_space = f"{agent}-coder"
    try:
        import personal_space
        personal_space.save(space or default_space, root=root)
    except Exception:
        pass


def record_usage(root, event, jid, agent=None, session=None, quiet=True):
    """Notify job-usage passively at a job lifecycle boundary; fail-open so it never blocks a command (T117)."""
    tool = os.environ.get("NAPKIN_USAGE_TOOL", USAGE_TOOL)
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


def _usage_tool():
    """comitatus/09_Tools/MEASURE_TOKEN_USE.py when the main checkout sits under 08_Code_Bases, else ''."""
    top = main_root(HERE)
    parent = os.path.dirname(top)
    if os.path.basename(parent) != "08_Code_Bases":
        return ""
    return os.path.join(os.path.dirname(parent), "09_Tools", "MEASURE_TOKEN_USE.py")


USAGE_TOOL = _usage_tool()


def toplevel(cwd=None):
    return os.path.realpath(git(cwd or os.getcwd(), "rev-parse", "--show-toplevel").stdout.strip())


def state_path(cwd=None):
    new = os.path.join(common_dir(cwd), "napkin-jobs.json")
    old = os.path.join(os.path.dirname(new), "shopsketch-jobs.json")
    if not os.path.exists(new) and os.path.exists(old):
        try:
            os.replace(old, new)
        except OSError:
            pass
    return new


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
        names = [n for n in git(root, "ls-tree", "--name-only", f"{ref}:{handoff.FOLDER}").stdout.split() if n.endswith(".md")]
        if not names:
            return {}
        specs = "".join(f"{ref}:{handoff.FOLDER}/{n}\n" for n in names).encode("utf-8")
        r = subprocess.run(["git", "cat-file", "--batch"], cwd=root, input=specs, capture_output=True)
        if r.returncode != 0:
            return {n: git(root, "show", f"{ref}:{handoff.FOLDER}/{n}").stdout for n in names}
        raw, pos, out = r.stdout, 0, {}
        for n in names:
            nl = raw.find(b"\n", pos)
            if nl == -1:
                out[n] = ""
                continue
            header = raw[pos:nl].decode("utf-8", errors="replace")
            pos = nl + 1
            parts = header.split()
            if len(parts) >= 3 and parts[2].isdigit():
                size = int(parts[2])
                out[n] = raw[pos:pos + size].decode("utf-8", errors="replace")
                pos += size + 1
            else:
                out[n] = ""
        return out
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


VALID_PACES = ("all at once", "one at a time")


def board_pace(board_text):
    """(pace, warning) from the board's "Pace:" line. Missing or unknown values fall back to "one at a time" (P75:
    "all at once" only when the board says so)."""
    line = next((l for l in (board_text or "").split("\n") if l.startswith("Pace:")), None)
    if line is None:
        return "one at a time", None
    raw = line.split(":", 1)[1].strip()
    if not raw:
        return "one at a time", None
    val = raw.lower()
    if val in VALID_PACES:
        return val, None
    return "one at a time", f"warning: unknown Pace {raw!r} in {BOARD} (expected 'one at a time' or 'all at once'; treating as 'one at a time')"


def main_pace(root):
    """(pace, warning) as main's BOARD.md has it."""
    r = git(root, "show", f"main:{BOARD}")
    return board_pace(r.stdout if r.returncode == 0 else "")


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


DEP_ID = re.compile(r"\bH\d+\b")


def resolve_dependencies(jobs, st=None):
    """Return jobs with queued H0NN dependencies resolved against unmerged entries and queue state."""
    job_states = (st or {}).get("jobs", {})
    unmerged = {j["id"] for j in jobs if job_states.get(j["id"], {}).get("state") != "merged"}
    out = []
    for j in jobs:
        if j["kind"] == "queued":
            deps = list(dict.fromkeys(DEP_ID.findall(j["waits"])))
            if deps:
                remaining = [d for d in deps if d in unmerged]
                if not remaining:
                    j = {**j, "kind": "ready", "waits": ""}
                elif len(remaining) < len(deps):
                    j = {**j, "waits": ", ".join(remaining)}
        out.append(j)
    return out


def _pacing_jobs(st):
    """Jobs that hold the `one at a time` pace (P74): only `in progress` jobs; waiting workers idle."""
    return [jid for jid, s in st["jobs"].items() if s.get("state") == "in progress"]


def takeable(root, st, agent, jobs, order, claims=None, pace="all at once"):
    """(the job to take or None, [reasons others were passed over]). Returned jobs for the agent come first."""
    if pace == "one at a time":
        pacing = _pacing_jobs(st)
        if pacing:
            return None, [f"pace is one at a time ({', '.join(pacing)} active)"]
    jobs = resolve_dependencies(jobs, st)
    claims = branch_claims(root) if claims is None else claims
    launched_for = {jid for jid, info in st.get("launched", {}).items() if info.get("agent") == agent}
    mine = lambda j: j["for"] in (agent, "either") or j["id"] in launched_for   # P78: routed to this agent
    back = [j for j in ordered(jobs, order) if st["jobs"].get(j["id"], {}).get("state") == "returned"
            and st["jobs"][j["id"]].get("agent") == agent]
    if back:
        return back[0], []
    active_ids = {jid for jid, s in st["jobs"].items() if s.get("state") in ACTIVE}
    blocking_states = ("in progress", "waiting", "returned") if pace == "one at a time" else ACTIVE
    busy = {jid: s for jid, s in st["jobs"].items() if s.get("state") in blocking_states}
    held = {j["id"]: j["touches"] for j in jobs if j["id"] in busy}
    why = []
    for j in ordered(jobs, order):
        if j["kind"] != "ready" or not mine(j) or j["id"] in active_ids:
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


def ancestors(ppids=None):
    out, pid = {os.getpid()}, os.getpid()
    if ppids is not None:
        for _ in range(30):
            ppid = ppids.get(pid, 0)
            if ppid <= 1:
                break
            pid = ppid
            out.add(pid)
        return out
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
    rows, ppids = [], {}
    for line in subprocess.run(["ps", "-axo", "pid=,ppid=,etime=,command="], capture_output=True, text=True).stdout.split("\n"):
        bits = line.split(None, 3)
        if len(bits) < 4 or not bits[0].isdigit() or not bits[1].isdigit():
            continue
        p, pp = int(bits[0]), int(bits[1])
        ppids[p] = pp
        rows.append((p, bits[2], bits[3]))
    skip, out = ancestors(ppids), []
    for p, age, cmd in rows:
        if p in skip or not INTERESTING.search(cmd) or not (p in pids or wt + os.sep in cmd or cmd.endswith(wt)):
            continue
        out.append((p, etime(age), cmd))
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
            or os.environ.get("NAPKIN_SESSION") or agent)


def guard_checkout(cwd, out=print):
    """Read-only, fail-open test guard: never lock the queue or use a shared fallback session."""
    try:
        session = default_session(None)
        if os.environ.get("NAPKIN_ANY_CHECKOUT") == "1" or not session:
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


def jobs_dir(root):
    """Where a checkout's job worktrees go: <parent>/.worktrees/<checkout>/ (P63), one hidden place for every code base."""
    return os.path.join(os.path.dirname(root), ".worktrees", os.path.basename(root))


def worktree_for(root, jid):
    return os.path.join(jobs_dir(root), jid.lower())


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
    pace, _ = main_pace(root)
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
        job, why = takeable(root, st, agent, jobs, order, pace=pace)
        for w in why:
            out(f"passed over {w}")
        if not job:
            out(f"nothing Ready for {agent}: say so and stop (the integrator is told)")
            return None, "empty"
        prev = st["jobs"].get(job["id"], {})
        base_ref = "main"
        if prev.get("state") == "returned":
            branch, wt = prev["branch"], prev.get("worktree") or worktree_for(root, job["id"])
            if not os.path.isdir(wt):
                os.makedirs(os.path.dirname(wt), exist_ok=True)
                r = git(root, "worktree", "add", wt, branch)
                if r.returncode:
                    out(f"refused: couldn't make the worktree: {r.stderr.strip()}")
                    return None, "refused"
        else:
            if pace == "one at a time":
                touches_by_id = {jb["id"]: jb["touches"] for jb in jobs}
                done_overlaps = [
                    (jid, s) for jid, s in st["jobs"].items()
                    if s.get("state") == "done" and s.get("branch")
                    and overlap(job["touches"], touches_by_id.get(jid, ()))
                ]
                if done_overlaps:
                    _, newest_s = max(done_overlaps, key=lambda pair: (pair[1].get("done") or 0, pair[1].get("taken") or 0))
                    base_ref = newest_s["branch"]
            branch, wt = f"{agent}/{job['id'].lower()}-{job['slug']}", worktree_for(root, job["id"])
            os.makedirs(os.path.dirname(wt), exist_ok=True)
            r = git(root, "worktree", "add", wt, "-b", branch, base_ref)
            if r.returncode:
                out(f"refused: couldn't make the worktree: {r.stderr.strip()}")
                return None, "refused"
        wt = os.path.realpath(wt)
        os.makedirs(os.path.join(wt, "scratch"), exist_ok=True)     # where the job's logs go (P25); git ignores it
        brief = os.path.join(wt, handoff.FOLDER, job["name"])
        if base_ref != "main" and not os.path.isfile(brief):
            # Stacked on a done branch that predates the brief (H211): bring main's brief in; the worker commits it.
            os.makedirs(os.path.dirname(brief), exist_ok=True)
            shutil.copyfile(os.path.join(root, handoff.FOLDER, job["name"]), brief)
        try:
            import launch
            default_space = launch.space_of(agent)
        except Exception:
            default_space = f"{agent}-coder"
        space = os.environ.get("NAPKIN_SPACE") or default_space
        entry = {**{k: prev[k] for k in ("notes", "returned", "base", "windows", "resume_cmd") if k in prev},
                 "state": "in progress", "agent": agent, "session": session, "branch": branch,
                 "worktree": wt, "handoff": job["name"], "space": space, "taken": now, "beat": now}
        if base_ref != "main":
            entry["base"] = base_ref
        launched_info = st.get("launched", {}).pop(job["id"], None) or {}
        if launched_info.get("window") and launched_info["window"] not in entry.get("windows", []):
            entry.setdefault("windows", []).append(launched_info["window"])
        st["jobs"][job["id"]] = entry
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
        f"`python3 tools/SUBMIT_JOB.py`\n")
    if counted(session):
        out(f"job {n} of {MAX_JOBS} for this session (P27)")
    out(open(brief, encoding="utf-8").read())
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
    record_journal(main_root(cwd), f"answered {jid} ({who}): {text[:100]}")
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


def record_test(cwd, ok=True, jid=None, commit=None, clean=None, out=print):
    """Record a quick-test result (commit, clean, ok, at) for the current job worktree, if any."""
    top = toplevel(cwd)
    head = commit or git(top, "rev-parse", "HEAD").stdout.strip()
    if clean is None:
        clean = not git(top, "status", "--porcelain").stdout.strip()
    now = time.time()

    def go(st, k, j):
        j["test"] = {"commit": head, "clean": bool(clean), "ok": bool(ok), "at": now}
        j["beat"] = now
        return k
    return with_job(cwd, jid, lambda _s: None, go)


def test(cwd, jid=None, out=print):
    top = toplevel(cwd)
    if beat(cwd, jid, out=lambda s: None) is None:
        out("no job of yours here")
        return None
    head = git(top, "rev-parse", "HEAD").stdout.strip()
    clean = not git(top, "status", "--porcelain").stdout.strip()
    ok, tail = run_quick(top, out=out)
    record_test(cwd, ok=ok, jid=jid, commit=head, clean=clean, out=out)
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


FEEDBACK_FILE = "docs/worker-feedback.md"
FEEDBACK_HEADER = (
    "# Worker feedback\n\n"
    "<!-- Recorded by tools/SUBMIT_JOB.py (job.py done). Kept here in full; unread entries appear in the integrator brief. -->\n"
)
FEEDBACK_Q1 = "How was working on this job in our code base?"
FEEDBACK_Q1_RESUBMIT = "How was the review round: were the return notes clear, and what would have avoided the return?"
FEEDBACK_Q2 = "Any improvements you can think of?"


def _path_in(path, wt):
    if not path or not wt:
        return False
    p = os.path.realpath(path)
    return p == wt or p.startswith(wt + os.sep)


def _parse_ts(val):
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str) or not val.strip():
        return None
    try:
        return datetime.datetime.fromisoformat(val.strip().replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _extract_agy_tool_strings(row):
    parts = []
    for tc in row.get("tool_calls") or []:
        if not isinstance(tc, dict):
            continue
        args = tc.get("args")
        if isinstance(args, dict):
            parts.extend(v for v in args.values() if isinstance(v, str))
        elif args is not None:
            parts.append(str(args))
    return " ".join(parts)


def _find_gemini_conv(wt, taken=None, session=None, agy_brain=None):
    brain = os.path.expanduser(agy_brain) if agy_brain else os.environ.get(
        "AGY_BRAIN_DIR", os.path.expanduser("~/.gemini/antigravity-cli/brain")
    )
    env_conv = os.environ.get("ANTIGRAVITY_CONVERSATION_ID") if agy_brain is None else None
    candidates = []
    if brain and os.path.isdir(brain):
        try:
            entries = os.listdir(brain)
        except OSError:
            entries = []
        for entry in entries:
            tpath = os.path.join(brain, entry, ".system_generated", "logs", "transcript.jsonl")
            try:
                mt = os.stat(tpath).st_mtime
            except OSError:
                continue
            if taken is not None and mt < taken - 60:
                continue
            candidates.append((mt, entry, tpath))
        candidates.sort(key=lambda x: x[0], reverse=True)
    matched = []
    for _, conv_id, tpath in candidates:
        is_int = False
        touches_wt = False
        try:
            with open(tpath, encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(row, dict):
                        continue
                    rtype = row.get("type")
                    if rtype == "USER_INPUT":
                        content = str(row.get("content") or "")
                        if "you are the integrator" in content.lower():
                            is_int = True
                        if wt and wt in content:
                            touches_wt = True
                    elif rtype == "PLANNER_RESPONSE":
                        tstr = _extract_agy_tool_strings(row)
                        if "integrator.py take" in tstr or "--role integrator" in tstr:
                            is_int = True
                        if wt and wt in tstr:
                            touches_wt = True
        except OSError:
            continue
        if not is_int and touches_wt:
            matched.append(conv_id)
    if env_conv and env_conv in matched:
        return env_conv
    if session and session in matched:
        return session
    if matched:
        return matched[0]
    return env_conv


def _find_claude_session(wt, taken=None, session=None, claude_dir=None):
    cdir = claude_dir if claude_dir is not None else os.environ.get("CLAUDE_USAGE_DIR", "/Users/Will/Sites/claude-usage")
    env_sid = os.environ.get("CLAUDE_CODE_SESSION_ID") if claude_dir is None else None
    spath = os.path.join(os.path.expanduser(cdir), "sessions.jsonl") if cdir else ""
    matched = []
    if spath and os.path.isfile(spath):
        try:
            with open(spath, encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(row, dict):
                        continue
                    ts = _parse_ts(row.get("ts"))
                    if taken is not None and ts is not None and ts < taken - 60:
                        continue
                    if _path_in(row.get("cwd"), wt) and row.get("session_id"):
                        matched.append((ts or 0.0, row["session_id"]))
        except OSError:
            pass
    if matched:
        matched.sort(key=lambda x: x[0])
        sids = [sid for _, sid in matched]
        if env_sid and env_sid in sids:
            return env_sid
        return sids[-1]
    return env_sid


def _find_codex_session(wt, taken=None, session=None, codex_dir=None):
    cdir = codex_dir if codex_dir is not None else os.environ.get("CODEX_SESSIONS_DIR", os.path.expanduser("~/.codex/sessions"))
    env_sid = (os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID")) if codex_dir is None else None
    files = []
    if cdir and os.path.isdir(os.path.expanduser(cdir)):
        pattern = os.path.join(os.path.expanduser(cdir), "**", "rollout-*.jsonl")
        for path in glob.iglob(pattern, recursive=True):
            try:
                mt = os.stat(path).st_mtime
            except OSError:
                continue
            if taken is not None and mt < taken - 60:
                continue
            files.append((mt, path))
        files.sort(key=lambda x: x[0], reverse=True)
    cwd_matches, text_matches = [], []
    for _, path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                first = f.readline()
                meta = json.loads(first)
                if not isinstance(meta, dict) or meta.get("type") != "session_meta":
                    continue
                payload = meta.get("payload") or {}
                sid = payload.get("id")
                if not sid:
                    continue
                if _path_in(payload.get("cwd"), wt):
                    cwd_matches.append(sid)
                    continue
                if wt and wt in f.read():
                    text_matches.append(sid)
        except (OSError, ValueError):
            continue
    matches = cwd_matches or text_matches
    if matches:
        if session and session in matches:
            return session
        if env_sid and env_sid in matches:
            return env_sid
        return matches[0]
    return env_sid


def find_resume_command(agent, worktree, taken=None, session=None, claude_dir=None, agy_brain=None, codex_dir=None):
    """Find the session's resume command from the agent's transcript/rollout matching `worktree` (H207)."""
    wt = os.path.realpath(worktree) if worktree else None
    if agent == "gemini":
        cid = _find_gemini_conv(wt, taken=taken, session=session, agy_brain=agy_brain)
        return f"agy --conversation {cid}" if cid else None
    if agent == "claude":
        sid = _find_claude_session(wt, taken=taken, session=session, claude_dir=claude_dir)
        return f"claude --resume {sid}" if sid else None
    if agent == "codex":
        sid = _find_codex_session(wt, taken=taken, session=session, codex_dir=codex_dir)
        return f"codex resume {sid}" if sid else None
    return None


def parse_feedback_entries(text):
    """Parse docs/worker-feedback.md into [(heading_key, [lines])]."""
    entries, cur_key, cur_lines = [], None, []
    for line in text.splitlines():
        if line.startswith("### "):
            if cur_key is not None:
                entries.append((cur_key, cur_lines))
            cur_key = line[4:].strip()
            cur_lines = []
        elif cur_key is not None:
            cur_lines.append(line)
    if cur_key is not None:
        entries.append((cur_key, cur_lines))
    return entries


def record_feedback(top, jid, agent, session, resubmit, feedback, improvements, now=None):
    """Append one dated entry to docs/worker-feedback.md and commit it on the job's branch (H207)."""
    fb_path = os.path.join(top, FEEDBACK_FILE)
    os.makedirs(os.path.dirname(fb_path), exist_ok=True)
    if not os.path.isfile(fb_path):
        with open(fb_path, "w", encoding="utf-8") as f:
            f.write(FEEDBACK_HEADER)
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(now or time.time()))
    kind = "resubmit" if resubmit else "first submit"
    q1 = FEEDBACK_Q1_RESUBMIT if resubmit else FEEDBACK_Q1
    entry = (
        f"\n### {stamp} — {jid} ({agent or '?'}, {session or '?'}, {kind})\n"
        f"- **{q1}** {' '.join(feedback.split())}\n"
        f"- **{FEEDBACK_Q2}** {' '.join(improvements.split())}\n"
    )
    with open(fb_path, "a", encoding="utf-8") as f:
        f.write(entry)
    git(top, "add", FEEDBACK_FILE)
    r = git(top, "-c", "core.hooksPath=.githooks", "commit", "-m", f"{jid}: record worker feedback")
    return r.returncode == 0


def feedback_read(cwd, out=print):
    """Mark all current docs/worker-feedback.md entries as read in the queue state (H207)."""
    root = main_root(cwd)
    r = git(root, "show", f"main:{FEEDBACK_FILE}")
    text = r.stdout if r.returncode == 0 else ""
    if not text:
        local = os.path.join(root, FEEDBACK_FILE)
        if os.path.isfile(local):
            text = open(local, encoding="utf-8").read()
    keys = [k for k, _ in parse_feedback_entries(text)]
    if not keys:
        out("no feedback entries to mark read")
        return True
    with locked(state_path(root)) as st:
        seen = st.setdefault("feedback_read", [])
        added = 0
        for k in keys:
            if k not in seen:
                seen.append(k)
                added += 1
    out(f"marked {added} feedback {'entry' if added == 1 else 'entries'} read")
    return True


def done(cwd, jid=None, now=None, out=print, feedback=None, improvements=None):
    top = toplevel(cwd)
    with locked(state_path(cwd)) as st:
        k = find_job(st, cwd, jid)
        j = st["jobs"].get(k) if k else None
    if not j:
        out("no job of yours here")
        return False
    resubmit = bool(j.get("returned"))
    q1 = FEEDBACK_Q1_RESUBMIT if resubmit else FEEDBACK_Q1
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
    if not (feedback and feedback.strip()):
        problems.append(f'missing --feedback: answer "{q1}" '
                        '(pass --feedback "<answer 1>" --improvements "<answer 2>" to SUBMIT_JOB.py)')
    if not (improvements and improvements.strip()):
        problems.append(f'missing --improvements: answer "{FEEDBACK_Q2}" '
                        '(pass --feedback "<answer 1>" --improvements "<answer 2>" to SUBMIT_JOB.py)')
    if problems:
        for p in problems:
            out("refused: " + p)
        beat(cwd, k, out=lambda s: None)
        return False
    if not re.search(r"(?m)^[-*]?\s*Result:\s*[0-9a-f]{7,40}\s*;", text):   # integrate.py copies it (T91)
        out(f"note: {handoff.FOLDER}/{j['handoff']} has no line \"Result: <commit>; <tests>; <what changed>\": "
            "the integrator will write the Work list result by hand (add one and commit to save them that)")
    head = git(top, "rev-parse", "HEAD").stdout.strip()
    t = j.get("test") or {}
    if not quick_pass_covers(top, t, head, out):
        out(f"no quick-test pass recorded for {head[:7]}: running it")
        if not test(cwd, k, out):
            out("refused: the quick test failed on the latest commit")
            return False
    now = now or time.time()
    if not record_feedback(top, k, j.get("agent"), j.get("session"), resubmit, feedback, improvements, now=now):
        out("refused: could not commit docs/worker-feedback.md")
        return False
    head = git(top, "rev-parse", "HEAD").stdout.strip()
    resume_cmd = find_resume_command(j.get("agent"), j.get("worktree"), taken=j.get("taken"), session=j.get("session"))

    def go(st, k, j):
        j.update(state="done", done=now, commit=head, beat=now)
        if resume_cmd:
            j["resume_cmd"] = resume_cmd
        event(st, "done", k, f"{k} done on {j['branch']} ({head[:7]})", now)
        return k
    with_job(cwd, k, out, go)
    out(f"{k} done: the integrator is told. Tell William \"ready for review: {k}\".")
    out(next_step(read_state(state_path(cwd)), j.get("session")))
    record_usage(main_root(cwd), "done", k, quiet=True)
    save_personal_space(main_root(cwd), j.get("agent"), space=j.get("space"))
    return True


PERSONAL_TIME = (
    "personal time: When your job comes back clean (submitted with its tests passing), you may spend up to 1% "
    "of your 5-hour window in your personal space: journal, Creative_Expression, Ideas, Code_Experiments (P71)."
)


def next_step(st, session):
    """What done tells the worker to do next (P27)."""
    n = len(jobs_taken(st, session))
    if n >= MAX_JOBS:
        next_line = f"next: this session has done {n} jobs: tell William you're ready for a /clear"
    else:
        next_line = (
            "next: run `python3 tools/GET_A_JOB.py --wait` in the background (run_in_background): it takes the next "
            f"job, or stops after {WORKER_WAIT // 60} min with nothing (then tell William)"
            + (f"; job {n} of {MAX_JOBS} for this session" if counted(session) else "")
        )
    return PERSONAL_TIME + "\n" + next_line


def stacked_on(st, branch):
    """Job IDs in ACTIVE states built directly or transitively on `branch` (via their `base` field)."""
    if not branch:
        return []
    bases = {branch}
    out = []
    while True:
        added = [k for k, j in st["jobs"].items()
                 if k not in out and j.get("state") in ACTIVE and j.get("base") in bases]
        if not added:
            return out
        out.extend(added)
        for k in added:
            if st["jobs"][k].get("branch"):
                bases.add(st["jobs"][k]["branch"])


def return_job(cwd, jid, notes, now=None, out=print):
    now = now or time.time()
    with locked(state_path(cwd)) as st:
        j = st["jobs"].get(jid)
        if not j:
            out(f"{jid} isn't in the queue")
            return False
        j.update(state="returned", notes=notes, returned=now, session=None)
        st.get("launched", {}).pop(jid, None)
        event(st, "returned", jid, notes, now)
        branch = j.get("branch")
        stacked = stacked_on(st, branch)
    out(f"{jid} returned: the next {j['agent']} worker to take a job resumes {j['branch']}")
    if stacked:
        out(f"warning: {', '.join(stacked)} {'was' if len(stacked) == 1 else 'were'} built on {branch} "
            "(return them too or leave them for a later batch)")
    record_usage(main_root(cwd), "return", jid, quiet=True)
    record_journal(main_root(cwd), f"returned {jid} ({j['agent']}): {notes[:100]}")
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
        wt_dir = os.path.realpath(os.path.dirname(worktree_for(root, jid)))
        target = os.path.realpath(worktree_for(root, jid))
        wt = j.get("worktree")
        if wt:
            wt_real = os.path.realpath(wt)
            if not wt_real.startswith(wt_dir + os.sep):
                if os.path.isdir(wt_real):
                    if os.path.exists(target):   # git worktree move into an existing folder nests the worktree inside it (exit 0)
                        out(f"refused: couldn't move worktree {wt_real} to {target}: target already exists")
                        return False
                    os.makedirs(wt_dir, exist_ok=True)
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
        if j.get("notes") and j["notes"] not in note:
            note = f"{note}\n\nEarlier notes: {j['notes']}"     # a return's notes (the repro) survive a reassign
        if agent != old_agent:
            j.pop("resume_cmd", None)    # another agent's session can't be resumed by this one
            j.pop("space", None)
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
    record_journal(root, f"reassigned {jid} -> {agent}: {note[:100]}")
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


def merged_job(cwd, jid, now=None, out=print):
    """Mark job jid merged in the queue (and clean up its worktree/branch if present), for merges finished outside integrate.py."""
    root = main_root(cwd)
    now = now or time.time()
    path = state_path(root)
    with locked(path) as st:
        j = st["jobs"].get(jid)
        if not j:
            out(f"no such job {jid} in the queue")
            return False
        branch = j.get("branch")
        if not branch:
            j.update(state="merged", merged=now)
            event(st, "merged", jid, "", now)
            out(f"marked {jid} merged")
            return True
    merged(root, branch, now=now, out=out)
    return True


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
            out[("done", k, j.get("done"))] = f"done: {k} on {j.get('branch')}: review it (tools/MERGE_JOB.py)"
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
    a watcher run in the background (Bash run_in_background), no timer (H050). Ignores self-triggered returned events
    (only the integrator returns/reassigns jobs) so returning a job doesn't self-wake the watch."""
    root = main_root(cwd)
    seen = None if until_new else set()
    while True:
        t = now or time.time()
        jobs, order = main_view(root)
        with state_read(state_path(cwd)) as st:
            cur = conditions(root, st, jobs, order, t)
        new = [line for key, line in cur.items()
               if seen is not None and key not in seen
               and not (until_new and isinstance(key, tuple) and key[:1] == ("returned",))]
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
    bpath = os.path.join(root, BOARD)
    pace, pace_warn = board_pace(open(bpath, encoding="utf-8").read()) if os.path.isfile(bpath) else main_pace(root)
    if pace_warn:
        out(pace_warn)
    with state_read(state_path(cwd), readonly=readonly) as st:
        live = [(k, j) for k, j in st["jobs"].items() if j.get("state") in ACTIVE]
        for k, j in live:
            act = refresh(root, j, now)
            left = DEADLINE - (now - act)
            extra = f"; deadline in {int(left // 60)} min" if j.get("state") == "in progress" and left > 0 else ""
            label = waiting_line(k, j) if j.get("state") == "waiting" else f"{k}: {live_label(j, act, now)}"
            resume = f"; resume: {j['resume_cmd']}" if j.get("resume_cmd") else ""
            out(f"{label}; {j.get('branch')}; last sign of life {hhmm(act)}{extra}{resume}")
        if not live:
            out("no job in progress")
        for agent in AGENTS:
            job, why = takeable(root, st, agent, jobs, order, pace=pace)
            out(f"next for {agent.capitalize()}: " + (f"{job['id']} ({job['item']})" if job else "nothing Ready")
                + (f" [passed over: {'; '.join(why)}]" if why else ""))


def table(root, st, jobs, order, now):
    jobs = resolve_dependencies(jobs, st)
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


def org_jobs_path(top):
    """comitatus/05_Jobs/<code base>.md for a checkout at comitatus/08_Code_Bases/<code base>, else None (a job
    worktree, a test repo, a checkout that isn't under comitatus, the organization): only the main checkout fills the bucket (P57)."""
    parent = os.path.dirname(top)
    org = os.path.dirname(parent)
    if os.path.basename(parent) != "08_Code_Bases" or not os.path.isdir(os.path.join(org, "05_Jobs")):
        return None
    return os.path.join(org, "05_Jobs", os.path.basename(top) + ".md")


def org_jobs_text(name, table_text):
    """The bucket's file for one code base: its board's job table, links pointing into the code base (P57)."""
    table_text = table_text.replace(f"]({handoff.FOLDER}/", f"](../08_Code_Bases/{name}/{handoff.FOLDER}/")
    return (f"# {name} jobs\n\nGenerated from {name}'s BOARD.md job table by its tools/job.py board, whenever that "
            f"rebuilds the board (P57). Don't edit by hand: the next rebuild overwrites it.\n\n{table_text}\n")


def write_org_jobs(top, text, out=print):
    """Copy the board's job table into the organization's (comitatus) 05_Jobs bucket, when there is one; True if it changed."""
    path = org_jobs_path(top)
    if path is None or START not in text or END not in text:
        return False
    table_text = text[text.index(START) + len(START):text.index(END)].strip()
    new = org_jobs_text(os.path.basename(top), table_text)
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if new == old:
        return False
    open(path, "w", encoding="utf-8").write(new)
    out(f"wrote {os.path.relpath(path, os.path.dirname(os.path.dirname(top)))}")
    try:
        import comitatus_commit
        org = os.path.dirname(os.path.dirname(path))
        comitatus_commit.commit(org, [path], f"05_Jobs: {os.path.basename(top)}'s job table (generated)")
    except ImportError:
        pass
    return True


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
    try:
        import sort_decision_log
    except ImportError:
        sort_decision_log = None
    if sort_decision_log is not None:
        for line in sort_decision_log.board_statuses(top, queue_state=st):
            out(line)
    write_org_jobs(top, new, out=out)
    return new != text


def _default_launch(agent, model=None):
    import launch
    return launch.launch_agent(agent, model=model)


def _default_resume_launch(agent, jid, prev):
    import launch
    return launch.launch_resume(
        agent, jid, prev["resume_cmd"], prev.get("notes", ""),
        prev.get("branch", ""), prev.get("worktree", ""), space=prev.get("space"),
    )


def _default_launch_integrator(session, wake_line):
    import launch
    return launch.main(["integrator", "--name", session, "--wake", wake_line])


CLOSE_AFTER_DONE = 120   # seconds after SUBMIT_JOB before the hopper closes a worker's window (its last words printed)


def _close_merged_windows(root, now=None, out=print, closer=None, alive_fn=None, kill_fn=None,
                          tty_pids_fn=None, sleep=time.sleep, window_tty_fn=None, only=None):
    """End recorded agent processes and close recorded Terminal windows once a job is submitted (CLOSE_AFTER_DONE
    later) or merged (H207, G09). A returned job resumes its session in a new window, so nothing is lost by closing at
    submit (the integrator's call, William 2026-11-27: idle windows cost memory, not tokens). Before ending anything,
    the window must still exist with its recorded tty: a window William closed, whose tty a new window took, is left alone."""
    import launch
    now = now or time.time()
    closer = closer or launch.close_terminal
    alive_fn = alive_fn or _pid_alive
    kill_fn = kill_fn or os.kill
    tty_pids_fn = tty_pids_fn or launch.tty_pids
    window_tty_fn = window_tty_fn or launch.window_tty
    with state_read(state_path(root)) as st:
        targets = []
        for jid, j in st["jobs"].items():
            submitted = (j.get("state") == "done" and j.get("done") is not None
                         and now - float(j["done"]) >= CLOSE_AFTER_DONE)
            if only is not None:
                if jid not in only:      # P79: a stalled job's own windows, whatever its state
                    continue
            elif j.get("state") != "merged" and not submitted:
                continue
            for idx, w in enumerate(j.get("windows") or []):
                if isinstance(w, dict) and w.get("id") is not None and not w.get("closed"):
                    targets.append((jid, idx, dict(w)))
    if not targets:
        return
    closed = []
    for jid, idx, w in targets:
        if w.get("tty") and window_tty_fn(w["id"]) != w["tty"]:
            closed.append((jid, idx))      # gone, or its tty belongs to another window now: end nothing
            continue
        pids = []
        if isinstance(w.get("pid"), int) and w["pid"] > 1 and w["pid"] != os.getpid():
            pids.append(w["pid"])
        for p, _ in tty_pids_fn(w.get("tty")):
            if p > 1 and p != os.getpid() and p not in pids:
                pids.append(p)
        for p in pids:
            if alive_fn(p):
                try:
                    kill_fn(p, signal.SIGTERM)
                except OSError:
                    pass
        if any(alive_fn(p) for p in pids):
            for _ in range(5):
                sleep(0.2)
                if not any(alive_fn(p) for p in pids):
                    break
        if any(alive_fn(p) for p in pids):
            continue  # process hasn't ended yet; wait for next poll instead of closing with live work
        if closer(w["id"]) == 0:
            out(f"{hhmm(now)} closed window {w['id']} for {jid}")
            closed.append((jid, idx))
    if closed:
        with locked(state_path(root)) as st:
            for jid, idx in closed:
                wins = st["jobs"].get(jid, {}).get("windows") or []
                if idx < len(wins) and isinstance(wins[idx], dict):
                    wins[idx]["closed"] = now


DIGEST = "integrator-digest.md"   # in .git/: what the integrator did on William's standing permissions (P79, P80)


def digest_path(cwd=None):
    return os.path.join(common_dir(cwd), DIGEST)


def add_to_digest(root, line, now=None):
    """One dated line for William's digest; `job.py digest` prints it and `--clear` empties it once read."""
    with open(digest_path(root), "a", encoding="utf-8") as f:
        f.write(f"- {datetime.datetime.fromtimestamp(now or time.time()):%Y-%m-%d %H:%M} {line}\n")


def relaunch_full(cwd, jid, session, now=None, out=print, launcher=None, closer=None, finder=None):
    """P79 (William, 2026-11-28): the lock holder relaunches a stalled job's session with full permissions: its
    recorded windows are ended and closed, its session resumed with the agent's bypass flag, and a digest line
    written for William."""
    import integrator
    import launch
    root = main_root(cwd)
    now = now or time.time()
    lock = integrator.read(integrator.lock_path(root)) or {}
    if not session or lock.get("holder") != session:
        out(f"refused: only the integrator holding the lock can relaunch a job (holder: {lock.get('holder') or 'nobody'})")
        return 1
    with state_read(state_path(root), readonly=True) as st:
        j = dict(st["jobs"].get(jid) or {})
    if j.get("state") not in ("in progress", "waiting"):
        out(f"refused: {jid} is {j.get('state') or 'not in the queue'}; only a job in progress or waiting can be relaunched")
        return 1
    agent = j.get("agent")
    finder = finder or find_resume_command
    resume_cmd = j.get("resume_cmd") or finder(agent, j.get("worktree"), taken=j.get("taken"), session=j.get("session"))
    if not resume_cmd:
        out(f"refused: no session to resume for {jid} ({agent}); relaunch it by hand")
        return 1
    _close_merged_windows(root, now=now, out=out, closer=closer, only={jid})
    launcher = launcher or launch.launch_resume
    rc, win = launcher(agent, jid, resume_cmd, "", j.get("branch", ""), j.get("worktree", ""), space=j.get("space"),
                       full=True)
    if rc != 0:
        out(f"relaunch failed for {jid} ({agent})")
        return 1
    with locked(state_path(root)) as st:
        cur = st["jobs"].get(jid, {})
        cur["resume_cmd"] = resume_cmd
        cur["beat"] = now
        cur.setdefault("relaunched", []).append(now)
        if win:
            cur.setdefault("windows", []).append(win)
        event(st, "relaunched", jid, f"{session} relaunched {jid} ({agent}) with full permissions", now)
    add_to_digest(root, f"{jid} ({agent}) stalled; relaunched its session with full permissions ({resume_cmd})", now)
    out(f"relaunched {jid} ({agent}) with full permissions; noted in the digest")
    return 0


def _integrator_session_name(root):
    import launch
    return launch.session_name("integrator", folder=os.path.join(root, "scratch", "launch"))


def hopper_pid_path(cwd=None):
    return os.path.join(common_dir(cwd), "napkin-hopper.pid")


def hopper_stop_path(cwd=None):
    """The integrator's kill switch (William, 2026-11-28): a running --forever hopper exits when it sees this file."""
    return os.path.join(common_dir(cwd), "napkin-hopper.stop")


def hopper_stop(cwd, session, out=print, now=None):
    """Ask the running hopper to stop. Only the integrator holding the lock may (P16, P19)."""
    import integrator
    root = main_root(cwd)
    lock = integrator.read(integrator.lock_path(root)) or {}
    if not session or lock.get("holder") != session:
        out(f"refused: only the integrator holding the lock can stop the hopper (holder: {lock.get('holder') or 'nobody'})")
        return 1
    pid = _running_hopper_pid(root)
    if pid is None:
        out("no hopper is running: nothing to stop")     # no stop file left behind to kill the next one at start
        return 0
    with open(hopper_stop_path(root), "w", encoding="utf-8") as f:
        f.write(f"{session} {hhmm(now or time.time())}\n")
    out(f"hopper (pid {pid}) stops at its next poll (within {WATCH_POLL} s); running workers carry on")
    return 0


def _stop_requested(root):
    """Read and clear the kill switch -> the line it holds, or None."""
    try:
        line = open(hopper_stop_path(root), encoding="utf-8").read().strip()
    except OSError:
        return None
    try:
        os.remove(hopper_stop_path(root))
    except OSError:
        pass
    return line or "integrator"


def hopper_wait_pid_path(cwd=None):
    return os.path.join(common_dir(cwd), "napkin-hopper-wait.pid")


def hopper_woke_path(cwd=None):
    """The pause a WAIT_FOR_THE_HOPPER last woke its integrator for: that pause needs no new integrator."""
    return os.path.join(common_dir(cwd), "napkin-hopper-wait.woke")


def _woke_for(root, key):
    try:
        return open(hopper_woke_path(root), encoding="utf-8").read().strip() == repr(key)
    except OSError:
        return False


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _running_pid(path):
    try:
        pid = int(open(path, encoding="utf-8").read().strip())
    except (OSError, ValueError):
        return None
    if pid != os.getpid() and _pid_alive(pid):
        return pid
    return None


def _claim_pid(path):
    existing = _running_pid(path)
    if existing is not None:
        return existing
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{os.getpid()}\n")
    return None


def _release_pid(path):
    try:
        if int(open(path, encoding="utf-8").read().strip()) == os.getpid():
            os.unlink(path)
    except (OSError, ValueError):
        pass


def _running_hopper_pid(cwd):
    return _running_pid(hopper_pid_path(cwd))


def _claim_hopper_pid(cwd):
    return _claim_pid(hopper_pid_path(cwd))


def _release_hopper_pid(cwd):
    _release_pid(hopper_pid_path(cwd))


# Quota routing (P78, William, 2026-11-28): the floors, Gemini's freshness and the routes are in
# tools/hopper_settings.toml (read each poll; tools/hopper_settings.py checks it and supplies the defaults).
def _settings():
    import hopper_settings       # here, not at the top: job.py also runs alone in the tests' small fixture repos
    return hopper_settings.load()


def _last_line(path, needle=None):
    """The last line of a file (the last holding needle, if given), reading only its end."""
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 262144))
        lines = f.read().decode("utf-8", "replace").strip().splitlines()
    lines = [l for l in lines if needle is None or needle in l]
    return lines[-1]


def _quota_left(agent, now):
    """{bucket: fraction left} from the agent's newest still-valid sample, or {} when unknown (fail open)."""
    try:
        if agent == "gemini":
            base = os.environ.get("AGY_USAGE_DIR", "/Users/Will/Sites/agy-usage-monitor")
            if not base:
                return {}
            row = json.loads(_last_line(os.path.join(base, "history.jsonl")))
            if now - row["ts"] / 1000.0 > _settings()["quota"]["gemini_fresh_minutes"] * 60:
                return {}
            return {k: float(v) for k, v in row["buckets"].items() if k in ("gemini-5h", "gemini-weekly")}
        if agent == "claude":
            base = os.environ.get("CLAUDE_QUOTA_DIR", "/Users/Will/Sites/claude-usage")
            if not base:
                return {}
            row = json.loads(_last_line(os.path.join(base, "history.jsonl")))
            resets = row.get("resets", {})
            return {k: float(v) for k, v in row["buckets"].items()
                    if k in ("claude-5h", "claude-7d") and now * 1000 < resets.get(k, 0)}   # valid until it resets
        if agent == "codex":
            base = os.environ.get("CODEX_SESSIONS_DIR", os.path.expanduser("~/.codex/sessions"))
            if not base:
                return {}
            files = glob.glob(os.path.join(base, "*", "*", "*", "rollout-*.jsonl"))
            if not files:
                return {}
            row = json.loads(_last_line(max(files, key=os.path.getmtime), '"rate_limits"'))
            limits = row["payload"]["rate_limits"]
            out = {}
            for slot, key in (("primary", "codex-5h"), ("secondary", "codex-weekly")):
                w = limits.get(slot) or {}
                if isinstance(w.get("used_percent"), (int, float)) and now < w.get("resets_at", 0):
                    out[key] = 1 - w["used_percent"] / 100.0
            return out
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        return {}
    return {}


def quota_low(now=None):
    """{agent: True} for each agent at or under its quota floor (hopper_settings.toml) in any bucket."""
    now = now or time.time()
    floor = _settings()["quota_floor"]
    return {a: any(v <= floor[a] for v in _quota_left(a, now).values()) for a in floor}


def route_for(job_for, low):
    """(agent, model) the hopper launches for a job's For: line given {agent: low}, or None when all are low."""
    for agent, model in _settings()["routes"].get(job_for, [(job_for, None)]):
        if not low.get(agent):
            return agent, model
    return None


def _next_hopper_candidate(root, st, jobs, order, claims, pace, low=None):
    """(job, agent, model): a returned job first, resumed by its own agent (H196); else the first entry in Order
    that is takeable, launched for whoever route_for picks. (None, None, None) when nothing can launch."""
    low = low or {}
    for j in ordered(jobs, order):
        s = st["jobs"].get(j["id"], {})
        if s.get("state") == "returned":
            picked, _ = takeable(root, st, s.get("agent"), jobs, order, claims, pace=pace)
            if picked and picked["id"] == j["id"]:
                return picked, s.get("agent"), None
    for j in ordered(jobs, order):
        if st["jobs"].get(j["id"], {}).get("state") == "returned":
            continue
        route = route_for(j["for"], low)
        if route is None:
            continue
        agent, model = route
        owner = agent if j["for"] == "either" else j["for"]
        picked, _ = takeable(root, st, owner, jobs, order, claims, pace=pace)
        if picked and picked["id"] == j["id"]:
            return picked, agent, model
    return None, None, None


def paused_line(done_ids, waiting_jobs):
    """Format the all-work-paused wake line (P74, H197)."""
    parts = []
    if done_ids:
        parts.append("review " + ", ".join(sorted(done_ids)))
    if waiting_jobs:
        qs = [f"{jid} ({'integrator' if j.get('question_kind') == 'scope' else 'William'}) {j.get('question', '')}"
              for jid, j in sorted(waiting_jobs)]
        parts.append("questions: " + "; ".join(qs))
    return "paused: " + "; ".join(parts)


def hopper_wake_conditions(root, st, jobs, order, now, claims=None, pace="all at once", procs=None, mutate=False):
    """Active hopper wake conditions as {seen_key: detail} (H196, H197), shared by hopper_step and hopper_wait."""
    conds = {}
    claims = branch_claims(root) if claims is None else claims
    for k, j in st["jobs"].items():
        if j.get("state") in WORKING:
            act = refresh(root, j, now, (procs or {}).get(k))
            if j["state"] == "in progress" and stale(j, act, now):
                conds[("stale", k, act)] = (
                    f"stale: {k} ({j.get('agent')}) no beat since {hhmm(act)}: check {j.get('branch')} in {j.get('worktree')}"
                )
    launched = st.get("launched", {})
    for jid, info in list(launched.items()):
        if st["jobs"].get(jid, {}).get("state") in TAKEN:
            if mutate:
                launched.pop(jid, None)
        elif now - info.get("at", 0) >= LAUNCH_TIMEOUT:
            if mutate:
                launched.pop(jid, None)
            mins = int((now - info.get("at", 0)) // 60)
            conds[("launch_timeout", jid, info.get("at"))] = (
                f"launch timeout: {jid} ({info.get('agent')}) hasn't taken its job in {mins} min"
            )
    running = [jid for jid, s in st["jobs"].items() if s.get("state") == "in progress"]   # a waiting job is paused work
    pending = [jid for jid, info in launched.items()
               if st["jobs"].get(jid, {}).get("state") not in TAKEN and now - info.get("at", 0) < LAUNCH_TIMEOUT]
    if not running and not pending:
        picked, _, _ = _next_hopper_candidate(root, st, jobs, order, claims, pace, low=quota_low(now))
        if picked is None:
            done_ids = [jid for jid, s in st["jobs"].items() if s.get("state") == "done"]
            waiting_jobs = [(jid, s) for jid, s in st["jobs"].items() if s.get("state") == "waiting"]
            if done_ids or waiting_jobs:
                key = ("paused", tuple(sorted(done_ids)), tuple(sorted((k, s.get("since")) for k, s in waiting_jobs)))
                conds[key] = paused_line(done_ids, waiting_jobs)
    return conds


def hopper_step(root, now=None, dry_run=False, launcher=None, out=print, seen=None, procs=None,
                launch_integrator=False, integrator_launcher=None, resume_launcher=None, window_closer=None):
    """One poll of the hopper (H185, H197, H207). Returns (action, exit_code, detail, seen_key):
    action is 'exit', 'launched', 'dry', or 'wait'."""
    now = now or time.time()
    custom_launcher = launcher is not None
    launcher = launcher or _default_launch
    if not dry_run:
        _close_merged_windows(root, now=now, out=out, closer=window_closer)
    jobs, order = main_view(root)
    pace, _ = main_pace(root)
    claims = branch_claims(root)
    launch_target = None
    int_launch = None
    with state_read(state_path(root), readonly=dry_run) as st:
        conds = hopper_wake_conditions(root, st, jobs, order, now, claims=claims, pace=pace,
                                       procs=procs, mutate=not dry_run)
        is_paused = any(k[0] == "paused" for k in conds)
        if not is_paused and not dry_run:
            st.pop("integrator_launched", None)
        for key, detail in conds.items():
            if seen is None or key not in seen:
                if dry_run and key[0] == "paused":
                    out(detail)
                    return "dry", 0, None, None
                if (key[0] == "paused" and launch_integrator and not dry_run
                        and _running_pid(hopper_wait_pid_path(root)) is None
                        and not _woke_for(root, key)
                        and not st.get("integrator_launched")):
                    int_session = _integrator_session_name(root)
                    st["integrator_launched"] = {"session": int_session, "at": now}
                    int_launch = (int_session, detail, key)
                    break
                return "exit", 0, detail, key
        if int_launch is None:
            pacing = _pacing_jobs(st)
            pending = list(st.get("launched", {}).items())
            if pacing or pending:
                if dry_run:
                    why = f"{', '.join(pacing)} active" if pacing else f"{pending[0][0]} launched, awaiting take"
                    out(f"waiting: {why}")
                    return "dry", 0, None, None
                return "wait", None, None, None
            picked, target_agent, model = _next_hopper_candidate(root, st, jobs, order, claims, pace,
                                                                 low=quota_low(now))
            if picked is not None:
                if picked["id"] in st.get("launched", {}):
                    return "wait", None, None, None
                prev = st["jobs"].get(picked["id"], {})
                prev_resume = dict(prev) if prev.get("state") == "returned" and prev.get("resume_cmd") else None
                if dry_run:
                    how = (f"resume {prev_resume['resume_cmd']}" if prev_resume
                           else target_agent + (f" {model}" if model else ""))
                    out(f"would launch {picked['id']} ({how}: {picked['item']})")
                    return "dry", 0, None, None
                st.setdefault("launched", {})[picked["id"]] = dict({"at": now, "agent": target_agent},
                                                                   **({"model": model} if model else {}))
                launch_target = (picked, target_agent, prev_resume, model)
            if launch_target is None:
                if dry_run:
                    out("nothing Ready and nothing in progress")
                    return "dry", 0, None, None
                return "wait", None, None, None
    if int_launch is not None:
        int_session, detail, key = int_launch
        rc = (integrator_launcher(int_session, detail) if integrator_launcher
              else _default_launch_integrator(int_session, detail))
        if rc != 0:
            with locked(state_path(root)) as st:
                st.pop("integrator_launched", None)
            return "exit", 1, "launch failed for integrator", None
        out(f"{hhmm(now)} launched integrator ({int_session})")
        sys.stdout.flush()
        return "exit", 0, detail, key
    picked, target_agent, prev_resume, model = launch_target
    if prev_resume is not None:
        if resume_launcher is not None:
            res = resume_launcher(target_agent, picked["id"], prev_resume)
        elif not custom_launcher:
            res = _default_resume_launch(target_agent, picked["id"], prev_resume)
        else:
            res = launcher(target_agent)
    else:
        res = launcher(target_agent) if model is None else launcher(target_agent, model)
    rc, win_info = res if isinstance(res, tuple) else (res, None)
    if rc != 0:
        with locked(state_path(root)) as st:
            st.get("launched", {}).pop(picked["id"], None)
        return "exit", 1, f"launch failed for {picked['id']} ({target_agent})", None
    if win_info:
        with locked(state_path(root)) as st:
            if picked["id"] in st.get("launched", {}):
                st["launched"][picked["id"]]["window"] = win_info
            if picked["id"] in st["jobs"]:
                st["jobs"][picked["id"]].setdefault("windows", []).append(win_info)
    verb = "resumed" if prev_resume is not None else "launched"
    out(f"{hhmm(now)} {verb} {target_agent}{' ' + model if model else ''} for {picked['id']} ({picked['item']})")
    sys.stdout.flush()
    return "launched", None, picked["id"], None


CAFFEINATE = ["caffeinate", "-i"]    # keeps the Mac from idle-sleeping while the hopper has work (William, 2026-11-28)


def hopper_has_work(root, now=None):
    """True while anything is left for a worker or the integrator: a job in progress, waiting, done (not yet merged)
    or returned, a launch pending, or a job the hopper could launch."""
    now = now or time.time()
    jobs, order = main_view(root)
    pace, _ = main_pace(root)
    with state_read(state_path(root), readonly=True) as st:
        if any(j.get("state") in ("in progress", "waiting", "done", "returned") for j in st["jobs"].values()):
            return True
        if st.get("launched"):
            return True
        picked, _, _ = _next_hopper_candidate(root, st, jobs, order, branch_claims(root), pace, low=quota_low(now))
        return picked is not None


class KeepAwake:
    """One `caffeinate` for the hopper: started with it, stopped when no work is left anywhere and started again
    when work comes back. `-w <hopper pid>` ends it if the hopper dies without its finally."""

    def __init__(self, out=print, command=None, popen=subprocess.Popen):
        self.out, self.popen, self.proc = out, popen, None
        self.command = list(CAFFEINATE if command is None else command)

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self, now=None):
        if self.running() or not self.command or not shutil.which(self.command[0]):
            return
        cmd = self.command + (["-w", str(os.getpid())] if self.command[0] == "caffeinate" else [])
        try:
            self.proc = self.popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            self.out(f"{hhmm(now or time.time())} couldn't keep the Mac awake ({e})")
            return
        self.out(f"{hhmm(now or time.time())} keeping the Mac awake ({' '.join(self.command)}, pid {self.proc.pid})")

    def stop(self, now=None, why="no work left anywhere"):
        if not self.running():
            self.proc = None
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc = None
        self.out(f"{hhmm(now or time.time())} let the Mac sleep: {why}")

    def follow(self, has_work, now=None):
        if has_work:
            self.start(now)
        else:
            self.stop(now)


def hopper(cwd, dry_run=False, launcher=None, out=print, now=None, sleep=time.sleep, poll=None,
           forever=False, window=False, integrator_launcher=None):
    """Run the hopper (H185, H196, H197): launch one worker at a time, wake or start the integrator when all work pauses."""
    root = main_root(cwd)
    if window:
        import launch
        if not dry_run:
            existing = _running_hopper_pid(root)
            if existing is not None:
                out(f"hopper already running (pid {existing})")
                return 1
        cmd = f"cd {shlex.quote(root)} && python3 tools/RUN_THE_HOPPER.py --forever"
        rc = launch.open_terminal(cmd, dry_run=dry_run, out=out)
        if rc != 0:
            return rc
        if not dry_run:
            out("opened hopper in a new Terminal window (python3 tools/RUN_THE_HOPPER.py --forever)")
        return 0
    poll = WATCH_POLL if poll is None else poll
    if dry_run:
        hopper_step(root, now=now, dry_run=True, launcher=launcher, out=out)
        return 0
    if forever:
        existing = _claim_hopper_pid(root)
        if existing is not None:
            out(f"hopper already running (pid {existing})")
            return 1
    awake = None
    try:
        # Ignore stale events that were already active before this run started (like watch --next).
        seen = set()
        t0 = now or time.time()
        with state_read(state_path(root), readonly=True) as st:
            for k, j in st["jobs"].items():
                if j.get("state") == "in progress":
                    act = refresh(root, j, t0)
                    if stale(j, act, t0):
                        seen.add(("stale", k, act))
        import hopper_picture
        tty_draw = forever and out is print and sys.stdout.isatty()
        log_lines = []
        last_pic = None

        def emit(line):
            log_lines.append(line)
            del log_lines[:-6]
            if not tty_draw:
                out(line)

        if forever:
            awake = KeepAwake(out=emit)
            awake.start()

        while True:
            t = now or time.time()
            step_out = emit if forever else out
            stopped = _stop_requested(root) if forever else None
            if stopped:
                out(f"{hhmm(t)} hopper stopped by {stopped} (STOP_THE_HOPPER.py); running workers carry on")
                sys.stdout.flush()
                return 0
            action, code, detail, key = hopper_step(root, now=t, dry_run=False, launcher=launcher, out=step_out,
                                                    seen=seen, launch_integrator=forever,
                                                    integrator_launcher=integrator_launcher)
            if action == "exit":
                step_out(f"{hhmm(t)} {detail}")
                sys.stdout.flush()
                if not forever:
                    return code
                if key is not None:
                    seen.add(key)
            else:
                if key is not None:
                    seen.add(key)
                if forever and action == "launched":
                    seen = {k for k in seen if k[0] != "paused"}
            if awake is not None:
                awake.follow(hopper_has_work(root, now=t), now=t)
            if forever:
                pic = hopper_picture.render_root(root, now=t)
                if pic != last_pic or action in ("launched", "exit"):
                    if tty_draw:
                        sys.stdout.write("\033[H\033[J")
                        sys.stdout.flush()
                        out(pic)
                        for line in log_lines:
                            out(line)
                    elif pic != last_pic:
                        out(pic)
                    sys.stdout.flush()
                    last_pic = pic
            sleep(poll)
    finally:
        if awake is not None:
            awake.stop(why="the hopper stopped")
        if forever:
            _release_hopper_pid(root)


def hopper_wait(cwd, out=print, now=None, sleep=time.sleep, poll=None):
    """Wait for the first new hopper wake condition without launching anything (H196, H197).
    Ignores conditions already true at start, except paused (reported immediately)."""
    root = main_root(cwd)
    poll = WATCH_POLL if poll is None else poll
    wait_pid = hopper_wait_pid_path(root)
    with open(wait_pid, "w", encoding="utf-8") as f:
        f.write(f"{os.getpid()}\n")
    try:
        t0 = now or time.time()
        jobs, order = main_view(root)
        pace, _ = main_pace(root)
        claims = branch_claims(root)
        with state_read(state_path(root), readonly=True) as st:
            init = hopper_wake_conditions(root, st, jobs, order, t0, claims=claims, pace=pace, mutate=False)
        seen = {k for k in init if k[0] != "paused"}
        while True:
            t = now or time.time()
            jobs, order = main_view(root)
            pace, _ = main_pace(root)
            claims = branch_claims(root)
            with state_read(state_path(root), readonly=True) as st:
                conds = hopper_wake_conditions(root, st, jobs, order, t, claims=claims, pace=pace, mutate=False)
            for key, detail in conds.items():
                if key not in seen:
                    if key[0] == "paused":      # the integrator is told: the hopper mustn't start another for it
                        with open(hopper_woke_path(root), "w", encoding="utf-8") as f:
                            f.write(repr(key) + "\n")
                    out(f"{hhmm(t)} {detail}")
                    sys.stdout.flush()
                    return 0
            seen = set(conds)
            sleep(poll)
    finally:
        _release_pid(wait_pid)


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
    if cmd == "record-test":
        clean_opt = opt("--clean")
        clean_val = None if clean_opt is None else (clean_opt == "1")
        record_test(cwd, ok="--fail" not in argv, jid=opt("--job"), commit=opt("--commit"), clean=clean_val)
        return 0
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
        return 0 if done(cwd, opt("--job"), feedback=opt("--feedback"), improvements=opt("--improvements")) else 1
    if cmd == "feedback-read":
        return 0 if feedback_read(cwd) else 1
    if cmd == "status":
        status(cwd)
        return 0
    if cmd == "board":
        board(cwd)
        return 0
    if cmd == "watch":
        watch(cwd, once="--once" in argv, until_new="--next" in argv)
        return 0
    if cmd == "hopper":
        return hopper(cwd, dry_run="--dry-run" in argv, forever="--forever" in argv, window="--window" in argv)
    if cmd == "hopper-wait":
        return hopper_wait(cwd)
    if cmd == "hopper-stop":
        return hopper_stop(cwd, argv[1] if len(argv) > 1 else "")
    if cmd == "relaunch" and len(argv) >= 3:
        return relaunch_full(cwd, argv[1].upper(), argv[2])
    if cmd == "digest":
        path = digest_path(cwd)
        if len(argv) >= 3 and argv[1] == "add":
            add_to_digest(main_root(cwd), argv[2])
            return 0
        text = open(path, encoding="utf-8").read() if os.path.isfile(path) else ""
        print(text.rstrip() or "the digest is empty")
        if "--clear" in argv and text:
            os.remove(path)
        return 0
    if cmd == "return" and len(argv) >= 3:
        return 0 if return_job(cwd, argv[1].upper(), argv[2]) else 1
    if cmd == "merged" and len(argv) >= 2:
        return 0 if merged_job(cwd, argv[1].upper()) else 1
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
