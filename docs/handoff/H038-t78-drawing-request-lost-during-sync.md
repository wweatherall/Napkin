### H038 — T78: a drawing request made while a sync is in flight is lost

Author: Claude (integrator) | Date: 2026-11-22 | Status: open | For: Codex

References: T78; docs/protocol.md finding 3; viewport/document.gd `request_drawing`, `_send`, `on_sync_reply`.

Touches: viewport/document.gd, viewport/test_document.gd (headless, in the feature tests), docs/protocol.md
(finding 3: mark it fixed). Not viewport/main.gd (H036 is moving code out of it).

Request: when `request_drawing()` arrives during a sync, remember it, and send `drawing: true` with the
follow-up sync. Add document-test checks for: the request while idle (as today), the request during a sync
(the follow-up carries drawing), and a request that is answered once (the flag clears after it's sent).
