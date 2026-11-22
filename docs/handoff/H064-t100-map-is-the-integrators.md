### H064 — T100: ARCHITECTURE.md and docs/protocol.md are the integrator's

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: Claude

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

**Response** — Claude (worker, session ece2cf8a), 2026-11-22

Branch `claude/h064-t100-map-is-the-integrators`, commit 49a00b1. Quick test and gate pass;
test_check_architecture.py 11/11 (6 new), FOLLOW-UP TESTS 19/19 (8 new).

1. Architecture lines: `integrate.architecture(text)` reads `Architecture: <what>` lines (a leading "- " allowed;
   a mention mid-line isn't one). Changed from the request, at the integrator's ask (seen merging H062, where the
   merge commit on main was refused without the map): with any such lines and no --impact, integrate.py stops
   after the gate, **before** the merge commit, with the merge staged. It prints the lines under "for you now:"
   marked `map:` with "write these into ARCHITECTURE.md / docs/protocol.md ... then: python3 tools/integrate.py
   --continue --as <name> [--push]". `--continue` refuses (and shows the lines again) until ARCHITECTURE.md or
   docs/protocol.md is changed in the index (or --impact is given), then does the commit, job.merged(), the
   Result drafts, the For the integrator lines and the push. The state sits in git's common folder
   (`shopsketch-integrate.json`) until the commit lands. A merge commit the hook refuses (watched code, no map,
   no --impact) is left the same way and resumes with --continue. No Architecture lines: no stop, no reminder.
2. check_architecture.py: on a branch (the current branch isn't main, or --range), a commit touching watched code
   passes with `Architecture-Impact: in the handoff - H0NN` (or H-new-N) when docs/handoff/H0NN-*.md in the
   commit's index (or at the range's head) has an Architecture: line; without one it fails, saying to add them.
   `none - <why>` is as before. On main the "in the handoff" form is refused: the map changes in the same commit,
   or none with a reason. The PR workflow (--range) is unchanged and checks a PR as a branch; its docstring says
   so. Worth knowing: a worker writes its Architecture: lines into the entry in the same commit as the code (or
   earlier), not only in the final response.
3. CLAUDE.md (the two Working with Codex bullets), AGENTS.md (its architecture bullet, "architecture sections
   changed" → Architecture: lines), docs/agent-handoff.md (a rule beside the Touches rule; "a line in
   ARCHITECTURE.md" dropped from the hot spots). "The reviewer checks prose against code" is kept in CLAUDE.md.

For the integrator: P28's "Where in the code": tools/check_architecture.py (IN_HANDOFF, handoff_reader; on a branch only), tools/integrate.py (architecture(), stops before the merge commit with the merge staged; --continue: resume(), commit_and_finish()); checks: tools/test_check_architecture.py, tools/test_follow_ups.py. T100
For the integrator: BOARD.md's integrator section: after "merge what's good with `python3 tools/integrate.py <branch> --as <name> --push`", add "(a job with Architecture: lines stops with the merge staged: write the map, then `integrate.py --continue --as <name> --push`, P28)".
For the integrator: this merge itself has no Architecture lines (tools/ isn't watched), so it goes straight through.

Follow-up: CLAUDE.md's "Shared hot spots (the decision log's Work list, the handoff, ARCHITECTURE.md tables, viewport/main.gd)" line still names ARCHITECTURE.md tables as a hot spot; outside the bullets this job was given.

Result: 49a00b1; quick test and gate pass (architecture guard 11/11, FOLLOW-UP TESTS 19/19); the commit check takes "Architecture-Impact: in the handoff - H0NN" on a branch, and integrate.py stops a merge with Architecture: lines before its commit for the map, resumed with --continue (P28)
