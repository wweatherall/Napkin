"""14. a hole into the side that the mirror carries across (T76)."""
from scenario.context import ok, on_rect, only

requires = ()

def run(ctx):
    FIX = ctx.FIX
    step = ctx.step

    # 14. a hole into the side that the mirror carries across
    HOLE_L = [on_rect("s14r", "left", [-1, 0, 0], [0, 200, 100], [30, 30]),
              {"id": "s14", "type": "push_pull", "target": {"rect": "s14r"}, "distance": -18, "through": True}]
    step("cut a through-hole in the left side", FIX + HOLE_L, lambda st, a, b: [
        ok(st, 2), only(a, b, {"left", "right"}),
        ("left lost 30 x 30 x 18", abs(a["boards"]["left"]["vol"] - b["boards"]["left"]["vol"] - 30 * 30 * 18) < 0.1,
         b["boards"]["left"]["vol"]),
        ("the mirror has it too", b["boards"]["right"]["vol"] == b["boards"]["left"]["vol"], b["boards"]["right"]["vol"])])
    ctx.actions.update(HOLE_L=HOLE_L)
