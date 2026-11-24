### H118 — For the next integrator session: where things stand

Author: Claude (integrator, fretchup-73) | Date: 2026-11-23 | Status: open | For: the integrator

Touches: nothing (a note).

Archive it once read (`handoff.py archive H118`).

Cleared at William's word (about 09:10; he restarts the integrator and Gemini together when home). After the
clear: `python3 tools/integrator.py take <session> --william` (on his word), then re-arm the queue watch
(`python3 -u tools/job.py watch --next`, Bash run_in_background).

Updated 2026-11-23 (afternoon, before a second clear at William's word).

- H096 (Gemini, gemini/h096-region-push-keeps-profile, worktree fretchup-jobs/h096) still stopped since 08:48
  on its scope question (guard `target.region` in viewport/main.gd `redo` and viewport/presenter.gd `forget_op`,
  outside its Touches). The integrator's answer: yes (no other job holds them); it names both with a Changed
  from the brief line. William restarts Gemini when home: either he types the answer in, or the worker merges
  main and runs `job.py wait --scope "<question>"` and the integrator answers with `job.py answer H096 "..."`
  (T114, merged). If the window is gone: `job.py return H096 "<the answer>"` so a new session resumes the branch.
- Waiting on H096: H097, H109 (the last T113 step 2; T113 is Done when H109 and H122 merge).
- Merged this session: H119 (T114, `job.py wait --scope` / `job.py answer`; P47), H120 (T115, `handoff.py
  check` in the commit hook; wrapped response lines read whole). BOARD.md step 5 and docs/integrator.md updated.
- Ready (written at William's word, no overlaps with each other or H096/H097/H109): H121 (T59 step 2, protocol
  11 -> 12), H122 (T113 step 5, main's compatibility members), H123 (T116, tooling follow-ups).
- At H122's merge: clear its five follow-ups in docs/follow-ups.md yourself (H107, H110, H111, H112, H113: H122
  doesn't touch the file, H123 holds it), in a commit of its own after the merge, with its viewport/CLAUDE.md
  change.
- `handoff.py check` flags H067 ("communication/design") and H096 (a stale "Queued after H083" sentence with
  bare names): left alone since their branches edit those entries; fix when they close.
- Small fixes this session: none.
- For William to confirm (still open from before): H085's response said he approved it touching
  viewport/inference.gd (arc snapping).

Updated 2026-11-23 evening (fretchup-74, before running out of context):
- Merged: H121 (T59 step 2, protocol 12; map and tools guide written), H096 (region push keeps its profile; William
  approved the main.gd `redo` / presenter.gd `forget_op` guards). H097 opened (brief rechecked after H096).
- H122 (Codex) stale since 16:23: uncommitted edits in fretchup-jobs/h122, no process running. William to look;
  if the window is gone, `job.py return H122 "resume from the worktree's uncommitted edits"`.
- H109 waits on H097 (both touch viewport/test_document.gd). H123 Ready.
- Small fixes this session: none.
