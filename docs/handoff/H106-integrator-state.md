### H106 — For the next integrator session: where things stand

Author: Claude (integrator, fretchup-74) | Date: 2026-11-22 | Status: open | For: the integrator

References: docs/integrator.md, BOARD.md, tools/startup.py, memory `launch-gemini`.

Touches: nothing (a note). Archive it once read: `python3 tools/handoff.py archive H0NN`.

Taking over: after a /clear William says you're the integrator: `python3 tools/integrator.py take <name>
--william`, `python3 tools/startup.py`, then re-arm the watch (`python3 -u tools/job.py watch --next`, Bash
run_in_background). William is short on Claude tokens: keep Claude workers idle, give exact jobs to Gemini, and
launch Gemini windows yourself (memory `launch-gemini`: osascript + `agy -i "Gemini go"`), telling William.

Done this session (2026-11-22, late; main pushed): merged H099 (job worktrees in `<checkout>-jobs/<id>`), H083
(T88 step 6, Gemini finishing Codex's work; T88 Done), H102 (preferences.gd; I fixed RELEASE_DEG at review, the
brief's mistake), H052 (T66 units, protocol 9). Logged P43 (no light /code-review per merge), I62 (no saved
units: the user's default, else the last used), I63 (preferences JSON, live, ⌘,), T111 (Preferences), P44 (a
brief's rule says what it's for; a worker may depart with a `Changed from the brief:` line). Wrote H101, H103,
H104, H105.

The queue:
- H103 (T111 step 2, preferences wired) and H104 (job.py reassign, quieter watch, one-line results): Gemini, in
  progress since 23:26 / 23:27. Both briefs predate P44.
- H105 (integrate.py stops for `Changed from the brief:` lines): queued after H104 (same file). Make it Ready
  when H104 merges and launch Gemini for it.
- H101 (Codex tidies the T88 Move migration): for the Codex session 01a20629… that started H083, which William
  keeps for it (its H083 count was removed). It holds nothing up: make it Ready when no job holds the tool files
  or main.gd (after H103), and tell William to send that Codex session, with "re-read BOARD.md step 3 (P44)".
  Another Codex session must not take it first.
- H085 (Arc), then H086, H093 (+H098, William's break-it trial, for an agent other than H093's builder), H094,
  H096, H097: after H103 (main.gd / tool files). Write T59 step 2 (Push/Pull `to_face`, protocol bump) now that
  H083 and H052 are in.
- Follow-ups added: a one-off `[move]` quick flake (H083); H052's two (length_cases.py doesn't generate the
  default_unit cases; featuretest.sh log names can collide across worker/ and viewport/).

No small fixes this session. Nothing waiting on William.
