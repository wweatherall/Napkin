### H097 — T110: test helpers that make a failure-path check a few lines

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H096) | For: either

References: T110, P42 (briefs for saving, reloading or worker-link jobs list what can fail, each case with its
named check; this job makes those checks cheap), H092 (the ultra review: seven of ten findings on failure
paths; its deleted-file check had to be built by hand), T47 (test workers on their own port), P02 (test hooks are
for tests only).

Touches: a new worker/test_link.py (a helper, `# runner: none`, like worker/test_load.py), worker/test_serve.py
and worker/test_outside_save.py (moved onto the helper), viewport/test_document.gd (its stand-in client and
reply builders). Not the worker or viewport code itself: no new test hook in serve.py or document.gd (every
failure below is made from outside: a killed process, a read-only folder, bytes on disk, a reply delivered late
or never). Not the folder guides: write what they should say as "For the integrator:" lines. Queued after H094,
the last queued job touching worker/test_outside_save.py, and after H093, which touches viewport/test_document.gd.

Today (checked 2026-11-22): worker/test_serve.py and worker/test_outside_save.py each define their own `check`,
`Window` (a socket with `ask` and `wait`), `board_ops`, `sync` and `start_worker` (port 0 and `SERVE_PORT_FILE`,
T47), copied between them with small differences; test_outside_save.py adds `fresh_model`, `freecad_save` (a
real FreeCAD save through freecadcmd), `wait_outside`. A save failure is made by hand with `os.chmod(folder,
0o555)` and a `try/finally` to restore it (test_serve.py); a worker gone, by hand with `proc.kill()`. In
viewport/test_document.gd, `FakeClient` records what was sent, and `reply()` builds only a sync reply; every
reload, keep_mine, open or outside_save message is written out as a literal dictionary in each check.

Request:
1. worker/test_link.py, the shared worker-link helpers, importable from worker tests (they put worker/ on
   `sys.path` already). At least:
   - `start_worker(folder, **env)` returns a `Worker` with `.port`, `.proc`, `.log` (its log file's path),
     `.kill()` (SIGKILL: the worker gone, no goodbye), `.restart()` (a new worker on a new port, same folder) and
     `.stop()` (quit, then wait);
   - `Window(port)`: today's `ask` / `wait` (with `model=`) / `extra`, plus `send(req)` (no wait: so a test can
     send two requests before reading either answer), `drop()` (close the socket at once: the window gone, as
     closing the app without `bye` does) and `seq` numbering of its own;
   - `fresh_model(folder, name)`, `board_ops(width, rid=..., bid=...)`, `sync(window, model, ops)`;
   - `freecad_save(model, add=12)`, moved from test_outside_save.py;
   - failure makers, each restoring what it changed when the `with` block ends, even on an exception:
     `read_only(folder)` (the next save fails with the worker's PermissionError message), `unreadable(path)`
     (the file's bytes replaced by bytes that aren't a FreeCAD file, the original put back after), `missing(path)`
     (the file moved aside, put back after);
   - `Checks(name)`: `check(label, cond, detail="")` and `done()` printing `<NAME> TESTS: N passed, M failed` and
     returning the exit code, as each test does by hand today.
2. worker/test_serve.py and worker/test_outside_save.py use them: their own copies go. Every check keeps its
   label and its result (compare the PASS lines before and after: same labels, same count). Their run time stays
   about the same (say before and after).
3. viewport/test_document.gd: `FakeClient` gets `last_of(cmd)` (the last request of that kind) and `drain()`
   (what was sent since the last drain); beside `reply()`, builders for the other replies and events, each
   taking the request it answers so the seq matches: `reload_reply(req, ops, extra := {})`,
   `keep_mine_reply(req, extra := {})`, `open_reply(req, ops, extra := {})`, `error_reply(req, message)`, and
   `outside_save(d, unsaved := false)` (the worker's event for that document's model). Move the existing
   outside-save and open checks onto them where it makes them shorter; same labels, same count.
4. A short comment at the top of each helper says when to reach for it, with the P42 cases it covers: a file
   missing or unreadable (`missing`, `unreadable`), the worker gone (`Worker.kill`, then `restart`), a reply late
   or out of order (`Window.send` twice before reading; in test_document.gd, deliver replies in any order),
   a save that fails (`read_only`), a window gone (`Window.drop`).

Cases that must still work: every check in the three test files, with the same labels; `tools/featuretest.sh
--list` still shows test_serve.py and test_outside_save.py as `runner: python3` tests and doesn't run
test_link.py (it is a helper: `# runner: none` in its first five lines).

Checks (in a new section of worker/test_serve.py, each helper proving itself once):
- `read_only`: a flush inside it gets `save_failed` with the read-only message; after the block, a flush saves;
- `unreadable` and `missing`: inside, opening the model fails (an error reply), after, it opens;
- `Worker.kill`: the window's `wait` returns None (the link is gone); `restart` gives a worker that answers
  `hello`;
- `Window.drop`: the worker keeps running and answers another window;
- test_document.gd: a check using `reload_reply` and `error_reply` built from `last_of("reload")`, and one
  delivering two sync replies in the wrong order (the older one changes nothing).

Reading path: worker/test_serve.py (its helpers, top to `start_worker`) and worker/test_outside_save.py (its
helpers, through `wait_outside`, then section 8, the hand-built deleted-file check) → worker/test_load.py (the
helper pattern, `# runner: none`) → tools/featuretest.sh (how it finds and runs worker tests) →
viewport/test_document.gd (`FakeClient`, `make`, `reply`, the outside-saves section). Who owns what: the helpers
own nothing of the product; each test still says what it checks.

Run the feature tests while building (`tools/featuretest.sh`), then `python3 tools/job.py test`. End your
response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.
