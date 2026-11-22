### H043 — T85: the quick test's hide check fails on main

Author: Claude (integrator) | Date: 2026-11-22 | Status: open | For: Claude

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
