#!/usr/bin/env python3
"""Checks tools/integrate.py and tools/gate.sh on throwaway repositories (P18, P20). Summary line:
INTEGRATE TESTS: N passed, M failed."""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import integrate
import integrator

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def repo():
    root = tempfile.mkdtemp(prefix="integrate-test-")
    sh(root, "git", "init", "-q", "-b", "main")
    sh(root, "git", "config", "user.email", "t@example.invalid"); sh(root, "git", "config", "user.name", "t")
    os.makedirs(os.path.join(root, "docs", "handoff"))
    open(os.path.join(root, "docs", "decision-log.md"), "w").write("# Log\n\n## Work list\n\n| # | Item | Status |\n|---|---|---|\n| T1 | a | Open |\n")
    open(os.path.join(root, "docs", "agent-handoff.md"), "w").write("# Handoff\n\n## Open exchanges\n\n<!-- open list: built from docs/handoff/ by tools/handoff.py; don't edit by hand -->\n\n(none open)\n\n<!-- end of open list -->\n\n## Archived\n")
    open(os.path.join(root, "docs", "handoff-archive.md"), "w").write("# Archive\n")
    open(os.path.join(root, "notes.md"), "w").write("one\n")
    sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "base")
    return root


# 1. A conflict in a file integrate.py doesn't settle must stop it, before anything is staged.
root = repo()
sh(root, "git", "checkout", "-qb", "agent/x")
open(os.path.join(root, "notes.md"), "w").write("agent\n"); sh(root, "git", "commit", "-qam", "agent edit")
sh(root, "git", "checkout", "-q", "main")
open(os.path.join(root, "notes.md"), "w").write("main\n"); sh(root, "git", "commit", "-qam", "main edit")
integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
out = io.StringIO()
cwd = os.getcwd(); os.chdir(root)
try:
    with contextlib.redirect_stdout(out):
        rc = integrate.main(["agent/x", "--as", "tester", "--no-gate"])
finally:
    os.chdir(cwd)
check("a conflict in another file stops the merge", rc == 1 and "notes.md" in out.getvalue(), out.getvalue())
check("it is still unmerged afterwards (nothing staged over it)",
      "notes.md" in sh(root, "git", "diff", "--name-only", "--diff-filter=U").stdout)
check("and nothing was committed", sh(root, "git", "log", "--oneline", "-1").stdout.split()[1:3] == ["main", "edit"])
shutil.rmtree(root)

# 2. has_markers finds leftover conflict markers.
tmp = tempfile.mkdtemp(prefix="markers-")
p = os.path.join(tmp, "f.md"); open(p, "w").write("a\n<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> b\n")
q = os.path.join(tmp, "g.md"); open(q, "w").write("a line with ======= in it\n")
check("conflict markers are found", integrate.has_markers(p))
check("an ordinary ======= line isn't a marker", not integrate.has_markers(q))
shutil.rmtree(tmp)


# 3. The gate: a known UI failure never excuses a feature-test failure.
def gate(quick_out, quick_rc, known, full_rc=0, expected_full_args=""):
    root = tempfile.mkdtemp(prefix="gate-test-")
    sh(root, "git", "init", "-q")
    os.makedirs(os.path.join(root, "tools")); os.makedirs(os.path.join(root, "tests"))
    shutil.copy(os.path.join(HERE, "gate.sh"), os.path.join(root, "tools", "gate.sh"))
    open(os.path.join(root, "tools", "quicktest.sh"), "w").write(f"#!/bin/bash\ncat <<'X'\n{quick_out}\nX\nexit {quick_rc}\n")
    open(os.path.join(root, "tools", "fulltest.sh"), "w").write(
        '#!/bin/bash\nprintf "%s" "$*" > full-args\n' + f"exit {full_rc}\n")
    for f in ("quicktest.sh", "fulltest.sh"):
        os.chmod(os.path.join(root, "tools", f), 0o755)
    open(os.path.join(root, "tests", "known_failures.txt"), "w").write(known)
    r = sh(root, "bash", "tools/gate.sh")
    args = open(os.path.join(root, "full-args")).read()
    check("gate full-test mode: " + (expected_full_args or "standalone"), args == expected_full_args, args)
    shutil.rmtree(root)
    return r.returncode, r.stdout


