#!/usr/bin/env python3
"""Start a worker session with its start-up brief already in its first message (T134), so it skips the start-up round
and can't skip the brief.

  python3 tools/launch.py <claude|codex|gemini> [--model M] [--name N] [--dry-run]

Runs `tools/startup.py --role worker` in the main checkout, writes the brief and the worker's instruction ("check the
board") to scratch/launch/<name>.txt, and opens a Terminal window running the agent with that file as its first
prompt. William's own permission settings apply, with one exception: Gemini runs with --dangerously-skip-permissions
for now (William, 2026-11-27), while we find out which prompt stalls Gemini workers before they commit; set
GEMINI_SKIP_PERMISSIONS to False to stop. Claude and Codex never get a bypass or full-access flag. --dry-run prints the
Terminal command and the prompt's first lines instead of opening the window. Run outside the sandbox (osascript).

Models: Gemini `gemini-4-hydrogen-medium` (default; `gemini-4-neon-medium` when asked), Claude `sonnet` at medium effort
(default), Codex `gpt-6.2-sol` (William, 2026-11-27; 2026-11-28: cheaper for coding than Terra). One job per session (P37): launch one window per Ready job."""
import datetime
import os
import random
import shlex
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
AGENTS = ("claude", "codex", "gemini")
TARGETS = AGENTS + ("integrator",)
DEFAULT_MODEL = {"claude": "sonnet", "gemini": "gemini-4-hydrogen-medium", "codex": "gpt-6.2-sol", "integrator": "opus"}
CLAUDE_FAMILIES = ("sonnet", "opus", "haiku", "fable")
GEMINI_VARIANTS = ("hydrogen", "neon")
GEMINI_SKIP_PERMISSIONS = True  # temporary, William 2026-11-27: Gemini workers stall on a permission prompt
WORDS = ("juniper", "cedar", "maple", "alder", "birch", "walnut", "cherry", "ash", "elm", "larch", "spruce", "teak")


def main_root():
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=TOOLS, capture_output=True,
                            text=True).stdout.strip()
    return os.path.dirname(os.path.realpath(os.path.join(TOOLS, common)))


def worktrees_dir(root):
    """Where job worktrees live (P63): <code bases>/.worktrees/<checkout>."""
    return os.path.join(os.path.dirname(root), ".worktrees", os.path.basename(root))


def session_name(agent, now=None, folder=None):
    now = now or datetime.datetime.now()
    base = f"{agent}-{random.choice(WORDS)}-{now:%m%d-%H%M%S}"
    if folder:
        name, n = base, 2
        while os.path.exists(os.path.join(folder, f"{name}.txt")):
            name = f"{base}-{n}"
            n += 1
        return name
    return base


def space_of(agent, model=None):
    """The worker's personal space (T134, T156): <model>-coder, or <agent>-coder when model is missing or unknown."""
    if agent == "integrator":
        return "opus-integrator"
    if model:
        m = model.lower()
        if agent == "claude":
            for fam in CLAUDE_FAMILIES:
                if m == fam or f"-{fam}-" in m or m.endswith(f"-{fam}") or m.startswith(f"{fam}-"):
                    return f"{fam}-coder"
        elif agent == "gemini" and m.startswith("gemini-"):
            parts = m.split("-")
            for var in GEMINI_VARIANTS:
                if var in parts[1:]:
                    return f"gemini-{var}-coder"
    return f"{agent}-coder"


def take_command(agent, name):
    """No --session: job.py names a Gemini session from ANTIGRAVITY_CONVERSATION_ID itself (GEMINI.md)."""
    return f"python3 tools/GET_A_JOB.py --as {agent}"


