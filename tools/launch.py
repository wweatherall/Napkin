#!/usr/bin/env python3
"""Start a worker session with its start-up brief already in its first message (T134), so it skips the start-up round
and can't skip the brief.

  python3 tools/launch.py <claude|codex|gemini> [--model M] [--name N] [--dry-run]

Runs `tools/startup.py --role worker` in the main checkout, writes the brief and the worker's instruction ("check the
board") to scratch/launch/<name>.txt, and opens a Terminal window running the agent with that file as its first
prompt. William's own permission settings apply: no bypass or full-access flag is ever added. --dry-run prints the
Terminal command and the prompt's first lines instead of opening the window. Run outside the sandbox (osascript).

Models: Gemini `gemini-4-hydrogen-medium` (default; `gemini-4-neon-medium` when asked), Claude `sonnet` at medium effort
(default), Codex its own default. One job per session (P37): launch one window per Ready job."""
import datetime
import os
import random
import shlex
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
AGENTS = ("claude", "codex", "gemini")
DEFAULT_MODEL = {"claude": "sonnet", "gemini": "gemini-4-hydrogen-medium", "codex": None}
WORDS = ("juniper", "cedar", "maple", "alder", "birch", "walnut", "cherry", "ash", "elm", "larch", "spruce", "teak")


def main_root():
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=TOOLS, capture_output=True,
                            text=True).stdout.strip()
    return os.path.dirname(os.path.realpath(os.path.join(TOOLS, common)))


def worktrees_dir(root):
    """Where job worktrees live (P63): <code bases>/.worktrees/<checkout>."""
    return os.path.join(os.path.dirname(root), ".worktrees", os.path.basename(root))


def session_name(agent, now=None):
    now = now or datetime.datetime.now()
    return f"{agent}-{random.choice(WORDS)}-{now:%m%d-%H%M}"


def space_of(agent):
    """The worker's personal space (T134): comitatus/04_Personal_Space/<agent>-coder."""
    return f"{agent}-coder"


def take_command(agent, name):
    """No --session: job.py names a Gemini session from ANTIGRAVITY_CONVERSATION_ID itself (GEMINI.md)."""
    return f"python3 tools/job.py take --as {agent}"


def prompt(agent, name, brief):
    """The first message: who you are, the brief (already run), and what to do now."""
    guide = {"claude": "CLAUDE.md", "codex": "AGENTS.md", "gemini": "GEMINI.md"}[agent]
    return (f"You are a {agent.capitalize()} worker in Napkin (session {name}). Your start-up brief is below: "
            f"tools/startup.py --role worker has already been run for you, so don't run it again.\n\n{brief.strip()}\n\n"
            f"Now check the board: run `{take_command(agent, name)}` (outside the sandbox) and follow BOARD.md and "
            f"{guide} for that one job (P37).\n\nYour personal space is {space_of(agent)}: log what you do with "
            f"`python3 tools/personal_space.py log {space_of(agent)} \"<line>\"`, and keep a journal of your own (what you "
            f"noticed, liked, found hard, want to try) with `python3 tools/personal_space.py journal {space_of(agent)} "
            f"\"<line>\"`; the next {agent.capitalize()} worker sees the last ten lines of each.\n")


def agent_command(agent, root, prompt_file, name, model=None):
    """The shell command the Terminal window runs."""
    model = model or DEFAULT_MODEL[agent]
    first = f'"$(cat {shlex.quote(prompt_file)})"'
    wt = shlex.quote(worktrees_dir(root))
    if agent == "gemini":
        run = f"agy --model {shlex.quote(model)} -i {first}"
    elif agent == "claude":
        run = (f"claude --model {shlex.quote(model)} --effort medium --add-dir {wt} --remote-control "
               f"{shlex.quote(name)} {first}")
    else:
        run = f"codex -C {shlex.quote(root)} --add-dir {wt}" + (f" -m {shlex.quote(model)}" if model else "") + f" {first}"
    return f"cd {shlex.quote(root)} && {run}"


def applescript(command):
    """`tell application "Terminal" to do script "<command>"`, the command escaped for an AppleScript string."""
    escaped = command.replace("\\", "\\\\").replace('"', '\\"')
    return f'tell application "Terminal" to do script "{escaped}"'


def parse(argv):
    if not argv or argv[0] not in AGENTS:
        raise SystemExit(__doc__)
    opts = {"agent": argv[0], "model": None, "name": None, "dry": False}
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--dry-run":
            opts["dry"] = True
        elif a in ("--model", "--name") and i + 1 < len(argv):
            opts[a[2:]] = argv[i + 1]; i += 1
        else:
            raise SystemExit(f"unknown argument {a}\n\n{__doc__}")
        i += 1
    return opts


def main(argv=None):
    o = parse(sys.argv[1:] if argv is None else argv)
    root = main_root()
    name = o["name"] or session_name(o["agent"])
    r = subprocess.run([sys.executable, os.path.join(root, "tools", "startup.py"), "--role", "worker", "--space",
                        space_of(o["agent"])], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout + r.stderr)
        return 1
    folder = os.path.join(root, "scratch", "launch")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name + ".txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(prompt(o["agent"], name, r.stdout))
    command = agent_command(o["agent"], root, path, name, o["model"])
    if o["dry"]:
        print(command)
        print("".join(open(path, encoding="utf-8").readlines()[:3]))
        return 0
    s = subprocess.run(["osascript", "-e", applescript(command)], capture_output=True, text=True)
    if s.returncode != 0:
        print(s.stderr.strip() or "osascript failed")
        return 1
    print(f"launched {name} ({o['agent']}) with its brief in {os.path.relpath(path, root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