KNOWN = "[hide] View > Hidden geometry shows it ghosted  # T85\n"
HIDE = "QUICK FAIL [hide] View > Hidden geometry shows it ghosted  <Object#null>"
OK_FEAT = "features: NATIVE TESTS: 83 passed, 0 failed | SCENARIO TESTS: 170 passed, 0 failed | viewport: QUICK 152 passed, 1 failed in 11 s"
BAD_FEAT = "features: NATIVE TESTS: 83 passed, 0 failed | SCENARIO TESTS: 169 passed, 1 failed | viewport: QUICK 152 passed, 1 failed in 11 s"
rc, out = gate(HIDE + "\n" + OK_FEAT, 1, KNOWN)
check("a listed UI failure alone passes the gate", rc == 0 and "GATE PASS" in out, out)
rc, out = gate(HIDE + "\n" + BAD_FEAT, 1, KNOWN)
check("a listed UI failure plus a feature-test failure fails the gate (Codex's case)", rc == 1 and "SCENARIO TESTS" in out, out)
rc, out = gate(HIDE + "\n" + OK_FEAT, 1, "")
check("an unlisted UI failure fails the gate", rc == 1 and "NEW FAILURE" in out, out)
rc, out = gate("QUICK 153 passed, 0 failed", 0, "", expected_full_args="")
check("no feature-test summary at all fails the gate", rc == 1 and "no feature-test summary" in out, out)
ALL_OK = OK_FEAT.replace("QUICK 152 passed, 1 failed", "QUICK 153 passed, 0 failed")
rc, out = gate(ALL_OK, 0, "", expected_full_args="--gate-ui-only")
check("a successful quick run reuses its parse and feature checks", rc == 0 and "GATE PASS" in out, out)
rc, out = gate(ALL_OK, 0, "", full_rc=1, expected_full_args="--gate-ui-only")
check("a full-test failure still fails the gate after reuse", rc == 1 and "full test FAILS" in out, out)
rc, out = gate(HIDE + "\n" + OK_FEAT.replace("NATIVE TESTS: 83 passed, 0 failed", "native did not finish"), 1, KNOWN)
check("a listed UI failure cannot excuse an unfinished feature test", rc == 1 and "didn't finish cleanly" in out, out)
rc, out = gate("SCRIPT ERROR: broken\n" + OK_FEAT, 0, "", expected_full_args="")
check("script errors fail the gate and keep full parsing enabled", rc == 1 and "didn't finish cleanly" in out, out)
rc, out = gate(ALL_OK, 1, "")
check("an unexplained quick exit still fails the gate", rc == 1 and "without a QUICK FAIL" in out, out)
check("the real known-failures list holds only failures with an open Work list item",
      all("# T" in l for l in open(os.path.join(HERE, "..", "tests", "known_failures.txt")) if l.strip() and not l.startswith("#")))


# 4. The protocol version: a branch's bump goes on top of main's (A35), and files outside the Touches list are flagged.
def write(root, rel, text):
    os.makedirs(os.path.dirname(os.path.join(root, rel)) or root, exist_ok=True)
    open(os.path.join(root, rel), "w").write(text)


root = repo()
write(root, "worker/serve.py", "PROTOCOL_VERSION = 2\n")
write(root, "viewport/main.gd", "const PROTOCOL_VERSION := 2\n")
write(root, "docs/protocol.md", "The wire protocol's own version is **2** (currently 2).\n")
sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "v2")
sh(root, "git", "checkout", "-qb", "agent/y")
write(root, "worker/serve.py", "PROTOCOL_VERSION = 3\n")
write(root, "viewport/main.gd", "const PROTOCOL_VERSION := 3\n")
write(root, "docs/protocol.md", "The wire protocol's own version is **3** (currently 3).\n")
write(root, "worker/new_op.py", "x = 1\n")
write(root, "viewport/other.gd", "# not in the job\n")
write(root, "docs/handoff/H050-y.md", "### H050 — y\n\nAuthor: Claude | Date: 2026-11-22 | Status: answered\n\n"
      "Touches: worker/serve.py, viewport/main.gd, worker/new_op.py, docs/protocol.md.\n")
sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "branch bumps to 3")
sh(root, "git", "checkout", "-q", "main")
write(root, "worker/serve.py", "PROTOCOL_VERSION = 3\n"); write(root, "viewport/main.gd", "const PROTOCOL_VERSION := 3\n")
write(root, "docs/protocol.md", "The wire protocol's own version is **3** (currently 3).\n")
sh(root, "git", "commit", "-qam", "main bumps to 3")
integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
out = io.StringIO(); cwd = os.getcwd(); os.chdir(root)
try:
    with contextlib.redirect_stdout(out):
        rc = integrate.main(["agent/y", "--as", "tester", "--no-gate"])
finally:
    os.chdir(cwd)
said = out.getvalue()
check("both bumped 2 -> 3: the branch's lands as 4, both constants and the doc",
      open(os.path.join(root, "worker/serve.py")).read() == "PROTOCOL_VERSION = 4\n"
      and open(os.path.join(root, "viewport/main.gd")).read() == "const PROTOCOL_VERSION := 4\n"
      and "**4**" in open(os.path.join(root, "docs/protocol.md")).read() and "currently 4" in open(os.path.join(root, "docs/protocol.md")).read(), said)
check("it says so", "renumbered" in said or "is 4 on main" in said, said)
check("a file the job doesn't list is flagged, and only that one",
      "OUTSIDE ITS TOUCHES LIST: viewport/other.gd" in said and "new_op.py (" not in said.split("OUTSIDE")[-1], said)
check("the merge went in, and its message records both", rc == 0 and "renumbered to 4" in sh(root, "git", "log", "-1", "--format=%B").stdout
      and "viewport/other.gd" in sh(root, "git", "log", "-1", "--format=%B").stdout, said)
shutil.rmtree(root)

# 5. --job: a scratch branch (main merged into the job's branch first) delivers the job: it is marked merged, and
#    its worktree and its own branch go too; a job not in the queue, or one whose branch isn't in it, is refused.
import json
import job
root = repo()
sh(root, "git", "checkout", "-qb", "claude/h070-x")
write(root, "x.py", "x = 70\n"); sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "H070: x")
sh(root, "git", "checkout", "-q", "main")
write(root, "notes.md", "main moved on\n"); sh(root, "git", "commit", "-qam", "main moves")
wt = root + "-h070"
sh(root, "git", "worktree", "add", "-q", wt, "claude/h070-x")
sh(root, "git", "branch", "scratch/h070", "claude/h070-x")
sh(root, "git", "checkout", "-q", "scratch/h070"); sh(root, "git", "merge", "-q", "--no-edit", "main")
sh(root, "git", "checkout", "-q", "main")
open(job.state_path(root), "w").write(json.dumps({"jobs": {
    "H070": {"branch": "claude/h070-x", "worktree": wt, "state": "done"},
    "H071": {"branch": "other-job", "state": "done"}}, "events": []}))
integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)


def run_integrate(*args):
    out = io.StringIO(); cwd = os.getcwd(); os.chdir(root)
    try:
        with contextlib.redirect_stdout(out):
            rc = integrate.main(list(args))
    finally:
        os.chdir(cwd)
    return rc, out.getvalue()


head0 = sh(root, "git", "rev-parse", "HEAD").stdout
rc, said = run_integrate("scratch/h070", "--as", "tester", "--no-gate", "--job", "H099")
check("--job: a job not in the queue is refused, nothing merged",
      rc == 1 and "no such job" in said and sh(root, "git", "rev-parse", "HEAD").stdout == head0, said)
sh(root, "git", "branch", "other-job", "main")
write(root, "y.py", "y\n"); sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "main again")
sh(root, "git", "branch", "-f", "other-job", "HEAD"); sh(root, "git", "reset", "-q", "--hard", "HEAD~1")
head0 = sh(root, "git", "rev-parse", "HEAD").stdout
rc, said = run_integrate("scratch/h070", "--as", "tester", "--no-gate", "--job", "H071")
check("--job: a job whose branch isn't all in the scratch branch is refused, nothing merged",
      rc == 1 and "isn't all in" in said and sh(root, "git", "rev-parse", "HEAD").stdout == head0, said)
rc, said = run_integrate("scratch/h070", "--as", "tester", "--no-gate", "--job", "H070")
branches = sh(root, "git", "branch").stdout
check("--job: the scratch branch merges and the job is marked merged",
      rc == 0 and job.read_state(job.state_path(root))["jobs"]["H070"]["state"] == "merged", said)
check("--job: the job's worktree and its own branch are removed, and the scratch branch",
      not os.path.isdir(wt) and "claude/h070-x" not in branches and "scratch/h070" not in branches, said + branches)
