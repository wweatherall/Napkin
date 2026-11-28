"""Atomic single-file saves (A42) and legacy file-and-journal upgrades (G09): saves write <model>.saving.FCStd
and rename it over <model>.FCStd; nothing else is written beside the model. Opening removes any leftover
.saving.FCStd, and upgrades legacy <model>.shopsketch.json + <model>.floor.FCStd on first save.

  freecadcmd worker/test_generations.py        (TESTDIR=<folder> for its files)"""
import json
import os
import shutil
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import FreeCAD as App
import session as S
from common import OpError
from serve import open_reply
from session import Session, content_sha256, read_journal, saving_path, sha256

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
LEGACY_FIXTURE = os.path.join(REPO_ROOT, "tests", "legacy_one_file")

tmp = os.environ.get("TESTDIR", "/tmp/generations_test")
os.makedirs(tmp, exist_ok=True)
R = [0, 0]


def check(name, cond, detail=""):
    R[0 if cond else 1] += 1
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"), flush=True)


def board(n, w=200):
    return [{"id": f"r{n}", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, n * 300, 0]}, "size": [w, 100]},
            {"id": f"pp{n}", "type": "new_board", "target": {"rect": f"r{n}"}, "distance": 18, "body": f"b{n}"}]


def model(name):
    folder = os.path.join(tmp, name)
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)
    return os.path.join(folder, "m.FCStd")


def whole(p):
    jj = read_journal(p)
    if not (os.path.exists(p) and jj is not None):
        return False
    import zipfile, xml.etree.ElementTree as ET
    with zipfile.ZipFile(p) as z:
        root = ET.fromstring(z.read("Document.xml"))
    meta = {i.get("key"): i.get("value") for i in root.findall("./Properties/Property[@name='Meta']/Map/Item")}
    return meta.get("ShopSketchContentSha256") == content_sha256(p)


def rev_of(p):
    return int(read_journal(p)["rev"])


class Crash(BaseException):
    """A crash part way through a save: not an Exception, so save()'s clean-up doesn't run (a real crash wouldn't)."""


def saved_until_replace(s):
    """Save, stopping (as a crash would) just before the os.replace that writes s.path."""
    real = os.replace

    def replace(src, dst):
        if os.path.abspath(dst) == os.path.abspath(s.path):
            raise Crash()
        real(src, dst)
    S.os.replace = replace
    try:
        s.save()
    except Crash:
        pass
    finally:
        S.os.replace = real


def saved_three(path):
    """A model saved at revs 1, 2, 3 (one more board each)."""
    s = Session(path)
    ops = []
    for n in range(1, 4):
        ops += board(n)
        s.sync(ops)
        s.save()
    return s, ops


# ---------- a normal save leaves only the .FCStd in its folder, whole ----------
p = model("normal")
s, ops = saved_three(p)
check("a normal save: only m.FCStd in its folder, whole, rev=3",
      os.listdir(os.path.dirname(p)) == ["m.FCStd"] and whole(p) and rev_of(p) == 3 == s.rev,
      (os.listdir(os.path.dirname(p)), s.rev))
s.close()
s = Session(p)
check("reopening a whole single-file save: not external, rev=3, 6 ops",
      not s.external and s.recovered is None and s.rev == 3 and len(s.applied) == 6,
      (s.external, s.recovered, s.rev, len(s.applied)))
check("... and the open reply has no recovered field", "recovered" not in open_reply(s, 1))
s.close()

# ---------- copying only the .FCStd somewhere else opens with everything ----------
copy_dir = os.path.join(tmp, "copy-only")
shutil.rmtree(copy_dir, ignore_errors=True)
os.makedirs(copy_dir)
cp_path = os.path.join(copy_dir, "copied.FCStd")
shutil.copy2(p, cp_path)
s = Session(cp_path)
check("copying only the .FCStd opens cleanly with all ops and bodies",
      not s.external and s.rev == 3 and len(s.applied) == 6 and sorted(s.model.bodies()) == ["b1", "b2", "b3"],
      (s.external, s.rev, len(s.applied), sorted(s.model.bodies())))
s.close()

# ---------- crash between writing .saving.FCStd and os.replace: previous save whole, .saving removed ----------
p = model("crash-before-replace")
s, ops = saved_three(p)
ops += board(4)
s.sync(ops)
saved_until_replace(s)
s.close()
check("crash before replace: .saving.FCStd exists on disk, m.FCStd still rev 3",
      os.path.exists(saving_path(p)) and whole(p) and rev_of(p) == 3)
s = Session(p)
check("reopening after crash removes .saving.FCStd and opens rev 3 whole",
      not os.path.exists(saving_path(p)) and not s.external and s.rev == 3 and len(s.applied) == 6
      and sorted(s.model.bodies()) == ["b1", "b2", "b3"],
      (os.path.exists(saving_path(p)), s.external, s.rev, len(s.applied)))
