### H177 — main.gd step 1: history replies and live preferences move to their own files, behaviour unchanged

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 (architecture order: split main.gd and presenter.gd, so the map has real boundaries and
more jobs can run at once), comitatus principle C03 (simplify), P50 (each file's header line is its map line),
the pattern keys.gd (T75) and measure_box.gd already follow.

Touches: viewport/main.gd (its open, undo, redo, worker sync and confirmed boards sections, ~lines 703-898,
and its preferences section, ~1057-1180), viewport/history.gd (new), viewport/live_preferences.gd (new),
viewport/CLAUDE.md (its list of the main script's helpers, one line each), viewport/tests/ (only references that must
change; ideally none).

Reading path:
1. viewport/main.gd lines 60-75 and ~1200: how `measure` and `keys` are made (`load("res://...").new()`), given `m`,
   and how main.gd keeps forwarders so tools and tests that use the old names don't change.
2. viewport/measure_box.gd's header: a moved helper's header names what it owns and the forwarders main keeps.
3. viewport/main.gd's sections named above, and every caller of their functions and variables
   (`python3 tools/dependency_map.py callers viewport/main.gd:<name>` once H174 has merged; grep otherwise).

Today (checked 2026-11-27): main.gd is 1,264 lines and 50 KB with 77 functions; most jobs that touch the app touch
it, so they queue behind each other. Two sections are self-contained: answering FreeCAD's open, undo, redo and sync
replies (`_on_open`, undo/redo, `_on_synced`, `_on_rejected`, the confirmed-boards glue: ~195 lines), and live
preferences (loading, watching and applying user://preferences.json: ~125 lines).

Request:
1. **viewport/history.gd** takes the open/undo, redo, worker sync and confirmed-boards sections; **viewport/
   live_preferences.gd** takes the preferences section. Each is made like `measure`/`keys` (`m.history`,
   `m.live_prefs`), with a header whose first line is its map line (P50).
2. **Nothing else changes**: same behaviour, same signals and their order, same messages printed (tests read
   `SHOPSKETCH ...` lines). main.gd keeps a forwarder for each moved name that something outside main.gd uses, so
   tools and tests don't change; one that only main.gd used moves without a forwarder.
3. Report main.gd's size before and after (lines and KB) and each new file's.

Not in this job: presenter.gd (a later step), any rename, behaviour, or a function rewritten while it moves (move
it word for word, apart from `m.` where it now reaches back into main).

What can fail:
- A signal connected in main.gd's setup to a function that moved: connect to the new file's function, same order.
  Check: the quick and full viewport tests (they open, undo, redo, sync and switch models constantly).
- A test or tool using a moved name directly: a forwarder keeps it working. Check: no test file changes, or each
  change listed with why.
- Preferences watched twice or not at all after the move (the timer): check test_preferences.gd and the quick
  preferences tests pass unchanged.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); quick 401/401.
- `python3 tools/architecture_map.py --check` (the new files' header lines).

---
Response (Gemini, gemini-elm-1127-1021, 2026-11-27):

Moved the open/undo, redo, worker sync, and confirmed-boards sections to `viewport/history.gd` (`m.history`) and the live-preferences section to `viewport/live_preferences.gd` (`m.live_prefs`), keeping forwarders in `viewport/main.gd` for every symbol referenced outside `main.gd` (`undo`, `redo`, `_rebuild_rect_drafts`, `sync`, `_on_worker`, `_on_sync_failed`, `_ops_key`, `PREFERENCES_PATH`, `PREFERENCES_KEY`, `preferences_path`, `prefs`, `_prefs_timer`, `_init_preferences`, `_start_preferences`, `_apply_preferences`, `_open_preferences`). No test files were changed.

Sizes:
- `viewport/main.gd`: 1,264 lines / 50.2 KB (51,370 B) before -> 992 lines / 40.7 KB (41,653 B) after
- `viewport/history.gd`: 210 lines / 8.2 KB (8,353 B)
- `viewport/live_preferences.gd`: 120 lines / 4.5 KB (4,575 B)

Changed from the brief: With integrator scope approval (`job.py wait --scope`), regenerated `ARCHITECTURE.md` via `python3 tools/architecture_map.py` to include the two new modules and updated the 4 Producer/consumer references in `docs/protocol.md` (`_on_open`, `_on_synced`, `_on_boards_read`) to point to `viewport/history.gd` so `protocol_map.py --check` passes (`docs/dependency-map.md` is not on this branch yet).

Result: `tools/TEST_BEFORE_MERGING.sh` passed (full scope; quick 401/401 in 92.0 s, full suites + compare + field audit + feature tests including `PROTOCOL MAP TESTS: 14 passed, 0 failed`), `python3 tools/architecture_map.py --check` passed, `python3 tools/protocol_map.py --check` passed.
