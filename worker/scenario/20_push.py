"""1. push a face of a plain board (T76)."""
from scenario.context import face, ok, only

requires = ()

def run(ctx):
    FIX = ctx.FIX
    S = ctx.S
    step = ctx.step

    # 1. push a face of a plain board
    FRONT = {"id": "s1", "type": "push_pull", "target": {"face": face("bottom", [0, -1, 0], [300, 0, 9])}, "distance": 20}
    step("push the bottom's front edge out 20", FIX + [FRONT], lambda st, a, b: [
        ok(st, 1), only(a, b, {"bottom"}),
        ("bottom 20 mm deeper", b["boards"]["bottom"]["box"][1] == -20, b["boards"]["bottom"]["box"]),
        ("volume grew by the strip", abs(b["boards"]["bottom"]["vol"] - a["boards"]["bottom"]["vol"] - 564 * 18 * 20) < 0.1,
         b["boards"]["bottom"]["vol"])])

    # 2. pushing the holed top face up: the push carries the hole with it (the face it extrudes has the hole in it)
    THICK = {"id": "s2", "type": "push_pull", "target": {"face": face("bottom", [0, 0, 1], [100, 100, 18])}, "distance": 6}
    step("push the bottom's holed top face up 6", FIX + [THICK], lambda st, a, b: [
        ok(st, 1), only(a, b, {"bottom"}),
        ("the hole stays open through the new 6 mm", abs(b["boards"]["bottom"]["vol"] - (564 * 400 - 1600) * 24) < 0.1,
         b["boards"]["bottom"]["vol"])])

    # 2b. the board made thicker by its own FreeCAD value (the Properties panel, T46): the through-hole follows (I24)
    BOTTOM_EXT = next(o.Name for o in S.doc.Objects if getattr(o, "SSOp", "") == "p_bottom" and o.TypeId == "Part::Extrusion")
    THICK_PROP = {"id": "s2b", "type": "property_edit", "body": "bottom", "object": BOTTOM_EXT, "property": "LengthFwd",
                  "value": "24mm", "mode": "value"}
    step("make the bottom 24 thick in its FreeCAD value", FIX + [THICK_PROP], lambda st, a, b: [
        ok(st, 1), only(a, b, {"bottom"}),
        ("the through-hole still goes through", abs(b["boards"]["bottom"]["vol"] - (564 * 400 - 1600) * 24) < 0.1,
         b["boards"]["bottom"]["vol"])])
    ctx.actions.update(FRONT=FRONT, THICK=THICK, THICK_PROP=THICK_PROP)
