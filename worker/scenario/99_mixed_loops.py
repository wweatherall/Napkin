"""T109/I49/I51/I60: closed loops of mixed lines and arcs form pushable faces with exact arcs."""
import math
from common import V
from scenario.context import face, ok, only, snap
from session import Session

requires = ("99_arcs.py",)

CIRCLE_SEGMENTS = 64


def _arc_points(a, mid, b):
    """Same tessellation as viewport/presenter.gd arc_points so predictions match viewport outlines."""
    va, vm, vb = V(*a), V(*mid), V(*b)
    half = (vb - va).Length * 0.5
    along = (vb - va) * (1.0 / (2.0 * half))
    chord_mid = (va + vb) * 0.5
    sag = vm - chord_mid
    sag -= along * sag.dot(along)
    height = sag.Length
    side = sag * (1.0 / height)
    half_sweep = 2.0 * math.atan2(height, half)
    radius = (half * half + height * height) / (2.0 * height)
    count = max(2, math.ceil(CIRCLE_SEGMENTS * half_sweep / math.pi))
    pts = [list(a)]
    for i in range(1, count):
        angle = (2.0 * i / count - 1.0) * half_sweep
        rise = 2.0 * radius * math.sin((half_sweep + angle) * 0.5) * math.sin((half_sweep - angle) * 0.5)
        p = chord_mid + along * (radius * math.sin(angle)) + side * rise
        pts.append([p.x, p.y, p.z])
    pts.append(list(b))
    return pts


def _circle_edges(shape, radius):
    return [e for e in shape.Edges
            if e.Curve.__class__.__name__ == "Circle" and abs(e.Curve.Radius - radius) < 1e-6]


def _cyl_faces(shape, radius):
    return [f for f in shape.Faces
            if type(f.Surface).__name__ == "Cylinder" and abs(f.Surface.Radius - radius) < 1e-6]


