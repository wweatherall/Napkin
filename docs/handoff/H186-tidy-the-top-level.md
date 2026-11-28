### H186 — Napkin's top level: two old launchers go, the wave simulator moves to tools/

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: open | For: gemini

References: T155 (William's answers, 2026-11-27, in its notes), T164 (the three reference docs wait for William:
not this job), Q18 (decided: the chained-cut timing the speed launcher ran), W09 (the wave-front tunables the
simulator tries), P73.

Item: T155 | Completes: T155

Touches: Check FreeCAD speed.command (deleted), Open holed panel example.command (deleted), sim/front_sim.py (moved;
sim/ goes), tools/front_sim.py (new), the moved file, 03_Past_Decisions/decision-log.md (the Tunables table's
`Simulator` row only), tools/README.md (one line).

Today (checked 2026-11-27): nothing in the repo runs or links to the two launchers (`git grep` finds only T155).
`tools/cut_chain_check.py`, which the speed launcher ran, stays, and examples/holed_panel.FCStd, which the panel
launcher copied, stays in examples/ (protocol_map.py --check reads examples/). sim/front_sim.py imports only `math`
and `sys` and reads no files, so it runs the same from tools/. tools/test_scope.py doesn't name `sim`: an unknown top-level
folder means full scope, so tools/test_test_scope.py's `sim/x.py` fixture stays true after the move and doesn't change.

Request:
1. `git rm` the two launchers; `git mv sim/front_sim.py tools/front_sim.py`, so its history follows it.
2. The decision log's Tunables `Simulator` row: both paths become `tools/front_sim.py`; nothing else in the row or
   the log changes.
3. tools/README.md: one line, `front_sim.py` — simulate the wave-front controller to try W09's values without
   Godot (`python3 tools/front_sim.py`).
4. Your response's last step line: `Completes: T155`.

Not in this job: 'Codex's suggestions.md', FREECAD_FEATURE_MAP.md, the PNG (T164, waiting for William), README.txt,
`Start Shop Sketch.command`, common.sh, examples/.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes; `python3 tools/front_sim.py` runs as it did from sim/ (same output).
- `git grep -n "sim/front_sim\|Check FreeCAD speed\|Open holed panel"` finds nothing outside 03_Past_Decisions'
  archives, the handoff archive and this entry.
