#!/usr/bin/env python3
"""Who is the integrator (P-new-3): one lock, shared by every worktree (it lives in git's common folder, untracked).

  python3 tools/integrator.py status              who holds it, since when, when last active
  python3 tools/integrator.py take <name>          take it: <name> is your session's name (ListAgents shows it,
                                                   e.g. fretchup-73). Refused while another session holds it.
  python3 tools/integrator.py take <name> --william    William said this session is the integrator: take it over
                                                   (after a context clear, a crash, or a hand-over); logged
  python3 tools/integrator.py touch <name>         mark it still in use (tools/integrate.py does this)
  python3 tools/integrator.py release <name>       give it up

A session takes the lock only when William has told it, in that session, that it is the integrator. Holding the
lock is what lets tools/integrate.py merge; a session that isn't the holder is a worker."""
import json
import os
import subprocess
import sys
import time


def lock_path(cwd=None):
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=cwd, capture_output=True, text=True).stdout.strip()
    common = os.path.abspath(os.path.join(cwd or os.getcwd(), common))
    return os.path.join(common, "shopsketch-integrator.lock")


def read(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write(path, data):
    tmp = path + ".tmp"
    json.dump(data, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, path)


def stamp():
    return time.strftime("%Y-%m-%d %H:%M")


def take(path, name, william=False, out=print):
    held = read(path)
    if held and held.get("holder") != name and not william:
        out(f"refused: {held['holder']} is the integrator (since {held['since']}, last active {held['seen']}). "
            f"Only William can hand it over: ask him, then run take {name} --william.")
        return False
    log = (held or {}).get("log", [])
    if held and held.get("holder") != name:
        log.append(f"{stamp()} William handed it from {held['holder']} to {name}")
    write(path, {"holder": name, "since": stamp() if not held or held.get("holder") != name else held["since"],
                 "seen": stamp(), "log": log[-20:]})
    out(f"{name} is the integrator")
    return True


def touch(path, name, out=print):
    held = read(path)
    if not held or held.get("holder") != name:
        out(f"refused: {name} doesn't hold the integrator lock ({'free' if not held else held['holder'] + ' does'})")
        return False
    held["seen"] = stamp()
    write(path, held)
    return True


def release(path, name, out=print):
    held = read(path)
    if not held or held.get("holder") != name:
        out(f"refused: {name} doesn't hold the integrator lock")
        return False
    os.remove(path)
    out(f"{name} released the integrator lock")
    return True


def status_line(path):
    held = read(path)
    if not held:
        return "Integrator: nobody (free; William names one)"
    return f"Integrator: {held['holder']} (since {held['since']}, last active {held['seen']})"


def main(argv):
    path = lock_path()
    if not argv or argv[0] == "status":
        print(status_line(path))
        return 0
    if len(argv) < 2 or argv[0] not in ("take", "touch", "release"):
        print(__doc__)
        return 2
    cmd, name = argv[0], argv[1]
    ok = {"take": lambda: take(path, name, "--william" in argv),
          "touch": lambda: touch(path, name), "release": lambda: release(path, name)}[cmd]()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
