### H053 — T91: integrate.py drafts the Work list result and the board

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: Claude

References: T91, P16, P17 (workers put their result in the handoff; the integrator copies it to the Work list), P20
(integrate.py), P14 (BOARD.md), docs/agent-handoff.md (the response rules), AGENTS.md (Codex's copy of them).

Touches: tools/integrate.py, a new tools/test_bookkeeping.py (don't add it to the feature-test script: H049 owns
it; give the line in your response), docs/agent-handoff.md (the rules section only: one line on the Result line),
AGENTS.md and CLAUDE.md (the same line, kept in step), BOARD.md's integrator section (one line).

Changed 2026-11-22: the board's job table and moving a job to Done are now H058's (the job queue, P24); this job
keeps the Work list result. Request: today integrate.py finishes with "left for you: the Work list result and BOARD.md". Instead: (1) define one
line a response must carry, e.g. "Result: <commit>; <tests>; <what changed>", and add it to the handoff rules; (2) at
merge, append "Result (<commit>, merged <merge>): ..." to the item's Work list row (the T<n> from --status), and move
the job's board row to "Done since ..." (remove the row, add "H0NN (T<n>)" to the list, drop Notes lines naming
it); (3) show the two diffs and stop before the push for the integrator to look (a --yes to go on); a response with
no Result line leaves both for the integrator as today and says so. Checks: sample handoff + log + board in, the
three edits out; the missing-Result case; an already-recorded result isn't added twice. Run integrate.py's own
tests and the quick test; no merge of a real branch needed.

Response (Claude worker, 2026-11-22): branch claude/h053-t91-merge-bookkeeping, commit e507c6c.
- The line: a response ends with `Result: <commit>; <tests>; <what changed>` (rule added to docs/agent-handoff.md,
  AGENTS.md, CLAUDE.md, and one line in BOARD.md's integrator section).
- integrate.py step 8: for each answered entry it reads the newest Result line (before archiving the entry), finds
  the item (the --status T<n> its heading names, else the only --status, else the heading's T<n>), and after the
  merge commit appends `Result (<commit>, merged <merge>): <tests>; <what changed>.` to the row, in the live log or
  the archive (a --status Done row has moved there), as its own commit "T<n> (H0NN): Work list result, merged
  <merge>"; it prints the word diff. With --push it stops before pushing (says how to amend and push) unless --yes.
  No Result line or no item: nothing drafted, "left for you: the Work list result of H0NN (...)", and --push goes on
  as before. A row that already has `Result (<commit>` isn't added to again.
- The board half: dropped, as the 2026-11-22 change to this job says (H058's queue rebuilds the table).
- Tests: tools/test_bookkeeping.py 14/14 (parse, item choice, the row edit and its commit, the shown diff, --push
  stopping, Done into the archive, not twice, unknown item, the missing-Result case); tools/test_integrate.py 28/28;
  tools/quicktest.sh passed (QUICK 208/0, all feature tests). For the feature-test script (H049's), one line:
  `python3 tools/test_bookkeeping.py` (summary `BOOKKEEPING TESTS: N passed, M failed`).
- Architecture: no sections changed (ARCHITECTURE.md doesn't describe integrate.py).
- Open: `job.py done` could warn when a response has no Result line (job.py isn't in my Touches); BOARD.md's worker
  step 5 could name the line too (only its integrator section was mine).

Result: e507c6c; tools/test_bookkeeping.py 14/14, test_integrate.py 28/28, quick test passed; integrate.py appends a response's Result line to its Work list row in its own commit and stops before --push without --yes
