"""Stage-1 checks for the live-document worker.

  freecadcmd worker/test_native.py        (with QT_QPA_PLATFORM=offscreen)
  env ORACLE=dir  -> compare against bodies.json written by the v0.1 replay worker for the same ops

Covers: native feature tree, op-by-op == fresh, random undo / amend walks == fresh,
autosave + reopen + undo past the session start, an edit made in FreeCAD showing up on reopen."""
import json
import os
import random
import sys

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "replay.py")).read().replace("\nmain()\n", "\n")
exec(compile(src, "replay.py", "exec"))

R = [0, 0]


def check(name, cond, detail=""):
    R[0 if cond else 1] += 1
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"), flush=True)


def ground_rect(rid, origin, size):
    return {"id": rid, "type": "rect", "plane": {"normal": [0, 0, 1], "origin": origin}, "size": size}


def face_rect(rid, body, point, size, normal=(0, 0, 1)):
    return {"id": rid, "type": "rect", "plane": {"on": {"body": body, "normal": list(normal), "point": point}}, "size": size}


def push(oid, rid, d, body=None):
    op = {"id": oid, "type": "push_pull", "target": {"rect": rid}, "distance": d}
    if body:
        op["body"] = body
    return op


OPS = [
    ground_rect("r1", [0, 0, 0], [100, 50]), push("p1", "r1", 20, "b1"),
    {"id": "c1", "type": "make_component", "body": "b1", "name": "Shelf"},
    {"id": "mv1", "type": "move", "targets": ["b1"], "vector": [0, 200, 0], "copy": True, "new_ids": ["b2"]},
    face_rect("r2", "b2", [10, 210, 20], [20, 20]), push("p2", "r2", -5),            # notch drawn on an instance
    {"id": "m1", "type": "mirror", "targets": ["b1"], "plane": {"point": [150, 0, 0], "normal": [1, 0, 0]},
     "new_ids": ["b3"]},
    face_rect("r3", "b3", [220, 10, 20], [10, 10]), push("p3", "r3", 15),             # bump drawn on a mirrored copy
    {"id": "m2", "type": "mirror", "targets": ["b2"], "plane": {"point": [0, 225, 0], "normal": [0, 1, 0]},
     "replace": True},
    {"id": "mv2", "type": "move", "targets": ["b2"], "vector": [0, 100, 0]},            # move a flipped board
    {"id": "mat1", "type": "set_material", "targets": ["b3"], "material": "white oak"},
    ground_rect("r4", [0, 500, 0], [50, 50]), push("p4", "r4", 30, "b4"),
    {"id": "mv3", "type": "move", "targets": ["b4"], "vector": [100, 0, 0], "copy": True, "count": 3,
     "new_ids": ["b5", "b6", "b7"]},
    face_rect("r5", "b4", [10, 510, 30], [10, 10]), push("p5", "r5", -10),            # cut a plain board
    face_rect("r6", "b4", [10, 510, 30], [5, 5]), push("p6", "r6", -3),               # misses: inside the notch
    face_rect("r7", "b5", [110, 540, 30], [30, 30]), push("p7", "r7", 12),            # partly overhanging merge
]


def bodies_of(sess):
    m = sess.model
    out = {}
    for bid, obj in m.bodies().items():
        ws = m.world_shape(obj)
        bb = ws.BoundBox
        out[bid] = (round(ws.Volume, 2), tuple(round(v, 4) for v in (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)),
                    material_of(m, obj), component_of(m, obj))
    return out


def statuses(sess):
    return [(e["id"], e["status"]) for e in sess.status()]


def fresh(ops):
    s = Session(None)
    s.sync(ops)
    b, st = bodies_of(s), statuses(s)
    s.close()
    return b, st


def diff(a, b):
    keys = sorted(set(a) | set(b))
    return [(k, a.get(k), b.get(k)) for k in keys if a.get(k) != b.get(k)][:3]


tmp = os.environ.get("TESTDIR", "/tmp/native_test")
os.makedirs(tmp, exist_ok=True)
model_path = os.path.join(tmp, "model.FCStd")
for p in (model_path, journal_path(model_path)):
    if os.path.exists(p):
        os.remove(p)

# ---------- A. the whole log, fresh ----------
s = Session(model_path, fresh=True)
s.sync(OPS)
ref_bodies, ref_status = bodies_of(s), statuses(s)
st = dict(ref_status)
check("all ops ok except the miss", [k for k, v in ref_status if v != "ok"] == ["p6"], ref_status)
b = ref_bodies
check("notch on instance + bump on mirrored copy land on the shared definition",
      b["b1"][0] == b["b2"][0] == b["b3"][0] == 100000 - 2000 + 1500, (b["b1"][0], b["b2"][0], b["b3"][0]))
