### H098 — Trial: try to break H093 before it merges (checks only)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H093) | For: either (the integrator sets it, when H093 is done, to an agent other than H093's builder)

References: H093 (outside saves: a failed reload asks, a worker lost mid-reload reloads again, a question the
actions overtook closes; A36, A39), P42 (its "What can fail" list), H092 (seven of the first ultra review's ten
findings were failure paths of the outside-save code, T64). A one-off trial at William's request (2026-11-22):
not a rule.

Touches: the tests only: viewport/test_document.gd, viewport/tests/quick/outside_save.gd,
worker/test_outside_save.py, and this entry. No product code: not document.gd, main.gd, session.py or serve.py.

Start: H093's branch isn't merged yet. Merge it into your branch first (`git merge <H093's branch>`, named in
H093's response), so you test the code as built.

Request: read H093's code as built (its diff, then the whole of the outside-saves code it lives in: document.gd
`on_outside_save` to `on_keep_mine_reply` and `on_link_up`, main.gd's outside-saves section, session.py
`reload_outside`, serve.py's `reload` and `keep_mine`) and try to break it. Look for a failure H093's brief didn't list (its "Today", Request and Checks are its "What can
fail" list, P42): a step that fails (a file missing or unreadable, the worker gone, a save that fails), a reply
late, repeated or out of order (a reload's reply after a `keep_mine`, an old reply after a reconnect), a dialog
open while replies land, two of these at once (the worker lost while the question is open; a second outside save
while a reload is out). For each case you try, add a named check in the test files above. A check that passes is
kept as cover. A check that fails is kept too, but runs only when `BREAK_H093=1` is set in the environment (each prints
`SKIP <name> (BREAK_H093)` otherwise), so the quick test and `job.py done` still pass; it asserts what should
happen, not what does. Don't fix the code.

Response: a table of every case tried: the case, the check's name, passes or fails, and for a failure what
happens and what you'd expect (A36, A39). Then a line saying which of the failures H093's brief listed
and which it missed.

Reading path: H093's entry (its "Today", "Request" and checks), then the reading path it gives, then H093's
response and diff. Who owns what: you add checks; the builder (or a small fix) changes the code.

Run the feature tests (`tools/featuretest.sh`), the same with `BREAK_H093=1` (say what fails), and
`python3 tools/job.py test` (it must pass: the failing checks are off without the variable). End your
response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.
