### H060 — T97: follow-ups land on the integrator's list

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: Claude

References: P26 (William's call, 2026-11-22), T91 (H053: integrate.py already reads a response's "Result:" line;
follow its pattern: tools/integrate.py RESULT and step 8), T93 (startup.py's "Waiting on William"), P17, P24.

Touches: tools/integrate.py, tools/startup.py and tools/test_startup.py, a new tools/test_follow_ups.py (give its
feature-test line in your response: H057 owns that script), docs/follow-ups.md (new), docs/agent-handoff.md (its
rules section), AGENTS.md (the worker steps). Not CLAUDE.md (H057) or BOARD.md (the integrator's): give their lines
in your response.

Request: build P26.
1. In a response, each leftover is its own line `Follow-up: <what>` and each merge instruction its own line
   `For the integrator: <what>` (a leading "- " allowed, like Result:). Add the rule beside the Result line's.
2. At merge, before the entry is archived: integrate.py appends each Follow-up line to docs/follow-ups.md as
   `- <H0NN> (<date>): <what>` in the merge commit (a line already there isn't added twice), and prints the
   "For the integrator" lines after the merge, under "for you now:", before "left for you".
3. docs/follow-ups.md: a short header (what it is; the integrator removes a line in the commit that does it or
   turns it into a Work list item), then the open lines.
4. startup.py: a "Follow-ups (docs/follow-ups.md, from main)" section listing the open lines, after "Waiting on
   William"; "(none)" when empty.
Checks: lines parsed with and without "- "; copied once; printed instructions; a response with neither; startup's
section with lines and empty. Quick test, then the gate. End your response with a Result line, and use Follow-up
lines for anything you leave.