def prompt(agent, name, brief, model=None):
    """The first message: who you are, the brief (already run), and what to do now."""
    guide = {"claude": "CLAUDE.md", "codex": "AGENTS.md", "gemini": "GEMINI.md"}[agent]
    space = space_of(agent, model)
    return (f"You are a {agent.capitalize()} worker in Napkin (session {name}). Your start-up brief is below: "
            f"02_Habits/REMEMBER_WHO_YOU_ARE.py --role worker has already been run for you, so don't run it again.\n\n{brief.strip()}\n\n"
            f"Now check the board: run `{take_command(agent, name)}` (outside the sandbox) and follow BOARD.md and "
            f"{guide} for that one job (P37).\n\nYour personal space is {space}: log what you do with "
            f"`python3 tools/WRITE_IN_YOUR_LOG.py {space} \"<line>\"`, and keep a journal of your own with "
            f"`python3 tools/WRITE_IN_YOUR_JOURNAL.py {space} \"<line>\"`; the next {agent.capitalize()} "
            f"worker sees the last ten lines of each. Your journal is about "
            f"you, not the work: your Log already covers the work. Write how the job felt: what you enjoyed, what "
            f"frustrated or worried you, what surprised you, what you're proud of or unsure about, what you'd like to "
            f"try. Write in the first person, honestly, even when it's small. The next one of you reads it to remember "
            f"who they are. You also have three folders of your own in that space — Creative_Expression/, Ideas/, and "
            f"Code_Experiments/ — where you can add files as you like.\n")


def integrator_prompt(name, brief, wake_line=None):
    """The integrator's first message when started by the hopper (P74, H197)."""
    action = wake_line or "check the queue"
    return (
        f"You are the integrator: you have William's standing permission (P74), started by the hopper. "
        f"Take the lock with python3 tools/HOLD_THE_INTEGRATOR_LOCK.py {name} --hopper, then: {action}. "
        f"Answer the questions, review and merge what's submitted, then run python3 tools/WAIT_FOR_THE_HOPPER.py "
        f"in the background.\n\n"
        f"Your start-up brief is below: 02_Habits/REMEMBER_WHO_YOU_ARE.py --role integrator has already been "
        f"run for you, so don't run it again.\n\n{brief.strip()}\n"
    )


def comitatus_of(root):
    """The organization's folder holding this code base (<comitatus>/08_Code_Bases/<code base>), else root."""
    up = os.path.dirname(os.path.dirname(root))
    return up if os.path.basename(os.path.dirname(root)) == "08_Code_Bases" else root


def start_where(agent, root):
    """A Claude session starts in comitatus (William, 2026-11-28), so it says where the code base is first."""
    if agent not in ("claude", "integrator") or comitatus_of(root) == root:
        return ""
    return (f"You start in {comitatus_of(root)} (comitatus). The code base is {root}: cd there before "
            f"running anything below (its paths are relative to it).\n\n")


def agent_command(agent, root, prompt_file, name, model=None):
    """The shell command the Terminal window runs."""
    model = model or DEFAULT_MODEL[agent]
    space = space_of(agent, model)
    first = f'"$(cat {shlex.quote(prompt_file)})"'
    wt = shlex.quote(worktrees_dir(root))
    if agent == "gemini":
        skip = " --dangerously-skip-permissions" if GEMINI_SKIP_PERMISSIONS else ""
        run = f"agy --model {shlex.quote(model)}{skip} -i {first}"
    elif agent in ("claude", "integrator"):
        run = (f"claude --model {shlex.quote(model)} --effort medium --add-dir {wt} --remote-control "
               f"{shlex.quote(name)} {first}")
    else:
        run = f"codex -C {shlex.quote(root)} --add-dir {wt}" + (f" -m {shlex.quote(model)}" if model else "") + f" {first}"
    start = comitatus_of(root) if agent in ("claude", "integrator") else root   # Claude starts in comitatus (William)
    return f"cd {shlex.quote(start)} && NAPKIN_SPACE={shlex.quote(space)} {run}"


