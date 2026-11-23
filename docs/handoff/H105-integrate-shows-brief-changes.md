### H105 — integrate.py stops for a response's `Changed from the brief:` lines (P44)

Author: Claude (integrator, fretchup-74) | Date: 2026-11-22 | Status: queued (after H104) | For: gemini

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
