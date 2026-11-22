### H053 — T91: integrate.py drafts the Work list result and the board

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H056) | For: Claude

References: T91, P16, P17 (workers put their result in the handoff; the integrator copies it to the Work list), P20
(integrate.py), P14 (BOARD.md), docs/agent-handoff.md (the response rules), AGENTS.md (Codex's copy of them).

Touches: tools/integrate.py, a new tools/test_bookkeeping.py (don't add it to the feature-test script: H049 owns
it; give the line in your response), docs/agent-handoff.md (the rules section only: one line on the Result line),
AGENTS.md and CLAUDE.md (the same line, kept in step), BOARD.md's integrator section (one line).

Request: today integrate.py finishes with "left for you: the Work list result and BOARD.md". Instead: (1) define one
line a response must carry, e.g. "Result: <commit>; <tests>; <what changed>", and add it to the handoff rules; (2) at
merge, append "Result (<commit>, merged <merge>): ..." to the item's Work list row (the T<n> from --status), and move
the job's board row to "Done since ..." (remove the row, add "H0NN (T<n>)" to the list, drop Notes lines naming
it); (3) show the two diffs and stop before the push for the integrator to look (a --yes to go on); a response with
no Result line leaves both for the integrator as today and says so. Checks: sample handoff + log + board in, the
three edits out; the missing-Result case; an already-recorded result isn't added twice. Run integrate.py's own
tests and the quick test; no merge of a real branch needed.
