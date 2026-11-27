#!/usr/bin/env python3
"""Give placeholder IDs their numbers at merge (T74), so two branches never take the same number.

A branch that needs a new decision, Work list item, question or handoff entry writes a placeholder: the kind's
letter, "-new-" and a number of its own (I-new-N, T-new-N, Q-new-N, H-new-N with N = 1, 2 ...; a letter after N
is kept, so I-new-Nb becomes I49b). Only placeholders that are IDs are numbered (H073): a decision-log row the
branch adds (`| I-new-N |`) or its ### section, a docs/handoff/ entry's file name or ### heading, and every
reference to those. Any other placeholder (an example in prose) is left as written and reported as
"not numbered: <file>:<line>"; examples are best written with N instead of a digit all the same. The integrator merges with `git merge --no-ff --no-commit <branch>`, runs this, then commits:
each placeholder becomes the next free number of its kind, the same number everywhere it is cited, in every
tracked text file; a handoff file named after one is renamed (docs/handoff/H-new-N-slug.md -> H037-slug.md), the
decision log is sorted again and the handoff's open list is rebuilt (tools/handoff.py). Run it after each merge,
before the next: two branches merged together would share their I-new-N.

  python3 tools/number_ids.py              number them; prints each placeholder, its number and the files
  python3 tools/number_ids.py --dry-run    print what it would do, change nothing

"Next free" counts the IDs that are taken: the decision log's table rows and ### sections, in both its files
(03_Past_Decisions/decision-log.md and 03_Past_Decisions/decision-archive.md, P23), the ### headings of the
handoff, its archive and docs/handoff/, and the handoff files' names. Numbers are padded like the kind's
existing IDs (A01, T7, H036)."""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handoff
import sort_decision_log

PLACEHOLDER = re.compile(r"\b([A-Z]+)-new-(\d+)([a-z]*)\b")
DEFINES_ROW = re.compile(r"^\| ([A-Z]+)-new-(\d+)[a-z]* \|")
DEFINES_HEADING = re.compile(r"^### ([A-Z]+)-new-(\d+)[a-z]*\b")
DEFINES_FILE = re.compile(r"^([A-Z]+)-new-(\d+)[a-z]*-")
DEFINES_ENTRY = re.compile(r"^([A-Z]+)-new-(\d+)[a-z]*\.md$")
TAKEN = re.compile(r"^([A-Z]+)(\d+)[a-z]*$")
LOG = sort_decision_log.LIVE
ARCHIVE = sort_decision_log.ARCHIVE
ENTRY_FOLDERS = [sort_decision_log.RULINGS_DIR, sort_decision_log.WORK_DIR, sort_decision_log.QUESTIONS_DIR]
ID_FILES = [LOG, ARCHIVE, "docs/agent-handoff.md", "docs/handoff-archive.md"]
HISTORY_FILES = (ARCHIVE, "docs/handoff-archive.md")
SKIP = {"tools/test_number_ids.py", "tools/test_log_archive.py"}   # their checks are written with real placeholders


def taken(root):
    """{kind: (highest number taken, narrowest digit width seen)} from the files that define IDs."""
    found = {}

    def see(token):
        m = TAKEN.match(token)
        if m:
            k, digits = m.group(1), m.group(2)
            hi, w = found.get(k, (0, len(digits)))
            found[k] = (max(hi, int(digits)), min(w, len(digits)))

    paths = [os.path.join(root, p) for p in ID_FILES]
    for efolder in ENTRY_FOLDERS:
        for ident in sort_decision_log.folder_ids(os.path.join(root, efolder)):
            see(ident)
    cdir = sort_decision_log.comitatus_rulings_dir(root)
    if cdir:
        for ident in sort_decision_log.folder_ids(cdir):
            see(ident)
    folder = os.path.join(root, handoff.FOLDER)
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            see(name.split("-")[0])
            paths.append(os.path.join(folder, name))
    for path in paths:
        if not os.path.isfile(path):
            continue
        for line in open(path, encoding="utf-8"):
            if line.startswith("### "):
                see(line[4:].split()[0] if line[4:].split() else "")
            elif path.endswith((LOG, ARCHIVE)) and line.startswith("| "):
                see(line.split("|")[1].strip())
    return found


def tracked(root):
    """Text files git tracks (plus new ones not yet added), relative to root."""
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                             capture_output=True, text=True, check=True).stdout.strip()
        if os.path.realpath(top) != os.path.realpath(root):
            # A scratch fixture inside a checkout is its own tree, not that checkout's tracked files.
            raise OSError("root is nested inside another repository")
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=root,
                             capture_output=True, text=True, check=True).stdout.split("\n")
    except (OSError, subprocess.CalledProcessError):
        out = []
        for d, _, names in os.walk(root):
            out += [os.path.relpath(os.path.join(d, n), root) for n in names]
    return sorted(p for p in out if p and p not in SKIP and os.path.isfile(os.path.join(root, p)))


