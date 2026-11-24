### H122 — T113 step 5: main.gd's compatibility members go (callers use the modules)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-23 | Status: open | For: either

References: T113, A33b, P45; the follow-ups this clears: H107, H110, H111, H112, H113 (docs/follow-ups.md).

Touches: viewport/main.gd (`_menus`, `TRACKPAD_PX`, `ZOOM_STEP`, `yaw`, `dist`, `trackpad_px`, `zoom_step`,
`_tool_buttons`, `_update_toggles`, `wood_library`, `wood_keys`, `paint_material`, `set_paint_material`,
`_turn_grain`, `worker_port`, `worker_pid`, `lifecycle_test`, `_apply_preferences`, `_live_tuning`),
viewport/menus.gd, viewport/tests.gd, viewport/tests/quick/models.gd, viewport/tests/quick/registry.gd,
viewport/tests/quick/preferences.gd, viewport/tests/suites/shell.gd, viewport/tests/suites/lifecycle.gd. Not docs/follow-ups.md (H123 holds it; the integrator
clears these five at merge). Not the modules themselves (camera_rig.gd, ui.gd,
appearance.gd, worker_process.gd, menus.gd's own state): the members already live there. Not
viewport/CLAUDE.md: its Files list says main forwards the Wood names; write the change as a For the integrator
line.

Why: each T113 step moved a part of main.gd into its own module and left a getter or forwarder on main for
callers outside its Touches, with a follow-up to remove it. Each is a second name for one thing; a reader or a
tool has to learn both. The purpose: one name per member, the module's, and main.gd shorter. No change in
behaviour.

Today (checked 2026-11-23, main.gd line numbers approximate):
- `_menus` (~57, H110) → `menus.menus`: read by tests/quick/models.gd:20 and tests/suites/shell.gd:34.
- `TRACKPAD_PX`, `ZOOM_STEP`, `yaw`, `dist`, `trackpad_px`, `zoom_step` (~99-110, H113) → `camera_rig.*`: read
  by tests/quick/preferences.gd (lines 44-45, 82-83, 90-103, 124-135) and by main's own `_apply_preferences`
  (~1242) and `_live_tuning` (~1279).
- `_tool_buttons` (~205, H111) → `ui.tool_buttons`: read by tests/quick/registry.gd (27-58).
- `_update_toggles` (~455, H111) → `ui.update_toggles()`: called by menus.gd:117-118.
- `wood_library`, `wood_keys`, `paint_material`, `set_paint_material`, `_turn_grain` (~688-701, H112) →
  `appearance.*` (`_turn_grain` is `appearance.turn_grain(hover_body)`): called by menus.gd:126-140.
- `worker_port`, `worker_pid`, `lifecycle_test` (~1070-1076, H107) → `worker.*`: read by
  tests/suites/lifecycle.gd (16-30) and tests.gd (21, 35).

Request: point every caller listed at the module's name (`m.menus.menus`, `m.camera_rig.trackpad_px`,
`m.ui.tool_buttons`, `m.ui.update_toggles()`, `m.appearance.*`, `m.worker.*`; inside main.gd the module
directly), then delete the members and their "still read here" comments. Before deleting each, grep the whole
repo for it (`git grep -nP '\b<name>\b'`, tools/ and docs/ too) so no caller outside this list is left
calling a name that's gone; a caller found outside Touches: ask with `job.py wait --scope`.

Cases that must still work: the quick test (models, registry, preferences sections), the gate (the full test's
suites with no change to tests/reference/), `--shelltest` and `--lifecycletest` run by hand once (they are
targeted suites, not in the gate: say in your response that you ran them and what they printed), and the Wood
menu, Grid snap and New board menu items (registry and wood quick-test steps).

Checks: no new behaviour, so no new check; the existing ones above must pass, and a parse check
(`tools/parsecheck.sh`) catches a caller left on a deleted name in the viewport.

Run the quick test after each group of members, then `python3 tools/job.py test`. End your response with a Result line (main.gd's
line count before and after); leftovers as Follow-up lines; the viewport/CLAUDE.md change as a For the
integrator line.

#### Response — Gemini (gemini-birch-1123-1855), 2026-11-23

Architecture: `viewport/menus.gd` row — remove the note that main keeps a read-only `_menus` alias (`models.gd` and `shell.gd` now read `m.menus.menus`).
Architecture: `viewport/camera_rig.gd` and `viewport/preferences.gd` rows — remove the notes that main keeps read aliases (`yaw`, `dist`) and the two tunables (`TRACKPAD_PX`, `ZOOM_STEP`, `trackpad_px`, `zoom_step`) (`preferences.gd` quick test and main's `_apply_preferences` / `_live_tuning` now use `camera_rig.*` / `CameraRig.*` directly).
Architecture: `viewport/ui.gd` row — remove the note that main keeps `_update_toggles()` and `_tool_buttons` (`menus.gd` calls `m.ui.update_toggles()` and `registry.gd` reads `m.ui.tool_buttons`).
Architecture: `viewport/appearance.gd` row — remove the note that main keeps `wood_library`, `wood_keys`, `paint_material`, `set_paint_material` and `_turn_grain` (`menus.gd` uses `m.appearance.*` directly, calling `m.appearance.turn_grain(m.hover_body)` for Turn grain).
Architecture: `viewport/worker_process.gd` row — remove the note that main keeps read aliases `worker_port`, `worker_pid` and `lifecycle_test` (`tests.gd` and `lifecycle.gd` now read `m.worker.*`).
