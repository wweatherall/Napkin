#!/usr/bin/env python3
"""Keep the decision log tidy (P23): two files with the same IDs, docs/decision-log.md (live) and
docs/decision-archive.md (history). Tables sort by ID: A01, A02 ... A06, A06a, A07 ... then D, G, I, M, P, W;
Q1 ... Q31; T1 ... T49 (numbers in number order, a letter after a number comes after it).

  python3 tools/sort_decision_log.py [live [archive]]   default both files; rewrites only what changes
  python3 tools/sort_decision_log.py --check            exit 1 if either file isn't tidy or has a problem

Tidying, in order:
 - rows whose status belongs in the archive move there whole: Superseded decisions (their Principles cell becomes
   "<subject>; <principles>", so neither is lost), Decided questions, Done Work list items;
 - each "### <ID>" Details section moves to the file that holds its row;
 - tables sort by ID (tables whose first column isn't an ID, like Tunables and Subjects, keep their order), and
   so do Details sections;
 - the live file's generated columns are rebuilt: the Subjects index lists each subject's decision IDs (from the
   "### <subject>" groups under ## Decisions, which follow the index's order) and each principle's Explains
   lists the decisions that name it in their Principles column.
--check also fails when a row says "(Details below.)" without a section (or the reverse), a status isn't one its
table allows, an ID is in both files, a subject heading isn't in the index (or the reverse), or a decision names
a principle that doesn't exist. A live file without an archive beside it (the layout before P23) is only sorted.
The pre-commit hook (.githooks/pre-commit) runs this whenever either file is committed."""
import os
import re
import sys

LIVE = "docs/decision-log.md"
ARCHIVE = "docs/decision-archive.md"
# live section -> (archive section, the statuses that move there)
MOVES = {"## Decisions": ("## Superseded decisions", {"Superseded"}),
         "## Open questions": ("## Decided questions", {"Decided"}),
         "## Work list": ("## Done work", {"Done"})}
CITE = r"\b[A-Z]+(?:\d+|-new-\d+)[a-z]*\b"   # an ID cited in a cell
NONE = "—"   # a decision no principle explains yet

ID = re.compile(r"^([A-Z]+)(\d+)([a-z]*)$")
ROW = re.compile(r"^[A-Z]+(\d+|-new-\d+)[a-z]*$")   # an ID or a branch's placeholder (I-new-N, T74)


def key(row):
    """Sort key; a placeholder (I-new-N) sorts after its kind's numbered IDs until number_ids.py numbers it."""
    k = row.split("|")[1].strip()
    m = ID.match(k)
    if m:
        return (m.group(1), int(m.group(2)), m.group(3))
    m = re.match(r"^([A-Z]+)-new-(\d+)([a-z]*)$", k)
    return (m.group(1), 10 ** 9 + int(m.group(2)), m.group(3))


def sort_text(text):
    return generate(sort_tables(text))


def sort_tables(text):
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        # a table: a header row, a |---| row, then rows that start with "|"
        if lines[i].startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1]):
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            rows = lines[i + 2:j]
            if rows and all(ROW.match(r.split("|")[1].strip()) for r in rows):
                rows = sorted(rows, key=key)
            out += lines[i:i + 2] + rows
            i = j
        else:
            out.append(lines[i])
            i += 1
    return sort_details("\n".join(out))


def sort_details(text):
    """Sort the "### <ID>" sections under "## Details" (which runs to the next "## " heading or the end)."""
    lines = text.split("\n")
    if "## Details" not in lines:
        return text
    a = lines.index("## Details") + 1
    b = next((k for k in range(a, len(lines)) if lines[k].startswith("## ")), len(lines))
    first = next((k for k in range(a, b) if lines[k].startswith("### ")), b)
    sections, k = [], first
    while k < b:
        j = next((m for m in range(k + 1, b) if lines[m].startswith("### ")), b)
        body = lines[k:j]
        while body and body[-1] == "":
            body.pop()
        sections.append(body)
        k = j
    if not all(ID.match(sec[0][4:].strip()) for sec in sections):
        return text
    sections.sort(key=lambda sec: key("| " + sec[0][4:].strip() + " |"))
    body = []
    for sec in sections:
        body += sec + [""]
    tail = lines[b:]
    if tail:
        return "\n".join(lines[:first] + body + tail)
    out = lines[:first] + body
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def details_problems(text):
    """Rows marked "(Details below.)" and "### <ID>" sections must match one to one."""
    marked = {r.split("|")[1].strip() for r in text.split("\n") if r.startswith("| ") and "(Details below.)" in r}
    lines = text.split("\n")
    have = set()
    if "## Details" in lines:
        for l in lines[lines.index("## Details") + 1:]:
            if l.startswith("## "):
                break
            if l.startswith("### "):
                have.add(l[4:].strip())
    out = [f"{i} says (Details below.) but has no ### {i} section" for i in sorted(marked - have)]
    out += [f"### {i} has no row saying (Details below.)" for i in sorted(have - marked)]
    return out


