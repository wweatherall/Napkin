#!/usr/bin/env python3
"""Checks tools/startup.py (run by tools/featuretest.sh) on small inline samples, plus one smoke run of the real
script. Prints PASS/FAIL per check and one summary line: STARTUP TESTS: N passed, M failed."""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import startup as s

RESULTS = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, ok):
    RESULTS.append(ok)
    if not ok or VERBOSE:
        print(("PASS " if ok else "FAIL ") + name)


WT = ("worktree /repo\nHEAD abc\nbranch refs/heads/main\n\n"
      "worktree /tmp/x\nHEAD def\nbranch refs/heads/codex/h037-fit\n\n"
      "worktree /tmp/y\nHEAD 123\ndetached\n")
check("worktrees parse to path and branch, a detached one marked",
      s.parse_worktrees(WT) == [("/repo", "main"), ("/tmp/x", "codex/h037-fit"), ("/tmp/y", "(detached)")])

REFS = ("main|0 0|2026-11-22\nsmall-fixes|0 19|2026-11-21\ncodex/old|0 40|2026-11-20\n"
        "codex/plane|10 100|2026-11-21\nclaude/h036-keys|0 0|2026-11-22\nfeature|3 0|2026-11-22\n"
        "origin|0 16|2026-11-21\norigin/main|0 16|2026-11-21\norigin/codex/plane|10 100|2026-11-21\n"
        "origin/claude/cloud|2 5|2026-11-22\norigin/other|4 0|2026-11-22\n")
refs = s.parse_refs(REFS)
check("ref lines parse to name, ahead, behind, date", refs[3] == ("codex/plane", 10, 100, "2026-11-21"))
shown, hidden = s.agent_branches(refs)
names = [n for n, *_ in shown]
check("branches ahead of main are shown with count and date", ("codex/plane", 10, "2026-11-21") in shown)
check("main, small-fixes and origin/main are never shown", not {"main", "small-fixes", "origin/main"} & set(names))
check("a local branch other than main counts as an agent branch", "feature" in names)
check("a remote copy of a local branch is not shown twice", "origin/codex/plane" not in names)
check("a remote claude/* branch is shown; other remote branches aren't",
      "origin/claude/cloud" in names and "origin/other" not in names)
check("branches with nothing ahead are hidden and counted", hidden == 2 and "codex/old" not in names)
check("a branch an open handoff names but that's gone is reported; a live one (local or origin/) isn't",
      s.gone_branches({"H1.md": "on claude/h043-hide-check and codex/plane, claude/cloud.", "H2.md": "no branch"},
                      ["codex/plane", "origin/claude/cloud"]) == [("H1.md", "claude/h043-hide-check")])

BOARD = ("# Work board\n\n## Jobs\n\n| Job | For | Status | Item | Handoff | Waits for |\n|---|---|---|---|---|---|\n"
         "| H036 | Claude | **Ready** | T75: keys | [H036](x) | |\n"
         "| H037 | Codex | **Ready** | T54: fits | [H037](y) | |\n"
         "| next | either | Queued | T33: small | later | H036 |\n\n"
         "## Notes\n\n- Codex: take H037.\n- Second note.\n\n## After\n\n- not a note\n")
jobs = s.ready_jobs(BOARD, ["main", "codex/h037-fits"])
check("only Ready jobs are listed", [j[0] for j in jobs] == ["H036", "H037"])
check("a branch containing the job ID in lower case claims it", jobs[1][3] == "codex/h037-fits" and jobs[0][3] is None)
check("a job's For and Item are kept", jobs[0][1:3] == ("Claude", "T75: keys"))
check("notes are the Notes section's lines, not the next section's", s.notes(BOARD) == ["- Codex: take H037.", "- Second note."])
check("an empty board gives no jobs and no notes", s.ready_jobs("", []) == [] and s.notes("") == [])

