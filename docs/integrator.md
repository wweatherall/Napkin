# The integrator

What only the integrator does. Workers (every other session, Claude or Codex) don't need this page: CLAUDE.md
and BOARD.md are theirs. The shared rules are in BOARD.md's worker steps (Touches, placeholder IDs,
Architecture: lines, the response) and CLAUDE.md (commit trailers); this page says what the integrator does with them.

## The role and the lock
- One Claude session is the integrator (P16), and it holds the lock (`python3 tools/integrator.py status`, P19).
  Start with `python3 02_Habits/REMEMBER_WHO_YOU_ARE.py --role integrator` and this page only — skip `CLAUDE.md` and `BOARD.md` upfront
  (`REMEMBER_WHO_YOU_ARE.py` carries who you are, the principles, the board, pre-/clear state notes, `06_To-dos` counts, habits, tools, and personal time).
  You're the integrator only if William said so in this session: take the lock (and archive, commit and push any
  pre-/clear state note in one step) with
  `python3 tools/HOLD_THE_INTEGRATOR_LOCK.py <your session name> --william [--archive <ID> --push]` (drop `--william` if the
  lock is free; refused if another holds it without `--william`, P19; standalone archiving is
  `python3 tools/ARCHIVE_A_FINISHED_JOB.py <ID> --push`, which also tidies `docs/agent-handoff.md`). Commands that write `.git/`, push, launch Terminal windows, or
  read transcripts outside the workspace (`HOLD_THE_INTEGRATOR_LOCK.py`, `ARCHIVE_A_FINISHED_JOB.py --push`, `MERGE_JOB.py`,
  `osascript` worker launches, and `../../09_Tools/MEASURE_TOKEN_USE.py`) require running outside the sandbox (`BypassSandbox: true`).
- It keeps BOARD.md (nobody else edits it), assigns jobs, reviews, merges into main and pushes without asking once
  review and tests pass (P16, P49), and pushes verified integrator commits on main directly. Other sessions never
  merge or push.

## The queue watch
- No timed check-ins (P39): run `python3 tools/WAIT_FOR_THE_NEXT_JOB.py` in the background (it flushes stdout on every
  event and works read-only if `.git/` is sandboxed; no Monitor needed); it wakes you
  once on the first new worker/queue event (a job done, a job stale: its deadline passed, check its branch and worktree; a
  worker waiting on William; the queue empty while a worker waits on `GET_A_JOB.py --wait`: check in with William — self-triggered
  `returned` events are ignored by `--next` and reported only by `--once`). Start
  it again after each. After a context clear, re-arm it.
