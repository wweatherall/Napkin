# Work board

"Check the board" sends you here. Only the integrator edits this file; the job table is built from docs/handoff/
and the job queue.

Order: H140, H125, H128, H126, H127, H139, H136, H137, H138, H141, H129, H130

## If you're not the integrator

You're a worker: one job, then stop. Only the integrator merges or pushes (P16). Each shell command starts in the
main checkout: read there, but run everything else as `cd /Users/Will/Sites/fretchup-jobs/<id> && ...`, in your job's
worktree (T102).

1. `python3 tools/job.py take --as claude` (or `--as codex`) makes your job's worktree and branch and prints its
   entry (a returned job comes first). Nothing Ready: run `python3 tools/job.py take --wait` in the
   background; if it gives up (20 min), tell William.
2. Read the Notes at the bottom for anything addressed to you.
3. Change only the files on the job's Touches line; to touch another, ask first, in chat and your response (P45).
   One exception (P46): a `tools/test_*.py` check that only asserts on output your job changes (a message, a
   printed line) you update without asking, and name it in a `Changed from the brief:` line.
   Leave these alone:
   - the Work list: your result goes in your response (P17);
   - ARCHITECTURE.md and docs/protocol.md: a change to a module, a message, a file format, who owns some state,
     or saving gets `Architecture: <what>` lines in your response instead (P28); a changed message also bumps
     PROTOCOL_VERSION by one on both sides (A35);
   - log rows your job doesn't add or supersede. Add rows with `python3 tools/log.py add`, after merging main;
     new IDs are placeholders like T-new-N (T74).
   Shared files (the log, viewport/main.gd) get small edits, made at the end.
   A rule in the brief that, followed to the letter, would defeat what it's for or break something the code
   relies on: do what serves its purpose and say so in your response (step 6), don't stop (P44). Not for
   anything William would notice (behaviour, wording he sees, what is saved: ask, step 5), and never drop a
   "What can fail" case or a check, only change how one is met.
4. Run tests and long commands in the background as `python3 tools/job.py run -- <command>`: past 10 minutes it
   stops them and prints HUNG, and the fix is yours (P40); `python3 tools/job.py check` lists your processes.
   Quick test (`tools/quicktest.sh`) after every change; commit when it passes. Set no timer: after 30 minutes
   with no commit, test or job.py command, the integrator is told (P24).
5. To touch a file or function outside Touches, ask the integrator: `python3 tools/job.py wait --scope
   "<the question>"`. For behaviour, wording or what is saved, ask William in chat and run `python3 tools/job.py
   wait "<the question>"`. Run either in the background; on a timeout run the same command again. Quote the
   answer in your response (T114).
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
| H128 | either | Returned: **Ready** for Gemini (resumes gemini/h128-t109-mixed-line-arc-loops) | T109: closed loops of mixed lines and arcs form pushable faces with exact arcs | [H128](docs/handoff/H128-t109-mixed-line-arc-loops.md) |  |
| H126 | either | Queued | T61: face ties on linked copies (component definitions and instances) | [H126](docs/handoff/H126-t61-face-ties-linked-copies.md) | H125 |
| H127 | either | Queued | T62: face ties on shapes other than plain rectangular boards | [H127](docs/handoff/H127-t62-face-ties-other-shapes.md) | H126 |
| H139 | either | **Ready** | T125: Fix Pull/autosave lag (TechDraw-on-autosave stall, .FCBak/.saving clutter, and Push/Pull frame caching) | [H139](docs/handoff/H139-t125-pull-and-autosave-lag.md) |  |
| H136 | either | **Ready** | T122: Rectangle after-the-fact typed dimensions | [H136](docs/handoff/H136-t122-rect-amend-after-create.md) |  |
| H137 | either | **Ready** | T123: Move array live preview before click and amend after click | [H137](docs/handoff/H137-t123-move-array-live-preview.md) |  |
| H138 | either | **Ready** | T124: Auto-set document units from first typed length with an explicit unit | [H138](docs/handoff/H138-t124-units-from-first-typed-length.md) |  |
| H141 | either | Queued | T127: Enter and edit components, and Component Properties window (prioritizing critical dimensions and linked measurements) | [H141](docs/handoff/H141-t127-components-and-properties.md) | H126 |
| H129 | either | Queued | T84 step 1: Rotated Rectangle (R again toggles Rectangle and Rotated Rectangle) | [H129](docs/handoff/H129-t84-rotated-rectangle.md) | H128 |
| H130 | either | Queued | T84 step 2: Polygon tool (toolbar button without hotkey, exact FreeCAD sketch polygon) | [H130](docs/handoff/H130-t84-polygon-tool.md) | H129 |

<!-- end of job table -->

Done since the board started: H033 (T74 + T77), H034 (T76), H035 (T44), T56 (startup report), H036 (T75), H037 (T54), H038 (T78), H039 (T80), H040 (T33), H043 (T85), H044 (T58), H042 (T70), H041 (T81, Circle), H045 (T86), H047 (T88 spec), H048 (T79), H051 (T88 step 0), H049 (T90), H056 (T94), H058 (T96), H054 (T92), H055 (T93), H053 (T91).

## Notes

- T88: steps 1-5 (Paint H065, Select H071, Circle H072, Rectangle H075, Push/Pull H079) merged; step 6 (Move, and the legacy setup's removal) is H083 (Gemini finishing Codex's work, William 2026-11-22), H052 (T66 units) and the rest go on from Gemini's version. H101 (Codex checks and tidies it) doesn't hold anything up: it runs when no job holds the tool files, from main as it is then, and Codex fixes whatever it touches (William, 2026-11-22).
- H101 is for the Codex session that started H083 (01a20629…, William): its H083 count was taken off so it can take H101 without a /clear.
