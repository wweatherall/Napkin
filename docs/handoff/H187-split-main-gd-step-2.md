### H187 — main.gd step 2: model files and rejection handling move to their own files, behaviour unchanged

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 (architecture order: split main.gd and presenter.gd; step 2 for the next batch), H177
(main.gd step 1: the pattern, `m.history` / `m.live_prefs`), P50 (a file's header line is its map line), P73,
comitatus principle C03.

Touches: viewport/main.gd (its "documents, menus, dialogs (T8)" section, ~lines 798-872, and from "the frame"
section only `reject_note`, `last_reject_note`, `force_reject_next`, `_on_wave_rejected_done` and `_on_rejected`,
~717-760), viewport/model_files.gd (new), viewport/rejections.gd (new), viewport/CLAUDE.md (its list of the main
script's helpers, one line each).

Reading path:
1. viewport/main.gd's "open, undo, sync (history.gd)" and "preferences (live_preferences.gd)" sections: how H177 made
   `m.history` and `m.live_prefs` and kept forwarders (one-line `func`s and `get`/`set` properties).
2. viewport/history.gd's header: what a moved helper's header says.
3. The two sections above in main.gd, and every caller of what they define:
   `python3 tools/dependency_map.py callers viewport/main.gd:<name>` for each function and variable
   (`switch_model`, `_reset_model_state`, `_on_rejected`, `reject_note`, ...). The map matches bare names, so check
   each hit by eye: `m.<name>` from another file is a real caller.

Today (checked 2026-11-27): main.gd is 992 lines. The documents section (settings file, `out_root`, last model,
outputs folder, window title, `switch_model`, `_reset_model_state`: ~75 lines) and the rejection handling (the
notes, the forced-rejection test switch, `_on_wave_rejected_done`, `_on_rejected`: ~40 lines) are self-contained.
`_on_rejected` changed in H183 (it passes `about` to `doc.reject`): move it as it is now.

Request:
1. **viewport/model_files.gd** takes the documents section (`m.files`); **viewport/rejections.gd** takes the
   rejection handling (`m.rejections`). Each is made like `m.history` (`load("res://...").new(self)`), with a header
   whose first line is its map line (P50).
2. **Nothing else changes**: same behaviour, same signals and their order, same `SHOPSKETCH ...` lines printed.
   main.gd keeps a forwarder for each moved name something outside main.gd uses (tools, menus, prompts, tests); one
   only main.gd used moves without one. `const SETTINGS` stays reachable as `m.SETTINGS` if anything reads it.
3. Report main.gd's size before and after (lines and KB) and each new file's.
4. Your response's `Architecture:` lines: `Architecture: viewport/model_files.gd owns <what>` and the same for
   rejections.gd.

Not in this job: presenter.gd (H188), the menus themselves (menus.gd), any rename, behaviour, or a function rewritten
while it moves (word for word, apart from `m.` where it now reaches back into main).

What can fail:
- Switching models (File > Open, New, New Window) losing state: `switch_model` and `_reset_model_state` reach into
  many parts of main through `m.`. Check: the quick and full viewport tests (they switch models constantly).
- A rejection's wave or note changing: `_on_rejected` and `_on_wave_rejected_done` are called from the frame and
  from history.gd. Check: the REJECTTEST lines and the rejection checks in the quick tests pass unchanged.
- A test using a moved name directly: a forwarder keeps it working; no test file changes, or each listed with why.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); quick 401/401.
- `python3 tools/architecture_map.py --check` and `python3 tools/dependency_map.py --check`.

Response — Gemini (gemini-cherry-1127-191429), 2026-11-27:
Split model file management (`m.files`) and rejection handling (`m.rejections`) out of `viewport/main.gd` into `viewport/model_files.gd` and `viewport/rejections.gd` with behaviour unchanged.

- `viewport/main.gd`: 992 lines (41,673 B / 40.7 KB) → 913 lines (38,695 B / 37.8 KB).
- `viewport/model_files.gd`: 82 lines (3,314 B / 3.2 KB). Kept `SETTINGS` and forwarders for `_beside_project`, `_model_before`, `switch_model`, and `_reset_model_state` (used by `ui.gd`, `worker_process.gd`, `history.gd`, `menus.gd`, and tests); `out_root`, `_last_model`, `_remember_model`, `_out_for`, and `_set_title` moved without forwarders.
- `viewport/rejections.gd`: 41 lines (1,834 B / 1.8 KB). Kept forwarders for `reject_note`, `last_reject_note`, `force_reject_next`, and `_on_rejected` (used by `history.gd` and tests); `_on_wave_rejected_done` moved without a forwarder and connects directly from `pres.wave_rejected_done`.
- Updated `viewport/CLAUDE.md` helper list.

Architecture: viewport/model_files.gd owns settings path, output folders, window title, last-model persistence, `_beside_project`, and model switching (`switch_model`, `_reset_model_state`).
Architecture: viewport/rejections.gd owns rejection status notes (`reject_note`, `last_reject_note`), the forced-rejection test hook (`force_reject_next`), and rejection-wave cleanup (`_on_wave_rejected_done`, `_on_rejected`).
Changed from the brief: regenerated `ARCHITECTURE.md` and `docs/dependency-map.md` using `tools/architecture_map.py` and `tools/dependency_map.py` (P73) so `--check` passes.
Result: `tools/TEST_BEFORE_MERGING.sh` GATE PASS (quick 401 passed, 0 failed in 31.2 s; full test passed in 18 s; 0 known failures; 85 s total); `python3 tools/architecture_map.py --check` and `python3 tools/dependency_map.py --check` passed.
