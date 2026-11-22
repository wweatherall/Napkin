"""runner: python3
The shop drawing and cut list show IDs as people read them (H059, T67): b3, not b3_<32 hex random part>.
Runs drawing.py (plain python3) on a small hand-made output folder."""
import csv, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    passed, failed = passed + bool(ok), failed + (not ok)
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))


out = tempfile.mkdtemp(prefix="drawing-ids-", dir=os.environ.get("TESTDIR"))
R = "0123456789abcdef0123456789abcdef"
view = '<svg><path d="M 0 0 L 600 400"/></svg>'
json.dump({k: view for k in ("Front", "Top", "Right", "Iso")}, open(os.path.join(out, "views.json"), "w"))
board = lambda bid, comp: {"id": bid, "component": comp, "size": [19, 300, 600], "material": "oak",
                           "world_bbox": [0, 0, 0, 600, 300, 19]}
json.dump([board(f"b3_{R}", None), board("b4", None), board(f"b5_{R}", "Shelf")],
          open(os.path.join(out, "bodies.json"), "w"))
json.dump({"ops": [{"id": f"pr2_{R}", "status": "ok"}, {"id": f"pp7_{R}", "status": "failed", "message": "no face"}],
           "total_ms": 5, "oplog": "test"}, open(os.path.join(out, "status.json"), "w"))
r = subprocess.run([sys.executable, os.path.join(HERE, "drawing.py"), out], capture_output=True, text=True)
check("drawing.py runs on the fixture", r.returncode == 0, r.stderr[-400:])
rows = list(csv.DictReader(open(os.path.join(out, "cutlist.csv")))) if r.returncode == 0 else []
check("the cut list names a board without a component b3, not its random ID; old IDs stay as they are",
      [x["part"] for x in rows] == ["b3", "b4", "Shelf"], rows)
check("the cut list's ids column has no random part", all(R not in x["ids"] for x in rows) and rows[2]["ids"] == "b5", rows)
svg = open(os.path.join(out, "drawing.svg")).read() if r.returncode == 0 else ""
check("a failed op on the drawing is named pp7", "FAILED pp7:" in svg and R not in svg, svg[-300:])
print(f"DRAWING ID TESTS: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
