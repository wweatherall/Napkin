#!/usr/bin/env python3
"""The handoff's entries, one file each (T77): docs/handoff/H037-short-slug.md holds one entry, headed
"### H037 — Subject" with the usual Author | Date | Status line. docs/agent-handoff.md keeps the how-to, the rules
and an open list this script builds from the folder, between its two marker lines; don't edit the list by hand.

  python3 tools/handoff.py list            rebuild the open list (tools/number_ids.py does this at every merge)
  python3 tools/handoff.py list --check    exit 1 if the list doesn't match the folder
  python3 tools/handoff.py split           move any entry written straight into docs/agent-handoff.md (a "### H..."
                                           section before "## Archived") into its own file, then rebuild the list;
                                           an entry that has a file and was answered inline (on a branch made
                                           before T77) updates its file, if only responses were added
  python3 tools/handoff.py overlaps         list files two open jobs both touch (P11; queued jobs don't count); exit 1 if any
  python3 tools/handoff.py archive H037    move the entry to the bottom of docs/handoff-archive.md, word for word,
                                           and add its line under "Archived" (outcome: its Resolution line)

A new entry on a branch is docs/handoff/H-new-N-slug.md with "### H-new-N — Subject" (N = 1, 2 ...); the
number is given at merge (tools/number_ids.py)."""
import os
import re
import sys

FOLDER = "docs/handoff"
HANDOFF = "docs/agent-handoff.md"
ARCHIVE = "docs/handoff-archive.md"
START = "<!-- open list: built from docs/handoff/ by tools/handoff.py; don't edit by hand -->"
END = "<!-- end of open list -->"
ID = re.compile(r"^H(?:(\d+)|-new-(\d+))")


def order(name):
    m = ID.match(name)
    if not m:
        return (2, 0, name)
    return (0, int(m.group(1)), name) if m.group(1) else (1, int(m.group(2)), name)


def entries(root):
    """[(file name, heading after "### ", {field: value} from the Author line)] in ID order."""
    folder = os.path.join(root, FOLDER)
    out = []
    if not os.path.isdir(folder):
        return out
    for name in sorted((n for n in os.listdir(folder) if n.endswith(".md")), key=order):
        lines = open(os.path.join(folder, name), encoding="utf-8").read().split("\n")
        head = next((l[4:].strip() for l in lines if l.startswith("### ")), name)
        fields = {}
        meta = next((l for l in lines if l.startswith("Author:")), "")
        for part in meta.split(" | "):
            if ":" in part:
                k, v = part.split(":", 1)
                fields[k.strip()] = v.strip()
        out.append((name, head, fields))
    return out


def list_text(root):
    lines = []
    for name, head, f in entries(root):
        extra = f"status: {f.get('Status', '?')}"
        if f.get("For"):
            extra += f"; for: {f['For']}"
        lines.append(f"- [{head}](handoff/{name}) — {extra}")
    return "\n".join(lines) if lines else "(none open)"


def with_list(text, root):
    if START not in text or END not in text:
        raise SystemExit(f"{HANDOFF} has no open-list markers ({START} ... {END})")
    a = text.index(START) + len(START)
    b = text.index(END)
    return text[:a] + "\n\n" + list_text(root) + "\n\n" + text[b:]


def write_list(root):
    path = os.path.join(root, HANDOFF)
    text = open(path, encoding="utf-8").read()
    new = with_list(text, root)
    if new != text:
        open(path, "w", encoding="utf-8").write(new)
    return new != text


def slug(subject):
    words = re.findall(r"[a-z0-9]+", subject.lower())
    return "-".join(words[:6]) or "entry"


def split(root):
    """Move inline "### H..." entries above "## Archived" (but not the template below it) into docs/handoff/;
    put the open-list markers under "## Open exchanges" if they're missing. Returns the files written."""
    path = os.path.join(root, HANDOFF)
    lines = open(path, encoding="utf-8").read().split("\n")
    stop = lines.index("## Archived") if "## Archived" in lines else len(lines)
    keep, written, k = [], [], 0
    while k < len(lines):
        line = lines[k]
        if k < stop and line.startswith("### ") and ID.match(line[4:]):
            j = next((m for m in range(k + 1, len(lines)) if lines[m].startswith("## ") or lines[m].startswith("### ")),
                     len(lines))
            head = line[4:].strip()
            hid = head.split()[0]
            subject = head.split("—", 1)[1] if "—" in head else head[len(hid):]
            name = f"{hid}-{slug(subject)}.md"
            os.makedirs(os.path.join(root, FOLDER), exist_ok=True)
            body = "\n".join(lines[k:j]).strip("\n") + "\n"
            have = [n for n in os.listdir(os.path.join(root, FOLDER)) if n.split("-")[0] == hid and ID.match(hid)
                    and not hid.startswith("H-")]
            if have:
                # a branch made before T77 answered the entry inline: the file plus new responses replaces the file
                name = have[0]
                old = open(os.path.join(root, FOLDER, name), encoding="utf-8").read()
                if not body.startswith(old.rstrip("\n")):
                    raise SystemExit(f"{hid} is in {HANDOFF} and {FOLDER}/{name} differs from it: merge them by hand")
            open(os.path.join(root, FOLDER, name), "w", encoding="utf-8").write(body)
            written.append(name)
            k = j
            continue
        keep.append(line)
        k += 1
    text = "\n".join(keep)
    if written:
        text = re.sub(r"\n{3,}", "\n\n", text)
    if START not in text and "## Open exchanges" in text:
        text = text.replace("## Open exchanges\n", f"## Open exchanges\n\n{START}\n\n{END}\n", 1)
    open(path, "w", encoding="utf-8").write(text)
    write_list(root)
    return written