check("mirrored copy sits across the plane", b["b3"][1][0] == 200 and b["b3"][1][3] == 300, b["b3"][1])
check("flipped board moved", b["b2"][1][1] == 300 and b["b2"][1][4] == 350, b["b2"][1])
check("material set through a mirror reaches the component", b["b1"][2] == b["b2"][2] == "white oak", b)
check("copies of a plain board are independent of later cuts",
      b["b4"][0] == 75000 - 1000 and b["b6"][0] == 75000, (b["b4"][0], b["b6"][0]))
check("overhanging merge adds the whole rectangle", round(b["b5"][0]) == 75000 + 30 * 30 * 12, b["b5"][0])
types = {o.TypeId for o in s.doc.Objects}
check("native feature tree", {"App::Part", "Part::Plane", "Part::Extrusion", "Part::MultiFuse", "Part::Cut", "Part::Compound",
                              "App::Link", "Part::Mirroring", "Part::Feature"} <= types, types)
check("one FreeCAD undo step per ok op", s.doc.UndoCount == sum(1 for _, v in ref_status if v == "ok"),
      (s.doc.UndoCount, len(ref_status)))

if os.environ.get("ORACLE"):
    old = {x["id"]: x for x in json.load(open(os.path.join(os.environ["ORACLE"], "bodies.json")))}
    bad = [k for k in old if k not in b or abs(old[k]["volume_mm3"] - b[k][0]) > 0.1
           or any(abs(x - y) > 1e-3 for x, y in zip(old[k]["world_bbox"], b[k][1]))
           or old[k]["component"] != b[k][3] or (old[k]["material"] or "") != b[k][2]]
    check("matches the v0.1 replay worker on every board", not bad and sorted(old) == sorted(b), bad)
s.close()

# ---------- B. op by op == fresh ----------
s = Session(None)
for k in range(1, len(OPS) + 1):
    s.sync(OPS[:k])
check("op by op == all at once", bodies_of(s) == ref_bodies and statuses(s) == ref_status, diff(bodies_of(s), ref_bodies))

# ---------- C. random undo / amend walk ----------
rng = random.Random(7)
cur = list(OPS)
ok_all = True
hows = set()
for step in range(25):
    r = rng.random()
    if r < 0.5:
        cur = list(OPS[:rng.randint(0, len(OPS))])          # undo back some way, or redo forward
    elif r < 0.8 and cur:
        i = max(i for i, o in enumerate(cur) if o["type"] in ("push_pull", "move")) if any(
            o["type"] in ("push_pull", "move") for o in cur) else None
        if i is not None:                                   # amend: retype the last distance / vector
            o = json.loads(json.dumps(cur[i]))
            if o["type"] == "push_pull":
                o["distance"] = o["distance"] * rng.choice([0.5, 1.5, 2])
            else:
                o["vector"] = [v * rng.choice([0.5, 2]) for v in o["vector"]]
            cur = cur[:i] + [o] + cur[i + 1:]
    else:
        cur = list(OPS)
    how, _ = s.sync(cur)
    hows.add(how.split(",")[0].split(" ")[0])
    fb, fs = fresh(cur)
    if bodies_of(s) != fb or statuses(s) != fs:
        ok_all = False
        print("   walk step", step, how, diff(bodies_of(s), fb), flush=True)
        break
check("25-step undo/amend walk always equals a fresh build", ok_all)
check("walk used FreeCAD undo, not rebuilds", "undid" in hows and "rebuilt" not in hows, hows)
s.close()

# ---------- D. autosave, reopen, undo past the session start ----------
s = Session(model_path, fresh=True)
s.sync(OPS)
n_undo = s.doc.UndoCount
s.save(tmp)
check("saving doesn't touch the undo history", s.doc.UndoCount == n_undo, (s.doc.UndoCount, n_undo))
rev = s.rev
s.close()
s = Session(model_path)
check("reopen adopts the journal (failed ops dropped)",
      [e["op"]["id"] for e in s.applied] == [o["id"] for o in OPS if o["id"] != "p6"], [e["id"] for e in s.applied])
check("reopen: same revision, no outside edits", s.rev == rev and not s.external and s.undo_floor == 0,
      (s.rev, rev, s.external, s.undo_floor))
