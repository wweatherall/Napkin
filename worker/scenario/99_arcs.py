"""I60/P21: compare the viewport's arc regions with exact FreeCAD joins and cuts."""
import json
import math
from pathlib import Path
import subprocess

from common import V
from scenario.context import face, ok

requires = ()


def run(ctx):
    viewport = Path(__file__).resolve().parents[2] / "viewport"
    output = Path(ctx.TESTDIR).resolve() / "arc-prediction.json"
    result = subprocess.run(
        ["/Applications/Godot.app/Contents/MacOS/Godot", "--headless", "--path", str(viewport),
         "--script", "res://test_regions.gd", "--", "--arc-output=" + str(output)],
        capture_output=True, text=True, timeout=30,
    )
    ctx.check("arc: viewport region predictions passed", result.returncode == 0, result.stdout + result.stderr)
    if result.returncode:
        return
    prediction = json.loads(output.read_text())
    board = "arc_stock"
    radius = 72.5
    sweep = 4 * math.atan2(20, 50)
    area = 5000 + radius**2 * (sweep - math.sin(sweep)) / 2
    base = [
        dict(id="arc_base", type="rect", plane={"origin": [800, 0, 0], "normal": [0, 0, 1]}, size=[100, 100]),
        dict(id="arc_board", type="push_pull", target={"rect": "arc_base"}, distance=20, body=board),
    ]
    arc = dict(id="divider_arc", type="arc", plane={"on": face(board, (0, 0, 1), (850, 0, 20))},
               mid=[870, 50, 20], end=[850, 100, 20], snap_start=True, snap_end=True)
    region = {k: prediction[k] for k in ("outline", "holes", "normal")}
    region["lines"] = [arc["id"]]
    target = dict(face=face(board, (0, 0, 1), (830, 50, 20)), region=region)
    for distance in (10, -10):
        push = dict(id="arc_push", type="push_pull", target=target, distance=distance)

        def exact(st, _before, _after, depth=distance):
            model = ctx.S.model
            shape = model.world_shape(model.body(board))
            native_area = (shape.Volume - 200000) / depth
            sketch = next(o for o in ctx.S.doc.Objects if getattr(o, "SSLineId", "") == arc["id"])
            return [ok(st, 4),
                    ("saved as one fully constrained sketch arc", sketch.FullyConstrained
                     and abs(sketch.Geometry[0].Radius - radius) < 1e-8, sketch.Geometry),
                    ("solid has exact arc-bounded volume", abs(native_area - area) < 0.002, native_area),
                    ("prediction agrees within native_region bound",
                     abs(native_area - prediction["area"]) <= max(0.001, 400 * 0.2, 10000 * 0.005), prediction["area"]),
                    ("solid has a cylindrical face at the native radius",
                     any(type(f.Surface).__name__ == "Cylinder" and abs(f.Surface.Radius - radius) < 1e-8
                         for f in shape.Faces), ""),
                    ("other side retains original top", any(f.normalAt(0, 0).z > 0.999
                     and f.isInside(V(885, 50, 20), 0.001, True) for f in shape.Faces), "")]

        ctx.step("arc region push %s" % distance, ctx.FIX + base + [arc, push], exact)

    # A loose profile uses the same native refinement path as a board face.
    profile = dict(base[0], plane={"origin": [800, 0, 20], "normal": [0, 0, 1]})
    loose_arc = dict(arc, plane={"origin": [850, 0, 20], "normal": [0, 0, 1]})
    extrude = dict(id="arc_profile_push", type="push_pull", target={"rect": profile["id"], "region": region},
                   distance=10, body="arc_profile_stock")
    def exact_profile(st, _before, _after):
        model = ctx.S.model
        volume = model.world_shape(model.body(extrude["body"])).Volume
        return [ok(st, 3), ("only the exact cell is extruded", abs(volume - area * 10) < 0.002, volume)]

    ctx.step("arc splits a loose rectangle profile", ctx.FIX + [profile, loose_arc, extrude], exact_profile)

    for label, mid in [("collinear", [850, 50, 20]), ("off-plane", [870, 50, 21]), ("coincident", [850, 0, 20]),
                       ("non-finite", ["inf", 50, 20])]:
        ctx.step("arc rejects " + label, ctx.FIX + base + [dict(arc, mid=mid)], lambda st, a, b: [
            ("failed without creating a drawing", st[-1]["status"] == "failed"
             and all(getattr(o, "SSLineId", "") != arc["id"] for o in ctx.S.doc.Objects), st[-1])])
