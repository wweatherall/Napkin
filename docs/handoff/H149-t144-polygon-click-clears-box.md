### H149 — T144 step 2: the click that starts a Polygon clears digits not entered

Author: Claude (integrator, fretchup-75) | Date: 2026-11-26 | Status: open | For: either

References: T144, I72, I64, H130 (follow-up), T88 (tool interface).

Touches: viewport/tools/polygon_tool.gd (`click`), viewport/tool_context.gd (the `ui` capability: new `clear_typed`), viewport/test_tool_context.gd (the `ui` allowlist), viewport/measure_box.gd (only if a clear helper is needed), docs/specs/T88-tool-interface.md (the `ctx.ui` section), viewport/tools/CLAUDE.md (the interface list), viewport/tests/quick/polygon.gd.

Reading path:
1. `viewport/keys.gd` (around line 50): an idle tool with `accepts_idle` gets digits into the box (`box.type_char`); only Polygon has it.
2. `viewport/tools/polygon_tool.gd` `click`: starts the gesture (`state = {"active": true, ...}`) and leaves the box alone, so `5` typed before the click stays and a radius `20` typed after reads `520`.
3. `viewport/measure_box.gd` `apply` (it empties `vcb` on Return) and `update`; `viewport/tool_context.gd` the `ui` class (`typed_text`, `refresh_measurements`).

Today (checked 2026-11-26 on main e94daf4): tools can read the box (`ctx.ui.typed_text()`) but can't empty it; switching tools empties it (the polygon quick test checks that).

Request (I72): when a click starts a Polygon gesture (not the click that finishes one), empty the measurements box and
refresh it, so a radius typed next starts from nothing. Add `ctx.ui.clear_typed()` (empties measure.vcb and calls
measure.update) to the `ui` capability, since a tool may only reach the box through `ctx` (A40), and add it to the
allowlist in test_tool_context.gd, the spec's `ctx.ui` paragraph and tools/CLAUDE.md's interface line. An entered
`8s` is unaffected (Return already applied and emptied it). Other tools don't change: none takes digits while idle.

Checks: in `viewport/tests/quick/polygon.gd`, type `5` (no Return) with Polygon idle, click a centre, type `20` + Return
and check the op's radius is 20 (not 520) and sides unchanged; name it "a click that starts a polygon drops digits not
entered". It must fail without the change. test_tool_context.gd's allowlist check covers the new member.

