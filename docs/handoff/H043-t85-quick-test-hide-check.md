### H043 — T85: the quick test's hide check fails on main

Author: Claude (integrator) | Date: 2026-11-22 | Status: answered | For: Claude

References: T85, P07; viewport/tests/quick/hide.gd (the check at "View > Hidden geometry shows it ghosted"),
viewport/selection.gd `toggle_hidden_geometry`, viewport/presenter.gd (where `mat_hidden_ghost` is applied).

Touches: viewport/tests/quick/hide.gd, viewport/tests/quick/selection_row.gd (if its occasional failures share the
cause), viewport/tests/harness.gd. Read-only on selection.gd, presenter.gd and main.gd: H041 (the Circle tool) is
changing presenter.gd and main.gd. If the cause is in app code rather than the test, stop and report it in the
handoff before changing anything.

Request: `[hide] View > Hidden geometry shows it ghosted` fails on every quick test since at least 2026-11-22 01:00,
on main back to 8ff1f91, though workers saw it pass the evening before. b1's material_override is null, so the H
press before it didn't hide b1 (the click on b1 then H, in hide.gd). Find out why: the test's timing, the click
missing b1, or something in the environment (it passed before on the same code). Also seen once: four
`[selection_row]` checks failing together. Done when 5 quick tests in a row pass with no hide failure. Report what
the cause was.

**Response — Claude, 2026-11-22.** Branch `claude/h043-hide-check`. Cause: the test, not the app. `main.gd`'s
`_menu` drops a repeat of the same command within 150 ms (so a menu item and its key don't both fire). hide.gd
presses H, then (wave, drag, Cmd+Z, wave, click) H again; instrumented, the gap at the click was 190–270 ms, and on
a fast run the second H fell inside 150 ms and was thrown away: b1 selected, never hidden, material_override null.
Passing runs were the slower ones (16–21 s), which is why it looked environmental. The `[selection_row]` cluster
fits the same cause (Backspace → `_menu("delete")` right after the previous lap's Backspace); not reproduced in
these runs. Fix (test only): `harness._menu_settle()` waits until no command fired in the last 160 ms; every
`_key*` helper calls it, and hide.gd's direct `m._menu(...)` calls go through `harness._menu(tag)`. No app code
changed. Verified: `tools/quicktest.sh` 6 runs in a row, no hide failure (5 × 153/153; the 6th 152/153, see below).
Architecture sections changed: none.
Still open: (1) `[worker] a new worker took over and confirmed the next board` fails intermittently, on main
before this change too (shown ids `["b1","b3"]`, no b9); outside this job's files (worker.gd). (2) Capturing a
quick test's output with `$(...)` sometimes never returns, as if a process from the run outlives it holding stdout
(perhaps the worker the `[worker]` lap restarts); a plain run redirected to a file takes 17 s. Both worth a Work
list item. (3) linked.gd calls `m._menu("detach")` directly; harmless now, but could use `harness._menu`.
