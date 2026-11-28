# runner: none (shared worker-link and failure-path test helpers, not a test)
"""Shared worker-link and failure-path helpers for worker tests (T110, P42).

Reach for these when writing worker protocol, saving, or outside-save checks:
- start_worker() / Worker: run an isolated worker on a free port (T47).
  P42 worker gone: Worker.kill() (SIGKILL, no goodbye), then Worker.restart().
- Window: stand-in Napkin window with its own seq numbering.
  P42 reply late or out of order: Window.send() twice before reading with wait().
  P42 window gone: Window.drop() (closes the socket without bye).
- read_only(folder): P42 save that fails (PermissionError; restored on exit).
- unreadable(path): P42 file unreadable (non-FCStd bytes; original restored on exit).
- missing(path): P42 file missing (moved aside; original restored on exit).
- fresh_model(), board_ops(), sync(), freecad_save(), Checks: common test scaffolding.
"""
import contextlib
import json
import os
import shutil
import socket
import stat
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FC = os.environ.get("FREECAD", "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd")


class Checks:
    """Pass/fail counter and summary line printer (`<NAME> TESTS: N passed, M failed`)."""
    def __init__(self, name):
        self.name = name
        self.passed = 0
        self.failed = 0

    def check(self, label, cond, detail=""):
        if cond:
            self.passed += 1
        else:
            self.failed += 1
        print(("PASS " if cond else "FAIL ") + label + ("" if cond else f"  {detail}"), flush=True)
        return bool(cond)

    def done(self):
        print(f"\n{self.name} TESTS: {self.passed} passed, {self.failed} failed", flush=True)
        return 1 if self.failed else 0


class Window:
    """A stand-in for one Napkin window over TCP, with its own seq numbering.

    Reach for Window.send() twice before reading to test P42 late/out-of-order replies,
    and Window.drop() to test P42 window gone (disconnect without bye).
    """
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=60)
        self.buf = b""
        self.extra = []                     # unsolicited events (saved, focus, outside_save)
        self.seq = 0

    def next_seq(self):
        self.seq += 1
        return self.seq

    def send(self, req):
        """Send a request without waiting for its reply. Assigns a fresh seq unless req already sets one."""
        msg = dict(req)
        if "seq" not in msg:
            msg["seq"] = self.next_seq()
        self.sock.sendall((json.dumps(msg) + "\n").encode())
        return msg.get("seq")

    def ask(self, req, want, timeout=60, model=None):
        """Send a request and wait for the matching reply."""
        self.send(req)
        return self.wait(want, timeout=timeout, model=model)

    def wait(self, want, timeout=60, model=None):
        """Wait for a message with cmd == want (and optional model). Other messages stay in self.extra."""
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
            try:
                self.sock.settimeout(max(0.001, deadline - time.monotonic()))
                chunk = self.sock.recv(65536)
            except (socket.timeout, ConnectionResetError, BrokenPipeError, OSError):
                return None
            finally:
                try:
                    self.sock.settimeout(60)
                except OSError:
                    pass
            if not chunk:
                return None
            self.buf += chunk
        return None

    def drop(self):
        """Close the socket at once without sending bye (P42: window gone)."""
        try:
            self.sock.close()
        except OSError:
            pass

    def close(self):
        self.drop()


class Worker:
    """A running FreeCAD worker started on its own free port (T47).

    Reach for kill() then restart() for the P42 worker-gone case, and stop() for a clean shutdown.
    """
    def __init__(self, folder, port, proc, log, env):
        self.folder = folder
        self.port = port
        self.proc = proc
        self.log = log
        self._env = dict(env)

    def kill(self):
        """SIGKILL the worker with no goodbye (P42: worker gone)."""
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(timeout=30)

    def stop(self, timeout=20):
        """Ask the worker to quit cleanly, then wait; falls back to kill() if unreachable."""
        if self.proc.poll() is not None:
            return self.proc.returncode
        try:
            win = Window(self.port)
            try:
                win.ask({"cmd": "quit"}, "quit", timeout=5)
            finally:
                win.drop()
            return self.proc.wait(timeout=timeout)
        except Exception:
            self.kill()
            return self.proc.returncode

    def restart(self):
        """Start a fresh worker on a new port in the same folder (P42: after worker gone)."""
        if self.proc.poll() is None:
            self.stop()
        return start_worker(self.folder, _append_log=True, **self._env)


