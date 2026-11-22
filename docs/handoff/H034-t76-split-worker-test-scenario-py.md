### H034 — T76: split worker/test_scenario.py into a file per feature

Author: Claude (integrator) | Date: 2026-11-21 | Status: open | For: Codex

References: T76, P07, T48; bfbfa67 (the quick test finds its sections by name, the model to follow).

Touches: worker/test_scenario.py (becomes a thin runner or goes), worker/scenario/*.py (new, one per feature),
tests/scenario_fixture.json if its layout must change, tools/featuretest.sh (the scenario line; this job may edit
this one file under tools/; H033 adds one line to it too, keep yours to the scenario entry), worker/CLAUDE.md
(the scenario-test paragraph), CLAUDE.md (only the sentence "A new feature gets steps in `worker/test_scenario.py` first").

Request: same steps, same answers, same order where order matters (later steps build on earlier ones; keep
that chain explicit, e.g. numbered file names). The runner finds feature files by name, so a new feature adds a
file and edits nothing shared; a file listed but missing fails, it doesn't hang. Report the step count before
and after (must match) and `tools/featuretest.sh` timing before and after.
