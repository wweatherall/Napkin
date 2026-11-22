### H060 — T97: follow-ups land on the integrator's list

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: Claude

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

Response — Claude (worker, 2026-11-22): built P26 on branch claude/h060-t97-follow-ups, commit 5ae4845.
- tools/integrate.py: `follow_ups()` / `for_integrator()` read `Follow-up: <what>` and `For the integrator: <what>`
  lines (a leading "- " allowed, at line start only, like RESULT). Step 9: before the entries are archived, each
  follow-up is appended to docs/follow-ups.md as `- <H0NN> (<date>): <what>` and staged into the merge commit
  (`add_follow_ups`; the same entry and text isn't added twice, whatever its date; a missing file is made with its
  header). After the merge commit and the Result draft, the instructions print under "for you now:", before "left
  for you". A response with neither changes nothing.
- docs/follow-ups.md (new): header (what it is; the integrator removes a line in the commit that does it or turns
  it into a Work list item), then "## Open" with "(none)".
- tools/startup.py: "Follow-ups (docs/follow-ups.md, from main):" after "Waiting on William"; "(none)" when empty
  or missing on main.
- Rules: docs/agent-handoff.md (beside the Result line's rule) and AGENTS.md (the "When it's done" step).
- Decision log: P26's "Where in the code" now names the code and the test (was "Not built: T97").
- Tests: tools/test_follow_ups.py 11/11 (parsing with and without "- "; copied once, including a line already on
  main; instructions printed in place; a response with neither); tools/test_startup.py 41/41 (section with lines
  and empty, smoke order). test_bookkeeping 14/14, test_integrate 28/28. Quick test passed on 5ae4845; gate passed.
- No ARCHITECTURE.md change (tooling only). No placeholders.

For the integrator: add tools/test_follow_ups.py to tools/featuretest.sh (H057 owns it): `"followups|python3 tools/test_follow_ups.py|FOLLOW-UP TESTS"`
For the integrator: CLAUDE.md's Codex section, the "Jobs run through the queue (P24)" bullet, could add: "Leftovers go in a response as `Follow-up:` lines and merge instructions as `For the integrator:` lines; integrate.py copies the first into docs/follow-ups.md and prints the second (P26)."
For the integrator: BOARD.md's "If you're the integrator" paragraph, after "a response without one is yours to record.", could add: "It also copies Follow-up lines into docs/follow-ups.md and prints For the integrator lines under 'for you now:' (P26); clear a follow-up in the commit that does it."
For the integrator: this merge runs main's integrate.py, which doesn't read these lines yet: copy this entry's Follow-up line into docs/follow-ups.md by hand.
Follow-up: integrate.py takes an entry's ID from its file name's first dash, so an entry still named H-new-N at merge records its Result and follow-ups as "H" (number_ids runs after); seen in reading, not hit yet.

Result: 5ae4845; tools/test_follow_ups.py 11/11, test_startup 41/41, quick test and gate passed; integrate.py copies Follow-up lines to docs/follow-ups.md and prints For the integrator lines, startup.py lists open follow-ups