STATUSES = {   # the only statuses each table may use (P17): workers write results in their handoff file
    "## Principles": {"Active", "Tentative"},
    "## Decisions": {"Active", "Tentative"},
    "## Superseded decisions": {"Superseded"},
    "## Open questions": {"Open", "Decided", "Parked"},   # Decided and Done move to the archive when tidied
    "## Decided questions": {"Decided"},
    "## Work list": {"Open", "In progress", "Done", "Parked", "Split"},
    "## Done work": {"Done", "Split"},
}
QUEUED = re.compile(r"^Open \(queued: H\d+\)$")


def status_problems(text):
    """Every table row's Status must be one its section allows; a Work list item may also be "Open (queued: H040)"."""
    out, section = [], None
    for line in text.split("\n"):
        if line.startswith("## "):
            section = line.strip()
            continue
        if section in STATUSES and line.startswith("| ") and not line.startswith("| ID ") and ID.match(line.split("|")[1].strip()):
            cells = [c.strip() for c in line.split("|")]
            status = cells[3] if len(cells) > 3 else ""
            if status not in STATUSES[section] and not (section == "## Work list" and QUEUED.match(status)):
                out.append(f"{cells[1]}: status '{status}' isn't one of {sorted(STATUSES[section])} ({section[3:]})")
    return out


def cells(line):
    return [c.strip() for c in line.split("|")[1:-1]]


def row_id(line):
    """The ID of an ID-keyed table row, else None."""
    if not line.startswith("| "):
        return None
    k = line.split("|")[1].strip()
    return k if ROW.match(k) else None


def make_row(c):
    return "| " + " | ".join(c) + " |"


def tables(lines):
    """Each table: (header index, header cells, [row indexes], its "## " section, its "### " group or None)."""
    out, section, group, i = [], None, None, 0
    while i < len(lines):
        l = lines[i]
        if l.startswith("## "):
            section, group = l.strip(), None
        elif l.startswith("### "):
            group = l[4:].strip()
        elif l.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1]):
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            out.append((i, cells(l), list(range(i + 2, j)), section, group))
            i = j
            continue
        i += 1
    return out


def section_range(lines, heading):
    """(first, end) line indexes of a "## " section's body, or None."""
    if heading not in lines:
        return None
    a = lines.index(heading) + 1
    return a, next((k for k in range(a, len(lines)) if lines[k].startswith("## ")), len(lines))


def generate(text):
    """Rebuild the live file's generated parts: subject groups in the index's order, the index's Decisions
    column, the principles' Explains column. A file without a "## Subjects" index is left as it is."""
    lines = text.split("\n")
    if "## Subjects" not in lines or "## Decisions" not in lines:
        return text
    order = [cells(lines[r])[0] for h, hc, rs, sec, g in tables(lines) if sec == "## Subjects" for r in rs]
    a, b = section_range(lines, "## Decisions")
    first = next((k for k in range(a, b) if lines[k].startswith("### ")), b)
    groups, k = [], first
    while k < b:
        j = next((m for m in range(k + 1, b) if lines[m].startswith("### ")), b)
        body = lines[k:j]
        while body and body[-1] == "":
            body.pop()
        groups.append(body)
        k = j
    rank = {name: n for n, name in enumerate(order)}
    groups.sort(key=lambda g: rank.get(g[0][4:].strip(), len(rank)))
    body = []
    for g in groups:
        body += g + [""]
    lines = lines[:first] + body + lines[b:]
    ids, cited = {}, {}
    for h, hc, rs, sec, g in tables(lines):
        if sec == "## Decisions" and g:
            ids.setdefault(g, [])
            col = hc.index("Principles") if "Principles" in hc else None
            for r in rs:
                c = cells(lines[r])
                ids[g].append(c[0])
                if col is not None and col < len(c):
                    for p in re.findall(CITE, c[col]):
                        cited.setdefault(p, []).append(c[0])
    for h, hc, rs, sec, g in tables(lines):
        if sec == "## Subjects" and "Decisions" in hc:
            col = hc.index("Decisions")
            for r in rs:
                c = cells(lines[r])
                c[col] = ", ".join(ids.get(c[0], [])) or NONE
                lines[r] = make_row(c)
        if sec == "## Principles" and "Explains" in hc:
            col = hc.index("Explains")
            for r in rs:
                c = cells(lines[r])
                c[col] = ", ".join(sorted(cited.get(c[0], []), key=lambda x: key(f"| {x} |"))) or NONE
                lines[r] = make_row(c)
    return "\n".join(lines)


