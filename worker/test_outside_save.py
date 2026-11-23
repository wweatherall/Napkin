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
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FC = os.environ.get("FREECAD", "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd")
tmp = os.path.abspath(os.environ.get("TESTDIR") or tempfile.mkdtemp(prefix="shopsketch-outside-"))
os.makedirs(tmp, exist_ok=True)
R = [0, 0]


def check(name, cond, detail=""):
    R[0 if cond else 1] += 1
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"), flush=True)


class Window:
    """A stand-in for one Shop Sketch window: a connection and its replies (the worker may also send on its own)."""
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=60)
        self.buf = b""
        self.extra = []                     # messages that weren't the reply we waited for (saved, focus)

    def ask(self, req, want):
        self.sock.sendall((json.dumps(req) + "\n").encode())
        return self.wait(want)

    def wait(self, want, timeout=60, model=None):
        for i, msg in enumerate(self.extra):
            if msg.get("cmd") == want and (model is None or msg.get("model") == model):
                return self.extra.pop(i)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                msg = json.loads(line)
                if msg.get("cmd") == want and (model is None or msg.get("model") == model):
                    return msg
                self.extra.append(msg)
            self.sock.settimeout(max(0.001, deadline - time.monotonic()))
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                return None
            finally:
                self.sock.settimeout(60)
            if not chunk:
                return None
            self.buf += chunk
        return None

    def close(self):
        self.sock.close()


def board_ops(w):
    return [{"id": "r1", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, 0, 0]}, "size": [w, 100]},
            {"id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": 18, "body": "b1"}]


def sync(win, model, ops, seq):
    out = os.path.join(tmp, os.path.basename(model) + "-out")
    os.makedirs(out, exist_ok=True)
    return win.ask({"cmd": "sync", "model": model, "outdir": out, "seq": seq,
                    "oplog": {"format": "oplog/0.1", "units": "mm", "ops": ops}}, "sync")


port_file = os.path.join(tmp, "worker.port")
log = open(os.path.join(tmp, "worker.log"), "w")
env = dict(os.environ, SERVE_PORT="0", SERVE_PORT_FILE=port_file, SERVE_IDLE_EXIT="2")   # it picks its own port (T47)


def start_worker():
    """A worker on port 0: it binds a free port itself and writes it to SERVE_PORT_FILE (T47)."""
    if os.path.exists(port_file):
        os.remove(port_file)
    p = subprocess.Popen([FC, os.path.join(HERE, "replay.py")], env=env, stdout=log, stderr=subprocess.STDOUT)
    t0 = time.time()
    while time.time() - t0 < 60 and not os.path.exists(port_file):
        time.sleep(0.05)
    return p, (int(open(port_file).read()) if os.path.exists(port_file) else 0)

EDIT = os.path.join(tmp, "freecad_edit.py")
with open(EDIT, "w") as f:
    f.write('''import os, FreeCAD as App
doc = App.openDocument(os.environ["EDIT_MODEL"])
ex = [o for o in doc.Objects if o.TypeId == "Part::Extrusion"][0]
ex.LengthFwd = ex.LengthFwd.Value + float(os.environ.get("EDIT_ADD", "12"))
doc.recompute()
doc.save()
App.closeDocument(doc.Name)
''')


def freecad_save(model, add=12):
    """What William does in FreeCAD: open the model, make its first board thicker, save."""
    subprocess.run([FC, EDIT], env=dict(os.environ, EDIT_MODEL=model, EDIT_ADD=str(add)),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def journal(model):
    return json.load(open(os.path.splitext(model)[0] + ".shopsketch.json"))


def second(w):
    return [{"id": "r2", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, 300, 0]}, "size": [w, 100]},
            {"id": "pp2", "type": "push_pull", "target": {"rect": "r2"}, "distance": 18, "body": "b2"}]


def fresh_model(name):
    folder = os.path.join(tmp, name)
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)
    return os.path.join(folder, name + ".FCStd")


def thickness(outdir, bid):
    for b in json.load(open(os.path.join(outdir, "bodies.json"))):
        if b["id"] == bid:
            return round(b["world_bbox"][5] - b["world_bbox"][2], 3)
    return None


proc, port = start_worker()
w = Window(port)
seq = [0]


def ask(req, want):
    seq[0] += 1
    return w.ask(dict(req, seq=seq[0]), want)


def opened(model):
    return ask({"cmd": "open", "model": model, "fresh": True}, "open")


def wait_outside(model, timeout=10):
    """The worker's outside_save event for this model (others are kept in w.extra and counted as stray)."""
    return w.wait("outside_save", timeout=timeout, model=model)


