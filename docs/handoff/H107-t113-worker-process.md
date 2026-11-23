### H107 — T113 step 1a: the FreeCAD worker's process moves out of main.gd into worker_process.gd

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H094) | For: either

References: T113, P45, A27, W13, A35, T47, viewport/CLAUDE.md "Worker (W13)".

Touches: viewport/worker_process.gd (new), viewport/main.gd (the section "the FreeCAD worker (T6)": its consts and
vars, `_free_port`, `_worker_files`, `_worker_identity`, `_port_free`,
`_probe_worker`, `_worker_of`, `_hello`, `_pick_worker`, `_start_worker`, `_await_port_file`, `_watch_worker`,
`_say_worker`, `_send_open`, `_on_link_down`, `_on_link_up`, `_shutdown_worker`, `_log_worker`; the calls to them in `_ready`,
`_process`, `_exit_tree`, `_close_now`, `_ask_outside`), viewport/tests/quick/hash.gd,
viewport/tests/quick/protocol.gd, viewport/tests/quick/worker.gd. Not the worker, not worker_client.gd, not tools/.

Why (P45, T113): main.gd (~2,130 lines) is the file every job meets; moving whole sections out lets jobs run side by side and makes it easier to read. Behaviour unchanged: nothing William would notice changes, no message, file or saving changes. A filler job: Ready when nothing else holds its files.

Rules for every T113 step (each says what it is for, P44):
- Move the code, don't rewrite it: same names minus the leading `_` where callers outside the new file now need them, same comments, so `git diff --color-moved` shows a move and review is quick.
- No forwarders left in main.gd for the moved names (the point is a thinner main): callers, tests included, call the new object. Keep a forwarder only where a caller can't be changed in this job (say which in your response).
- The new file is a plain `RefCounted` (or `Node` if it needs `_process`/timers/dialogs as children) made in main like `keys` and `measure` (`load("res://<file>.gd").new()`, given `self`), no `class_name` (viewport/CLAUDE.md).

Today (checked 2026-11-22): main.gd lines ~1343-1611 hold the worker's process: FREECAD_CANDIDATES,
WORKER_MAX_RESTARTS, `freecad_path`, `worker_script`, `worker_log`, `worker_port`, `worker_pid`, `_port_file`,
`_worker_restarts`, `_worker_check`, `_first_open`, `lifecycle_test`, `PROTOCOL_VERSION` (9), and `_free_port`,
`_worker_files`, `_worker_identity`, `_port_free`, `_probe_worker`, `_worker_of`, `_hello`, `_pick_worker`,
`_start_worker`, `_await_port_file`, `_watch_worker` (called from `_process`), `_say_worker`, `_send_open`,
`_on_link_down`, `_on_link_up`, `_shutdown_worker` (called from `_exit_tree` and `_close_now`). `_log_worker`
(line ~1740, in the outside-saves section) writes worker.log; it moves too. Tests call `m._worker_identity`,
`m._probe_worker` (hash.gd), `m._worker_of`, `m._hello` (protocol.gd).

Request: move all of that into viewport/worker_process.gd as `m.worker`; `_send_open`, `_on_link_down` and
`_on_link_up` may stay in main if they mostly touch main's state (they open the model and resend): your call,
say which. `PROTOCOL_VERSION` stays in main.gd as it is (tools/integrate.py
reads it there to renumber a bump, A35); worker_process.gd reads `m.PROTOCOL_VERSION`.

What can fail (P42; each case has a named check today, which must still pass unchanged):
- The worker dies: whichever window notices starts it again, and the lost request is resent (quick test worker).
- Five restarts in a minute: it says so and stops trying (WORKER_MAX_RESTARTS; quick test worker, if covered;
  else add a headless check that calls the restart counter six times).
- A worker on 7878 speaking another protocol or with another hash isn't shared; a private one starts on a free
  port (quick tests protocol, hash).
- Tests pass `--port`: `worker_pid` stays -1, the window never kills or restarts a worker it didn't start.
- Our worker reports its port in a file (T47); a file that never comes is a failure the window says, not a hang.
- Closing sends bye and the worker saves (quick test save_failure, close steps).

Cases that must still work: the whole quick test and full test (the gate) with no change to tests/reference/.

Checks: the existing quick tests above, now calling `m.worker.*`; `wc -l viewport/main.gd` in your response
(before and after).

Reading path: main.gd `_ready` (where the port is picked) → `_pick_worker` → `_worker_of` / `_hello` →
`_start_worker` → `_await_port_file` → `_process` → `_watch_worker` → `_on_link_up` → `_close_now` /
`_exit_tree` → `_shutdown_worker`. Who owns what: worker_process.gd owns the process and port; main owns the
model and the window; worker_client.gd owns the socket.

Run the feature tests while building (`tools/featuretest.sh`), the quick test after each change, then `python3 tools/job.py test`. End your response with a Result line; leftovers as Follow-up lines; the folder-guide change (viewport/CLAUDE.md's Files list) as a For the integrator line.
