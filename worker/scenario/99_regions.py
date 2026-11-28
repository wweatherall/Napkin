"""I51/P21: execute the viewport's actual region finder, compare native area, bounds and volume."""
import json
import os
import subprocess
from common import V
from scenario.context import face, ok, only, snap
from session import Session

requires = ("99_lines.py",)


def run(ctx):
    viewport = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "viewport"))
    output = os.path.abspath(os.path.join(ctx.TESTDIR, "region-predictions.json"))  # Godot runs in viewport/ (H069)
    result = subprocess.run(["/Applications/Godot.app/Contents/MacOS/Godot", "--headless", "--path", viewport,
                             "--script", "res://test_regions.gd", "--", "--regions-output=" + output],
                            capture_output=True, text=True, timeout=30)
    ctx.check("regions: viewport prediction tests pass before native comparisons", result.returncode == 0,
              result.stdout[-600:] + result.stderr[-600:])
    cases = json.load(open(output))
    for case in cases:
        if case.get("circle_radius"):
            continue  # native curved-boundary refinement is checked separately below
        spec = {k: case[k] for k in ("outline", "holes", "normal")}
        op = dict(id="region_push", type="new_board", target={"region": spec}, distance=12.5, body="region_board")
        def compare(st, a, b, c=case):
            model = ctx.S.model
            board = model.body("region_board")
            base = board.Tip.Base.Shape
            box = base.BoundBox
            bounds = [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]
            expected = c["lo"] + c["hi"]
            return [ok(st, 1), only(a, b, {"region_board"}),
                    ("native face area matches predicted preview", abs(base.Area - c["area"]) < max(0.02, c["area"] * 1e-5), (base.Area, c["area"])),
                    ("native face bounds match predicted preview", max(abs(x-y) for x,y in zip(bounds, expected)) < 0.002, (bounds, expected)),
                    ("native extrusion matches predicted volume", abs(model.world_shape(board).Volume - c["area"] * 12.5) < max(0.2, c["area"] * 0.0002), model.world_shape(board).Volume)]
        ctx.step("region prediction: " + case["name"], ctx.FIX + [op], compare)
    circular = next(c for c in cases if c.get("circle_radius"))
    import math
    circle_spec = {k: circular[k] for k in ("outline", "holes", "normal")}
    circle_spec["lines"] = ["circle_divider"]
    circle_ops = [dict(id="circle_base", type="circle", plane={"origin":[800,0,0],"normal":[0,0,1]}, radius=50),
                  dict(id="circle_stock", type="new_board", target={"rect":"circle_base"}, distance=20, body="round_stock"),
                  dict(id="circle_divider", type="line", plane={"on":face("round_stock",(0,0,1),(800,-50,20))}, end=[800,50,20]),
                  dict(id="circle_region", type="push_pull", target={"face":face("round_stock",(0,0,1),(780,0,20)), "region":circle_spec}, distance=10)]
    def exact_circle(st, a, b):
        shape = ctx.S.model.world_shape(ctx.S.model.body("round_stock"))
        return [ok(st,4), only(a,b,{"round_stock"}),
                ("native semicircle has exact volume", abs(shape.Volume - math.pi * 2500 * 25) < 0.02, shape.Volume),
                ("curved boundary retains circle edges", any(e.Curve.__class__.__name__ == "Circle" for e in shape.Edges), ""),
                ("preview area differs only by existing circle facets", abs(circular["area"] - math.pi * 1250) / (math.pi*1250) < 0.002, circular["area"])]
    ctx.step("region keeps exact circular boundary", ctx.FIX + circle_ops, exact_circle)
    base = [dict(id="region_base", type="rect", plane={"origin": [800, 0, 0], "normal": [0, 0, 1]}, size=[100,100]),
            dict(id="region_stock", type="new_board", target={"rect":"region_base"}, distance=20, body="split_stock")]
    line = dict(id="divider", type="line", plane={"on":face("split_stock", (0,0,1), (850,0,20))}, end=[850,100,20])
    region = dict(outline=[[800,0,20],[850,0,20],[850,100,20],[800,100,20]], holes=[], normal=[0,0,1], lines=["divider"])
    target = dict(face=face("split_stock", (0,0,1), (820,20,20)), region=region)
    for distance in (10, -5):
        pushed = dict(id="split_push", type="push_pull", target=target, distance=distance, resize_stock=True)
        ctx.step("region edits only half the stock %s" % distance, ctx.FIX + base + [line, pushed], lambda st, a, b, d=distance: [ok(st, 4),
            ("half alone changes volume even with resize_stock requested", abs(b["boards"]["split_stock"]["vol"] - (200000 + 5000*d)) < 0.02, b["boards"]["split_stock"]),
            ("other half still has its original top face", any(f.normalAt(0,0).z > 0.999 and f.isInside(V(875,50,20),0.001,True) for f in ctx.S.model.world_shape(ctx.S.model.body("split_stock")).Faces), "")])
    separate = dict(id="split_separate", type="new_board", target=target, distance=10, body="separate_region")
    story = ctx.FIX + base + [line, separate]
    ctx.step("region New board leaves source unchanged", story, lambda st, a, b: [ok(st, 4),
        ("source stays whole", b["boards"]["split_stock"]["vol"] == 200000, ""),
        ("separate region exact volume", b["boards"]["separate_region"]["vol"] == 50000, "")])
    for what, change in [("missing drawing", {"lines":["missing"]}), ("outside source", {"outline":[[750,0,20],[850,0,20],[850,100,20],[750,100,20]]}), ("off source plane", {"outline":[[800,0,21],[850,0,21],[850,100,21],[800,100,21]]})]:
        spec = dict(region, **change)
        op = dict(id="invalid_region", type="push_pull", target=dict(target, region=spec), distance=10)
        ctx.step("region rejects " + what, ctx.FIX + base + [line, op], lambda st, a, b: [
            ("rejected atomically", st[-1]["status"] == "failed" and b["boards"]["split_stock"]["vol"] == 200000, st[-1])])
    ctx.S.sync(story)
    live = snap(ctx.S)
    ctx.S.sync(story[:-1])
    ctx.check("region undo leaves drawing and source", "separate_region" not in ctx.S.model.bodies() and any(getattr(o,"SSLineId","") == "divider" for o in ctx.S.doc.Objects))
    ctx.S.sync(story)
    ctx.check("region redo restores exact state", snap(ctx.S) == live)
    fresh = Session(None)
    try:
        fresh.sync(story)
        ctx.check("region story equals fresh build", snap(fresh) == live)
    finally: fresh.close()
    ctx.S.save()
    path = ctx.S.path
    ctx.S.close()
    ctx.S = Session(path)
    ctx.check("region story reopens exactly", snap(ctx.S) == live)
    ctx.S.sync(ctx.FIX)
    ctx.check("region undo all restores fixture", snap(ctx.S) == ctx.S0)