def archive(root, hid):
    """Move entry hid (e.g. "H037") to the archive's bottom and index it under "## Archived" (newest first)."""
    match = [n for n, _, _ in entries(root) if n.split("-")[0] == hid]
    if len(match) != 1:
        raise SystemExit(f"no single {FOLDER}/{hid}-*.md (found {match})")
    path = os.path.join(root, FOLDER, match[0])
    body = open(path, encoding="utf-8").read().strip("\n")
    head = next(l[4:].strip() for l in body.split("\n") if l.startswith("### "))
    res = [l[len("Resolution:"):].strip() for l in body.split("\n") if l.startswith("Resolution:")]
    outcome = res[-1] if res else "see the archive"
    arch = os.path.join(root, ARCHIVE)
    text = open(arch, encoding="utf-8").read().rstrip("\n")
    open(arch, "w", encoding="utf-8").write(text + "\n\n" + body + "\n")
    hpath = os.path.join(root, HANDOFF)
    lines = open(hpath, encoding="utf-8").read().split("\n")
    a = lines.index("## Archived")
    first = next((k for k in range(a + 1, len(lines)) if lines[k].startswith("- ") or lines[k].startswith("## ")), len(lines))
    lines.insert(first, f"- {head}. Resolved: {outcome}")
    open(hpath, "w", encoding="utf-8").write("\n".join(lines))
    os.remove(path)
    write_list(root)
    return head


PATH = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)+(?:[\w.*-]+)?|[\w-]+\.(?:md|py|gd|sh|json|cfg|gdshader))(?![\w/])")
TOP = {"ARCHITECTURE.md", "CLAUDE.md", "AGENTS.md", "BOARD.md", "README.txt", "FREECAD_FEATURE_MAP.md"}
SKIP = re.compile(r"^(not |read-only|if |nothing |no )", re.I)


def touches(body):
    """The files a job says it will change, from its "Touches:" paragraph. Sentences that say what it won't touch
    ("Not viewport/main.gd ...", "Read-only on ...") are left out; a folder or glob (viewport/tools/*) is kept as is."""
    lines = body.split("\n")
    k = next((i for i, l in enumerate(lines) if l.startswith("Touches:")), None)
    if k is None:
        return set()
    para = []
    for l in lines[k:]:
        if not l.strip():
            break
        para.append(l)
    text = " ".join(para)[len("Touches:"):]
    out = set()
    for sentence in re.split(r"(?<=[.;])\s+(?=[A-Z(])", text):
        if SKIP.match(sentence.strip()):
            continue
        for m in PATH.finditer(sentence):
            p = m.group(1).rstrip(".,;:")
            if "/" in p or p in TOP:
                out.add(p)
    return out


def _covers(a, b):
    """Does path a include path b (equal, a folder of it, or a glob over it)?"""
    if a == b:
        return True
    if a.endswith("*"):                       # viewport/tools/* or worker/scenario/NN_*
        return b.startswith(a.rstrip("*"))
    if "." not in a.rsplit("/", 1)[-1]:       # a folder: worker/scenario, docs/handoff/
        return b.startswith(a.rstrip("/") + "/")
    return False


def overlaps_in(texts, statuses=("open", "answered")):
    """[(file, [job IDs])] for files two or more open jobs both say they touch (P11). texts: {file name: entry text}.
    Queued jobs don't count: they wait for the job they'd overlap."""
    jobs = {}
    for name, text in texts.items():
        head = next((l[4:].strip() for l in text.split("\n") if l.startswith("### ")), name)
        meta = next((l for l in text.split("\n") if l.startswith("Author:")), "")
        status = next((p.split(":", 1)[1].strip() for p in meta.split(" | ") if p.strip().startswith("Status:")), "")
        if status.split(" ")[0] in statuses:
            jobs[head.split()[0]] = touches(text)
    out = {}
    ids = sorted(jobs)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            for pa in jobs[a]:
                for pb in jobs[b]:
                    if _covers(pa, pb) or _covers(pb, pa):
                        out.setdefault(pa if len(pa) >= len(pb) else pb, set()).update([a, b])
    return sorted((k, sorted(v)) for k, v in out.items())


def overlaps(root):
    folder = os.path.join(root, FOLDER)
    return overlaps_in({n: open(os.path.join(folder, n), encoding="utf-8").read() for n, _, _ in entries(root)})


def main():
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    args = sys.argv[1:]
    if args[:1] == ["list"]:
        if "--check" in args:
            text = open(os.path.join(root, HANDOFF), encoding="utf-8").read()
            if with_list(text, root) != text:
                print(f"{HANDOFF}: the open list doesn't match {FOLDER}/: run python3 tools/handoff.py list")
                sys.exit(1)
        elif write_list(root):
            print(f"rebuilt the open list in {HANDOFF}")
    elif args[:1] == ["overlaps"]:
        found = overlaps(root)
        for path, ids in found:
            print(f"{path}: {', '.join(ids)}")
        if not found:
            print("no two open jobs touch the same file")
        sys.exit(1 if found else 0)
    elif args[:1] == ["split"]:
        for name in split(root):
            print(f"moved {name[:-3].split('-')[0]} to {FOLDER}/{name}")
    elif args[:1] == ["archive"] and len(args) == 2:
        print(f"archived {archive(root, args[1])}")
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
