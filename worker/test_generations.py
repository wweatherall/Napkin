"""The model and its journal saved as one generation (A32, T40): the new pair under the .saving names, the current
one kept as .prev, then renamed into place; opening finds the newest whole pair after a save that stopped part
way, and says so. A file FreeCAD changed is still external (A25), with no recovery.

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

# ---------- the same crash with the new journal lost: the .prev pair is opened ----------
p = model("prev")
s, ops = saved_three(p)
ops += board(4)
s.sync(ops)
saved_until(s, "journal")
s.close()
g = generation(p)
os.remove(g["saving_journal"])
s = Session(p)
check("crash after the file's rename, new journal lost: the last whole pair (rev 3) opens, reported",
      s.recovered is not None and s.recovered["from"] == "prev" and s.recovered["rev"] == 3 and s.rev == 3
      and len(s.applied) == 6 and not s.external, s.recovered)
check("... the unmatched rev 4 file is kept aside, not deleted", os.path.exists(g["unmatched_file"])
      and S.file_rev(g["unmatched_file"]) == 4)
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
check("a missing journal with a whole .prev pair: the .prev pair (rev 2) opens, reported",
      s.recovered is not None and s.recovered["from"] == "prev" and s.recovered["rev"] == 2 and s.rev == 2
      and len(s.applied) == 4 and "journal was missing" in s.recovered["why"], s.recovered)
check("... the rev 3 file is kept aside", os.path.exists(g["unmatched_file"]) and S.file_rev(g["unmatched_file"]) == 3)
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

print(f"\nGENERATION TESTS: {R[0]} passed, {R[1]} failed", flush=True)
sys.exit(1 if R[1] else 0)
