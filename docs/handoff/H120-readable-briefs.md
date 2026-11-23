### H120 — T115: briefs the tools can read (Touches checked at Ready; wrapped response lines read whole)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-23 | Status: open | For: either

References: T115, P45 (Touches), P44 (Changed from the brief), P28 (Architecture lines), P26 (follow-ups).

Touches: tools/handoff.py (a new `check` command and `touches_named`'s callers only; not how Touches are
parsed for overlaps), .githooks/pre-commit, tools/integrate.py (`ARCHITECTURE_LINE`, `CHANGED`,
`RESPONSE_HEADING`, `follow_ups`, `for_integrator`, `architecture`, `changed_from_brief`), a new
tools/test_handoff.py, tools/test_integrate.py, docs/follow-ups.md (clear the two follow-ups this job does).

Why: the tools read briefs and responses more strictly than people write them. On 2026-11-23: H110's Touches
named `registry.gd` and `units.gd` bare after a full path, so the merge flagged them as outside Touches (a
false alarm); H114's `viewport/tests/quick/*.gd` matched H093's test file and held it back; and H093's
`Changed from the brief:` lines, wrapped by Codex, were cut mid-sentence at the review stop and in the merge
message. The purpose: a brief is checked when it is written, and a response is read the way it was written.

Request:
1. `python3 tools/handoff.py check [H0NN ...]` (all open and queued job entries when none given): for each
   entry, list problems in its Touches paragraph: a bare file name (a word ending .gd/.py/.sh/.md/.json/.tscn/
   .cfg with no `/`, outside a "Not ..." sentence or an aside the parser already skips, and not a top-level file
   the parser knows); a glob (`*`); a path that doesn't exist and isn't marked "(new)" or "a new". Exit 1 with
   one line per problem: `H0NN: Touches: <problem>: <word>`; exit 0 and print nothing when clean.
2. .githooks/pre-commit runs it on the entries a commit adds or changes whose Status is open or queued, so a
   brief can't be marked Ready with a Touches the tools misread (the hook already rebuilds the open list there).
3. integrate.py: each of `Architecture:`, `Changed from the brief:`, `Follow-up:` and `For the integrator:` is
   read from its keyword to the next blank line, the next line starting with one of those keywords or
   `Result:`, or the end; its lines are joined with spaces. `RESPONSE_HEADING` matches only a heading line
   (`#...# Response`, `**Response`, `Response —`, `Response from`), not a brief's own `Response: a table ...`.
   This clears two follow-ups in docs/follow-ups.md (the integrator's of 2026-11-23 on wrapped lines and H105's
   on `RESPONSE_HEADING`): remove them in the code commit, before the quick test.

What can fail (each gets a named check):
- Today's open and queued entries must pass `check` as they stand (the integrator fixed H109's bare names on
  2026-11-23): run it on all of them and list any it flags in your response rather than editing those entries.
- A Touches that says "Not presenter.gd's waves" or "(don't add it to tools/x.sh)" is not a bare-name problem.
- A path marked new ("viewport/ui.gd (new)", "a new worker/test_link.py") isn't missing.
- A wrapped `Changed from the brief:` of three lines followed by `Architecture:` gives one whole change and
  one architecture line; a one-line one followed by a blank line is unchanged from today.
- A `Result:` line after a wrapped `For the integrator:` isn't swallowed into it.
- A brief whose Request has a line `Response: a table ...` and whose response has no `Changed from the brief:`:
  no stop (H105's case, now with the heading tightened).
- The archived entries (docs/handoff-archive.md) are not checked: old wording stays as written.

Reading path: handoff.py `touches_named` (PATH, SKIP, NOT_ASIDE, TOP) → `shared_touches` → the pre-commit hook
→ integrate.py `follow_ups` / `for_integrator` / `architecture` / `changed_from_brief` and their regexes →
`archive_entries` (where they are collected) → `pause_for_map` (where they print).

Run `python3 tools/test_handoff.py` and `python3 tools/test_integrate.py` while building, then
`python3 tools/job.py test`. End your response with a Result line; leftovers as Follow-up lines; anything for
the merge as For the integrator lines.