LOG = ("## Decisions\n\n| ID | Decision | Status |\n|---|---|---|\n"
       "| I40 | A push stays tied to a face. " + "x" * 300 + " (Details below.) | Active |\n"
       "| A23 | sync keeps the prefix | Active |\n\n"
       "## Work list\n\n| # | Item | Status | Covers | Result |\n|---|---|---|---|---|\n"
       "| T53 | Plane fits | Done | I40 | ok |\n"
       "| T54 | Refit only changed | In progress | T53, I40, A23, Q99 | assigned |\n\n"
       "## Details\n\n### I40\n\ntext\n")
check("a row is found by its first cell", s.find_row(LOG, "A23").startswith("| A23 |"))
check("an ID that is only a prefix of another doesn't match", s.find_row(LOG, "T5") is None)
check("Covers IDs are read from a Work list row", s.cited_ids(s.find_row(LOG, "T54")) == ["T53", "I40", "A23", "Q99"])
lines, unknown = s.report_ids(LOG, ["T54"])
out = "\n".join(lines)
check("an asked-for row is printed whole", "| T54 | Refit only changed |" in out)
check("each cited row is printed, shortened to ~200 characters",
      "  A23: | A23 |" in out and all(len(l) <= s.SHORT + 60 for l in lines[2:]))
check("a cited (Details below.) row says it has a ### section",
      any(l.startswith("  I40:") and "### section" in l for l in lines))
check("a cited ID missing from the log says so", "  Q99: not found" in out and unknown == [])
lines, unknown = s.report_ids(LOG, ["A23"])
check("a decision row is printed without following citations", len(lines) == 2)
lines, unknown = s.report_ids(LOG, ["T54", "T999"])
check("an unknown ID asked for is reported", unknown == ["T999"] and any("T999: not found" in l for l in lines))

WLOG = ("## Principles\n\n| ID | Principle | Status | Covers | Date |\n|---|---|---|---|---|\n"
        "| G01 | Feel first. | Active | A02 | 2026-11-22 |\n| G14 | Measure twice. | Tentative | I01 | 2026-11-22 |\n\n"
        "## Work list\n\n| # | Item | Status | Covers | Result / next step |\n|---|---|---|---|---|\n"
        "| T65 | Ask on a dropped save | Open | Q19 | After T64; the question's wording is your call. |\n"
        "| T66 | Units | Open | T32 | Units preference: your call. Decided 2026-11-22: I57. |\n"
        "| T25 | AppKit | Parked | I31 | Your call, 2026-11-21: wait for a prototype. |\n"
        "| T67 | Paint key | Open | Q14 | Your call, 2026-11-21: P. |\n"
        "| T68 | Done one | Done | Q1 | your call |\n"
        "| T69 | Plain | Open | Q2 | After T68. |\n")
rows = s.waiting_rows(WLOG)
check("an Open Work list row left as 'your call' is waiting, with its sentence",
      rows[:1] == [("T65", "After T64; the question's wording is your call.")])
check("a 'your call' row with a decision ID after it was answered and isn't listed", "T66" not in [r[0] for r in rows])
check("'Your call, <date>:' records an answer; Parked and Done rows aren't listed", [r[0] for r in rows] == ["T65"])
check("a Tentative principle is waiting; an Active one isn't", s.tentative_principles(WLOG) == [("G14", "Measure twice.")])

HO = {"H060-a.md": "### H060\n\nAuthor: x | Date: d | Status: open | For: Claude\n\nAsk William which key. Then build.\n",
      "H061-b.md": "### H061\n\nAuthor: x | Date: d | Status: open | For: Claude\n\nAsk William which key.\n\n"
                   "Response — Claude: logged as I70 (Option).\n",
      "H062-c.md": "### H062\n\nAuthor: x | Date: d | Status: queued (after H060) | For: Codex\n\nFirst, ask William two"
                   " things.\n\n- William's answers, logged: yes.\n",
      "H063-d.md": "### H063\n\nAuthor: x | Date: d | Status: answered | For: Codex\n\nAsk William.\n",
      "H064-e.md": "### H064\n\nAuthor: x | Date: d | Status: queued (after H060) | For: Codex\n\nNo question.\n"}
