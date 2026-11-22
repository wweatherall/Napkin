# runner: none (shared by test_native.py and test_runs.py, not a test)
"""Shared by worker/test_native.py and worker/test_runs.py (T49 split them to run side by side): check() and its
counts, the op builders, the reference op log OPS, and ways to read a session's boards. Named test_* so it stays
out of the worker's hash and the app bundle."""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_load  # Configure the FreeCAD test runtime before loading worker modules.
from export import component_of, material_of
from session import Session

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


def hole(k, x, y, size=20, depth=-18, body="b1", z=18):
    return [face_rect(f"rh{k}", body, [x, y, z], [size, size]), push(f"ph{k}", f"rh{k}", depth)]


def vol(sess, bid="b1"):
    return round(sess.model.world_shape(sess.model.body(bid)).Volume, 3)


def kinds(sess, bid="b1"):
    c = sess.model.definition(sess.model.body(bid))
    return sorted(o.TypeId for o in c.Group if o.TypeId in ("Part::Cut", "Part::MultiFuse", "Part::Fuse"))


V1 = 600 * 300 * 18                  # the 600 x 300 x 18 board the hole tests cut into
HOPS = [ground_rect("r1", [0, 0, 0], [600, 300]), push("p1", "r1", 18, "b1")]   # that board with 6 holes
for k in range(6):
    HOPS += hole(k, 30 + k * 90, 30)
