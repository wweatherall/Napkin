# Work board

"Check the board" sends you here. Only the integrator edits this file; the job table is built from docs/handoff/
and the job queue.

Order: H105, H115, H085, H086, H093, H098, H094, H096, H097, H107, H108, H109, H110, H111, H112, H113, H114

## If you're not the integrator

You're a worker: one job, then stop. Only the integrator merges or pushes (P16). Each shell command starts in the
main checkout: read there, but run everything else as `cd /Users/Will/Sites/fretchup-jobs/<id> && ...`, in your job's
worktree (T102).

1. `python3 tools/job.py take --as claude` (or `--as codex`) makes your job's worktree and branch and prints its
   entry (a returned job comes first). Nothing Ready: run `python3 tools/job.py take --wait` in the
   background; if it gives up (20 min), tell William.
2. Read the Notes at the bottom for anything addressed to you.
3. Change only the files on the job's Touches line; to touch another, ask first, in chat and your response (P11).
   Leave these alone:
   - the Work list: your result goes in your response (P17);
   - ARCHITECTURE.md and docs/protocol.md: a change to a module, a message, a file format, who owns some state,
     or saving gets `Architecture: <what>` lines in your response instead (P28); a changed message also bumps
     PROTOCOL_VERSION by one on both sides (A35);
   - log rows your job doesn't add or supersede. Add rows with `python3 tools/log.py add`, after merging main;
     new IDs are placeholders like T-new-1 (T74).
   Shared files (the log, viewport/main.gd) get small edits, made at the end.
   A rule in the brief that, followed to the letter, would defeat what it's for or break something the code
   relies on: do what serves its purpose and say so in your response (step 6), don't stop (P44). Not for
   anything William would notice (behaviour, wording he sees, what is saved: ask, step 5), and never drop a
   "What can fail" case or a check, only change how one is met.
4. Run tests and long commands in the background as `python3 tools/job.py run -- <command>`: past 10 minutes it
   stops them and prints HUNG, and the fix is yours (P40); `python3 tools/job.py check` lists your processes.
   Quick test (`tools/quicktest.sh`) after every change; commit when it passes. Set no timer: after 30 minutes
   with no commit, test or job.py command, the integrator is told (P24).
