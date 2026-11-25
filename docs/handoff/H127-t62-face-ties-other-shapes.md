### H127 — T62: face ties on shapes other than plain rectangular boards

Author: Gemini (integrator, gemini-cedar-1123-1844) | Date: 2026-11-23 | Status: open | For: either

References: T62, T14, I26b, I40, I49.

Touches: worker/plane_fit.py, worker/push.py, worker/test_properties.py, viewport/property_panel.gd, viewport/tools/push_tool.gd, viewport/tests/quick/properties.gd.

Why: I26b / I40 face ties currently apply only to plain rectangular stock (`Part::Extrusion` of `Part::Plane`). T62 extends face ties to non-rectangular boards (circles, closed line/arc profiles, boards with cuts/pockets) so pushing or linking any planar face up to another board's face stays live.

Note for the integrator: recheck this brief against `main` once H126 (T61) merges before marking it `open` — add exact `Today`, `Reading path`, `Request`, and `Checks` details from the post-T61 code.
