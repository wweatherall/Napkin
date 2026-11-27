### H172 — status.json written only by one-off replays, not on every edit in the app

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: open | For: gemini

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
