# runner: python3 (it starts freecadcmd itself)
"""One FreeCAD worker serving several windows (W13): run with plain python3 (it starts freecadcmd itself).
  python3 worker/test_serve.py   (TESTDIR=<folder> for its files; FREECAD=<freecadcmd> to override)"""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FC = os.environ.get("FREECAD", "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd")
tmp = os.path.abspath(os.environ.get("TESTDIR") or tempfile.mkdtemp(prefix="shopsketch-serve-"))
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


# Events can arrive before the command reply, under load or in the same socket read.
reader, writer = socket.socketpair()
queued = Window.__new__(Window)
queued.sock, queued.buf, queued.extra = reader, b"", []
try:
    writer.sendall(b'{"cmd":"saved","model":"one"}\n{"cmd":"saved","model":"two"}\n'
                   b'{"cmd":"focus"}\n{"cmd":"sync"}\n')
    check("a command reply can follow unsolicited events", queued.wait("sync") == {"cmd": "sync"})
    check("waiting retrieves saved and focus events already buffered before the reply",
          queued.wait("saved", model="two") == {"cmd": "saved", "model": "two"}
          and queued.wait("saved", model="one") == {"cmd": "saved", "model": "one"}
          and queued.wait("focus") == {"cmd": "focus"}
          and queued.extra == [])
finally:
    reader.close()
    writer.close()


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


proc, port = start_worker()
log.flush()
check("a worker started on port 0 binds a free port itself and reports it in SERVE_PORT_FILE (T47)",
      port > 0 and f"listening on 127.0.0.1:{port}" in open(os.path.join(tmp, "worker.log")).read(), port)
