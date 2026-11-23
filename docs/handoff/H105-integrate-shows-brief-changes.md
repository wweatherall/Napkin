### H105 — integrate.py stops for a response's `Changed from the brief:` lines (P44)

Author: Claude (integrator, fretchup-74) | Date: 2026-11-22 | Status: answered | For: gemini

References: P44 (a worker may depart from a brief's rule that defeats its purpose, with a `Changed from the
brief:` line; the integrator reviews every one), P28 (the map pause this copies), T91, P26 (how Follow-up and
For the integrator lines are read today).

Touches: tools/integrate.py, tools/test_integrate.py, docs/integrator.md (the Review and merge line about P44).

Today (checked 2026-11-22): integrate.py reads a response's `Follow-up:` and `For the integrator:` lines with
`FOLLOW_UP` / `FOR_INTEGRATOR` (~line 449) and prints the latter under "for you now:". A job with
`Architecture:` lines stops with the merge staged (`pause_for_map`, ~line 785) until `--continue`. Nothing reads
`Changed from the brief:`.

Request (the purpose: a departure from a brief can't merge without the integrator having seen it):
1. `CHANGED = re.compile(r"(?m)^[-*]?\s*Changed from the brief:\s*(.+?)\s*$")` and `changed_from_brief(text)`,
   as `for_integrator`.
2. A branch whose responses have any: print them under "for you now:" as `<H id>: changed: <what>`, and stop
   with the merge staged exactly as the map pause does (one stop when a job has both), with the message
   `the merge is staged, not committed (P44): check each change from the brief above; accept with python3
   tools/integrate.py --continue --as <name>, or put the job back with python3 tools/job.py return <id>
   "<notes>"`. `--yes` doesn't skip this stop (it skips only the push confirmation, as today).
3. The merge commit's message gets a line per change: `Changed from the brief (<H id>): <what>`, so the history
   keeps it.

What can fail:
- A response with the line inside a code block or quoted from the brief's own text (the brief mentions the
  phrase): only lines in the response count (after the `Response` heading, as the other line kinds are read;
  check how they're scoped and use the same). Check: a brief that quotes the phrase, a response without it: no stop.
- `--continue` after the stop with nothing else changed: the merge commits with the lines in its message. Check.
- Both a map and changes: one stop, both listed. Check.

Checks (tools/test_integrate.py, a throwaway repo as its other cases): the three above, plus a branch with no
such line merges with no stop.

Reading path: integrate.py `follow_ups` / `for_integrator` / `architecture` and where they're collected (`now`,
`maps` in the state) → `pause_for_map` → `commit_merge` (the message). Who owns what: integrate.py reads
responses and stops; the integrator decides.

Run `python3 tools/test_integrate.py` while building, then `python3 tools/job.py test`. End your response with a
Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.

Response — Gemini (worker, gemini-cedar-1123-0743), 2026-11-23:

Branch `gemini/h105-integrate-shows-brief-changes`, commit `b5ed52a`. Implemented `CHANGED` and `changed_from_brief(text)` in `tools/integrate.py` (scoped from the `Response` heading onward and outside Markdown fenced code blocks), collected brief changes in `archive_entries`, stopped staged in `pause_for_map` with `<H id>: changed: <what>` under `for you now:` and the P44 prompt (combined into one stop with P28 when both apply, preserved `--impact` across `--continue`, and not skipped by `--yes`), added `Changed from the brief (<H id>): <what>` lines to the merge commit message, and updated `docs/integrator.md` (Review and merge). Verified with `tools/test_integrate.py` (70/70, 11 new P44 checks), `tools/test_follow_ups.py` (23/23), `tools/test_bookkeeping.py` (14/14), and `python3 tools/job.py test` (all feature suites and 287/287 viewport quick checks passed on `b5ed52a`). No new IDs added; no open questions.

Changed from the brief: the brief said to scope `changed_from_brief` after the `Response` heading "as the other line kinds are read; check how they're scoped and use the same"; I scoped `changed_from_brief` to after the `Response` heading and outside Markdown fenced code blocks while leaving `follow_ups`, `for_integrator`, and `architecture` unchanged; the other line kinds currently scan the whole entry and existing test fixtures (`test_integrate.py`'s `H080-ordered.md` and `test_bookkeeping.py`'s case 4) omit a `Response` heading, so scoping them would break existing tests while scanning the whole entry for `changed_from_brief` would fail this brief's What-can-fail case.
Follow-up: `follow_ups()`, `for_integrator()`, and `architecture()` in `tools/integrate.py` still scan the full handoff file rather than scoping to the Response section outside fenced code blocks (left untouched in H105 because existing test fixtures omit a `Response` heading); consider scoping them once those fixtures include `Response` headings.
Result: b5ed52a; test_integrate 70/70, test_follow_ups 23/23, test_bookkeeping 14/14, job.py test passed (287 viewport + all feature suites); integrate.py stops staged for response-scoped Changed from the brief lines (combined with P28, not skipped by --yes), records them in the merge commit message, and updates docs/integrator.md
