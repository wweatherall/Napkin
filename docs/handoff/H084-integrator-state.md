### H084 — For the next integrator session: where things stand

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: the integrator

References: docs/integrator.md, BOARD.md, tools/startup.py.

Touches: nothing (a note). Archive it once read: `python3 tools/handoff.py archive H0NN`.

Taking over: `python3 tools/integrator.py take fretchup-73` (a /clear keeps the name; another name needs
`--william`), then `python3 tools/startup.py`, then re-arm the watch (docs/integrator.md). A watch from before the
clear may still be running; a second one is harmless.

Done this session (2026-11-22, late evening; main pushed): merged H079 (T88 step 5, Push/Pull on ToolContext,
Codex; William chose no ultra review); map and viewport guides updated. Wrote H083 (T88 step 6: Move, and the
legacy setup's removal), with the first "Reading path:" line. T107 dropped by William: briefs get a Reading path
line instead (integrator.md, Writing jobs).

Ready, for Codex (William is spending Codex tokens; don't start Claude workers unless he asks): H080 (T105), H081
(T106), H083 (T88 step 6). No overlaps. Then H052 (T66 units), queued after H083.

Codex's feedback after H079: the brief and the recorded suites were what made it safe; the friction was who owns
what (Main, the tool, ToolContext and the presenter all had face-highlight methods). Keep writing ownership into
briefs.

Waiting on William, still open from earlier: the whole-code `/code-review ultra` findings (H074 in the archive) and
a light /code-review on every merge.
