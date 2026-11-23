### H100 — For the next integrator session: where things stand

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: the integrator

References: docs/integrator.md, BOARD.md, tools/startup.py.

Touches: nothing (a note). Archive it once read: `python3 tools/handoff.py archive H0NN`.

Taking over: `python3 tools/integrator.py take fretchup-73` (a /clear keeps the name; another name needs
`--william`), then `python3 tools/startup.py`, then re-arm the watch (`python3 -u tools/job.py watch --next`,
Bash run_in_background). A watch from before the clear may still be running; a second one is harmless.

Done this session (2026-11-22, late; main pushed): merged H088, H087 (+ protocol 8 for the journal's
floor_copy), H091, H090 (T59 step 1), H095, and small-fixes twice (ultra review findings 1, 3, 10 by
fretchup-f9; finding 7 by me). Wrote H090, H091, H093-H099. Logged A39 (outside-save question closes when the
actions land), P42 (briefs for saving/reload/worker-link jobs list what can fail, each with a check; the review
checks each), T110 (failure-path test helpers, job H097).

The queue:
- H099 (Gemini, in progress since 22:09): job worktrees in `~/Sites/fretchup-jobs/<id>`. When it merges, remind
  William: Gemini's `~/.gemini/antigravity-cli/settings.json` can then trust only `/Users/Will/Sites/fretchup`
  and `/Users/Will/Sites/fretchup-jobs`, with `allowNonWorkspaceAccess` off (he gave it wider access earlier;
  I checked then that it hadn't touched anything outside its worktrees).
- H083 (Codex, stale since 20:13, uncommitted work in ../fretchup-h083): leave it for Codex to resume.
  Behind it: H052, H085, H086 (in that order), H093 (main.gd) and H096 (presenter.gd). H094 waits for H093; H097
  for H094.
- H098: William's one-off trial. When H093 is done, set H098's For to an agent other than H093's builder and
  make it Ready; H093 merges only after H098 is in. H098 keeps only the checks that find a bug (William), each
  behind `BREAK_H093=1`. Then: if it found something H093's brief missed, propose to William that it become a
  step for P42 jobs; if nothing, tell him it cost one small job.
- T59 step 2 (Push/Pull sends `to_face`, protocol bump) is to be written once H083 and H052 are in.

Small fixes merged this session, to list for William (P22): the worker survives an unreadable model file in
save/watch; the reload reply's rev is the session's; a region push builds its face once; a saved revision's op
list keeps only the ops that worked (finding 7).

Still open with William: a light `/code-review` on every merge (docs/follow-ups.md).
