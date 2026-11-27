#!/usr/bin/env python3
"""Who is the integrator (P19): one lock, shared by every worktree (it lives in git's common folder, untracked).

  python3 tools/integrator.py status              who holds it, since when, when last active
  python3 tools/integrator.py take <name>          take it: <name> is your session's name (ListAgents shows it,
                                                   e.g. fretchup-73). Refused while another session holds it.
  python3 tools/integrator.py take <name> --william [--archive <ID> [--commit | --push]]
                                                   William said this session is the integrator: take it over
                                                   (after a context clear, a crash, or a hand-over); logged.
                                                   With --archive <ID>, also archive that pre-/clear note once
                                                   the lock is taken (--commit stages+commits; --push also pushes main)
  python3 tools/integrator.py touch <name>         mark it still in use (tools/integrate.py does this)
  python3 tools/integrator.py release <name>       give it up
  python3 tools/integrator.py note "<line>"        append one line to the integrator's Log (personal space, T134)

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


def journal_path(cwd=None):
    return os.path.join(os.path.dirname(lock_path(cwd)), "shopsketch-integrator-journal.log")


def note(path, text, limit=20, out=print):
    line = " ".join(text.split())
    if not line:
        out("note cannot be empty")
        return False
    existing = []
    if os.path.isfile(path):
        existing = [l.rstrip() for l in open(path, encoding="utf-8").read().splitlines() if l.strip()]
    entry = f"{stamp()} {line}"
    kept = (existing + [entry])[-limit:]
    tmp = path + ".tmp"
    open(tmp, "w", encoding="utf-8").write("\n".join(kept) + "\n")
    os.replace(tmp, path)
    out(entry)
    return True


def log_note(text, root=None, out=print):
    """A note goes to the integrator's Log in its personal space (T134), found from the checkout at `root` (a test
    repo has none); without one, to the old journal file in that checkout's .git."""
    try:
        import personal_space
        import startup
        main = personal_space.main_root(root or os.getcwd())
        if personal_space.path_of(startup.INTEGRATOR_SPACE, "log", main) is not None:
            return personal_space.add(startup.INTEGRATOR_SPACE, "log", text, root=main, out=out)
    except ImportError:
        pass
    return note(journal_path(root), text, out=out)


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


def parse_take_args(argv):
    """Parse flags after `take <name>` -> (william, archives, commit, push, error)."""
    william, archives, commit, push, i = False, [], False, False, 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--william":
            william = True
            i += 1
        elif arg == "--archive":
            if i + 1 >= len(argv) or argv[i + 1].startswith("-"):
                return False, [], False, False, "take --archive needs a handoff ID (e.g. H134)"
            archives.append(argv[i + 1])
            i += 2
        elif arg == "--commit":
            commit = True
            i += 1
        elif arg == "--push":
            push = True
            i += 1
        else:
            return False, [], False, False, f"unknown flag for take: {arg}"
    if (commit or push) and not archives:
        return False, [], False, False, "--commit / --push require --archive <ID>"
    return william, archives, commit or push, push, None


def take_and_archive(path, name, william=False, archives=(), commit=False, push=False, root=None, out=print):
    """Take the integrator lock, then (only if granted) archive any listed state notes."""
    if not take(path, name, william=william, out=out):
        return False
    if not archives:
        return True
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import handoff
    repo = root or os.path.normpath(os.path.join(here, ".."))
    for idx, hid in enumerate(archives):
        head, sha, pushed = handoff.archive_and_commit(repo, hid, commit=commit or push, push=push and idx == len(archives) - 1)
        out(f"archived {head}")
        if sha:
            out(f"committed {sha} Archive {head}")
        if pushed:
            out("pushed main")
    return True


def main(argv):
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    path = lock_path()
    if not argv or argv[0] == "status":
        print(status_line(path))
        return 0
    if len(argv) < 2 or argv[0] not in ("take", "touch", "release", "note"):
        print(__doc__)
        return 2
    cmd, name = argv[0], argv[1]
    try:
        if cmd == "note":
            ok = log_note(" ".join(argv[1:]))
        elif cmd == "take":
            william, archives, commit, push, err = parse_take_args(argv[2:])
            if err:
                print(err)
                print(__doc__)
                return 2
            ok = take_and_archive(path, name, william=william, archives=archives, commit=commit, push=push)
        else:
            ok = {"touch": lambda: touch(path, name), "release": lambda: release(path, name)}[cmd]()
    except PermissionError as exc:
        print(f"cannot write integrator lock: {exc} (re-run outside sandbox)")
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
