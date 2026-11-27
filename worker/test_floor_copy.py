"""Floor copy (A38): rebuilding past FreeCAD's 20 undo steps or below session_base keeps FreeCAD's edits
by starting from <model>.floor.FCStd beside the model, recorded in the journal's floor_copy field.
Covers: external edit on reopen, reload_outside, rebuild across restart, missing or tampered floor copy,
legacy journal without floor_copy, and models never edited outside.

  freecadcmd worker/test_floor_copy.py        (TESTDIR=<folder> for its files)"""
import json
import os
import shutil
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import FreeCAD as App
from common import OpError
from session import Session, atomic_json, generation, read_journal, sha256

tmp = os.environ.get("TESTDIR", "/tmp/floor_copy_test")
os.makedirs(tmp, exist_ok=True)
R = [0, 0]
MISSING_MSG = "can't undo past the FreeCAD edit: its copy is missing"


def check(name, cond, detail=""):
    R[0 if cond else 1] += 1
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"), flush=True)


def board(n, w=200):
    return [{"id": f"r{n}", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, n * 300, 0]}, "size": [w, 100]},
            {"id": f"pp{n}", "type": "push_pull", "target": {"rect": f"r{n}"}, "distance": 18, "body": f"b{n}"}]


def extra_25_ops(start=4):
    """25 ok ops (> FreeCAD's 20 undo steps): 12 new boards (24 ops) + 1 paint op."""
    ops = []
    for n in range(start, start + 12):
        ops += board(n)
    ops.append({"id": f"pt{start}", "type": "paint", "body": f"b{start}", "material": "walnut"})
    assert len(ops) == 25
    return ops


def model(name):
    folder = os.path.join(tmp, name)
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)
    return os.path.join(folder, "m.FCStd")


def add_freecad_cube(path, label):
    d = App.openDocument(path)
    box = d.addObject("Part::Box", label)
    box.Label = label
    box.Length = 50
    box.Width = 50
    box.Height = 50
    d.recompute()
    d.save()
    App.closeDocument(d.Name)


def has_label(doc, label):
    return any(o.Label == label for o in doc.Objects)


def three_boards(path):
    s = Session(path)
    ops = board(1) + board(2) + board(3)
    s.sync(ops)
    s.save()
    return s, ops


# ---------- 1. External edit -> reopen -> floor copy & journal -> 25 ops -> rebuild ----------
p = model("external-reopen")
g = generation(p)
s, base_ops = three_boards(p)
s.close()

add_freecad_cube(p, "WorkshopCube")
s = Session(p)
check("reopen after FreeCAD edit: external, undo_floor=6, floor copy exists",
      s.external and s.undo_floor == 6 and os.path.exists(g["floor_file"]),
      (s.external, s.undo_floor, os.path.exists(g["floor_file"])))
floor_sha = sha256(g["floor_file"])
check("... floor_copy matches the floor file's sha and undo_floor",
      s.floor_copy == {"sha256": floor_sha, "ops": 6}, s.floor_copy)
s.save()
j = read_journal(g["journal"])
check("... saved journal records floor_copy matching the floor file",
      j is not None and j.get("floor_copy") == {"sha256": floor_sha, "ops": 6} and j.get("floor") == 6,
      j and (j.get("floor_copy"), j.get("floor")))

more = extra_25_ops(4)
how, _ = s.sync(base_ops + more)
check("25 new ops apply on top of FreeCAD's edit (15 boards + cube)",
      len(s.model.bodies()) == 15 and has_label(s.doc, "WorkshopCube"),
      (how, len(s.model.bodies()), has_label(s.doc, "WorkshopCube")))

how, _ = s.sync(base_ops + more[:2])
check("sync back to the first 2 new ops rebuilds from the floor copy",
      how == "rebuilt" and s.undo_floor == 6 and s.session_base == 6,
      (how, s.undo_floor, s.session_base))
check("... FreeCAD's cube survives the rebuild and boards are b1..b4",
      has_label(s.doc, "WorkshopCube") and sorted(s.model.bodies()) == ["b1", "b2", "b3", "b4"]
      and len(s.applied) == 8,
      (has_label(s.doc, "WorkshopCube"), sorted(s.model.bodies()), len(s.applied)))

