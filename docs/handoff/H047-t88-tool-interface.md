### H047 — T88 stage 1: the tools' interface to Main (inventory and proposal)

Author: Claude (integrator) | Date: 2026-11-22 | Status: open | For: Codex

References: T88, A33b, A34 (the tool registry), P10 (documentation owners); viewport/tools/*.gd, viewport/main.gd,
viewport/document.gd, selection.gd, presenter.gd, inference.gd, measure_box.gd, keys.gd; viewport/tools/CLAUDE.md
(the tool interface as written today). William's call, 2026-11-22: this goes before the Line tool (H046 waits for it).

Touches: docs/specs/T88-tool-interface.md (new). Read-only on all code.

Request: tools reach into Main for shared state (move_tool.gd uses `m.` ~130 times, push_tool.gd ~61); main.gd is
~2,060 lines and every feature touches it. Write the spec for a small, named interface tools use instead:
1. Inventory: for each tool, every `m.` name it reads, writes or calls, grouped by what it's for (picking and
   snapping, drafts and previews, the op list and counters, selection and context, the measurements box, materials,
   messages), and which module really owns it today (main.gd itself, or forwarded from doc / sel / pres / measure).
2. Proposal: the interface: what a tool may read, what it may call, and what goes through which owner, so a tool
   needs nothing else from Main. Name each member, say who implements it, and mark what tools write today that
   they shouldn't (state they should ask an owner to change). Say how the tests keep working (they call m.* too).
3. A migration plan: an order to move the tools (smallest first: paint, select, circle, rect, push, move), each a
   separate step behind the gate, with what each step removes from main.gd, and where the Line tool (H046) slots in.
4. Open questions for William, if any (behaviour shouldn't change; ask only where the code forces a choice).
Keep it to what a reviewer can check against the code: cite file:function for each group.
