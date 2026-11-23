### H101 — T88 after H083: Codex checks and tidies the Move migration as built (no behaviour change)

Author: Claude (integrator, fretchup-74) | Date: 2026-11-22 | Status: queued (after H083; then whenever no job holds the tool files) | For: codex

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
