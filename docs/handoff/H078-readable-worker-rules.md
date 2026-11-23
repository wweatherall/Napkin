### H078 — T104: the worker's instructions, cheap to read

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: Claude

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