def find_row(lines, ident):
    return next((i for i, l in enumerate(lines) if row_id(l) == ident), None)


def insert_row(text, row, section, group=None):
    """Add a row at the end of the table under section (and "### group" inside it); sort_text puts it in order."""
    lines = text.split("\n")
    for h, hc, rs, sec, g in tables(lines):
        if sec == section and (group is None or g == group):
            lines.insert((rs[-1] if rs else h + 1) + 1, row)
            return "\n".join(lines)
    raise ValueError(f"no table under {section}" + (f" / ### {group}" if group else ""))


def remove_row(text, ident):
    """(text without the row, the row or None)."""
    lines = text.split("\n")
    i = find_row(lines, ident)
    if i is None:
        return text, None
    row = lines.pop(i)
    return "\n".join(lines), row


def where(text, ident):
    """(section, group) of an ID's row, or None."""
    lines = text.split("\n")
    for h, hc, rs, sec, g in tables(lines):
        for r in rs:
            if row_id(lines[r]) == ident:
                return sec, g
    return None


def details_sections(text):
    """{ID: [lines of its "### ID" section, trailing blanks dropped]} under "## Details"."""
    lines = text.split("\n")
    rng = section_range(lines, "## Details")
    out = {}
    if not rng:
        return out
    a, b = rng
    k = next((m for m in range(a, b) if lines[m].startswith("### ")), b)
    while k < b:
        j = next((m for m in range(k + 1, b) if lines[m].startswith("### ")), b)
        body = lines[k:j]
        while body and body[-1] == "":
            body.pop()
        out[lines[k][4:].strip()] = body
        k = j
    return out


def take_details(text, ident):
    """(text without the "### ident" section, its lines or None)."""
    lines = text.split("\n")
    rng = section_range(lines, "## Details")
    if not rng:
        return text, None
    a, b = rng
    start = next((k for k in range(a, b) if lines[k].startswith("### ") and lines[k][4:].strip() == ident), None)
    if start is None:
        return text, None
    end = next((m for m in range(start + 1, b) if lines[m].startswith("### ")), b)
    body = lines[start:end]
    del lines[start:end]
    while body and body[-1] == "":
        body.pop()
    return "\n".join(lines), body


def add_details(text, body):
    """Put a "### ID" section under "## Details" (sorted into place by sort_text)."""
    lines = text.split("\n")
    rng = section_range(lines, "## Details")
    if not rng:
        raise ValueError("no ## Details section")
    b = rng[1]
    while b > rng[0] and lines[b - 1] == "":
        b -= 1
    lines[b:b] = ["", *body]
    return "\n".join(lines)


def archived_row(row, subject):
    """A decision row as it goes into the archive: its Principles cell keeps the subject too."""
    c = cells(row)
    if len(c) > 5:
        c[5] = f"{subject}; {c[5]}" if c[5] else subject
    return make_row(c)


def tidy(live, archive):
    """(live, archive) with archival rows moved, Details beside their rows, everything sorted and generated."""
    lines = live.split("\n")
    moving = []
    for h, hc, rs, sec, g in tables(lines):
        if sec in MOVES and "Status" in hc:
            col = hc.index("Status")
            for r in rs:
                c = cells(lines[r])
                if row_id(lines[r]) and col < len(c) and c[col] in MOVES[sec][1]:
                    moving.append((r, MOVES[sec][0], archived_row(lines[r], g) if sec == "## Decisions" and g else lines[r]))
    for r, target, row in sorted(moving, reverse=True):
        del lines[r]
    live = "\n".join(lines)
    for r, target, row in moving:
        archive = insert_row(archive, row, target)
    for src, dst in ((0, 1), (1, 0)):
        texts = [live, archive]
        held = {row_id(l) for l in texts[dst].split("\n") if row_id(l)}
        mine = {row_id(l) for l in texts[src].split("\n") if row_id(l)}
        for ident in list(details_sections(texts[src])):
            if ident in held and ident not in mine:
                texts[src], body = take_details(texts[src], ident)
                texts[dst] = add_details(texts[dst], body)
        live, archive = texts
    return sort_text(live), sort_text(archive)