def start_worker(folder, _append_log=False, **env):
    """Start a worker on port 0 in `folder` (SERVE_PORT_FILE, T47). Returns a Worker.

    Reach for this in any worker-link test; pass env overrides like SERVE_IDLE_EXIT="2" as keyword args.
    """
    folder = os.path.abspath(folder)
    os.makedirs(folder, exist_ok=True)
    port_file = os.path.join(folder, "worker.port")
    log_path = os.path.join(folder, "worker.log")
    if os.path.exists(port_file):
        os.remove(port_file)
    proc_env = dict(os.environ, SERVE_PORT="0", SERVE_PORT_FILE=port_file, SERVE_IDLE_EXIT="2")
    for k, v in env.items():
        proc_env[k] = str(v)
    with open(log_path, "a" if _append_log else "w") as log_fh:
        proc = subprocess.Popen([FC, os.path.join(HERE, "replay.py")],
                                env=proc_env, stdout=log_fh, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 60
    port = 0
    while time.monotonic() < deadline:
        if os.path.exists(port_file):
            raw = open(port_file).read().strip()
            if raw:
                port = int(raw)
                break
        if proc.poll() is not None:
            break
        time.sleep(0.05)
    return Worker(folder, port, proc, log_path, env)


def fresh_model(folder, name):
    """Create a clean subfolder `<folder>/<name>/` and return `<folder>/<name>/<name>.FCStd`."""
    sub = os.path.join(folder, name)
    shutil.rmtree(sub, ignore_errors=True)
    os.makedirs(sub)
    return os.path.join(sub, name + ".FCStd")


def board_ops(width, rid="r1", bid="b1", origin=(0, 0, 0), ppid=None):
    """Return rect + push_pull ops for one 100 mm x 18 mm board of the given width."""
    if ppid is None:
        ppid = "pp" + rid[1:] if rid.startswith("r") and rid[1:].isdigit() else f"pp_{rid}"
    return [
        {"id": rid, "type": "rect", "plane": {"normal": [0, 0, 1], "origin": list(origin)}, "size": [width, 100]},
        {"id": ppid, "type": "new_board", "target": {"rect": rid}, "distance": 18, "body": bid},
    ]


def sync(window, model, ops, outdir=None, seq=None):
    """Send a sync for `model` with `ops` using `window`'s own seq (or an explicit seq) and return its reply."""
    out = outdir or (model + "-out")
    os.makedirs(out, exist_ok=True)
    req = {"cmd": "sync", "model": model, "outdir": out,
           "oplog": {"format": "oplog/0.1", "units": "mm", "ops": ops}}
    if seq is not None:
        req["seq"] = seq
    return window.ask(req, "sync")


_FREECAD_EDIT_SCRIPT = '''import json, os, FreeCAD as App
doc = App.openDocument(os.environ["EDIT_MODEL"])
edits = json.loads(os.environ["EDIT_META"])
if edits:
    meta = doc.Meta
    for key, value in edits.items():
        if value is None:
            meta.pop(key, None)
        else:
            meta[key] = value
    doc.Meta = meta
ex = [o for o in doc.Objects if o.TypeId == "Part::Extrusion"][0]
ex.LengthFwd = ex.LengthFwd.Value + float(os.environ.get("EDIT_ADD", "12"))
doc.recompute()
doc.save()
App.closeDocument(doc.Name)
'''


def freecad_save(model, add=12, **meta):
    """Open `model` in FreeCAD, make its first board thicker by `add` mm, optionally edit Meta, then save."""
    script = model + ".freecad_edit.py"
    with open(script, "w") as f:
        f.write(_FREECAD_EDIT_SCRIPT)
    try:
        subprocess.run(
            [FC, script],
            env=dict(os.environ, EDIT_MODEL=model, EDIT_ADD=str(add), EDIT_META=json.dumps(meta)),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120, check=True,
        )
    finally:
        if os.path.exists(script):
            os.remove(script)


@contextlib.contextmanager
def read_only(folder):
    """Make `folder` read-only so the next save fails with PermissionError; restore on exit (P42: save that fails)."""
    prev = stat.S_IMODE(os.stat(folder).st_mode)
    os.chmod(folder, 0o555)
    try:
        yield folder
    finally:
        os.chmod(folder, prev)


@contextlib.contextmanager
def unreadable(path, data=b"not a FreeCAD file"):
    """Replace `path` with non-FCStd bytes and put the original back on exit (P42: file unreadable)."""
    existed = os.path.exists(path)
    orig = open(path, "rb").read() if existed else None
    tmp_path = path + ".unreadable.tmp"
    with open(tmp_path, "wb") as f:
        f.write(data)
    os.replace(tmp_path, path)
    try:
        yield path
    finally:
        if existed:
            with open(tmp_path, "wb") as f:
                f.write(orig)
            os.replace(tmp_path, path)
        elif os.path.exists(path):
            os.remove(path)


@contextlib.contextmanager
def missing(path):
    """Move `path` aside and put it back on exit (P42: file missing)."""
    backup = os.path.join(os.path.dirname(os.path.abspath(path)),
                          "." + os.path.basename(path) + ".missing-backup")
    moved = False
    if os.path.exists(path):
        os.replace(path, backup)
        moved = True
    try:
        yield path
    finally:
        if moved and os.path.exists(backup):
            os.replace(backup, path)