s.close()

# ---------- a failed save holds rev back, cleans up .saving.FCStd, retry succeeds (T79) ----------
p = model("failed")
s, ops = saved_three(p)
real = os.replace


def failing(src, dst):
    if os.path.abspath(dst) == os.path.abspath(p):
        raise OSError("disk full")
    real(src, dst)


ops += board(4)
s.sync(ops)
S.os.replace = failing
try:
    s.save()
    raised = False
except OSError:
    raised = True
finally:
    S.os.replace = real
check("a failed save raises, holds the revision back and cleans up .saving.FCStd",
      raised and s.rev == 3 and not os.path.exists(saving_path(p)), s.rev)
check("... the current file is untouched", whole(p) and rev_of(p) == 3)
s.save()
check("... and the retry saves it", s.rev == 4 and whole(p) and rev_of(p) == 4)
s.close()

# ---------- legacy upgrade (G09): fixture written by main's code upgrades on first save ----------
upg_dir = os.path.join(tmp, "legacy-upgrade")
shutil.rmtree(upg_dir, ignore_errors=True)
shutil.copytree(LEGACY_FIXTURE, upg_dir)
upg_p = os.path.join(upg_dir, "model.FCStd")
upg_unmatched = os.path.join(upg_dir, "model.unmatched.FCStd")
with open(upg_unmatched, "wb") as f:
    f.write(b"user-unmatched-bytes")

s = Session(upg_p)
res99 = "b99_" + f"{99:032x}"
check("legacy fixture opens with full history, undo_floor=4, dropped, reserved_ids, units, WorkshopCube",
      not s.external and s.undo_floor == 4 and len(s.applied) == 26 and len(s.dropped) == 2
      and res99 in s.ids.reserved and s.units == "in-frac:1/16"
      and s.doc.getObject("WorkshopCube") is not None and len(s.model.bodies()) == 13,
      (s.external, s.undo_floor, len(s.applied), len(s.dropped), res99 in s.ids.reserved, s.units))

# Undo > 20 steps back to undo_floor + 2 ops (rebuilds from legacy model.floor.FCStd)
kept_to_floor = [e["op"] for e in s.applied[:6]]
how_u, _ = s.sync(kept_to_floor)
check("legacy fixture undoes > 20 steps via floor copy and keeps WorkshopCube",
      how_u == "rebuilt" and s.doc.getObject("WorkshopCube") is not None and len(s.model.bodies()) == 3,
      (how_u, len(s.model.bodies())))

# Undoing before undo_floor is refused
refused_below = False
try:
    s.sync([e["op"] for e in s.applied[:2]])
except OpError:
    refused_below = True
check("legacy fixture refuses undo before undo_floor", refused_below)

# A failing save (read-only folder) leaves the old journal and floor copy in place
os.chmod(upg_dir, 0o555)
ro_failed = False
try:
    s.save()
except PermissionError:
    ro_failed = True
finally:
    os.chmod(upg_dir, 0o755)
check("failed save on legacy model leaves old journal and floor copy in place",
      ro_failed and os.path.exists(os.path.join(upg_dir, "model.shopsketch.json"))
      and os.path.exists(os.path.join(upg_dir, "model.floor.FCStd")),
      (ro_failed, os.listdir(upg_dir)))

# First successful save embeds everything and removes old journal/floor, leaving .unmatched alone
s.save()
after_ls = sorted(os.listdir(upg_dir))
check("first save removes legacy journal/floor and preserves .unmatched",
      after_ls == ["model.FCStd", "model.unmatched.FCStd"], after_ls)
s.close()

# Copy ONLY model.FCStd to a fresh folder and reopen: everything survives + floor rebuild still works
alone_dir = os.path.join(tmp, "legacy-alone")
shutil.rmtree(alone_dir, ignore_errors=True)
os.makedirs(alone_dir)
alone_p = os.path.join(alone_dir, "model.FCStd")
shutil.copy2(upg_p, alone_p)
s = Session(alone_p)
check("reopening upgraded .FCStd alone keeps bodies, WorkshopCube, floor, dropped, reserved_ids, units",
      not s.external and s.undo_floor == 4 and len(s.applied) == 6 and len(s.dropped) == 2
      and res99 in s.ids.reserved and s.units == "in-frac:1/16"
      and s.doc.getObject("WorkshopCube") is not None and len(s.model.bodies()) == 3,
      (s.external, s.undo_floor, len(s.applied), len(s.dropped), res99 in s.ids.reserved, s.units))
more_u = []
for n in range(20, 32):
    more_u += board(n)
s.sync(kept_to_floor + more_u)
how_u2, _ = s.sync(kept_to_floor)
check("upgraded .FCStd alone still rebuilds > 20 steps from embedded floor copy",
      how_u2 == "rebuilt" and s.doc.getObject("WorkshopCube") is not None and len(s.model.bodies()) == 3,
      (how_u2, len(s.model.bodies())))