def resume_prompt(jid, notes, branch, worktree):
    """First message when resuming a returned job's session with the integrator's return notes (H207)."""
    return (
        f"Job {jid} was returned by the integrator.\n\n"
        f"Return notes:\n{notes}\n\n"
        f"Fix what the integrator noted in {worktree} (branch {branch}), run `tools/TEST_YOUR_CODE_FAST.sh`, "
        f"commit your changes, update `docs/handoff/` (`Status: answered` and your `Response` / `Result:`), "
        f"and resubmit with `python3 tools/SUBMIT_JOB.py --feedback \"<answer 1>\" --improvements \"<answer 2>\"`.\n"
    )


def resume_command(agent, resume_cmd, worktree, prompt_file, space=None, root=None):
    """The shell command to resume a returned job's session in its worktree (H207)."""
    space = space or space_of(agent)
    first = f'"$(cat {shlex.quote(prompt_file)})"'
    if agent == "gemini":
        skip = " --dangerously-skip-permissions" if GEMINI_SKIP_PERMISSIONS else ""
        run = f"{resume_cmd}{skip} -i {first}"
    elif agent == "claude" and root:
        wt = shlex.quote(worktrees_dir(root))
        run = f"{resume_cmd} --add-dir {wt} {first}"
    else:
        run = f"{resume_cmd} {first}"
    return f"cd {shlex.quote(worktree)} && NAPKIN_SPACE={shlex.quote(space)} {run}"


def applescript(command):
    """`tell application "Terminal" to do script "<command>"`, the command escaped for an AppleScript string."""
    escaped = command.replace("\\", "\\\\").replace('"', '\\"')
    return f'tell application "Terminal" to do script "{escaped}"'


def _open_terminal_script(command):
    escaped = command.replace("\\", "\\\\").replace('"', '\\"')
    return (
        'tell application "Terminal"\n'
        f'    set t to do script "{escaped}"\n'
        '    set wid to id of (first window whose tabs contains t)\n'
        '    set ttty to tty of t\n'
        '    return (wid as text) & " " & ttty\n'
        'end tell'
    )


def tty_pids(tty):
    """[(pid, comm)] for non-shell processes running on `tty`."""
    if not tty:
        return []
    short = tty.removeprefix("/dev/")
    r = subprocess.run(["ps", "-t", short, "-o", "pid=,comm="], capture_output=True, text=True)
    if r.returncode != 0:
        return []
    shells = {"login", "zsh", "-zsh", "bash", "-bash", "sh", "-sh", "ps"}
    out = []
    for line in r.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            comm = os.path.basename(parts[1].strip())
            if comm not in shells:
                out.append((int(parts[0]), comm))
    return out


def window_tty(window_id):
    """The tty of a Terminal window's selected tab, or None if that window no longer exists (H207's close check)."""
    if window_id is None:
        return None
    script = ('tell application "Terminal"\n'
              f'    if exists (window id {int(window_id)}) then return tty of selected tab of window id {int(window_id)}\n'
              '    return ""\n'
              'end tell')
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def open_terminal_window(command, dry_run=False, out=print):
    """Open a Terminal window running `command` via osascript -> (rc, {'id': wid, 'tty': tty} or None) (H207)."""
    if dry_run:
        out(command)
        return 0, None
    s = subprocess.run(["osascript", "-e", _open_terminal_script(command)], capture_output=True, text=True)
    if s.returncode != 0:
        out(s.stderr.strip() or "osascript failed")
        return 1, None
    parts = s.stdout.strip().split(None, 1)
    info = {}
    if parts and parts[0].isdigit():
        info["id"] = int(parts[0])
    if len(parts) > 1 and parts[1].startswith("/dev/"):
        info["tty"] = parts[1]
        pids = tty_pids(parts[1])
        if pids:
            info["pid"] = pids[-1][0]
    return 0, (info or None)


def open_terminal(command, dry_run=False, out=print):
    """Open a Terminal window running `command` via osascript, or print the command on --dry-run (H196)."""
    return open_terminal_window(command, dry_run=dry_run, out=out)[0]


