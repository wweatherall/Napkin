### H208 — Napkin's freecadcmd never saves over William's FreeCAD settings (T167)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-28 | Status: open | For: codex | Item: T167

References: T167 (William, 2026-11-28: "my FreeCAD settings appear to be gone"), G09 (never lose work: his settings
are his work too), A41 (`worker/session.py` `no_backups`, which already restores the one setting Napkin changes),
FreeCAD 1.1.4 `freecadcmd --help`: `-u [ --user-cfg ] arg  User config file to load/save user settings`.

Today: FreeCAD keeps its preferences in `~/Library/Preferences/FreeCAD/v1-1/user.cfg`. Every `freecadcmd` loads that
file at start and writes it back at exit. Napkin starts many: the app's worker (`viewport/worker_process.gd`, two
`OS.create_process` calls near line 171), each test lane's worker, and the feature/full tests (`tools/featuretest.sh`
and `tools/fulltest.sh` `FC=`, `common.sh`, `tools/length_cases.py`, `tools/job.py` where it runs one). On
2026-11-28 the file was rewritten at 01:20 with no FreeCAD window open; a `freecadcmd` that started before William
changed a setting in FreeCAD, and exited after, writes its stale copy over his change.

Touches: viewport/worker_process.gd, tools/featuretest.sh, tools/fulltest.sh, tools/length_cases.py,
tools/job.py (only where it builds a freecadcmd command line), worker/CLAUDE.md (a short trap note; also the top-level common sh script), tools/test_freecad_user_cfg.py (new; or a check added to an existing tools test).

Request:
1. Every `freecadcmd` Napkin starts passes `-u <file>` (and `-s <file>` for system.cfg) pointing at Napkin's own copy,
   so FreeCAD never writes William's file: for the app, `user://freecad/user.cfg` (resolved with
   `ProjectSettings.globalize_path`); for tests, a file in the run's own scratch/out folder. Its purpose: nothing
   Napkin runs can change the preferences William set in FreeCAD.
2. Napkin's copy starts as a copy of William's `v1-1/user.cfg` when that exists and Napkin's copy doesn't (so the
   worker sees the same units and document settings he chose), and is never copied back.
3. Check by hand that `-u` is honoured by `freecadcmd` 1.1.4 (run one with `-u scratch/u.cfg`, change a parameter
   with `App.ParamGet(...).SetBool`, exit, and confirm William's file's mtime is unchanged and the scratch file has
   it). Put what you saw in the response. If `-u` isn't honoured, stop and say so: don't build a workaround.
4. Add a one-line trap to `worker/CLAUDE.md`: launch freecadcmd only through these paths, always with `-u`.

What can fail (P42):
- The copy can't be made (William's file missing or unreadable): start the worker with an empty Napkin copy, say
  nothing to the user, and log one line in worker.log. Check: the test runs the launcher's copy step with a missing source.
- `user://freecad/` doesn't exist yet: the launcher creates it. Check: the same test, from an empty folder.
- An app built into `dist/Napkin.app` (A30): the same path works from the bundle. Check: say in the response that
  you ran `tools/BUILD_THE_APP.sh` and the app's worker started (worker.log shows its port).

Checks:
- A named check that every freecadcmd command line in the files above carries `-u` (a grep-style test in tools/ is
  fine: it fails if a new launch site is added without it).
- `tools/TEST_BEFORE_MERGING.sh` passes.
- The response says William's `v1-1/user.cfg` mtime before and after a full gate run (unchanged).
