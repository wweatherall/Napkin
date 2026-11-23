### H123 — Three tooling follow-ups: feature-test logs by folder, length cases with a default unit, response lines read from the response

Author: Claude (integrator, fretchup-73) | Date: 2026-11-23 | Status: open | For: either

References: T116, P26 (follow-ups), P21 (predictions checked against FreeCAD), T95 (the feature tests find
their files), H052 and H105 (the follow-ups this clears).

Touches: tools/featuretest.sh, tools/length_cases.py, tests/length_cases.json (only if regenerating changes it:
see 2), tools/integrate.py (`follow_ups`, `for_integrator`, `architecture`, `_response_body`),
tools/test_integrate.py, tools/test_follow_ups.py, docs/follow-ups.md (clear the three follow-ups). Not
`changed_from_brief` or `response_values` (H120's, as they are), not tools/quicktest.sh or tools/gate.sh beyond
what reading featuretest.sh's new log names needs (say so if it does).

Why: three small traps found by workers, each written down as a follow-up and none big enough for a job alone.

Request:
1. featuretest.sh (H052's follow-up): each test's log, rc and time files are named by its basename after
   `test_` (`name=${name#test_}`), so worker/test_x.py and viewport/test_x.gd would overwrite each other's
   results and one of them would pass or fail silently. Name each by folder and name (`worker-x`, `tools-x`,
   `viewport-x`): unique by construction, since a folder can't hold two files of one name. Keep the summary
   line's `<NAME> TESTS:` text as the tests print it; only the file names and the `[name]` prefixes change.
   If anything reads those file names (grep tools/ for `.rc`, `.time` and the feature log folder), update it.
2. length_cases.py (H052's follow-up): tests/length_cases.json ends with 21 cases with a `default_unit` (17
   "in", 2 "cm", 2 "m") that were appended by hand; the generator doesn't make them, so regenerating would drop them and
   viewport/test_units.gd would stop checking typed lengths in a model's default unit. Add a `DEFAULT_UNIT`
   list to the generator holding exactly those 21 (text, unit) pairs, in the file's order, evaluated with
   `evaluate(text, unit)`, written after the others with the same keys as today. Check: regenerating
   (`freecadcmd tools/length_cases.py`) leaves tests/length_cases.json byte-for-byte unchanged (`git diff
   --exit-code`), so the generator and the file agree; if it doesn't, say why in your response before
   committing a changed file.
3. integrate.py (H105's follow-up): `follow_ups`, `for_integrator` and `architecture` read the whole entry, so a
   brief's own line starting `Follow-up:` or `Architecture:` (a brief quoting the format) would be taken as the
   worker's. Read them from `_response_body(text)` as `changed_from_brief` does, with one difference so nothing
   a worker wrote is lost: when the entry has no Response heading, read the whole text, as today. (An entry
   with no recognized heading is a worker's formatting slip; losing its Follow-up lines would lose the
   leftovers silently.)

What can fail (each gets a named check):
- featuretest.sh `--list` shows the new names, and a stand-in pair (a worker/ and a viewport/ test of one name,
  made in a scratch copy, not committed) keeps two logs: a check in a tools/test_*.py, or a line in your
  response saying how you proved it if a shell check doesn't fit.
- The regenerated length cases equal the file (2's check), and viewport/test_units.gd and
  worker/test_length_input.py pass on it.
- In tools/test_follow_ups.py or test_integrate.py: a brief with a line `Follow-up: <example>` above its
  `Response —` heading, and a response with one `Follow-up:` line: only the response's is read; the same for
  `For the integrator:` and `Architecture:`. An entry with no Response heading and a `Follow-up:` line: read,
  as today. The existing fixtures (which have no Response heading) pass unchanged.

Reading path: featuretest.sh (the `TESTS` loop, then the result loop) → length_cases.py `main` →
tests/length_cases.json's last 21 cases → viewport/test_units.gd (how it reads `default_unit`) →
integrate.py `RESPONSE_HEADING`, `_response_body`, `response_values`, `changed_from_brief`, and where the three
are collected (`archive_entries`, ~797).

Run `python3 tools/test_integrate.py`, `python3 tools/test_follow_ups.py` and `tools/featuretest.sh` while
building, then `python3 tools/job.py test`. Clear the three follow-ups in docs/follow-ups.md (H052's two, H105's
first: "`follow_ups()`, `for_integrator()`, and `architecture()` ... still scan the full handoff file") in the
code commit, before the quick test. End your response with a Result line; leftovers as Follow-up lines.
