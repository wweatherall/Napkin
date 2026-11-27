### H172 — status.json written only by one-off replays, not on every edit in the app

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 (protocol.md walk-through, Shared files: "Ok do it"), comitatus principle C07
(token and time efficiency), P07 (feature tests replay op logs with no window).

Touches: worker/serve.py (`run_sync`), worker/replay.py, docs/protocol.md (its status-file paragraph and
"Publication and locations" only), worker/test_serve.py.

Reading path:
1. worker/serve.py `run_sync` (line ~32: `atomic_json(os.path.join(outdir, "status.json"), result)`), and `main` (serve
   mode with `SERVE_PORT`; one-off replay with `OPLOG` / `OUTDIR`).
2. worker/replay.py docstring; tools/compare_suites.py lines ~26-27 and tools/fulltest.sh line ~84 (they read the
   replay's status.json); worker/drawing.py line ~24 (reads a replay's OUTDIR).

Today (checked 2026-11-27): `run_sync` writes status.json into the output folder on every sync, in the app as in
replays. Nothing in the app reads it: the window gets the same result in the sync reply. Its readers are the
one-off replay's: tools/compare_suites.py and tools/fulltest.sh (the reference results) and worker/drawing.py.

Request: write status.json only in one-off replay mode (no `SERVE_PORT`), exactly as today there; a serve-mode sync
no longer writes it. protocol.md's `status.json` paragraph and "Publication and locations" say so. Nothing else
changes: same file, same contents, in replays.

What can fail:
- A reference test that reads status.json from a serve-mode run: `tools/fulltest.sh` and compare_suites pass
  unchanged. Check: the full gate.
- An old status.json left in an app output folder: harmless (nothing reads it); leave it.

Checks:
- worker/test_serve.py: a serve-mode sync leaves no status.json in its outdir; a one-off replay still writes it,
  with the same fields as before.
- `python3 tools/protocol_map.py --check`; `tools/TEST_BEFORE_MERGING.sh` passes (full scope).

Response (gemini-maple-1127-0833):
- `worker/serve.py`: `run_sync` now writes `status.json` only when `SERVE_PORT` is unset (one-off replay) or `SERVE_STATUS_FILE=1`.
- `worker/replay.py`, `docs/protocol.md`: updated `status.json` publication notes in `sync`, `Publication and locations`, and `status.json`, `views.json`, startup port file.
- `tools/fulltest.sh`: exports `SERVE_STATUS_FILE=1` when starting lane workers so `compare_suites.py` and `--update-reference` still receive `status.json`.
- `worker/test_serve.py`: added checks that serve mode without `SERVE_STATUS_FILE` writes no `status.json`, serve mode with `SERVE_STATUS_FILE=1` writes `status.json` matching the `sync` result, and one-off replay writes `status.json` with the expected fields.

Changed from the brief:
- Added `SERVE_STATUS_FILE=1` opt-in in `worker/serve.py` and exported it in `tools/fulltest.sh` (outside `Touches`, approved via `job.py wait --scope`: "Keep it opt-in: run_sync writes status.json in serve mode only when the environment has SERVE_STATUS_FILE=1 (one-off replays always write it, as today). tools/fulltest.sh exports SERVE_STATUS_FILE=1 where it starts its workers; you may touch tools/fulltest.sh for that one line. compare_suites.py and viewport/ stay as they are. protocol.md says it in one sentence. test_serve.py: serve mode without the variable writes no status.json; with it, the same file as before. Name it in a Changed from the brief line.").

Result: `python3 tools/protocol_map.py --check` passed; `tools/TEST_BEFORE_MERGING.sh` passed (`GATE PASS: full test passes; QUICK 401 passed, 0 failed in 24.7 s ; 0 known failure(s); 71 s total`).
