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
check("native feature tree", {"App::Part", "Part::Plane", "Part::Extrusion", "Part::Fuse", "Part::Cut",
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

print(f"\nNATIVE TESTS: {R[0]} passed, {R[1]} failed")