check("an open handoff with an unanswered 'Ask William' is waiting, with its sentence",
      s.waiting_handoffs(HO) == [("H060", "Ask William which key.")])
check("a Response naming a logged decision, or a 'William's answers' line, answers it; an answered entry isn't open",
      [h for h, _ in s.waiting_handoffs(HO)] == ["H060"])
WBOARD = "## Notes\n\n- William: say whether to clear the old worktrees.\n- For William: T38's key.\n- Codex: take H046.\n"
check("board notes addressed to William are listed; others aren't",
      s.william_notes(WBOARD) == ["William: say whether to clear the old worktrees.", "For William: T38's key."])
out = s.waiting_on_william(WLOG, HO, WBOARD, True)
check("the section has one line per source, with IDs, and the watch reminder when the lock is held",
      any(l.startswith("  T65 (Work list):") for l in out) and any(l.startswith("  G14 (principle") for l in out)
      and any(l.startswith("  H060 (handoff):") for l in out) and sum("Board note:" in l for l in out) == 2
      and "watch --next" in out[-1])
check("nothing waiting says so; no lock, no reminder", s.waiting_on_william("", {}, "", False) == ["  (nothing)"])

FU = ("# Follow-ups\n\nLeftovers (P26). A line like `- H0NN (<date>): <what>` in prose isn't one.\n\n## Open\n\n"
      "- H060 (2026-11-22): say which key Paint takes\n- H061 (2026-11-23): retire the old flag\n")
check("the follow-ups section lists each open line, without its dash",
      s.follow_up_lines(FU) == ["  H060 (2026-11-22): say which key Paint takes", "  H061 (2026-11-23): retire the old flag"])
check("no open follow-ups (or no file on main) says (none)",
      s.follow_up_lines(FU.split("## Open")[0] + "## Open\n\n(none)\n") == ["  (none)"] and s.follow_up_lines("") == ["  (none)"])

check("parse_args defaults to no role and keeps positional IDs",
      s.parse_args(["T54", "A23"]) == (None, ["T54", "A23"], None))
check("parse_args accepts --role <name> and --role=<name> (case-insensitive) alongside IDs",
      s.parse_args(["--role", "INTEGRATOR", "T54"]) == ("integrator", ["T54"], None)
      and s.parse_args(["T54", "--role=worker"]) == ("worker", ["T54"], None))
check("parse_args rejects a missing or unknown role",
      s.parse_args(["--role"])[2] is not None and "unknown role" in s.parse_args(["--role", "wizard"])[2])

INOTES = {
    "H067-roles.md": "### H067 — Agent roles\n\nAuthor: x | Date: d | Status: open | For: the integrator\n",
    "H131-state.md": "### H131 — Where things stand\n\nAuthor: x | Date: d | Status: open | For: integrator\n",
    "H132-done.md": "### H132 — Old note\n\nAuthor: x | Date: d | Status: answered | For: the integrator\n",
    "H125-job.md": "### H125 — Worker job\n\nAuthor: x | Date: d | Status: open | For: either\n",
}
check("integrator_notes lists only open handoffs addressed to the integrator with their paths",
      s.integrator_notes(INOTES) == [("H067 — Agent roles", "docs/handoff/H067-roles.md"),
                                     ("H131 — Where things stand", "docs/handoff/H131-state.md")])
STATE_TEXT = ("### H131 — Where things stand\n\nAuthor: x | Date: d | Status: open | For: the integrator\n\n"
              "Touches: nothing.\n\nArchive it once read.\n\nPaused before quota.\n")
check("is_state_note spots pre-/clear state notes and ignores design handoffs",
      s.is_state_note("H131-integrator-state.md", "body") and s.is_state_note("H131-note.md", STATE_TEXT)
      and not s.is_state_note("H067-agent-role-system.md", INOTES["H067-roles.md"]))