def read_text(path):
    try:
        return open(path, encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        return None


def _head_text(root, rel):
    """HEAD:<rel> when root is a git checkout with HEAD, else None."""
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                             capture_output=True, text=True, check=True).stdout.strip()
        if os.path.realpath(top) != os.path.realpath(root):
            return None
        r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=root, capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.CalledProcessError):
        return None


def _archived_lines(root, rel, text):
    """1-based line numbers in a history file that belong to already-archived entries (never rewritten)."""
    if rel not in HISTORY_FILES or not text:
        return set()
    lines = text.split("\n")
    head = _head_text(root, rel)
    skip = set()
    if rel == "docs/handoff-archive.md":
        head_chunks = {c.strip() for c in re.split(r"(?m)(?=^### )", head) if c.strip()} if head is not None else set()
        head_ids = {m.group(1) for m in re.finditer(r"(?m)^### ([A-Z]+\d+[a-z]*)\b", head)} if head is not None else set()
        i = 0
        while i < len(lines):
            if lines[i].startswith("### "):
                j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith("### ")), len(lines))
                chunk = "\n".join(lines[i:j]).strip()
                m = re.match(r"^### ([A-Z]+\d+[a-z]*)\b", lines[i])
                is_old = (chunk in head_chunks or (m and m.group(1) in head_ids)) if head is not None else bool(m)
                if is_old:
                    skip.update(range(i + 1, j + 1))
                i = j
            else:
                i += 1
        return skip
    # decision-archive.md: lines/Details sections already in HEAD (or numbered rows/sections when outside git)
    if head is not None:
        head_lines = set(head.split("\n"))
        head_ids = {m.group(1) for m in re.finditer(r"(?m)^### ([A-Z]+\d+[a-z]*)\b", head)}
        in_old_details = False
        for idx, line in enumerate(lines, 1):
            if line.startswith("### "):
                m = re.match(r"^### ([A-Z]+\d+[a-z]*)\b", line)
                in_old_details = bool(m and m.group(1) in head_ids)
            elif line.startswith("## "):
                in_old_details = False
            if in_old_details or (line.strip() and line in head_lines):
                skip.add(idx)
        return skip
    in_old_details = False
    for idx, line in enumerate(lines, 1):
        if line.startswith("### "):
            in_old_details = bool(re.match(r"^### ([A-Z]+\d+[a-z]*)\b", line))
        elif line.startswith("## "):
            in_old_details = False
        if in_old_details or (line.startswith("| ") and not DEFINES_ROW.match(line)):
            skip.add(idx)
    return skip


def defined(root, files):
    """{(kind, n)} of the placeholders that are IDs (H073): a ruling file (`rulings/I-new-N.md`), a decision-log
    row a branch adds (`| X-new-N |`) or its `### X-new-N` Details section, in either log file; in docs/handoff/,
    an entry's file name (H-new-N-slug.md) or its `### H-new-N` heading. Only these are numbered; the rest are
    examples in prose."""
    found = set()
    entry_prefixes = tuple(f.rstrip("/") + "/" for f in ENTRY_FOLDERS)
    for rel in files:
        if rel.startswith(entry_prefixes):
            m = DEFINES_ENTRY.match(os.path.basename(rel))
            if m:
                found.add((m.group(1), int(m.group(2))))
            continue
        in_log = rel in (LOG, ARCHIVE)
        in_handoff = rel.startswith(handoff.FOLDER.rstrip("/") + "/")
        in_handoff_archive = rel == "docs/handoff-archive.md"
        if not (in_log or in_handoff or in_handoff_archive):
            continue
        if in_handoff:
            m = DEFINES_FILE.match(os.path.basename(rel))
            if m:
                found.add((m.group(1), int(m.group(2))))
        text = read_text(os.path.join(root, rel)) or ""
        archived = _archived_lines(root, rel, text) if rel in HISTORY_FILES else set()
        for idx, line in enumerate(text.split("\n"), 1):
            if idx in archived:
                continue
            m = DEFINES_HEADING.match(line) or (in_log and DEFINES_ROW.match(line))
            if m:
                found.add((m.group(1), int(m.group(2))))
    return found