shutil.rmtree(root)

# 6. A BOARD.md conflict (H073): main's Order line, job table and Notes stay; the branch's edits to the other
#    sections come with it; both changing one section stops the merge.
BOARD = ("# Work board\n\nIntro.\n\nOrder: H001\n\n## If you're not the integrator\n\n1. Take a job.\n\n"
         "## If you're the integrator\n\nSee integrator.md.\n\n## Jobs\n\n| Job |\n|---|\n| H001 |\n\n## Notes\n\n- one\n")
main_b = BOARD.replace("Order: H001", "Order: H001, H002").replace("| H001 |", "| H001 |\n| H002 |").replace("- one", "- main's note")
branch_b = BOARD.replace("1. Take a job.", "1. Take a job, then read its Notes.").replace("- one", "- branch's note")
text, clashes = integrate.settle_board(main_b, BOARD, branch_b)
check("board: the branch's instructions and main's Order, table and Notes all stay",
      clashes == [] and "1. Take a job, then read its Notes." in text and "Order: H001, H002" in text
      and "| H002 |" in text and "- main's note" in text and "branch's note" not in text, text)
added = branch_b.replace("## Jobs", "## Tips\n\nA tip.\n\n## Jobs")
text, _ = integrate.settle_board(main_b, BOARD, added)
check("board: a section the branch adds goes in where the branch put it",
      text.index("See integrator.md.") < text.index("## Tips") < text.index("## Jobs"), text)
text, _ = integrate.settle_board(main_b, BOARD, BOARD)
check("board: a branch that changed nothing leaves main's file as it is", text == main_b, text)
both = main_b.replace("1. Take a job.", "1. Take one job.")
text, clashes = integrate.settle_board(both, BOARD, branch_b)
check("board: both changing the same section is reported", clashes == ["If you're not the integrator"], clashes)

root = repo()
write(root, "BOARD.md", BOARD); sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "board")
sh(root, "git", "checkout", "-qb", "agent/b")
write(root, "BOARD.md", branch_b); sh(root, "git", "commit", "-qam", "branch edits the board")
sh(root, "git", "checkout", "-q", "main")
write(root, "BOARD.md", main_b); sh(root, "git", "commit", "-qam", "main edits the board")
integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
rc, said = run_integrate("agent/b", "--as", "tester", "--no-gate")
board = open(os.path.join(root, "BOARD.md")).read()
check("board merge: the branch's instructions and main's Notes are both in the merge",
      rc == 0 and "1. Take a job, then read its Notes." in board and "- main's note" in board
      and "<<<<<<<" not in board and "settled BOARD.md" in said, said + board)
sh(root, "git", "checkout", "-qb", "agent/c", "HEAD~1")
write(root, "BOARD.md", main_b.replace("1. Take a job, then read its Notes.", "x").replace("1. Take a job.", "1. Take two jobs.")
      .replace("- main's note", "- c's note"))
sh(root, "git", "commit", "-qam", "c edits the same section")
sh(root, "git", "checkout", "-q", "main")
head0 = sh(root, "git", "rev-parse", "HEAD").stdout
rc, said = run_integrate("agent/c", "--as", "tester", "--no-gate")
check("board merge: both editing the same section stops it, nothing committed",
      rc == 1 and "both changed" in said and "If you're not the integrator" in said
      and sh(root, "git", "rev-parse", "HEAD").stdout == head0, said)
sh(root, "git", "merge", "--abort")
shutil.rmtree(root)

# 7. Trace the actual steps through main(), including the map pause and --continue. The names below are
#    the documented order, independent of the production tuples. Wrappers still run each step's real work.
MERGE_ORDER = ["check_start", "prepare_log", "merge_branch", "settle_conflicts", "check_touches", "number_entries",
               "archive_entries", "update_statuses", "rebuild_and_check", "run_gate", "pause_for_map"]
FINISH_ORDER = ["commit_merge", "clean_up_job", "record_results", "push_main"]


@contextlib.contextmanager
def trace_steps():
    calls, states = [], []

    def wrap(step):
        def traced(state):
            calls.append(step.__name__)
            states.append(state)
            returned = step(state)
            if returned is not state:
                raise AssertionError(f"{step.__name__} didn't return its run state")
            return returned
        return traced

    with patch.object(integrate, "MERGE_STEPS", tuple(wrap(f) for f in integrate.MERGE_STEPS)), \
         patch.object(integrate, "FINISH_STEPS", tuple(wrap(f) for f in integrate.FINISH_STEPS)), \
         patch.object(integrate, "load_continuation", wrap(integrate.load_continuation)):
        yield calls, states