check("reopened document == built one", bodies_of(s) == ref_bodies, diff(bodies_of(s), ref_bodies))
adopted = [e["op"] for e in s.applied]
how, _ = s.sync(adopted + [ground_rect("r9", [0, 900, 0], [40, 40]), push("p9", "r9", 10, "b9")])
check("new ops after reopen apply as transactions", how.startswith("undid 0") and "b9" in bodies_of(s), how)
how, _ = s.sync(adopted)
check("undo of this session's ops uses FreeCAD undo", how.startswith("undid 2"), how)
how, _ = s.sync(adopted[:4])
check("undo past the session start rebuilds from the journal", how == "rebuilt" and bodies_of(s) == fresh(adopted[:4])[0],
      how)
s.sync(adopted)
s.save(tmp)
s.close()

# ---------- E. an edit made in FreeCAD ----------
d = App.openDocument(model_path)
ext = [o for o in d.Objects if o.Label == "p1 push"][0]
ext.LengthFwd = 40                   # the shelf is now 40 thick, edited in FreeCAD
d.recompute()
d.save()
App.closeDocument(d.Name)
s = Session(model_path)
b = bodies_of(s)
check("FreeCAD's edit shows on reopen, on every instance and mirror",
      b["b1"][1][5] == 40 and b["b2"][1][5] == 40 and b["b3"][1][5] == 40, (b["b1"][1], b["b3"][1]))
check("reopen notices the outside edit", s.external and s.undo_floor == len(s.applied), (s.external, s.undo_floor))
try:
    s.sync(adopted[:-2])
    refused = False
except OpError:
    refused = True
check("won't undo past an outside edit (no silent loss; merge is stage 2)", refused)
how, _ = s.sync(adopted + [ground_rect("r9", [0, 900, 0], [40, 40]), push("p9", "r9", 10, "b9")])
b = bodies_of(s)
check("new work on top keeps FreeCAD's edit", "b9" in b and b["b1"][1][5] == 40, how)
s.save(tmp)
s.close()
s = Session(model_path)
check("after our save the file is ours again", not s.external and bodies_of(s)["b1"][1][5] == 40)
s.close()

# ---------- F. mirrors of a component instance that sits away from its definition ----------
# Released FreeCAD 1.1 mirrors an App::Link without its placement, so instances are mirrored through a compound.
MOPS = [
    ground_rect("r1", [0, 0, 0], [100, 50]), push("p1", "r1", 20, "b1"),
    {"id": "c1", "type": "make_component", "body": "b1", "name": "Shelf"},
    {"id": "mv1", "type": "move", "targets": ["b1"], "vector": [0, 200, 0], "copy": True, "new_ids": ["b2"]},
    {"id": "m1", "type": "mirror", "targets": ["b2"], "plane": {"point": [150, 0, 0], "normal": [1, 0, 0]},
     "new_ids": ["b3"]},
]
s = Session(None)
s.sync(MOPS)
b = bodies_of(s)
check("mirrored copy of a moved instance sits across the plane", b["b3"][1] == (200, 200, 0, 300, 250, 20), b["b3"][1])
more = MOPS + [{"id": "mv2", "type": "move", "targets": ["b2"], "vector": [0, 100, 30]}]
s.sync(more)
b = bodies_of(s)
check("the mirrored copy follows when its instance moves",
      b["b2"][1] == (0, 300, 30, 100, 350, 50) and b["b3"][1] == (200, 300, 30, 300, 350, 50), (b["b2"][1], b["b3"][1]))
more = more + [face_rect("r2", "b3", [280, 310, 50], [10, 10]), push("p2", "r2", 15),
               {"id": "m2", "type": "mirror", "targets": ["b3"], "plane": {"point": [0, 400, 0], "normal": [0, 1, 0]},
                "new_ids": ["b4"]}]
s.sync(more)
b = bodies_of(s)
check("a bump drawn on it lands on the shared definition",
      statuses(s)[-2:] == [("p2", "ok"), ("m2", "ok")] and all(b[k][0] == 101500 for k in ("b1", "b2", "b3", "b4"))
      and b["b1"][1][5] == 35 and b["b3"][1][5] == 65, (statuses(s)[-3:], b["b1"], b["b3"]))
check("a mirror of that mirror lands across its plane", b["b4"][1] == (200, 450, 30, 300, 500, 65), b["b4"][1])
how, _ = s.sync(MOPS)
check("undo brings the mirrored copy back", how.startswith("undid") and bodies_of(s)["b3"][1] == (200, 200, 0, 300, 250, 20),
      (how, bodies_of(s)["b3"][1]))
s.close()

