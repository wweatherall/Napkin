### H204 — Rename everything to Napkin: the app, its files, the names saved inside models, and the tools (T139, P51)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: queued (after H199) | For: gemini | Item: T139 | Completes: T139

References: P51 (the app is named Napkin, replacing Shop Sketch and FretchUp), T139 (William, 2026-11-26: change every
name, including the .shopsketch.json files and the names stored inside .FCStd files; existing models must still open;
run it with no other job in progress; icon: a bench or cube drawn on a napkin), William, 2026-11-27 ("we need to do
another purge of the Shop Sketch name"), A43 (no shims: the one-time updater from H199 converts saved files), P73.

Touches: 01_Principles/principle_ratings.json, 01_Principles/ranking.md, 04_Napkin_Drawings/README.md, AGENTS.md, ARCHITECTURE.md, CLAUDE.md, FREECAD_FEATURE_MAP.md, GEMINI.md, README.txt, Start Shop Sketch.command, docs/follow-ups.md, docs/integrator.md, docs/protocol.md, docs/specs/U01-history.md, docs/spikes/t38/REPORT.md, docs/spikes/t38/spike.py, examples/holed_panel.shopsketch.json, examples/stool_session/ops.json, tests/legacy_one_file/model.shopsketch.json, tests/reference/movetest/status.json, tools/BUILD_THE_LAUNCHER.sh, tools/README.md, tools/build_app.sh, tools/featuretest.sh, tools/fulltest.sh, tools/gate.sh, tools/integrate.py, tools/integrator.py, tools/job.py, tools/parsecheck.sh, tools/quicktest.sh, tools/sort_decision_log.py, tools/startup.py, tools/test_featuretest.py, tools/test_integrate.py, tools/test_integrator.py, tools/test_job.py, tools/test_startup.py, tools/test_test_scope.py, viewport/document.gd, viewport/history.gd, viewport/main.gd, viewport/model_files.gd, viewport/project.godot, viewport/save_prompts.gd, viewport/test_document.gd, viewport/test_units.gd, viewport/tests/quick/outside_save.gd, viewport/tests/quick/preferences.gd, viewport/tests/quick/protocol.gd, viewport/tests/quick/units.gd, viewport/tests/quick/worker.gd, viewport/units.gd, viewport/worker_process.gd, worker/CLAUDE.md, worker/common.py, worker/export.py, worker/materials.py, worker/model.py, worker/plane_fit.py, worker/replay.py, worker/scenario/context.py, worker/serve.py, worker/session.py, worker/test_combos.py, worker/test_field_audit.py, worker/test_floor_copy.py, worker/test_generations.py, worker/test_link.py, worker/test_model_units.py, worker/test_native.py, worker/test_outside_save.py, worker/test_properties.py, worker/test_serve.py, examples/, tests/legacy_one_file/, tests/reference/, 04_Napkin_Drawings/, worker/update_old_files.py (new in H199),
worker/test_update_old_files.py (new in H199), tools/icon.svg (removed: tools/napkin_icon.svg becomes the app's icon
too).

Also in the comitatus repo (not in Touches: the check reads Napkin paths): 09_Tools/MEASURE_TOKEN_USE.py and
09_Tools/test_measure_token_use.py (the usage file's name).

Reading path:
1. `git grep -i -n -E "shop ?sketch|fretchup"` for every place; `git ls-files | grep -i shopsketch` for the three files
   named after it.
2. worker/session.py: the Meta keys saved inside each .FCStd (ShopSketchOps, ShopSketchRev, ShopSketchJournal,
   ShopSketchUnits, ShopSketchFloor, ShopSketchContentSha) and the legacy `<model>.shopsketch.json` sidecar.
3. tools/job.py and its neighbours: `.git/shopsketch-*` state files (the job queue, the hopper pid, usage) and the
   SHOPSKETCH_* environment variables.
4. tools/build_app.sh (dist/Shop Sketch.app, bundle id local.shopsketch) and tools/BUILD_THE_LAUNCHER.sh (it opens it).

Today (checked 2026-11-27): 307 "Shop Sketch", 145 "shopsketch" and ~280 ShopSketch*/SHOPSKETCH_* names in 78 tracked
files, plus the three file names and the Meta keys inside every saved .FCStd.

Request:
1. Every name says Napkin, in the forms the code already uses: "Napkin" in text and window titles, `napkin` in file
   and folder names, `Napkin<Thing>` for Meta keys (NapkinOps, NapkinRev, ...), `NAPKIN_*` for environment variables
   (NAPKIN_SPACE already exists), `.git/napkin-*` for state files, dist/Napkin.app with bundle id local.napkin and
   tools/napkin_icon.svg as its icon. "Start Shop Sketch.command" becomes "Start Napkin.command".
2. History stays as it was written: the archives (docs/handoff-archive.md, docs/protocol-archive.md), the rulings
   and Work list files in 03_Past_Decisions/, past handoff briefs and proposals keep the old name where they quote
   what was true then.
3. Saved files: the updater (H199) gets one more rule, renaming the Meta keys and the `.shopsketch.json` sidecar;
   run it on examples/, tests/legacy_one_file/, tests/reference/, 04_Napkin_Drawings/ and the app's working file in
   models/, and commit the results. Opening a file that still holds old keys is H199's normal "older Napkin" rejection.
4. The job queue's state files move to their new names in one step that keeps their contents (G09): job.py reads the
   new name and, if only the old file exists, renames it first; that one-line move may stay until William says
   otherwise, since the queue is live while this job runs. The usage file's name changes in the comitatus repo's
   09_Tools/MEASURE_TOKEN_USE.py too (a comitatus branch, merged first, as H195 did).
5. Afterwards `git grep -i -E "shop ?sketch|fretchup"` finds only the history in item 2 and the updater's rule.

Not in this job: the code base's own folder names (T135), Napkin's behaviour.

What can fail:
- A model that no longer opens because a Meta key was renamed in the code but not in the file (G09). Check: every
  example and reference model opens and rebuilds to the same bodies before and after; a copy of an old-format file
  is refused with the "older Napkin" message, then opens after the updater runs on it.
- The live job queue lost when its file is renamed while the hopper runs. Check: a test starts from only the old
  state file and finds every job afterwards; the integrator restarts the hopper after the merge.
- Preferences and units saved under the old name (user://, ~/Documents/Shop Sketch) left behind. Check: say in
  `Changed from the brief:` where each lives and whether it moves.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); the full field audit passes; `tools/BUILD_THE_APP.sh` builds
  dist/Napkin.app and it starts.
