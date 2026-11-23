# Follow-ups

Leftovers from merged jobs (P26): a worker writes each one as its own `Follow-up: <what>` line in its handoff
response, and tools/integrate.py copies it here at merge. The integrator removes a line in the commit that does it,
or that turns it into a Work list item. `python3 tools/startup.py` lists the open ones.

## Open

- H061 (2026-11-22): Codex sessions are counted only if CODEX_SESSION_ID or CODEX_THREAD_ID is set; if Codex has neither, its count never applies (it falls back to "codex"). Worth checking from a Codex session.
- H062 (2026-11-22): the .unmatched files are never cleaned up (overwritten by the next recovery); fine while recoveries are rare.
- H063 (2026-11-22): after a crash during an outside-save wait, "Keep Shop Sketch's" on the new worker saves FreeCAD's file plus the window's actions on top (the new worker loaded FreeCAD's file); the aside copy is still made.
- H059 (2026-11-22): tools/test_log.py assumes its copied real log has no I/G/Q/T/A placeholders when testing branch allocation; adding an I-new decision on a worker branch caused four false failures. Its temporary test edit was reverted to avoid overlap with H068; H059 uses a W-new View decision. H068 owns this test, so carry any fix there.
- integrator (2026-11-22): document.gd reserve_values and session.py id_strings reserve every string in the ops (types, wood names, typed values), not only ID fields; the whole set goes out with every sync and into the journal. Fine at today's sizes; limit it to ID fields before models get long (H059).
- H090 (2026-11-22): T59 step 2 (Push/Pull tool sending `to_face` on face-behind snap, dropping it on typed length per I40, bumping `PROTOCOL_VERSION`, quick-test step) waits for H083 and H052.
- H090 (2026-11-22): T59 later: tying a cut to another board's face, and keeping the length with a note when a floor cutter is deleted in FreeCAD (I26b).
- H083 (2026-11-22): one gate run had a one-off `[move]` quick-test failure (`moved 150 along red` moved along (147.09, -29.42)); it didn't repeat in job.py test, the second gate or the merge gate. Watch for it again (a timing flake in tests/quick/move.gd's drag, not seen before).
- H052 (2026-11-22): tools/length_cases.py does not yet generate the default_unit cases appended to tests/length_cases.json; add a default_unit list to tools/length_cases.py next time it is regenerated.
- H052 (2026-11-22): tools/featuretest.sh keys each test's log by basename after test_, so a worker/test_<name>.py and viewport/test_<name>.gd with the same <name> overwrite each other's log (avoided here by naming worker/test_model_units.py); prefixing logs by folder in featuretest.sh would prevent silent collisions.
- H104 (2026-11-23): `tools/job.py` `return_job` does not refuse when run inside a job worktree (unlike `reassign_job`); decide whether `return` should refuse it too.
- H103 (2026-11-23): Godot 4.6's macOS NativeMenu.get_item_accelerator() maps keyEquivalent "," through find_keycode_from_string(","), returning KEY_MASK_META without KEY_COMMA; verify ⌘, opens preferences.json interactively during the hardware feel test (Q4), and add a Cmd+, fallback in viewport/keys.gd if macOS menu dispatch ever misses it.
- H103 (2026-11-23): T111 Mac Preferences window remains future work once the JSON file and hardware feel test (Q4) settle the tunables.
- H113 (2026-11-23): To remove the preference aliases, point main's preference wiring and `tests/quick/preferences.gd` at
- H105 (2026-11-23): `follow_ups()`, `for_integrator()`, and `architecture()` in `tools/integrate.py` still scan the full handoff file rather than scoping to the Response section outside fenced code blocks (left untouched in H105 because existing test fixtures omit a `Response` heading); consider scoping them once those fixtures include `Response` headings.
- H086 (2026-11-23): a typed corner radius too big for the two edges (`_fillet` returns empty) does nothing and says nothing; a status line like the chord's "Radius must be at least half the chord" would tell the user why.
- H105 (2026-11-23): integrate.py `RESPONSE_HEADING` also matches a brief's own line starting `Response:` (briefs say "Response: a table of..."), so `Changed from the brief:` scoping can start inside the brief; anchor it to a heading (`#### Response` or `Response —`/`Response from`).
- H110 (2026-11-23): When the model quick test and shell suite can be edited, have them read the menu RIDs from `m.menus` and remove main's compatibility getter.
- H112 (2026-11-23): Point the native Wood menu at `m.appearance` and remove its five Main forwarders when `menus.gd` is in scope.
- H111 (2026-11-23): When their callers are in scope, change the native menu commands to call `m.ui.update_toggles()` and the registry quick test to read `m.ui.tool_buttons`, then remove main's compatibility members.