def ordered_repo(gate_rc=0):
    root = repo()
    write(root, "ARCHITECTURE.md", "# Map\n")
    # A real subprocess gate, with a visible verdict; no actual remote is needed for these merge checks.
    write(root, "tools/gate.sh", f"#!/bin/sh\necho GATE {'PASS' if not gate_rc else 'FAIL'}\nexit {gate_rc}\n")
    os.chmod(os.path.join(root, "tools/gate.sh"), 0o755)
    sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "map and gate")
    sh(root, "git", "checkout", "-qb", "agent/ordered")
    write(root, "notes.md", "ordered change\n")
    write(root, "docs/handoff/H080-ordered.md",
          "### H080 — T1: ordered merge\n\nAuthor: Codex | Status: answered\n\n"
          "Architecture: update the map.\nResult: abc1234; fixture checks; ordered change\n")
    sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "ordered branch")
    sh(root, "git", "checkout", "-q", "main")
    integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
    return root


root = ordered_repo()
with trace_steps() as (calls, states):
    rc, said = run_integrate("agent/ordered", "--as", "tester", "--impact", "fixture")
check("main runs every named step in documented order", rc == 0 and calls == MERGE_ORDER + FINISH_ORDER, calls)
check("each step takes and returns the same run state", len({id(s) for s in states}) == 1)
check("the ordered run gates, commits, and records the merge result",
      "GATE PASS" in said and "Result (abc1234, merged" in open(os.path.join(root, "docs/decision-log.md")).read()
      and not os.path.exists(integrate.state_file(root)), said)
shutil.rmtree(root)

root = ordered_repo()
head0 = sh(root, "git", "rev-parse", "HEAD").stdout
with trace_steps() as (calls, _):
    rc, said = run_integrate("agent/ordered", "--as", "tester")
check("the map pause stops after the gate, before commit or cleanup",
      rc == 0 and calls == MERGE_ORDER and "GATE PASS" in said and "staged, not committed" in said
      and sh(root, "git", "rev-parse", "HEAD").stdout == head0 and os.path.isfile(integrate.state_file(root)), said + str(calls))
with trace_steps() as (calls, _):
    rc, said = run_integrate("--continue", "--as", "tester")
check("continue without a map edit stops at continuation validation",
      rc == 1 and calls == ["load_continuation"] and "aren't changed yet" in said, said + str(calls))
write(root, "ARCHITECTURE.md", "# Map\n\nUpdated after review.\n")
sh(root, "git", "add", "ARCHITECTURE.md")
with trace_steps() as (calls, states):
    rc, said = run_integrate("--continue", "--as", "tester")
check("continue runs only validation and the shared steps after the pause",
      rc == 0 and calls == ["load_continuation"] + FINISH_ORDER and "GATE PASS" not in said
      and len({id(s) for s in states}) == 1 and not os.path.exists(integrate.state_file(root)), said + str(calls))
check("continue includes the reviewed map and records the merge result",
      "Updated after review." in sh(root, "git", "show", "HEAD:ARCHITECTURE.md").stdout
      and "Result (abc1234, merged" in open(os.path.join(root, "docs/decision-log.md")).read(), said)
shutil.rmtree(root)

root = ordered_repo(gate_rc=1)
head0 = sh(root, "git", "rev-parse", "HEAD").stdout
with trace_steps() as (calls, _):
    rc, said = run_integrate("agent/ordered", "--as", "tester")
check("a failed gate stops before the map pause and every finishing step",
      rc == 1 and calls == MERGE_ORDER[:-1] and "GATE FAIL" in said
      and sh(root, "git", "rev-parse", "HEAD").stdout == head0
      and not os.path.exists(integrate.state_file(root)), said + str(calls))
shutil.rmtree(root)

# 8. Live gate progress streaming (H088): progress lines arrive before the gate ends; non-progress lines are held
#    until the failure tail; verdict and the 2000-char failure tail stay as before.
def run_integrate_live(repo_root, args, release_on, release_path):
    env = dict(os.environ, RELEASE=release_path)
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "integrate.py"), *args],
                         cwd=repo_root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
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


