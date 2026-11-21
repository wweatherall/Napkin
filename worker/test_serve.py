"""One FreeCAD worker serving several windows (W13): run with plain python3 (it starts freecadcmd itself).
  python3 worker/test_serve.py   (TESTDIR=<folder> for its files; FREECAD=<freecadcmd> to override)"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FC = os.environ.get("FREECAD", "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd")
tmp = os.environ.get("TESTDIR") or tempfile.mkdtemp(prefix="shopsketch-serve-")
os.makedirs(tmp, exist_ok=True)
R = [0, 0]


def check(name, cond, detail=""):
    R[0 if cond else 1] += 1
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"), flush=True)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Window:
    """A stand-in for one Shop Sketch window: a connection and its replies (the worker may also send on its own)."""
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=60)
        self.buf = b""
        self.extra = []                     # messages that weren't the reply we waited for (saved, focus)

    def ask(self, req, want):
        self.sock.sendall((json.dumps(req) + "\n").encode())
        return self.wait(want)

    def wait(self, want, timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                msg = json.loads(line)
                if msg.get("cmd") == want:
                    return msg
                self.extra.append(msg)
            chunk = self.sock.recv(65536)
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


port = free_port()
log = open(os.path.join(tmp, "worker.log"), "w")
env = dict(os.environ, SERVE_PORT=str(port), SERVE_IDLE_EXIT="2")
proc = subprocess.Popen([FC, os.path.join(HERE, "replay.py")], env=env, stdout=log, stderr=subprocess.STDOUT)
t0 = time.time()
while time.time() - t0 < 60:
    try:
        socket.create_connection(("127.0.0.1", port), timeout=1).close()
        break
    except OSError:
        time.sleep(0.2)
try:
    m1, m2 = os.path.join(tmp, "one.FCStd"), os.path.join(tmp, "two.FCStd")
    a, b = Window(port), Window(port)
    ha, hb = a.ask({"cmd": "hello"}, "hello"), b.ask({"cmd": "hello"}, "hello")
    check("both windows reach the same worker, which says who it is",
          ha and hb and ha["app"] == "shopsketch" and ha["pid"] == hb["pid"] and len(ha["worker"]) == 32, (ha, hb))
    oa = a.ask({"cmd": "open", "model": m1, "fresh": True}, "open")
    ob = b.ask({"cmd": "open", "model": m2, "fresh": True}, "open")
    check("each window opens its own model", oa["ok"] and ob["ok"], (oa, ob))
    sa, sb = sync(a, m1, board_ops(300), 1), sync(b, m2, board_ops(500), 1)
    vols = []
    for m in (m1, m2):
        bodies = json.load(open(os.path.join(tmp, os.path.basename(m) + "-out", "bodies.json")))
        vols.append(bodies[0]["volume_mm3"] if bodies else 0)
    check("both get their own board, in their own document", sa["ok"] and sb["ok"] and vols == [300 * 100 * 18, 500 * 100 * 18],
          (sa.get("error"), sb.get("error"), vols))
    saved = a.wait("saved", timeout=10)
    check("the window that owns a model hears when it's saved", saved is not None and saved["model"] == m1, saved)
    ob2 = b.ask({"cmd": "open", "model": m1}, "open")
    focus = a.wait("focus", timeout=5)
    check("opening a model another window has is refused (one window per model)",
          ob2 and not ob2["ok"] and ob2["error"] == "already_open", ob2)
    check("and the window that has it is asked to come forward", focus is not None and focus["model"] == m1, focus)
    sb2 = sync(b, m1, board_ops(50), 2)
    check("a sync on another window's model is refused too", not sb2["ok"] and "another window" in sb2["error"], sb2)
    bye = a.ask({"cmd": "bye"}, "bye")
    check("a window leaving says bye (its model saved and let go)", bye is not None and bye["ok"], bye)
    a.close()
    ob3 = b.ask({"cmd": "open", "model": m1}, "open")
    check("then the other window can open it, with its work", ob3["ok"] and len(ob3["ops"]) == 2, ob3)
    q = b.ask({"cmd": "quit"}, "quit")
    check("quit from the last window stops the worker", q["stopped"] and proc.wait(timeout=20) == 0, q)
    # idle exit: a fresh worker stops by itself after its last window disconnects
    proc = subprocess.Popen([FC, os.path.join(HERE, "replay.py")], env=env, stdout=log, stderr=subprocess.STDOUT)
    t0 = time.time()
    while time.time() - t0 < 60:
        try:
            c = Window(port)
            break
        except OSError:
            time.sleep(0.2)
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
