"""The connection loop: one worker serving every window (W13), and the one-off replay (main)."""
import hashlib
import json
import os
import time
from common import HERE, OpError
from session import Session, atomic_json
import length_input

# The window <-> worker protocol's version (docs/protocol.md): bump it when a message or shared-file field changes.
# Reported in hello; a window whose PROTOCOL_VERSION (viewport/main.gd) differs starts its own worker.
PROTOCOL_VERSION = 5


def run_sync(session, req):
    ops = req["oplog"]["ops"] if "oplog" in req else req["ops"]
    if req.get("oplog", {}).get("units", "mm") != "mm":
        raise OpError("only mm supported")
    if req.get("drawing"):
        session.drawing = True
    how, ms = session.sync(ops)
    outdir = req.get("outdir") or os.path.dirname(session.path)
    export_ms = session.export(outdir)
    status = session.status()
    result = {"oplog": req.get("name", "live"), "total_ms": ms, "export_ms": export_ms, "how": how,
              "ops": status, "rev": session.rev + (1 if session.dirty else 0), "model": session.path}
    atomic_json(os.path.join(outdir, "status.json"), result)
    return result, outdir


def worker_files(folder=HERE):
    """The worker's own scripts: every .py beside replay.py except the tests, in name order."""
    return sorted(n for n in os.listdir(folder) if n.endswith(".py") and not n.startswith("test_"))


