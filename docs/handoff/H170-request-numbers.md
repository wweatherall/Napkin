### H170 — One name per meaning for message numbers: `seq` for the model's state, `request_id` for the request

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 ("Sounds fine add it to the board", on unifying the message numbers), A35 (a
changed message bumps PROTOCOL_VERSION on both sides), H169 (the generated message list and its check).

Touches: worker/length_input.py (`handle`), worker/serve.py (`PROTOCOL_VERSION`), viewport/main.gd
(`PROTOCOL_VERSION`, `_on_worker`'s length branch), viewport/measure_box.gd (the `length` send and its reply check),
docs/protocol.md (`length` and the Types, units and correlation section), worker/test_length_input.py,
worker/test_serve.py, viewport/tests/ (any test that sends or checks a length `id`).

Reading path:
1. docs/protocol.md `## Types, units and correlation` (what `seq` means) and `### length`, `### inspect_properties`.
2. viewport/measure_box.gd around `m.client.send({"cmd": "length", "id": length_id, ...})` and where its reply is
   matched; viewport/main.gd `_on_worker` (`resp.get("cmd") == "length"`), `_request_properties`, `_on_properties`.
3. worker/length_input.py `handle` (echoes `id`).

Today (checked 2026-11-27): three numbers travel on requests. `seq` is the document's sync number: it says *which
state of the model* a reply is about, and the window drops a reply about an old state. `inspect_properties`
carries `seq` and also `request_id` (which Properties request this answers). `length` carries neither: its own
`id`, which is also the word every op uses for its ID (`"id": "pp1"`). So `request_id` and length's `id` mean the
same thing under two names, and `id` means two things.

Request: length's `id` becomes `request_id` on the request and the reply (worker and window), so `seq` always means
the model's state, `request_id` always means "which request of mine is this", and `id` only ever names an op.
Bump PROTOCOL_VERSION to 16 on both sides (A35). protocol.md says the rule once, in Types, units and correlation:
`seq` = state, `request_id` = request, `id` = op. Nothing a user sees changes.

Not in this job: `seq` on length requests, any other field or message.

What can fail:
- A window and a worker of different versions: the version check already makes the window start its own worker
  (a mismatched `hello`). Check: test_serve.py's version test still passes with 16.
- A typed length answered after a newer one was typed: still dropped (the reply check matches `request_id` as it
  matched `id`). Check: the measure box's existing stale-reply test, renamed.

Checks:
- worker/test_length_input.py, worker/test_serve.py, the viewport quick tests that type lengths.
- `python3 tools/protocol_map.py --check` (H169) passes.
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope).

### Response (Gemini, gemini-spruce-1127-0758, 2026-11-27)

Branch: `gemini/h170-request-numbers` | Commit: `b7549be`

- Renamed `length`'s correlation field from `id` to `request_id` on both request and reply: `worker/length_input.py` (`handle`), `viewport/measure_box.gd` (`length_pending`, `apply`, `on_length`), and `docs/protocol.md` (Types, units and correlation; `### length`; generated message table; moved `ARCHITECTURE.md` section).
- Bumped `PROTOCOL_VERSION` from 15 to 16 in `worker/serve.py`, `viewport/main.gd`, and `docs/protocol.md` (A35).
- Added `handle` `request_id` echo tests in `worker/test_length_input.py` and a stale-reply `request_id` test in `viewport/test_units.gd`.
- Verified: `python3 tools/protocol_map.py --check`, `tools/TEST_BEFORE_MERGING.sh` (`GATE PASS`, full scope, 401/401 quick tests, all feature tests and full suites), and `python3 tools/job.py test` on `b7549be`.
- IDs added: none. Open questions: none.

Changed from the brief: Touches listed `viewport/tests/` rather than `viewport/test_units.gd`, `worker/test_model_units.py`, and `worker/test_length_protocol.py`, and did not need an edit to `viewport/main.gd:_on_worker`; updated those three test files (plus the stale-reply test in `viewport/test_units.gd`) with integrator scope approval (`job.py wait --scope`: "Yes, both: viewport/test_units.gd and worker/test_model_units.py where they send or check a length id, plus the stale-reply test. Name them in a Changed from the brief line." and "Yes. And any other test that sends or checks a length id: update it without asking again, and list them all in your Changed from the brief line.").
Architecture: `length` now uses `request_id` (not `id`) for request/reply correlation (`seq` = model state, `request_id` = request, `id` = op), and `PROTOCOL_VERSION` is bumped 15 -> 16 in `worker/serve.py`, `viewport/main.gd`, and `docs/protocol.md`.
Result: b7549be; GATE PASS + job.py test (401/401 quick, 26/26 length, 3/3 length protocol, 29/29 serve, 22/22 worker units, 178/178 units); length uses request_id and PROTOCOL_VERSION 16
