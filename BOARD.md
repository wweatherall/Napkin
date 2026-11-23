# Work board

"Check the board" sends you here. Only the integrator edits this file; the job table is built from docs/handoff/
and the job queue.

Order: H079, H080, H081, H052

## If you're not the integrator

You're a worker: one job, then stop. Only the integrator merges or pushes (P16). Each shell command starts in the
main checkout: read there, but run everything else as `cd /Users/Will/Sites/fretchup-<id> && ...`, in your job's
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
4. Run tests and long commands in the background as `python3 tools/job.py run -- <command>`: past 10 minutes it
   stops them and prints HUNG, and the fix is yours (P40); `python3 tools/job.py check` lists your processes.
   Quick test (`tools/quicktest.sh`) after every change; commit when it passes. Set no timer: after 30 minutes
   with no commit, test or job.py command, the integrator is told (P24).
5. A question for William: ask in chat and run `python3 tools/job.py wait "<the question>"`.
6. Append your response to the entry, dated and signed: branch, commit, what you verified, IDs you added, open
   questions. Then a line each: `Architecture: <what>`; `Follow-up: <what>` per thing left; `For the integrator:
   <what>` per merge step (P26); last, `Result: <commit>; <tests>; <what changed>`, no `|` (T91). Set Status to
   `answered`; commit.
7. `python3 tools/job.py done` (it checks the response, the Status, a quick-test pass and hung processes). Tell
   William "ready for review: <ID>" and stop: one job a session (P37). Don't take the integrator lock.

## If you're the integrator

Only if William said so in this session and you hold the lock (P16, P19): read
[docs/integrator.md](docs/integrator.md).

## Jobs

<!-- job table: built by tools/job.py board from docs/handoff/ and the queue; don't edit by hand -->

| Job | For | Status | Item | Handoff | Waits for |
|---|---|---|---|---|---|
| H079 | either | **Ready** | T88 step 5: Push/Pull moves to ToolContext | [H079](docs/handoff/H079-t88-push-to-toolcontext.md) |  |
| H080 | either | **Ready** | T105: job.py done reuses a quick-test pass across handoff-only commits | [H080](docs/handoff/H080-done-reuses-quick-pass.md) |  |
| H081 | either | **Ready** | T106: the test scripts show progress and keep their output in the job's scratch/ | [H081](docs/handoff/H081-test-progress-and-scratch.md) |  |
| H052 | either | Queued | T66: lengths shown in the model's units | [H052](docs/handoff/H052-t66-units.md) | T88's tool moves |

<!-- end of job table -->

Done since the board started: H033 (T74 + T77), H034 (T76), H035 (T44), T56 (startup report), H036 (T75), H037 (T54), H038 (T78), H039 (T80), H040 (T33), H043 (T85), H044 (T58), H042 (T70), H041 (T81, Circle), H045 (T86), H047 (T88 spec), H048 (T79), H051 (T88 step 0), H049 (T90), H056 (T94), H058 (T96), H054 (T92), H055 (T93), H053 (T91).

## Notes

- T88: steps 1-4 (Paint H065, Select H071, Circle H072, Rectangle H075) merged; step 5 (Push/Pull) is H079; Move (step 6) after it.
- H079, H080 and H081 touch different files and can run side by side.
