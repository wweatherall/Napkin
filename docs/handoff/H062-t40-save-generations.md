### H062 — T40: the model and its journal saved as one generation

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: Claude

References: A32 (Active: William's call, 2026-11-22, with the file arrangement), G09 (never lose work), A24 (the
journal), T79 / I54 (failed saves already shown and retried), A35 (PROTOCOL_VERSION).

Touches: worker/session.py (save, _write, _open_existing), worker/serve.py (only the open reply), a new
worker/test_generations.py, viewport/document.gd and viewport/main.gd (only to show a recovery once: a small
edit), viewport/test_document.gd, docs/decision-log.md (A32's "Where in the code"). Not docs/protocol.md or
ARCHITECTURE.md: H046 (Codex) has them; give their new text as "For the integrator:" lines (the reply's field,
the save/open steps), and the integrator puts it in the merge commit. Say so in your commit's Architecture-Impact
line.

Request: build A32. Today the .FCStd is swapped in (os.replace) and then the journal is written: a crash between
the two leaves a file and journal that don't match, and the model opens as "external" with its history behind an
undo floor.
1. Save: write `<model>.saving.FCStd` and `<model>.shopsketch.saving.json` (the journal names the new file's
   sha256 and rev); then keep the current pair as `<model>.prev.FCStd` / `<model>.shopsketch.prev.json`; then
   rename both new files into place. Until both renames are done, the .prev pair is whole. A failed save keeps
   today's behaviour (save_failed, revision held back, retried; T79).
2. Open: if the file and journal match (rev and sha256), use them (as today). If not, and the .prev pair matches
   each other, and the current file is one Shop Sketch was mid-saving (its ShopSketchRev is the journal's rev + 1,
   or the journal is newer than the file, or one of them is missing), open the newest whole pair and report it.
   A file FreeCAD changed (no Shop Sketch rev bump) is still "external", as today (A25): don't mistake an outside
   edit for a broken save. Never delete either pair while opening.
3. Report: the open reply carries `recovered: {"from": "prev", "rev": N, "why": "..."}` when it fell back; the
   viewport shows it once in the save indicator (e.g. "Recovered the last whole save (rev N)"). Bump
   PROTOCOL_VERSION on both sides (A35).
Checks (worker/test_generations.py): a normal save leaves both pairs, matching; a crash after the .FCStd rename but
before the journal's opens the .prev pair (or the whole new one, whichever is complete) and reports it; a missing
journal; a file edited by FreeCAD stays external with no recovery; the reply's field; test_document.gd shows the
message once. Quick test, then the gate. End your response with a Result line; leftovers as Follow-up lines;
anything for the merge as For the integrator lines.