check("state_note_body strips heading/Author/Touches boilerplate and keeps the note body",
      s.state_note_body(STATE_TEXT) == ["Archive it once read.", "", "Paused before quota."])

pm = s.parse_interrupted_merge({"branch": "gemini/h125-ties", "maps": [["H125", "m"]], "changed": [["H125", "c"]]},
                               "deadbeef123456", "/repo/.git/shopsketch-integrate.json")
check("parse_interrupted_merge reports paused integrate.py merge with reasons and --continue",
      pm and pm["kind"] == "paused" and "map updates (1)" in pm["summary"] and "brief changes (1)" in pm["summary"]
      and "--continue" in pm["action"])
gm = s.parse_interrupted_merge(None, "deadbeef123456", "")
check("parse_interrupted_merge reports raw MERGE_HEAD with no state file",
      gm and gm["kind"] == "git_merge" and "MERGE_HEAD" in gm["summary"])
sm = s.parse_interrupted_merge({"branch": "codex/h090"}, "", "/repo/.git/shopsketch-integrate.json")
check("parse_interrupted_merge reports stale state file when MERGE_HEAD is absent",
      sm and sm["kind"] == "stale_state" and "stale paused-merge state" in sm["summary"])
check("parse_interrupted_merge returns None when clean", s.parse_interrupted_merge(None, "", "") is None)

WENTRIES = {"H125-t60-chains.md": "### H125 — T60 chains\n\nAuthor: x | Date: d | Status: open | For: either\n\n"
                                  "Touches: worker/stock.py, worker/test_chains.py.\n"}
check("worker_job_context finds the assigned job and Touches from branch or worktree folder",
      s.worker_job_context("/repo-jobs/h125", "main", WENTRIES)
      == ("H125", "H125 — T60 chains", "docs/handoff/H125-t60-chains.md", "Touches: worker/stock.py, worker/test_chains.py.")
      and s.worker_job_context("/repo", "gemini/h125-ties", WENTRIES)[0] == "H125"
      and s.worker_job_context("/repo", "main", WENTRIES) is None)

acts = s.integrator_next_actions(
    "gemini-maple", ["H131"], pm,
    [("H125", {"state": "waiting", "label": "H125 asks scope"}),
     ("H128", {"state": "done", "branch": "gemini/h128-loops"}),
     ("H129", {"state": "stale", "branch": "codex/h129-rect", "worktree": "/jobs/h129"})],
    2)
joined_acts = "\n".join(acts)
check("integrator_next_actions keeps authority separate and surfaces merge, waiting, done, stale, combined lock+archive, watch",
      "does not grant authority" in joined_acts and "Interrupted merge:" in joined_acts
      and "ANSWER_A_WORKERS_QUESTION.py H125" in joined_acts and "MERGE_JOB.py gemini/h128-loops" in joined_acts
      and "stale job H129" in joined_acts
      and "HOLD_THE_INTEGRATOR_LOCK.py <session> --william --archive H131 --push" in joined_acts
      and "BypassSandbox: true" in joined_acts and "WAIT_FOR_THE_NEXT_JOB.py" in joined_acts)
plain_acts = "\n".join(s.integrator_next_actions(None, [], None, [], 0))
check("integrator_next_actions omits --william and --archive when lock is free and no state notes exist",
      "HOLD_THE_INTEGRATOR_LOCK.py <session>" in plain_acts and "--william" not in plain_acts and "--archive" not in plain_acts
      and "BypassSandbox: true" in plain_acts)

summary_lines = s.role_summary("gemini-maple", ["H131"], 2, None, in_job_id="H125")
check("role_summary summarizes lock, state note, ready count, merge state and detected job checkout",
      len(summary_lines) == 2 and "gemini-maple" in summary_lines[0] and "H131" in summary_lines[0]
      and "Ready jobs: 2." in summary_lines[0] and "No interrupted merges." in summary_lines[0]
      and "Job checkout detected: H125." in summary_lines[0] and "--role worker" in summary_lines[1]
      and "never takes the lock" in summary_lines[1])

