### H219 — Mutation testing for the viewport's GDScript (T171 step 3)

Author: Claude (integrator, integrator-opus) | Date: 2026-11-28 | Status: open | For: Codex | Item: T171

References: H217 (`tools/mutate.py`: its runner, lanes, resume and matrix); T171, T172; viewport/CLAUDE.md (the
viewport tests, the quick test's lanes).

Today: once H217 merges, `tools/mutate.py` mutates worker/ Python with `ast` and picks the tests to run from line
traces. GDScript has neither: there is no GDScript parser in Python and no tracer, so nothing says which viewport test
runs which line. The viewport feature tests (`viewport/test_*.gd`, 7 files, about 37 s added up, Godot headless) are
fast; the quick test (`tools/quicktest.sh`, three lanes, about 30 s each, all 66 quick-test files) is the slow part.

Touches: tools/mutate.py (new in H217; `--gd`), tools/test_mutate.py (new in H217), tests/kill_matrix_viewport.json (new, generated).

Request:
1. `--gd <viewport/file.gd>` makes mutants of a .gd file with a small tokenizer (skip strings and comments; GDScript
   comparison, arithmetic and `and`/`or`/`not` tokens, number constants, `true`↔`false`, a statement line inside a
   `func` replaced by `pass` at the same indent); same id scheme and operators as H217 where GDScript has them. Mutate
   `viewport/*.gd` and `viewport/tools/*.gd`, not tests or `viewport/tests/`.
2. With no traces, pick tests by what loads the file: every viewport feature test always (they're fast), and the quick
   test only with `--with-quick` (it's the expensive part: say what a sample costs with it). A mutant that breaks the
   parse is killed by `tools/CHECK_THE_SCRIPTS_PARSE.sh` first and recorded as `parse` (cheap, and not interesting).
3. Run a `--sample 10` over the viewport's scripts without the quick test and a small one (`--sample 2`) with it; commit
   `tests/kill_matrix_viewport.json` (same format as `tests/kill_matrix.json`). Say in your response the costs, the
   projected full run, how many survived where, and whether the quick test catches mutants the feature tests miss.

Checks:
- `tools/test_mutate.py`: each GDScript operator on a small script gives the expected mutant, nothing inside a string or
  comment is mutated, a `pass` keeps its indent, a parse-breaking mutant is recorded `parse`.
- The sample runs, the matrix committed, the numbers in your response.
- `tools/TEST_BEFORE_MERGING.sh` passes.