def stray():
    return [m for m in w.extra if m.get("cmd") == "outside_save"]


# 1. Nothing pending: reload, the changed board, undo stops at the FreeCAD change.
m1 = fresh_model("quiet")
out1 = m1 + "-out"
opened(m1)
ops = board_ops(300)
sync(w, m1, ops, 1)
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
bad = sync(w, m1, ops[:1], 3)
check("a sync taking back an op below the floor is refused", bad and not bad["ok"] and "FreeCAD" in bad["error"], bad)
sync(w, m1, ops + second(200), 4)
ask({"cmd": "flush", "model": m1}, "flush")
j = journal(m1)
check("a later save keeps the floor in the journal", j["floor"] == 2 and len(j["ops"]) == 4, (j.get("floor"), len(j["ops"])))
check("and no outside save is reported for our own save", wait_outside(m1, 1.0) is None)

# 2. Actions pending that land: held (no autosave over FreeCAD's file), then the reload drops them into the journal.
m2 = fresh_model("busy")
out2 = m2 + "-out"
opened(m2)
sync(w, m2, board_ops(300), 1)
ask({"cmd": "flush", "model": m2}, "flush")
# Prepare FreeCAD's save away from the watched path. Stop the worker at an acknowledged
# process boundary, queue the actions and publish the save, then resume. The watch's first
# look settles the new file; the queued sync lands before its next look reports unsaved.
edit = m2 + ".edited.FCStd"
shutil.copy2(m2, edit)
freecad_save(edit)
fc_sha = sha(edit)
os.kill(proc.pid, signal.SIGSTOP)
_, stopped = os.waitpid(proc.pid, os.WUNTRACED)
assert os.WIFSTOPPED(stopped), stopped
try:
    out = os.path.join(tmp, os.path.basename(m2) + "-out")
    os.makedirs(out, exist_ok=True)
    req = {"cmd": "sync", "model": m2, "outdir": out, "seq": 2,
           "oplog": {"format": "oplog/0.1", "units": "mm", "ops": board_ops(300) + second(200)}}
    w.sock.sendall((json.dumps(req) + "\n").encode())
    os.replace(edit, m2)
finally:
    os.kill(proc.pid, signal.SIGCONT)
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
sync(w, m3, board_ops(300), 1)
ask({"cmd": "flush", "model": m3}, "flush")
freecad_save(m3)
fc_sha = sha(m3)
sync(w, m3, board_ops(300) + second(200), 2)
wait_outside(m3)
k = ask({"cmd": "keep_mine", "model": m3, "outdir": out3}, "keep_mine")
aside = (k or {}).get("aside") or ""
check("Keep Shop Sketch's copies FreeCAD's file aside as <model>.freecad-<time>.FCStd",
      k and k["ok"] and re.fullmatch(r"mine\.freecad-\d{8}-\d{6}\.FCStd", os.path.basename(aside)) is not None, k)
check("the copy is FreeCAD's save, byte for byte", os.path.exists(aside) and sha(aside) == fc_sha)
j = journal(m3)
check("then Shop Sketch's version is the model, with every action",
      sha(m3) != fc_sha and j["file_sha256"] == sha(m3) and len(j["ops"]) == 4 and j.get("dropped") == [], len(j["ops"]))
sync(w, m3, board_ops(300) + second(220), 3)
ask({"cmd": "flush", "model": m3}, "flush")
check("autosave carries on after the choice", journal(m3)["ops"][2]["size"] == [220, 100])
check("one choice, one copy: no second outside save after ours", stray() == [] and
      len([n for n in os.listdir(os.path.dirname(m3)) if ".freecad-" in n]) == 1, stray())

# 4. A flush (closing) while held keeps both the same way.
m4 = fresh_model("closing")
opened(m4)
sync(w, m4, board_ops(300), 1)
ask({"cmd": "flush", "model": m4}, "flush")
freecad_save(m4)
fc_sha = sha(m4)
sync(w, m4, board_ops(300) + second(200), 2)
wait_outside(m4)
fl = ask({"cmd": "flush", "model": m4}, "flush")
asides = [s.get("aside") for s in (fl or {}).get("saved", [])]
check("a flush of a held model copies FreeCAD's save aside before saving ours",
      fl and fl["ok"] and asides and asides[0] and sha(asides[0]) == fc_sha and len(journal(m4)["ops"]) == 4, fl)