check("role_brief returns checklists for integrator and worker",
      any("docs/integrator.md" in l for l in s.role_brief("integrator"))
      and any("WAIT_FOR_THE_NEXT_JOB.py" in l for l in s.role_brief("integrator"))
      and any("ARCHIVE_A_FINISHED_JOB.py <ID> --push" in l for l in s.role_brief("integrator"))
      and any("BOARD.md" in l for l in s.role_brief("worker"))
      and any("SUBMIT_JOB.py" in l for l in s.role_brief("worker")))

# A generous bound (120 s), not a machine-speed threshold: a hang still fails here, not only under job.py run (P40).
r = subprocess.run([sys.executable, os.path.join(HERE, "startup.py")], capture_output=True, text=True, timeout=120)
check("smoke: the real report runs and has every section plus Summary, Role tip and live Job queue",
      r.returncode == 0 and all(h in r.stdout for h in ("This checkout:", "Worktrees", "Recent main:",
                                                         "Branches with commits", "Ready on the board",
                                                         "Job queue (tools/CHECK_THE_JOB_BOARD.py):",
                                                         "Waiting on William", "Follow-ups (docs/follow-ups.md",
                                                         "Summary:", "Role tip:"))
      and "Job queue: not read" not in r.stdout)
check("smoke: Follow-ups comes after Waiting on William",
      r.stdout.find("Follow-ups (docs/follow-ups.md") > r.stdout.find("Waiting on William"))
r = subprocess.run([sys.executable, os.path.join(HERE, "startup.py"), "--role", "integrator"], capture_output=True, text=True, timeout=120)
check("smoke: --role integrator prints interrupted merges, notes, next actions and checklist with live queue",
      r.returncode == 0 and "Interrupted merges:" in r.stdout
      and "Notes for the integrator (main:docs/handoff/):" in r.stdout
      and "Next actions (read-only briefing; does not take the lock):" in r.stdout
      and "Integrator checklist (docs/integrator.md):" in r.stdout and "Role tip:" not in r.stdout
      and "Job queue (tools/CHECK_THE_JOB_BOARD.py):" in r.stdout and "Job queue: not read" not in r.stdout)
r = subprocess.run([sys.executable, os.path.join(HERE, "startup.py"), "--role", "worker", "T1"], capture_output=True, text=True, timeout=120)
check("smoke: --role worker prints a lean worker brief with live queue and still resolves IDs",
      r.returncode == 0 and "Ready on the board" in r.stdout and "Worker checklist (BOARD.md):" in r.stdout
      and "Job queue (tools/CHECK_THE_JOB_BOARD.py):" in r.stdout and "Job queue: not read" not in r.stdout
      and "== T1" in r.stdout and "Follow-ups (docs/follow-ups.md" not in r.stdout
      and "Waiting on William" not in r.stdout)
r = subprocess.run([sys.executable, os.path.join(HERE, "startup.py"), "--role", "wizard"], capture_output=True, text=True, timeout=120)
check("smoke: an unknown --role exits 1", r.returncode == 1 and "unknown role" in r.stdout)
r = subprocess.run([sys.executable, os.path.join(HERE, "startup.py"), "T1"], capture_output=True, text=True, timeout=120)
check("smoke: asking for T1 prints its item (from its file since H153)", r.returncode == 0 and "== T1" in r.stdout
      and "Mirror fix" in r.stdout)
r = subprocess.run([sys.executable, os.path.join(HERE, "startup.py"), "T99999"], capture_output=True, text=True, timeout=120)
check("smoke: an unknown ID exits 1", r.returncode == 1 and "T99999: not found" in r.stdout)

ARCHIVED = "## Done work\n\n| # | Item | Status | Covers | Result |\n|---|---|---|---|---|\n| T50 | Old item | Done | A23 | ok |\n"
lines, unknown = s.report_ids(LOG, ["T50"], ARCHIVED)
check("an ID only in 03_Past_Decisions/decision-archive.md is found and marked (P23)", not unknown and lines[0] == "== T50" + s.ARCHIVE_NOTE)
check("an archived Work list item's Covers IDs are looked up in the live file", any(l.startswith("  A23: | A23 |") for l in lines))
lines, unknown = s.report_ids(LOG, ["T51"], ARCHIVED)
check("an ID in neither file is unknown", unknown == ["T51"])

