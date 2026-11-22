"""12. a new board drawn on a face, as a separate board (B) (T76)."""
from scenario.context import ok, on_rect, only

requires = ()

def run(ctx):
    FIX = ctx.FIX
    step = ctx.step

    # 12. a new board drawn on a face, as a separate board (B)
    CAP = [on_rect("s12r", "left", [0, 0, 1], [4, 100, 720], [10, 100]),
           {"id": "s12", "type": "push_pull", "target": {"rect": "s12r"}, "distance": 20, "body": "cap"}]
    step("draw a separate cap on the left side", FIX + CAP, lambda st, a, b: [
        ok(st, 2), only(a, b, {"cap"}),
        ("cap sits on top (z 720..740)", b["boards"].get("cap", {}).get("box", (0,) * 6)[2::3] == (720, 740),
         b["boards"].get("cap"))])

    # 13. a /N row of new posts
    POSTS = [{"id": "s13r", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [700, 0, 0]}, "size": [20, 20]},
             {"id": "s13p", "type": "push_pull", "target": {"rect": "s13r"}, "distance": 100, "body": "post"},
             {"id": "s13", "type": "move", "targets": ["post"], "vector": [300, 0, 0], "copy": True, "count": 3, "divide": True,
              "new_ids": ["post2", "post3", "post4"]}]
    step("a post and three copies spread over 300 (/3)", FIX + POSTS, lambda st, a, b: [
        ok(st, 3), only(a, b, {"post", "post2", "post3", "post4"}),
        ("posts at x 700, 800, 900, 1000", [b["boards"].get(k, {}).get("box", (None,))[0] for k in ("post", "post2", "post3", "post4")]
         == [700, 800, 900, 1000], [b["boards"].get(k) for k in ("post2", "post3", "post4")])])
    ctx.actions.update(POSTS=POSTS)