def worker_identity():
    """What a window compares before sharing this worker: the scripts it runs (same contents = same worker).
    MD5 of the worker_files() one after another; main.gd's _worker_identity() computes the same."""
    h = hashlib.md5()
    for name in worker_files():
        with open(os.path.join(HERE, name), "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def open_reply(s, seq):
    """The open reply for a session. A recovery (A32) is reported once: a later open of the same session doesn't."""
    resp = {"ok": True, "cmd": "open", "model": s.path, "rev": s.rev, "ops": [e["op"] for e in s.applied],
            "undo_floor": s.undo_floor, "external": s.external, "seq": seq}
    if s.recovered:
        resp["recovered"], s.recovered = s.recovered, None
    return resp


def serve(port):
    """Long-running worker: newline-delimited JSON over localhost TCP. One worker serves every Shop Sketch window,
    each on its own FreeCAD document; a model belongs to one window at a time (W13).
      {"cmd": "hello"} -> {"ok", "cmd": "hello", "app": "shopsketch", "protocol": PROTOCOL_VERSION,
                           "worker": <md5 of the worker's scripts>, "pid"}
      {"cmd": "open", "model": ".../model.FCStd", "fresh": false}
          -> {"ok", "cmd": "open", "ops", "undo_floor", "external", "rev", "recovered"?}
             recovered: {"from": "new"|"prev", "rev", "why"} once, when opening found a save that stopped part way
             and put the newest whole pair in place (A32)
          -> {"ok": false, "cmd": "open", "error": "already_open", "model"} when another window has it; that window
             is sent {"cmd": "focus", "model"} so it can come to the front
      {"cmd": "sync", "model": "...", "oplog": {...}, "outdir": "...", "seq": n, "drawing": false}
          -> {"ok", "cmd": "sync", "result": {...status...}, "outdir" (bodies.json, meshes/), "seq", "wall_ms"}
      {"cmd": "replay", ...}  same as sync on a fresh document (one-shot rebuild)
      {"cmd": "flush", "model"?}  save everything now (or only that model);  {"cmd": "bye"}  save this window's model and let it go
      {"cmd": "quit"}   save, and stop if no other window is connected (else just this window leaves)
          flush / bye / quit answer with what they saved and what they couldn't (T79):
          {"ok": <nothing failed>, "saved": [{"model", "rev"}], "failed": [{"model", "rev", "error"}], "error"?}
          quit stops even when a save failed (the window has asked you first, I55).
    The reply goes out first; the autosave waits until every window has been quiet for IDLE_SAVE_S, so quick
    successive actions never queue behind a save. When a save lands the window that owns the model is told:
          {"cmd": "saved", "model": "...", "rev": n}   (the viewport's quiet 'Saved' indicator, Q22)
    and when one fails: {"cmd": "save_failed", "model", "rev" (the one it tried), "error"}. A failed save stays
    pending: the autosave doesn't keep trying it, but the next sync, flush, bye or quit does (T79, I54).
    SERVE_IDLE_EXIT=<s>: save and exit that long after the last window leaves (the shared worker windows start)."""
    import select
    import socket
    sessions = {}
    to_save = {}          # session path -> (session, outdir)
    failed = set()        # paths in to_save whose last save failed: retried on the next sync or flush, not by the timer
    owners = {}           # model path -> the connection (window) that has it open
    clients = {}          # connection -> {"buf": bytes, "models": set of paths}
    IDLE_SAVE_S = 0.25
    idle_exit = float(os.environ.get("SERVE_IDLE_EXIT", "0") or 0)
    me = worker_identity()
    clock = {"active": time.monotonic(), "alone": None}

    def send(conn, obj):
        try:
            conn.sendall((json.dumps(obj) + "\n").encode())
        except OSError:
            pass

    def save_pending(paths=None, retry=True):
        """Save what's pending (only `paths`, if given). retry=False (the timer) skips saves that last failed.
        Returns {"saved": [{model, rev}], "failed": [{model, rev, error}]}; a failure stays pending (T79)."""
        out = {"saved": [], "failed": []}
        for path, (sess, od) in list(to_save.items()):
            if paths is not None and path not in paths:
                continue
            if not retry and path in failed:
                continue
            try:
                save_ms = sess.save(od)
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                print(f"WORKER save failed: {err}", flush=True)
                failed.add(path)
                msg = {"model": sess.path, "rev": sess.rev + 1, "error": err}
                out["failed"].append(msg)
                if owners.get(path) in clients:
                    send(owners[path], dict(msg, ok=False, cmd="save_failed"))
                continue
            print(f"WORKER saved rev {sess.rev} in {save_ms} ms", flush=True)
            to_save.pop(path, None)
            failed.discard(path)
            out["saved"].append({"model": sess.path, "rev": sess.rev})
            if owners.get(path) in clients:
                send(owners[path], {"ok": True, "cmd": "saved", "model": sess.path, "rev": sess.rev})
        return out

    def answer(conn, cmd, seq, saves, **extra):
        """flush / bye / quit's reply: what was saved and what couldn't be (ok only when nothing failed)."""
        resp = dict({"ok": not saves["failed"], "cmd": cmd, "seq": seq}, **saves, **extra)
        if saves["failed"]:
            resp["error"] = "; ".join(f"couldn't save {os.path.basename(f['model'])}: {f['error']}" for f in saves["failed"])
        send(conn, resp)

    def session_for(path, fresh=False, reload=False):
        path = os.path.abspath(path)
        if path in sessions and (fresh or (reload and sessions[path].changed_on_disk())):
            sessions.pop(path).close()
        if path not in sessions:
            sessions[path] = Session(path, fresh=fresh)
        return sessions[path]

    def let_go(conn, paths):
        saves = save_pending(set(paths))            # whatever it changed is saved before anyone else can open it
        for p in paths:
            clients[conn]["models"].discard(p)
            if owners.get(p) is conn:
                owners.pop(p)
        return saves

    def release(conn):
        if conn in clients:
            let_go(conn, list(clients[conn]["models"]))
            clients.pop(conn)
        try:
            conn.close()
        except OSError:
            pass
        if not clients:
            clock["alone"] = time.monotonic()

    def claim(conn, path):
        """This window takes the model (leaving the one it had). Returns the other window if it's taken."""
        other = owners.get(path)
        if other is not None and other is not conn and other in clients:
            return other
        let_go(conn, [p for p in clients[conn]["models"] if p != path])
        owners[path] = conn
        clients[conn]["models"].add(path)
        return None

    def handle(conn, line):
        t0 = time.perf_counter()
        after = None
        seq = cmd = None
        try:
            req = json.loads(line)
            cmd = req.get("cmd")
            seq = req.get("seq")
            if cmd == "length":                     # typed lengths with arithmetic, evaluated by FreeCAD (T32, I35)
                send(conn, length_input.handle(req))
                return None
            if cmd == "hello":
                send(conn, {"ok": True, "cmd": "hello", "seq": seq, "app": "shopsketch", "protocol": PROTOCOL_VERSION,
                            "worker": me, "pid": os.getpid()})
                return None
            if cmd == "quit":
                if len(clients) > 1:                # other windows still use this worker: only this one leaves
                    answer(conn, "quit", seq, let_go(conn, list(clients[conn]["models"])), stopped=False)
                    release(conn)
                    return None
                answer(conn, "quit", seq, save_pending(), stopped=True)
                return "stop"
            if cmd == "bye":
                answer(conn, "bye", seq, let_go(conn, list(clients[conn]["models"])))
                release(conn)
                return None
            if cmd == "flush":              # save now (tests, closing a window: "model" saves just that one)
                only = {os.path.abspath(req["model"])} if req.get("model") else None
                answer(conn, "flush", seq, save_pending(only))
                return None
            if req.get("delay_ms"):        # test hook: simulate a slow FreeCAD calculation
                time.sleep(float(req["delay_ms"]) / 1000.0)
            if cmd == "open":
                path = os.path.abspath(req["model"])
                other = claim(conn, path)
                if other is not None:
                    send(other, {"ok": True, "cmd": "focus", "model": path})
                    resp = {"ok": False, "cmd": "open", "error": "already_open", "model": path, "seq": seq}
                else:
                    s = session_for(path, fresh=req.get("fresh", False), reload=True)
                    resp = open_reply(s, seq)
            elif cmd == "inspect_properties":         # the Properties panel's snapshot of one piece (T46)
                model = os.path.abspath(req["model"])
                if claim(conn, model) is not None:
                    raise OpError("Model is open in another window")
                s = session_for(model)
                from object_properties import inspect
                resp = {"ok": True, "cmd": cmd, "seq": seq, "model": model,
                        "request_id": req["request_id"], "properties": inspect(s.model, req["body"])}
            elif cmd in ("sync", "replay"):
                model = os.path.abspath(req.get("model") or os.path.join(req["outdir"], "model.FCStd"))
                if claim(conn, model) is not None:
                    raise OpError(f"{os.path.basename(model)} is open in another window")
                s = session_for(model, fresh=(cmd == "replay"))
                res, outdir = run_sync(s, req)
                resp = {"ok": True, "cmd": "sync", "result": res, "outdir": outdir,
                        "seq": seq, "wall_ms": round((time.perf_counter() - t0) * 1000, 1)}
                if s.dirty or req.get("drawing"):
                    after = (s, outdir)
            else:
                raise OpError(f"unknown cmd '{cmd}'")
        except Exception as e:
            resp = {"ok": False, "cmd": cmd, "error": f"{type(e).__name__}: {e}", "seq": seq}
        if cmd == "inspect_properties":
            resp["request_id"] = req.get("request_id")
        send(conn, resp)
        if after:
            to_save[after[0].path] = after
            failed.discard(after[0].path)           # a new change: the timer tries its save again (T79)
        print(f"WORKER {cmd} seq={seq} {resp.get('wall_ms')} ms "
              f"{resp.get('result', {}).get('how', '') if resp.get('ok') else resp.get('error')}"
              f"  [{len(clients)} window{'s' if len(clients) != 1 else ''}]", flush=True)
        return None

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))          # port 0: the system picks a free one (T47), reported below
    srv.listen(16)
    port = srv.getsockname()[1]
    print(f"WORKER listening on 127.0.0.1:{port}" + (f" (exits {idle_exit:g} s after the last window)" if idle_exit else ""),
          flush=True)
    if os.environ.get("SERVE_PORT_FILE"):     # whoever started us learns the port from this file (written whole,
        tmp = os.environ["SERVE_PORT_FILE"] + ".tmp"     # after the line above, so its log already says so)
        with open(tmp, "w") as f:
            f.write(f"{port}\n")
        os.replace(tmp, os.environ["SERVE_PORT_FILE"])
    while True:
        readable, _, _ = select.select([srv] + list(clients), [], [], IDLE_SAVE_S)
        now = time.monotonic()
        if not readable:
            if to_save and now - clock["active"] >= IDLE_SAVE_S:
                save_pending(retry=False)
            if idle_exit and not clients and clock["alone"] is not None and now - clock["alone"] >= idle_exit:
                save_pending()
                print("WORKER no windows left: stopping", flush=True)
                return
            continue
        for sock in readable:
            if sock is srv:
                conn, _ = srv.accept()
                clients[conn] = {"buf": b"", "models": set()}
                clock["alone"] = None
                continue
            if sock not in clients:
                continue
            try:
                chunk = sock.recv(65536)
            except OSError:
                chunk = b""
            if not chunk:                   # the window went away: its last change still gets saved
                release(sock)
                continue
            clock["active"] = now
            st = clients[sock]
            st["buf"] += chunk
            while sock in clients and b"\n" in st["buf"]:
                line, st["buf"] = st["buf"].split(b"\n", 1)
                if line.strip() and handle(sock, line) == "stop":
                    return
            clock["active"] = time.monotonic()     # the quiet before an autosave counts from the last reply


def main():
    if os.environ.get("SERVE_PORT"):
        serve(int(os.environ["SERVE_PORT"]))
        return
    oplog_path = os.environ["OPLOG"]
    with open(oplog_path) as f:
        log = json.load(f)
    outdir = os.environ["OUTDIR"]
    s = Session(os.path.join(outdir, "model.FCStd"), fresh=True)
    res, _ = run_sync(s, {"oplog": log, "outdir": outdir, "drawing": True, "name": os.path.basename(oplog_path)})
    s.save(outdir)
    ok = sum(1 for e in res["ops"] if e["status"] == "ok")
    print(f"REPLAY: {ok}/{len(res['ops'])} ops ok in {res['total_ms']} ms")
    for e in res["ops"]:
        if e["status"] != "ok":
            print(f"REPLAY FAILED {e['id']}: {e['message']}")
    s.close()