s.close()

# Legacy journal with mismatched sha opens external on first open, then removes old journal on save
mm_dir = os.path.join(tmp, "legacy-mismatch")
shutil.rmtree(mm_dir, ignore_errors=True)
shutil.copytree(LEGACY_FIXTURE, mm_dir)
mm_p = os.path.join(mm_dir, "model.FCStd")
mm_jp = os.path.join(mm_dir, "model.shopsketch.json")
with open(mm_jp) as f:
    mm_j = json.load(f)
mm_j["file_sha256"] = "0" * 64
with open(mm_jp, "w") as f:
    json.dump(mm_j, f)
s = Session(mm_p)
check("legacy journal with mismatched sha opens external on first open",
      s.external and s.undo_floor == 26, (s.external, s.undo_floor))
s.save()
check("... and first save removes the old journal and floor file",
      os.listdir(mm_dir) == ["model.FCStd"], os.listdir(mm_dir))
s.close()

# ---------- T125: one-shot drawing export, clean Label / no .FCBak, GLB write skipping ----------
import xml.etree.ElementTree as ET
import zipfile


def doc_label(fcstd_path):
    with zipfile.ZipFile(fcstd_path) as z:
        root = ET.fromstring(z.read("Document.xml"))
    prop = root.find("./Properties/Property[@name='Label']/String")
    return prop.get("value") if prop is not None else None


def fcbak_files(folder):
    return [n for n in os.listdir(folder) if ".FCBak" in n]


prefs = App.ParamGet("User parameter:BaseApp/Preferences/Document")
had_pref = "CreateBackupFiles" in prefs.GetBools()
orig_pref = prefs.GetBool("CreateBackupFiles", True)

# 1. Explicit drawing export writes views.json, leaves no TechDraw in model.FCStd, clears s.drawing, clean Label & no .FCBak
p = model("drawing-oneshot")
folder = os.path.dirname(p)
out = os.path.join(folder, "out")
os.makedirs(out, exist_ok=True)
prefs.SetBool("CreateBackupFiles", True)
s = Session(p, fresh=True)
ops = board(1)
s.sync(ops)
s.save(out)
check("ordinary autosave sets Document.xml Label to the real model stem and leaves zero .FCBak files",
      doc_label(p) == "m" and fcbak_files(folder) == [], (doc_label(p), fcbak_files(folder)))
s.drawing = True
s.save(out)
views_path = os.path.join(out, "views.json")
with zipfile.ZipFile(p) as z:
    xml_after_draw = z.read("Document.xml").decode()
check("explicit drawing export writes views.json, embeds no TechDraw in model.FCStd, and resets drawing=False",
      os.path.exists(views_path) and "Front" in json.load(open(views_path))
      and "TechDraw" not in xml_after_draw and not s.drawing
      and doc_label(p) == "m" and fcbak_files(folder) == []
      and not os.path.exists(saving_path(p)),
      (os.path.exists(views_path), "TechDraw" in xml_after_draw, s.drawing, doc_label(p), fcbak_files(folder)))
os.remove(views_path)
ops += board(2)
s.sync(ops)
s.save(out)
check("subsequent ordinary autosave after drawing export does not re-run TechDraw",
      not os.path.exists(views_path) and fcbak_files(folder) == [], (os.path.exists(views_path), fcbak_files(folder)))
s.close()

# 2. Reopening a FreeCAD-created .FCStd containing TechDraw strips it, leaves s.drawing=False, no .FCBak on next save
p = model("drawing-reopen")
folder = os.path.dirname(p)
out = os.path.join(folder, "out")
os.makedirs(out, exist_ok=True)
s = Session(p, fresh=True)
ops = board(1)
s.sync(ops)
s.save(out)
s.close()
d = App.openDocument(p)
S.add_drawing_page(d, [o for o in d.Objects if getattr(o, "SSRole", None) == "body"])
d.save()
App.closeDocument(d.Name)
for n in fcbak_files(folder):
    os.remove(os.path.join(folder, n))  # d.save() was FreeCAD's own save with backups on
s = Session(p)
check("reopening a .FCStd with a TechDraw page strips it and leaves drawing=False",
      not [o for o in s.doc.Objects if o.TypeId.startswith("TechDraw")] and not s.drawing, s.drawing)
s.sync(ops + board(2))
s.save(out)
check("autosave after reopening a TechDraw file writes no views.json and no .FCBak files",
      not os.path.exists(os.path.join(out, "views.json")) and fcbak_files(folder) == [], fcbak_files(folder))
s.close()

