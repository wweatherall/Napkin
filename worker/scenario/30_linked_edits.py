"""3. draw on a linked board: its copy changes too (T76)."""
from scenario.context import ok, on_rect, only

requires = ()

def run(ctx):
    FIX = ctx.FIX
    step = ctx.step

    # 3. draw on a linked board: its copy changes too
    BUMP = [on_rect("s3r", "shelf", [0, 0, 1], [100, 100, 378], [50, 50]),
            {"id": "s3", "type": "push_pull", "target": {"rect": "s3r"}, "distance": 30}]
    step("add a block on the linked shelf", FIX + BUMP, lambda st, a, b: [
        ok(st, 2), only(a, b, {"shelf", "shelf2"}),
        ("shelf grew by the block", abs(b["boards"]["shelf"]["vol"] - a["boards"]["shelf"]["vol"] - 50 * 50 * 30) < 0.1,
         b["boards"]["shelf"]["vol"]),
        ("its linked copy grew the same", b["boards"]["shelf2"]["vol"] == b["boards"]["shelf"]["vol"], b["boards"]["shelf2"])])

    # 4. make the copy unique first: the original stays as it was
    UNIQUE = {"id": "s4u", "type": "make_unique", "targets": ["shelf2"]}
    BUMP2 = [on_rect("s4r", "shelf2", [0, 0, 1], [100, 100, 558], [50, 50]),
             {"id": "s4", "type": "push_pull", "target": {"rect": "s4r"}, "distance": 30}]
    step("make the shelf copy unique, then add a block", FIX + [UNIQUE] + BUMP2, lambda st, a, b: [
        ok(st, 3), only(a, b, {"shelf2"}),
        ("the copy grew", abs(b["boards"]["shelf2"]["vol"] - a["boards"]["shelf2"]["vol"] - 50 * 50 * 30) < 0.1,
         b["boards"]["shelf2"]["vol"])])
    ctx.actions.update(BUMP=BUMP)