ruling_text = (
    "# I34 — Pushing a piece toward another has three snaps.\n\n"
    "Status: Active | Subject: Push/Pull | Principles: G04 | Date: 2026-11-21\n"
    "Replaces / replaced by: —\nWhere in the code: —\n\n"
    "Pushing a piece toward another has three snaps.\n\nWhy: Agreed.\n"
)
rlines, runknown = s.report_ids("", ["I34"], "", read_ruling=lambda i: ruling_text if i == "I34" else None)
check("a named ID's lines come from its ruling file",
      not runknown and rlines[0] == "== I34" and "Pushing a piece toward another has three snaps." in rlines[1])

work_text = (
    "# T147 — Plane fits keep their target.\n\n"
    "Status: Open | Covers: I34\n"
    "Jobs: H150 merged 4bb59a0 · H151 in progress (gemini)\n\n"
    "Plane fits keep their target.\n\n"
    "Result / next step: Your call: pick the snap rule.\n"
)
wlines, wunknown = s.report_ids(
    "", ["T147"], "",
    read_ruling=lambda i: ruling_text if i == "I34" else None,
    read_work=lambda i: work_text if i == "T147" else None,
)
check("a named T item's lines and its Covers rows come from files",
      not wunknown and wlines[0] == "== T147" and "Plane fits keep their target." in wlines[1]
      and any(l.startswith("  I34: Pushing a piece toward another") for l in wlines))
check("a named item's lines include its Jobs line",
      any("Jobs: H150 merged 4bb59a0 · H151 in progress (gemini)" in l for l in wlines))
w_rows = s.waiting_rows("", work_entries={"T147": work_text})
check("a 'your call' item in a file is waiting on William",
      w_rows == [("T147", "Your call: pick the snap rule.")])

# --- Onboarding brief sections (H163) ---
check("parse_ranking sorts table rows by rank regardless of input order",
      s.parse_ranking("| # | Rating | Compared | Principle | |\n|---|---|---|---|---|\n"
                      "| 2 | 1000 | 2 | org U2 | Second rule. |\n"
                      "| 1 | 1050 | 3 | org 02 | First rule. |\n")
      == ["1. First rule.", "2. Second rule."])
check("parse_ranking falls back to plain principle lines when there is no table",
      s.parse_ranking("# Principles\n\nHigher wins when two pull against each other.\n\n"
                      "- Alpha rule.\n- Beta rule.\n")
      == ["- Alpha rule.", "- Beta rule."])

