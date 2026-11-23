### H052 — T66: lengths shown in the model's units

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H083) | For: either

References: T66, I57 (the Units menu, rounding, ~, saved per model), I59 (bare numbers typed are in the model's
units), I35 and T32 (typing lengths), P21 (viewport vs FreeCAD answers: tests/length_cases.json), Q22.

Touches: viewport/units.gd and viewport/test_units.gd (formatting), viewport/measure_box.gd (display, default_unit),
every viewport/tools/*_tool.gd's vcb_value (a length, not a string in mm), viewport/main.gd (the Units menu only),
worker/session.py (the units in the .FCStd's Meta, beside ShopSketchRev) and worker/serve.py (open / set_units),
docs/protocol.md and both PROTOCOL_VERSIONs if a message changes, a new quick section, ARCHITECTURE.md.
Waits for T88's tool moves (H051 and the per-tool jobs touch every tool file); written now so the answers are kept.

Request: build I57 and I59. Feet and inches 8' 3 1/4", inches as fractions 99 1/4", as decimals 99.25", metric m /
cm / mm, each with its rounding; default fractional inches at 1/16"; ~ in front of a length rounding changed; the
choice saved in the model, a new model starting with the last units used (user://settings.cfg); a bare typed number
in the model's units. Display only: ops stay in exact mm. Checks: unit tests for every format and rounding (and the
~), a round-trip check that what the box shows parses back to the same rounded length through units.gd and
FreeCAD's length_input (P21), a worker test that the units survive save and reopen, a quick section that switches
units and reads the box.
