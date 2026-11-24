# runner: python3 (it starts freecadcmd itself)
"""Outside saves (T64, A36): FreeCAD saves the open model; the worker notices without a sync, holds the model (no
autosave over FreeCAD's file), tells the window, and reloads it or keeps both, as the window says. Covers: nothing
pending (reload, changed boards, undo floor in this session and the journal); actions that landed in time (held,
dropped into the journal); 'Use FreeCAD's version' and 'Keep Shop Sketch's' (files on disk, the copy-aside name);
a flush of a held model keeps both; a FreeCAD save of an older revision isn't taken for a broken save by a new
worker (the journal's outside_sha256).
  python3 worker/test_outside_save.py   (TESTDIR=<folder> for its files; FREECAD=<freecadcmd> to override)"""
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from test_link import (FC, Checks, Window, board_ops, freecad_save,
                       fresh_model as _fresh_model, start_worker, sync)

tmp = os.path.abspath(os.environ.get("TESTDIR") or tempfile.mkdtemp(prefix="shopsketch-outside-"))
os.makedirs(tmp, exist_ok=True)
checks = Checks("OUTSIDE SAVE")
check = checks.check

READ_LABEL = os.path.join(tmp, "freecad_label.py")
with open(READ_LABEL, "w") as f:
    f.write('''import os, FreeCAD as App
doc = App.openDocument(os.environ["READ_MODEL"])
print("MODEL LABEL: " + doc.Label, flush=True)
App.closeDocument(doc.Name)
''')


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def journal(model):
    return json.load(open(os.path.splitext(model)[0] + ".shopsketch.json"))


def second(w):
    return board_ops(w, rid="r2", bid="b2", origin=(0, 300, 0))


def fresh_model(name):
    return _fresh_model(tmp, name)


def thickness(outdir, bid):
    for b in json.load(open(os.path.join(outdir, "bodies.json"))):
        if b["id"] == bid:
            return round(b["world_bbox"][5] - b["world_bbox"][2], 3)
    return None


worker = start_worker(tmp)
w = Window(worker.port)


def ask(req, want):
    return w.ask(req, want)


def opened(model):
    return ask({"cmd": "open", "model": model, "fresh": True}, "open")


def wait_outside(model, timeout=10):
    """The worker's outside_save event for this model (others are kept in w.extra and counted as stray)."""
    return w.wait("outside_save", timeout=timeout, model=model)


def stray():
    return [m for m in w.extra if m.get("cmd") == "outside_save"]