with tempfile.TemporaryDirectory(prefix="startup-h163-") as tmp:
    org = os.path.join(tmp, "comitatus")
    repo = os.path.join(org, "08_Code_Bases", "Shop")
    os.makedirs(os.path.join(org, "07_Org_Chart_and_Roles"))
    os.makedirs(os.path.join(org, "01_Principles"))
    os.makedirs(os.path.join(org, "02_Habits"))
    os.makedirs(os.path.join(org, "09_Tools"))
    os.makedirs(os.path.join(org, "06_To-dos", "waiting_on_William"))
    os.makedirs(os.path.join(org, "06_To-dos", "waiting_on_integrator"))
    os.makedirs(os.path.join(repo, "01_Principles"))
    os.makedirs(os.path.join(repo, "02_Habits"))
    os.makedirs(os.path.join(repo, "tools"))

    open(os.path.join(org, "07_Org_Chart_and_Roles", "coders.md"), "w").write(
        "# Coders\n\nCode solutions and tests.\n")
    open(os.path.join(org, "07_Org_Chart_and_Roles", "integrator.md"), "w").write(
        "# Integrator\n\nReview and merge.\n")
    open(os.path.join(org, "07_Org_Chart_and_Roles", "william.md"), "w").write(
        "# William\n\nDirection and testing.\n")
    open(os.path.join(org, "01_Principles", "ranking.md"), "w").write(
        "| # | Rating | Compared | Principle | |\n|---|---|---|---|---|\n"
        "| 1 | 1050 | 3 | org 02 | Org first. |\n")
    open(os.path.join(repo, "01_Principles", "ranking.md"), "w").write(
        "| # | Rating | Compared | Principle | |\n|---|---|---|---|---|\n"
        "| 1 | 1040 | 2 | shop G01 | Shop first. |\n")
    open(os.path.join(org, "02_Habits", "README.md"), "w").write("# Habits\n\n- `ORG_HABIT.py` — org habit.\n")
    open(os.path.join(repo, "02_Habits", "README.md"), "w").write("# Habits\n\n- `REPO_HABIT.py` — repo habit.\n")
    open(os.path.join(org, "09_Tools", "README.md"), "w").write(
        "# Tools\n\n- `ORG_TOOL.py` — org tool\n  with continuation.\n")
    open(os.path.join(repo, "tools", "README.md"), "w").write("# Tools\n\n- `REPO_TOOL.py` — repo tool.\n")
    open(os.path.join(org, "06_To-dos", "waiting_on_William", "Shop_T1_ASK.md"), "w").write("x")
    open(os.path.join(org, "06_To-dos", "waiting_on_integrator", "Shop_T2_DO.md"), "w").write("x")
    open(os.path.join(org, "06_To-dos", "waiting_on_integrator", "Shop_T3_DO.md"), "w").write("x")

    who_w = "\n".join(s.who_lines("worker", org))
    who_i = "\n".join(s.who_lines("integrator", org))
    check("who_lines strips title and loads coders.md for worker, integrator.md for integrator, plus William",
          "# Coders" not in who_w and "Code solutions and tests." in who_w and "Direction and testing." in who_w
          and "# Integrator" not in who_i and "Review and merge." in who_i and "Direction and testing." in who_i)

    princ = "\n".join(s.principles_lines(org, repo))
    check("principles_lines prints P70 header, Comitatus then code base in order",
          "answer to the organization's (P70)." in princ
          and princ.index("Comitatus:") < princ.index("1. Org first.") < princ.index("Shop:") < princ.index("1. Shop first."))

    hab = "\n".join(s.habits_lines(org, repo))
    tls = "\n".join(s.tools_lines(org, repo))
    check("habits_lines and tools_lines keep comitatus then code base lists including continuations",
          hab.index("ORG_HABIT.py") < hab.index("REPO_HABIT.py")
          and tls.index("ORG_TOOL.py") < tls.index("with continuation.") < tls.index("REPO_TOOL.py"))

    todos = "\n".join(s.org_todos_lines(org))
    check("org_todos_lines counts both queues and lists waiting_on_William filenames",
          "waiting_on_William: 1" in todos and "Shop_T1_ASK.md" in todos and "waiting_on_integrator: 2" in todos)

    check("personal_time_lines gives 1% to worker and 3% to integrator",
          "1%" in "\n".join(s.personal_time_lines("worker"))
          and "3%" in "\n".join(s.personal_time_lines("integrator")))

    outside = os.path.join(tmp, "standalone")
    os.makedirs(outside)
    subprocess.run(["git", "init", "-q"], cwd=outside, check=True)
    _saved_nc = os.environ.pop("NAPKIN_COMITATUS", None)
    try:
        check("missing sources and checkouts outside comitatus are skipped silently",
              s.comitatus_root(outside) == (None, os.path.realpath(outside))
              and s.who_lines("worker", None) == []
              and s.principles_lines(None, outside) == []
              and s.habits_lines(None, outside) == []
              and s.tools_lines(None, outside) == []
              and s.org_todos_lines(None) == [])
    finally:
        if _saved_nc is not None:
            os.environ["NAPKIN_COMITATUS"] = _saved_nc

