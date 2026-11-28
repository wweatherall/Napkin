# runner: python3 (it starts freecadcmd itself)
"""Display units saved in .FCStd Meta (H052, I57, I59, I62, P21, P42):
  - set_units with no action after it is saved on flush and comes back on reopen;
  - units survive a rebuild past FreeCAD's 20-step undo history (both empty rebuild and floor-copy rebuild);
  - undo doesn't change the units;
  - old files (no NapkinUnits in Meta) and unreadable values ('furlongs') open cleanly without stopping open;
  - outside saves: reload takes FreeCAD's file's units, Keep Napkin's keeps the window's;
  - P21 round-trip: every formatted length across all 6 formats and all roundings parses back to the same rounded
    length through FreeCAD's length_input.evaluate.
  python3 worker/test_model_units.py   (TESTDIR=<folder>; FREECAD=<freecadcmd>)"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
FC = os.environ.get("FREECAD", "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd")
tmp = os.path.abspath(os.environ.get("TESTDIR") or tempfile.mkdtemp(prefix="napkin-units-"))
os.makedirs(tmp, exist_ok=True)
R = [0, 0]


def check(name, cond, detail=""):
    R[0 if cond else 1] += 1
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"), flush=True)


class Window:
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=60)
        self.buf = b""
        self.extra = []

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


def fresh_model(name):
    folder = os.path.join(tmp, name)
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)
    return os.path.join(folder, name + ".FCStd")


def board_ops(n=1):
    ops = []
    for i in range(1, n + 1):
        ops.append({"id": f"r{i}", "type": "rect",
                    "plane": {"normal": [0, 0, 1], "origin": [0, i * 120, 0]}, "size": [100, 80]})
        ops.append({"id": f"pp{i}", "type": "new_board",
                    "target": {"rect": f"r{i}"}, "distance": 18, "body": f"b{i}"})
    return ops


def sync(win, model, ops, seq):
    out = os.path.join(tmp, os.path.basename(model) + "-out")
    os.makedirs(out, exist_ok=True)
    return win.ask({"cmd": "sync", "model": model, "outdir": out, "seq": seq,
                    "oplog": {"format": "oplog/0.1", "units": "mm", "ops": ops}}, "sync")


def meta_units(fcstd):
    with zipfile.ZipFile(fcstd) as z:
        xml = z.read("Document.xml").decode("utf-8", "replace")
    import re
    m = re.search(r'<Item key="NapkinUnits" value="([^"]*)"', xml)
    return m.group(1) if m else None


port_file = os.path.join(tmp, "worker.port")
log = open(os.path.join(tmp, "worker.log"), "w")
env = dict(os.environ, SERVE_PORT="0", SERVE_PORT_FILE=port_file, SERVE_IDLE_EXIT="2")


def start_worker():
    if os.path.exists(port_file):
        os.remove(port_file)
    p = subprocess.Popen([FC, os.path.join(HERE, "replay.py")], env=env, stdout=log, stderr=subprocess.STDOUT)
    t0 = time.time()
    while time.time() - t0 < 60 and not os.path.exists(port_file):
        time.sleep(0.05)
    return p, (int(open(port_file).read()) if os.path.exists(port_file) else 0)


# Helper script to write/edit a .FCStd file directly in FreeCAD (for old/corrupt files and outside saves).
FC_HELPER = os.path.join(tmp, "fc_helper.py")
with open(FC_HELPER, "w") as f:
    f.write('''import os, FreeCAD as App
mode = os.environ["HELPER_MODE"]
path = os.environ["HELPER_MODEL"]
if mode == "plain":
    doc = App.newDocument("Old")
    doc.saveAs(path)
    App.closeDocument(doc.Name)
elif mode == "set_meta":
    doc = App.openDocument(path)
    meta = doc.Meta
    meta["NapkinUnits"] = os.environ["HELPER_UNITS"]
    doc.Meta = meta
    doc.save()
    App.closeDocument(doc.Name)
elif mode == "edit_and_units":
    doc = App.openDocument(path)
    ex = [o for o in doc.Objects if o.TypeId == "Part::Extrusion"][0]
    ex.LengthFwd = ex.LengthFwd.Value + 10.0
    if "HELPER_UNITS" in os.environ:
        meta = doc.Meta
        meta["NapkinUnits"] = os.environ["HELPER_UNITS"]
        doc.Meta = meta
    doc.recompute()
    doc.save()
    App.closeDocument(doc.Name)
''')


def run_helper(mode, model, **extra):
    subprocess.run([FC, FC_HELPER], env=dict(os.environ, HELPER_MODE=mode, HELPER_MODEL=model, **extra),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120, check=True)


proc, port = start_worker()
w = Window(port)
seq = [0]


def ask(req, want):
    seq[0] += 1
    return w.ask(dict(req, seq=seq[0]), want)


try:
    # 1. set_units with no action after it: saved on flush and survives reopen in a fresh worker.
    m1 = fresh_model("save_only")
    o = ask({"cmd": "open", "model": m1, "fresh": True}, "open")
    check("new model open reply has no units field", o and o["ok"] and "units" not in o, o)
    su = ask({"cmd": "set_units", "model": m1, "units": "ft-in:1/32"}, "set_units")
    check("set_units succeeds and advances anticipated rev", su and su["ok"] and su["units"] == "ft-in:1/32" and su["rev"] == 1, su)
    bad_su = ask({"cmd": "set_units", "model": m1, "units": "furlongs"}, "set_units")
    check("set_units refuses an unknown units spec", bad_su and not bad_su["ok"], bad_su)
    fl = ask({"cmd": "flush", "model": m1}, "flush")
    check("flush saves the units-only change", fl and fl["ok"] and len(fl["saved"]) == 1 and meta_units(m1) == "ft-in:1/32", (fl, meta_units(m1)))
    w.ask({"cmd": "quit"}, "quit")
    proc.wait(30)

    proc, port = start_worker()
    w = Window(port)
    o = ask({"cmd": "open", "model": m1}, "open")
    check("reopening returns the saved units", o and o["ok"] and o.get("units") == "ft-in:1/32", o)

    # 2. Rebuild past FreeCAD's 20-step undo history keeps the units (P42).
    m2 = fresh_model("rebuild")
    ask({"cmd": "open", "model": m2, "fresh": True}, "open")
    ask({"cmd": "set_units", "model": m2, "units": "in-frac:1/16"}, "set_units")
    many = board_ops(12)  # 24 actions (> 20 undo steps)
    s1 = sync(w, m2, many, 1)
    check("24 actions synced", s1 and s1["ok"], s1)
    s2 = sync(w, m2, many[:2], 2)  # undo 22 actions -> forces _rebuild() (_new_doc)
    check("undoing past 20 actions triggers a rebuild", s2 and s2["ok"] and s2["result"]["how"] == "rebuilt", s2)
    ask({"cmd": "flush", "model": m2}, "flush")
    w.ask({"cmd": "quit"}, "quit")
    proc.wait(30)

    proc, port = start_worker()
    w = Window(port)
    o2 = ask({"cmd": "open", "model": m2}, "open")
    check("units survive a rebuild past 20 undo steps", o2 and o2.get("units") == "in-frac:1/16", o2)

    # 3. Rebuild from a floor copy (A38) keeps the units too.
    m3 = fresh_model("floor_rebuild")
    ask({"cmd": "open", "model": m3, "fresh": True}, "open")
    sync(w, m3, board_ops(1), 1)
    ask({"cmd": "set_units", "model": m3, "units": "mm:1"}, "set_units")
    ask({"cmd": "flush", "model": m3}, "flush")
    run_helper("edit_and_units", m3)   # external edit in FreeCAD (still mm:1 in Meta)
    ev = w.wait("outside_save", timeout=10, model=m3)
    check("outside save noticed before floor-copy rebuild check", ev is not None, ev)
    ask({"cmd": "reload", "model": m3, "outdir": m3 + "-out"}, "reload")
    ask({"cmd": "set_units", "model": m3, "units": "in-dec:0.01"}, "set_units")  # changed AFTER floor copy written!
    more = board_ops(13)  # 26 ops (2 below floor, 24 above floor)
    sync(w, m3, more, 2)
    s_reb = sync(w, m3, more[:4], 3)  # undo 22 ops -> rebuilds from floor copy (whose Meta still says mm:1!)
    check("undoing past 20 steps above floor rebuilds from floor copy", s_reb and s_reb["ok"] and s_reb["result"]["how"] == "rebuilt", s_reb)
    ask({"cmd": "flush", "model": m3}, "flush")
    w.ask({"cmd": "quit"}, "quit")
    proc.wait(30)

    proc, port = start_worker()
    w = Window(port)
    o3 = ask({"cmd": "open", "model": m3}, "open")
    check("units survive a floor-copy rebuild without reverting to floor Meta", o3 and o3.get("units") == "in-dec:0.01", o3)

    # 4. Undo doesn't change the units.
    m4 = fresh_model("undo_keeps")
    ask({"cmd": "open", "model": m4, "fresh": True}, "open")
    ops4 = board_ops(2)
    sync(w, m4, ops4, 1)
    ask({"cmd": "set_units", "model": m4, "units": "cm:0.1"}, "set_units")
    sync(w, m4, ops4[:2], 2)  # undo b2
    ask({"cmd": "flush", "model": m4}, "flush")
    check("undo after a units change leaves the units intact", meta_units(m4) == "cm:0.1", meta_units(m4))

    # 5. Old file (no NapkinUnits) and corrupt Meta ("furlongs") open cleanly (I62).
    m5 = fresh_model("old_no_units")
    run_helper("plain", m5)
    o5 = ask({"cmd": "open", "model": m5}, "open")
    check("pre-T66 file with no NapkinUnits opens with no units field", o5 and o5["ok"] and "units" not in o5, o5)
    ask({"cmd": "set_units", "model": m5, "units": "m:0.001"}, "set_units")
    ask({"cmd": "flush", "model": m5}, "flush")
    check("and saving writes the chosen units into Meta", meta_units(m5) == "m:0.001", meta_units(m5))

    m6 = fresh_model("corrupt_units")
    run_helper("plain", m6)
    run_helper("set_meta", m6, HELPER_UNITS="furlongs")
    check("fixture genuinely has NapkinUnits='furlongs'", meta_units(m6) == "furlongs", meta_units(m6))
    o6 = ask({"cmd": "open", "model": m6}, "open")
    check("unreadable NapkinUnits ('furlongs') never stops open and reads as unset", o6 and o6["ok"] and "units" not in o6, o6)
    ask({"cmd": "set_units", "model": m6, "units": "in-frac:1/32"}, "set_units")
    ask({"cmd": "flush", "model": m6}, "flush")
    check("subsequent save replaces unreadable Meta with valid units", meta_units(m6) == "in-frac:1/32", meta_units(m6))

    # 6. Outside save (A36): reload takes FreeCAD's file's units; Keep Napkin's keeps ours.
    m7 = fresh_model("outside_reload")
    ask({"cmd": "open", "model": m7, "fresh": True}, "open")
    sync(w, m7, board_ops(1), 1)
    ask({"cmd": "set_units", "model": m7, "units": "mm:0.1"}, "set_units")
    ask({"cmd": "flush", "model": m7}, "flush")
    run_helper("edit_and_units", m7, HELPER_UNITS="ft-in:1/16")
    ev7 = w.wait("outside_save", timeout=10, model=m7)
    check("outside save detected for reload units check", ev7 is not None, ev7)
    r7 = ask({"cmd": "reload", "model": m7, "outdir": m7 + "-out"}, "reload")
    check("reload takes the units in FreeCAD's file", r7 and r7["ok"] and r7.get("units") == "ft-in:1/16", r7)

    m8 = fresh_model("outside_keep_mine")
    ask({"cmd": "open", "model": m8, "fresh": True}, "open")
    sync(w, m8, board_ops(1), 1)
    ask({"cmd": "set_units", "model": m8, "units": "mm:0.1"}, "set_units")
    ask({"cmd": "flush", "model": m8}, "flush")
    run_helper("edit_and_units", m8, HELPER_UNITS="ft-in:1/8")
    ev8 = w.wait("outside_save", timeout=10, model=m8)
    check("outside save detected for keep_mine units check", ev8 is not None, ev8)
    ask({"cmd": "set_units", "model": m8, "units": "in-dec:0.001"}, "set_units")
    k8 = ask({"cmd": "keep_mine", "model": m8, "outdir": m8 + "-out"}, "keep_mine")
    aside = (k8 or {}).get("aside") or ""
    check("Keep Napkin's saves the window's units and preserves FreeCAD's in the aside copy",
          k8 and k8["ok"] and meta_units(m8) == "in-dec:0.001" and aside and meta_units(aside) == "ft-in:1/8",
          (k8, meta_units(m8), meta_units(aside) if aside else None))

    # 7. P21 round-trip through FreeCAD's length_input via the worker's length command:
    # every formatted style parses back to the exact rounded length in FreeCAD too.
    rt_samples = [
        ("8' 3 1/4\"", 2520.95, "in"),
        ("-8' 3 1/4\"", -2520.95, "in"),
        ("1' 0\"", 304.8, "in"),
        ("1' 1/2\"", 317.5, "in"),
        ("-1' 1/2\"", -317.5, "in"),
        ("99 1/4\"", 2520.95, "in"),
        ("-99 1/4\"", -2520.95, "in"),
        ("3/4\"", 19.05, "in"),
        ("-3/4\"", -19.05, "in"),
        ("1/64\"", 25.4 / 64.0, "in"),
        ("0\"", 0.0, "in"),
        ("99.25\"", 2520.95, "in"),
        ("0.125\"", 3.175, "in"),
        ("1.234 m", 1234.0, "m"),
        ("12.5 cm", 125.0, "cm"),
        ("19.06 mm", 19.06, "mm"),
        ("-19.1 mm", -19.1, "mm"),
        ("12", 304.8, "in"),
        ("3/4", 19.05, "in"),
        ("19mm", 19.0, "in"),
        ("2.5", 25.0, "cm"),
        ("1.5", 1500.0, "m"),
    ]
    rt_wrong = []
    for idx, (text, want_mm, du) in enumerate(rt_samples, 1):
        lr = w.ask({"cmd": "length", "request_id": idx, "texts": [text], "default_unit": du}, "length")
        if not lr or not lr.get("ok") or abs(lr["values"][0] - want_mm) > 1e-6:
            rt_wrong.append((text, du, want_mm, lr))
    check("FreeCAD's length_input round-trips all formatted styles and bare-number default_units (P21)",
          not rt_wrong, rt_wrong[:5])

    w.ask({"cmd": "quit"}, "quit")
    proc.wait(30)
finally:
    if proc.poll() is None:
        proc.kill()
print(f"WORKER UNITS TESTS: {R[0]} passed, {R[1]} failed", flush=True)
sys.exit(1 if R[1] else 0)