s.save()
check("saving after a floor-copy rebuild writes the model path and leaves the floor copy untouched",
      sha256(g["floor_file"]) == floor_sha and read_journal(g["journal"])["file_sha256"] == sha256(p)
      and read_journal(g["journal"]).get("floor_copy") == {"sha256": floor_sha, "ops": 6})
s.close()

# Reopen after save: floor_copy comes from the journal on disk and still supports rebuild across restarts.
s = Session(p)
check("reopen after save: not external, keeps cube, b1..b4, undo_floor=6, floor_copy from journal",
      not s.external and has_label(s.doc, "WorkshopCube")
      and sorted(s.model.bodies()) == ["b1", "b2", "b3", "b4"]
      and s.undo_floor == 6 and s.floor_copy == {"sha256": floor_sha, "ops": 6},
      (s.external, s.undo_floor, s.floor_copy))
how, _ = s.sync(base_ops)
check("rebuild across a restart (below session_base) keeps FreeCAD's cube and b1..b3",
      how == "rebuilt" and has_label(s.doc, "WorkshopCube")
      and sorted(s.model.bodies()) == ["b1", "b2", "b3"] and s.undo_floor == 6 and s.session_base == 6,
      (how, has_label(s.doc, "WorkshopCube"), sorted(s.model.bodies())))
s.close()

# ---------- 2. Outside save while open (reload_outside) -> 25 ops -> rebuild ----------
p = model("reload-outside")
g = generation(p)
s, base_ops = three_boards(p)

add_freecad_cube(p, "ReloadCube")
s.reload_outside()
check("reload_outside writes the floor copy and records it in the journal",
      os.path.exists(g["floor_file"]) and s.undo_floor == 6
      and read_journal(g["journal"]).get("floor_copy") == {"sha256": sha256(g["floor_file"]), "ops": 6},
      (os.path.exists(g["floor_file"]), s.undo_floor, read_journal(g["journal"]).get("floor_copy")))
floor_sha = sha256(g["floor_file"])

more = extra_25_ops(4)
s.sync(base_ops + more)
how, _ = s.sync(base_ops + more[:2])
check("after reload_outside, rebuild past 20 undo steps keeps FreeCAD's cube and b1..b4",
      how == "rebuilt" and has_label(s.doc, "ReloadCube")
      and sorted(s.model.bodies()) == ["b1", "b2", "b3", "b4"]
      and s.undo_floor == 6 and s.session_base == 6,
      (how, has_label(s.doc, "ReloadCube"), sorted(s.model.bodies())))
s.save()
check("saving after reload_outside rebuild writes model path and preserves floor copy",
      sha256(g["floor_file"]) == floor_sha and read_journal(g["journal"])["file_sha256"] == sha256(p))
s.close()

# ---------- 3. Deleted or tampered floor copy -> OpError and document unchanged ----------
for mode in ("deleted", "tampered"):
    p = model("missing-" + mode)
    g = generation(p)
    s, base_ops = three_boards(p)
    s.close()
    add_freecad_cube(p, "GuardedCube")
    s = Session(p)
    more = extra_25_ops(4)
    s.sync(base_ops + more)
    before_doc = s.doc.Name
    before_bodies = sorted(s.model.bodies())
    before_applied = [e["id"] for e in s.applied]
    if mode == "deleted":
        os.remove(g["floor_file"])
    else:
        with open(g["floor_file"], "ab") as f:
            f.write(b"x")
    err = None
    try:
        s.sync(base_ops + more[:2])
    except OpError as e:
        err = str(e)
    check(f"{mode} floor copy: rebuild raises OpError with the exact message",
          err == MISSING_MSG, err)
    check(f"{mode} floor copy: document and applied ops stay unchanged",
          s.doc is not None and s.doc.Name == before_doc
          and sorted(s.model.bodies()) == before_bodies
          and [e["id"] for e in s.applied] == before_applied
          and has_label(s.doc, "GuardedCube"),
          (s.doc and s.doc.Name, len(s.model.bodies()), len(s.applied)))
    s.close()

