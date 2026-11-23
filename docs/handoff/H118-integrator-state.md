### H118 — For the next integrator session: where things stand

Author: Claude (integrator, fretchup-73) | Date: 2026-11-23 | Status: open | For: the integrator

Touches: nothing (a note). Archive it once read: `python3 tools/handoff.py archive H0NN`.

Cleared at William's word (about 09:10; he restarts the integrator and Gemini together when home). After the
clear: `python3 tools/integrator.py take <session> --william` (on his word), then re-arm the queue watch
(`python3 -u tools/job.py watch --next`, Bash run_in_background).

- H096 (Gemini, gemini/h096-region-push-keeps-profile, worktree fretchup-jobs/h096) stopped at 08:48 with
  `job.py wait`, asking to also guard `target.region` in viewport/main.gd `redo` and viewport/presenter.gd
  `forget_op` (outside its Touches). The integrator's answer: yes (no other job holds them); it names both with a
  Changed from the brief line. Its Gemini window will be gone after the restart: when a new Gemini session takes
  it (the job may need `job.py return H096 "<the answer above>"` first, or `reassign`, so it resumes the branch),
  give it that answer in the notes.
- Waiting on H096: H097 (test_document.gd), H109 (T113 step 2, the last T113 step; also waited on H094, merged).
  When H109 merges, T113 is Done (every other step merged: H107, H108, H110-H114).
- Merged this session (2026-11-23, after the 07:45 clear): H113, H105, H086 (T83 Done), H110, H112, H111, H114,
  H093 (with H098's 16 checks, returned twice: H098 findings, then the reload snapshot's Label), H098 (its branch
  came in with H093; marked merged by hand with `job.merged`), H094 (protocol 11: Meta `ShopSketchOps`), H107,
  H108. main.gd ~1,390 lines (2,224 this morning).
- Small fixes this session (listed for William): Gemini session names carry the start time (before the clear);
  a job's Author line may say `Builds on: H0NN` and the queue lets its overlap with that job through (H098).
- Brief lesson: Touches must name full paths (bare names after a path aren't matched: H110's flag) and no globs
  (`tests/quick/*.gd` held H114 behind H093). `git grep -E` has no `\b`: use `-P` for stale-caller checks.
- For William to confirm (still open from before): H085's response said he approved it touching
  viewport/inference.gd (arc snapping).