root = ordered_repo()
release = os.path.join(root, ".release-pass")
write(root, "tools/gate.sh", """#!/bin/bash
echo "noise before"
echo "gate: quick test started"
echo "quick: parse started"
for ((i=0; i<100; i++)); do [ -f "$RELEASE" ] && break; sleep 0.05; done
if [ ! -f "$RELEASE" ]; then echo "STUB TIMED OUT"; exit 2; fi
echo "noise middle"
echo "quick: parse passed in 1 s"
echo "gate: quick test passed in 1 s"
echo "gate: full test started"
echo "full: viewport suites started"
echo "full: viewport suites passed in 1 s"
echo "gate: full test passed in 1 s"
echo "GATE PASS: stub passed"
""")
os.chmod(os.path.join(root, "tools/gate.sh"), 0o755)
sh(root, "git", "add", "tools/gate.sh"); sh(root, "git", "commit", "-qm", "live gate stub")
rc, lines, before_release, alive = run_integrate_live(
    root, ["agent/ordered", "--as", "tester", "--impact", "fixture"], "quick: parse started", release)
expected_progress = [
    "gate: quick test started",
    "quick: parse started",
    "quick: parse passed in 1 s",
    "gate: quick test passed in 1 s",
    "gate: full test started",
    "full: viewport suites started",
    "full: viewport suites passed in 1 s",
    "gate: full test passed in 1 s",
]
got_progress = [l for l in lines if l.startswith(("gate: ", "quick: ", "full: "))]
check("run_gate relays the first progress line before the gate ends",
      rc == 0 and alive and before_release is not None and "gate: quick test started" in before_release,
      (rc, alive, before_release, lines))
check("run_gate relays gate:, quick: and full: progress lines in order, then says the verdict",
      got_progress == expected_progress and "integrate: GATE PASS: stub passed" in lines
      and lines.index(expected_progress[-1]) < lines.index("integrate: GATE PASS: stub passed"), lines)
check("run_gate does not print non-progress lines live on a passing gate",
      "noise before" not in lines and "noise middle" not in lines, lines)
shutil.rmtree(root)

root = ordered_repo()
release = os.path.join(root, ".release-fail")
write(root, "tools/gate.sh", f"""#!/bin/bash
echo "early-marker-trimmed"
"{sys.executable}" -c 'print("x" * 2100)'
echo "noise before fail"
echo "quick: parse started"
for ((i=0; i<100; i++)); do [ -f "$RELEASE" ] && break; sleep 0.05; done
if [ ! -f "$RELEASE" ]; then echo "STUB TIMED OUT"; exit 2; fi
echo "stderr-detail-line" >&2
echo "quick: parse failed in 1 s"
echo "GATE FAIL: stub failed"
exit 1
""")
os.chmod(os.path.join(root, "tools/gate.sh"), 0o755)
sh(root, "git", "add", "tools/gate.sh"); sh(root, "git", "commit", "-qm", "failing live gate stub")
head0 = sh(root, "git", "rev-parse", "HEAD").stdout
rc, lines, before_release, alive = run_integrate_live(
    root, ["agent/ordered", "--as", "tester", "--impact", "fixture"], "quick: parse started", release)
verdict_idx = lines.index("integrate: GATE FAIL: stub failed") if "integrate: GATE FAIL: stub failed" in lines else -1
tail_text = "\n".join(lines[verdict_idx + 1:]) if verdict_idx >= 0 else ""
check("a failing gate streams progress live without leaking non-progress lines first",
      rc == 1 and alive and before_release is not None
      and "noise before fail" not in before_release and "early-marker-trimmed" not in before_release,
      (rc, alive, before_release, lines))
check("a failing gate says the verdict, prints the last 2000 chars of output, and leaves the merge uncommitted",
      verdict_idx >= 0 and "noise before fail" in tail_text and "stderr-detail-line" in tail_text
      and "early-marker-trimmed" not in tail_text and lines[-1] == "integrate: the merge is left uncommitted"
      and sh(root, "git", "rev-parse", "HEAD").stdout == head0, (verdict_idx, lines[-10:]))
shutil.rmtree(root)

print(f"INTEGRATE TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
raise SystemExit(0 if all(RESULTS) else 1)   # a failed check fails the run, not only its summary
