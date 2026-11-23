### H078 — T104: the worker's instructions, cheap to read

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: Claude

References: T104, P14 (the board), P24, P37, P40, H070 (the last trim of CLAUDE.md and AGENTS.md). From a
worker's feedback, 2026-11-22: "The rules are thorough but dense, and full of IDs (P22, T74, H060) that you have to
look up to follow. For a small tooling job, the instructions took more reading than the code did." William: do what
you think best.

Touches: BOARD.md (only its sections above "## Jobs": the intro and "If you're not the integrator"; this job may
edit them), CLAUDE.md (only "Working with William" and "Working with Codex (ChatGPT) and other sessions"),
AGENTS.md, docs/agent-handoff.md (only its rules section at the top, above the open list). Not docs/integrator.md,
the decision log's rules or the folder guides.

Request: a worker should get from "check the board" to working on its job by reading the board's worker steps
and the one job entry, with nothing to look up. Rewrite for that reader:
- Plain words first: each step says what to do and the command, in a sentence a new reader follows. An ID appears
  only as a trailing "why" reference in parentheses, never as the thing the sentence depends on ("Use the
  main checkout only for reading (P25)", not "per P25").
- One place per rule: the worker's steps live in BOARD.md; CLAUDE.md and AGENTS.md say "check the board" and keep
  only what every session needs before it (startup, commit trailers, where scratch files go, who William is);
  docs/agent-handoff.md's rules keep only how to write an entry. Remove repeats rather than rewording them.
- Every rule kept: list in your response each rule you moved or merged, and where it lives now, so the integrator
  can check nothing was lost. A rule you think is no longer needed: keep it and say so in a Follow-up line; don't
  drop it.
- A budget: the worker's path (BOARD.md above "## Jobs" + AGENTS.md, or BOARD.md above "## Jobs" + CLAUDE.md's two
  sections) about half its word count today (BOARD.md 637, CLAUDE.md 1768, AGENTS.md 368 words in all, 2026-11-22);
  give the before and after counts.
- Mention the new habit in the steps: every shell command starts in the main checkout, so `cd` into the job's
  worktree in each command (T102 adds a guard for the tests, H076).
Checks: tools/test_job.py and tools/test_integrate.py still pass (they build boards of their own; the board's
Order line and "## Jobs" table must keep their form); the quick test, then the gate. Then read your own BOARD.md
cold, as a worker would, and say in the response what you'd still have had to look up. End your response with a
Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.

Response — Claude (worker), 2026-11-22:

Branch `claude/h078-readable-worker-rules`, commit a31a7fb (text) and this response. Files: BOARD.md (above
"## Jobs" only), CLAUDE.md ("Working with William" and "Working with Codex" only), AGENTS.md (rewritten),
docs/agent-handoff.md (its rules section, now "How to write an entry"). No code, no decision rows.

Word counts (words split on whitespace; BOARD.md above "## Jobs"; CLAUDE.md's two sections), before → after:
BOARD.md 494 → 431; CLAUDE.md's two sections 808 → 322; AGENTS.md 368 → 198; agent-handoff rules 583 → 312.
Worker's path: BOARD + AGENTS 862 → 629 (73%); BOARD + CLAUDE 1302 → 753 (58%). The Claude path meets the
budget near enough; the Codex path doesn't: BOARD.md now carries every step of a job (it gained rules from
the other three files), and AGENTS.md has to repeat CLAUDE.md's session rules for a reader who doesn't read
CLAUDE.md. Getting further would mean dropping rules, which the job forbids.

Verified: tools/test_job.py 96/0, tools/test_integrate.py 38/0, test_bookkeeping 14/0, test_number_ids 43/0,
test_follow_ups 23/0, test_check_architecture OK (all run in the worktree); quick test: see the Result line.
The Order line and the "## Jobs" table keep their form.

Where each rule lives now (B = BOARD.md worker steps, C = CLAUDE.md, A = AGENTS.md, H = agent-handoff rules):
- CLAUDE "Working with William": one item at a time, say which, files carry state → C (kept). Result line at
  the end of the handoff, integrate.py copies it (P17, T91) → B6. Each item on its own branch, commit when tests
  pass → B1 (job.py makes the branch), B4. Integrator merges/pushes, others never (P16) → B intro, C. Quick test
  after every change → B4; full test on failure / before a merge, a quick-test step per feature → CLAUDE.md
  "## Tests" already says both (repeat removed). Behaviour choices, one question, recommendation, log → C, A.
  Finish before the next; one job a session (P37) → C, B7. "Handoff note if Codex is affected" → C ("when you
  leave Codex something, tell William"). Tests are memory → C. Small fixes light path (P22) → C, A (codex
  branch). FreeCAD 1.1.4, AppKit waits → C.
