### H035 — T44: write the window ↔ worker protocol down (docs/protocol.md)

Author: Claude (integrator) | Date: 2026-11-21 | Status: open | For: Codex (a second session, or after H034)

References: T44, W13, A27, A29; ARCHITECTURE.md line ~290 (already points at T44).

Touches: docs/protocol.md (new), ARCHITECTURE.md (one link line where it mentions T44; nothing else),
docs/decision-log.md (the T44 row only). Read-only on code.

Request: every command and reply (hello, open, sync, replay, flush, bye, quit, saved, focus, and any others the
code has), with fields, types, units and an example; the files the worker writes (bodies.json, meshes,
materials.json, model.glb, the journal) and their fields; a protocol version number. Take it from the code
(worker/replay.py and the worker modules, viewport/document.gd and the worker link in viewport/), not from
memory or older docs, and cite file:function for each message. List any mismatches you find between the two
sides as findings; don't fix code in this job.
