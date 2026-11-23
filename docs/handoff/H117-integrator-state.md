### H117 — For the next integrator session: where things stand

Author: Claude (integrator, fretchup-73) | Date: 2026-11-23 | Status: open | For: the integrator

Touches: nothing (a note). Archive it once read: `python3 tools/handoff.py archive H0NN`.

Cleared at William's word (about 07:45). After the clear: `python3 tools/integrator.py take fretchup-73 --william`
(on his word), then re-arm the queue watch (`python3 -u tools/job.py watch --next`, Bash run_in_background).

- In progress since 07:41-07:43, four windows the integrator opened: H086 (Codex, arcs on corners), H093 (Codex,
  outside-save failures), H113 (Codex, camera to camera_rig.gd), H105 (Gemini, integrate.py stops for `Changed from
  the brief:` lines). None overlap (by function in main.gd, P45). Review each as it comes in.
- H093 merges only after H098 (the break-it trial): Codex built H093, so set H098 `For: claude` or `gemini` when
  H093 is done and mark it Ready.
- Waiting: H096 on H093 (test_document.gd), H110 on H113 (tests/harness.gd), H114 on H086 (test_tool_context.gd);
  H094 after H093, H097 after H094, H107 after H094. Check overlaps (`handoff.py overlaps`) before opening each.
- Merged this morning: H104, H103, H115 (T112 Done: overlap by function now in the tools), H085 (T83 Arc tool,
  protocol 10; T83 Open until H086), one small fix (Gemini session names carry the start time; take's MAX_JOBS
  refusal names the jobs). Logged P46 (William): a worker may update a tools/test_*.py check that only asserts on
  its own job's changed output without asking.
- Codex windows: `codex -C /Users/Will/Sites/fretchup --add-dir /Users/Will/Sites/fretchup-jobs "Check the board"`
  in Terminal via osascript (Codex's request: the jobs folder writable). Desktop Codex needs the folder granted in
  its managed profile by William.
- For William to confirm: H085's response says he approved it touching viewport/inference.gd (arc snapping); it
  was accepted on that word.

Small fixes this session (listed for William): the Gemini session-name fix above.