try:
    # 1. Nothing pending: reload, the changed board, undo stops at the FreeCAD change.
    m1 = fresh_model("quiet")
    out1 = m1 + "-out"
    opened(m1)
    ops = board_ops(300)
    sync(w, m1, ops)
    ask({"cmd": "flush", "model": m1}, "flush")
    freecad_save(m1)
    fc_sha = sha(m1)
    ev = wait_outside(m1)
    check("an outside save is noticed without a sync, and the window told", ev is not None and ev["model"] == m1, ev)
    check("with nothing unsaved it says so, and gives the file's revision", ev and ev["unsaved"] is False and ev["rev"] == 1, ev)
    r = ask({"cmd": "reload", "model": m1, "outdir": out1}, "reload")
    check("reload answers with the model's ops and the board FreeCAD changed",
          r and r["ok"] and r["changed"] == ["b1"] and len(r["ops"]) == 2 and r["dropped"] == [], r)
    check("the reloaded board has FreeCAD's thickness (18 + 12)", thickness(out1, "b1") == 30.0, thickness(out1, "b1"))
    check("undo stops at the FreeCAD change (undo_floor = 2)", r and r["undo_floor"] == 2, r and r["undo_floor"])
    check("reloading leaves FreeCAD's file as it is", sha(m1) == fc_sha)
    j = journal(m1)
    check("the journal now names FreeCAD's file, with the floor", j["file_sha256"] == fc_sha and j["floor"] == 2, j.get("floor"))
    bad = sync(w, m1, ops[:1])
    check("a sync taking back an op below the floor is refused", bad and not bad["ok"] and "FreeCAD" in bad["error"], bad)
    sync(w, m1, ops + second(200))
    ask({"cmd": "flush", "model": m1}, "flush")
    label_read = subprocess.run([FC, READ_LABEL], env=dict(os.environ, READ_MODEL=m1),
                                capture_output=True, text=True, timeout=120)
    expected_label = os.path.splitext(os.path.basename(m1))[0]
    # FreeCAD normalizes the label on open, so check what Shop Sketch saved as well.
    with zipfile.ZipFile(m1) as archive:
        document_xml = ET.fromstring(archive.read("Document.xml"))
        saved_label = document_xml.find("./Properties/Property[@name='Label']/String").get("value")
    check("FreeCAD reopens the saved reload with the model's file stem as its label",
          label_read.returncode == 0 and f"MODEL LABEL: {expected_label}" in label_read.stdout.splitlines()
          and saved_label == expected_label, f"saved label: {saved_label!r}")
    j = journal(m1)
    check("a later save keeps the floor in the journal", j["floor"] == 2 and len(j["ops"]) == 4, (j.get("floor"), len(j["ops"])))
    check("and no outside save is reported for our own save", wait_outside(m1, 1.0) is None)

    # 2. Actions pending that land: held (no autosave over FreeCAD's file), then the reload drops them into the journal.
    m2 = fresh_model("busy")
    out2 = m2 + "-out"
    opened(m2)
    sync(w, m2, board_ops(300))
    ask({"cmd": "flush", "model": m2}, "flush")
    # Prepare FreeCAD's save away from the watched path. Stop the worker at an acknowledged
    # process boundary, queue the actions and publish the save, then resume. The watch's first
    # look settles the new file; the queued sync lands before its next look reports unsaved.
    edit = m2 + ".edited.FCStd"
    shutil.copy2(m2, edit)
    freecad_save(edit)
    fc_sha = sha(edit)
    os.kill(worker.proc.pid, signal.SIGSTOP)
    _, stopped = os.waitpid(worker.proc.pid, os.WUNTRACED)
    assert os.WIFSTOPPED(stopped), stopped
    try:
        os.makedirs(out2, exist_ok=True)
        w.send({"cmd": "sync", "model": m2, "outdir": out2,
                "oplog": {"format": "oplog/0.1", "units": "mm", "ops": board_ops(300) + second(200)}})
        os.replace(edit, m2)
    finally:
        os.kill(worker.proc.pid, signal.SIGCONT)
    landed = w.wait("sync")
    check("the pending actions land before the outside-save notification", landed and landed["ok"], landed)
    ev = wait_outside(m2)
    check("an outside save with actions unsaved says so", ev and ev["unsaved"] is True, ev)
    time.sleep(1.0)                                      # four autosave periods
    check("no autosave writes over the outside save meanwhile", sha(m2) == fc_sha)
    r = ask({"cmd": "reload", "model": m2, "outdir": out2}, "reload")
    check("the reload takes the actions FreeCAD's save didn't have out of the list",
          r and [o["id"] for o in r["ops"]] == ["r1", "pp1"] and [o["id"] for o in r["dropped"]] == ["r2", "pp2"], r)
    j = journal(m2)
    check("they stay in the journal as dropped, with the revision they came after",
          [d["op"]["id"] for d in j["dropped"]] == ["r2", "pp2"] and j["dropped"][0]["after_rev"] == 1, j.get("dropped"))
    check("b2 is gone from the boards and b1 changed", r["changed"] == ["b1"] and r["removed"] == ["b2"], r)

    # 3. 'Keep Shop Sketch's': FreeCAD's file aside first, then ours over it. Both survive on disk.
    m3 = fresh_model("mine")
    out3 = m3 + "-out"
    opened(m3)
    sync(w, m3, board_ops(300))
    ask({"cmd": "flush", "model": m3}, "flush")
    freecad_save(m3)
    fc_sha = sha(m3)
    sync(w, m3, board_ops(300) + second(200))
    wait_outside(m3)
    k = ask({"cmd": "keep_mine", "model": m3, "outdir": out3}, "keep_mine")
    aside = (k or {}).get("aside") or ""
    check("Keep Shop Sketch's copies FreeCAD's file aside as <model>.freecad-<time>.FCStd",
          k and k["ok"] and re.fullmatch(r"mine\.freecad-\d{8}-\d{6}\.FCStd", os.path.basename(aside)) is not None, k)
    check("the copy is FreeCAD's save, byte for byte", os.path.exists(aside) and sha(aside) == fc_sha)
    j = journal(m3)
    check("then Shop Sketch's version is the model, with every action",
          sha(m3) != fc_sha and j["file_sha256"] == sha(m3) and len(j["ops"]) == 4 and j.get("dropped") == [], len(j["ops"]))
    sync(w, m3, board_ops(300) + second(220))
    ask({"cmd": "flush", "model": m3}, "flush")
    check("autosave carries on after the choice", journal(m3)["ops"][2]["size"] == [220, 100])
    check("one choice, one copy: no second outside save after ours", stray() == [] and
          len([n for n in os.listdir(os.path.dirname(m3)) if ".freecad-" in n]) == 1, stray())

    # 4. A flush (closing) while held keeps both the same way.
    m4 = fresh_model("closing")
    opened(m4)
    sync(w, m4, board_ops(300))
    ask({"cmd": "flush", "model": m4}, "flush")
    freecad_save(m4)
    fc_sha = sha(m4)
    sync(w, m4, board_ops(300) + second(200))
    wait_outside(m4)
    fl = ask({"cmd": "flush", "model": m4}, "flush")
    asides = [s.get("aside") for s in (fl or {}).get("saved", [])]
    check("a flush of a held model copies FreeCAD's save aside before saving ours",
          fl and fl["ok"] and asides and asides[0] and sha(asides[0]) == fc_sha and len(journal(m4)["ops"]) == 4, fl)

    # 5. FreeCAD saves an older revision (it opened rev 1, Shop Sketch saved rev 2 since); the worker stops before the
    #    reload. A new worker opens FreeCAD's file as an outside edit, not as a save of ours that stopped part way.
    m5 = fresh_model("older")
    opened(m5)
    sync(w, m5, board_ops(300))
    ask({"cmd": "flush", "model": m5}, "flush")
    rev1 = m5 + ".rev1"
    shutil.copy2(m5, rev1)
    sync(w, m5, board_ops(300) + second(200))
    ask({"cmd": "flush", "model": m5}, "flush")
    freecad_save(rev1)
    os.replace(rev1, m5)                               # FreeCAD's save of the revision it had open
    fc_sha = sha(m5)
    ev = wait_outside(m5)
    check("an outside save of an older revision is noticed", ev and ev["rev"] == 1, ev)
    w.ask({"cmd": "quit"}, "quit")
    worker.proc.wait(30)
    w.drop()
    worker = worker.restart()
    w = Window(worker.port)
    o = ask({"cmd": "open", "model": m5}, "open")
    check("a new worker opens it as FreeCAD's (external, nothing recovered), the file untouched",
          o and o["external"] and "recovered" not in o and sha(m5) == fc_sha
          and not os.path.exists(os.path.splitext(m5)[0] + ".unmatched.FCStd"), o)
    ask({"cmd": "bye"}, "bye")                         # the worker lets the window go and stops by itself
    worker.proc.wait(30)
    w.drop()

    # 6. In one worker, the same older-revision save reloads with what came after rev 1 dropped.
    worker = worker.restart()
    w = Window(worker.port)
    m6 = fresh_model("older_live")
    opened(m6)
    sync(w, m6, board_ops(300))
    ask({"cmd": "flush", "model": m6}, "flush")
    rev1 = m6 + ".rev1"
    shutil.copy2(m6, rev1)
    sync(w, m6, board_ops(300) + second(200))
    ask({"cmd": "flush", "model": m6}, "flush")
    freecad_save(rev1)
    os.replace(rev1, m6)
    wait_outside(m6)
    r = ask({"cmd": "reload", "model": m6, "outdir": m6 + "-out"}, "reload")
    check("the actions saved after the revision FreeCAD opened are dropped",
          r and [o["id"] for o in r["ops"]] == ["r1", "pp1"] and [o["id"] for o in r["dropped"]] == ["r2", "pp2"], r)
    check("the reload's rev is the session's (2), not the older file's", r and r["rev"] == 2, r and r.get("rev"))

    # 7. An undo since the revision FreeCAD opened: the reload keeps that revision's ops (the undone one is back), and
    #    only what's new since counts as dropped.
    m7 = fresh_model("undone")
    opened(m7)
    sync(w, m7, board_ops(300) + second(200))
    ask({"cmd": "flush", "model": m7}, "flush")
    rev1 = m7 + ".rev1"
    shutil.copy2(m7, rev1)
    third = board_ops(150, rid="r3", bid="b3", origin=(0, 600, 0))
    sync(w, m7, board_ops(300) + third)                # b2 undone, b3 made
    ask({"cmd": "flush", "model": m7}, "flush")
    os.replace(rev1, m7)
    wait_outside(m7)
    r = ask({"cmd": "reload", "model": m7, "outdir": m7 + "-out"}, "reload")
    check("after an undo the reload keeps the revision's own ops and drops only the newer ones",
          r and [o["id"] for o in r["ops"]] == ["r1", "pp1", "r2", "pp2"] and [o["id"] for o in r["dropped"]] == ["r3", "pp3"]
          and r["changed"] == ["b2"] and r["removed"] == ["b3"], r)

    # 7b. A rejected action in the saved revision (H092 finding 7): a reload keeps only the ops that worked, as opening
    #     and the .prev journal do, so the window isn't left with a failed op below the undo floor.
    m7b = fresh_model("rejected")
    opened(m7b)
    bad = {"id": "bad1", "type": "push_pull", "target": {"rect": "r1"}, "distance": 0}
    sync(w, m7b, board_ops(300) + [bad])
    ask({"cmd": "flush", "model": m7b}, "flush")
    freecad_save(m7b)
    wait_outside(m7b)
    r = ask({"cmd": "reload", "model": m7b, "outdir": m7b + "-out"}, "reload")
    check("a reload of a revision with a rejected action keeps only the ops that worked",
          r and [o["id"] for o in r["ops"]] == ["r1", "pp1"] and r["undo_floor"] == 2 and r["dropped"] == [], r)

    # An unreadable outside save leaves the live document and its undo floor intact. The window can still keep ours.
    broken = fresh_model("unreadable")
    opened(broken)
    ops = board_ops(300)
    sync(w, broken, ops)
    ask({"cmd": "flush", "model": broken}, "flush")
    freecad_save(broken)
    wait_outside(broken)
    live_out = broken + "-out"
    first_reload = ask({"cmd": "reload", "model": broken, "outdir": live_out}, "reload")
    check("the previous outside edit sets a floor and changes the live board",
          first_reload and first_reload["ok"] and first_reload["undo_floor"] == 2 and thickness(live_out, "b1") == 30.0,
          first_reload)
    floor = os.path.splitext(broken)[0] + ".floor.FCStd"
    floor_sha = sha(floor)
    freecad_save(broken)
    held_event = wait_outside(broken)
    ops += second(200)
    sync(w, broken, ops)
    with open(broken + ".invalid", "wb") as f:
        f.write(b"invalid FCStd")
    os.replace(broken + ".invalid", broken)
    broken_sha = sha(broken)
    held_journal = journal(broken)
    r = ask({"cmd": "reload", "model": broken, "outdir": live_out}, "reload")
    check("an unreadable outside save fails reload while the model is held", held_event and r and not r["ok"], r)
    check("failed reload leaves the floor, journal, and outside file intact",
          sha(floor) == floor_sha and journal(broken) == held_journal and sha(broken) == broken_sha)
    os.remove(os.path.join(live_out, "bodies.json"))
    still_live = sync(w, broken, ops, outdir=live_out)
    check("after failed reload the live document still exports both boards",
          still_live and still_live["ok"] and thickness(live_out, "b1") == 30.0 and thickness(live_out, "b2") == 18.0,
          still_live)
    k = ask({"cmd": "keep_mine", "model": broken, "outdir": live_out}, "keep_mine")
    check("after failed reload Keep Shop Sketch's copies the unreadable file aside and saves ours",
          k and k["ok"] and sha(k["aside"]) == broken_sha and journal(broken)["file_sha256"] == sha(broken)
          and journal(broken)["ops"] == ops and journal(broken)["floor"] == 2, k)

    # 8. A held model with unsaved actions whose file is then deleted: the window closing (its save keeps both, and
    #    the copy aside fails) is a failed save, not the end of the worker for every window.
    m8 = fresh_model("deleted")
    opened(m8)
    sync(w, m8, board_ops(300))
    ask({"cmd": "flush", "model": m8}, "flush")
    freecad_save(m8)
    wait_outside(m8)
    sync(w, m8, board_ops(300) + second(200))          # held: these wait, unsaved
    os.remove(m8)
    w.drop()
    time.sleep(0.5)
    check("a held model's file deleted and its window closed: the worker keeps running", worker.proc.poll() is None,
          worker.proc.poll())
    w = Window(worker.port)
    q = w.ask({"cmd": "quit", "seq": 99}, "quit")
    check("and still answers the next window", q is not None, q)
    worker.proc.wait(30)
    w.drop()

    # H098 outside-save regressions
    H098_CHECKS = [
        "after a deleted outside save fails reload, Keep Shop Sketch's still saves ours",
        "an outside save with corrupt Document.xml fails reload instead of wiping the model",
        "a reload failure while writing the floor copy leaves the live document intact",
        "a retried reload on a new worker after a crash drops post-rev ops and keeps the rev",
    ]

    worker = worker.restart()
    w = Window(worker.port)

    # 1. Deleted file while held: reload fails, then Keep Shop Sketch's still saves ours
    m_del = fresh_model("deleted_keep_mine")
    out_del = m_del + "-out"
    os.makedirs(out_del, exist_ok=True)
    opened(m_del)
    ops_del = board_ops(300)
    sync(w, m_del, ops_del)
    ask({"cmd": "flush", "model": m_del}, "flush")
    freecad_save(m_del)
    wait_outside(m_del)
    ops_del += second(200)
    sync(w, m_del, ops_del)
    os.remove(m_del)
    r_del = ask({"cmd": "reload", "model": m_del, "outdir": out_del}, "reload")
    k_del = ask({"cmd": "keep_mine", "model": m_del, "outdir": out_del}, "keep_mine")
    check(H098_CHECKS[0],
          r_del and not r_del["ok"] and k_del and k_del["ok"] and os.path.exists(m_del)
          and journal(m_del)["ops"] == ops_del, (r_del, k_del))

    # 2. Valid zip with corrupt Document.xml: reload must fail instead of wiping the model
    m_xml = fresh_model("corrupt_xml")
    out_xml = m_xml + "-out"
    os.makedirs(out_xml, exist_ok=True)
    opened(m_xml)
    sync(w, m_xml, board_ops(300))
    ask({"cmd": "flush", "model": m_xml}, "flush")
    bad_zip = m_xml + ".badxml"
    with zipfile.ZipFile(bad_zip, "w") as z:
        z.writestr("Document.xml", "<<<not xml>>>")
    os.replace(bad_zip, m_xml)
    wait_outside(m_xml)
    r_xml = ask({"cmd": "reload", "model": m_xml, "outdir": out_xml}, "reload")
    check(H098_CHECKS[1], r_xml and not r_xml["ok"], r_xml)

    # 3. Reload failure while writing the floor copy leaves the live document intact
    m_flr = fresh_model("floor_fail")
    out_flr = m_flr + "-out"
    opened(m_flr)
    ops_flr = board_ops(300)
    sync(w, m_flr, ops_flr, outdir=out_flr)
    ask({"cmd": "flush", "model": m_flr}, "flush")
    freecad_save(m_flr)
    wait_outside(m_flr)
    ops_flr += second(200)
    sync(w, m_flr, ops_flr, outdir=out_flr)
    bodies_flr = os.path.join(out_flr, "bodies.json")
    with open(bodies_flr, "rb") as f:
        live_bodies = f.read()
    flr_path = os.path.splitext(m_flr)[0] + ".floor.FCStd"
    os.mkdir(flr_path)
    r_flr = ask({"cmd": "reload", "model": m_flr, "outdir": out_flr}, "reload")
    os.rmdir(flr_path)
    with open(bodies_flr, "rb") as f:
        check("a failed floor replacement leaves the last viewport export intact",
              r_flr and not r_flr["ok"] and f.read() == live_bodies, r_flr)
    journal_path = os.path.splitext(m_flr)[0] + ".shopsketch.json"
    journal_backup = journal_path + ".test-backup"
    os.rename(journal_path, journal_backup)
    os.mkdir(journal_path)
    try:
        r_jrnl = ask({"cmd": "reload", "model": m_flr, "outdir": out_flr}, "reload")
        with open(bodies_flr, "rb") as f:
            check("a failed journal replacement keeps the last viewport export and rolls back the floor",
                  r_jrnl and not r_jrnl["ok"] and f.read() == live_bodies and not os.path.exists(flr_path), r_jrnl)
    finally:
        os.rmdir(journal_path)
        os.rename(journal_backup, journal_path)
    blocked_outdir = os.path.join(out_flr, "blocked")
    with open(blocked_outdir, "w"):
        pass
    journal_before = sha(journal_path)
    r_export = ask({"cmd": "reload", "model": m_flr, "outdir": blocked_outdir}, "reload")
    check("a failed reload export rolls back the journal and floor",
          r_export and not r_export["ok"] and sha(journal_path) == journal_before and not os.path.exists(flr_path),
          r_export)
    k_flr = ask({"cmd": "keep_mine", "model": m_flr, "outdir": out_flr}, "keep_mine")
    km_ops = journal(m_flr)["ops"] if k_flr and k_flr.get("ok") else []
    s_flr = sync(w, m_flr, ops_flr, outdir=out_flr)
    b1_t = thickness(out_flr, "b1") if os.path.exists(os.path.join(out_flr, "bodies.json")) else None
    b2_t = thickness(out_flr, "b2") if os.path.exists(os.path.join(out_flr, "bodies.json")) else None
    check(H098_CHECKS[2],
          r_flr and not r_flr["ok"] and k_flr and k_flr["ok"] and km_ops == ops_flr
          and s_flr and s_flr["ok"] and b1_t == 18.0 and b2_t == 18.0,
          (r_flr, k_flr, len(km_ops), b1_t, b2_t))

    # 4. Worker crash mid-reload: retried reload on a new worker (without open) drops post-rev ops and keeps rev
    m_cr = fresh_model("crash_mid_reload")
    out_cr = m_cr + "-out"
    os.makedirs(out_cr, exist_ok=True)
    opened(m_cr)
    sync(w, m_cr, board_ops(300))
    ask({"cmd": "flush", "model": m_cr}, "flush")
    rev1_cr = m_cr + ".rev1"
    shutil.copy2(m_cr, rev1_cr)
    sync(w, m_cr, board_ops(300) + second(200))
    ask({"cmd": "flush", "model": m_cr}, "flush")
    freecad_save(rev1_cr)
    os.replace(rev1_cr, m_cr)
    wait_outside(m_cr)
    worker.kill()
    w.drop()
    worker = worker.restart()
    w = Window(worker.port)
    r_cr = ask({"cmd": "reload", "model": m_cr, "outdir": out_cr}, "reload")
    check(H098_CHECKS[3],
          r_cr and r_cr["ok"] and [o["id"] for o in r_cr["ops"]] == ["r1", "pp1"]
          and r_cr["undo_floor"] == 2 and [o["id"] for o in r_cr["dropped"]] == ["r2", "pp2"]
          and r_cr["rev"] >= 2 and r_cr["changed"] == ["b1"] and r_cr["removed"] == ["b2"]
          and thickness(out_cr, "b1") == 30.0 and thickness(out_cr, "b2") is None,
          r_cr)

    # H094: a real FreeCAD save keeps the Meta of its open copy after rev 1 has aged out.
    def saved_reload_fixture(model):
        opened(model)
        kept = board_ops(300) + second(200)
        kept[1]["typed"] = '18 mm " & < 90°'
        assert sync(w, model, kept)["ok"]
        assert ask({"cmd": "flush", "model": model}, "flush")["ok"]
        rev1 = model + ".rev1.FCStd"
        shutil.copy2(model, rev1)
        recent = list(kept)
        for rev in range(2, 54):
            recent.append({"id": f"r{rev + 1}", "type": "rect", "plane": kept[0]["plane"], "size": [rev, 100]})
            assert sync(w, model, recent)["ok"]
            assert ask({"cmd": "flush", "model": model}, "flush")["ok"]
        assert journal(model)["rev"] >= 53
        return rev1, kept, recent[len(kept):]

    for restart in (False, True):
        name = "after worker restart" if restart else "after 52 more saves"
        m = fresh_model("meta_cold" if restart else "meta_live")
        rev1, kept, dropped = saved_reload_fixture(m)
        if restart:
            worker.kill()
            w.drop()
            worker = worker.restart()
            w = Window(worker.port)
        freecad_save(rev1)
        os.replace(rev1, m)
        if not restart:
            wait_outside(m)
        out = m + "-out"
        r = ask({"cmd": "reload", "model": m, "outdir": out}, "reload")
        check(f"FreeCAD's rev 1 save keeps both boards' ops and drops newer actions {name}",
              r and r["ok"] and [o["id"] for o in r["ops"]] == ["r1", "pp1", "r2", "pp2"]
              and r["dropped"] == dropped and r["undo_floor"] == 4
              and thickness(out, "b1") == 30.0 and thickness(out, "b2") == 18.0, r)
        if not restart:
            unchanged = sync(w, m, kept)
            j = journal(m)
            check("XML quotes, ampersand, angle bracket and degree sign survive with the same canonical op keys",
                  r and r["ops"] == kept and unchanged and unchanged["ok"]
                  and unchanged["result"]["how"] == "nothing", (r, unchanged))
            check("Meta entries publish the kept ops as ok in the reload journal",
                  j["ops"] == kept and j["status"] == [{"status": "ok"}] * len(kept), j.get("status"))

    for case, (name, metadata, restart, keep) in enumerate((
        ("missing ShopSketchOps falls back to the previous journal", {"ShopSketchOps": None}, True, True),
        ("invalid ShopSketchOps JSON falls back to the live revision", {"ShopSketchOps": "["}, False, True),
        ("a ShopSketchOps object falls back to the live revision", {"ShopSketchOps": "{}"}, False, True),
        ("a ShopSketchOps list with a non-op falls back to the live revision", {"ShopSketchOps": "[{}]"}, False, True),
        ("ShopSketchOps with no ShopSketchRev falls back to no ops", {"ShopSketchRev": None}, False, False),
    )):
        m = fresh_model(f"meta_fallback_{case}")
        opened(m)
        kept = board_ops(300)
        sync(w, m, kept)
        ask({"cmd": "flush", "model": m}, "flush")
        rev1 = m + ".rev1.FCStd"
        shutil.copy2(m, rev1)
        sync(w, m, kept + second(200))
        ask({"cmd": "flush", "model": m}, "flush")
        freecad_save(rev1, **metadata)
        os.replace(rev1, m)
        wait_outside(m)
        if restart:
            worker.kill()
            w.drop()
            worker = worker.restart()
            w = Window(worker.port)
        r = ask({"cmd": "reload", "model": m, "outdir": m + "-out"}, "reload")
        check(name, r and r["ok"] and r["ops"] == (kept if keep else []), r)

    # Exercise mismatch with the requested revision and the save rollback at the Session boundary.
    META_CHECK = os.path.join(tmp, "session_meta.py")
    with open(META_CHECK, "w") as f:
        f.write('''import json, os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.environ["SESSION_SRC"])
from session import Session

session = Session(os.environ["META_MODEL"], fresh=True)
ops = json.loads(os.environ["META_OPS"])
session.sync(ops[:2])
session.save()
old_meta = dict(session.doc.Meta)
print("META REV MISMATCH:", session._file_ops(session.path, session.rev + 1) == [], flush=True)

session.sync(ops)
write = session._write
def fail_write(g, outdir):
    meta = session.doc.Meta
    assert meta["ShopSketchRev"] == "2" and json.loads(meta["ShopSketchOps"]) == ops
    raise OSError("injected save failure")

session._write = fail_write
try:
    session.save()
except OSError:
    restored = session.rev == 1 and dict(session.doc.Meta) == old_meta
else:
    restored = False
session._write = write
session.save()
session.rev_ops.clear()
retried = [e["op"] for e in session._file_ops(session.path, 2)] == ops
print("META SAVE ROLLBACK:", restored and session.rev == 2 and retried, flush=True)
session.close()
''')
    meta_run = subprocess.run([FC, META_CHECK], env=dict(os.environ, SESSION_SRC=HERE,
                              META_MODEL=fresh_model("meta_failed_save"), META_OPS=json.dumps(board_ops(300) + second(200))),
                              capture_output=True, text=True, timeout=120)
    for marker, name in (
        ("META REV MISMATCH", "ShopSketchOps with a different revision falls back to no ops"),
        ("META SAVE ROLLBACK", "a failed save restores both Meta keys and a retry saves them together"),
    ):
        check(name, meta_run.returncode == 0 and f"{marker}: True" in meta_run.stdout.splitlines(),
              meta_run.stdout + meta_run.stderr)

    w.ask({"cmd": "quit", "seq": 999}, "quit")
    worker.proc.wait(30)
    w.drop()
finally:
    if worker.proc.poll() is None:
        worker.kill()

sys.exit(checks.done())
