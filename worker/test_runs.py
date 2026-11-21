"""Runs of cuts and merges (Q20, A22b), split out of test_native.py so the two run side by side (T49): back-to-back
cuts share one Part::Cut, back-to-back merges one Part::MultiFuse; overlaps, rejections, moving and copying a
hole of a run, undo and redo.

  freecadcmd worker/test_runs.py        (TESTDIR=<folder> for its files)"""
import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_native_common import *  # noqa: E402,F403

tmp = os.environ.get("TESTDIR", "/tmp/runs_test")
os.makedirs(tmp, exist_ok=True)

# ---------- runs: back-to-back cuts share one Cut, back-to-back merges one MultiFuse (Q20) ----------
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

print(f"\nRUN TESTS: {R[0]} passed, {R[1]} failed", flush=True)   # flush: sys.exit in freecadcmd drops buffered output
sys.exit(1 if R[1] else 0)
