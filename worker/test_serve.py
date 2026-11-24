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
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from test_link import (Checks, Window, board_ops, fresh_model, missing,
                       read_only, start_worker, sync, unreadable)

tmp = os.path.abspath(os.environ.get("TESTDIR") or tempfile.mkdtemp(prefix="shopsketch-serve-"))
os.makedirs(tmp, exist_ok=True)
checks = Checks("SERVE")
check = checks.check


# Events can arrive before the command reply, under load or in the same socket read.
reader, writer = socket.socketpair()
queued = Window.__new__(Window)
queued.sock, queued.buf, queued.extra, queued.seq = reader, b"", [], 0
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


worker = start_worker(tmp)
check("a worker started on port 0 binds a free port itself and reports it in SERVE_PORT_FILE (T47)",
      worker.port > 0 and f"listening on 127.0.0.1:{worker.port}" in open(worker.log).read(), worker.port)
try:
    m1, m2 = os.path.join(tmp, "one.FCStd"), os.path.join(tmp, "two.FCStd")
    a, b = Window(worker.port), Window(worker.port)
    ha, hb = a.ask({"cmd": "hello", "seq": 11}, "hello"), b.ask({"cmd": "hello", "seq": None}, "hello")
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
    sa, sb = sync(a, m1, board_ops(300)), sync(b, m2, board_ops(500))
    vols = []
    for m in (m1, m2):
        bodies = json.load(open(os.path.join(m + "-out", "bodies.json")))
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
    sb2 = sync(b, m1, board_ops(50))
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
    sync(b, m3, board_ops(200))
    first = b.wait("saved", timeout=10, model=m3)
    with read_only(ro):
        sync(b, m3, board_ops(250))
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
    check("quit from the last window stops the worker", q["stopped"] and q.get("seq") == 16 and worker.proc.wait(timeout=20) == 0, q)
    # idle exit: a fresh worker stops by itself after its last window disconnects
    worker = worker.restart()
    c = Window(worker.port)
    c.ask({"cmd": "hello"}, "hello")
    c.close()
    t1 = time.time()
    try:
        code = worker.proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        code = None
    check("a worker stops by itself after the last window leaves (SERVE_IDLE_EXIT)", code == 0 and time.time() - t1 < 10,
          (code, round(time.time() - t1, 1)))

    # T110: each failure-path helper in worker/test_link.py proves itself once
    worker = worker.restart()
    h = Window(worker.port)
    mh = fresh_model(tmp, "helper_ro")
    h.ask({"cmd": "open", "model": mh, "fresh": True}, "open")
    sync(h, mh, board_ops(200))
    h.ask({"cmd": "flush", "model": mh}, "flush")
    h.extra.clear()
    with read_only(os.path.dirname(mh)):
        sync(h, mh, board_ops(260))
        fl_ro = h.ask({"cmd": "flush", "model": mh}, "flush")
        sf_ro = h.wait("save_failed", timeout=5, model=mh)
    fl_ok = h.ask({"cmd": "flush", "model": mh}, "flush")
    check("helper read_only fails a flush with the read-only message and restores writes after",
          fl_ro and not fl_ro["ok"] and sf_ro and "read-only" in sf_ro.get("error", "")
          and fl_ok and fl_ok["ok"] and len(fl_ok["saved"]) == 1, (fl_ro, sf_ro, fl_ok))
    h.ask({"cmd": "bye"}, "bye")
    h.drop()

    mf = fresh_model(tmp, "helper_file")
    w_file = Window(worker.port)
    w_file.ask({"cmd": "open", "model": mf, "fresh": True}, "open")
    sync(w_file, mf, board_ops(300))
    w_file.ask({"cmd": "flush", "model": mf}, "flush")
    w_file.ask({"cmd": "bye"}, "bye")
    w_file.drop()

    w_bad = Window(worker.port)
    with unreadable(mf):
        o_unr = w_bad.ask({"cmd": "open", "model": mf}, "open")
    o_unr_after = w_bad.ask({"cmd": "open", "model": mf}, "open")
    check("helper unreadable makes opening fail with an error reply and restores the file after",
          o_unr and not o_unr["ok"] and o_unr_after and o_unr_after["ok"] and len(o_unr_after["ops"]) == 2,
          (o_unr, o_unr_after))
    w_bad.ask({"cmd": "bye"}, "bye")
    w_bad.drop()

    w_miss = Window(worker.port)
    with missing(mf):
        r_miss = w_miss.ask({"cmd": "reload", "model": mf, "outdir": mf + "-out"}, "reload")
    o_miss_after = w_miss.ask({"cmd": "open", "model": mf}, "open")
    check("helper missing moves the file aside (reload fails) and restores it so open succeeds after",
          r_miss and not r_miss["ok"] and o_miss_after and o_miss_after["ok"] and len(o_miss_after["ops"]) == 2,
          (r_miss, o_miss_after))

    # Window.drop: closing the socket without bye leaves the worker alive for another window
    w_drop = Window(worker.port)
    w_drop.ask({"cmd": "hello"}, "hello")
    w_drop.drop()
    w_other = Window(worker.port)
    h_other = w_other.ask({"cmd": "hello"}, "hello")
    check("helper Window.drop closes without bye while the worker keeps answering another window",
          worker.proc.poll() is None and h_other and h_other.get("ok"), h_other)

    # Worker.kill and Worker.restart: wait returns None on a killed worker, restart answers hello
    worker.kill()
    gone = w_other.wait("hello", timeout=5)
    w_other.drop()
    w_miss.drop()
    worker = worker.restart()
    w_re = Window(worker.port)
    h_re = w_re.ask({"cmd": "hello"}, "hello")
    w_re.drop()
    check("helper Worker.kill ends the link (wait returns None) and restart gives a worker answering hello",
          gone is None and h_re and h_re.get("ok") and h_re.get("app") == "shopsketch", (gone, h_re))
    worker.stop()
finally:
    if worker.proc.poll() is None:
        worker.kill()
sys.exit(checks.done())
