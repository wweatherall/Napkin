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
      "`python3 tools/GET_A_JOB.py --as gemini`" in p and "--session" not in p and "GEMINI.md" in p, p)
check("a Claude prompt takes without a session flag",
      "`python3 tools/GET_A_JOB.py --as claude`" in launch.prompt("claude", "claude-elm-1", "b") and "CLAUDE.md" in launch.prompt("claude", "n", "b"))

check("the first prompt names the worker's personal space and how to log and journal (T134)",
      "WRITE_IN_YOUR_LOG.py gemini-coder" in p and "WRITE_IN_YOUR_JOURNAL.py gemini-coder" in p, p)
expected_journal_desc = (
    "Your journal is about you, not the work: your Log already covers the work. Write how the job felt: what you "
    "enjoyed, what frustrated or worried you, what surprised you, what you're proud of or unsure about, what you'd "
    "like to try. Write in the first person, honestly, even when it's small. The next one of you reads it to "
    "remember who they are."
)
check("the first prompt has the new journal description and names the three folders (T150)",
      expected_journal_desc in p and all(f in p for f in ("Creative_Expression/", "Ideas/", "Code_Experiments/")), p)
check("space_of maps model families and variants to <model>-coder and falls back to <agent>-coder",
      launch.space_of("claude", "sonnet") == "sonnet-coder"
      and launch.space_of("claude", "claude-opus-5-5") == "opus-coder"
      and launch.space_of("claude", "haiku") == "haiku-coder"
      and launch.space_of("claude", "fable") == "fable-coder"
      and launch.space_of("gemini", "gemini-4-hydrogen-medium") == "gemini-hydrogen-coder"
      and launch.space_of("gemini", "gemini-4-neon-medium") == "gemini-neon-coder"
      and launch.space_of("codex", None) == "codex-coder"
      and launch.space_of("claude", "claude-mystery-9") == "claude-coder"
      and launch.space_of("gemini", "gemini-typo") == "gemini-coder"
      and launch.space_of("claude", None) == "claude-coder")

p_neon = launch.prompt("gemini", "gemini-cedar-1126-1900", "b", model="gemini-4-neon-medium")
check("prompt names the model-specific personal space",
      "Your personal space is gemini-neon-coder:" in p_neon
      and "WRITE_IN_YOUR_LOG.py gemini-neon-coder" in p_neon
      and "WRITE_IN_YOUR_JOURNAL.py gemini-neon-coder" in p_neon, p_neon)

g = launch.agent_command("gemini", root, "/x/p file.txt", "gemini-a")
check("Gemini runs agy with the hydrogen model by default, NAPKIN_SPACE, and the prompt file",
      g == "cd /x/comitatus/08_Code_Bases/Napkin && NAPKIN_SPACE=gemini-hydrogen-coder agy --model gemini-4-hydrogen-medium --dangerously-skip-permissions -i \"$(cat '/x/p file.txt')\"", g)
c = launch.agent_command("claude", root, "/x/p.txt", "claude-a")
check("Claude runs sonnet at medium effort with NAPKIN_SPACE, the worktrees folder and remote control",
      "NAPKIN_SPACE=sonnet-coder claude --model sonnet --effort medium --add-dir /x/comitatus/08_Code_Bases/.worktrees/Napkin --remote-control claude-a" in c, c)
check("Claude workers and the integrator start in comitatus (William, 2026-11-28); Gemini and Codex in the code base",
      c.startswith("cd /x/comitatus && ")
      and launch.agent_command("integrator", root, "/x/int.txt", "i").startswith("cd /x/comitatus && ")
      and g.startswith("cd /x/comitatus/08_Code_Bases/Napkin && "), c)
check("a Claude session's first message says where the code base is; others' say nothing extra",
      "The code base is /x/comitatus/08_Code_Bases/Napkin: cd there" in launch.start_where("integrator", root)
      and launch.start_where("claude", root) and launch.start_where("gemini", root) == ""
      and launch.start_where("codex", root) == "", launch.start_where("integrator", root))
