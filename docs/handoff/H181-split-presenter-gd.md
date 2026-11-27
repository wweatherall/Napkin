### H181 — presenter.gd step 1: confirmation waves and selection drawing move to their own files, behaviour unchanged

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: open | For: gemini

References: William, 2026-11-27 (architecture order: split main.gd and presenter.gd), H177 (main.gd step 1, the same
pattern), W01-W09 (the confirmation wave), A33b (selection is drawn by the presenter from what selection.gd says),
comitatus principle C03, P50.

Touches: viewport/presenter.gd (its operation wave section, ~lines 769-886, and its selection-and-context drawing
section, ~887-988), viewport/waves.gd (new), viewport/selection_view.gd (new). (The integrator adds the viewport guide's lines after the merge: H177 holds that file.)

Reading path:
1. viewport/presenter.gd's header (what it owns) and the two sections named above.
2. How main.gd reaches the presenter (`m.pres`) and calls these functions: `python3 tools/dependency_map.py callers
   viewport/presenter.gd:attach_wave` (and `step_waves`, `apply_context`, `show_selection`, `show_siblings`).
3. viewport/main.gd's `measure` / `keys` pattern, as H177 uses it for main.gd.

Today (checked 2026-11-27): presenter.gd is 988 lines and 42 KB. The operation wave (W01-W09: the confirmation and
rejection waves) and the selection/context highlights are self-contained sections.

Request:
1. **viewport/waves.gd** takes the operation wave section; **viewport/selection_view.gd** takes the selection and
   context drawing section. Each is made by the presenter and reached through it (`pres.waves`, `pres.selection_view`),
   with a header whose first line is its map line (P50).
2. **Nothing else changes**: same behaviour and timing (waves are timed: same frame order), same names reachable
   through the presenter, so main.gd, tools and tests don't change: the presenter keeps a forwarder for each moved
   name used outside it; one only the presenter used moves without one.
3. Report presenter.gd's size before and after and each new file's.
4. Your response's `Architecture:` lines: `Architecture: viewport/waves.gd owns <what>` and the same for
   selection_view.gd (H180's forms).

Not in this job: main.gd (H177), any rename, behaviour change, or rewrite while moving (word for word, apart from
reaching back into the presenter).

What can fail:
- A wave's timing or colour changing: the quick tests that check waves and highlights pass unchanged. Check: the
  quick and full viewport tests.
- A test using a moved name directly: a forwarder keeps it working; no test file changes, or each listed with why.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); quick 401/401.
- `python3 tools/architecture_map.py --check` and `python3 tools/dependency_map.py --check`.
