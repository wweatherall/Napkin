### H033 — T74 + T77: IDs numbered at merge, one handoff file per entry

Author: Claude (integrator) | Date: 2026-11-21 | Status: answered | For: a second Claude session

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

Response — Claude (second session), 2026-11-21: ready for review on `claude/t74` (worktree ../fretchup-claude-t74),
commit cf86525 plus this response. The branch is main + c533dc3 (round1-jobs, fast-forwarded: only it had H033–H035).
(1) T74: `tools/number_ids.py [--dry-run]` numbers every `<kind>-new-<digit>` placeholder in all tracked text files
(a letter after it is kept: I-new-Nb → I49b), the same number everywhere; next free = highest ID taken in the log's
rows and ### sections, the ### headings of the handoff, the archive and docs/handoff/, and the handoff file names;
padded like the kind's IDs (H036, A34, T78). It renames `docs/handoff/H-new-N-slug.md` files, re-sorts the log and
rebuilds the open list, and prints each placeholder → number (files). Merge step: `git merge --no-ff --no-commit
<branch>; python3 tools/number_ids.py; git commit`, once per branch (two branches merged together would share
their I-new-N). Examples in prose write N (a digit makes a placeholder), so the T74 row, the round-1 rule and
this entry's request now read I-new-N: the only wording I changed in moved text. (2) T77: H030, H032–H035 are files in
docs/handoff/, moved word for word (checked against the old file). `tools/handoff.py list [--check]`, `archive H0NN`
(to the archive's bottom, index line from its Resolution), `split` (moves an inline entry out; if a branch made before
T77 answered H034/H035 inline, after taking its version of that section `split` updates the file, and it refuses if
the text before the response differs). How-to, template (`H-new-N`, a For field), CLAUDE.md and AGENTS.md lines updated.
Verified: `python3 tools/test_number_ids.py` 29/29 (no placeholders, two kinds at once, one placeholder in several
files, lettered, order, Superseded and archive numbers count, rename, dry run, list, archive, split, the real list
matches); `tools/quicktest.sh` passes (features all 0 failed, QUICK 139/139). `number_ids.py --dry-run` on the
branch: no placeholders. Architecture sections changed: none (ARCHITECTURE.md line 16 still points at the handoff;
"open entries in docs/handoff/" could be added there, a line outside my Touches). Still open: nothing for T74/T77;
the pre-commit hook could run `handoff.py list --check` (not in my Touches; the feature test checks it meanwhile).