- CLAUDE "Working with Codex": integrator / lock / integrator.md; workers follow BOARD; AGENTS in step → C.
  startup.py; nothing notifies; tell William → C, A. agent-handoff.md, docs/handoff/, handoff.py archive → H
  (C, A point there). Touches; overlapping jobs don't run at once → B3 (job.py enforces it, B1), H (the queue
  checks Touches); "tell William before starting one that overlaps" → docs/integrator.md already has it.
  Hot spots small edits at the end → B3. Placeholder IDs; change only rows your job adds/supersedes → B3, H.
  ARCHITECTURE.md / protocol.md the integrator's; Architecture: lines; PROTOCOL_VERSION bump (A35) → B3.
  Commit hook and Architecture-Impact trailers → C, A. scratch/ (P25) → C, A. Follow-up / For the integrator
  lines (P26) → B6. Save context, grep by ID, read by section → C.
- BOARD (old): integrator keeps it, nobody else edits, table built from the queue → B intro; "the integrator
  keeps the Order line" → docs/integrator.md already ("keep the board's Order line"). Take, returned job first,
  take --wait, 20 min then tell William → B1. Notes → B2. job.py run, 10 min, HUNG, fix it yourself, job.py check,
  no timer, beats and the 30-minute deadline → B4 (HUNG's exit code 124 dropped from the text: job.py prints it).
  job.py wait → B5. Response contents, Result, Status answered, commit → B6. job.py done and what it checks,
  tell William, stop, one job a session, don't take the lock → B7. Integrator section → one line.
- AGENTS (old): read CLAUDE.md, folder guides apply, documentation-ownership pointer → A. startup.py (with an ID)
  → A. Read agent-handoff.md and the open entries for Codex → A points to H; job.py take prints the job's entry.
  git log / git branch → A. Read the decision log as CLAUDE.md says; log.py add; Active decisions govern → A
  (log.py add), C's first section (unchanged). Check the board with --as codex, branch name, nothing Ready and
  can't wait → A. Only the job's worktree, never switch branches in the main checkout → A, B intro. Touches;
  William can authorize a wider scope → B3 ("ask first"). Merge/push only when William asks → A. One job a
  session → B7. Merge main daily → A. Record every William choice as its own row; merge main before editing the
  log → A, B3. List placeholder IDs in the response → B6 ("IDs you added"). Date, sign, decision IDs,
  verification, Architecture: lines, Status → B6. Archive resolved entries → H. Light path on codex/small-fixes
  → A. Unresolved questions in the handoff and in chat → B5, B6 ("open questions"). Nothing notifies Claude,
  tell William → A.
- agent-handoff rules: every rule kept in H except three moved to B: the Result line format (B6), Follow-up /
  For the integrator lines (B6) and take/done (B1, B7); H points to BOARD.md for how a job is answered.

Read cold, as a worker: BOARD.md gets me from "check the board" to working with nothing to look up for the
steps. Still to look up: what "watched code" is for the Architecture-Impact trailer (CLAUDE.md doesn't say;
tools/check_architecture.py knows), `log.py add`'s arguments (it prints its usage with none), and what the
gate is (CLAUDE.md "## Tests"). The trailing IDs never need following to act.

Follow-up: docs/agent-handoff.md's "Jobs, round 1" section (below the open list, outside this job's Touches)
repeats the old rules and is two days stale; archive or delete it.
Follow-up: AGENTS.md's `git log --oneline -15 main` / `git branch -a` step repeats what startup.py already
prints (recent main, branches with new commits); kept as asked, probably no longer needed.
Follow-up: say in CLAUDE.md what "watched code" is (which paths the architecture check watches), so a worker
can tell which trailer a commit needs.
For the integrator: docs/integrator.md's opening says the shared rules (Touches, placeholder IDs, Architecture:
lines) are in CLAUDE.md's "Working with Codex" section; they are now in BOARD.md's worker steps (step 3) and
docs/agent-handoff.md. Update that sentence (outside this job's Touches).

Result: a31a7fb; job 96/0, integrate 38/0, quick 240/0, gate PASS; BOARD.md's worker steps in plain words with every step of a job, CLAUDE.md and AGENTS.md cut to what a session needs before the board, agent-handoff.md to how to write an entry