- A worker's question (T114) shows as `waiting: H0NN asks the integrator (scope): <q>` or `waiting: H0NN asks
  William: <q>`. Answer a scope question with `python3 tools/ANSWER_A_WORKERS_QUESTION.py H0NN "<text>"`; relay William's answer
  with `--from william` (he can run it himself). The worker's background `wait` prints it; answers sent before
  it reads them arrive together, in recorded order (P47).
- `python3 tools/CHECK_THE_JOB_BOARD.py` shows the queue; `python3 tools/REBUILD_THE_JOB_BOARD.py` rebuilds the board's job table (the
  commit hook does it on main).
- **The hopper** (`Pace: one at a time` in `BOARD.md` under `Order:`): start the hopper once in its own Terminal
  window with `python3 tools/RUN_THE_HOPPER.py --window` (outside the sandbox; it runs `--forever` and survives a
  context clear, and a pid file in `.git/` refuses a second `--forever` hopper). After each start-up or clear, run
  `python3 tools/WAIT_FOR_THE_HOPPER.py` in the background: it launches nothing and wakes you when all work is paused
  (nothing `in progress`, no launch pending, and nothing takeable, with at least one job submitted or waiting on a
  question; stale jobs and launch failures still wake at once), with no need to restart the hopper after a clear.
  Questions don't hold the queue (P74): a waiting worker idles while the hopper launches the next takeable job, and
  stacks overlapping Ready jobs onto `done` branches (`base:`). A board with no Pace line runs one at a time (P75). Leave the integrator running or close it: either way,
  when all work pauses, the hopper wakes a running `WAIT_FOR_THE_HOPPER.py` or starts a new integrator with William's
  standing permission (`launch.py integrator`, P74). When the batch is submitted, merge all `done` jobs together with
  `python3 tools/MERGE_THE_BATCH.py [--push] [--yes]` (shows all review pauses together first, takes one `--continue`,
  runs the gate once, and resets `main` if the gate fails).
- Spinning up a worker window: `python3 tools/LAUNCH_A_WORKER.py <gemini|claude|codex> [--model M]` (T134; outside the sandbox;
  tell William) opens it with its start-up brief already in the first message; `--dry-run` shows the command. The
  commands it runs, for reference:
- Spinning up a Gemini worker window (tell William; run outside sandbox / `BypassSandbox: true`): run
  `osascript -e 'tell application "Terminal" to do script "cd /Users/Will/Sites/comitatus/08_Code_Bases/Napkin && agy --model gemini-4-hydrogen-medium -i \"Gemini go! Check the board.\""'`
  (models: `gemini-4-hydrogen-medium` for standard jobs, `gemini-4-neon-medium` when asked for Neon; `agy models` lists all).
- Spinning up a Claude worker window (only when William asks; tell him; outside sandbox): run
  `osascript -e 'tell application "Terminal" to do script "cd /Users/Will/Sites/comitatus/08_Code_Bases/Napkin && claude --model sonnet --effort medium --add-dir /Users/Will/Sites/comitatus/08_Code_Bases/.worktrees/Napkin --remote-control H0NN-worker \"You are a worker. Check the board.\""'`
- Your Log and Journal (T134): `python3 tools/WRITE_IN_YOUR_LOG.py "<line>"` (or `WRITE_IN_YOUR_LOG.py opus-integrator "<line>"`)
  adds a dated line to your Log, `comitatus/04_Personal_Space/opus-integrator/Log.md` (what you did; `job.py` and
  `integrate.py` add their own lines); `python3 tools/WRITE_IN_YOUR_JOURNAL.py opus-integrator "<line>"` adds to
  your Journal (about you, not the work: how the job felt, written in the first person, so the next one of you
  remembers who they are), and your space has `Creative_Expression/`, `Ideas/` and `Code_Experiments/` for your own
  files. `02_Habits/REMEMBER_WHO_YOU_ARE.py --role integrator` prints the last ten lines of each, so no pre-/clear
  shutdown commit is needed.
- Passive job usage (T117, T126): `job.py` (`take`, `done`, `return`) and `integrate.py` (`merge`) call
  `../../09_Tools/MEASURE_TOKEN_USE.py` fail-open, appending snapshots to untracked `.git/shopsketch-usage.jsonl`. Inspect (outside
  sandbox / `BypassSandbox: true` so `~/.gemini/antigravity-cli/brain` and `~/.claude/projects` are readable) with
  `python3 ../../09_Tools/MEASURE_TOKEN_USE.py orient` (startup benchmark), `bench` (worker + integrator summary with 5h % estimates),
  `viz` (`--solo --sort burn`, `--job <H0NN>`), `report --only-measured`, `overhead`, `compare`, or
  `holes <H0NN>` (Claude & AGY/Gemini transcripts).
  Codex job tokens and 5-hour and weekly quota come from `~/.codex/sessions` and appear in `report --all-agents`.

## Review and merge
- Review every done job (Codex's `codex/*` branches too). Read each `Changed from the brief:` line first (P44):
  accept it, or return the job; one that changes what William would notice goes to him (`integrate.py` also stops
  with the merge staged when any response has one, prints them under "for you now:", and records them in the merge
  commit on `--continue`; `--yes` doesn't skip this stop). Check the response's `Architecture:` lines (`owns`,
  `uses`, free text) against the code to confirm they're true (P32): `integrate.py` works out added/removed files,
  changed headers, and added/removed dependencies from the maps after the gate passes, and stops if any added file
  lacks an `owns` line or any added dependency lacks a `uses` line. For a brief with a "What can fail" section, check that each case
  listed there has its named check, and that the check fails without the change where it can (P42). Merge what's good with
  `python3 tools/MERGE_JOB.py <branch> --as <name> --push --yes` (P20, P49). It runs the gate, `tools/TEST_BEFORE_MERGING.sh` (P18; when only tools, hooks, docs or top-level guides changed, it runs parse and `tools-*` feature tests and skips viewport, worker and full tests; `--full` or `GATE_FULL=1` forces everything); flags
  files the branch changed outside its job's Touches list; renumbers a PROTOCOL_VERSION bump on top if main moved
  on meanwhile (A35); removes the job's worktree and branch, marks it merged, records Results and pushes `main` without
  stopping (drop `--yes` if you ever want to stop before pushing; `--yes` never skips P28/P44 pauses).
- Put one that fails review or the gate back with `python3 tools/RETURN_JOB.py <id> "<notes>"`; hand a job to another agent (moving its worktree into `../.worktrees/<checkout>/` if needed, P63) with `python3 tools/job.py reassign <id> --to claude|codex|gemini ["<notes>"]`.
- Placeholder IDs (T74): integrate.py runs `tools/number_ids.py` at merge, giving each I-new-N, T-new-N, H-new-N
  the next free number. It numbers only placeholders that are IDs (a log row, a handoff entry's file or heading, and
  references to them); any other is left and reported as "not numbered: <file>:<line>" (H073). Jobs you write on
  main get numbers the same way: run `python3 tools/NUMBER_A_NEW_ID.py`
  (`--dry-run` to look first) before committing.
- Codex records William's decisions in the log itself (P09, AGENTS.md). When integrating its branch, carry over
  only the rows it added or superseded: its copy of the rest may be older than main's.
- Results (T91, P17): integrate.py commits each response's `Result:` line to its Work list file (`03_Past_Decisions/work/<ID>.md`) and prints one short line per item plus the commit's oneline; a response without
  one is yours to record. Work list statuses move themselves (`On the board (<IDs>)` while jobs exist, `Open` when linked jobs finish with `"step merged (H0NN)"` in the result; it goes `Done` only when the brief says `Completes: T<n>` or `--status T<n>=Done` is given). If a merge stops for a gate failure, fix it and run `python3 tools/MERGE_JOB.py --continue --regate --as <name> [--push --yes]` to re-run the gate and finish; if a merge was finished outside `integrate.py`, run `python3 tools/job.py merged <ID>` to mark it merged in the queue. Follow-ups (P26): it copies `Follow-up:` lines into docs/follow-ups.md and prints
  `For the integrator:` lines under "for you now:"; clear a follow-up in the commit that does it.
- Small fixes (P22): merge and push the standing `small-fixes` (and `codex/small-fixes`) branch when the gate
  passes, without asking; list the fixes for William at the end of the session.

## The map (P28)
- `ARCHITECTURE.md` and `docs/protocol.md` are yours. A job with `Architecture:` lines stops at merge with the
  merge staged and prints them: write them in (the reviewer checks prose against code), then
  `MERGE_JOB.py --continue --as <name> --push --yes`.
- On main the map changes in the same commit as the code. The PR check (`tools/check_architecture.py --range`,
  read as a branch) is an additional omission detector, not a replacement for review.

## Writing jobs
- **Full briefs only on `BOARD.md`**: when taking a Work list item off `06_To-dos` to turn into jobs, run `python3 tools/PICK_UP_A_TO_DO.py T<n>` first. Every handoff entry on the board (whether `open` or `queued (after H0NN)`) must be a complete, ready-to-run brief (`Today`, `Reading path`, `Request`, `Touches`, `Checks`) so H146's auto-unblock works hands-free; write all of an item's jobs in one commit (the second as `queued (after H0NN)`), or if one merges before the next is written, it returns to `Open` with `"step merged (H0NN)"` in its result (a job's last step says `Completes: T<n>` to mark it `Done`; add `Item: T<n>` if the heading doesn't name it); partial ideas and unexpanded follow-ons stay in the Work list (`03_Past_Decisions/decision-log.md`) until ready for a full brief.
- A job adding a tool or an op also lists the places that pin them (H130 asked for them one by one):
  `viewport/keys.gd`, `main.gd` `redo`, `tool_context.gd` and `test_tool_context.gd`, `test_tools.gd`,
  `tools/push_tool.gd`, `tools/CLAUDE.md`, `worker/scenario/99_op_registry.py`.
- **Find callers before finalizing `Touches`**: when a brief changes a tool's hotkey, input mode, op schema, or function contract, run `python3 tools/dependency_map.py touches <file>:<function> [...]` (H174): it prints a ready Touches line from qualified calls, tests on their own, and lists calls it can't resolve for you to check by hand; `callers <file>:<function>` shows each call site. docs/dependency-map.md says which files use which.
- Write the next jobs as handoff entries (a Status of open is Ready; "queued (after H0NN)" waits), each with its
  Touches list, and keep the board's Order line. Before marking one Ready, compare its Touches with every Ready or
  claimed job's: two whose lists overlap don't run at once (tell William before starting one that does). A
  shared file named with backticked functions after it (`viewport/main.gd (`redo`)`) overlaps only where the
  names meet (P45; the tools check it once T112 is built, until then compare by eye).
- A job meant to share files with another (a trial that merges that job's branch first, like H098 on H093) says
  `| Builds on: H0NN` in its Author line: the queue then doesn't hold it back for that overlap.
- The shared hot spots (the decision log's indexes, the handoff, viewport/main.gd, the map) stay small edits
  made once the work is done.
- A job touching saving, reloading or the worker link gets a "What can fail" section in its brief (P42; the
  entry template has it): you write it, from reading the code, since you aren't the builder.
- A follow-up a job takes on: clear its line from docs/follow-ups.md yourself when you write the job (the brief names
  it), so jobs don't all list that file and overlap (H148, H149). If a worker must clear one, it goes on Touches and in
  the code commit, before the quick test: `job.py done` reuses a pass only across commits that change the handoff (H091).
- Workers' code commits often lack the `Architecture-Impact:` line (H149): integrate.py then stops; check it and give
  `--impact "none - <reason>"` on `--continue`.
- Every rule in a brief says what it's for, in a clause: the invariant it keeps or the case it prevents (P44).
  Before writing a rule that sets one value of a linked pair or group (two angles, a range, a count and its
  list), check the state it leaves the others in. The worker may depart from a rule whose letter defeats its
  purpose, with a `Changed from the brief:` line.
- When a job's blocker merges, recheck its brief against the code before opening it: the blocker may have
  rewritten what the brief describes (H094 and H108 both needed updating after H093). Re-date its "Today", fix what
  moved, and add the blocker's new names to its Touches.
- Make a brief exact: its scope, the exact wording of any message, the cases that must still work (H076 is the
  model; workers said its precision let them build it without guessing). Check every claim it makes about how
  the code works today against the code before marking it Ready: H077's brief stated an order of steps opposite
  to integrate.py's, and the worker had to choose between "no change in behaviour" and the brief.
- A brief whose job has a tricky part gets a `Reading path:` line: the functions to read, in order, to see the
  whole lifetime of what the job moves, and who owns what (T107, dropped in favour of this; H083 is the model).

## Traps seen at merge
- A paused merge (`--continue`) accepts changes only to ARCHITECTURE.md and docs/protocol.md. Folder-guide
  updates a response asks for go in a commit of their own after the merge.
- A branch started from an older main that touches files main changed since: merge main into it in a scratch
  worktree first and integrate that.
- Two jobs that each bump PROTOCOL_VERSION to the same number merge silently: bump the later one by one (A35).
- A merge that brings a new version of a tool integrate.py imports (number_ids, job) runs the old one for that
  merge: check its effect.
- `job.py take` with no job id takes the next Ready job for this session: an integrator never runs it.

