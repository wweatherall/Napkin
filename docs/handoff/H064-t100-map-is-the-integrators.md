### H064 — T100: ARCHITECTURE.md and docs/protocol.md are the integrator's

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: Claude

References: P28 (William's call, 2026-11-22; replaces his rule of 2026-11-21 in CLAUDE.md's "Working with Codex":
the agent changing a module updates the map in the same commit), P26 / T97 (Follow-up and For the integrator
lines: follow that pattern in tools/integrate.py), tools/check_architecture.py (the commit hook and the PR check).

Touches: tools/check_architecture.py, tools/test_check_architecture.py, tools/integrate.py, tools/test_follow_ups.py
(or a new test file), CLAUDE.md (the "Working with Codex" bullets on the map and the Architecture-Impact line), AGENTS.md (its architecture bullet and the "When it's done" step), docs/agent-handoff.md (the rules beside
the Follow-up rule). Not BOARD.md or the decision log (H062 has it): give BOARD.md's lines and P28's "Where in the
code" as "For the integrator:" lines.

Request: build P28.
1. A response may carry `Architecture: <what>` lines (a leading "- " allowed, like Follow-up:): what the change
   does to ARCHITECTURE.md's map or docs/protocol.md (a module, a message, state ownership, saving). At merge,
   integrate.py prints them under "for you now:" with the For the integrator lines, marked as map changes, and
   says "write these into ARCHITECTURE.md / docs/protocol.md before pushing" when there are any.
2. tools/check_architecture.py: on a branch (not main), a commit touching watched code passes with
   `Architecture-Impact: in the handoff - H0NN` (or H-new-N) when that handoff file on the branch has at least one
   Architecture: line; without the lines it fails, saying to add them. `Architecture-Impact: none - <why>` stays as
   it is. On main (the merge commit or the integrator's follow-up commit), the check is as today: the map changes
   in the same commit, or none with a reason. Keep the PR workflow working (--range); say what it checks now.
3. Workers don't edit ARCHITECTURE.md or docs/protocol.md: CLAUDE.md, AGENTS.md and the handoff rules say so in a
   line or two, and that the integrator writes the change at merge. Keep "the reviewer checks prose against code".
Checks: lines parsed with and without "- "; printed at merge with the reminder; none means no reminder; the check
passes a branch commit naming a handoff with Architecture lines, fails one naming a handoff without them, and on
main still wants the map. Quick test, then the gate. End your response with a Result line; leftovers as Follow-up
lines; anything for the merge as For the integrator lines.