# ---------- G. rejections (I08) leave nothing behind ----------
GOPS = [ground_rect("r1", [0, 0, 0], [100, 50]), push("p1", "r1", 20, "b1")]
REJECTS = [
    ("cut that misses the board", [{"id": "rg1", "type": "rect", "plane": {"on": {"body": "b1", "normal": [0, 0, 1],
                                   "point": [10, 10, 20]}}, "corner": [300, 0], "size": [20, 20]},
                                   push("pg1", "rg1", -5)], "doesn't reach"),
    ("cut through the whole board", [{"id": "rg2", "type": "rect", "plane": {"on": {"body": "b1", "normal": [0, 0, 1],
                                     "point": [10, 10, 20]}}, "corner": [-20, -20], "size": [200, 100]},
                                     push("pg2", "rg2", -30)], "whole body"),
    ("merge that doesn't touch the board", [{"id": "rg3", "type": "rect", "plane": {"on": {"body": "b1", "normal": [0, 0, 1],
                                            "point": [10, 10, 20]}}, "corner": [300, 0], "size": [20, 20]},
                                            push("pg3", "rg3", 5)], "doesn't touch"),
]
s = Session(None)
s.sync(GOPS)
ref = bodies_of(s)
n_undo = s.doc.UndoCount
for name, extra, words in REJECTS:
    s.sync(GOPS + extra)
    st = s.status()[-1]
    check(f"rejected: {name}", st["status"] == "failed" and words in st.get("message", ""), st)
    check(f"rejected: {name} leaves the board and undo history as they were",
          bodies_of(s) == ref and s.doc.UndoCount == n_undo + 1, (bodies_of(s), s.doc.UndoCount))   # +1: the rect
    s.sync(GOPS)
s.close()

# ---------- H. runs: back-to-back cuts share one Cut, back-to-back merges one MultiFuse (Q20) ----------
def hole(k, x, y, size=20, depth=-18, body="b1", z=18):
    return [face_rect(f"rh{k}", body, [x, y, z], [size, size]), push(f"ph{k}", f"rh{k}", depth)]


def vol(sess, bid="b1"):
    return round(sess.model.world_shape(sess.model.body(bid)).Volume, 3)


def kinds(sess, bid="b1"):
    c = sess.model.definition(sess.model.body(bid))
    return sorted(o.TypeId for o in c.Group if o.TypeId in ("Part::Cut", "Part::MultiFuse", "Part::Fuse"))


V1 = 600 * 300 * 18
HOPS = [ground_rect("r1", [0, 0, 0], [600, 300]), push("p1", "r1", 18, "b1")]
for k in range(6):
    HOPS += hole(k, 30 + k * 90, 30)
s = Session(None)
s.sync(HOPS)
check("6 holes on a board: one Cut holding 6 cutters", kinds(s) == ["Part::Cut"]
      and len(s.model.definition(s.model.body("b1")).Tip.Tool.Links) == 6 and vol(s) == V1 - 6 * 7200, (kinds(s), vol(s)))
check("each hole is still its own undo step", s.doc.UndoCount == len(HOPS) - 0 and all(e["status"] == "ok" for e in s.applied),
      (s.doc.UndoCount, len(HOPS)))
how, _ = s.sync(HOPS[:-4])
check("undo two holes: FreeCAD undo, 4 holes left", how.startswith("undid 4") and vol(s) == V1 - 4 * 7200, (how, vol(s)))
s.sync(HOPS)
# overlapping and nested cutters in one run
more = HOPS + hole(10, 30, 150, size=200, depth=-6) + hole(11, 100, 200, size=10, depth=-12, z=12) \
    + hole(12, 120, 160, size=40, depth=-10, z=12)                     # pin hole and a deeper pocket, in the pocket
s.sync(more)
ref = Part.makeBox(600, 300, 18)
for k in range(6):
    ref = ref.cut(Part.makeBox(20, 20, 18, V(30 + k * 90, 30, 0)))
ref = ref.cut(Part.makeBox(200, 200, 6, V(30, 150, 12))).cut(Part.makeBox(10, 10, 12, V(100, 200, 0)))
ref = ref.cut(Part.makeBox(40, 40, 10, V(120, 160, 2)))
check("overlapping and nested cutters in one run (pin hole in a pocket, pocket in a pocket)",
      [e["status"] for e in s.applied[-6:]] == ["ok"] * 6 and abs(vol(s) - ref.Volume) < 1e-3 and kinds(s) == ["Part::Cut"],
      (s.status()[-6:], vol(s), ref.Volume))