def run(ctx):
    # 1. Ground loop of 3 lines + 1 arc (arch/tombstone): 100x80 base + semicircle r=50
    arch_arc_pts = _arc_points([800, 80, 0], [850, 130, 0], [900, 80, 0])
    arch_outline = [[800, 0, 0], [900, 0, 0], [900, 80, 0]] + list(reversed(arch_arc_pts))[1:-1] + [[800, 80, 0]]
    arch_lines = [
        dict(id="arch_bot", type="line", plane={"origin": [800, 0, 0], "normal": [0, 0, 1]}, end=[900, 0, 0]),
        dict(id="arch_right", type="line", plane={"origin": [900, 0, 0], "normal": [0, 0, 1]}, end=[900, 80, 0]),
        dict(id="arch_left", type="line", plane={"origin": [800, 0, 0], "normal": [0, 0, 1]}, end=[800, 80, 0]),
        dict(id="arch_top", type="arc", plane={"origin": [800, 80, 0], "normal": [0, 0, 1]},
             mid=[850, 130, 0], end=[900, 80, 0]),
    ]
    arch_spec = dict(outline=arch_outline, holes=[], normal=[0, 0, 1],
                     lines=[o["id"] for o in arch_lines])
    arch_push = dict(id="arch_push", type="new_board", target={"region": arch_spec}, distance=20, body="arch_board")
    arch_area = 8000.0 + 0.5 * math.pi * 2500.0
    arch_story = ctx.FIX + arch_lines + [arch_push]

    def check_arch(st, a, b):
        shape = ctx.S.model.world_shape(ctx.S.model.body("arch_board"))
        return [
            ok(st, 5), only(a, b, {"arch_board"}),
            ("arch has exact Part.Circle edges at r=50", len(_circle_edges(shape, 50.0)) >= 2, len(_circle_edges(shape, 50.0))),
            ("arch has cylindrical wall at r=50", len(_cyl_faces(shape, 50.0)) >= 1, ""),
            ("arch volume matches exact area * 20", abs(shape.Volume - arch_area * 20.0) < 0.02, shape.Volume),
        ]

    ctx.step("ground 3-line + 1-arc tombstone keeps exact arc", arch_story, check_arch)

    # Undo/redo, fresh build, and save + reopen for the ground arch
    ctx.S.sync(arch_story)
    live = snap(ctx.S)
    ctx.S.sync(arch_story[:-1])
    ctx.check("arch undo removes board and keeps drawings",
              "arch_board" not in ctx.S.model.bodies()
              and any(getattr(o, "SSLineId", "") == "arch_top" for o in ctx.S.doc.Objects))
    ctx.S.sync(arch_story)
    ctx.check("arch redo restores exact state", snap(ctx.S) == live)
    fresh = Session(None)
    try:
        fresh.sync(arch_story)
        ctx.check("arch story equals fresh build", snap(fresh) == live)
    finally:
        fresh.close()
    ctx.S.save()
    path = ctx.S.path
    ctx.S.close()
    ctx.S = Session(path)
    ctx.check("arch story reopens with exact curved solid",
              snap(ctx.S) == live and len(_circle_edges(ctx.S.model.world_shape(ctx.S.model.body("arch_board")), 50.0)) >= 2)
    ctx.S.sync(ctx.FIX)

    # 2. Ground loop of 2 arcs (lens): chord 100, sagitta 20 on both sides (r=72.5)
    top_pts = _arc_points([800, 0, 0], [850, 20, 0], [900, 0, 0])
    bot_pts = _arc_points([800, 0, 0], [850, -20, 0], [900, 0, 0])
    lens_outline = bot_pts[:-1] + list(reversed(top_pts))[:-1]
    lens_ops = [
        dict(id="lens_top", type="arc", plane={"origin": [800, 0, 0], "normal": [0, 0, 1]},
             mid=[850, 20, 0], end=[900, 0, 0]),
        dict(id="lens_bot", type="arc", plane={"origin": [800, 0, 0], "normal": [0, 0, 1]},
             mid=[850, -20, 0], end=[900, 0, 0]),
        dict(id="lens_push", type="new_board",
             target={"region": dict(outline=lens_outline, holes=[], normal=[0, 0, 1], lines=["lens_top", "lens_bot"])},
             distance=15, body="lens_board"),
    ]
    r_lens = 72.5
    sweep_lens = 4.0 * math.atan2(20.0, 50.0)
    lens_area = r_lens * r_lens * (sweep_lens - math.sin(sweep_lens))

    def check_lens(st, a, b):
        shape = ctx.S.model.world_shape(ctx.S.model.body("lens_board"))
        return [
            ok(st, 3), only(a, b, {"lens_board"}),
            ("lens has exact Part.Circle edges on both sides", len(_circle_edges(shape, r_lens)) >= 4, len(_circle_edges(shape, r_lens))),
            ("lens has two cylindrical walls at r=72.5", len(_cyl_faces(shape, r_lens)) >= 2, len(_cyl_faces(shape, r_lens))),
            ("lens volume matches exact area * 15", abs(shape.Volume - lens_area * 15.0) < 0.02, shape.Volume),
        ]

    ctx.step("ground 2-arc lens keeps exact arcs on both sides", ctx.FIX + lens_ops, check_lens)

    # 3. On-face loop of lines + arc pushed up (boss) and down (pocket and through-hole)
    stock_ops = [
        dict(id="ml_base", type="rect", plane={"origin": [800, 0, 0], "normal": [0, 0, 1]}, size=[100, 100]),
        dict(id="ml_stock", type="new_board", target={"rect": "ml_base"}, distance=20, body="ml_stock"),
    ]
    face_arc_pts = _arc_points([820, 50, 20], [850, 80, 20], [880, 50, 20])
    face_outline = [[820, 20, 20], [880, 20, 20], [880, 50, 20]] + list(reversed(face_arc_pts))[1:-1] + [[820, 50, 20]]
    face_drawings = [
        dict(id="fl_bot", type="line", plane={"on": face("ml_stock", (0, 0, 1), (820, 20, 20))}, end=[880, 20, 20]),
        dict(id="fl_right", type="line", plane={"on": face("ml_stock", (0, 0, 1), (880, 20, 20))}, end=[880, 50, 20]),
        dict(id="fl_left", type="line", plane={"on": face("ml_stock", (0, 0, 1), (820, 20, 20))}, end=[820, 50, 20]),
        dict(id="fl_arc", type="arc", plane={"on": face("ml_stock", (0, 0, 1), (820, 50, 20))},
             mid=[850, 80, 20], end=[880, 50, 20]),
    ]
    face_area = 1800.0 + 0.5 * math.pi * 900.0
    face_target = dict(
        face=face("ml_stock", (0, 0, 1), (850, 40, 20)),
        region=dict(outline=face_outline, holes=[], normal=[0, 0, 1], lines=[o["id"] for o in face_drawings]),
    )
    for label, dist in [("boss +10", 10), ("pocket -10", -10), ("through-hole -20", -20)]:
        push = dict(id="fl_push", type="push_pull", target=face_target, distance=dist)

        def check_face_loop(st, _a, _b, d=dist):
            shape = ctx.S.model.world_shape(ctx.S.model.body("ml_stock"))
            expected_vol = 200000.0 + face_area * d
            return [
                ok(st, 7),
                ("on-face loop has exact cylindrical wall at r=30", len(_cyl_faces(shape, 30.0)) >= 1, ""),
                ("on-face loop volume matches exact", abs(shape.Volume - expected_vol) < 0.02, shape.Volume),
            ]

        ctx.step("on-face mixed loop " + label, ctx.FIX + stock_ops + face_drawings + [push], check_face_loop)

    # 4. Ground loop with an inner mixed-loop hole (outer 120x120 square, inner D-shape r=30)
    outer_pts = [[800, 0, 0], [920, 0, 0], [920, 120, 0], [800, 120, 0]]
    hole_arc_pts = _arc_points([840, 30, 0], [870, 60, 0], [840, 90, 0])
    hole_outline = hole_arc_pts[:-1] + [[840, 90, 0]]
    holed_drawings = [
        dict(id="ho_1", type="line", plane={"origin": [800, 0, 0], "normal": [0, 0, 1]}, end=[920, 0, 0]),
        dict(id="ho_2", type="line", plane={"origin": [920, 0, 0], "normal": [0, 0, 1]}, end=[920, 120, 0]),
        dict(id="ho_3", type="line", plane={"origin": [920, 120, 0], "normal": [0, 0, 1]}, end=[800, 120, 0]),
        dict(id="ho_4", type="line", plane={"origin": [800, 120, 0], "normal": [0, 0, 1]}, end=[800, 0, 0]),
        dict(id="hi_line", type="line", plane={"origin": [840, 30, 0], "normal": [0, 0, 1]}, end=[840, 90, 0]),
        dict(id="hi_arc", type="arc", plane={"origin": [840, 30, 0], "normal": [0, 0, 1]},
             mid=[870, 60, 0], end=[840, 90, 0]),
    ]
    holed_push = dict(
        id="holed_push", type="new_board",
        target={"region": dict(outline=outer_pts, holes=[hole_outline], normal=[0, 0, 1],
                               lines=[o["id"] for o in holed_drawings])},
        distance=20, body="holed_board",
    )
    holed_area = 14400.0 - 0.5 * math.pi * 900.0

    def check_holed(st, a, b):
        shape = ctx.S.model.world_shape(ctx.S.model.body("holed_board"))
        top = [f for f in shape.Faces if f.normalAt(0, 0).z > 0.999]
        return [
            ok(st, 7), only(a, b, {"holed_board"}),
            ("holed board is valid with an inner hole wire", shape.isValid() and len(top) == 1 and len(top[0].Wires) == 2, len(top[0].Wires) if top else 0),
            ("holed board keeps exact Part.Circle edges at r=30", len(_circle_edges(shape, 30.0)) >= 2, len(_circle_edges(shape, 30.0))),
            ("holed board volume matches exact", abs(shape.Volume - holed_area * 20.0) < 0.02, shape.Volume),
        ]

    ctx.step("ground loop with inner mixed-loop hole", ctx.FIX + holed_drawings + [holed_push], check_holed)

    # 5. Concave U-shaped ground loop with semicircular notch (r=20)
    notch_pts = _arc_points([830, 80, 0], [850, 60, 0], [870, 80, 0])
    u_outline = [[800, 0, 0], [900, 0, 0], [900, 80, 0], [870, 80, 0]] + list(reversed(notch_pts))[1:-1] + [[830, 80, 0], [800, 80, 0]]
    u_drawings = [
        dict(id="u_bot", type="line", plane={"origin": [800, 0, 0], "normal": [0, 0, 1]}, end=[900, 0, 0]),
        dict(id="u_right", type="line", plane={"origin": [900, 0, 0], "normal": [0, 0, 1]}, end=[900, 80, 0]),
        dict(id="u_top_r", type="line", plane={"origin": [900, 80, 0], "normal": [0, 0, 1]}, end=[870, 80, 0]),
        dict(id="u_notch", type="arc", plane={"origin": [830, 80, 0], "normal": [0, 0, 1]},
             mid=[850, 60, 0], end=[870, 80, 0]),
        dict(id="u_top_l", type="line", plane={"origin": [830, 80, 0], "normal": [0, 0, 1]}, end=[800, 80, 0]),
        dict(id="u_left", type="line", plane={"origin": [800, 80, 0], "normal": [0, 0, 1]}, end=[800, 0, 0]),
    ]
    u_push = dict(
        id="u_push", type="new_board",
        target={"region": dict(outline=u_outline, holes=[], normal=[0, 0, 1],
                               lines=[o["id"] for o in u_drawings])},
        distance=15, body="u_board",
    )
    u_area = 8000.0 - 0.5 * math.pi * 400.0

    def check_u(st, a, b):
        shape = ctx.S.model.world_shape(ctx.S.model.body("u_board"))
        return [
            ok(st, 7), only(a, b, {"u_board"}),
            ("concave U-shape has exact cylindrical notch at r=20", len(_cyl_faces(shape, 20.0)) >= 1, ""),
            ("concave U-shape volume matches exact", abs(shape.Volume - u_area * 15.0) < 0.02, shape.Volume),
        ]

    ctx.step("concave U-shaped ground loop with arc notch", ctx.FIX + u_drawings + [u_push], check_u)

    # 6. Rejections: unclosed ground loop and missing line id
    unclosed_spec = dict(outline=arch_outline, holes=[], normal=[0, 0, 1],
                         lines=["arch_right", "arch_left", "arch_top"])
    ctx.step("ground loop rejects unclosed drawings",
             ctx.FIX + arch_lines[1:] + [dict(id="bad_open", type="new_board", target={"region": unclosed_spec}, distance=20, body="bad_open")],
             lambda st, _a, _b: [("unclosed loop rejected", st[-1]["status"] == "failed", st[-1])])

    missing_spec = dict(outline=arch_outline, holes=[], normal=[0, 0, 1],
                        lines=[o["id"] for o in arch_lines] + ["no_such_line"])
    ctx.step("ground loop rejects missing line id",
             ctx.FIX + arch_lines + [dict(id="bad_miss", type="new_board", target={"region": missing_spec}, distance=20, body="bad_miss")],
             lambda st, _a, _b: [("missing line rejected", st[-1]["status"] == "failed", st[-1])])
