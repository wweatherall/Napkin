### H208 — Napkin's freecadcmd never saves over William's FreeCAD settings (T167)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-28 | Status: answered | For: codex | Item: T167

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

Architecture: viewport/worker_process.gd owns the app's FreeCAD user and system config paths. Its launcher seeds user.cfg from the macOS FreeCAD profile on first use, then passes the app-owned paths on every start. Each test process uses paths in its own output folder.

Response — Codex, 2026-11-28: Worked on `codex/h208-freecad-settings-kept` (`8f08dd8`, tested after bringing main into the job branch at `66ff5b1`). The app passes explicit `-u` and `-s` under `user://freecad/`. It seeds `user.cfg` from the macOS FreeCAD profile once, with a log-only fallback to FreeCAD defaults when the source is unavailable. Test processes and the source-launcher version check use separate scratch configs. `tools/job.py` delegates to the test scripts and has no direct FreeCAD command to change.

- FreeCAD 1.1.4 wrote both `App.ParamGet(...).SetBool` probe values to scratch configs on exit. The desktop configs had the same mtimes before and after that probe.
- `tools/BUILD_THE_APP.sh` built the signed bundle. In a scratch home, its `worker.log` showed the worker listening on port 43808 and the app's `freecad/user.cfg` contained the seed marker.
- `tools/test_freecad_user_cfg.py` passed all 12 checks, including both launch flags, an absent source and destination, a single log line, and preservation of the existing copy. The named typed-length tool regenerated 2,521 cases with a byte-for-byte match.
- Recorded quick test passed on `66ff5b1`. The full merge gate passed with 405 viewport checks, zero failures and a passing field audit. An earlier gate overlapped H211's unflagged FreeCAD processes, so the timestamp check was repeated after they exited. Before and after the final gate, the desktop `v1-1/user.cfg` mtime was `2026-11-28 07:56:01.832355814 CST`, and `system.cfg` was `2026-11-28 07:56:01.831326073 CST`. Both SHA-256 hashes matched before and after.

Changed from the brief: `tools/RUN_ONE_TEST.sh` now calls the shared feature test launcher so its direct runner uses the same private config paths.

Changed from the brief: `worker/test_link.py`, `worker/test_length_protocol.py`, `worker/test_model_units.py`, `worker/test_outside_save.py`, and `worker/test_serve.py` also start FreeCAD. Their calls now use a common helper with private config paths per process.

Changed from the brief: `worker/test_floor_copy.py` explicitly disables backups during its external-edit fixture. Its file-count checks had depended on the desktop FreeCAD preference.

Changed from the brief: `tools/test_named_scripts.py` expects the named length-case tool in its help text, which now documents the isolated entry point.

Result: 8f08dd8; recorded quick test, full merge gate (405 viewport checks), 12 config checks and signed bundle smoke passed; isolated all FreeCAD command-line launches and verified the desktop settings files kept their timestamps and contents.
