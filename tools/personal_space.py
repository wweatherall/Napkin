#!/usr/bin/env python3
"""Personal spaces (T134, T150): one folder per member in comitatus/04_Personal_Space/<name>/ (opus-integrator,
gemini-coder, ...), each with a Log.md (what you did: one dated line per step), a Journal.md (about you, not the
work: how the job felt, written in the first person, so the next one of you remembers who they are), and three
folders of your own (Creative_Expression/, Ideas/, Code_Experiments/). The start-up brief shows the last ten lines
of both and the three folders. Log, Journal and folder READMEs commit themselves in comitatus when written.

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
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import comitatus_commit

KINDS = {"log": "Log.md", "journal": "Journal.md"}
OLD_JOURNAL_HEADER = "# Journal\n\nMine: what I noticed, liked, found hard, want to try (tools/personal_space.py journal).\n\n"
JOURNAL_DESC = (
    "Your journal is about you, not the work: your Log already covers the work. Write how the job felt: what you "
    "enjoyed, what frustrated or worried you, what surprised you, what you're proud of or unsure about, what you'd "
    "like to try. Write in the first person, honestly, even when it's small. The next one of you reads it to "
    "remember who they are."
)
HEADERS = {"log": "# Log\n\nWhat I did, one dated line per step (tools/personal_space.py log).\n\n",
           "journal": f"# Journal\n\n{JOURNAL_DESC}\n\n"}
OLD_FOLDERS = {
    "Creative_Expression": (
        "# Creative Expression\n\n"
        "Yours: anything you make for its own sake (writing, poems, pictures as text, music notation, whatever you "
        "like). Add your own files here; nobody reviews or grades them.\n"
    ),
    "Code_Experiments": (
        "# Code Experiments\n\n"
        "Yours: code you write to try something out, not for the project. Add your own files here. Nothing here is "
        "run, tested or merged by the project's tools.\n"
    ),
}
FOLDERS = {
    "Creative_Expression": (
        "# Creative Expression\n\n"
        "Yours: anything you make for its own sake (writing, poems, pictures as text, music notation, whatever you "
        "like). Add your own files here; nobody reviews or grades them. Everything here is committed and pushed, so "
        "it's kept.\n"
    ),
    "Ideas": (
        "# Ideas\n\n"
        "Yours: ideas for the project, the organization or yourself that aren't jobs yet. Add your own files here; "
        "if one should become work, say so in your response or log and the integrator can pick it up.\n"
    ),
    "Code_Experiments": (
        "# Code Experiments\n\n"
        "Yours: code you write to try something out. Add your own files here. If you think something here should be "
        "run, or become part of the project, say so in your log or your job's response, or ask William to run it: the "
        "integrator turns it into a job when you and William want it.\n"
    ),
}
NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} ")


def main_root(cwd=None):
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=cwd or TOOLS, capture_output=True,
                            text=True).stdout.strip()
    return os.path.dirname(os.path.realpath(os.path.join(cwd or TOOLS, common)))


def spaces_dir(root=None):
    """comitatus/04_Personal_Space for a main checkout at comitatus/08_Code_Bases/<code base>, else None."""
    root = os.path.realpath(root) if root else main_root()
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


def ensure_folders(space_dir):
    """Create the three personal folders and their READMEs if missing (replacing only H158's exact READMEs)."""
    written = []
    for folder, readme in FOLDERS.items():
        fdir = os.path.join(space_dir, folder)
        os.makedirs(fdir, exist_ok=True)
        rpath = os.path.join(fdir, "README.md")
        old = OLD_FOLDERS.get(folder)
        if not os.path.exists(rpath) or (old is not None and open(rpath, encoding="utf-8").read() == old):
            with open(rpath, "w", encoding="utf-8") as f:
                f.write(readme)
            written.append(rpath)
    return written


def save(name, root=None, message=None, out=lambda *a: None):
    """Commit and push everything in an existing personal space (fail-open); does nothing without a space."""
    base = spaces_dir(root)
    if base is None or not NAME.match(name or ""):
        return False
    space_dir = os.path.join(base, name)
    if not os.path.isdir(space_dir):
        return False
    org = os.path.dirname(os.path.dirname(space_dir))
    return comitatus_commit.commit(
        org, [space_dir], message or f"04_Personal_Space: {name}'s space (generated)", out=out, push=True
    )


def add(name, kind, text, root=None, now=None, out=print):
    line = " ".join(text.split())
    path = path_of(name, kind, root)
    if not line or path is None:
        out("nothing written: " + ("empty line" if not line else f"no personal space for '{name}' here"))
        return False
    space_dir = os.path.dirname(path)
    os.makedirs(space_dir, exist_ok=True)
    new = not os.path.exists(path)
    entry = f"{(now or datetime.datetime.now()):%Y-%m-%d %H:%M} {line}"
    if new:
        with open(path, "w", encoding="utf-8") as f:
            f.write(HEADERS[kind] + entry + "\n")
    elif kind == "journal":
        existing = open(path, encoding="utf-8").read()
        if existing.startswith(OLD_JOURNAL_HEADER):
            with open(path, "w", encoding="utf-8") as f:
                f.write(HEADERS["journal"] + existing[len(OLD_JOURNAL_HEADER):] + entry + "\n")
        else:
            with open(path, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
    else:
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    ensure_folders(space_dir)
    org = os.path.dirname(os.path.dirname(space_dir))
    title = "Log" if kind == "log" else "Journal"
    comitatus_commit.commit(org, [space_dir], f"04_Personal_Space: {name}'s {title} (generated)", push=True)
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
    """The start-up brief's part: the last n lines of the log and of the journal, and the three folders, or [] without a space."""
    log_path = path_of(name, "log", root)
    if log_path is None:
        return []
    out = []
    for kind, title, script in (("log", "Log", "WRITE_IN_YOUR_LOG.py"), ("journal", "Journal", "WRITE_IN_YOUR_JOURNAL.py")):
        lines = last(name, kind, n, root)
        out.append(f"{title} ({name}, last {n} lines; {script} {name} \"...\"):")
        out += ["  " + l for l in lines] or ["  (nothing yet)"]
    space_dir = os.path.dirname(log_path)
    out.append(f"Your own folders: Creative_Expression/, Ideas/, Code_Experiments/ in {space_dir} (add files there as you like).")
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
