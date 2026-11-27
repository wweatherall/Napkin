#!/usr/bin/env python3
"""Checks T134's launcher (tools/launch.py): the first prompt carries the worker brief and the take command, each agent
gets its own command with William's settings (no bypass flags), and the AppleScript string survives quoting. Opens no
window. Summary line: LAUNCH TESTS: N passed, M failed."""
import datetime
import os
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import launch

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        print(f"FAIL {name}  {detail}")


root = "/x/comitatus/08_Code_Bases/Napkin"
p = launch.prompt("gemini", "gemini-cedar-1126-1900", "This checkout: ...\nReady on the board:\n  H150\n")
check("the first prompt carries the brief and says not to run start-up again",
      "Ready on the board:\n  H150" in p and "don't run it again" in p, p)
check("a Gemini prompt takes with no --session (job.py reads Gemini's conversation id, GEMINI.md)",
      "`python3 tools/job.py take --as gemini`" in p and "--session" not in p and "GEMINI.md" in p, p)
check("a Claude prompt takes without a session flag",
      "take --as claude`" in launch.prompt("claude", "claude-elm-1", "b") and "CLAUDE.md" in launch.prompt("claude", "n", "b"))

g = launch.agent_command("gemini", root, "/x/p file.txt", "gemini-a")
check("Gemini runs agy with the hydrogen model by default and the prompt file",
      g == "cd /x/comitatus/08_Code_Bases/Napkin && agy --model gemini-4-hydrogen-medium -i \"$(cat '/x/p file.txt')\"", g)
c = launch.agent_command("claude", root, "/x/p.txt", "claude-a")
check("Claude runs sonnet at medium effort with the worktrees folder and remote control",
      "claude --model sonnet --effort medium --add-dir /x/comitatus/08_Code_Bases/.worktrees/Napkin --remote-control claude-a" in c, c)
x = launch.agent_command("codex", root, "/x/p.txt", "codex-a")
check("Codex gets its root and the worktrees folder", "codex -C /x/comitatus/08_Code_Bases/Napkin --add-dir "
      "/x/comitatus/08_Code_Bases/.worktrees/Napkin \"$(cat /x/p.txt)\"" in x, x)
check("no command adds a bypass or full-access flag",
      not any(w in g + c + x for w in ("dangerously", "skip-permissions", "full-auto", "yolo", "bypass")))
check("--model replaces the default", "--model gemini-4-neon-medium" in
      launch.agent_command("gemini", root, "/p", "n", "gemini-4-neon-medium"))

script = launch.applescript(g)
inner = script[len('tell application "Terminal" to do script "'):-1]
check("the AppleScript string unescapes to the command",
      inner.replace('\\"', '"').replace("\\\\", "\\") == g
      and all(inner[i - 1] == "\\" for i, ch in enumerate(inner) if ch == '"'), script)
check("a session name is <agent>-<word>-<MMDD-HHMM>",
      launch.session_name("gemini", datetime.datetime(2026, 11, 26, 19, 5)).endswith("-1126-1905")
      and launch.session_name("gemini").split("-")[1] in launch.WORDS)

out = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "launch.py"), "gemini",
                      "--dry-run", "--name", "gemini-test-dryrun"], capture_output=True, text=True)
made = os.path.join(launch.main_root(), "scratch", "launch", "gemini-test-dryrun.txt")
check("--dry-run prints the command, writes the prompt with the real brief, opens nothing",
      out.returncode == 0 and "agy --model gemini-4-hydrogen-medium -i" in out.stdout and os.path.exists(made)
      and "Worker checklist" in open(made).read(), out.stdout + out.stderr)
if os.path.exists(made):
    os.remove(made)

print(f"LAUNCH TESTS: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
