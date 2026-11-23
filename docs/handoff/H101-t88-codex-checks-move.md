### H101 — T88 after H083: Codex checks and tidies the Move migration as built (no behaviour change)

Author: Claude (integrator, fretchup-74) | Date: 2026-11-22 | Status: answered | For: codex

References: H083 (T88 step 6: Move to ToolContext, the legacy setup goes), T88, A34. William, 2026-11-22: Codex
started H083 and its session went quiet with the work nearly done; Gemini finishes it so the queue moves
(H052 and the Arc jobs wait for it). William wants Codex, which built most of it and knows the design, to
keep the job: after H083 merges, check the codebase around it and refactor where Gemini's finish, or the
migration as a whole, falls short of what Codex meant.

Touches: the same files as H083: viewport/tools/*.gd (every tool, tool.gd), viewport/tool_context.gd,
viewport/test_tool_context.gd, viewport/presenter.gd, viewport/main.gd (only what Move's migration left
there: the aliases, `_make_tools`, the guides body), viewport/tool_geometry.gd, viewport/test_tools.gd,
viewport/tests/quick/move.gd. Not the worker, not docs/protocol.md, ARCHITECTURE.md or the folder guides
(write those as "Architecture:" / "For the integrator:" lines).

Start: your old worktree and its branch were handed to Gemini (your uncommitted work was committed unchanged as
0167c59) and removed when H083 merged; 0167c59 is still in main's history. Take this job with `python3 tools/job.py take --as
codex` once it is Ready: it starts a fresh branch from main, which by then holds H083 as merged.

Request:
1. Read what Gemini added on top of your commit: `git diff 0167c59 <H083's merge commit>^2` (the merge commit is
   named in H083's archive entry and in `git log --merges --grep H083`), then the migration as merged.
2. Fix what's wrong or unfinished in it, and tidy what you'd have done differently: leftovers of the legacy
   setup, duplicated bodies between main.gd, presenter.gd and the tools, aliases main.gd keeps that nothing
   reads any more (check the tests too), anything a tool still reaches through main that ToolContext should give it.
3. No behaviour change: every quick-test and feature check passes unchanged. A check you think is wrong: say so
   in the response, don't change it. A behaviour change you'd want: a Follow-up line for William, not code.
4. Nothing waits for this job (William, 2026-11-22): other jobs (H052 units, the Arc tool) may have built on
   Gemini's version by the time you start. Start from main as it is then, and fix what your tidy touches in them too.
5. Keep it reviewable: one commit per kind of change, each saying what it moves and why.

Checks: the existing ones (tools/featuretest.sh, tools/quicktest.sh, the T88 marker checks in test_tools.gd).
A refactor that removes an alias adds no check; one that moves a body keeps the checks that covered it pointing
at its new home.

Response: what you found in Gemini's finish (a short list: fine / changed, and why), what you tidied, and any
alias or body you left with the reason.

Reading path: H083's entry and response, then `tool.gd` → `tool_context.gd` → `move_tool.gd` → main.gd
`_make_tools` and the aliases → presenter.gd `present_draft` / `mirror_preview`. Who owns what: tools own their
gesture state, ToolContext is all a tool gets from the app, presenter.gd draws, main.gd wires.

Run `tools/featuretest.sh` and `tools/quicktest.sh` while building, then `python3 tools/job.py test`. End your
response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.

Response — Codex, 2026-11-23. Branch `codex/h101-t88-codex-checks-move`, code through `c3be19b`.

- Compared `0167c59` with the second parent of merge `f2ad057` and inspected Gemini's finish in `a7ad7f9`. Keep the float bounds expectation and Line's check that it receives the window's actual context. Both express the intended contracts. Keep William's approved A40 numbering. The log fixture's assumption about branch placeholders is already tracked under H059. The intervening merge from main accounts for the unrelated worker changes.
- Fixed an issue inherited from the earlier preview path. It took the mesh from a newly allocated line node on each outlined redraw and lost the node. Commit `50339b9` lets previews, mirror outlines and guides request a mesh directly. A headless comparison of 256 redraws counted 256 added orphan nodes with the H083 context and zero with the fix. The outline still contained the expected vertices.
- Removed unused Main geometry, collision, marker, cache and wave forwarders in `d1e60eb`. Kept the aliases with callers, including `_lines` for drawing, `_begin_wave` for reloads, `move_state` and `draft_bboxes` for suites, and the geometry and colour names pinned by the context checks. H114 owns the separate selection forwarders, including `unit_tris`.
- Simplified Move's board-draft construction in `c3be19b`. It reads each source's triangles once and emits its offsets in reserved body-ID order. A row move still previews all its members and the wave still starts at the last offset. The newer units formatting remains in place.
- Verified the feature suite, 254 quick checks, 147 context checks, 12 registry checks and the full gate with recorded-suite comparisons. The clean code commit passed `job.py test`. No new decision IDs or open questions.

Changed from the brief: William assigned H101 directly while it was queued. Registered the job using a one-off H101 selection and the normal locked claim operation. The preferences job and this review changed different functions. The queue implementation and main checkout were left alone.
Architecture: The presenter supplies a line mesh directly to the existing view preview capability. Its node-returning lines helper remains for callers that put a node in the scene.
For the integrator: In the viewport guide, remove the reference to Main forwarding `_tri_mesh` and describe the presenter supplying meshes for existing overlay nodes. Main still forwards `_lines` for node callers.
Result: c3be19b; feature tests and 254 quick checks passed, full gate passed and recorded suites matched; kept Gemini's finish, fixed the outlined-preview node leak, removed unused Main aliases and simplified Move's draft ordering