# 5. FreeCAD saves an older revision (it opened rev 1, Shop Sketch saved rev 2 since); the worker stops before the
#    reload. A new worker opens FreeCAD's file as an outside edit, not as a save of ours that stopped part way.
m5 = fresh_model("older")
opened(m5)
sync(w, m5, board_ops(300), 1)
ask({"cmd": "flush", "model": m5}, "flush")
rev1 = m5 + ".rev1"
shutil.copy2(m5, rev1)
sync(w, m5, board_ops(300) + second(200), 2)
ask({"cmd": "flush", "model": m5}, "flush")
freecad_save(rev1)
os.replace(rev1, m5)                               # FreeCAD's save of the revision it had open
fc_sha = sha(m5)
ev = wait_outside(m5)
check("an outside save of an older revision is noticed", ev and ev["rev"] == 1, ev)
w.ask({"cmd": "quit"}, "quit")
proc.wait(30)
proc, port = start_worker()
w = Window(port)
o = ask({"cmd": "open", "model": m5}, "open")
check("a new worker opens it as FreeCAD's (external, nothing recovered), the file untouched",
      o and o["external"] and "recovered" not in o and sha(m5) == fc_sha
      and not os.path.exists(os.path.splitext(m5)[0] + ".unmatched.FCStd"), o)
ask({"cmd": "bye"}, "bye")                         # the worker lets the window go and stops by itself
proc.wait(30)

# 6. In one worker, the same older-revision save reloads with what came after rev 1 dropped.
proc, port = start_worker()
w = Window(port)
m6 = fresh_model("older_live")
opened(m6)
sync(w, m6, board_ops(300), 1)
ask({"cmd": "flush", "model": m6}, "flush")
rev1 = m6 + ".rev1"
shutil.copy2(m6, rev1)
sync(w, m6, board_ops(300) + second(200), 2)
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
sync(w, m7, board_ops(300) + second(200), 1)
ask({"cmd": "flush", "model": m7}, "flush")
rev1 = m7 + ".rev1"
shutil.copy2(m7, rev1)
third = [{"id": "r3", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, 600, 0]}, "size": [150, 100]},
         {"id": "pp3", "type": "push_pull", "target": {"rect": "r3"}, "distance": 18, "body": "b3"}]
sync(w, m7, board_ops(300) + third, 2)             # b2 undone, b3 made
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
sync(w, m7b, board_ops(300) + [bad], 1)
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
sync(w, broken, ops, 1)
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
sync(w, broken, ops, 2)
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
still_live = ask({"cmd": "sync", "model": broken, "outdir": live_out,
                  "oplog": {"format": "oplog/0.1", "units": "mm", "ops": ops}}, "sync")
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
sync(w, m8, board_ops(300), 1)
ask({"cmd": "flush", "model": m8}, "flush")
freecad_save(m8)
wait_outside(m8)
sync(w, m8, board_ops(300) + second(200), 2)       # held: these wait, unsaved
os.remove(m8)
w.close()
time.sleep(0.5)
check("a held model's file deleted and its window closed: the worker keeps running", proc.poll() is None,
      proc.poll())
w = Window(port)
q = w.ask({"cmd": "quit", "seq": 99}, "quit")
check("and still answers the next window", q is not None, q)
proc.wait(30)

# H098 break-it trial checks (only run with BREAK_H093=1; keep only failures)
BREAK_H093_NAMES = [
    "after a deleted outside save fails reload, Keep Shop Sketch's still saves ours",
    "an outside save with corrupt Document.xml fails reload instead of wiping the model",
    "a reload failure while writing the floor copy leaves the live document intact",
    "a retried reload on a new worker after a crash drops post-rev ops and keeps the rev",
]
if os.environ.get("BREAK_H093") != "1":
    for _name in BREAK_H093_NAMES:
        print(f"SKIP {_name} (BREAK_H093)", flush=True)
