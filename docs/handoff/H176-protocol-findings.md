### H176 — The two old protocol findings: drop the unused `replay` command, and one place for a session's name

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: answered | For: gemini

Item: T157
Completes: T157, T158

References: T157, T158 (protocol findings 6 and 7, in docs/protocol-archive.md), A35 (a changed message bumps
PROTOCOL_VERSION on both sides; it is 17), comitatus principle C03 (simplify), H169 (protocol_map.py --check).

Touches: worker/serve.py (`handle`'s `sync`/`replay` branch, `run_sync`, `PROTOCOL_VERSION`), viewport/main.gd
(`PROTOCOL_VERSION` only), viewport/document.gd (`oplog`), docs/protocol.md (the `sync` and `replay` section, the
StatusResult table), worker/test_serve.py.

Reading path:
1. docs/protocol.md `### sync and replay` and the StatusResult table.
2. worker/serve.py `handle` (`elif cmd in ("sync", "replay")`, `fresh=(cmd == "replay")`) and `run_sync`
   (`"oplog": req.get("name", "live")`); worker/replay.py's one-off path (it calls `run_sync` with a top-level
   `name`).
3. viewport/document.gd `oplog()` (`{"format": "oplog/0.1", "units": "mm", "name": "Shop Sketch session", ...}`).

Today (checked 2026-11-27): the worker accepts a `replay` command (sync on a fresh session), but nothing sends it:
no window, tool or test (`grep -rn '"replay"'`); the one-off replay mode is worker/replay.py with `OPLOG`, not this
command. The window sends the op list's name nested (`oplog.name`, and it is still the old name "Shop Sketch
session"), while the worker names the result from a top-level `name`, so every app sync reports `oplog: "live"`.

Request:
1. **Drop the `replay` command**: `handle` answers it as any unknown command (the generic error). The one-off
   replay mode (worker/replay.py, `OPLOG`/`OUTDIR`) is untouched.
2. **One place for the name**: the window stops sending `oplog.name`; `run_sync` keeps reading the top-level `name`
   (default `"live"`), so worker/replay.py's name still reaches status.json. protocol.md's oplog field list loses
   `name` and says the top-level `name` is the only one.
3. **Protocol 18** on both sides. protocol.md: the section becomes `### sync`; StatusResult's `oplog` row says where
   the name comes from.

Not in this job: `oplog.format` / `units` (still sent and checked as today), status.json (H172).

What can fail:
- Something did send `replay` after all: the grep above, quoted in the response, finds none outside serve.py.
- A one-off replay losing its name in status.json: test_serve.py or the replay test checks `oplog` is the file's
  name.

Checks:
- worker/test_serve.py: `replay` gets the unknown-command error; a sync without nested name works; protocol 18.
- `python3 tools/protocol_map.py --check`; `tools/TEST_BEFORE_MERGING.sh` passes (full scope).

Architecture: `worker/serve.py` drops the `replay` command from `serve.handle` (returning the generic unknown-command error), `viewport/document.gd:oplog()` drops nested `oplog.name` (top-level `name` is the sole session name source), and `PROTOCOL_VERSION` is bumped to 18 in `worker/serve.py` and `viewport/main.gd`.

Response (Gemini, gemini-maple-1127-0956, 2026-11-27):
- Branch: `gemini/h176-protocol-findings`
- Commit: `9c5f8a9`
- Verified:
  - `grep -rn '"replay"' . --exclude-dir=.git` before editing found no sender outside `worker/serve.py` (`tools/protocol_map.py:568`, `viewport/main.gd:832` reply check, `docs/protocol.md`, `docs/protocol-archive.md`, `docs/handoff/H176-protocol-findings.md`, `worker/serve.py:309,313`).
  - `python3 tools/protocol_map.py --check` passed.
  - `tools/TEST_BEFORE_MERGING.sh` (full scope) passed: `GATE PASS: full test passes; QUICK 401 passed, 0 failed in 60.4 s`.
  - `python3 tools/job.py test` on `9c5f8a9` passed: `SERVE TESTS: 34 passed, 0 failed`, `QUICK 401 passed, 0 failed in 55.4 s`.
- IDs added: none
- Open questions: none

Follow-up: `viewport/main.gd:832` still checks `resp.get("cmd", "") in ["sync", "replay"]` and `tools/protocol_map.py:568` still has `not (lit_cmd == "sync" and "replay" in cmds)`; both are harmless leftovers outside H176's Touches.

Result: 9c5f8a9; quick test passed (SERVE 34/34, QUICK 401/401), gate passed (full + QUICK 401/401), protocol_map --check passed; dropped replay command, removed nested oplog.name, bumped PROTOCOL_VERSION to 18