r_int = subprocess.run([sys.executable, os.path.join(HERE, "startup.py"), "--role", "integrator"],
                       capture_output=True, text=True, timeout=120)
r_wrk = subprocess.run([sys.executable, os.path.join(HERE, "startup.py"), "--role", "worker"],
                       capture_output=True, text=True, timeout=120)
check("smoke: --role integrator has Principles, Habits, Tools, and 3% Personal time",
      r_int.returncode == 0
      and all(h in r_int.stdout for h in ("Principles:", "Habits:", "Tools:", "Personal time:", "3%")))
check("smoke: --role worker has Principles, Habits, Tools, 1% Personal time, and no Organization to-dos",
      r_wrk.returncode == 0
      and all(h in r_wrk.stdout for h in ("Principles:", "Habits:", "Tools:", "Personal time:", "1%"))
      and "Organization to-dos" not in r_wrk.stdout
      and r_wrk.stdout.find("Principles:") < r_wrk.stdout.find("This checkout:")
      and r_wrk.stdout.find("Worker checklist") < r_wrk.stdout.find("Habits:") < r_wrk.stdout.find("Tools:") < r_wrk.stdout.find("Personal time:"))

_cdir = s.s.comitatus_rulings_dir(os.path.dirname(HERE))
if _cdir and os.path.isfile(os.path.join(_cdir, "P16.md")):
    r_p16 = subprocess.run([sys.executable, os.path.join(HERE, "startup.py"), "P16"],
                           capture_output=True, text=True, timeout=120)
    check("smoke: startup.py P16 prints P16 from comitatus when not on Napkin main",
          r_p16.returncode == 0 and "== P16" in r_p16.stdout and "One Claude session is the integrator" in r_p16.stdout)

# --- Integrator Log usage annotation (H190) ---
with tempfile.TemporaryDirectory(prefix="startup-h190-") as tmp:
    sample_slines = [
        'Log (opus-integrator, last 10 lines; WRITE_IN_YOUR_LOG.py opus-integrator "..."):',
        "  2026-11-27 18:54 merged H184",
        "  2026-11-27 19:05 merged H186",
        'Journal (opus-integrator, last 10 lines; WRITE_IN_YOUR_JOURNAL.py opus-integrator "..."):',
        "  2026-11-27 19:00 felt good",
    ]
    annotated = s.annotate_integrator_log_lines(sample_slines, {"2026-11-27 18:54 merged H184": 0.012})
    check("annotate_integrator_log_lines appends [claude 5h -1.2] only to matching Log lines",
          annotated[1] == "  2026-11-27 18:54 merged H184  [claude 5h -1.2]"
          and annotated[2] == "  2026-11-27 19:05 merged H186"
          and annotated[4] == "  2026-11-27 19:00 felt good")

    # Absent tool fails open
    check("fetch_log_claude_5h returns {} when tool is absent",
          s.fetch_log_claude_5h(tmp, "opus-integrator", usage_tool=os.path.join(tmp, "missing.py")) == {})

    # Raising/failing tool fails open
    bad_tool = os.path.join(tmp, "bad_tool.py")
    open(bad_tool, "w").write("import sys; sys.exit(1)\n")
    check("fetch_log_claude_5h returns {} when tool exits non-zero",
          s.fetch_log_claude_5h(tmp, "opus-integrator", usage_tool=bad_tool) == {})

    # Working tool returns claude-5h map
    good_tool = os.path.join(tmp, "good_tool.py")
    open(good_tool, "w").write(
        'import json; print(json.dumps({"rows": [{"raw": "2026-11-27 18:54 merged H184", "claude": {"claude-5h": 0.012}}]}))\n'
    )
    check("fetch_log_claude_5h parses claude-5h from tool --json output",
          s.fetch_log_claude_5h(tmp, "opus-integrator", usage_tool=good_tool)
          == {"2026-11-27 18:54 merged H184": 0.012})

print(f"STARTUP TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
sys.exit(0 if all(RESULTS) else 1)
