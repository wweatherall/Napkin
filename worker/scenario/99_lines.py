"""T82 stage 1: saved segments, closed polygon profiles, native solids and undo/reopen."""
from session import Session
from scenario.context import face, ok, only, snap

requires = ()


def run(ctx):
    def lines(points, on=None, normal=(0, 0, 1)):
        out = []
        for i, (a, b) in enumerate(zip(points, points[1:])):
            plane = {"on": face(on, normal, a)} if on else {"origin": a, "normal": list(normal)}
            op = dict(id="line%d" % i, type="line", plane=plane, end=b)
            if i == len(points) - 2 and points[0] == points[-1]: op["outline"] = points[:-1]
            out.append(op)
        return out

    triangle = [[800, 0, 0], [900, 0, 0], [800, 60, 0], [800, 0, 0]]
    drawing = lines(triangle)
    ctx.step("lines preserve drawings without solids", ctx.FIX + drawing, lambda st, a, b: [ok(st, 3),
        ("no solid changed", a == b, ""),
        ("each line is an editable constrained sketch", len([o for o in ctx.S.doc.Objects if getattr(o, "SSLineId", "")]) == 3 and all(o.FullyConstrained for o in ctx.S.doc.Objects if getattr(o, "SSLineId", "")), ""),
        ("closed outline has exact triangular area", abs(ctx.S.model.rect_obj("line2").Shape.Area - 3000) < 1e-6, "")])
    def push(distance, body=None):
        op = dict(id="linepush", type="push_pull", target={"rect": "line2"}, distance=distance)
        if body: op["body"] = body
        return op
    solid = drawing + [push(20, "triangle")]
    ctx.step("closed lines push into a board", ctx.FIX + solid, lambda st, a, b: [ok(st, 4), only(a, b, {"triangle"}),
        ("triangular prism exact volume", abs(b["boards"].get("triangle", {}).get("vol", 0) - 60000) < 0.02, b["boards"].get("triangle"))])
    on_face = lines([[50, 150, 18], [150, 150, 18], [50, 210, 18], [50, 150, 18]], "bottom")
    for distance in (-5, 10):
        ctx.step("closed lines on face push %s" % distance, ctx.FIX + on_face + [push(distance)], lambda st, a, b, d=distance: [ok(st, 4), only(a, b, {"bottom"}),
            ("triangle alone changes volume", abs(b["boards"]["bottom"]["vol"] - a["boards"]["bottom"]["vol"] - 3000 * d) < 0.02, "")])
    vertical = lines([[18, 160, 200], [18, 200, 200], [18, 160, 240], [18, 160, 200]], "left", (1, 0, 0))
    ctx.step("closed lines on vertical mirrored face", ctx.FIX + vertical + [push(-5)], lambda st, a, b: [ok(st, 4),
        ("source and mirror both lose triangular pocket", all(abs(a["boards"][k]["vol"] - b["boards"][k]["vol"] - 4000) < 0.02 for k in ("left", "right")), "")])
    for end in ([800, 0, 0], [800, 0, 1]):
        ctx.step("invalid line endpoint rejected atomically %s" % end, ctx.FIX + [dict(id="badline", type="line", plane={"origin": [800, 0, 0], "normal": [0, 0, 1]}, end=end)], lambda st, a, b: [
            ("rejected", st[-1]["status"] == "failed", st[-1]), ("solids unchanged", a == b, ""),
            ("no rejected drawing remains", not any(getattr(o, "SSLineId", "") == "badline" for o in ctx.S.doc.Objects), "")])
    ctx.S.sync(ctx.FIX + solid)
    live = snap(ctx.S)
    ctx.S.sync(ctx.FIX + drawing)
    ctx.check("line undo push leaves loose profile", ctx.S.model.rect_obj("line2") is not None and "triangle" not in ctx.S.model.bodies())
    ctx.S.sync(ctx.FIX + solid)
    ctx.check("line redo restores solid", snap(ctx.S) == live)
    fresh = Session(None)
    try:
        fresh.sync(ctx.FIX + solid)
        ctx.check("line live equals fresh build", snap(fresh) == live)
    finally: fresh.close()
    ctx.S.save()
    path = ctx.S.path
    ctx.S.close()
    ctx.S = Session(path)
    ctx.check("line reopen preserves solid and all drawings", snap(ctx.S) == live and len([o for o in ctx.S.doc.Objects if getattr(o, "SSLineId", "")]) == 3)
    ctx.S.sync(ctx.FIX)
    ctx.check("line undo all restores fixture", snap(ctx.S) == ctx.S0)
