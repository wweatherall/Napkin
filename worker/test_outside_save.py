# runner: python3 (it starts freecadcmd itself)
"""Outside saves (T64, A36): FreeCAD saves the open model; the worker notices without a sync, holds the model (no
autosave over FreeCAD's file), tells the window, and reloads it or keeps both, as the window says. Covers: nothing
pending (reload, changed boards, undo floor in this session and the journal); actions that landed in time (held,
dropped into the journal); 'Use FreeCAD's version' and 'Keep Napkin's' (files on disk, the copy-aside name);
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
from test_link import (FC, Checks, Window, board_ops,
                       fresh_model as _fresh_model, start_worker, sync)

tmp = os.path.abspath(os.environ.get("TESTDIR") or tempfile.mkdtemp(prefix="napkin-outside-"))
os.makedirs(tmp, exist_ok=True)
checks = Checks("OUTSIDE SAVE")
check = checks.check

FC_HELPER = os.path.join(tmp, "freecad_helper.py")
with open(FC_HELPER, "w") as f:
    f.write('''import json, sys, FreeCAD as App
print("HELPER_READY", flush=True)
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    req = json.loads(line)
    cmd = req.get("cmd")
    if cmd == "quit":
        break
    if cmd == "edit":
        doc = App.openDocument(req["model"])
        edits = req.get("meta") or {}
        if edits:
            meta = doc.Meta
            for key, value in edits.items():
                if value is None:
                    meta.pop(key, None)
                else:
                    meta[key] = value
            doc.Meta = meta
        if req.get("label") is not None:
            doc.Label = req["label"]
        add = float(req.get("add", 12))
        if add:
            ex = [o for o in doc.Objects if o.TypeId == "Part::Extrusion"][0]
            ex.LengthFwd = ex.LengthFwd.Value + add
        doc.recompute()
        doc.save()
        App.closeDocument(doc.Name)
        print("HELPER_RESP:" + json.dumps({"ok": True}), flush=True)
    elif cmd == "read_label":
        doc = App.openDocument(req["model"])
        label = doc.Label
        App.closeDocument(doc.Name)
        print("HELPER_RESP:" + json.dumps({"ok": True, "label": label}), flush=True)
''')

_fc_proc = subprocess.Popen([FC, FC_HELPER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
while True:
    _line = _fc_proc.stdout.readline()
    if not _line or _line.strip() == "HELPER_READY":
        break


def _fc_call(req):
    _fc_proc.stdin.write(json.dumps(req) + "\n")
    _fc_proc.stdin.flush()
    while True:
        line = _fc_proc.stdout.readline()
        if not line:
            raise RuntimeError("freecad helper exited unexpectedly")
        if line.startswith("HELPER_RESP:"):
            return json.loads(line[len("HELPER_RESP:"):])


def freecad_save(model, add=12, label=None, **meta):
    _fc_call({"cmd": "edit", "model": model, "add": add, "label": label, "meta": meta})


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def journal(model):
    with zipfile.ZipFile(model) as z:
        root = ET.fromstring(z.read("Document.xml"))
    meta = {i.get("key"): i.get("value") for i in root.findall("./Properties/Property[@name='Meta']/Map/Item")}
    return json.loads(meta["NapkinJournal"])


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
    check("reloading leaves FreeCAD's file as it is and writes no sidecars",
          sha(m1) == fc_sha and not os.path.exists(os.path.splitext(m1)[0] + ".napkin.json")
          and not os.path.exists(os.path.splitext(m1)[0] + ".floor.FCStd"))
    bad = sync(w, m1, ops[:1])
    check("a sync taking back an op below the floor is refused", bad and not bad["ok"] and "FreeCAD" in bad["error"], bad)
    sync(w, m1, ops + second(200))
    ask({"cmd": "flush", "model": m1}, "flush")
    label_read = _fc_call({"cmd": "read_label", "model": m1})
    expected_label = os.path.splitext(os.path.basename(m1))[0]
    # FreeCAD normalizes the label on open, so check what Napkin saved as well.
    with zipfile.ZipFile(m1) as archive:
        document_xml = ET.fromstring(archive.read("Document.xml"))
        saved_label = document_xml.find("./Properties/Property[@name='Label']/String").get("value")
    check("FreeCAD reopens the saved reload with the model's file stem as its label",
          label_read.get("label") == expected_label
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
    check("b2 is gone from the boards and b1 changed", r["changed"] == ["b1"] and r["removed"] == ["b2"], r)
    sync(w, m2, board_ops(300) + second(200))
    ask({"cmd": "flush", "model": m2}, "flush")
    j = journal(m2)
    check("they stay in the journal as dropped, with the revision they came after",
          [d["op"]["id"] for d in j["dropped"]] == ["r2", "pp2"] and j["dropped"][0]["after_rev"] == 1, j.get("dropped"))

    # 3. 'Keep Napkin's': FreeCAD's file aside first, then ours over it. Both survive on disk.
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
    check("Keep Napkin's copies FreeCAD's file aside as <model>.freecad-<time>.FCStd",
          k and k["ok"] and re.fullmatch(r"mine\.freecad-\d{8}-\d{6}\.FCStd", os.path.basename(aside)) is not None, k)
    check("the copy is FreeCAD's save, byte for byte", os.path.exists(aside) and sha(aside) == fc_sha)
    j = journal(m3)
    check("then Napkin's version is the model, with every action",
          sha(m3) != fc_sha and len(j["ops"]) == 4 and j.get("dropped") == [], len(j["ops"]))
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

    # 5. FreeCAD saves an older revision (it opened rev 1, Napkin saved rev 2 since); the worker stops before the
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
    freecad_save(broken)
    held_event = wait_outside(broken)
    ops += second(200)
    sync(w, broken, ops)
    with open(broken + ".invalid", "wb") as f:
        f.write(b"invalid FCStd")
    os.replace(broken + ".invalid", broken)
    broken_sha = sha(broken)
    r = ask({"cmd": "reload", "model": broken, "outdir": live_out}, "reload")
    check("an unreadable outside save fails reload while the model is held", held_event and r and not r["ok"], r)
    check("failed reload leaves the outside file intact", sha(broken) == broken_sha)
    os.remove(os.path.join(live_out, "bodies.json"))
    still_live = sync(w, broken, ops, outdir=live_out)
    check("after failed reload the live document still exports both boards",
          still_live and still_live["ok"] and thickness(live_out, "b1") == 30.0 and thickness(live_out, "b2") == 18.0,
          still_live)
    k = ask({"cmd": "keep_mine", "model": broken, "outdir": live_out}, "keep_mine")
    check("after failed reload Keep Napkin's copies the unreadable file aside and saves ours",
          k and k["ok"] and sha(k["aside"]) == broken_sha
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
        "after a deleted outside save fails reload, Keep Napkin's still saves ours",
        "an outside save with corrupt Document.xml fails reload instead of wiping the model",
        "a reload failure while writing the floor copy leaves the live document intact",
        "a retried reload on a new worker after a crash drops post-rev ops and keeps the rev",
    ]

    worker = worker.restart()
    w = Window(worker.port)

    # 1. Deleted file while held: reload fails, then Keep Napkin's still saves ours
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

    # 3. Reload failure during export leaves the live document intact
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
    blocked_outdir = os.path.join(out_flr, "blocked")
    with open(blocked_outdir, "w"):
        pass
    r_export = ask({"cmd": "reload", "model": m_flr, "outdir": blocked_outdir}, "reload")
    with open(bodies_flr, "rb") as f:
        check("a failed reload export keeps the last viewport export intact",
              r_export and not r_export["ok"] and f.read() == live_bodies, r_export)
    k_flr = ask({"cmd": "keep_mine", "model": m_flr, "outdir": out_flr}, "keep_mine")
    km_ops = journal(m_flr)["ops"] if k_flr and k_flr.get("ok") else []
    s_flr = sync(w, m_flr, ops_flr, outdir=out_flr)
    b1_t = thickness(out_flr, "b1") if os.path.exists(os.path.join(out_flr, "bodies.json")) else None
    b2_t = thickness(out_flr, "b2") if os.path.exists(os.path.join(out_flr, "bodies.json")) else None
    check(H098_CHECKS[2],
          r_export and not r_export["ok"] and k_flr and k_flr["ok"] and km_ops == ops_flr
          and s_flr and s_flr["ok"] and b1_t == 18.0 and b2_t == 18.0,
          (r_export, k_flr, len(km_ops), b1_t, b2_t))

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
          and r_cr["undo_floor"] == 2 and r_cr["dropped"] == []
          and r_cr["rev"] == 1 and r_cr["changed"] == ["b1"] and r_cr["removed"] == ["b2"]
          and thickness(out_cr, "b1") == 30.0 and thickness(out_cr, "b2") is None,
          r_cr)

    # H094: a real FreeCAD save keeps the Meta of its open copy after rev 1 has aged out.
    def saved_reload_fixture(model):
        opened(model)
        kept = board_ops(300) + second(200) + [
            {"id": "c1", "type": "make_component", "body": "b1", "name": '18 mm " & < 90°'}
        ]
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
              r and r["ok"] and [o["id"] for o in r["ops"]] == ["r1", "pp1", "r2", "pp2", "c1"]
              and r["dropped"] == ([] if restart else dropped) and r["undo_floor"] == 5
              and thickness(out, "b1") == 30.0 and thickness(out, "b2") == 18.0, r)
        if not restart:
            unchanged = sync(w, m, kept)
            ask({"cmd": "set_units", "model": m, "units": "mm:1"}, "set_units")
            ask({"cmd": "flush", "model": m}, "flush")
            j = journal(m)
            check("XML quotes, ampersand, angle bracket and degree sign survive with the same canonical op keys",
                  r and r["ops"] == kept and unchanged and unchanged["ok"]
                  and unchanged["result"]["how"] == "nothing", (r, unchanged))
            check("Meta entries publish the kept ops as ok in the reload journal",
                  j["ops"] == kept and j["status"] == [{"status": "ok"}] * len(kept), j.get("status"))

    for case, (name, metadata, restart, keep) in enumerate((
        ("missing NapkinOps falls back to NapkinJournal", {"NapkinOps": None}, True, True),
        ("invalid NapkinOps JSON falls back to the live revision", {"NapkinOps": "["}, False, True),
        ("a NapkinOps object falls back to the live revision", {"NapkinOps": "{}"}, False, True),
        ("a NapkinOps list with a non-op falls back to the live revision", {"NapkinOps": "[{}]"}, False, True),
        ("NapkinOps with no NapkinRev falls back to no ops", {"NapkinRev": None}, False, False),
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
    assert meta["NapkinRev"] == "2" and json.loads(meta["NapkinOps"]) == ops
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
        ("META REV MISMATCH", "NapkinOps with a different revision falls back to no ops"),
        ("META SAVE ROLLBACK", "a failed save restores both Meta keys and a retry saves them together"),
    ):
        check(name, meta_run.returncode == 0 and f"{marker}: True" in meta_run.stdout.splitlines(),
              meta_run.stdout + meta_run.stderr)

    # Closed model: our own save reopens non-external; a FreeCAD save changing only a property (no geometry) opens external.
    m_prop = fresh_model("prop_only")
    opened(m_prop)
    sync(w, m_prop, board_ops(300))
    ask({"cmd": "flush", "model": m_prop}, "flush")
    ask({"cmd": "bye"}, "bye")
    worker.proc.wait(30)
    w.drop()
    worker = worker.restart()
    w = Window(worker.port)
    o_ours = ask({"cmd": "open", "model": m_prop}, "open")
    check("a file saved by Napkin reopens non-external",
          o_ours and o_ours["ok"] and o_ours["external"] is False, o_ours)
    ask({"cmd": "bye"}, "bye")
    worker.proc.wait(30)
    w.drop()
    freecad_save(m_prop, add=0, label="PropOnlyLabel")
    worker = worker.restart()
    w = Window(worker.port)
    o_prop = ask({"cmd": "open", "model": m_prop}, "open")
    check("a FreeCAD save changing only a property (no geometry) while closed opens external",
          o_prop and o_prop["ok"] and o_prop["external"] is True, o_prop)

    w.ask({"cmd": "quit", "seq": 999}, "quit")
    worker.proc.wait(30)
    w.drop()
finally:
    if worker.proc.poll() is None:
        worker.kill()
    try:
        if _fc_proc.poll() is None:
            _fc_proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
            _fc_proc.stdin.flush()
            _fc_proc.wait(timeout=10)
    except Exception:
        if _fc_proc.poll() is None:
            _fc_proc.kill()

sys.exit(checks.done())
