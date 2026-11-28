### H218 — Read the kill matrix: which tests stand for which, the gaps, and a draft tree of dense tests (T171 step 2)

Author: Claude (integrator, integrator-opus) | Date: 2026-11-28 | Status: queued (after H217) | For: either | Item: T171

References: H217 (`tests/kill_matrix.json`: per mutant, the tests that killed it); T172 and its notes (William's tree:
ultra-dense tests at the top, each linking about 5 less dense ones; a bug may fail two branches, so a node may share
children; a middle level can be a group of its children); T173 (cutting the merge gate, only where this shows a test is
covered); William, 2026-11-28: no cuts until he agrees.

Today: once H217 merges, `tests/kill_matrix.json` holds a sample matrix (20 mutants per worker file) and per-test
seconds; the integrator may have replaced it with a full overnight run by the time this starts (read whichever is
committed).

Touches: tools/kill_matrix.py (new), tools/test_kill_matrix.py (new), tests/dense_tree_draft.json (new, generated).
The integrator adds its line to the tools README at merge.

Request:
1. `python3 tools/kill_matrix.py --report` reads the matrix and prints:
   - the mutation score per worker file (killed / covered) and the surviving mutants grouped by function (the gaps:
     code whose bugs no test notices);
   - per test file: mutants it kills, mutants only it kills, and seconds;
   - subsumption: test A stands for test B when A kills everything B kills (B non-empty); list the pairs;
   - tests that kill nothing (candidates to cut or rewrite) and tests with no unique kills (candidate probes), for
     William to look at, not to change (no test is changed in this job);
   - the smallest set of test files that kills every killed mutant (greedy set cover, cheapest per new kill first), its
     total seconds against the whole suite's: the front line's cost.
2. `--tree` writes `tests/dense_tree_draft.json`: a draft of William's tree, built by grouping tests whose kill sets
   overlap most (hierarchical clustering on Jaccard similarity of kill sets), about 5 children per node, the leaves
   being test files; each node lists the mutants it kills, its children and their total seconds. A test that belongs
   under two nodes is listed under both. Print it as an indented tree with kill counts and seconds per node.
3. Say in your response what it shows: how much of the suite the front line is, how deep the tree goes, and which
   gaps look most worth a test. It's a draft for the integrator's T172 design, not the design itself.

Checks:
- `tools/test_kill_matrix.py` (summary line `KILL MATRIX TESTS: N passed, M failed`): on a small hand-made matrix,
  subsumption, unique kills, the set cover and the tree come out as worked by hand; a test killing nothing is listed.
- Run it on the committed matrix, commit `tests/dense_tree_draft.json`, paste the report and the tree into your response.
- `tools/TEST_BEFORE_MERGING.sh` passes.
