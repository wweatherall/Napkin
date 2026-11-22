### H042 — T70: a late worker reply can't replace a newer state

Author: Claude (integrator) | Date: 2026-11-22 | Status: open | For: Claude

References: T70, U02 (its last clause), W13; docs/protocol.md findings 2 and 4 (lifecycle replies reach sync
logic; an open reply has no seq); viewport/document.gd `send_open`, `on_opened`, `on_sync_reply`;
viewport/main.gd `_on_worker`, `_on_open`; worker/serve.py `handle`.

Touches: viewport/document.gd, viewport/main.gd (`_on_worker` and `_on_open` only), worker/serve.py (`handle`:
echo seq on open and lifecycle replies), viewport/test_document.gd, a new worker/scenario or a check in
worker/test_serve.py, docs/protocol.md (findings 2 and 4: mark fixed; the reply fields), ARCHITECTURE.md if the
protocol section names reply fields. Not viewport/tools/* (H040), not viewport/tests/suites/* or harness.gd (H039).

Request: every worker reply the window acts on can be matched to the request it answers, and one that answers
an older request is ignored. (1) `open` echoes the request's seq and model; the window drops an open reply for a
model it has since left, or older than its latest open. (2) `_on_worker` routes flush / hello / bye / quit replies
by cmd, so they never reach `on_sync_reply`. (3) Sync already does this by seq: check it holds when a reply
arrives after a model switch. This is a protocol change: bump the reference version in docs/protocol.md. Checks:
a stale open after a quick A → B switch is ignored (headless document test), a flush reply doesn't touch sync
state, the serve test sees seq echoed.
