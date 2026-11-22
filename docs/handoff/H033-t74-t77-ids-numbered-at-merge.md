### H033 — T74 + T77: IDs numbered at merge, one handoff file per entry

Author: Claude (integrator) | Date: 2026-11-21 | Status: open | For: a second Claude session

References: T74, T77, P09, P11; the I43–I45 clash (H032); tools/sort_decision_log.py (an existing log tool to copy the style of).

Touches: tools/number_ids.py (new) + tools/test_number_ids.py (new), docs/handoff/ (new, one file per open entry),
docs/agent-handoff.md (becomes the rules + an open list built from docs/handoff/), docs/decision-log.md (P09's ID
rule if needed, the T74/T77 rows), CLAUDE.md and AGENTS.md (the "Working with Codex" handoff/ID lines only),
tools/featuretest.sh only to add the new test to its list (one line; H034 also edits this file: add your line last).

Request: (1) T74: a branch writes placeholders (I-new-N, T-new-N, H-new-N, ...); `tools/number_ids.py` run on main
at merge replaces each with the next free number across the decision log, handoff files and the branch's
commit-touched docs, and reports what it did. A dry-run mode. Tests for: no placeholders, two kinds at once,
a placeholder cited in several files gets one number. (2) T77: open entries move to `docs/handoff/H0NN-slug.md`;
`docs/agent-handoff.md` keeps the how-to, the rules above, and an open list the script (or a small companion)
rebuilds from the folder; archiving moves a file to the archive the same way as today. Migrate H030, H032 and
H033–H035 last, after merging main (Codex will have written responses in H034/H035 by then). Ask William
before changing anything an agent would notice beyond what T74/T77 say.
