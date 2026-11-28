### H217 — Mutation testing for worker/: plant small bugs one at a time and record which tests catch each (T171 step 1)

Author: Claude (integrator, integrator-opus) | Date: 2026-11-28 | Status: answered | For: Codex | Item: T171

References: T171 (William, 2026-11-28: go ahead, "divide it into as many jobs as you think is necessary"); T172 and its
notes (William's tree of dense tests: ultra-dense tests at the top, each linking about 5 less dense ones, down to tests
that pinpoint the cause); H214 (`tools/test_inventory.py`, `tests/test_inventory.json`: each file's runner and seconds);
H215 (`tools/line_trace.py`, `test_inventory.py --coverage`: which lines each test runs); ChatGPT's caution, 2026-11-28:
running the same lines doesn't mean catching the same bugs, which is why this matrix matters more than coverage.

Today: `tools/test_inventory.py --coverage` traces every worker and tools test file (about 9 minutes) and writes per-test
line traces to `scratch/coverage/` (not committed; a fresh worktree has none) and per-file functions to
`tests/test_coverage.json`. `tools/featuretest.sh` can be sourced for `test_runner_for <file>` and `run_test_command`,
which set up each test's runner, TESTDIR and private FreeCAD config. Worker line coverage is 90%.

Touches: tools/mutate.py (new), tools/test_mutate.py (new), tests/kill_matrix.json (new, generated).
The integrator adds its line to the tools README at merge.

Request:
1. `tools/mutate.py --list <worker/file.py>` makes the mutants of a file with `ast`, each with a stable id
   `file:line:col:operator`: a comparison flipped (`<`↔`>=`, `<=`↔`>`, `==`↔`!=`), `+`↔`-` and `*`↔`/`, `and`↔`or`, a
   `not` dropped, a number constant n → n+1 (0 → 1), `True`↔`False`, a statement inside a function replaced by `pass`,
   and a `return x` made `return None`. Skip docstrings, logging and print lines, and `if __name__` blocks (mutants there
   are noise). Mutate worker/*.py only, never test files.
2. Run a mutant: in an isolated copy (a detached `git worktree` under `scratch/mutation/tree-<n>`, one per parallel
   lane, removed at the end; the job's own tree is never mutated), write the mutant, run every test file whose trace
   covers its line (from `scratch/coverage/`, regenerated first with `test_inventory.py --coverage` if missing or older
   than the code), each through featuretest.sh's runner with a time limit of 3× its time in `tests/test_inventory.json`,
   then restore the file. Record per test: killed (fails or prints a FAIL), survived, or timeout (counted as killed,
   kept apart). Run all covering tests, not just until the first kill: the matrix needs every test's answer. A mutant no
   test covers is recorded `no coverage` without running anything.
3. Make it resumable and bounded: results append to `scratch/mutation/results.jsonl`; a rerun skips mutant ids already
   there (unless the file changed since); `--budget-minutes N` stops cleanly; `--lanes N` (default 4) runs side by side;
   `--sample K` takes K mutants per file, spread through the file, with a fixed seed.
4. `--matrix` writes `tests/kill_matrix.json`: per mutant its id, function, operator and the tests that killed it (by
   file; the check names that failed where the output gives them); per test file its seconds. Keep it compact enough to
   commit (lists of indexes, not repeated names).
5. In this job, run `--sample 20` over all of worker/ and commit that matrix. Say in your response how long a mutant
   takes on average, the projected time for every mutant in worker/ at 4 lanes, how many mutants survived and in which
   functions, and anything that made results noisy (flaky tests, mutants that hang FreeCAD). The full run is a command
   the integrator starts overnight after the merge.

What can fail:
- A mutant leaves a FreeCAD process or a model file behind and the next run sees it. Check: every test runs with its own
  TESTDIR in its lane's tree, and after a run `git status` in that tree is clean before the next mutant.
- A killed run is reported as survived because the runner printed no summary line. Check: a test with no summary line
  counts as killed (it crashed), and a test-only check plants a mutant that makes a worker module fail to import.
- The real repo is changed. Check: a run ends with `git status` in the job's tree showing only the files it means to
  write.

Checks:
- `tools/test_mutate.py` (summary line `MUTATE TESTS: N passed, M failed`): each operator on a tiny source gives the
  expected mutant and nothing in a docstring; ids are stable across runs; resume skips finished ids; a covering-test
  lookup picks the right test files from a fake trace; a crash counts as killed.
- The sample run, `tests/kill_matrix.json` committed, the numbers in your response.
- `tools/TEST_BEFORE_MERGING.sh` passes.

## Response (2026-11-28, Codex worker)

Branch `codex/h217-mutation-runner` carries the runner in `d0c1844` and `72677af`, the sample in `8a5cb60`, and the process cleanup fixture in `5092556`.

The fixed-seed `--sample 20` run recorded 482 mutants across all 25 worker modules and ran 2,507 individual tests. Tests caught 319 mutants, 123 survived in 72 functions or module scopes, and 40 had no traced coverage. The covered mutation score was 72.2%. A mutant averaged 34.7 seconds in its lane, or 37.8 seconds among mutants with traced coverage. Weighting each module's sample runtime by its full mutant count projects 17.2 hours for all 7,224 mutants on four lanes. Weighting the observed cost of each test by its projected invocation count gives 17.8 hours.

All 21 covering tests passed against unmodified worker sources in the same isolated runner. The sample recorded 68 test timeouts across 48 mutants, with 40 in `worker/test_outside_save.py`. Timeouts supplied the only kill for six mutants. Mutations that prevent the deletion fixed-point loop or the circle parent traversal from advancing account for several timeouts. The coverage tracer reported untraced child processes in `worker/test_outside_save.py`, `worker/test_scenario.py`, and `worker/test_serve.py`. The matrix uses the available line traces. All 25 early unnamed kills reproduced on replay, and the replay recovered one additional check label.

Each invocation used a separate test directory and FreeCAD configuration. Lane status was checked after restoration, and the sample and short-budget check both removed their detached worktrees. A repeat `--sample 20` skipped all 482 saved IDs. I checked every exported row against the journal and its covering-test selection. The 169,261-byte matrix indexes 45 tests and 794 failed check names.

The initial full gate exposed a process cleanup check that depended on startup completing within a short window. The updated check waits for the child to report that it started before checking cleanup, and a separate check exercises the test timeout.

### Surviving mutants by worker function

- `worker/arc.py` (3) — `ArcActions.op_arc` (3)
- `worker/assembly.py` (8) — `AssemblyActions.copy_into_assembly` (1), `AssemblyActions.move_members` (4), `AssemblyActions.op_make_assembly` (3)
- `worker/circle.py` (7) — `CircleActions.circle_feature` (2), `CircleActions.circle_world` (2), `CircleActions.op_circle` (3)
- `worker/common.py` (5) — `Frame.shape` (1), `add_props` (2), `material_card` (2)
- `worker/deletion.py` (2) — `DeleteActions.op_delete` (1), `DeleteActions.remove_unneeded` (1)
- `worker/drawing.py` (15) — `<module>` (11), `dim_h` (2), `extents` (1), `paper_box` (1)
- `worker/export.py` (11) — `<module>` (1), `add_drawing_page` (3), `board_mesh_file` (1), `cuts_of` (1), `material_color` (1), `mesh_of` (3), `write_glb.add_view` (1)
- `worker/field_audit.py` (1) — `format_report` (1)
- `worker/length_input.py` (1) — `evaluate` (1)
- `worker/line.py` (5) — `LineActions.ground_region_sheet` (1), `LineActions.native_region` (2), `LineActions.op_line` (1), `LineActions.polygon_face` (1)
- `worker/materials.py` (12) — `<module>` (11), `card_text` (1)
- `worker/mirror.py` (5) — `MirrorActions.mirror_input` (1), `MirrorActions.op_mirror` (4)
- `worker/model.py` (5) — `Model.assembly_of` (1), `Model.check_result` (1), `Model.plane_feature` (1), `Model.resolve_face` (2)
- `worker/move.py` (7) — `MoveActions.copy_assembly_mirror` (1), `MoveActions.copy_assembly_mirror.clone` (1), `MoveActions.copy_body` (1), `MoveActions.new_array` (1), `MoveActions.op_make_unique` (2), `MoveActions.op_move` (1)
- `worker/object_properties.py` (2) — `apply` (1), `describe` (1)
- `worker/op_contracts.py` (1) — `collect_contracts` (1)
- `worker/paint.py` (2) — `PaintActions.board_axes` (1), `PaintActions.op_turn_grain` (1)
- `worker/plane_fit.py` (4) — `_active_tips` (1), `apply` (1), `resize_face` (1), `update` (1)
- `worker/polygon.py` (6) — `PolygonActions.op_polygon` (2), `PolygonActions.polygon_feature` (1), `PolygonActions.polygon_world` (3)
- `worker/push.py` (4) — `PushActions._new_board_op` (1), `PushActions._resize_stock_op` (1), `PushActions._resolve_push_target` (1), `PushActions.op_rect` (1)
- `worker/replay.py` (2) — `<module>` (2)
- `worker/serve.py` (3) — `run_sync` (1), `serve` (1), `serve.release` (1)
- `worker/session.py` (1) — `Session.sync` (1)
- `worker/update_old_files.py` (7) — `_free_rects_in` (1), `_sha256_file` (1), `_upgrade_journal_obj` (2), `_v_cross` (1), `update_paths` (1), `upgrade_op` (1)
- `worker/visibility.py` (4) — `VisibilityActions.add_hidden_props` (1), `VisibilityActions.op_hide` (3)

Changed from the brief: the commit hook regenerated `ARCHITECTURE.md` to index the new runner.
Changed from the brief: the commit hook regenerated `docs/dependency-map.md` to index the new runner.
Architecture: `tools/mutate.py` owns mutation generation, detached lane execution, resumption by source digest and kill matrix export.
Architecture: `tools/mutate.py` uses the per-test line traces and the test inventory to select and time tests, then runs them through `tools/featuretest.sh`.
Architecture: `tests/kill_matrix.json` stores zero-based indexes into `tests` and `checks`. A mutant's `killed` list includes its `timeouts` list. Each `failures` entry pairs a test index with the indexes of its failed check names.
For the integrator: Run `python3 tools/mutate.py --lanes 4` after merge and export with `python3 tools/mutate.py --matrix`. To cap each overnight session, supply `--budget-minutes` and repeat the command to resume. Add the runner's line to the tools README at merge.
Result: 5092556; full TEST_BEFORE_MERGING.sh passed with 439 quick viewport checks, 43 mutation runner checks and 0 known failures; committed the resumable worker mutation runner and the 482-mutant kill matrix
