### H062 — T40: the model and its journal saved as one generation

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: Claude

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

**Response** — Claude (worker, session ece2cf8a), 2026-11-22

Branch `claude/h062-t40-save-generations`, commit c949c0a. Quick test and gate pass (GENERATION TESTS 26/26, new;
DOCUMENT TESTS 70, 5 new).

1. Save (`Session._write`, names from `generation()`): the new file goes to `<model>.saving.FCStd`, then its
   journal (with the new file's sha256 and rev) to `<model>.shopsketch.saving.json`; the current pair is kept as
   `<model>.prev.FCStd` / `<model>.shopsketch.prev.json` by hard link (instant, a copy where links fail); then the
   new file and the new journal are renamed into place. Since .prev is linked, not moved, the current pair stays
   whole until its file is renamed over, so there's a whole pair at every step. Checked that FreeCAD saves by
   rename, not in place, so a FreeCAD edit can't change .prev through the link. A failed save is as before (T79):
   raises, rev held back, the .saving files removed, retried.
2. Open (`recover_generation()`, before the document opens): a matching file and journal open as today. Otherwise
   it recovers only if the file looks mid-save: its ShopSketchRev is the journal's + 1, or the journal is newer, or
   one of them is missing. Then the newest pair (by rev) among {file, .saving, .prev} × {journal, .saving, .prev}
   whose journal names its file's sha256 is copied into place. A FreeCAD edit (same rev, other sha) is external
   with no recovery (A25). Nothing of either pair is deleted: a displaced file goes to
   `<model>.unmatched.FCStd` / `.shopsketch.unmatched.json`, unless the same bytes are kept elsewhere.
3. Report: `open_reply()` (serve.py) adds `recovered: {"from": "new"|"prev", "rev", "why"}`, once per session.
   "new" means it finished a save that stopped part way (the crash between the two renames); "prev" means it fell
   back to the save before. The save indicator shows "Recovered the last whole save (rev N)" or "Finished the last
   save (rev N)" until the next save lands. PROTOCOL_VERSION 3 → 4 on both sides.

Choices of mine that are worth a look: the .unmatched names; finishing a save from the new pair (better than the
.prev the request named, when that pair is whole); a missing journal with a whole .prev pair opens .prev (as the
request says), so the journal-less newer file is kept as .unmatched rather than opened external.

Commit check: committed with P28's interim line (Architecture-Impact: none - ... Architecture: lines; T100 not
built), as the integrator said, after William's P28.

Architecture: ARCHITECTURE.md § saving (~line 254): `Session.save()` writes the new FCStd and its journal under the .saving names (the journal names the new file's sha256), keeps the current pair as .prev (hard link), then renames the file and then the journal into place; a whole pair exists at every step (A32).
Architecture: ARCHITECTURE.md § saving (~line 256), replacing "the FCStd and journal are not one atomic multi-file transaction ...": opening runs `recover_generation()`: a mismatch where the file looks mid-save (ShopSketchRev = journal rev + 1, journal newer, or one missing) puts the newest whole pair in place and reports it; a FreeCAD edit (same rev, other hash) stays external with an undo floor (A25); displaced files go to the .unmatched names, never deleted.
Architecture: ARCHITECTURE.md module table, `worker/session.py` row: add "save generations and recovery (A32)" and `recover_generation`, `generation` to its entry points.
Architecture: docs/protocol.md, open reply: optional `recovered: {"from": "new"|"prev", "rev": N, "why": "..."}`, sent once when opening recovered a save that stopped part way (A32); PROTOCOL_VERSION 4.

Follow-up: worker/CLAUDE.md's "Autosave is atomic" bullet could name the generation files (.saving, .prev, .unmatched); outside this job's Touches.
Follow-up: the .unmatched files are never cleaned up (overwritten by the next recovery); fine while recoveries are rare.

Result: c949c0a; quick test and gate pass (GENERATION TESTS 26/26, DOCUMENT TESTS 70/70); saves write a .saving pair, keep .prev, then rename in; opening recovers the newest whole pair after a broken save and reports it once (A32)
