"""The model and its journal saved as one generation (A32, T40): the new pair under the .saving names, the current
one kept as .prev, then renamed into place. Opening finishes identifiable interrupted saves (A37), falling back
to .prev only for missing/unreadable models. Newer FreeCAD work stays external (A25), with no recovery.

  freecadcmd worker/test_generations.py        (TESTDIR=<folder> for its files)"""
import json
import os
import shutil
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import FreeCAD as App
import session as S
from serve import open_reply
from session import Session, generation, read_journal, sha256

tmp = os.environ.get("TESTDIR", "/tmp/generations_test")
os.makedirs(tmp, exist_ok=True)
R = [0, 0]


def check(name, cond, detail=""):
    R[0 if cond else 1] += 1
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"), flush=True)


def board(n, w=200):
    return [{"id": f"r{n}", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, n * 300, 0]}, "size": [w, 100]},
            {"id": f"pp{n}", "type": "push_pull", "target": {"rect": f"r{n}"}, "distance": 18, "body": f"b{n}"}]


def model(name):
    folder = os.path.join(tmp, name)
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)
    return os.path.join(folder, "m.FCStd")


def whole(g, f, j):
    jj = read_journal(g[j])
    return os.path.exists(g[f]) and jj is not None and jj["file_sha256"] == sha256(g[f])


def rev_of(g, j):
    return int(read_journal(g[j])["rev"])


class Crash(BaseException):
    """A crash part way through a save: not an Exception, so save()'s clean-up doesn't run (a real crash wouldn't)."""


def saved_until(s, dst_key):
    """Save, stopping (as a crash would) just before the os.replace that writes g[dst_key]."""
    g = generation(s.path)
    real = os.replace

    def replace(src, dst):
        if os.path.abspath(dst) == os.path.abspath(g[dst_key]):
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
    """A model saved at revs 1, 2, 3 (one more board each), then closed."""
    s = Session(path)
    ops = []
    for n in range(1, 4):
        ops += board(n)
        s.sync(ops)
        s.save()
    return s, ops


# ---------- a normal save leaves both pairs, each whole ----------
p = model("normal")
s, ops = saved_three(p)
g = generation(p)
check("a normal save: the current pair matches (journal names the file's sha256)", whole(g, "file", "journal")
      and rev_of(g, "journal") == 3 == s.rev, (s.rev,))
check("... and the pair before it is kept as .prev, whole", whole(g, "prev_file", "prev_journal")
      and rev_of(g, "prev_journal") == 2)
check("... and nothing is left under the .saving names",
      not os.path.exists(g["saving_file"]) and not os.path.exists(g["saving_journal"]))
s.close()
s = Session(p)
check("reopening a whole pair: not external, nothing recovered", not s.external and s.recovered is None
      and s.rev == 3 and len(s.applied) == 6, (s.external, s.recovered, s.rev))
check("... and the open reply has no recovered field", "recovered" not in open_reply(s, 1))
s.close()

# ---------- a crash after the .FCStd rename, before the journal's: the whole new pair is finished ----------
p = model("after-file")
s, ops = saved_three(p)
ops += board(4)
s.sync(ops)
saved_until(s, "journal")
s.close()
g = generation(p)
check("crash after the file's rename: the file is rev 4, the journal still rev 3",
      S.file_rev(g["file"]) == 4 and rev_of(g, "journal") == 3 and whole(g, "file", "saving_journal"))
s = Session(p)
check("... opening finishes the save: the new pair (rev 4), reported", s.recovered is not None
      and s.recovered["from"] == "new" and s.recovered["rev"] == 4 and s.rev == 4 and len(s.applied) == 8, s.recovered)
check("... and it isn't external: undo reaches back as before", not s.external and s.undo_floor == 0)
check("... the file and journal now match", whole(g, "file", "journal"))
check("... the .prev pair was left alone (rev 3)", whole(g, "prev_file", "prev_journal") and rev_of(g, "prev_journal") == 3)
r = open_reply(s, 7)
check("the open reply carries recovered {from, rev, why}", r.get("recovered", {}).get("rev") == 4
      and r["recovered"]["from"] == "new" and "didn't match" in r["recovered"]["why"], r.get("recovered"))