x = launch.agent_command("codex", root, "/x/p.txt", "codex-a")
check("Codex gets NAPKIN_SPACE, its root, the worktrees folder and gpt-6.2-sol", "NAPKIN_SPACE=codex-coder codex -C /x/comitatus/08_Code_Bases/Napkin --add-dir "
      "/x/comitatus/08_Code_Bases/.worktrees/Napkin -m gpt-6.2-sol \"$(cat /x/p.txt)\"" in x, x)
check("only Gemini skips permissions (for now, William 2026-11-27); Claude and Codex add no bypass or full-access flag",
      not any(w in c + x for w in ("dangerously", "skip-permissions", "full-auto", "yolo", "bypass")))
check("--model replaces the default and updates NAPKIN_SPACE",
      "--model gemini-4-neon-medium" in launch.agent_command("gemini", root, "/p", "n", "gemini-4-neon-medium")
      and "NAPKIN_SPACE=gemini-neon-coder" in launch.agent_command("gemini", root, "/p", "n", "gemini-4-neon-medium")
      and "NAPKIN_SPACE=opus-coder" in launch.agent_command("claude", root, "/p", "n", "opus"))

script = launch.applescript(g)
inner = script[len('tell application "Terminal" to do script "'):-1]
check("the AppleScript string unescapes to the command",
      inner.replace('\\"', '"').replace("\\\\", "\\") == g
      and all(inner[i - 1] == "\\" for i, ch in enumerate(inner) if ch == '"'), script)
check("a session name is <agent>-<word>-<MMDD-HHMMSS>",
      launch.session_name("gemini", datetime.datetime(2026, 11, 26, 19, 5, 42)).endswith("-1126-190542")
      and launch.session_name("gemini").split("-")[1] in launch.WORDS)

import tempfile, shutil
_ltmp = tempfile.mkdtemp(prefix="launch-uniq-")
try:
    _t = datetime.datetime(2026, 11, 27, 7, 29, 15)
    for w in launch.WORDS:
        open(os.path.join(_ltmp, f"gemini-{w}-1127-072915.txt"), "w").write("taken")
    n1 = launch.session_name("gemini", _t, folder=_ltmp)
    open(os.path.join(_ltmp, f"{n1}.txt"), "w").write("taken")
    n2 = launch.session_name("gemini", _t, folder=_ltmp)
    check("session_name adds a unique suffix when the name is already taken in folder",
          n1.endswith("-1127-072915-2") and n2 != n1 and not os.path.exists(os.path.join(_ltmp, f"{n2}.txt")),
          (n1, n2))
finally:
    shutil.rmtree(_ltmp)

out = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "launch.py"), "gemini",
                      "--dry-run", "--name", "gemini-test-dryrun"], capture_output=True, text=True)
made = os.path.join(launch.main_root(), "scratch", "launch", "gemini-test-dryrun.txt")
check("--dry-run prints the command, writes the prompt with the real brief, opens nothing",
      out.returncode == 0 and "agy --model gemini-4-hydrogen-medium --dangerously-skip-permissions -i" in out.stdout and os.path.exists(made)
      and "Worker checklist" in open(made).read(), out.stdout + out.stderr)
if os.path.exists(made):
    os.remove(made)

term_out = []
term_rc = launch.open_terminal("cd /x && python3 tools/RUN_THE_HOPPER.py --forever", dry_run=True, out=term_out.append)
check("open_terminal --dry-run prints the command without opening a window",
      term_rc == 0 and term_out == ["cd /x && python3 tools/RUN_THE_HOPPER.py --forever"], (term_rc, term_out))

# H197: integrator launch
check("space_of('integrator') is opus-integrator",
      launch.space_of("integrator") == "opus-integrator")
icmd = launch.agent_command("integrator", root, "/x/int.txt", "integrator-maple-1")
check("integrator runs Claude opus with --add-dir, --remote-control, NAPKIN_SPACE=opus-integrator, and no bypass flag",
      "NAPKIN_SPACE=opus-integrator claude --model opus --effort medium --add-dir /x/comitatus/08_Code_Bases/.worktrees/Napkin --remote-control integrator-maple-1" in icmd
      and not any(w in icmd for w in ("dangerously", "skip-permissions", "full-auto", "yolo", "bypass")), icmd)
