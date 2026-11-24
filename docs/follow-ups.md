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
- H104 (2026-11-23): `tools/job.py` `return_job` does not refuse when run inside a job worktree (unlike `reassign_job`); decide whether `return` should refuse it too.
- H103 (2026-11-23): Godot 4.6's macOS NativeMenu.get_item_accelerator() maps keyEquivalent "," through find_keycode_from_string(","), returning KEY_MASK_META without KEY_COMMA; verify ⌘, opens preferences.json interactively during the hardware feel test (Q4), and add a Cmd+, fallback in viewport/keys.gd if macOS menu dispatch ever misses it.
- H103 (2026-11-23): T111 Mac Preferences window remains future work once the JSON file and hardware feel test (Q4) settle the tunables.
- H086 (2026-11-23): a typed corner radius too big for the two edges (`_fillet` returns empty) does nothing and says nothing; a status line like the chord's "Radius must be at least half the chord" would tell the user why.
- H093 (2026-11-23): H063 still applies to a replacement worker that never held Shop Sketch's live pre-conflict document.
- H096 (2026-11-23): One `job.py test` run hit a one-off timing flake in unrelated `viewport/tests/quick/rect.gd` (`the second click finishes a 100 x 150` got `[2, [50.0, 70.0]]` under parallel test load); it passed cleanly on the immediately preceding and following runs.