try:
    m1, m2 = os.path.join(tmp, "one.FCStd"), os.path.join(tmp, "two.FCStd")
    a, b = Window(port), Window(port)
    ha, hb = a.ask({"cmd": "hello", "seq": 11}, "hello"), b.ask({"cmd": "hello"}, "hello")
    check("both windows reach the same worker, which says who it is",
          ha and hb and ha["app"] == "shopsketch" and ha["pid"] == hb["pid"] and len(ha["worker"]) == 32, (ha, hb))
    with open(os.path.join(HERE, "serve.py")) as f:
        version = int(re.search(r"^PROTOCOL_VERSION = (\d+)$", f.read(), re.M).group(1))
    with open(os.path.join(HERE, "..", "viewport", "main.gd")) as f:
        window_version = int(re.search(r"^const PROTOCOL_VERSION := (\d+)$", f.read(), re.M).group(1))
    check("hello carries the protocol version (serve.py PROTOCOL_VERSION), the same main.gd checks for",
          ha.get("protocol") == version == window_version and isinstance(ha.get("protocol"), int),
          (ha.get("protocol"), version, window_version))
    check("hello echoes its seq (T70)", ha and ha.get("seq") == 11 and "seq" in hb and hb["seq"] is None, (ha, hb))
    oa = a.ask({"cmd": "open", "model": m1, "fresh": True, "seq": 12}, "open")
    ob = b.ask({"cmd": "open", "model": m2, "fresh": True}, "open")
    check("each window opens its own model", oa["ok"] and ob["ok"], (oa, ob))
    check("an open reply echoes its seq and model, so a late one can be told apart (T70)",
          oa.get("seq") == 12 and oa["model"] == os.path.abspath(m1), oa)
    sa, sb = sync(a, m1, board_ops(300), 1), sync(b, m2, board_ops(500), 1)
    vols = []
    for m in (m1, m2):
        bodies = json.load(open(os.path.join(tmp, os.path.basename(m) + "-out", "bodies.json")))
        vols.append(bodies[0]["volume_mm3"] if bodies else 0)
    check("both get their own board, in their own document", sa["ok"] and sb["ok"] and vols == [300 * 100 * 18, 500 * 100 * 18],
          (sa.get("error"), sb.get("error"), vols))
    saved = a.wait("saved", timeout=10, model=m1)
    check("the window that owns a model hears when it's saved", saved is not None and saved["model"] == m1, saved)
    ob2 = b.ask({"cmd": "open", "model": m1, "seq": 13}, "open")
    focus = a.wait("focus", timeout=5, model=m1)
    check("opening a model another window has is refused (one window per model)",
          ob2 and not ob2["ok"] and ob2["error"] == "already_open" and ob2.get("seq") == 13, ob2)
    fl = b.ask({"cmd": "flush", "seq": 14}, "flush")
    check("flush echoes its seq (T70)", fl and fl.get("seq") == 14, fl)
    check("and the window that has it is asked to come forward", focus is not None and focus["model"] == m1, focus)
    sb2 = sync(b, m1, board_ops(50), 2)
    check("a sync on another window's model is refused too", not sb2["ok"] and "another window" in sb2["error"], sb2)
    bye = a.ask({"cmd": "bye", "seq": 15}, "bye")
    check("a window leaving says bye (its model saved and let go)", bye is not None and bye["ok"] and bye.get("seq") == 15, bye)
    a.close()
    ob3 = b.ask({"cmd": "open", "model": m1}, "open")
    check("then the other window can open it, with its work", ob3["ok"] and len(ob3["ops"]) == 2, ob3)
    # T79: a save that fails (a read-only folder) stays pending, the window is told, flush answers not ok
    ro = os.path.join(tmp, "readonly")
    os.makedirs(ro, exist_ok=True)
    m3 = os.path.join(ro, "three.FCStd")
    b.ask({"cmd": "open", "model": m3, "fresh": True}, "open")
    sync(b, m3, board_ops(200), 3)
    first = b.wait("saved", timeout=10, model=m3)
    os.chmod(ro, 0o555)
    try:
        sync(b, m3, board_ops(250), 4)
        bad = b.wait("save_failed", timeout=10, model=m3)
        check("a save that fails tells the window that owns the model (save_failed: model, rev, error)",
              bad is not None and bad["model"] == m3 and first and bad["rev"] == first["rev"] + 1
              and bad.get("error") == "PermissionError: the folder readonly is read-only",
              (first, bad))
        time.sleep(1.0)                         # the timer doesn't keep retrying a failed save
        fl2 = b.ask({"cmd": "flush", "seq": 17}, "flush")
        tries = [m for m in b.extra if m.get("cmd") == "save_failed"]     # only flush's own retry (sent before its reply)
        check("the timer doesn't retry a failed save; flush does, and answers not ok with what failed",
              len(tries) == 1 and fl2 and not fl2["ok"] and fl2.get("seq") == 17 and fl2["saved"] == []
              and [f["rev"] for f in fl2["failed"]] == [bad["rev"]] and "three.FCStd" in fl2.get("error", ""),
              (len(tries), fl2))
    finally:
        os.chmod(ro, 0o755)
    fl3 = b.ask({"cmd": "flush", "seq": 18}, "flush")
    landed = next((m for m in reversed(b.extra) if m.get("cmd") == "saved"), None)    # sent before flush's reply
    jr = json.load(open(os.path.join(ro, "three.shopsketch.json")))
    check("once the folder is writable again the retry saves the same revision, and flush answers ok",
          fl3 and fl3["ok"] and fl3["saved"] == [{"model": m3, "rev": bad["rev"]}] and fl3["failed"] == []
          and landed and landed["rev"] == bad["rev"] and jr["rev"] == bad["rev"] and len(jr["ops"]) == 2,
          (fl3, landed, jr.get("rev")))
    fl4 = b.ask({"cmd": "flush", "seq": 19}, "flush")
    check("a flush with nothing pending saves nothing and answers ok", fl4["ok"] and fl4["saved"] == [], fl4)
    q = b.ask({"cmd": "quit", "seq": 16}, "quit")
    check("quit from the last window stops the worker", q["stopped"] and q.get("seq") == 16 and proc.wait(timeout=20) == 0, q)
    # idle exit: a fresh worker stops by itself after its last window disconnects
    proc, port = start_worker()
    c = Window(port)
    c.ask({"cmd": "hello"}, "hello")
    c.close()
    t1 = time.time()
    try:
        code = proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        code = None
    check("a worker stops by itself after the last window leaves (SERVE_IDLE_EXIT)", code == 0 and time.time() - t1 < 10,
          (code, round(time.time() - t1, 1)))
finally:
    if proc.poll() is None:
        proc.kill()
print(f"\nSERVE TESTS: {R[0]} passed, {R[1]} failed")
sys.exit(1 if R[1] else 0)
