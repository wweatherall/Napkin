### H170 — One name per meaning for message numbers: `seq` for the model's state, `request_id` for the request

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: queued (after H169) | For: gemini

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
