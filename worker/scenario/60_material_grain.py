"""9. paint a linked board: both copies change (T76)."""
from scenario.context import ok, only

requires = ()

def run(ctx):
    FIX = ctx.FIX
    step = ctx.step

    # 9. paint a linked board: both copies change
    PAINT = {"id": "s9", "type": "set_material", "targets": ["shelf2"], "material": "black-walnut"}
    step("paint the shelf copy walnut", FIX + [PAINT], lambda st, a, b: [
        ok(st, 1), only(a, b, {"shelf", "shelf2"}),
        ("both shelves walnut", b["boards"]["shelf"]["mat"] == b["boards"]["shelf2"]["mat"] == "black-walnut",
         (b["boards"]["shelf"]["mat"], b["boards"]["shelf2"]["mat"]))])

    # 10. turn the bottom's grain
    GRAIN = {"id": "s10", "type": "turn_grain", "targets": ["bottom"]}
    step("turn the bottom's grain", FIX + [GRAIN], lambda st, a, b: [
        ok(st, 1), only(a, b, {"bottom"}),
        ("grain turned 90 degrees", b["boards"]["bottom"]["grain"] != a["boards"]["bottom"]["grain"],
         (a["boards"]["bottom"]["grain"], b["boards"]["bottom"]["grain"]))])
    ctx.actions.update(PAINT=PAINT, GRAIN=GRAIN)
