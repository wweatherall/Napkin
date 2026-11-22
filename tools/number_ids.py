#!/usr/bin/env python3
"""Give placeholder IDs their numbers at merge (T74), so two branches never take the same number.

A branch that needs a new decision, Work list item, question or handoff entry writes a placeholder: the kind's
letter, "-new-" and a number of its own (I-new-N, T-new-N, Q-new-N, H-new-N with N = 1, 2 ...; a letter after N
is kept, so I-new-Nb becomes I49b). Examples in prose write N instead of a digit, so they are
never numbered. The integrator merges with `git merge --no-ff --no-commit <branch>`, runs this, then commits:
each placeholder becomes the next free number of its kind, the same number everywhere it is cited, in every
tracked text file; a handoff file named after one is renamed (docs/handoff/H-new-N-slug.md -> H037-slug.md), the
decision log is sorted again and the handoff's open list is rebuilt (tools/handoff.py). Run it after each merge,
before the next: two branches merged together would share their I-new-N.

  python3 tools/number_ids.py              number them; prints each placeholder, its number and the files
  python3 tools/number_ids.py --dry-run    print what it would do, change nothing

"Next free" counts the IDs that are taken: the decision log's table rows and ### sections, the ### headings of the
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
TAKEN = re.compile(r"^([A-Z]+)(\d+)[a-z]*$")
LOG = "docs/decision-log.md"
ID_FILES = [LOG, "docs/agent-handoff.md", "docs/handoff-archive.md"]
SKIP = {"tools/test_number_ids.py"}   # its checks are written with real placeholders


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
            elif path.endswith(LOG) and line.startswith("| "):
                see(line.split("|")[1].strip())
    return found


def tracked(root):
    """Text files git tracks (plus new ones not yet added), relative to root."""
    try:
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


def plan(root, files=None):
    """Work out the numbers without changing anything.
    Returns (numbers {(kind, n): new ID without letter}, cited {(kind, n): [files]}, renames [(old, new)])."""
    files = tracked(root) if files is None else files
    cited = {}
    for rel in files:
        text = read_text(os.path.join(root, rel))
        for m in PLACEHOLDER.finditer(text or ""):
            where = cited.setdefault((m.group(1), int(m.group(2))), [])
            if rel not in where:
                where.append(rel)
        for m in PLACEHOLDER.finditer(rel):
            where = cited.setdefault((m.group(1), int(m.group(2))), [])
            if rel not in where:
                where.append(rel)
    have = taken(root)
    numbers = {}
    for kind, n in sorted(cited):
        hi, width = have.get(kind, (0, 2))
        numbers[(kind, n)] = f"{kind}{hi + 1:0{width}d}"
        have[kind] = (hi + 1, width)
    renames = [(rel, replace(rel, numbers)) for rel in files if PLACEHOLDER.search(rel)]
    return numbers, cited, renames


def replace(text, numbers):
    return PLACEHOLDER.sub(lambda m: numbers[(m.group(1), int(m.group(2)))] + m.group(3), text)


def apply(root, files=None, dry_run=False, out=print):
    """Number every placeholder; returns the numbers given ({"I-new-N": "I49", ...})."""
    files = tracked(root) if files is None else files
    numbers, cited, renames = plan(root, files)
    if not numbers:
        out("no placeholders")
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
        if text and PLACEHOLDER.search(text):
            open(path, "w", encoding="utf-8").write(replace(text, numbers))
    for old, new in renames:
        if os.path.exists(os.path.join(root, new)):
            raise SystemExit(f"can't rename {old}: {new} already exists")
        if subprocess.run(["git", "mv", old, new], cwd=root, capture_output=True).returncode != 0:
            os.rename(os.path.join(root, old), os.path.join(root, new))
    log = os.path.join(root, LOG)
    if os.path.isfile(log):
        text = open(log, encoding="utf-8").read()
        new = sort_decision_log.sort_text(text)
        if new != text:
            open(log, "w", encoding="utf-8").write(new)
    if os.path.isfile(os.path.join(root, handoff.HANDOFF)):
        handoff.write_list(root)
    return {f"{k}-new-{n}": v for (k, n), v in numbers.items()}


def main():
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    apply(root or os.getcwd(), dry_run="--dry-run" in sys.argv)


if __name__ == "__main__":
    main()
