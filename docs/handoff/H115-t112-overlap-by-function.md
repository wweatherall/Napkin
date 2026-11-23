### H115 — T112: the queue checks overlap by function (P45)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: Codex

References: P45 (replaces P11), T112, T113 (H107-H114, the jobs this lets run side by side).

Touches: tools/handoff.py (`touches`, `overlaps_in`, a new function beside them), tools/job.py (`jobs_from`,
`overlap`, `takeable`'s message), tools/test_number_ids.py (its "P11 overlap check" block), tools/test_job.py,
docs/agent-handoff.md (one sentence in "How to use this file", the bullet ending "Its Touches line is what the
queue checks for overlap"). Not tools/integrate.py (H105 holds it; its `outside_touches` keeps using `touches()`
as it is), not tools/startup.py unless its call to `overlaps_in` needs a change to keep working. Queued after
H104, which holds job.py and test_job.py.

Why: P45 (William, 2026-11-22). Six queued jobs each list viewport/main.gd and wait on each other although they
change different functions; git merges separate hunks, the integrator resolves a textual clash at merge and the
gate catches the rest. The queue still compares whole files, so today the integrator checks by eye.

Today (checked 2026-11-22): handoff.py `touches(body)` returns the set of paths in a job's "Touches:" paragraph
(PATH regex; `NOT_ASIDE` strips "(not ...)" / "(don't ...)" asides; sentences starting "Not", "Read-only", ...
are skipped). `overlaps_in(texts)` (used by `handoff.py overlaps` and tools/startup.py) and job.py `overlap(a, b)`
(used by `takeable`, which passes a Ready job over when it overlaps one in progress) compare those paths with
`_covers` (equal, folder, or glob). integrate.py `outside_touches` also calls `touches()` to flag files a branch
changed outside its list.

Request:
1. A Touches entry names functions by backticked identifiers in the parenthetical right after its path:
   `viewport/main.gd (the redo section: `redo`, `_ask_outside`, `PROTOCOL_VERSION`)`. A backticked span counts
   only if it is wholly an identifier (`[A-Za-z_]\w*`, optionally followed by `()`); `m.sel`, `ui_*` or a path
   don't count. The parenthetical runs to its matching `)` (briefs nest them: "the section "the worker (T6)": ...").
   A path with no counted names is the whole file, as today. Why: a brief can stay prose, and a name that can't be
   compared falls back to the safe answer (whole file).
2. A new `handoff.touches_named(body) -> {path: set of names, or None for the whole file}`; `touches()` keeps its
   return value (integrate.py and others rely on a set of paths).
3. Two entries overlap when their paths cover each other (`_covers`, as today) and either is the whole file
   (None, or a folder / glob) or their name sets meet. `overlaps_in` and job.py `overlap` use that; each reports
   what is shared as `viewport/main.gd (redo)` when names caused it, the plain path otherwise, so takeable's
   "H002: overlaps H001 (...)" line and `handoff.py overlaps` say why.
4. One sentence in docs/agent-handoff.md after "Its Touches line is what the queue checks for overlap": a shared
   file can name the functions or constants it changes in backticks after it, and then overlaps only where the
   names meet (P45).

5. `_covers` treats a path with `*` only at its end as a glob: `viewport/tools/*.gd` is taken as a file, so
   integrate.py flagged viewport/tools/move_tool.gd as outside H101's Touches list (H101's merge, 2026-11-23). Make a
   `*` anywhere in the last part a glob (fnmatch on that part), so `viewport/tools/*.gd` covers
   `viewport/tools/move_tool.gd` but not `viewport/tools/sub/x.gd`. Why: a wrong "outside its Touches" flag makes the
   integrator check by hand, and a missed overlap lets two jobs clash. Check: that case, in test_number_ids.py.

Cases that must still work: every current check in test_number_ids.py's overlap block (H041's
"viewport/main.gd (the tool list only)" has no backticked names, so it is still the whole file and still clashes
with H042's "(`_on_open` only)"); test_job.py's "a job whose files overlap one in progress is passed over";
`python3 tools/handoff.py overlaps` and startup.py on main as it is.

Checks (in test_number_ids.py beside the existing ones, and one in test_job.py), each named:
- two jobs naming main.gd with `redo` and `_ask_outside` don't overlap;
- `redo` and `redo` do, reported as `viewport/main.gd (redo)`;
- named vs unnamed main.gd overlap (whole file);
- a glob (`viewport/*`) vs named main.gd overlap;
- `m._update_camera`, `ui_*` and a path in backticks aren't names (an entry with only those is the whole file);
- a nested parenthetical's names are read (`viewport/main.gd (the section "x (T6)": `a`, `b`)` gives {a, b});
- `touches()` returns the same paths as before for every case above;
- test_job.py: a Ready job naming different main.gd functions from one in progress is taken.

Run `python3 tools/job.py test` (the quick test is enough for tools/; the feature tests run tools/test_*.py). End
your response with a Result line; leftovers as Follow-up lines.
