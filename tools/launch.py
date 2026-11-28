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
(default), Codex `gpt-6.2-sol` (William, 2026-11-27). One job per session (P37): launch one window per Ready job."""
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
    return f"cd {shlex.quote(root)} && NAPKIN_SPACE={shlex.quote(space)} {run}"


def applescript(command):
    """`tell application "Terminal" to do script "<command>"`, the command escaped for an AppleScript string."""
    escaped = command.replace("\\", "\\\\").replace('"', '\\"')
    return f'tell application "Terminal" to do script "{escaped}"'


def open_terminal(command, dry_run=False, out=print):
    """Open a Terminal window running `command` via osascript, or print the command on --dry-run (H196)."""
    if dry_run:
        out(command)
        return 0
    s = subprocess.run(["osascript", "-e", applescript(command)], capture_output=True, text=True)
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


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    o = parse(argv)
    root = main_root()
    folder = os.path.join(root, "scratch", "launch")
    os.makedirs(folder, exist_ok=True)
    name = o["name"] or session_name(o["agent"], folder=folder)
    model = o["model"] or DEFAULT_MODEL[o["agent"]]
    role = "integrator" if o["agent"] == "integrator" else "worker"
    startup_cmd = [sys.executable, os.path.join(TOOLS, "startup.py"), "--role", role, "--space",
                   space_of(o["agent"], model)]
    if o["agent"] == "integrator":
        startup_cmd.extend(["--hopper", name])
    r = subprocess.run(startup_cmd, cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout + r.stderr)
        return 1
    path = os.path.join(folder, name + ".txt")
    with open(path, "w", encoding="utf-8") as f:
        if o["agent"] == "integrator":
            f.write(integrator_prompt(name, r.stdout, wake_line=o["wake"]))
        else:
            f.write(prompt(o["agent"], name, r.stdout, model=model))
    command = agent_command(o["agent"], root, path, name, o["model"])
    if o["dry"]:
        open_terminal(command, dry_run=True)
        print("".join(open(path, encoding="utf-8").readlines()[:3]))
        return 0
    if open_terminal(command) != 0:
        return 1
    print(f"launched {name} ({o['agent']}) with its brief in {os.path.relpath(path, root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