check("... once: the next open of the same session doesn't", "recovered" not in open_reply(s, 8))
s.close()

# ---------- the same crash with the new journal lost: preserve the newest model ----------
p = model("prev")
s, ops = saved_three(p)
ops += board(4)
s.sync(ops)
saved_until(s, "journal")
s.close()
g = generation(p)
os.remove(g["saving_journal"])
s = Session(p)
check("crash after the file's rename, new journal lost: rev 4 opens external with the undo floor",
      s.recovered is None and s.external and s.rev == 4 and s.undo_floor == 6
      and len(s.model.bodies()) == 4, (s.recovered, s.rev, s.undo_floor))
check("... the newest model is left in place, nothing set aside", not os.path.exists(g["unmatched_file"])
      and S.file_rev(p) == 4)
check("... and the .prev pair is still there", whole(g, "prev_file", "prev_journal"))
s.close()

# ---------- a crash after the .prev pair is kept, before any rename ----------
p = model("before-rename")
s, ops = saved_three(p)
ops += board(4)
s.sync(ops)
saved_until(s, "file")
s.close()
g = generation(p)
s = Session(p)
check("crash before the renames: the file and journal still match (rev 3); nothing to recover",
      s.recovered is None and s.rev == 3 and not s.external, (s.recovered, s.rev))
s.close()

# ---------- the file missing (a crash with only the new and .prev pairs) ----------
p = model("missing-file")
s, ops = saved_three(p)
ops += board(4)
s.sync(ops)
saved_until(s, "file")
s.close()
g = generation(p)
os.remove(g["file"])
s = Session(p)
check("the file missing: the newest whole pair (the new one, rev 4) is put in place", s.recovered is not None
      and s.recovered["rev"] == 4 and s.rev == 4 and whole(g, "file", "journal")
      and "missing" in s.recovered["why"], s.recovered)
s.close()

# ---------- a missing journal ----------
p = model("missing-journal")
s, ops = saved_three(p)
s.close()
g = generation(p)
os.remove(g["journal"])
s = Session(p)
check("a missing journal never replaces a readable model with .prev", s.recovered is None and s.external
      and s.rev == 3 and len(s.model.bodies()) == 3, (s.recovered, s.rev))
check("... the rev 3 file stays in place", not os.path.exists(g["unmatched_file"]) and S.file_rev(p) == 3)
s.close()
p = model("no-journal-at-all")
s = Session(p)
s.sync(board(1))
s.save()
s.close()
g = generation(p)
os.remove(g["journal"])
s = Session(p)
check("a missing journal and no .prev pair: opens external, as before", s.recovered is None and s.external)
s.close()

# ---------- a file FreeCAD changed stays external, with no recovery ----------
p = model("freecad-edit")
s, ops = saved_three(p)
s.close()
g = generation(p)
d = App.openDocument(p)
d.addObject("Part::Box", "FromFreeCAD")
d.recompute()
d.save()
App.closeDocument(d.Name)
before = sha256(p)
s = Session(p)
check("a file changed in FreeCAD (same ShopSketchRev): external, nothing recovered", s.external and s.recovered is None
      and s.rev == 3 and s.undo_floor == 6, (s.external, s.recovered, s.rev, s.undo_floor))
check("... and the file is left as FreeCAD saved it, nothing set aside", sha256(p) == before
      and not os.path.exists(g["unmatched_file"]))
check("... and FreeCAD's save didn't change the .prev pair (it's a hard link to the old file: FreeCAD must not "
      "write in place)", whole(g, "prev_file", "prev_journal"))
s.close()

# ---------- FreeCAD saved the revision it opened while Shop Sketch was closed ----------
p = model("freecad-older-rev")
s, ops = saved_three(p)
s.close()
g = generation(p)
# The previous file represents the revision FreeCAD had opened before our last save.
d = App.openDocument(g["prev_file"])
d.addObject("Part::Box", "FromFreeCAD")
d.recompute()
d.saveAs(p)
App.closeDocument(d.Name)
before = sha256(p)
s = Session(p)
check("FreeCAD's newer save with an older revision opens as outside work", s.external and s.recovered is None
      and s.rev == 2 and s.undo_floor == 6 and s.doc.getObject("FromFreeCAD") is not None)
