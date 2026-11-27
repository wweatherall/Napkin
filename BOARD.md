# Work board

"Check the board" sends you here. Only the integrator edits this file; the job table is built from docs/handoff/
and the job queue.

Order: H155, H156, H157, H154

## If you're not the integrator

You're a worker: one job, then stop. Only the integrator merges or pushes (P16). Each shell command starts in the
main checkout: read there, but run everything else as `cd /Users/Will/Sites/comitatus/08_Code_Bases/.worktrees/Napkin/<id> && ...`, in your job's
worktree (T102).

1. `python3 tools/GET_A_JOB.py --as claude` (or `--as codex` / `--as gemini`, outside sandbox if `.git/` is sandboxed)
   makes your job's worktree and branch and prints the full handoff entry — keep it in context instead of re-reading
   the file later (a returned job comes first). Nothing Ready: run `python3 tools/GET_A_JOB.py --wait` in the
   background; if it gives up (20 min), tell William.
2. Read the Notes at the bottom for anything addressed to you. Follow the brief's `Reading path:` and batch
   independent searches and file-slice reads in one turn; skip reading `CLAUDE.md` unless a rule isn't already covered
   by `startup.py`, `BOARD.md` and your brief.
3. Change only the files on the job's Touches line; to touch another, ask first, in chat and your response (P45).
   One exception (P46): a `tools/test_*.py` check that only asserts on output your job changes (a message, a
   printed line) you update without asking, and name it in a `Changed from the brief:` line.
   Leave these alone:
   - the Work list: your result goes in your response (P17);
   - ARCHITECTURE.md and docs/protocol.md: a change to a module, a message, a file format, who owns some state,
     or saving gets `Architecture: <what>` lines in your response instead (P28); a changed message also bumps
     PROTOCOL_VERSION by one on both sides (A35);
   - log rows your job doesn't add or supersede. Add rows with `python3 tools/RECORD_A_DECISION.py`, after merging main;
     new IDs are placeholders like T-new-N (T74).
   Shared files (the log, viewport/main.gd) get small edits, made at the end.
   A rule in the brief that, followed to the letter, would defeat what it's for or break something the code
   relies on: do what serves its purpose and say so in your response (step 6), don't stop (P44). Not for
   anything William would notice (behaviour, wording he sees, what is saved: ask, step 5), and never drop a
   "What can fail" case or a check, only change how one is met.
4. Run tests and long commands in the background as `python3 tools/job.py run -- <command>`: past 10 minutes it
   stops them and prints HUNG, and the fix is yours (P40); `python3 tools/job.py check` lists your processes.
   Quick test (`tools/TEST_YOUR_CODE_FAST.sh` — don't invoke `godot` directly without a running worker) after every change;
   commit when it passes. Set no timer: after 30 minutes with no commit, test or job.py command, the integrator is told (P24).
5. To touch a file or function outside Touches, ask the integrator: `python3 tools/job.py wait --scope
   "<the question>"`. For behaviour, wording or what is saved, ask William in chat and run `python3 tools/job.py
   wait "<the question>"`. Run either in the background; on a timeout run the same command again. Quote the
   answer in your response (T114).
6. Finish cleanly in two turns (don't re-read `tools/job.py` or your handoff — `job.py done` automatically reuses a
   clean `job.py test` pass across handoff-only commits):
   - Commit your code changes first (if committing watched code with `Architecture-Impact: in the handoff - <ID>`,
     include the `Architecture: <what>` line(s) in the handoff in that commit so the pre-commit hook passes), then
     run `python3 tools/job.py test` once.
   - Append your response to the handoff entry (dated and signed: branch, commit, what you verified, IDs you added,
     open questions; then a line each: `Changed from the brief: <what it said>; <what you did>; <why>` per departure
     (P44); `Architecture: <what>`; `Follow-up: <what>` per thing left; `For the integrator: <what>` per merge step
     (P26); last, `Result: <commit>; <tests>; <what changed>`, no `|` (T91)), set Status to `answered`, and in one
     chained command run `python3 tools/handoff.py list && git add docs/agent-handoff.md docs/handoff/<file> && git -c core.hooksPath=.githooks commit -m "<ID>: record response and mark answered" && python3 tools/SUBMIT_JOB.py`.
7. Once `SUBMIT_JOB.py` succeeds (it checks the response, Status, quick-test pass and hung processes), tell William
   "ready for review: <ID>" and stop: one job a session (P37). Don't take the integrator lock.

## If you're the integrator

Only if William said so in this session and you hold the lock (P16, P19): read
[docs/integrator.md](docs/integrator.md).

## Jobs

<!-- job table: built by tools/job.py board from docs/handoff/ and the queue; don't edit by hand -->

| Job | For | Status | Item | Handoff | Waits for |
|---|---|---|---|---|---|
| H158 | Gemini | In progress (gemini since 22:35) | Personal spaces: a journal about how it felt, three folders of your own, changes committed by themselves | [H158](docs/handoff/H158-personal-spaces-journal-and-own-folders.md) |  |
| H159 | Gemini | Queued | Personal spaces: everything an agent makes is committed and pushed; experiments can be run or merged | [H159](docs/handoff/H159-personal-spaces-saved-and-pushed.md) | H158 |

<!-- end of job table -->

Done since the board started: H033 (T74 + T77), H034 (T76), H035 (T44), T56 (startup report), H036 (T75), H037 (T54), H038 (T78), H039 (T80), H040 (T33), H043 (T85), H044 (T58), H042 (T70), H041 (T81, Circle), H045 (T86), H047 (T88 spec), H048 (T79), H051 (T88 step 0), H049 (T90), H056 (T94), H058 (T96), H054 (T92), H055 (T93), H053 (T91).

## Notes

- T88: steps 1-5 (Paint H065, Select H071, Circle H072, Rectangle H075, Push/Pull H079) merged; step 6 (Move, and the legacy setup's removal) is H083 (Gemini finishing Codex's work, William 2026-11-22), H052 (T66 units) and the rest go on from Gemini's version. H101 (Codex checks and tidies it) doesn't hold anything up: it runs when no job holds the tool files, from main as it is then, and Codex fixes whatever it touches (William, 2026-11-22).
- H101 is for the Codex session that started H083 (01a20629…, William): its H083 count was taken off so it can take H101 without a /clear.
