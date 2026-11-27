#!/usr/bin/env python3
"""Personal spaces (T134): one folder per member in comitatus/04_Personal_Space/<name>/ (opus-integrator,
gemini-coder, ...), each with a Log.md (what you did: one dated line per step) and a Journal.md (yours: what you
noticed, liked, found hard, want to try; personal, not a work record). The start-up brief shows the last ten lines
of both, so a new session remembers who it is and what it was doing.

  python3 tools/personal_space.py log <name> "<line>"        append a dated line to your Log.md
  python3 tools/personal_space.py journal <name> "<line>"    append a dated line to your Journal.md
  python3 tools/personal_space.py show <name> [N]            the last N (10) lines of each

Both files keep every line (nothing is cut). A checkout that isn't in comitatus/08_Code_Bases has no personal
spaces: the commands say so and do nothing."""
import datetime
import os
import re
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
KINDS = {"log": "Log.md", "journal": "Journal.md"}
HEADERS = {"log": "# Log\n\nWhat I did, one dated line per step (tools/personal_space.py log).\n\n",
           "journal": "# Journal\n\nMine: what I noticed, liked, found hard, want to try (tools/personal_space.py journal).\n\n"}
NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} ")


def main_root(cwd=None):
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=cwd or TOOLS, capture_output=True,
                            text=True).stdout.strip()
    return os.path.dirname(os.path.realpath(os.path.join(cwd or TOOLS, common)))


def spaces_dir(root=None):
    """comitatus/04_Personal_Space for a main checkout at comitatus/08_Code_Bases/<code base>, else None."""
    root = root or main_root()
    parent = os.path.dirname(root)
    org = os.path.dirname(parent)
    if os.path.basename(parent) != "08_Code_Bases" or not os.path.isdir(os.path.join(org, "04_Personal_Space")):
        return None
    return os.path.join(org, "04_Personal_Space")


def path_of(name, kind, root=None):
    base = spaces_dir(root)
    if base is None or not NAME.match(name or ""):
        return None
    return os.path.join(base, name, KINDS[kind])


def add(name, kind, text, root=None, now=None, out=print):
    line = " ".join(text.split())
    path = path_of(name, kind, root)
    if not line or path is None:
        out("nothing written: " + ("empty line" if not line else f"no personal space for '{name}' here"))
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    entry = f"{(now or datetime.datetime.now()):%Y-%m-%d %H:%M} {line}"
    with open(path, "a", encoding="utf-8") as f:
        f.write((HEADERS[kind] if new else "") + entry + "\n")
    out(entry)
    return True


def last(name, kind, n=10, root=None):
    """The last n dated lines of a member's Log.md or Journal.md ([] when there are none)."""
    path = path_of(name, kind, root)
    if path is None or not os.path.isfile(path):
        return []
    lines = [l.rstrip() for l in open(path, encoding="utf-8").read().splitlines() if LINE.match(l)]
    return lines[-n:]


def brief_lines(name, n=10, root=None):
    """The start-up brief's part: the last n lines of the log and of the journal, or [] without a space."""
    if path_of(name, "log", root) is None:
        return []
    out = []
    for kind, title, script in (("log", "Log", "WRITE_IN_YOUR_LOG.py"), ("journal", "Journal", "WRITE_IN_YOUR_JOURNAL.py")):
        lines = last(name, kind, n, root)
        out.append(f"{title} ({name}, last {n} lines; {script} {name} \"...\"):")
        out += ["  " + l for l in lines] or ["  (nothing yet)"]
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) >= 3 and argv[0] in KINDS:
        return 0 if add(argv[1], argv[0], " ".join(argv[2:])) else 1
    if len(argv) in (2, 3) and argv[0] == "show":
        print("\n".join(brief_lines(argv[1], int(argv[2]) if len(argv) == 3 else 10)) or "no personal spaces here")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