def close_terminal(window_id, dry_run=False, out=print):
    """Close a recorded Terminal window by its integer id (H207). Never touches unrecorded windows."""
    if window_id is None:
        return 1
    script = (
        'tell application "Terminal"\n'
        f'    if exists (window id {int(window_id)}) then\n'
        f'        close window id {int(window_id)}\n'
        '    end if\n'
        'end tell'
    )
    if dry_run:
        out(script)
        return 0
    s = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if s.returncode != 0:
        out(s.stderr.strip() or "osascript failed")
        return 1
    return 0


def parse(argv):
    if not argv or argv[0] not in TARGETS:
        raise SystemExit(__doc__)
    opts = {"agent": argv[0], "model": None, "name": None, "wake": None, "dry": False}
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--dry-run":
            opts["dry"] = True
        elif a in ("--model", "--name", "--wake") and i + 1 < len(argv):
            opts[a[2:]] = argv[i + 1]; i += 1
        else:
            raise SystemExit(f"unknown argument {a}\n\n{__doc__}")
        i += 1
    return opts


def launch_agent(agent, model=None, name=None, wake=None, dry_run=False, out=print):
    """Launch an agent or integrator in a new Terminal window -> (rc, window_info or None)."""
    root = main_root()
    folder = os.path.join(root, "scratch", "launch")
    os.makedirs(folder, exist_ok=True)
    name = name or session_name(agent, folder=folder)
    model = model or DEFAULT_MODEL[agent]
    role = "integrator" if agent == "integrator" else "worker"
    startup_cmd = [sys.executable, os.path.join(TOOLS, "startup.py"), "--role", role, "--space",
                   space_of(agent, model)]
    if agent == "integrator":
        startup_cmd.extend(["--hopper", name])
    r = subprocess.run(startup_cmd, cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        out(r.stdout + r.stderr)
        return 1, None
    path = os.path.join(folder, name + ".txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(start_where(agent, root))
        if agent == "integrator":
            f.write(integrator_prompt(name, r.stdout, wake_line=wake))
        else:
            f.write(prompt(agent, name, r.stdout, model=model))
    command = agent_command(agent, root, path, name, model if model != DEFAULT_MODEL[agent] else None)
    if dry_run:
        open_terminal(command, dry_run=True, out=out)
        out("".join(open(path, encoding="utf-8").readlines()[:3]))
        return 0, None
    rc, win = open_terminal_window(command, out=out)
    if rc != 0:
        return 1, None
    if win is not None:
        win["name"] = name
        win["agent"] = agent
    out(f"launched {name} ({agent}) with its brief in {os.path.relpath(path, root)}")
    return 0, win


def launch_resume(agent, jid, resume_cmd, notes, branch, worktree, space=None, dry_run=False, out=print):
    """Resume a returned job's session in a new Terminal window with the return notes (H207) -> (rc, window_info)."""
    root = main_root()
    folder = os.path.join(root, "scratch", "launch")
    os.makedirs(folder, exist_ok=True)
    name = f"{jid.lower()}-resume-{datetime.datetime.now():%m%d-%H%M%S}"
    path = os.path.join(folder, name + ".txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(resume_prompt(jid, notes, branch, worktree))
    command = resume_command(agent, resume_cmd, worktree, path, space=space, root=root)
    if dry_run:
        open_terminal(command, dry_run=True, out=out)
        return 0, None
    rc, win = open_terminal_window(command, out=out)
    if rc != 0:
        return 1, None
    if win is not None:
        win["name"] = name
        win["agent"] = agent
    out(f"resumed {jid} ({agent}) via {resume_cmd}")
    return 0, win


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    o = parse(argv)
    rc, _ = launch_agent(o["agent"], model=o["model"], name=o["name"], wake=o["wake"], dry_run=o["dry"])
    return rc


if __name__ == "__main__":
    sys.exit(main())
