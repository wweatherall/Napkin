"""T59 step 1 unit tests: pocket-floor ties edge cases beyond the scenario fixture.

Covers: distance-ignored expression driving depth, different start planes (bosses and opposite/positive cut
directions), linked instances and mirrored boards, arrayed pocket cutters (Draft OrthoArray), SSThrough and
LengthRev exclusions, Group-order tie-breaking, circular pockets, all to_face rejections, shallower edits,
push-up detach, and region pushes leaving ties intact.

  freecadcmd worker/test_cut_ties.py        (TESTDIR=<folder> for its files)"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_load  # Configure the FreeCAD test runtime before loading worker modules.
from session import Session

R = [0, 0]


def check(name, cond, detail=""):
    R[0 if cond else 1] += 1
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"), flush=True)


def cutter(doc, oid):
    return next((o for o in doc.Objects if getattr(o, "SSOp", "") == oid and o.TypeId == "Part::Extrusion"), None)


def expr_of(ext, prop="LengthFwd"):
    return next((e for p, e in getattr(ext, "ExpressionEngine", []) if p.lstrip(".") == prop), "")


def vol(sess, bid):
    return sess.model.world_shape(sess.model.body(bid)).Volume


def g_rect(rid, origin, size, normal=(0, 0, 1)):
    return {"id": rid, "type": "rect", "plane": {"normal": list(normal), "origin": list(origin)}, "size": list(size)}


def f_rect(rid, body, point, size, normal=(0, 0, 1), corner=None):
    op = {"id": rid, "type": "rect",
          "plane": {"on": {"body": body, "normal": list(normal), "point": list(point)}}, "size": list(size)}
    if corner is not None:
        op["corner"] = list(corner)
    return op


def push(oid, rid, dist, **extra):
    op_type = "new_board" if "body" in extra else "push_pull"
    op = {"id": oid, "type": op_type, "target": {"rect": rid}, "distance": dist}
    op.update(extra)
    return op


def prop_len(oid, body, obj_name, val):
    return {"id": oid, "type": "property_edit", "body": body, "object": obj_name,
            "property": "LengthFwd", "value": val, "mode": "value"}


tmp = os.environ.get("TESTDIR", "/tmp/cut_ties_test")
os.makedirs(tmp, exist_ok=True)

# 1. Expression drives depth regardless of op distance, different start levels (boss), shallower + deeper, push-up detach
s = Session(None)
ops = [
    g_rect("r0", [0, 0, 0], [300, 200]), push("p0", "r0", 20, body="b1"),
    # Pocket A on top (z=20), x=[20..120], y=[20..120], depth 6 -> floor at z=14
    f_rect("ra", "b1", [20, 20, 20], [100, 100]), push("pa", "ra", -6),
    # Boss on top (z=20 -> z=26) covering x=[100..200], y=[40..100] (plane point at x=160 is on solid top)
    f_rect("rboss", "b1", [160, 70, 20], [100, 60], corner=[-60, -30]), push("pboss", "rboss", 6),
    # Pocket B drawn on boss top (z=26), with prediction distance=-3 (wrong on purpose), tied to A's floor (z=14)
    f_rect("rb", "b1", [110, 50, 26], [60, 40]),
    push("pb", "rb", -3, to_face={"normal": [0, 0, 1], "point": [115, 70, 14]}),
]
s.sync(ops)
ea, eb = cutter(s.doc, "pa"), cutter(s.doc, "pb")
check("boss start plane: accepted and tied to A",
      all(e["status"] == "ok" for e in s.status()) and eb is not None and eb.SSTiedTo == "pa" and bool(expr_of(eb)),
      (s.status(), getattr(eb, "SSTiedTo", None)))
check("boss start plane: expression drives depth (12 mm, ignoring op distance -3)",
      abs(eb.LengthFwd.Value - 12.0) < 1e-4, eb.LengthFwd.Value)
# Make A deeper (10) and shallower (4)
s.sync(ops + [prop_len("ea10", "b1", ea.Name, "10mm")])
check("boss start plane: A=10 -> B=16", abs(eb.LengthFwd.Value - 16.0) < 1e-4, eb.LengthFwd.Value)
s.sync(ops + [prop_len("ea4", "b1", ea.Name, "4mm")])
check("boss start plane: A=4 (shallower) -> B=10", abs(eb.LengthFwd.Value - 10.0) < 1e-4, eb.LengthFwd.Value)
# Push B's floor UP (+2) -> detaches B keeping 12 mm; undo brings tie back
s.sync(ops)
push_up = {"id": "pup", "type": "push_pull",
           "target": {"face": {"body": "b1", "normal": [0, 0, 1], "point": [150, 70, 14]}}, "distance": 2}
s.sync(ops + [push_up])
check("push floor up detaches tie and keeps LengthFwd 12",
      s.status()[-1]["status"] == "ok" and not expr_of(eb) and eb.SSTiedTo == "" and abs(eb.LengthFwd.Value - 12.0) < 1e-4,
      (s.status()[-1], eb.ExpressionEngine, eb.SSTiedTo, eb.LengthFwd.Value))
s.sync(ops)
check("undo push floor up restores tie", bool(expr_of(eb)) and eb.SSTiedTo == "pa", (eb.ExpressionEngine, eb.SSTiedTo))
s.close()

# 2. Positive cut direction (+Z from bottom face z=0, and +X from left face x=0)
s = Session(None)
ops = [
    g_rect("r0", [0, 0, 0], [200, 200]), push("p0", "r0", 30, body="b1"),
    # Bottom face normal [0, 0, -1] (plane_from: x=+X, y=-Y), covers x=[20..100], y=[20..100], cut in +Z to z=6
    f_rect("rza", "b1", [20, 100, 0], [80, 80], normal=(0, 0, -1)), push("pza", "rza", -6),
    # Bottom boss down by 4 (to z=-4), covers x=[80..160], y=[30..90]
    f_rect("rzboss", "b1", [140, 60, 0], [80, 60], normal=(0, 0, -1), corner=[-60, -30]), push("pzboss", "rzboss", 4),
    # Cut from bottom boss (z=-4) in +Z covering x=[90..140], y=[40..80], tied to pza's floor (z=6) -> depth 10
    f_rect("rzb", "b1", [90, 80, -4], [50, 40], normal=(0, 0, -1)),
    push("pzb", "rzb", -10, to_face={"normal": [0, 0, -1], "point": [95, 60, 6]}),
    # Vertical face at x=0 (normal [-1, 0, 0]; plane_from: x=-Y, y=+Z), cut in +X to x=6
    # rxa covers y=[120..160], z=[5..25]; rxb covers y=[140..180], z=[5..25]
    f_rect("rxa", "b1", [0, 160, 5], [40, 20], normal=(-1, 0, 0)), push("pxa", "rxa", -6),
    f_rect("rxb", "b1", [0, 180, 5], [40, 20], normal=(-1, 0, 0)),
    push("pxb", "rxb", -6, to_face={"normal": [-1, 0, 0], "point": [6, 150, 15]}),
]
s.sync(ops)
eza, ezb = cutter(s.doc, "pza"), cutter(s.doc, "pzb")
exa, exb = cutter(s.doc, "pxa"), cutter(s.doc, "pxb")
check("+Z cut tie: tied and depth 10 from z=-4 boss",
      all(e["status"] == "ok" for e in s.status()) and ezb is not None and ezb.SSTiedTo == "pza" and abs(ezb.LengthFwd.Value - 10.0) < 1e-4,
      (s.status(), getattr(ezb, "SSTiedTo", None), getattr(ezb, "LengthFwd", None)))
check("+X vertical cut tie: tied and depth 6",
      exb is not None and exb.SSTiedTo == "pxa" and abs(exb.LengthFwd.Value - 6.0) < 1e-4,
      (getattr(exb, "SSTiedTo", None), getattr(exb, "LengthFwd", None)))
s.sync(ops + [prop_len("eza9", "b1", eza.Name, "9mm"), prop_len("exa11", "b1", exa.Name, "11mm")])
check("+Z and +X ties follow deeper floor edits",
      abs(ezb.LengthFwd.Value - 13.0) < 1e-4 and abs(exb.LengthFwd.Value - 11.0) < 1e-4,
      (ezb.LengthFwd.Value, exb.LengthFwd.Value))
# Wrong normal on to_face does not tie
s.sync(ops + [
    f_rect("rbadn", "b1", [20, 180, 0], [30, 30], normal=(0, 0, -1)),
    push("pbadn", "rbadn", -6, to_face={"normal": [0, 0, 1], "point": [50, 50, 6]}),
])
ebadn = cutter(s.doc, "pbadn")
check("wrong to_face normal makes plain untied cut",
      s.status()[-1]["status"] == "ok" and ebadn is not None and ebadn.SSTiedTo == "" and not expr_of(ebadn),
      (s.status()[-1], getattr(ebadn, "SSTiedTo", None)))
s.close()

# 3. Linked component instances and mirrored boards
s = Session(None)
ops = [
    g_rect("r0", [0, 0, 0], [200, 100]), push("p0", "r0", 20, body="b1"),
    {"id": "c1", "type": "make_component", "body": "b1", "name": "Panel"},
    {"id": "cp1", "type": "move", "targets": ["b1"], "vector": [0, 0, 100], "copy": True, "new_ids": ["b2"]},
    {"id": "m1", "type": "mirror", "targets": ["b1"], "plane": {"point": [250, 0, 0], "normal": [1, 0, 0]}, "new_ids": ["b3"]},
    # Pocket A on b1 at x=[20..100], y=[20..80], z=[14..20]
    f_rect("ra", "b1", [20, 20, 20], [80, 60]), push("pa", "ra", -6),
    # Pocket B drawn on translated linked copy b2 (z=120, floor at z=114), x=[70..150], y=[30..70]
    f_rect("rb", "b2", [130, 50, 120], [80, 40], corner=[-60, -20]),
    push("pb", "rb", -6, to_face={"normal": [0, 0, 1], "point": [85, 50, 114]}),
    # Pocket C drawn on mirrored copy b3 (x=[300..500], so b1 x=[20..100] -> [400..480], b2 x=[70..150] -> [350..430])
    f_rect("rc", "b3", [330, 40, 20], [50, 30]),
    push("pc", "rc", -6, to_face={"normal": [0, 0, 1], "point": [365, 55, 14]}),
]
s.sync(ops)
ea, eb, ec = cutter(s.doc, "pa"), cutter(s.doc, "pb"), cutter(s.doc, "pc")
check("linked instance and mirror: B tied to A, C tied to B",
      all(e["status"] == "ok" for e in s.status()) and eb is not None and ec is not None and eb.SSTiedTo == "pa" and ec.SSTiedTo == "pb",
      (s.status(), getattr(eb, "SSTiedTo", None), getattr(ec, "SSTiedTo", None)))
s.sync(ops + [prop_len("ea10", "b1", ea.Name, "10mm")])
check("linked instance and mirror: A=10 updates B, C, and all three boards match",
      abs(eb.LengthFwd.Value - 10.0) < 1e-4 and abs(ec.LengthFwd.Value - 10.0) < 1e-4
      and abs(vol(s, "b1") - vol(s, "b2")) < 0.1 and abs(vol(s, "b1") - vol(s, "b3")) < 0.1,
      (eb.LengthFwd.Value, ec.LengthFwd.Value, vol(s, "b1"), vol(s, "b2"), vol(s, "b3")))
# Detach C from mirrored copy b3 (x=340, y=55, z=14)
s.sync(ops)
s.sync(ops + [{"id": "det_c", "type": "push_pull",
               "target": {"face": {"body": "b3", "normal": [0, 0, 1], "point": [340, 55, 14]}}, "distance": -2}])
check("detach on mirrored copy clears C's tie",
      s.status()[-1]["status"] == "ok" and ec.SSTiedTo == "" and not expr_of(ec),
      (s.status()[-1], ec.SSTiedTo, ec.ExpressionEngine))
s.close()

# 4. Arrayed cutter (Draft OrthoArray), SSThrough exclusion, LengthRev exclusion, Group-order tie-break, circular pocket
s = Session(None)
ops = [
    g_rect("r0", [0, 0, 0], [400, 200]), push("p0", "r0", 20, body="b1"),
    # Pocket A at [20..60, 20..60], copied in X by 80 (copies at x=20..60 and x=100..140)
    f_rect("ra", "b1", [20, 20, 20], [40, 40]), push("pa", "ra", -6),
    {"id": "arr_a", "type": "move", "targets": [], "cut": {"body": "b1", "op": "pa"}, "vector": [80, 0, 0], "copy": True, "count": 1},
    # Circular pocket B overlapping the 2nd array copy at x=135, y=40, z=14
    {"id": "cb", "type": "circle", "plane": {"on": {"body": "b1", "normal": [0, 0, 1], "point": [145, 40, 20]}}, "radius": 20},
    push("pb", "cb", -6, to_face={"normal": [0, 0, 1], "point": [135, 40, 14]}),
    # Through-hole at [200..240, 20..60]
    f_rect("rthr", "b1", [200, 20, 20], [40, 40]), push("pthr", "rthr", -20, through=True),
    # Cut overlapping through-hole (x=[230..270], y=[20..60]), to_face at through-hole's far end -> must NOT tie to SSThrough
    f_rect("rnt", "b1", [260, 40, 20], [40, 40], corner=[-30, -20]),
    push("pnt", "rnt", -10, to_face={"normal": [0, 0, 1], "point": [235, 40, -1]}),
    # Overlapping pair A1 [20..80] and A2 [50..110] at y=[110..170], depth 6 -> tie to overlap picks first in Group order (pa1)
    f_rect("ra1", "b1", [20, 110, 20], [60, 60]), push("pa1", "ra1", -6),
    f_rect("ra2", "b1", [100, 140, 20], [60, 60], corner=[-50, -30]), push("pa2", "ra2", -6),
    f_rect("rovl", "b1", [115, 150, 20], [60, 40], corner=[-55, -20]),
    push("povl", "rovl", -6, to_face={"normal": [0, 0, 1], "point": [65, 140, 14]}),
]
s.sync(ops)
ea, eb, ent, eovl = cutter(s.doc, "pa"), cutter(s.doc, "pb"), cutter(s.doc, "pnt"), cutter(s.doc, "povl")
check("arrayed pocket + circular tied pocket: tied to array's Base extrusion",
      all(e["status"] == "ok" for e in s.status()) and eb is not None and eb.SSTiedTo == "pa" and bool(expr_of(eb)),
      (s.status(), getattr(eb, "SSTiedTo", None)))
s.sync(ops + [prop_len("ea9", "b1", ea.Name, "9mm")])
check("arrayed pocket: A=9 takes circular pocket B to 9", abs(eb.LengthFwd.Value - 9.0) < 1e-4, eb.LengthFwd.Value)
check("SSThrough cutter is never tied to", ent is not None and ent.SSTiedTo == "" and not expr_of(ent),
      (getattr(ent, "SSTiedTo", None), getattr(ent, "ExpressionEngine", None)))
check("overlapping cutters tie to first in Group order (pa1)", eovl is not None and eovl.SSTiedTo == "pa1",
      getattr(eovl, "SSTiedTo", None))

# LengthRev expression exclusion: set a LengthRev expression on pa1 and check a new cut ignores pa1 and picks pa2
s.sync(ops)
ea1 = cutter(s.doc, "pa1")
s.sync(ops + [
    {"id": "lrev", "type": "property_edit", "body": "b1", "object": ea1.Name,
     "property": "LengthRev", "value": "1mm", "mode": "expression"},
    f_rect("rovl2", "b1", [130, 140, 20], [80, 20], corner=[-70, -10]),
    push("povl2", "rovl2", -6, to_face={"normal": [0, 0, 1], "point": [65, 140, 14]}),
])
eovl2 = cutter(s.doc, "povl2")
check("cutter with LengthRev expression is skipped (ties to pa2 instead of pa1)",
      eovl2 is not None and eovl2.SSTiedTo == "pa2", (s.status()[-2:], getattr(eovl2, "SSTiedTo", None)))
s.close()

# 5. All invalid to_face placements reject with exact message
MSG = "to_face is only for a cut into a board"
s = Session(None)
base_ops = [
    g_rect("r0", [0, 0, 0], [200, 100]), push("p0", "r0", 20, body="b1"),
    g_rect("r_other", [300, 0, 0], [100, 100]), push("p_other", "r_other", 20, body="b2"),
]
s.sync(base_ops)
tf = {"normal": [0, 0, 1], "point": [50, 50, 14]}
bad_cases = [
    ("positive distance", [f_rect("rp", "b1", [10, 10, 20], [40, 40]), push("pp", "rp", 10, to_face=tf)]),
    ("with through=True", [f_rect("rt", "b1", [10, 10, 20], [40, 40]), push("pt", "rt", -20, through=True, to_face=tf)]),
    ("with resize_stock", [{"id": "prs", "type": "push_pull",
                            "target": {"face": {"body": "b1", "normal": [1, 0, 0], "point": [200, 50, 10]}},
                            "distance": -10, "resize_stock": True, "to_face": tf}]),
]
for label, extra in bad_cases:
    s.sync(base_ops + extra)
    last = s.status()[-1]
    check(f"reject to_face ({label})", last["status"] == "failed" and last.get("message") == MSG, last)
    s.sync(base_ops)
s.close()

# 6. Region push on a tied floor does NOT detach the outer pocket's tie
s = Session(None)
ops = [
    g_rect("r0", [0, 0, 0], [300, 200]), push("p0", "r0", 20, body="b1"),
    f_rect("ra", "b1", [20, 20, 20], [100, 100]), push("pa", "ra", -6),
    f_rect("rb", "b1", [160, 70, 20], [120, 60], corner=[-80, -30]),
    push("pb", "rb", -6, to_face={"normal": [0, 0, 1], "point": [100, 70, 14]}),
    {"id": "l1", "type": "line", "plane": {"on": {"body": "b1", "normal": [0, 0, 1], "point": [160, 40, 14]}},
     "end": [160, 100, 14]},
    {"id": "preg", "type": "push_pull",
     "target": {"face": {"body": "b1", "normal": [0, 0, 1], "point": [180, 70, 14]},
                "region": {"outline": [[160, 40, 14], [200, 40, 14], [200, 100, 14], [160, 100, 14]],
                           "holes": [], "normal": [0, 0, 1], "lines": ["l1"]}},
     "distance": -2},
]
s.sync(ops)
eb = cutter(s.doc, "pb")
check("region push on tied floor keeps B tied",
      all(e["status"] == "ok" for e in s.status()) and eb is not None and eb.SSTiedTo == "pa" and bool(expr_of(eb)),
      (s.status()[-2:], getattr(eb, "SSTiedTo", None), getattr(eb, "ExpressionEngine", None)))
s.close()

print(f"\nCUT TIES TESTS: {R[0]} passed, {R[1]} failed", flush=True)
sys.exit(1 if R[1] else 0)