def ids_of(text):
    return [row_id(l) for l in text.split("\n") if row_id(l)]


def layout_problems(live, archive):
    """Problems that tidying can't fix: an ID in both files, the index and the subject headings out of step,
    a decision naming a principle that doesn't exist."""
    out = []
    both = sorted(set(ids_of(live)) & set(ids_of(archive)), key=lambda x: key(f"| {x} |"))
    out += [f"{i} is in both {LIVE} and {ARCHIVE}" for i in both]
    for name, text in ((LIVE, live), (ARCHIVE, archive)):
        seen = set()
        for i in ids_of(text):
            if i in seen:
                out.append(f"{i} has two rows in {name}")
            seen.add(i)
    lines = live.split("\n")
    index = [cells(lines[r])[0] for h, hc, rs, sec, g in tables(lines) if sec == "## Subjects" for r in rs]
    rng = section_range(lines, "## Decisions")
    heads = [lines[k][4:].strip() for k in range(*rng) if lines[k].startswith("### ")] if rng else []
    out += [f"### {h} under ## Decisions isn't in the Subjects index" for h in heads if h not in index]
    out += [f"the Subjects index names {s}, which has no ### heading under ## Decisions" for s in index if s not in heads]
    if rng and any(row_id(lines[k]) for k in range(rng[0], next((k for k in range(*rng) if lines[k].startswith("### ")), rng[1]))):
        out.append("## Decisions has rows before its first ### subject heading")
    principles = {cells(lines[r])[0] for h, hc, rs, sec, g in tables(lines) if sec == "## Principles" for r in rs}
    for h, hc, rs, sec, g in tables(lines):
        if sec == "## Decisions" and "Principles" in hc:
            col = hc.index("Principles")
            for r in rs:
                c = cells(lines[r])
                cell = c[col] if col < len(c) else ""
                if not cell:
                    out.append(f"{c[0]}: no principle named (write {NONE} if none fits yet)")
                for p in re.findall(CITE, cell):
                    if p not in principles:
                        out.append(f"{c[0]} names principle {p}, which isn't in ## Principles")
    return out


def check_files(live, archive=None):
    """Every problem with the log (both files when there's an archive)."""
    if archive is None:
        out = [] if sort_text(live) == live else [f"{LIVE} is not sorted by ID: run python3 tools/sort_decision_log.py"]
        return out + details_problems(live) + status_problems(live)
    out = []
    l2, a2 = tidy(live, archive)
    if l2 != live:
        out.append(f"{LIVE} is not tidy: run python3 tools/sort_decision_log.py")
    if a2 != archive:
        out.append(f"{ARCHIVE} is not tidy: run python3 tools/sort_decision_log.py")
    for name, text in ((LIVE, live), (ARCHIVE, archive)):
        out += [f"{name}: {p}" for p in details_problems(text) + status_problems(text)]
    return out + layout_problems(live, archive)


def main():
    args = [a for a in sys.argv[1:] if a != "--check"]
    live_path = args[0] if args else LIVE
    arch_path = args[1] if len(args) > 1 else os.path.join(os.path.dirname(live_path), os.path.basename(ARCHIVE))
    live = open(live_path, encoding="utf-8").read()
    archive = open(arch_path, encoding="utf-8").read() if os.path.isfile(arch_path) else None
    if "--check" in sys.argv:
        problems = check_files(live, archive)
        if problems:
            print("\n".join(problems))
            sys.exit(1)
        return
    if archive is None:
        new = sort_text(live)
        if new != live:
            open(live_path, "w", encoding="utf-8").write(new)
            print(f"sorted {live_path} by ID")
        return
    l2, a2 = tidy(live, archive)
    for path, old, new in ((live_path, live, l2), (arch_path, archive, a2)):
        if new != old:
            open(path, "w", encoding="utf-8").write(new)
            print(f"tidied {path}")


if __name__ == "__main__":
    main()