else:
    import zipfile
    proc, port = start_worker()
    w = Window(port)

    # 1. Deleted file while held: reload fails, then Keep Shop Sketch's still saves ours
    m_del = fresh_model("deleted_keep_mine")
    out_del = m_del + "-out"
    os.makedirs(out_del, exist_ok=True)
    opened(m_del)
    ops_del = board_ops(300)
    sync(w, m_del, ops_del, 1)
    ask({"cmd": "flush", "model": m_del}, "flush")
    freecad_save(m_del)
    wait_outside(m_del)
    ops_del += second(200)
    sync(w, m_del, ops_del, 2)
    os.remove(m_del)
    r_del = ask({"cmd": "reload", "model": m_del, "outdir": out_del}, "reload")
    k_del = ask({"cmd": "keep_mine", "model": m_del, "outdir": out_del}, "keep_mine")
    check(BREAK_H093_NAMES[0],
          r_del and not r_del["ok"] and k_del and k_del["ok"] and os.path.exists(m_del)
          and journal(m_del)["ops"] == ops_del, (r_del, k_del))

    # 2. Valid zip with corrupt Document.xml: reload must fail instead of wiping the model
    m_xml = fresh_model("corrupt_xml")
    out_xml = m_xml + "-out"
    os.makedirs(out_xml, exist_ok=True)
    opened(m_xml)
    sync(w, m_xml, board_ops(300), 1)
    ask({"cmd": "flush", "model": m_xml}, "flush")
    bad_zip = m_xml + ".badxml"
    with zipfile.ZipFile(bad_zip, "w") as z:
        z.writestr("Document.xml", "<<<not xml>>>")
    os.replace(bad_zip, m_xml)
    wait_outside(m_xml)
    r_xml = ask({"cmd": "reload", "model": m_xml, "outdir": out_xml}, "reload")
    check(BREAK_H093_NAMES[1], r_xml and not r_xml["ok"], r_xml)

    # 3. Reload failure while writing the floor copy leaves the live document intact
    m_flr = fresh_model("floor_fail")
    out_flr = m_flr + "-out"
    os.makedirs(out_flr, exist_ok=True)
    opened(m_flr)
    ops_flr = board_ops(300)
    sync(w, m_flr, ops_flr, 1)
    ask({"cmd": "flush", "model": m_flr}, "flush")
    freecad_save(m_flr)
    wait_outside(m_flr)
    ops_flr += second(200)
    sync(w, m_flr, ops_flr, 2)
    flr_path = os.path.splitext(m_flr)[0] + ".floor.FCStd"
    os.mkdir(flr_path)
    r_flr = ask({"cmd": "reload", "model": m_flr, "outdir": out_flr}, "reload")
    os.rmdir(flr_path)
    k_flr = ask({"cmd": "keep_mine", "model": m_flr, "outdir": out_flr}, "keep_mine")
    km_ops = journal(m_flr)["ops"] if k_flr and k_flr.get("ok") else []
    s_flr = ask({"cmd": "sync", "model": m_flr, "outdir": out_flr,
                 "oplog": {"format": "oplog/0.1", "units": "mm", "ops": ops_flr}}, "sync")
    b1_t = thickness(out_flr, "b1") if os.path.exists(os.path.join(out_flr, "bodies.json")) else None
    b2_t = thickness(out_flr, "b2") if os.path.exists(os.path.join(out_flr, "bodies.json")) else None
    check(BREAK_H093_NAMES[2],
          r_flr and not r_flr["ok"] and k_flr and k_flr["ok"] and km_ops == ops_flr
          and s_flr and s_flr["ok"] and b1_t == 18.0 and b2_t == 18.0,
          (r_flr, k_flr, len(km_ops), b1_t, b2_t))

    # 4. Worker crash mid-reload: retried reload on a new worker (without open) drops post-rev ops and keeps rev
    m_cr = fresh_model("crash_mid_reload")
    out_cr = m_cr + "-out"
    os.makedirs(out_cr, exist_ok=True)
    opened(m_cr)
    sync(w, m_cr, board_ops(300), 1)
    ask({"cmd": "flush", "model": m_cr}, "flush")
    rev1_cr = m_cr + ".rev1"
    shutil.copy2(m_cr, rev1_cr)
    sync(w, m_cr, board_ops(300) + second(200), 2)
    ask({"cmd": "flush", "model": m_cr}, "flush")
    freecad_save(rev1_cr)
    os.replace(rev1_cr, m_cr)
    wait_outside(m_cr)
    proc.kill()
    proc.wait(30)
    w.close()
    proc, port = start_worker()
    w = Window(port)
    r_cr = ask({"cmd": "reload", "model": m_cr, "outdir": out_cr}, "reload")
    check(BREAK_H093_NAMES[3],
          r_cr and r_cr["ok"] and [o["id"] for o in r_cr["ops"]] == ["r1", "pp1"]
          and r_cr["undo_floor"] == 2 and [o["id"] for o in r_cr["dropped"]] == ["r2", "pp2"]
          and r_cr["rev"] >= 2 and thickness(out_cr, "b1") == 30.0 and thickness(out_cr, "b2") is None,
          r_cr)
    w.ask({"cmd": "quit", "seq": 999}, "quit")
    proc.wait(30)

print(f"OUTSIDE SAVE TESTS: {R[0]} passed, {R[1]} failed", flush=True)
sys.exit(1 if R[1] else 0)
