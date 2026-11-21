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
check("copies of a board are linked (A22c): a cut on b4 shows on its copy b6",
      b["b4"][0] == b["b6"][0] == 75000 - 1000 + 30 * 30 * 12, (b["b4"][0], b["b6"][0]))
check("overhanging merge on a copy adds the whole rectangle, on every copy", round(b["b5"][0]) == 75000 - 1000 + 30 * 30 * 12, b["b5"][0])
types = {o.TypeId for o in s.doc.Objects}
check("native feature tree", {"App::Part", "Part::Plane", "Part::Extrusion", "Part::MultiFuse", "Part::Cut", "Part::Compound",
                              "App::Link", "Part::Mirroring", "App::Placement"} <= types and "Part::Feature" not in types, types)   # copies are links (A22c)
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

# ---------- I. undoing past FreeCAD's 20-step history rebuilds, one Ctrl+Z at a time ----------
IOPS = [ground_rect("r1", [0, 0, 0], [600, 300]), push("p1", "r1", 18, "b1")]
for k in range(12):
    IOPS += hole(k, 30 + (k % 6) * 90, 30 + (k // 6) * 120)
s = Session(None)
s.sync(IOPS)
hows, vols_ok = [], True
for n in range(len(IOPS) - 1, 1, -1):
    how, _ = s.sync(IOPS[:n])
    hows.append(how)
    holes_left = sum(1 for o in IOPS[:n] if o["type"] == "push_pull") - 1
    vols_ok &= vol(s) == V1 - holes_left * 7200
check("FreeCAD keeps 20 undo steps; the 21st Ctrl+Z in a row rebuilds, then undo works again",
      hows[:20] == ["undid 1, applied 0"] * 20 and hows[20] == "rebuilt" and all(h.startswith("undid 1") for h in hows[21:]), hows)
check("the model is right after every one of those undos", vols_ok)
s.close()

# ---------- J. a cut to the opposite face stays through when the board changes in FreeCAD (I24) ----------
JOPS = [ground_rect("r1", [0, 0, 0], [300, 200]), push("p1", "r1", 18, "b1"),
        face_rect("rj1", "b1", [50, 50, 18], [20, 20]), dict(push("pj1", "rj1", -18), through=True),
        face_rect("rj2", "b1", [150, 50, 18], [20, 20]), push("pj2", "rj2", -10)]
jpath = os.path.join(tmp, "through.FCStd")
for q in (jpath, journal_path(jpath)):
    if os.path.exists(q):
        os.remove(q)
s = Session(jpath, fresh=True)
s.sync(JOPS)
check("through-hole and a 10 mm blind hole", vol(s) == 300 * 200 * 18 - 7200 - 4000, vol(s))
s.export(tmp)
thru = [c for c in json.load(open(os.path.join(tmp, "bodies.json")))[0]["cuts"] if c["op"] == "pj1"][0]
check("the through-hole's outline stays inside the board", thru["lo"][2] >= -1e-6 and thru["hi"][2] <= 18 + 1e-6, thru)
s.save(tmp)
s.close()


def set_thickness(t):
    d = App.openDocument(jpath)
    [o for o in d.Objects if o.TypeId == "Part::Extrusion" and getattr(o, "SSOp", "") == "p1"][0].LengthFwd = t
    d.recompute()
    d.save()
    App.closeDocument(d.Name)


set_thickness(30)
s = Session(jpath)
check("board made 30 mm thick in FreeCAD: the through-hole still goes through (the blind one doesn't)",
      vol(s) == 300 * 200 * 30 - 20 * 20 * 30 - 4000, vol(s))
s.close()
set_thickness(12)
s = Session(jpath)
check("...and at 12 mm thick, still through (the blind one, drawn at 18 mm, now only reaches 8..12 mm)",
      vol(s) == 300 * 200 * 12 - 20 * 20 * 12 - 20 * 20 * 4, vol(s))
s.close()

# ---------- K. one mesh file per board, rewritten only when that board changes (T3) ----------
kdir = os.path.join(tmp, "meshes_test")
KOPS = [ground_rect("r1", [0, 0, 0], [300, 200]), push("p1", "r1", 18, "b1"),
        ground_rect("r2", [400, 0, 0], [100, 100]), push("p2", "r2", 30, "b2")]
s = Session(None)
s.sync(KOPS)
s.export(kdir)
first = {b["id"]: b["mesh"] for b in json.load(open(os.path.join(kdir, "bodies.json")))}
files0 = sorted(os.listdir(os.path.join(kdir, "meshes")))
check("a mesh file per board", sorted(first.values()) == files0 and len(files0) == 2, (first, files0))
s.sync(KOPS + hole("k", 50, 50))
s.export(kdir)
second = {b["id"]: b["mesh"] for b in json.load(open(os.path.join(kdir, "bodies.json")))}
files1 = sorted(os.listdir(os.path.join(kdir, "meshes")))
check("a hole in b1 rewrites b1's file only, and the old one is gone",
      second["b2"] == first["b2"] and second["b1"] != first["b1"] and files1 == sorted(second.values()), (first, second, files1))
raw = open(os.path.join(kdir, "meshes", second["b1"]), "rb").read()
counts, off = [], 0
for _ in range(4):
    t, n = struct.unpack_from("<II", raw, off)
    counts.append((t, n))
    off += 8 + n * 12
check("the file is four Godot vector arrays: triangles, normals, edges (pairs), corners",
      off == len(raw) and all(t == 36 for t, _ in counts) and counts[0][1] == counts[1][1] and counts[0][1] % 3 == 0
      and counts[2][1] == 2 * 24 and counts[3][1] == 16, counts)        # a box (12 edges) + a through-hole (12)
s.close()

# ---------- L. the saved file shows the right things when opened in FreeCAD (T29) ----------
import zipfile
import xml.etree.ElementTree as ET
lpath = os.path.join(tmp, "shown.FCStd")
for q in (lpath, journal_path(lpath)):
    if os.path.exists(q):
        os.remove(q)
s = Session(lpath, fresh=True)
s.sync(HOPS[:6])                      # a board with two holes: a Cut over the board's extrusion
s.save(tmp)
names = {o.Name: o.TypeId for o in s.doc.Objects}
s.close()


def gui_visibility(path):
    with zipfile.ZipFile(path) as z:
        g = ET.fromstring(z.read("GuiDocument.xml"))
    out = {}
    for vp in g.iter("ViewProvider"):
        for p in vp.iter("Property"):
            if p.get("name") == "Visibility":
                out[vp.get("name")] = p.find("Bool").get("value") == "true"
    return out, g


vis, _ = gui_visibility(lpath)
tips = [n for n, t in names.items() if t == "Part::Cut"]
steps = [n for n, t in names.items() if t in ("Part::Extrusion", "Part::Compound")]
origins = [n for n, t in names.items() if t in ("App::Origin", "App::Line", "App::Plane")]
check("saved file has FreeCAD's view part: the board's solid shown, its steps and axes hidden",
      set(vis) == set(names) and all(vis[n] for n in tips) and not any(vis[n] for n in steps + origins), (tips, steps, vis))
# FreeCAD's own view settings survive the next Shop Sketch save
with zipfile.ZipFile(lpath) as z:
    entries = {n: z.read(n) for n in z.namelist()}
g = ET.fromstring(entries["GuiDocument.xml"])
for vp in g.iter("ViewProvider"):
    if vp.get("name") == tips[0]:
        props = vp.find("Properties")
        c = ET.SubElement(props, "Property", name="LineWidth", type="App::PropertyFloat", status="1")
        ET.SubElement(c, "Float", value="4.0")
ET.SubElement(g, "Camera", settings="OrthographicCamera { height 123 }")
entries["GuiDocument.xml"] = ET.tostring(g)
with zipfile.ZipFile(lpath, "w", zipfile.ZIP_DEFLATED) as z:
    for n, b in entries.items():
        z.writestr(n, b)
s = Session(lpath)
s.sync([e["op"] for e in s.applied] + hole(50, 400, 100))
s.save(tmp)
s.close()
vis2, g2 = gui_visibility(lpath)
kept = [p for vp in g2.iter("ViewProvider") if vp.get("name") == tips[0] for p in vp.iter("Property") if p.get("name") == "LineWidth"]
check("FreeCAD's own view settings (a line width, the camera) survive Shop Sketch's next save",
      bool(kept) and g2.find("Camera") is not None and "123" in g2.find("Camera").get("settings") and vis2.get(tips[0]), (kept, vis2.get(tips[0])))

# ---------- M. linked copies, arrays, Make unique, Detach from array (T12: A22c, I25, I28, Q29) ----------
def bx(sess, bid):
    return tuple(round(v, 3) for v in bodies_of(sess)[bid][1][:3])


MO = [ground_rect("r1", [0, 0, 0], [100, 50]), push("p1", "r1", 18, "b1"),
      {"id": "mv1", "type": "move", "targets": ["b1"], "vector": [0, 100, 0], "copy": True, "new_ids": ["b2"]}]
s = Session(None)
s.sync(MO)
check("a copy of a plain board: both become links to one definition",
      s.model.is_instance(s.model.body("b1")) and s.model.is_instance(s.model.body("b2"))
      and s.model.body("b1").LinkedObject is s.model.body("b2").LinkedObject)
MO += [face_rect("rm1", "b2", [50, 125, 18], [20, 20]), push("pm1", "rm1", -18)]
s.sync(MO)
check("a hole drawn on the copy is in the original too", bodies_of(s)["b1"][0] == bodies_of(s)["b2"][0] == 100 * 50 * 18 - 20 * 20 * 18,
      (bodies_of(s)["b1"][0], bodies_of(s)["b2"][0]))
MO += [{"id": "mv2", "type": "move", "targets": ["b1"], "vector": [150, 0, 0], "copy": True, "count": 3, "new_ids": ["b3", "b4", "b5"]},
       {"id": "mv3", "type": "move", "targets": ["b1"], "vector": [0, 0, 300], "copy": True, "count": 3, "divide": True,
        "new_ids": ["b6", "b7", "b8"]}]
s.sync(MO)
check("3x array at 150 mm and a /3 array over 300 mm", [bx(s, b)[0] for b in ("b3", "b4", "b5")] == [150, 300, 450]
      and [bx(s, b)[2] for b in ("b6", "b7", "b8")] == [100, 200, 300], [bx(s, b) for b in ("b3", "b4", "b5", "b6", "b7", "b8")])
arr3 = [o for o in s.doc.Objects if getattr(o, "SSRole", "") == "array" and o.SSOp == "mv3"][0]
arr3.Span = V(0, 0, 600)                          # as if edited in FreeCAD
s.doc.recompute()
check("the /3 array re-spreads when its span changes (I25)", [bx(s, b)[2] for b in ("b6", "b7", "b8")] == [200, 400, 600],
      [bx(s, b) for b in ("b6", "b7", "b8")])
arr3.Span = V(0, 0, 300)
s.doc.recompute()
MO += [{"id": "mv4", "type": "move", "targets": ["b4"], "vector": [0, 0, 1000]}]
s.sync(MO)
check("moving one copy moves its whole row, original included", bx(s, "b4")[2] == 1000 and bx(s, "b1")[2] == 1000
      and bx(s, "b3")[2] == 1000 and bx(s, "b7")[2] == 1200, [bx(s, b) for b in ("b1", "b3", "b4", "b7")])
MO += [{"id": "dt1", "type": "detach", "targets": ["b7"]}, {"id": "mu1", "type": "make_unique", "targets": ["b8"]}]
s.sync(MO)
arr3 = [o for o in s.doc.Objects if getattr(o, "SSRole", "") == "array" and o.SSOp == "mv3"][0]
arr3.Span = V(0, 0, 900)
s.doc.recompute()
check("a detached copy stays put when the row changes; a unique one still follows it (Q29)",
      bx(s, "b7")[2] == 1200 and bx(s, "b8")[2] == 1900 and bx(s, "b6")[2] == 1300, [bx(s, b) for b in ("b6", "b7", "b8")])
arr3.Span = V(0, 0, 300)
s.doc.recompute()
MO += [face_rect("rm2", "b1", [80, 10, 1018], [10, 10]), push("pm2", "rm2", -18)]
s.sync(MO)
check("after Make unique, editing the others leaves it alone (I28)",
      bodies_of(s)["b1"][0] == bodies_of(s)["b7"][0] == 100 * 50 * 18 - 500 * 18 and bodies_of(s)["b8"][0] == 100 * 50 * 18 - 400 * 18,
      (bodies_of(s)["b1"][0], bodies_of(s)["b7"][0], bodies_of(s)["b8"][0]))
check("statuses all ok", all(st == "ok" for _, st in statuses(s)), [x for x in statuses(s) if x[1] != "ok"])
s.export(os.path.join(tmp, "m_out"))
fam = {e["id"]: e.get("family", "") for e in json.load(open(os.path.join(tmp, "m_out", "bodies.json")))}
check("bodies.json says which boards are linked (family) for the viewport's tint", fam["b1"] == fam["b3"] != "" and fam["b8"] == "", fam)
how, _ = s.sync(MO[:3])
check("undo it all back to the first copy", how.startswith("undid") and len(bodies_of(s)) == 2, (how, sorted(bodies_of(s))))
s.close()

# ---------- N. assemblies (T20) ----------
NO = [ground_rect("r1", [0, 0, 0], [100, 50]), push("p1", "r1", 18, "b1"),
      ground_rect("r2", [0, 100, 0], [100, 50]), push("p2", "r2", 18, "b2"),
      ground_rect("r3", [300, 0, 0], [100, 50]), push("p3", "r3", 18, "b3"),
      {"id": "as1", "type": "make_assembly", "targets": ["b1", "b2"], "new_id": "a1", "name": "Drawer"}]
s = Session(None)
s.sync(NO)
a1 = s.model.assemblies().get("a1")
check("two boards grouped into an assembly", a1 is not None and sorted(o.BodyId for o in a1.Group) == ["b1", "b2"],
      a1 and [o.Label for o in a1.Group])
NO += [{"id": "mva", "type": "move", "targets": ["a1"], "vector": [0, 0, 200]}]
s.sync(NO)
check("moving the assembly moves both boards, not the third", bx(s, "b1")[2] == 200 and bx(s, "b2")[2] == 200 and bx(s, "b3")[2] == 0,
      [bx(s, b) for b in ("b1", "b2", "b3")])
NO += [face_rect("rn1", "b1", [50, 25, 218], [20, 20]), push("pn1", "rn1", -18)]
s.sync(NO)
check("a hole drawn inside the moved assembly lands on its board", bodies_of(s)["b1"][0] == 100 * 50 * 18 - 20 * 20 * 18, bodies_of(s)["b1"][0])
NO += [{"id": "mvc", "type": "move", "targets": ["b1"], "vector": [500, 0, 0], "copy": True, "count": 2, "new_ids": ["b4", "b5"]},
       {"id": "mvd", "type": "move", "targets": ["b5"], "vector": [0, 300, 0], "detach": True}]
s.sync(NO)
check("inside an entered array, a copy moves alone and leaves the row (I32)",
      bx(s, "b5")[:2] == (1000, 300) and bx(s, "b4")[:2] == (500, 0) and not s.model.body("b5").SSArray, [bx(s, b) for b in ("b4", "b5")])
s.export(os.path.join(tmp, "n_out"))
asm = {e["id"]: e.get("assembly", "") for e in json.load(open(os.path.join(tmp, "n_out", "bodies.json")))}
check("bodies.json says which assembly each board is in (copies made of a member join it)",
      asm["b1"] == asm["b2"] == asm["b4"] == asm["b5"] == "a1" and asm["b3"] == "", asm)
check("statuses all ok", all(st == "ok" for _, st in statuses(s)), [x for x in statuses(s) if x[1] != "ok"])
how, _ = s.sync(NO[:6])
check("undo back to before the assembly", how.startswith("undid") and not s.model.assemblies(), how)
s.close()

# ---------- O. mirror groups (T26, A11b) ----------
NG = [ground_rect("r1", [0, 0, 0], [100, 50]), push("p1", "r1", 18, "b1"),
      {"id": "m1", "type": "mirror", "targets": ["b1"], "plane": {"point": [200, 0, 0], "normal": [1, 0, 0]},
       "new_ids": ["b2"], "group": "a1"}]
s = Session(None)
s.sync(NG)
g = s.model.assemblies().get("a1")
check("a mirrored copy and its original make a mirror group", g is not None and g.SSKind == "mirror"
      and sorted(o.BodyId for o in g.Group) == ["b1", "b2"], g and [o.Label for o in g.Group])
check("the copy sits across the plane", bx(s, "b2")[:3] == (300, 0, 0), bx(s, "b2"))
NG += [{"id": "mv1", "type": "move", "targets": ["b2"], "vector": [50, 20, 0]}]
s.sync(NG)
check("moving the copy moves the original the mirrored way (x reflected, y the same)",
      bx(s, "b1")[:2] == (-50, 20) and bx(s, "b2")[:2] == (350, 20), [bx(s, "b1"), bx(s, "b2")])
NG += [{"id": "mv2", "type": "move", "targets": ["b1"], "vector": [10, 0, 0]}]
s.sync(NG)
check("moving the original: the copy reflects it", bx(s, "b1")[0] == -40 and bx(s, "b2")[0] == 340, [bx(s, "b1"), bx(s, "b2")])
NG += [{"id": "mv3", "type": "move", "targets": ["a1"], "vector": [0, 0, 100]}]
s.sync(NG)
check("moving the group moves both and its plane", bx(s, "b1")[2] == 100 and bx(s, "b2")[2] == 100 and bx(s, "b2")[0] == 340,
      [bx(s, "b1"), bx(s, "b2")])
NG += [{"id": "mv4", "type": "move", "targets": ["a1"], "vector": [100, 0, 0]}]
s.sync(NG)
check("moving the group sideways keeps the pair mirrored", bx(s, "b1")[0] == 60 and bx(s, "b2")[0] == 440, [bx(s, "b1"), bx(s, "b2")])
NG += [{"id": "m2", "type": "mirror", "targets": ["b1"], "plane": {"point": [0, 0, 0], "normal": [1, 0, 0]}, "replace": True},
       {"id": "mv5", "type": "move", "targets": ["a1"], "vector": [0, 0, 100]}]
s.sync(NG)
check("a board flipped in place stays in its group, and moves with it", s.model.assembly_of(s.model.body("b1")) is g
      and bx(s, "b1")[2] == 200 and bx(s, "b2")[2] == 200, [bx(s, "b1"), bx(s, "b2")])
NG += [{"id": "m3", "type": "mirror", "targets": ["b2"], "plane": {"point": [500, 0, 0], "normal": [0.7071068, 0.7071068, 0]},
        "new_ids": ["b4"]}]
s.sync(NG)
v2, v4 = bodies_of(s)["b2"][0], bodies_of(s).get("b4", [0])[0]
check("a mirror across a sloped plane (a face at 45 degrees) keeps the volume", abs(v2 - v4) < 1e-3 and v4 > 0, [v2, v4])
s.export(os.path.join(tmp, "o_out"))
ent = {e["id"]: e for e in json.load(open(os.path.join(tmp, "o_out", "bodies.json")))}
check("bodies.json gives the copy's mirror plane", ent["b2"]["mirror_plane"] and abs(ent["b2"]["mirror_plane"][0][0] - 300) < 1e-6,
      ent["b2"].get("mirror_plane"))
check("statuses all ok", all(st == "ok" for _, st in statuses(s)), [x for x in statuses(s) if x[1] != "ok"])
s.close()

print(f"\nNATIVE TESTS: {R[0]} passed, {R[1]} failed")
