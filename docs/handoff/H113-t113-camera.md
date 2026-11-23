### H113 — T113 step 4c: the camera (orbit, pan, zoom, trackpad) moves out of main.gd into camera_rig.gd

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

References: T113, P45, Q4, I63 (the feel tunables, wired by H103).

Touches: viewport/camera_rig.gd (new), viewport/main.gd (`_zoom`, `_update_camera`, the camera's state vars, the
camera branches of `_unhandled_input`), viewport/tests/harness.gd, viewport/tests/suites/*.gd (only
`m._update_camera` calls: breath, heavy, zfight, fx, line, gesture, model), viewport/tests/quick/trackpad.gd.
`_input` / `_unhandled_input` stay in main as the entry points (tests call `m._unhandled_input`) and
`_repeat_gesture` with them.

Why (P45, T113): main.gd (~2,130 lines) is the file every job meets; moving whole sections out lets jobs run side by side and makes it easier to read. Behaviour unchanged: nothing William would notice changes, no message, file or saving changes. A filler job: Ready when nothing else holds its files.

Rules for every T113 step (each says what it is for, P44):
- Move the code, don't rewrite it: same names minus the leading `_` where callers outside the new file now need them, same comments, so `git diff --color-moved` shows a move and review is quick.
- No forwarders left in main.gd for the moved names (the point is a thinner main): callers, tests included, call the new object. Keep a forwarder only where a caller can't be changed in this job (say which in your response).
- The new file is a plain `RefCounted` (or `Node` if it needs `_process`/timers/dialogs as children) made in main like `keys` and `measure` (`load("res://<file>.gd").new()`, given `self`), no `class_name` (viewport/CLAUDE.md).

Today (checked 2026-11-22): main.gd ~2015-2131 holds input dispatch and the camera; eight suites and harness.gd
call `m._update_camera`. H103 wires the feel tunables from preferences; re-read how the camera reads them after
it merges, and keep reading them the same way.

Request: camera_rig.gd as `m.cam` owns the orbit / pan / zoom state and their tunables' use; main's
`_unhandled_input` hands camera events to it. Picking (tool_move, tool_click) stays in main.

Cases that must still work: orbit, pan, zoom (mouse and trackpad), a recorded suite's camera (the recorded
suites compare with tests/reference/: no change); I11 (orbiting mid-operation doesn't change its target).

Checks: the gate with no change to tests/reference/; quick test trackpad; `wc -l viewport/main.gd` before and
after.

Run the feature tests while building (`tools/featuretest.sh`), the quick test after each change, then `python3 tools/job.py test`. End your response with a Result line; leftovers as Follow-up lines; the folder-guide change (viewport/CLAUDE.md's Files list) as a For the integrator line.

#### Response — Codex, 2026-11-23

Branch `codex/h113-t113-camera`, implementation commit `5108f56`. `main.gd` went from 2,224 to 2,182 lines.
Feature tests, the full gate, and `job.py test` passed. The quick test passed all 287 checks, including trackpad
and live preferences. All six recorded suites matched their references. The standalone gesture and mouse-pan
checks passed. In the orbit suite, FreeCAD confirmed all four ops and the second board started on the original
+X face and extended 250 mm along +X (I11). No decision-log rows added or open behaviour questions.

Changed from the brief: Use the requested camera controller as `m.camera_rig` because `m.cam` already holds the
scene Camera3D and has projection callers outside the Touches list. The existing preferences wiring and its
quick test still use main's aliases for the two tunables, their defaults, yaw, and distance.
Architecture: `viewport/camera_rig.gd` is a RefCounted controller (`m.camera_rig`) that owns the orbit target,
angles, distance, drag state, and live trackpad and wheel tunables. It updates the scene Camera3D and grid fade.
`main.gd` owns the scene nodes, applies preferences, filters and dispatches input, and handles tool picking.
Follow-up: To remove the preference aliases, point main's preference wiring and `tests/quick/preferences.gd` at
the rig when those files are in scope.
For the integrator: In `viewport/CLAUDE.md`'s Files list, add `camera_rig.gd` (`m.camera_rig`) for orbit, pan,
zoom, and live trackpad and wheel tuning. Note that `main.gd` dispatches camera input and owns the scene Camera3D.
Result: 5108f56; gate passed with 287 quick checks and six reference matches, job.py test passed, gesture, mouse pan and I11 orbit passed; camera input and state moved into camera_rig.gd
