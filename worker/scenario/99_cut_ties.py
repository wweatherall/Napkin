"""T59 step 1: a cut made up to a pocket's floor stays tied to it (I26b, I24)."""
from session import Session
from scenario.context import face, ok, on_rect, only, snap

requires = ()


def _cutter(doc, oid):
    return next((o for o in doc.Objects if getattr(o, "SSOp", "") == oid and o.TypeId == "Part::Extrusion"), None)


def _length_expr(ext):
    return next((expr for path, expr in getattr(ext, "ExpressionEngine", []) if path.lstrip(".") == "LengthFwd"), "")


def _prop_depth(oid, ext_name, value):
    return {"id": oid, "type": "property_edit", "body": "bottom", "object": ext_name,
            "property": "LengthFwd", "value": value, "mode": "value"}


def run(ctx):
    V0 = (564 * 400 - 1600) * 18
    AREA_AB = 100 * 60 + 100 * 40 - 40 * 40        # 8400 mm^2
    AREA_ABC = AREA_AB + 80 * 40 - 40 * 30         # 10400 mm^2

    PA = [on_rect("r_tie_a", "bottom", [0, 0, 1], [60, 60, 18], [100, 60]),
          {"id": "p_tie_a", "type": "push_pull", "target": {"rect": "r_tie_a"}, "distance": -6}]
    PB = [{"id": "r_tie_b", "type": "rect", "plane": {"on": face("bottom", [0, 0, 1], [200, 100, 18])},
           "corner": [-80, -20], "size": [100, 40]},
          {"id": "p_tie_b", "type": "push_pull", "target": {"rect": "r_tie_b"}, "distance": -6,
           "to_face": {"normal": [0, 0, 1], "point": [140, 100, 12]}}]
    PC = [{"id": "r_tie_c", "type": "rect", "plane": {"on": face("bottom", [0, 0, 1], [240, 110, 18])},
           "corner": [-60, -20], "size": [80, 40]},
          {"id": "p_tie_c", "type": "push_pull", "target": {"rect": "r_tie_c"}, "distance": -6,
           "to_face": {"normal": [0, 0, 1], "point": [200, 105, 12]}}]

    # 1. Pocket B tied to Pocket A's floor
    def check_ab(st, a, b):
        ext_b = _cutter(ctx.S.doc, "p_tie_b")
        return [
            ok(st, 4), only(a, b, {"bottom"}),
            ("B has LengthFwd expression", bool(ext_b and _length_expr(ext_b)), getattr(ext_b, "ExpressionEngine", None)),
            ("B SSTiedTo equals A's op id", ext_b is not None and getattr(ext_b, "SSTiedTo", "") == "p_tie_a",
             getattr(ext_b, "SSTiedTo", None)),
            ("volume equals two plain 6 mm pockets", abs(b["boards"]["bottom"]["vol"] - (V0 - AREA_AB * 6)) < 0.1,
             b["boards"]["bottom"]["vol"]),
        ]

    ctx.step("cut B tied to pocket A's floor", ctx.FIX + PA + PB, check_ab)

    # 2. A made 10 deep -> B follows; detach by pushing B's floor; undo brings tie back; A=10 takes B again
    ops_ab = ctx.FIX + PA + PB
    ctx.S.sync(ops_ab)
    ext_a = _cutter(ctx.S.doc, "p_tie_a")
    ext_b = _cutter(ctx.S.doc, "p_tie_b")
    a_name = ext_a.Name
    deep_a = _prop_depth("e_tie_a10", a_name, "10mm")
    ctx.S.sync(ops_ab + [deep_a])
    vol_10 = snap(ctx.S)["boards"]["bottom"]["vol"]
    ctx.check("cut tie follow: property_edit accepted", ctx.S.status()[-1]["status"] == "ok", ctx.S.status()[-1])
    ctx.check("cut tie follow: B LengthFwd becomes 10", abs(ext_b.LengthFwd.Value - 10.0) < 1e-4, ext_b.LengthFwd.Value)
    ctx.check("cut tie follow: volume reflects both pockets at 10 mm",
              abs(vol_10 - (V0 - AREA_AB * 10)) < 0.1, (vol_10, V0 - AREA_AB * 10))

    # Back to 6 mm pockets, then push B's floor by -2 to detach
    ctx.S.sync(ops_ab)
    push_floor = {"id": "p_tie_detach", "type": "push_pull",
                  "target": {"face": face("bottom", [0, 0, 1], [200, 100, 12])}, "distance": -2}
    ctx.S.sync(ops_ab + [push_floor])
    vol_det = snap(ctx.S)["boards"]["bottom"]["vol"]
    ctx.check("cut tie detach: push floor accepted", ctx.S.status()[-1]["status"] == "ok", ctx.S.status()[-1])
    ctx.check("cut tie detach: B has no LengthFwd expression", not _length_expr(ext_b), ext_b.ExpressionEngine)
    ctx.check("cut tie detach: B SSTiedTo is empty", getattr(ext_b, "SSTiedTo", None) == "", getattr(ext_b, "SSTiedTo", None))
    ctx.check("cut tie detach: B keeps LengthFwd 6", abs(ext_b.LengthFwd.Value - 6.0) < 1e-4, ext_b.LengthFwd.Value)
    ctx.check("cut tie detach: refined floor is 2 mm deeper",
              abs(vol_det - (V0 - AREA_AB * 8)) < 0.1, (vol_det, V0 - AREA_AB * 8))

    # Undo the detach: tie returns, and A=10 takes B with it again
    how, _ = ctx.S.sync(ops_ab)
    ctx.check("cut tie detach undo: undone by FreeCAD undo", how.startswith("undid"), how)
    ctx.check("cut tie detach undo: B LengthFwd expression restored", bool(_length_expr(ext_b)), ext_b.ExpressionEngine)
    ctx.check("cut tie detach undo: B SSTiedTo restored", getattr(ext_b, "SSTiedTo", "") == "p_tie_a",
              getattr(ext_b, "SSTiedTo", None))
    ctx.S.sync(ops_ab + [deep_a])
    vol_10_again = snap(ctx.S)["boards"]["bottom"]["vol"]
    ctx.check("cut tie detach undo: A=10 takes B again",
              abs(ext_b.LengthFwd.Value - 10.0) < 1e-4 and abs(vol_10_again - (V0 - AREA_AB * 10)) < 0.1,
              (ext_b.LengthFwd.Value, vol_10_again))

    # 3. Chain: C tied to B's floor -> A=10 takes B and C
    ops_abc = ops_ab + PC
    ctx.S.sync(ops_abc)
    ext_c = _cutter(ctx.S.doc, "p_tie_c")
    ctx.check("cut tie chain: C SSTiedTo equals B's op id", ext_c is not None and getattr(ext_c, "SSTiedTo", "") == "p_tie_b",
              getattr(ext_c, "SSTiedTo", None))
    ctx.S.sync(ops_abc + [deep_a])
    vol_abc_10 = snap(ctx.S)["boards"]["bottom"]["vol"]
    ctx.check("cut tie chain: A=10 takes B and C",
              abs(ext_b.LengthFwd.Value - 10.0) < 1e-4 and abs(ext_c.LengthFwd.Value - 10.0) < 1e-4
              and abs(vol_abc_10 - (V0 - AREA_ABC * 10)) < 0.1,
              (ext_b.LengthFwd.Value, ext_c.LengthFwd.Value, vol_abc_10))

    # Save and reopen: ties persist and A=10 still takes B and C
    ctx.S.sync(ops_abc)
    ctx.S.save()
    path = ctx.S.path
    ctx.S.close()
    ctx.S = Session(path)
    re_a = _cutter(ctx.S.doc, "p_tie_a")
    re_b = _cutter(ctx.S.doc, "p_tie_b")
    re_c = _cutter(ctx.S.doc, "p_tie_c")
    ctx.check("cut tie reopen: B expression and SSTiedTo survive",
              re_b is not None and bool(_length_expr(re_b)) and getattr(re_b, "SSTiedTo", "") == "p_tie_a",
              (getattr(re_b, "ExpressionEngine", None), getattr(re_b, "SSTiedTo", None)))
    ctx.check("cut tie reopen: C expression and SSTiedTo survive",
              re_c is not None and bool(_length_expr(re_c)) and getattr(re_c, "SSTiedTo", "") == "p_tie_b",
              (getattr(re_c, "ExpressionEngine", None), getattr(re_c, "SSTiedTo", None)))
    ctx.S.sync(ops_abc + [_prop_depth("e_tie_a10_re", re_a.Name, "10mm")])
    vol_re_10 = snap(ctx.S)["boards"]["bottom"]["vol"]
    ctx.check("cut tie reopen: A=10 still takes B and C",
              abs(re_b.LengthFwd.Value - 10.0) < 1e-4 and abs(re_c.LengthFwd.Value - 10.0) < 1e-4
              and abs(vol_re_10 - (V0 - AREA_ABC * 10)) < 0.1,
              (re_b.LengthFwd.Value, re_c.LengthFwd.Value, vol_re_10))

    ctx.S.sync(ctx.FIX)
    ctx.check("cut tie story: undo back to fixture", snap(ctx.S) == ctx.S0)

    # 4. to_face on a point with no pocket floor -> plain untied 6 mm cut, no error
    open_cut = [on_rect("r_tie_open", "bottom", [0, 0, 1], [380, 280, 18], [40, 40]),
                {"id": "p_tie_open", "type": "push_pull", "target": {"rect": "r_tie_open"}, "distance": -6,
                 "to_face": {"normal": [0, 0, 1], "point": [400, 300, 12]}}]

    def check_open(st, a, b):
        ext = _cutter(ctx.S.doc, "p_tie_open")
        return [
            ok(st, 2), only(a, b, {"bottom"}),
            ("plain untied cut", ext is not None and not _length_expr(ext) and getattr(ext, "SSTiedTo", None) == "",
             (getattr(ext, "ExpressionEngine", None), getattr(ext, "SSTiedTo", None))),
            ("depth is 6 mm", ext is not None and abs(ext.LengthFwd.Value - 6.0) < 1e-4
             and abs(b["boards"]["bottom"]["vol"] - (V0 - 40 * 40 * 6)) < 0.1,
             (getattr(ext, "LengthFwd", None), b["boards"]["bottom"]["vol"])),
        ]

    ctx.step("to_face on open point makes plain untied cut", ctx.FIX + open_cut, check_open)

    # 5. Rejections: positive distance and through=True
    bad_pos = [on_rect("r_tie_bad1", "bottom", [0, 0, 1], [380, 280, 18], [40, 40]),
               {"id": "p_tie_bad1", "type": "push_pull", "target": {"rect": "r_tie_bad1"}, "distance": 6,
                "to_face": {"normal": [0, 0, 1], "point": [400, 300, 12]}}]
    ctx.step("reject to_face with positive distance", ctx.FIX + bad_pos, lambda st, a, b: [
        ("rejected with exact message",
         st[-1]["status"] == "failed" and st[-1].get("message") == "to_face is only for a cut into a board", st[-1]),
        ("fixture unchanged", a == b, ""),
    ])

    bad_thr = [on_rect("r_tie_bad2", "bottom", [0, 0, 1], [380, 280, 18], [40, 40]),
               {"id": "p_tie_bad2", "type": "push_pull", "target": {"rect": "r_tie_bad2"}, "distance": -18,
                "through": True, "to_face": {"normal": [0, 0, 1], "point": [400, 300, 12]}}]
    ctx.step("reject to_face with through", ctx.FIX + bad_thr, lambda st, a, b: [
        ("rejected with exact message",
         st[-1]["status"] == "failed" and st[-1].get("message") == "to_face is only for a cut into a board", st[-1]),
        ("fixture unchanged", a == b, ""),
    ])
