### H169 — protocol.md's message list generated from the code, and a check that keeps the rest honest

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: queued (after H167) | For: gemini

References: William, 2026-11-27 (going through protocol.md: "Is it possible to generate these from the actual code
using a script automatically?"), comitatus principles C05 ("can it just be a Python script?") and C06 (one spot per
idea; if in several, can it be written automatically?), H167 (adds a last section to protocol.md first), T157/T158.

Touches: docs/protocol.md, tools/protocol_map.py (new), tools/test_protocol_map.py (new), worker/serve.py (its
`serve` docstring only), .githooks/pre-commit (one line), tools/README.md (one line).

Reading path:
1. docs/protocol.md `## Commands and events` (each message: request fields, reply fields, example, Producer/consumer).
2. worker/serve.py: the `serve` docstring (lines ~59-95: a second copy of the message list) and the nested `handle`
   (`if cmd == "..."` branches, each building its reply as a dict literal, `resp = {...}` or `send(conn, {...})`).
3. worker/length_input.py `handle` (the length reply), viewport/main.gd `_on_worker` (how the window routes replies
   by `cmd`).
4. tools/architecture_map.py (H165): the same pattern, a marked generated section plus `--check`.

Today (checked 2026-11-27): every message is a plain `cmd == "<name>"` branch in serve.py's `handle`, and every reply
a dict literal, so the command list and each reply's keys can be read from the code with Python's `ast`. The doc is
hand-written and has drifted: the `hello` example says `"protocol":3` (it is 15); the events section's
"Both are unsolicited" follows only `outside_save` (an edit put it in front of the `saved`/`focus` text) and its
example block includes an `open` refusal; `reload`, `keep_mine` and `set_units` have no example and no
Producer/consumer line. serve.py's docstring repeats the message list a second time.

Request:
1. **`python3 tools/protocol_map.py`** rebuilds a generated section at the top of `## Commands and events`, between
   marker lines like ARCHITECTURE.md's module map: one row per command the worker handles and per event it sends
   unprompted: `cmd`, the request fields the branch reads (`req.get("x")` / `req["x"]`), the reply's keys (the dict
   literals' keys; `**saves` and the like listed by name), and `file:function` of the handler. Read from the code
   with `ast`, never by running FreeCAD (so it runs in the tools-scope gate, well under a second).
2. **`--check`** exits 1, naming each problem, when:
   - the generated section is stale;
   - a command or event in the code has no `### ` section in the doc, or the doc has one the code doesn't handle;
   - a `file:function` named in a Sources or Producer/consumer line doesn't exist (function or nested function in
     that file; `.gd` files by `func name`);
   - an example's JSON line doesn't parse, or its `cmd`'s keys aren't a subset of what the code can send or read for
     that cmd; `hello`'s `protocol` value differs from `PROTOCOL_VERSION`.
   The pre-commit hook runs the rebuild when serve.py, length_input.py or protocol.md is committed, like the module
   map's.
3. **The prose stays hand-written, but once:** fix the drift listed above (the events section put back in order:
   each event once, its example under it; examples for reload, keep_mine and set_units; their Producer/consumer
   lines). serve.py's docstring becomes two lines pointing at docs/protocol.md (one spot per idea); quote in your
   response anything it said that protocol.md didn't, and where you put it.
4. **H167's moved section:** if H167 left a `## Moved from ARCHITECTURE.md (H167)` section, leave it alone: William
   and the integrator fold it in.

Not in this job: changing any message (that is H170), Operation payloads and Shared files (a later job may generate
those the same way; say in a Follow-up whether the op handlers are as regular), the archive doc.

What can fail:
- A command handled in a way the parser doesn't expect (a reply built in a helper like `open_reply`): the check
  follows a call to a function in the same file that returns a dict literal, or lists the command with
  `reply: built by <function>`; never silently drops a command. Check: test_protocol_map.py with a throwaway file.
- A false alarm blocking every commit: each check has a test where it passes on today's (fixed) doc.

Checks:
- tools/test_protocol_map.py: each check passing and failing on throwaway files; the real doc passes `--check`.
- `python3 tools/protocol_map.py --check` passes on the branch; quote its run time.
- `tools/TEST_BEFORE_MERGING.sh` passes.
