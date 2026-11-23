"""I61: a tangent arc cuts a tabletop through at the two side faces."""
import math

from common import V
from scenario.context import face, ok


def run(ctx):
    board = "tangent_stock"
    radius = 50
    x, y, top = 800, 0, 20
    normal = (0, 0, 1)
    start = [x + radius, y, top]
    end = [x, y + radius, top]
    inset = radius * (1 - math.sqrt(0.5))
    arc = dict(id="tangent_arc", type="arc", plane={"on": face(board, normal, start)},
               mid=[x + inset, y + inset, top], end=end, snap_start=True, snap_end=True)
    # The selected region follows the corner and the display chords of the arc.
    outline = [[x, y, top], start]
    for i in range(1, 16):
        angle = math.pi * i / 32
        outline.append([x + radius * (1 - math.sin(angle)), y + radius * (1 - math.cos(angle)), top])
    outline.append(end)
    outline_area = abs(sum(a[0] * b[1] - b[0] * a[1]
                           for a, b in zip(outline, outline[1:] + outline[:1]))) / 2
    ops = [
        dict(id="tangent_base", type="rect", plane={"origin": [x, y, 0], "normal": normal}, size=[600, 400]),
        dict(id="tangent_board", type="push_pull", target={"rect": "tangent_base"}, distance=top, body=board),
        arc,
        dict(id="tangent_cut", type="push_pull", distance=-top, through=True, target={
            "face": face(board, normal, [x + 5, y + 5, top]),
            "region": {"outline": outline, "holes": [], "lines": [arc["id"]], "normal": normal},
        }),
    ]

    def checked(statuses, _before, _after):
        model = ctx.S.model
        shape = model.world_shape(model.body(board))
        native_area = (600 * 400 * top - shape.Volume) / top
        expected_area = radius**2 * (1 - math.pi / 4)
        cylinders = [f for f in shape.Faces if type(f.Surface).__name__ == "Cylinder"]
        checks = [ok(statuses, 4),
                  ("cut through the exact corner region", shape.isValid() and len(shape.Solids) == 1
                   and abs(native_area - expected_area) < 1e-6, native_area),
                  ("display chords agree with the exact native region", abs(outline_area - native_area) < 5,
                   (outline_area, native_area)),
                  ("one cylindrical face of radius 50", len(cylinders) == 1
                   and abs(cylinders[0].Surface.Radius - radius) < 1e-6, cylinders)]
        for seam, outward in [(V(x + radius, y, top / 2), V(0, -1, 0)),
                              (V(x, y + radius, top / 2), V(-1, 0, 0))]:
            sides = [f for f in shape.Faces if type(f.Surface).__name__ == "Plane"
                     and f.normalAt(0, 0).dot(outward) > 1 - 1e-6 and f.isInside(seam, 1e-6, True)]
            difference = math.inf
            if cylinders and sides and cylinders[0].isInside(seam, 1e-6, True):
                cylinder = cylinders[0]
                normal_at_seam = cylinder.normalAt(*cylinder.Surface.parameter(seam))
                difference = (normal_at_seam - sides[0].normalAt(0, 0)).Length
            checks.append(("cylinder meets the side tangentially at %s" % seam, difference < 1e-6, difference))
        return checks

    ctx.step("tangent corner through-cut", ctx.FIX + ops, checked)