5. A question for William: ask in chat and run `python3 tools/job.py wait "<the question>"`.
6. Append your response to the entry, dated and signed: branch, commit, what you verified, IDs you added, open
   questions. Then a line each: `Changed from the brief: <what it said>; <what you did>; <why>` per departure
   (P44); `Architecture: <what>`; `Follow-up: <what>` per thing left; `For the integrator:
   <what>` per merge step (P26); last, `Result: <commit>; <tests>; <what changed>`, no `|` (T91). Set Status to
   `answered`, run `python3 tools/handoff.py list` (the open list shows each job's status); commit.
7. `python3 tools/job.py done` (it checks the response, the Status, a quick-test pass and hung processes). Tell
   William "ready for review: <ID>" and stop: one job a session (P37). Don't take the integrator lock.

## If you're the integrator

Only if William said so in this session and you hold the lock (P16, P19): read
[docs/integrator.md](docs/integrator.md).

## Jobs

<!-- job table: built by tools/job.py board from docs/handoff/ and the queue; don't edit by hand -->

| Job | For | Status | Item | Handoff | Waits for |
|---|---|---|---|---|---|
| H105 | Gemini | **Ready** | integrate.py stops for a response's `Changed from the brief:` lines (P44) | [H105](docs/handoff/H105-integrate-shows-brief-changes.md) |  |
| H115 | Codex | **Done**: for review (codex) | T112: the queue checks overlap by function (P45) | [H115](docs/handoff/H115-t112-overlap-by-function.md) |  |
| H085 | either | In progress (codex since 07:10) | T83: the Arc tool (2-Point and Centre arcs, exact in FreeCAD, splitting faces) | [H085](docs/handoff/H085-t83-arc-tool.md) |  |
| H086 | either | Queued | T83 step 2: an arc on a corner is tangent to both edges (rounded corners) | [H086](docs/handoff/H086-t83-arc-corner-tangent.md) | H085 |
| H093 | either | **Ready** | Outside saves: a failed reload asks, a worker lost mid-reload reloads again, and a question the actions overtook closes (H092 findings 2 and 5, A39) | [H093](docs/handoff/H093-outside-save-failures.md) |  |
| H094 | either | Queued | A reload from a revision Shop Sketch no longer remembers keeps the ops that file holds (H092 finding 6) | [H094](docs/handoff/H094-reload-unknown-revision.md) | H093 |
| H096 | either | Queued | Pushing one cell of a split profile keeps the rest of the profile on screen (H092 finding 9) | [H096](docs/handoff/H096-region-push-keeps-profile.md) | H083 |
| H097 | either | Queued | T110: test helpers that make a failure-path check a few lines | [H097](docs/handoff/H097-failure-path-test-helpers.md) | H094 |
| H107 | either | Queued | T113 step 1a: the FreeCAD worker's process moves out of main.gd into worker_process.gd | [H107](docs/handoff/H107-t113-worker-process.md) | H094 |
| H108 | either | Queued | T113 step 1b: the closing and outside-save dialogs move out of main.gd into save_prompts.gd | [H108](docs/handoff/H108-t113-save-prompts.md) | H107 |
| H109 | either | Queued | T113 step 2: what a rejection takes with it moves to document.gd, and main's document pass-throughs go | [H109](docs/handoff/H109-t113-rejections.md) | H096, H094 |
| H110 | either | Queued | T113 step 3: the menus move out of main.gd into menus.gd | [H110](docs/handoff/H110-t113-menus.md) | H103, H101 |
| H111 | either | Queued | T113 step 4a: building the interface moves out of main.gd into ui.gd | [H111](docs/handoff/H111-t113-ui.md) | H110 |
| H112 | either | Queued | T113 step 4b: wood rendering moves from main.gd to appearance.gd | [H112](docs/handoff/H112-t113-wood.md) | H101, H110 |
| H113 | either | **Ready** | T113 step 4c: the camera (orbit, pan, zoom, trackpad) moves out of main.gd into camera_rig.gd | [H113](docs/handoff/H113-t113-camera.md) |  |
| H114 | either | Queued | T113 step 4d: main.gd's selection pass-throughs go; callers use m.sel | [H114](docs/handoff/H114-t113-selection-forwarders.md) | H101 |

<!-- end of job table -->

Done since the board started: H033 (T74 + T77), H034 (T76), H035 (T44), T56 (startup report), H036 (T75), H037 (T54), H038 (T78), H039 (T80), H040 (T33), H043 (T85), H044 (T58), H042 (T70), H041 (T81, Circle), H045 (T86), H047 (T88 spec), H048 (T79), H051 (T88 step 0), H049 (T90), H056 (T94), H058 (T96), H054 (T92), H055 (T93), H053 (T91).

## Notes

- H085, H093 and H113 share viewport/main.gd by function (P45: `redo`'s op-type branch; the outside-saves section; the camera functions): they run at once. H096, H110 and H114 wait: they overlap H085 or H093 in whole files (test_document.gd, measure_box.gd, presenter.gd, tool_context.gd).
- H093 merges only after H098 (the break-it trial, William's request): H098 goes to an agent other than H093's builder.
- T88: steps 1-5 (Paint H065, Select H071, Circle H072, Rectangle H075, Push/Pull H079) merged; step 6 (Move, and the legacy setup's removal) is H083 (Gemini finishing Codex's work, William 2026-11-22), H052 (T66 units) and the rest go on from Gemini's version. H101 (Codex checks and tidies it) doesn't hold anything up: it runs when no job holds the tool files, from main as it is then, and Codex fixes whatever it touches (William, 2026-11-22).
- H101 is for the Codex session that started H083 (01a20629…, William): its H083 count was taken off so it can take H101 without a /clear.