def plan(root, files=None):
    """Work out the numbers without changing anything.
    Returns (numbers {(kind, n): new ID without letter}, cited {(kind, n): [files]}, renames [(old, new)],
    left [(file, line, placeholder)]: placeholders that match no row or entry, so they stay as written)."""
    files = tracked(root) if files is None else files
    ids = defined(root, files)
    cited, left = {}, []

    def cite(key, rel):
        where = cited.setdefault(key, [])
        if rel not in where:
            where.append(rel)

    for rel in files:
        for m in PLACEHOLDER.finditer(rel):
            key = (m.group(1), int(m.group(2)))
            cite(key, rel) if key in ids else left.append((rel, 0, m.group(0)))
        text = read_text(os.path.join(root, rel)) or ""
        archived = _archived_lines(root, rel, text)
        for i, line in enumerate(text.split("\n"), 1):
            for m in PLACEHOLDER.finditer(line):
                key = (m.group(1), int(m.group(2)))
                if i in archived and key in ids:
                    continue
                cite(key, rel) if key in ids else left.append((rel, i, m.group(0)))
    have = taken(root)
    numbers = {}
    for kind, n in sorted(cited):
        hi, width = have.get(kind, (0, 2))
        numbers[(kind, n)] = f"{kind}{hi + 1:0{width}d}"
        have[kind] = (hi + 1, width)
    renames = [(rel, replace(rel, numbers)) for rel in files if replace(rel, numbers) != rel]
    return numbers, cited, renames, left


def replace(text, numbers):
    """text with each numbered placeholder given its number; any other placeholder is left as written."""
    return PLACEHOLDER.sub(lambda m: (numbers[(m.group(1), int(m.group(2)))] + m.group(3)
                                      if (m.group(1), int(m.group(2))) in numbers else m.group(0)), text)


def apply(root, files=None, dry_run=False, out=print):
    """Number every placeholder that is an ID; returns the numbers given ({"I-new-N": "I49", ...})."""
    files = tracked(root) if files is None else files
    numbers, cited, renames, left = plan(root, files)
    for rel, line, ph in left:
        out(f"not numbered: {rel}" + (f":{line}" if line else "") + f" ({ph}: no log row or handoff entry defines it)")
    if not numbers:
        out("nothing numbered" if left else "no placeholders")
        return {}
    for (kind, n), new in sorted(numbers.items()):
        out(f"{kind}-new-{n} -> {new}  ({', '.join(cited[(kind, n)])})")
    for old, new in renames:
        out(f"rename {old} -> {new}")
    if dry_run:
        out("dry run: nothing changed")
        return {f"{k}-new-{n}": v for (k, n), v in numbers.items()}
    for rel in files:
        path = os.path.join(root, rel)
        text = read_text(path)
        if not text or not PLACEHOLDER.search(text):
            continue
        archived = _archived_lines(root, rel, text)
        if archived:
            new_text = "\n".join(
                line if idx in archived else replace(line, numbers)
                for idx, line in enumerate(text.split("\n"), 1)
            )
        else:
            new_text = replace(text, numbers)
        if new_text != text:
            open(path, "w", encoding="utf-8").write(new_text)
    for old, new in renames:
        if os.path.exists(os.path.join(root, new)):
            raise SystemExit(f"can't rename {old}: {new} already exists")
        if subprocess.run(["git", "mv", old, new], cwd=root, capture_output=True).returncode != 0:
            os.rename(os.path.join(root, old), os.path.join(root, new))
    tidy_log(root)
    if os.path.isfile(os.path.join(root, handoff.HANDOFF)):
        handoff.write_list(root)
    return {f"{k}-new-{n}": v for (k, n), v in numbers.items()}


def tidy_log(root):
    """Sort the decision log again (both files when the archive exists, which also moves archival rows and refreshes entry indexes)."""
    log, arch = os.path.join(root, LOG), os.path.join(root, ARCHIVE)
    rdir = os.path.join(root, sort_decision_log.RULINGS_DIR)
    wdir = os.path.join(root, sort_decision_log.WORK_DIR)
    qdir = os.path.join(root, sort_decision_log.QUESTIONS_DIR)
    if not os.path.isfile(log):
        return
    text = open(log, encoding="utf-8").read()
    if os.path.isfile(arch):
        old = open(arch, encoding="utf-8").read()
        has_rulings = (os.path.isdir(rdir) or sort_decision_log.comitatus_rulings_dir(root)
                       or sort_decision_log._ruling_rows_in(text) or sort_decision_log._ruling_rows_in(old))
        new, new_arch = sort_decision_log.tidy(
            text, old,
            rulings_dir=sort_decision_log.ruling_dirs(root) if has_rulings else None,
            work_dir=wdir if os.path.isdir(wdir) else None,
            questions_dir=qdir if os.path.isdir(qdir) else None,
        )
        if new_arch != old:
            open(arch, "w", encoding="utf-8").write(new_arch)
    else:
        new = sort_decision_log.sort_text(text)
    if new != text:
        open(log, "w", encoding="utf-8").write(new)


def main():
    if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
        print(__doc__)
        return
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    apply(root or os.getcwd(), dry_run="--dry-run" in sys.argv)


if __name__ == "__main__":
    main()
