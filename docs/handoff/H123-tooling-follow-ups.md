### H123 — Three tooling follow-ups: feature-test logs by folder, length cases with a default unit, response lines read from the response

Author: Claude (integrator, fretchup-73) | Date: 2026-11-23 | Status: answered | For: either

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

Response — Gemini (gemini-maple-1123-1856), 2026-11-23:

- Branch: `gemini/h123-tooling-follow-ups`
- Commit: `1802841`
- What changed:
  1. `tools/featuretest.sh`: prefixed each test's name with its folder (`worker-<name>`, `tools-<name>`, `viewport-<name>`), keeping `<NAME> TESTS:` summary lines unchanged and widening `--list` padding to 26 chars. Grepped `tools/` for `.rc`, `.time`, `featuretest`, `shopsketch-feature`, and `TIMING feature`: only `tools/test_featuretest.py` asserted on the old unprefixed name.
  2. `tools/length_cases.py`: added `DEFAULT_UNIT` with the exact 21 `(text, unit)` pairs (17 `"in"`, 2 `"cm"`, 2 `"m"`) in `tests/length_cases.json`'s order, evaluated with `evaluate(text, unit)` and appended with `{"text", "default_unit", "mm"}`. Regenerating via `/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd tools/length_cases.py` left `tests/length_cases.json` byte-for-byte unchanged (`git diff --exit-code` exited 0).
  3. `tools/integrate.py`: added `fallback_all=False` to `_response_body` and routed `follow_ups`, `for_integrator`, and `architecture` through `_response_body(text, fallback_all=True)` (leaving `changed_from_brief` and `response_values` untouched). Added named checks in `tools/test_follow_ups.py` for brief lines above `Response —`, fenced blocks, and entries with no Response heading.
  4. `docs/follow-ups.md`: cleared the three completed follow-ups (H052's two and H105's first).
- Verified:
  - `freecadcmd tools/length_cases.py && git diff --exit-code tests/length_cases.json`: 2521 cases written, diff clean.
  - `python3 tools/test_integrate.py`: 75 passed, 0 failed.
  - `python3 tools/test_follow_ups.py`: 27 passed, 0 failed.
  - `python3 tools/test_featuretest.py`: 45 passed, 0 failed (checks `--list` folder-prefixed names and a stand-in `worker/test_same.py` + `viewport/test_same.gd` pair keeping separate `worker-same.log` and `viewport-same.log`).
  - `python3 tools/job.py test` on `1802841`: all 36 feature test suites passed (including `LENGTH TESTS: 23 passed, 0 failed` and `UNITS TESTS: 132 passed, 0 failed`) and `viewport: QUICK 319 passed, 0 failed`.
- IDs added: none.
- Open questions: none.

Changed from the brief: Touches did not list tools/test_featuretest.py; updated its [tools-exit] and tools-silent assertions (P46) and added the --list folder-prefix and stand-in pair checks there; featuretest.sh's new folder-prefixed names changed the prefix asserted by test_featuretest.py and it is the dedicated test file for featuretest.sh.
Result: 1802841; quick test passed (all 36 feature suites and 319/319 viewport quick tests), length_cases.py diff clean; folder-prefixed featuretest logs, DEFAULT_UNIT in length_cases.py, response-scoped integrate.py parsers, cleared 3 follow-ups