inside = more + hole(13, 30, 30, size=10, depth=-5)          # drawn in the corner of hole 0, inside its empty space
s.sync(inside)
check("a hole inside an existing hole of the run is rejected (I08)", s.status()[-1]["status"] == "failed", s.status()[-1])
# a merge breaks the run; stacked and overlapping bumps in one MultiFuse
bumps = more + hole(20, 500, 200, size=60, depth=10) + hole(21, 510, 210, size=20, depth=30, z=28) \
    + hole(22, 540, 230, size=40, depth=10, z=28)       # starts on the first bump's top, overhangs it
s.sync(bumps)
ref2 = ref.fuse(Part.makeBox(60, 60, 10, V(500, 200, 18))).fuse(Part.makeBox(20, 20, 30, V(510, 210, 28)))
ref2 = ref2.fuse(Part.makeBox(40, 40, 10, V(540, 230, 28)))
check("bumps after cuts: a new run, one MultiFuse; stacked and overlapping bumps add up right",
      kinds(s) == ["Part::Cut", "Part::MultiFuse"] and abs(vol(s) - ref2.Volume) < 1e-3
      and [e["status"] for e in s.applied[-6:]] == ["ok"] * 6, (kinds(s), vol(s), ref2.Volume, s.status()[-6:]))
detached = bumps + [{"id": "rh23", "type": "rect", "plane": {"on": {"body": "b1", "normal": [0, 0, 1], "point": [10, 10, 18]}},
                     "corner": [900, 0], "size": [20, 20]}, push("ph23", "rh23", 5)]
s.sync(detached)
check("a detached bump in a merge run is rejected (I08)", s.status()[-1]["status"] == "failed"
      and "doesn't touch" in s.status()[-1].get("message", ""), s.status()[-1])
cuts_again = bumps + hole(30, 300, 100)
s.sync(cuts_again)
check("a cut after the merges starts a third run", kinds(s) == ["Part::Cut", "Part::Cut", "Part::MultiFuse"]
      and abs(vol(s) - (ref2.Volume - 7200)) < 1e-3, (kinds(s), vol(s)))
# move one hole out of the middle of a run, then copy another into a row
mv = cuts_again + [{"id": "mvh", "type": "move", "targets": [], "cut": {"body": "b1", "op": "ph2"}, "vector": [0, 60, 0]}]
s.sync(mv)
s.export(tmp)
cuts = {c["op"]: c for c in json.load(open(os.path.join(tmp, "bodies.json")))[0]["cuts"]}
check("move the 3rd of 6 holes: it moves, the others stay", s.status()[-1]["status"] == "ok"
      and [round(v) for v in cuts["ph2"]["lo"][:2]] == [210, 90] and [round(v) for v in cuts["ph3"]["lo"][:2]] == [300, 30]
      and abs(vol(s) - (ref2.Volume - 7200)) < 1e-3, (s.status()[-1], cuts.get("ph2"), cuts.get("ph3")))
row = mv + [{"id": "mvr", "type": "move", "targets": [], "cut": {"body": "b1", "op": "ph4"}, "vector": [0, 50, 0], "copy": True,
             "count": 3}]
s.sync(row)
s.export(tmp)
listed = [c["op"] for c in json.load(open(os.path.join(tmp, "bodies.json")))[0]["cuts"]]
check("copy the 5th hole into a row of 4: 3 more holes, listed under its op", s.status()[-1]["status"] == "ok"
      and abs(vol(s) - (ref2.Volume - 4 * 7200)) < 1e-3 and listed.count("ph4") == 4, (s.status()[-1], vol(s), listed))
off = row + [{"id": "mvo", "type": "move", "targets": [], "cut": {"body": "b1", "op": "ph1"}, "vector": [5000, 0, 0]}]
s.sync(off)
check("moving a hole of a run off the board is rejected", s.status()[-1]["status"] == "failed", s.status()[-1])
how, _ = s.sync(HOPS)
check("undo all of it back to the 6 holes: FreeCAD undo", how.startswith("undid") and vol(s) == V1 - 6 * 7200 and kinds(s) == ["Part::Cut"],
      (how, vol(s), kinds(s)))
fb, fst = fresh(row)       # first: it leaves another document active, which Draft arrays used to trip over
s.sync(row)
check("redo after undo == a fresh build, with runs (and arrays build in the right document)", fb == bodies_of(s) and fst == statuses(s),
      (diff(bodies_of(s), fb), [x for x in zip(statuses(s), fst) if x[0] != x[1]][:3]))
s.close()

print(f"\nNATIVE TESTS: {R[0]} passed, {R[1]} failed")