# 3. Failed save during explicit drawing export rolls back rev/Meta and keeps drawing=True for retry
p = model("drawing-retry")
folder = os.path.dirname(p)
out = os.path.join(folder, "out")
os.makedirs(out, exist_ok=True)
s = Session(p, fresh=True)
s.sync(board(1))
s.save(out)
s.drawing = True
real = os.replace


def fail_replace(src, dst):
    if os.path.abspath(dst) == os.path.abspath(p):
        raise OSError("disk full")
    real(src, dst)


S.os.replace = fail_replace
try:
    s.save(out)
    raised = False
except OSError:
    raised = True
finally:
    S.os.replace = real
views_path = os.path.join(out, "views.json")
if os.path.exists(views_path):
    os.remove(views_path)
check("failed save during drawing export rolls back rev/Meta and keeps drawing=True",
      raised and s.rev == 1 and s.doc.Meta.get("ShopSketchRev") == "1" and s.drawing,
      (raised, s.rev, s.doc.Meta.get("ShopSketchRev"), s.drawing))
s.save(out)
check("retry after failed drawing export writes views.json and clears drawing=False",
      s.rev == 2 and os.path.exists(views_path) and not s.drawing,
      (s.rev, os.path.exists(views_path), s.drawing))
s.close()

# 4. GLB write skipping on pure set_units vs refresh on geometry/material edit or missing file
p = model("glb-skip")
folder = os.path.dirname(p)
out = os.path.join(folder, "out")
os.makedirs(out, exist_ok=True)
glb_calls = [0]
real_write_glb = S.write_glb


def count_glb(m, path):
    glb_calls[0] += 1
    return real_write_glb(m, path)


S.write_glb = count_glb
try:
    s = Session(p, fresh=True)
    ops = board(1)
    s.sync(ops)
    s.save(out)
    glb_path = os.path.join(out, "model.glb")
    check("initial save writes model.glb", glb_calls[0] == 1 and os.path.exists(glb_path), glb_calls[0])
    s.set_units("in-frac:1/16")
    s.save(out)
    check("pure set_units save skips rewriting existing model.glb", glb_calls[0] == 1, glb_calls[0])
    os.remove(glb_path)
    s.set_units("mm:1")
    s.save(out)
    check("save rewrites model.glb when it is missing", glb_calls[0] == 2 and os.path.exists(glb_path), glb_calls[0])
    ops = ops + [{"id": "sm1", "type": "set_material", "targets": ["b1"], "material": "white-oak"}]
    s.sync(ops)
    s.save(out)
    check("save after geometry/material edit rewrites model.glb", glb_calls[0] == 3, glb_calls[0])
    s.close()
finally:
    S.write_glb = real_write_glb

# 5. Backup preference (CreateBackupFiles) is restored after every save and untouched on import (A41, T148)
import importlib

try:
    p = model("backup-on")
    folder = os.path.dirname(p)
    prefs.SetBool("CreateBackupFiles", True)
    s = Session(p, fresh=True)
    ops = board(1)
    s.sync(ops)
    s.save()
    s.sync(ops + board(2))
    s.save()
    check("a save leaves the backup preference as it found it (on)",
          prefs.GetBool("CreateBackupFiles", False) is True and fcbak_files(folder) == [],
          (prefs.GetBool("CreateBackupFiles", False), fcbak_files(folder)))
    s.close()

    p = model("backup-off")
    prefs.SetBool("CreateBackupFiles", False)
    s = Session(p, fresh=True)
    s.sync(board(1))
    s.save()
    check("a save leaves the backup preference as it found it (off)",
          "CreateBackupFiles" in prefs.GetBools() and prefs.GetBool("CreateBackupFiles", True) is False,
          ("CreateBackupFiles" in prefs.GetBools(), prefs.GetBool("CreateBackupFiles", True)))
    s.close()

    p = model("backup-readonly")
    folder = os.path.dirname(p)
    s = Session(p, fresh=True)
    s.sync(board(1))
    prefs.SetBool("CreateBackupFiles", True)
    os.chmod(folder, 0o555)
    raised_ro = False
    try:
        s.save()
    except PermissionError:
        raised_ro = True
    finally:
        os.chmod(folder, 0o755)
    check("a save that fails still puts the preference back",
          raised_ro and prefs.GetBool("CreateBackupFiles", False) is True,
          (raised_ro, prefs.GetBool("CreateBackupFiles", False)))
    s.close()

    prefs.SetBool("CreateBackupFiles", True)
    importlib.reload(S)
    check("importing session no longer changes the preference",
          prefs.GetBool("CreateBackupFiles", False) is True,
          prefs.GetBool("CreateBackupFiles", False))
finally:
    if had_pref:
        prefs.SetBool("CreateBackupFiles", orig_pref)
    else:
        prefs.RemBool("CreateBackupFiles")

print(f"\nGENERATION TESTS: {R[0]} passed, {R[1]} failed", flush=True)
sys.exit(1 if R[1] else 0)