check("... no newer work is moved aside or replaced", sha256(p) == before
      and not os.path.exists(g["unmatched_file"]))
s.close()

# ---------- missing or corrupt main file, with only the .prev pair available ----------
for broken in ("missing", "unreadable"):
    p = model("fallback-" + broken)
    s, ops = saved_three(p)
    s.close()
    g = generation(p)
    os.remove(p)
    if broken == "unreadable":
        with open(p, "wb") as f:
            f.write(b"interrupted zip")
    s = Session(p)
    check(broken + " main file restores .prev", s.recovered is not None
          and s.recovered["from"] == "prev" and s.rev == 2 and not s.external
          and whole(g, "file", "journal") and broken in s.recovered["why"], s.recovered)
    check(broken + " main file preserves displaced bytes", broken == "missing"
          or open(g["unmatched_file"], "rb").read() == b"interrupted zip")
    s.close()

# ---------- a whole staged pair can finish a one-revision interrupted save ----------
for newer_main in (False, True):
    p = model("staged-" + str(newer_main))
    s, ops = saved_three(p)
    s.sync(ops + board(4))
    saved_until(s, "journal")
    s.close()
    g = generation(p)
    shutil.copy2(p, g["saving_file"])
    main_time = os.stat(p).st_mtime_ns
    staged_time = main_time - 1000000000 if newer_main else main_time + 1000000000
    os.utime(g["saving_file"], ns=(staged_time, staged_time))
    # Same revision, different bytes: only a whole staged pair plus rev+1 identifies this save.
    d = App.openDocument(p)
    d.addObject("Part::Box", "OtherBytes")
    d.recompute()
    d.save()
    App.closeDocument(d.Name)
    os.utime(p, ns=(main_time, main_time))
    before = sha256(p)
    s = Session(p)
    if newer_main:
        check("an older staged pair never replaces a newer main file", s.recovered is None and s.external
              and sha256(p) == before and s.doc.getObject("OtherBytes") is not None)
    else:
        check("rev+1 with a newer whole staged pair finishes our save", s.recovered is not None
              and s.recovered["from"] == "new" and s.rev == 4 and not s.external
              and whole(g, "file", "journal"), s.recovered)
    s.close()

# ---------- a failed save keeps today's behaviour (T79) ----------
p = model("failed")
s, ops = saved_three(p)
g = generation(p)
real = os.replace


def failing(src, dst):
    if os.path.abspath(dst) == os.path.abspath(g["file"]):
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
check("a failed save raises, holds the revision back and cleans up the .saving files", raised and s.rev == 3
      and not os.path.exists(g["saving_file"]) and not os.path.exists(g["saving_journal"]), s.rev)
check("... the current pair is untouched", whole(g, "file", "journal") and rev_of(g, "journal") == 3)
s.save()
check("... and the retry saves it", s.rev == 4 and whole(g, "file", "journal") and rev_of(g, "prev_journal") == 3)
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


# 1. Explicit drawing export writes views.json, leaves no TechDraw in model.FCStd, clears s.drawing, clean Label & no .FCBak
p = model("drawing-oneshot")
folder = os.path.dirname(p)
out = os.path.join(folder, "out")
os.makedirs(out, exist_ok=True)
App.ParamGet("User parameter:BaseApp/Preferences/Document").SetBool("CreateBackupFiles", True)
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
      and not os.path.exists(generation(p)["saving_file"]),
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
g = generation(p)
s.drawing = True
real = os.replace


def fail_replace(src, dst):
    if os.path.abspath(dst) == os.path.abspath(g["file"]):
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

print(f"\nGENERATION TESTS: {R[0]} passed, {R[1]} failed", flush=True)
sys.exit(1 if R[1] else 0)