# Legacy journal without floor_copy field reads as no copy and refuses rebuild safely.
p = model("legacy-no-floor-copy")
g = generation(p)
s, base_ops = three_boards(p)
s.close()
add_freecad_cube(p, "LegacyCube")
s = Session(p)
s.sync(base_ops + board(4))
s.save()
s.close()
j = read_journal(g["journal"])
j.pop("floor_copy", None)
atomic_json(g["journal"], j)
s = Session(p)
check("a journal without floor_copy reads as no copy",
      not s.external and s.undo_floor == 6 and s.floor_copy is None,
      (s.external, s.undo_floor, s.floor_copy))
before_bodies = sorted(s.model.bodies())
err = None
try:
    s.sync(base_ops)
except OpError as e:
    err = str(e)
check("... rebuild without journal floor_copy raises OpError and leaves document unchanged",
      err == MISSING_MSG and sorted(s.model.bodies()) == before_bodies and has_label(s.doc, "LegacyCube"),
      (err, sorted(s.model.bodies())))
s.close()

# ---------- 4. Model never edited outside: no floor copy, rebuild works as today ----------
p = model("never-edited")
g = generation(p)
s, base_ops = three_boards(p)
s.close()
s = Session(p)
check("model never edited outside: no floor copy file, no floor_copy in journal",
      not s.external and s.undo_floor == 0 and s.floor_copy is None
      and not os.path.exists(g["floor_file"])
      and "floor_copy" not in read_journal(g["journal"]),
      (s.external, s.undo_floor, s.floor_copy, os.path.exists(g["floor_file"])))
more = extra_25_ops(4)
s.sync(base_ops + more)
how, _ = s.sync(base_ops + more[:2])
check("... rebuild past 20 undo steps works as today and writes no floor copy",
      how == "rebuilt" and sorted(s.model.bodies()) == ["b1", "b2", "b3", "b4"]
      and s.undo_floor == 0 and not os.path.exists(g["floor_file"]),
      (how, sorted(s.model.bodies()), os.path.exists(g["floor_file"])))
s.save()
check("... saving still leaves no floor copy and no floor_copy field",
      not os.path.exists(g["floor_file"]) and "floor_copy" not in read_journal(g["journal"]))
s.close()

# ---------- 5. Legacy fit op in floor entries + floor_copy rebuild ----------
p = model("legacy-fit-floor")
g = generation(p)
s = Session(p)
fit_base = board(1) + board(2)
fit_base[2]["plane"]["origin"] = [0, 0, 100]  # b2 above b1
fit_op = {"id": "fit1", "type": "fit", "body": "b1", "target_body": "b2", "axis": 2, "face": 4, "fit_mode": 0}
s.sync(fit_base + [fit_op])
s.save()
s.close()

add_freecad_cube(p, "FitFloorCube")
# Rewrite journal before reopen so the floor entry is a legacy property_edit plane_fit.
with open(g["journal"]) as f:
    j_raw = json.load(f)
j_raw["ops"][-1] = {"id": "fit1", "type": "property_edit", "mode": "plane_fit",
                    "body": "b1", "target_body": "b2", "axis": 2, "face": 4, "fit_mode": 0}
atomic_json(g["journal"], j_raw)

s = Session(p)
check("legacy fit in floor entries is upgraded on open",
      s.external and s.undo_floor == 5 and s.applied[-1]["op"] == fit_op,
      (s.external, s.undo_floor, s.applied[-1]["op"]))
more = extra_25_ops(4)
s.sync(fit_base + [fit_op] + more)
how, _ = s.sync(fit_base + [fit_op] + more[:2])
check("rebuild from floor copy keeps upgraded fit floor entry and FreeCAD cube",
      how == "rebuilt" and has_label(s.doc, "FitFloorCube") and s.applied[4]["op"] == fit_op,
      (how, has_label(s.doc, "FitFloorCube"), s.applied[4]["op"]))
s.close()

print(f"\nFLOOR COPY TESTS: {R[0]} passed, {R[1]} failed", flush=True)
sys.exit(1 if R[1] else 0)
