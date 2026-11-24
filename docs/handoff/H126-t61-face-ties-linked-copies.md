### H126 — T61: face ties on linked copies (component definitions and instances)

Author: Gemini (integrator, gemini-cedar-1123-1844) | Date: 2026-11-23 | Status: queued (after H125) | For: either

References: T61, T14, I26b, I40, A22c.

Touches: worker/plane_fit.py, worker/model.py, worker/test_properties.py, viewport/property_panel.gd, viewport/tools/push_tool.gd, viewport/tests/quick/properties.gd.

Why: I26b says linked copies follow together (the tie belongs to the shared definition), so editing a shared copy's fitted end or moving the target carries all instances of the component, and making a copy unique detaches its shared tie cleanly.

Note for the integrator: recheck this brief against `main` once H125 (T60) merges before marking it `open` — add exact `Today`, `Reading path`, `Request`, and `Checks` details from the post-T60 code.