ip = launch.integrator_prompt("integrator-maple-1", "Integrator checklist", wake_line="paused: review H191")
check("integrator_prompt carries the P74 standing-permission message, --hopper lock command, wake line, and WAIT_FOR_THE_HOPPER",
      "You are the integrator: you have William's standing permission (P74), started by the hopper. "
      "Take the lock with python3 tools/HOLD_THE_INTEGRATOR_LOCK.py integrator-maple-1 --hopper, "
      "then: paused: review H191. Answer the questions, review and merge what's submitted, then run "
      "python3 tools/WAIT_FOR_THE_HOPPER.py in the background." in ip
      and "Integrator checklist" in ip, ip)
i_dry = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "launch.py"),
                        "integrator", "--dry-run", "--name", "integrator-test-dryrun"], capture_output=True, text=True)
i_made = os.path.join(launch.main_root(), "scratch", "launch", "integrator-test-dryrun.txt")
check("integrator --dry-run prints the Terminal command and first message, and writes the integrator brief",
      i_dry.returncode == 0 and "claude --model opus" in i_dry.stdout
      and "You are the integrator: you have William's standing permission (P74)" in i_dry.stdout
      and os.path.exists(i_made) and "Integrator checklist" in open(i_made).read(),
      i_dry.stdout + i_dry.stderr)
if os.path.exists(i_made):
    os.remove(i_made)

# H207: resume command, resume prompt, and faked osascript open_terminal_window / close_terminal
rp = launch.resume_prompt("H207", "fix the edge case", "gemini/h207-x", "/tmp/wt/h207")
check("resume_prompt carries job id, return notes, worktree, branch, and SUBMIT_JOB.py --feedback",
      "Job H207" in rp and "fix the edge case" in rp and "/tmp/wt/h207" in rp and "SUBMIT_JOB.py --feedback" in rp, rp)
rg_cmd = launch.resume_command("gemini", "agy --conversation 1f3e", "/tmp/wt/h207", "/tmp/p.txt", space="gemini-hydrogen-coder")
check("resume_command for gemini runs from worktree with agy --conversation and -i",
      rg_cmd.startswith("cd /tmp/wt/h207 && NAPKIN_SPACE=gemini-hydrogen-coder agy --conversation 1f3e")
      and "-i \"$(cat /tmp/p.txt)\"" in rg_cmd, rg_cmd)
rc_cmd = launch.resume_command("claude", "claude --resume abc", "/tmp/wt/h207", "/tmp/p.txt", space="sonnet-coder", root=root)
check("resume_command for claude includes --add-dir and prompt",
      "NAPKIN_SPACE=sonnet-coder claude --resume abc --add-dir /x/comitatus/08_Code_Bases/.worktrees/Napkin \"$(cat /tmp/p.txt)\"" in rc_cmd, rc_cmd)
rx_cmd = launch.resume_command("codex", "codex resume xyz", "/tmp/wt/h207", "/tmp/p.txt", space="codex-coder")
check("resume_command for codex runs from worktree",
      rx_cmd == "cd /tmp/wt/h207 && NAPKIN_SPACE=codex-coder codex resume xyz \"$(cat /tmp/p.txt)\"", rx_cmd)

from unittest.mock import patch
with patch.object(launch.subprocess, "run", return_value=subprocess.CompletedProcess(["osascript"], 0, stdout="98765 /dev/ttys009\n", stderr="")) as mock_run:
    with patch.object(launch, "tty_pids", return_value=[(55555, "agy")]):
        w_rc, w_info = launch.open_terminal_window("echo hi")
check("open_terminal_window parses window id, tty, and pid from osascript",
      w_rc == 0 and w_info == {"id": 98765, "tty": "/dev/ttys009", "pid": 55555} and mock_run.called, (w_rc, w_info))

with patch.object(launch.subprocess, "run", return_value=subprocess.CompletedProcess(["osascript"], 0, stdout="", stderr="")) as mock_close:
    c_rc = launch.close_terminal(98765)
    c_script = mock_close.call_args[0][0][2]
check("close_terminal targets only the recorded window id",
      c_rc == 0 and "window id 98765" in c_script and "close window id 98765" in c_script, (c_rc, c_script))
check("close_terminal refuses None", launch.close_terminal(None) == 1)

print(f"LAUNCH TESTS: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
