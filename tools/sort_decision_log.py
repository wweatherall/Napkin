#!/usr/bin/env python3
"""Keep the decision log tidy (P23): two files with the same IDs, 03_Past_Decisions/decision-log.md (live) and
03_Past_Decisions/decision-archive.md (history). Tables sort by ID: A01, A02 ... A06, A06a, A07 ... then D, G, I, M, P, W;
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
import json
import os
import re
import shutil
import subprocess
import sys

LIVE = "03_Past_Decisions/decision-log.md"
ARCHIVE = "03_Past_Decisions/decision-archive.md"
RULINGS_DIR = "03_Past_Decisions/rulings"
WORK_DIR = "03_Past_Decisions/work"
QUESTIONS_DIR = "03_Past_Decisions/questions"
# live section -> (archive section, the statuses that move there)
MOVES = {"## Decisions": ("## Superseded decisions", {"Superseded"}),
         "## Open questions": ("## Decided questions", {"Decided"}),
         "## Work list": ("## Done work", {"Done"})}
RULING_SECTIONS = {"## Principles", "## Decisions", "## Superseded decisions"}
WORK_SECTIONS = {"## Work list", "## Done work"}
QUESTION_SECTIONS = {"## Open questions", "## Decided questions"}
QT_SECTIONS = WORK_SECTIONS | QUESTION_SECTIONS
CITE = r"\b[A-Z]+(?:\d+|-new-\d+)[a-z]*\b"   # an ID cited in a cell
NONE = "—"   # a decision no principle explains yet

ID = re.compile(r"^([A-Z]+)(\d+)([a-z]*)$")
ROW = re.compile(r"^[A-Z]+(\d+|-new-\d+)[a-z]*$")   # an ID or a branch's placeholder (I-new-N, T74)


def kind_of(ident):
    m = re.match(r"^([A-Z]+)", ident or "")
    return m.group(1) if m else ""


def is_ruling_id(ident):
    k = kind_of(ident)
    return bool(k and k not in ("Q", "T", "H"))


def is_work_id(ident):
    return kind_of(ident) == "T"


def is_question_id(ident):
    return kind_of(ident) == "Q"


def strip_details_note(text):
    return re.sub(r"\s*\(Details below\.\)\s*$", "", (text or "").strip()).strip()


def first_sentence(text, limit=90):
    """First sentence of text (with (Details below.) dropped), cut at limit with '...'."""
    cleaned = " ".join(strip_details_note(text).split())
    if not cleaned:
        return ""
    m = re.search(r"[.!?](?:\s|$)", cleaned)
    sent = cleaned[:m.start() + 1] if m else cleaned
    return sent if len(sent) <= limit else sent[:limit - 3] + "..."


def comitatus_root(root):
    """Return (comitatus_dir or None, main_repo_dir) for a checkout or worktree.
    NAPKIN_COMITATUS=<dir> overrides the comitatus directory for this repo's checkouts/worktrees."""
    r_top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, text=True)
    top = r_top.stdout.strip() if r_top.returncode == 0 else ""
    if top and os.path.realpath(top) == os.path.realpath(root):
        r = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=root, capture_output=True, text=True)
        common = r.stdout.strip() if r.returncode == 0 else ""
        main_repo = (os.path.dirname(os.path.realpath(os.path.join(root, common)))
                     if common else os.path.realpath(root))
    else:
        main_repo = os.path.realpath(root)
    parent = os.path.dirname(main_repo)
    org = os.path.dirname(parent)
    if os.path.basename(parent) == "08_Code_Bases" and os.path.isdir(org):
        env_org = os.environ.get("NAPKIN_COMITATUS", "").strip()
        if env_org and os.path.isdir(env_org):
            r_self = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                                    cwd=os.path.dirname(os.path.abspath(__file__)), capture_output=True, text=True)
            self_common = r_self.stdout.strip() if r_self.returncode == 0 else ""
            self_main = os.path.dirname(os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), self_common))) if self_common else ""
            if main_repo == self_main:
                return os.path.realpath(env_org), main_repo
        return org, main_repo
    return None, main_repo


def comitatus_rulings_dir(root):
    """Return comitatus/03_Past_Decisions/rulings if comitatus is beside root and the folder exists, else None."""
    org, _ = comitatus_root(root)
    if not org:
        return None
    d = os.path.join(org, RULINGS_DIR)
    return d if os.path.isdir(d) else None


def ruling_dirs(root):
    """[Napkin's rulings/] or [Napkin's rulings/, comitatus's rulings/] when comitatus is beside it."""
    dirs = [os.path.join(root, RULINGS_DIR)]
    cdir = comitatus_rulings_dir(root)
    if cdir and os.path.realpath(cdir) != os.path.realpath(dirs[0]):
        dirs.append(cdir)
    return dirs


def _folders(folder):
    return list(folder) if isinstance(folder, (list, tuple)) else [folder]


def folder_ids(folder):
    """Sorted IDs of <ID>.md files in folder (or list of folders)."""
    out = set()
    for d in _folders(folder):
        if os.path.isdir(d):
            out.update(n[:-3] for n in os.listdir(d) if n.endswith(".md") and ROW.match(n[:-3]))
    return sorted(out, key=lambda x: key(f"| {x} |"))


def parse_entry(text, ident=None):
    """Parse an entry file (<ID>.md) into {id, title, meta, body, why, details, raw}."""
    lines = text.splitlines()
    title = ""
    i = 0
    if lines and lines[0].startswith("# "):
        head = lines[0][2:].strip()
        if " — " in head:
            eid, title = head.split(" — ", 1)
            ident = ident or eid.strip()
        elif " - " in head:
            eid, title = head.split(" - ", 1)
            ident = ident or eid.strip()
        else:
            title = head
        i = 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    meta = {}
    while i < len(lines) and lines[i].strip() != "":
        line = lines[i]
        parts = line.split(" | ") if " | " in line and all(":" in p for p in line.split(" | ")) else [line]
        for part in parts:
            if ":" in part:
                k, v = part.split(":", 1)
                meta[k.strip()] = v.strip()
        i += 1
    rest = "\n".join(lines[i:]).lstrip("\n")
    details = ""
    if "\n## Details\n" in rest or rest.startswith("## Details\n"):
        if rest.startswith("## Details\n"):
            main_part, details = "", rest[len("## Details\n"):].strip("\n")
        else:
            main_part, details = rest.split("\n## Details\n", 1)
            details = details.strip("\n")
    else:
        main_part = rest
    why = ""
    result = ""
    notes = ""
    main_lines = main_part.rstrip("\n").splitlines()
    trailing_fields = (("Why:", "why"), ("Result / next step:", "result"), ("Notes:", "notes"))
    field_idx, field_key, field_prefix = None, None, ""
    for idx, l in enumerate(main_lines):
        for prefix, key_name in trailing_fields:
            if l == prefix or l.startswith(prefix + " "):
                field_idx, field_key, field_prefix = idx, key_name, prefix
                break
        if field_idx is not None:
            break
    if field_idx is not None:
        val = main_lines[field_idx][len(field_prefix):].strip()
        if field_idx + 1 < len(main_lines):
            extra = "\n".join(main_lines[field_idx + 1:]).strip()
            if extra:
                val = (val + "\n" + extra).strip()
        if field_key == "why":
            why = val
        elif field_key == "result":
            result = val
        elif field_key == "notes":
            notes = val
        body = "\n".join(main_lines[:field_idx]).strip()
    else:
        body = main_part.strip()
    return {"id": ident or "", "title": title.strip(), "meta": meta, "body": body,
            "why": why, "result": result, "notes": notes, "details": details, "raw": text}


def read_entry(folder, ident):
    for d in _folders(folder):
        path = os.path.join(d, f"{ident}.md")
        if os.path.isfile(path):
            return parse_entry(open(path, encoding="utf-8").read(), ident=ident)
    return None


def read_entries(folder):
    entries = {}
    for d in reversed(_folders(folder)):
        for ident in folder_ids(d):
            e = read_entry(d, ident)
            if e is not None:
                entries[ident] = e
    return entries


def write_entry(folder, ident, content):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{ident}.md")
    if not os.path.isfile(path) or open(path, encoding="utf-8").read() != content:
        open(path, "w", encoding="utf-8").write(content)


def format_ruling(ident, text, status, date, subject="", principles="", rel="", where="", why="", details=""):
    """Format a ruling file (03_Past_Decisions/rulings/<ID>.md) from its fields."""
    clean_text = strip_details_note(text)
    title = first_sentence(clean_text)
    lines = [f"# {ident} — {title}", ""]
    if kind_of(ident) == "G":
        lines.append(f"Status: {status} | Date: {date}")
        if rel and rel != NONE:
            lines.append(f"Replaces / replaced by: {rel}")
        if where and where != NONE:
            lines.append(f"Where in the code: {where}")
        lines += ["", clean_text]
        if why:
            lines += ["", f"Why: {why}"]
    else:
        princ = principles.strip() if principles and principles.strip() else NONE
        lines.append(f"Status: {status} | Subject: {subject} | Principles: {princ} | Date: {date}")
        lines.append(f"Replaces / replaced by: {rel.strip() if rel and rel.strip() else NONE}")
        lines.append(f"Where in the code: {where.strip() if where and where.strip() else NONE}")
        lines += ["", clean_text, "", f"Why: {why.strip()}" if why and why.strip() else "Why:"]
    if details and details.strip():
        lines += ["", "## Details", "", details.strip("\n")]
    return "\n".join(lines) + "\n"


def _details_text(details_lines):
    if not details_lines:
        return ""
    body = details_lines[1:] if details_lines[0].startswith("### ") else details_lines
    while body and body[0].strip() == "":
        body = body[1:]
    return "\n".join(body).strip("\n")


def format_work(ident, text, status, covers="", jobs="", result="", details=""):
    """Format a Work list file (03_Past_Decisions/work/<ID>.md) from its fields."""
    clean_text = strip_details_note(text)
    title = first_sentence(clean_text)
    cov = covers.strip() if covers and covers.strip() else NONE
    lines = [f"# {ident} — {title}", "", f"Status: {status} | Covers: {cov}"]
    if jobs and jobs.strip():
        lines.append(f"Jobs: {jobs.strip()}")
    lines += ["", clean_text, ""]
    lines.append(f"Result / next step: {result.strip()}" if result and result.strip() else "Result / next step:")
    if details and details.strip():
        lines += ["", "## Details", "", details.strip("\n")]
    return "\n".join(lines) + "\n"


def format_question(ident, text, status, notes="", details=""):
    """Format a question file (03_Past_Decisions/questions/<ID>.md) from its fields."""
    clean_text = strip_details_note(text)
    title = first_sentence(clean_text)
    lines = [f"# {ident} — {title}", "", f"Status: {status}", "", clean_text, ""]
    lines.append(f"Notes: {notes.strip()}" if notes and notes.strip() else "Notes:")
    if details and details.strip():
        lines += ["", "## Details", "", details.strip("\n")]
    return "\n".join(lines) + "\n"


def row_to_work(row, section=None, group=None, details_lines=None):
    """Convert a legacy Work list table row + optional ### <ID> details lines into (ident, file_text)."""
    c = cells(row)
    ident = c[0]
    text = c[1] if len(c) > 1 else ""
    status = c[2] if len(c) > 2 else "Open"
    covers = c[3] if len(c) > 3 else ""
    result = " | ".join(c[4:]) if len(c) > 4 else ""
    return ident, format_work(ident, text, status, covers=covers, result=result, details=_details_text(details_lines))


def row_to_question(row, section=None, group=None, details_lines=None):
    """Convert a legacy question table row + optional ### <ID> details lines into (ident, file_text)."""
    c = cells(row)
    ident = c[0]
    text = c[1] if len(c) > 1 else ""
    status = c[2] if len(c) > 2 else "Open"
    notes = " | ".join(c[3:]) if len(c) > 3 else ""
    return ident, format_question(ident, text, status, notes=notes, details=_details_text(details_lines))


def row_to_ruling(row, section, group=None, details_lines=None):
    """Convert a legacy table row + optional ### <ID> details lines into (ident, file_text)."""
    c = cells(row)
    ident = c[0]
    details = _details_text(details_lines)
    if section == "## Principles":
        # | ID | Principle | Status | Explains | Date |
        text = c[1] if len(c) > 1 else ""
        status = c[2] if len(c) > 2 else "Active"
        date = c[4] if len(c) > 4 else ""
        return ident, format_ruling(ident, text, status, date, details=details)
    # | ID | Decision | Status | Replaces / replaced by | Why | Principles/Area | Where in the code | Date |
    text = c[1] if len(c) > 1 else ""
    status = c[2] if len(c) > 2 else "Active"
    rel = c[3] if len(c) > 3 else ""
    why = c[4] if len(c) > 4 else ""
    pcol = c[5] if len(c) > 5 else ""
    where_col = c[6] if len(c) > 6 else ""
    date = c[7] if len(c) > 7 else ""
    if section == "## Superseded decisions":
        if "; " in pcol:
            subject, principles = pcol.split("; ", 1)
        else:
            subject, principles = pcol, NONE
    else:
        subject = group or ""
        principles = pcol
    return ident, format_ruling(ident, text, status, date, subject=subject, principles=principles,
                                rel=rel, where=where_col, why=why, details=details)


def index_row(entry):
    return make_row([entry["id"], entry["title"], entry["meta"].get("Status", "")])


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
ON_BOARD = re.compile(r"^On the board \(H(?:\d+|-new-\d+)(?:, H(?:\d+|-new-\d+))*\)$")
QUEUED = ON_BOARD   # alias kept for tools/log.py; On the board (H040) replaced Open (queued: H040)
LEGACY_QUEUED = re.compile(r"^Open \(queued: H\d+\)$")
PICKED_UP = re.compile(r"^Picked up \([^,)]+, \d{4}-\d{2}-\d{2}\)$")


def is_work_status(status):
    """True when status is valid for a ## Work list item."""
    return status in STATUSES["## Work list"] or bool(QUEUED.match(status)) or bool(PICKED_UP.match(status))


def status_problems(text):
    """Every table row's Status must be one its section allows; a Work list item may also be "On the board (H040)" or "Picked up (...)"."""
    out, section = [], None
    for line in text.split("\n"):
        if line.startswith("## "):
            section = line.strip()
            continue
        if section in STATUSES and line.startswith("| ") and not line.startswith("| ID ") and ID.match(line.split("|")[1].strip()):
            cells = [c.strip() for c in line.split("|")]
            status = cells[3] if len(cells) > 3 else ""
            if status not in STATUSES[section] and not (section == "## Work list" and is_work_status(status)):
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


def _replace_table(lines, section, group, new_header, new_rows):
    """Replace the table under section (and optional ### group) with new_header + new_rows."""
    for h, hc, rs, sec, g in tables(lines):
        if sec == section and (group is None or g == group):
            sep = "|" + "|".join(["---"] * len(new_header)) + "|"
            end = (rs[-1] if rs else h + 1) + 1
            return lines[:h] + [make_row(new_header), sep] + new_rows + lines[end:]
    return lines


def _worktree_merge_base(root):
    """Return merge-base SHA with main if `root` is a linked git worktree (not the main checkout), else None."""
    if not root or not os.path.isdir(root):
        return None
    r_dir = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=root, capture_output=True, text=True)
    r_comm = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=root, capture_output=True, text=True)
    if r_dir.returncode != 0 or r_comm.returncode != 0:
        return None
    gdir = os.path.realpath(os.path.join(root, r_dir.stdout.strip()))
    cdir = os.path.realpath(os.path.join(root, r_comm.stdout.strip()))
    if gdir == cdir:
        return None
    r_mb = subprocess.run(["git", "merge-base", "HEAD", "main"], cwd=root, capture_output=True, text=True)
    return r_mb.stdout.strip() if r_mb.returncode == 0 and r_mb.stdout.strip() else None


def _index_row_map(text, sections):
    """Return {ident: (section, group, line)} for every table row in `sections`."""
    if not text:
        return {}
    lines = text.split("\n")
    out = {}
    for _, _, rs, sec, g in tables(lines):
        if sec in sections:
            for r in rs:
                ident = row_id(lines[r])
                if ident:
                    out[ident] = (sec, g, lines[r])
    return out


def _branch_comitatus_skips(live, archive, rulings_dir, notes=None):
    """In a job worktree, find comitatus rulings whose index line this branch didn't change since its
    merge base with main, but which differ from live comitatus/rulings/. Returns {ident: (where, subj, row)}
    and appends `note: <ID> is newer in comitatus...` to `notes` when given."""
    if rulings_dir is None or archive is None:
        return {}
    dirs = _folders(rulings_dir)
    if len(dirs) < 2:
        return {}
    d0 = os.path.abspath(dirs[0])
    if os.path.basename(d0) != "rulings" or os.path.basename(os.path.dirname(d0)) != "03_Past_Decisions":
        return {}
    root = os.path.dirname(os.path.dirname(d0))
    base = _worktree_merge_base(root)
    if not base:
        return {}
    local_r = os.path.realpath(d0)
    cdirs = [d for d in dirs if os.path.realpath(d) != local_r]
    if not cdirs:
        return {}
    c_entries = read_entries(cdirs)
    n_entries = read_entries(dirs[0])
    r_live = subprocess.run(["git", "show", f"{base}:{LIVE}"], cwd=root, capture_output=True, text=True)
    r_arch = subprocess.run(["git", "show", f"{base}:{ARCHIVE}"], cwd=root, capture_output=True, text=True)
    base_live_map = _index_row_map(r_live.stdout if r_live.returncode == 0 else "", RULING_SECTIONS)
    base_arch_map = _index_row_map(r_arch.stdout if r_arch.returncode == 0 else "", {"## Superseded decisions"})
    cur_live = _index_row_map(live, RULING_SECTIONS)
    cur_arch = _index_row_map(archive, {"## Superseded decisions"})

    candidates = set(c_entries) | {
        ident for ident in (set(cur_live) | set(cur_arch))
        if ident not in n_entries and ident not in c_entries and kind_of(ident) == "P"
    }
    preserve = {}
    for ident in sorted(candidates, key=lambda x: key(f"| {x} |")):
        cur_l = cur_live.get(ident)
        cur_a = cur_arch.get(ident)
        if cur_l != base_live_map.get(ident) or cur_a != base_arch_map.get(ident):
            continue
        if ident in c_entries:
            e = c_entries[ident]
            st = e["meta"].get("Status", "")
            expected = index_row(e)
            if st in ("Active", "Tentative"):
                exp_sec = "## Principles" if kind_of(ident) == "G" else "## Decisions"
                exp_grp = e["meta"].get("Subject", "") if exp_sec == "## Decisions" else None
                if (cur_a is None and cur_l is not None and cur_l[0] == exp_sec
                        and (exp_sec != "## Decisions" or cur_l[1] == exp_grp) and cur_l[2] == expected):
                    continue
            elif st == "Superseded":
                if cur_l is None and cur_a is not None and cur_a[2] == expected:
                    continue
            else:
                continue
        if cur_l is not None:
            preserve[ident] = ("live", cur_l[1], cur_l[2])
        elif cur_a is not None:
            preserve[ident] = ("archive", None, cur_a[2])
        else:
            preserve[ident] = ("omit", None, None)
        if notes is not None:
            notes.append(f"note: {ident} is newer in comitatus than this branch's index; merging main brings it")
    return preserve


def generate_indexes(live, archive, entries, work_entries=None, question_entries=None, preserve=None):
    """Rebuild generated indexes in live and archive for rulings, work items, and questions."""
    lines = live.split("\n")
    alines = archive.split("\n") if archive is not None else None
    preserve = preserve or {}

    if entries is not None:
        active_p_items = [
            (e["id"], index_row(e)) for e in entries.values()
            if e["id"] not in preserve and kind_of(e["id"]) == "G" and e["meta"].get("Status") in ("Active", "Tentative")
        ]
        active_d_items = [
            (e["id"], e["meta"].get("Subject", ""), index_row(e)) for e in entries.values()
            if e["id"] not in preserve and kind_of(e["id"]) != "G" and e["meta"].get("Status") in ("Active", "Tentative")
        ]
        superseded_items = [
            (e["id"], index_row(e)) for e in entries.values()
            if e["id"] not in preserve and e["meta"].get("Status") == "Superseded"
        ]
        for ident, (where, subj, row_str) in preserve.items():
            if where == "live" and kind_of(ident) == "G":
                active_p_items.append((ident, row_str))
            elif where == "live":
                active_d_items.append((ident, subj, row_str))
            elif where == "archive":
                superseded_items.append((ident, row_str))
        active_p_items.sort(key=lambda item: key(f"| {item[0]} |"))
        active_d_items.sort(key=lambda item: key(f"| {item[0]} |"))
        superseded_items.sort(key=lambda item: key(f"| {item[0]} |"))
        lines = _replace_table(lines, "## Principles", None, ["ID", "Principle", "Status"],
                               [row_str for _, row_str in active_p_items])

        if "## Subjects" in lines and "## Decisions" in lines:
            order = [cells(lines[r])[0] for h, hc, rs, sec, g in tables(lines) if sec == "## Subjects" for r in rs]
            by_subj = {}
            for ident, subj, row_str in active_d_items:
                by_subj.setdefault(subj, []).append((ident, row_str))

            a, b = section_range(lines, "## Decisions")
            first = next((k for k in range(a, b) if lines[k].startswith("### ")), b)
            body = []
            for subj in order:
                rows_out = [row_str for _, row_str in by_subj.get(subj, [])]
                body += [f"### {subj}", "", "| ID | Decision | Status |", "|---|---|---|"] + rows_out + [""]
            lines = lines[:first] + body + lines[b:]

            for h, hc, rs, sec, g in tables(lines):
                if sec == "## Subjects" and "Decisions" in hc:
                    col = hc.index("Decisions")
                    for r in rs:
                        c = cells(lines[r])
                        c[col] = ", ".join(ident for ident, _ in by_subj.get(c[0], [])) or NONE
                        lines[r] = make_row(c)
        if alines is not None:
            alines = _replace_table(alines, "## Superseded decisions", None, ["ID", "Decision", "Status"],
                                    [row_str for _, row_str in superseded_items])

    if work_entries is not None:
        open_w = sorted(
            [e for e in work_entries.values() if e["meta"].get("Status") != "Done"],
            key=lambda e: key(f"| {e['id']} |"),
        )
        done_w = sorted(
            [e for e in work_entries.values() if e["meta"].get("Status") == "Done"],
            key=lambda e: key(f"| {e['id']} |"),
        )
        lines = _replace_table(lines, "## Work list", None, ["#", "Item", "Status"], [index_row(e) for e in open_w])
        if alines is not None:
            alines = _replace_table(alines, "## Done work", None, ["#", "Item", "Status"], [index_row(e) for e in done_w])

    if question_entries is not None:
        open_q = sorted(
            [e for e in question_entries.values() if e["meta"].get("Status") != "Decided"],
            key=lambda e: key(f"| {e['id']} |"),
        )
        decided_q = sorted(
            [e for e in question_entries.values() if e["meta"].get("Status") == "Decided"],
            key=lambda e: key(f"| {e['id']} |"),
        )
        lines = _replace_table(lines, "## Open questions", None, ["#", "Question", "Status"], [index_row(e) for e in open_q])
        if alines is not None:
            alines = _replace_table(alines, "## Decided questions", None, ["#", "Question", "Status"], [index_row(e) for e in decided_q])

    return "\n".join(lines), ("\n".join(alines) if alines is not None else None)


def _legacy_rows_in(text, sections):
    """[(line_idx, section, group, row_str, ident)] for full legacy rows (>= 4 columns) in sections."""
    lines = text.split("\n")
    out = []
    for h, hc, rs, sec, g in tables(lines):
        if sec in sections:
            for r in rs:
                if len(hc) >= 4 or len(cells(lines[r])) >= 4:
                    ident = row_id(lines[r])
                    if ident:
                        out.append((r, sec, g, lines[r], ident))
    return out


def _ruling_rows_in(text):
    """[(line_idx, section, group, row_str, ident)] for full ruling rows (>= 4 columns) in ruling sections."""
    return _legacy_rows_in(text, RULING_SECTIONS)


def _qt_rows_in(text, sections=QT_SECTIONS):
    """[(line_idx, section, group, row_str, ident)] for full Q/T rows (>= 4 columns) in Q/T sections."""
    return _legacy_rows_in(text, sections)


def _atomize_section_rows(texts, sections, target_dir, row_converter, dry_run):
    """Move legacy table rows in `sections` + their ### Details into `target_dir/<ID>.md`."""
    extra = {}
    for idx in (0, 1):
        if texts[idx] is None:
            continue
        rrows = _legacy_rows_in(texts[idx], sections)
        if not rrows:
            continue
        lines = texts[idx].split("\n")
        for r, sec, g, row_str, ident in sorted(rrows, reverse=True):
            del lines[r]
        texts[idx] = "\n".join(lines)
        for r, sec, g, row_str, ident in rrows:
            det_lines = None
            for k in (0, 1):
                if texts[k] is not None:
                    texts[k], taken = take_details(texts[k], ident)
                    if taken is not None and det_lines is None:
                        det_lines = taken
            _, content = row_converter(row_str, sec, g, det_lines)
            if not dry_run:
                write_dir = target_dir[0] if isinstance(target_dir, (list, tuple)) else target_dir
                write_entry(write_dir, ident, content)
            extra[ident] = parse_entry(content, ident=ident)
    return extra


def tidy(live, archive, rulings_dir=None, work_dir=None, questions_dir=None, dry_run=False, notes=None, _preserve=None):
    """(live, archive) with entry rows atomized (when their dirs are set), archival rows moved,
    Details beside their rows, everything sorted and generated."""
    if _preserve is None:
        _preserve = _branch_comitatus_skips(live, archive, rulings_dir, notes=notes)
    extra_r, extra_w, extra_q = {}, {}, {}
    texts = [live, archive]
    if rulings_dir is not None:
        extra_r = _atomize_section_rows(texts, RULING_SECTIONS, rulings_dir, row_to_ruling, dry_run)
    if work_dir is not None:
        extra_w = _atomize_section_rows(texts, WORK_SECTIONS, work_dir, row_to_work, dry_run)
    if questions_dir is not None:
        extra_q = _atomize_section_rows(texts, QUESTION_SECTIONS, questions_dir, row_to_question, dry_run)
    live, archive = texts

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
    live, archive = sort_text(live), sort_text(archive)
    if any(d is not None for d in (rulings_dir, work_dir, questions_dir)):
        r_entries = None
        if rulings_dir is not None:
            r_entries = read_entries(rulings_dir)
            r_entries.update(extra_r)
        w_entries = None
        if work_dir is not None:
            w_entries = read_entries(work_dir)
            w_entries.update(extra_w)
        q_entries = None
        if questions_dir is not None:
            q_entries = read_entries(questions_dir)
            q_entries.update(extra_q)
        live, archive = generate_indexes(live, archive, r_entries, work_entries=w_entries, question_entries=q_entries, preserve=_preserve)
    return live, archive


def ids_of(text):
    return [row_id(l) for l in text.split("\n") if row_id(l)]


def _check_qt_folder(folder, live_idx, arch_idx, allowed_statuses, closed_status, allow_queued=False):
    """Validate status and index membership for work/ or questions/ files."""
    out = []
    entries = read_entries(folder)
    for ident, e in sorted(entries.items(), key=lambda kv: key(f"| {kv[0]} |")):
        st = e["meta"].get("Status", "")
        if st not in allowed_statuses and not (allow_queued and is_work_status(st)):
            out.append(f"{ident}: status '{st}' in {folder}/{ident}.md isn't one of {sorted(allowed_statuses)}")
        elif st == closed_status:
            if ident not in arch_idx:
                out.append(f"{ident}: {closed_status} file exists without an index line in {ARCHIVE}")
        else:
            if ident not in live_idx:
                out.append(f"{ident}: file exists without an index line in {LIVE}")
    for ident in sorted(set(live_idx) | set(arch_idx), key=lambda x: key(f"| {x} |")):
        if ident not in entries:
            out.append(f"{ident} is in the index without a file in {folder}")
    return out


def layout_problems(live, archive, rulings_dir=None, work_dir=None, questions_dir=None, skip_ids=()):
    """Problems that tidying can't fix: an ID in both files, the index and the subject headings out of step,
    a decision naming a principle that doesn't exist, or entry files out of sync with the indexes."""
    skip_ids = set(skip_ids)
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

    alines = archive.split("\n")
    if work_dir is not None:
        live_w_idx = {row_id(lines[r]) for h, hc, rs, sec, g in tables(lines)
                      if sec == "## Work list" for r in rs if row_id(lines[r])}
        arch_w_idx = {row_id(alines[r]) for h, hc, rs, sec, g in tables(alines)
                      if sec == "## Done work" for r in rs if row_id(alines[r])}
        out += _check_qt_folder(work_dir, live_w_idx, arch_w_idx, STATUSES["## Work list"], "Done", allow_queued=True)

    if questions_dir is not None:
        live_q_idx = {row_id(lines[r]) for h, hc, rs, sec, g in tables(lines)
                      if sec == "## Open questions" for r in rs if row_id(lines[r])}
        arch_q_idx = {row_id(alines[r]) for h, hc, rs, sec, g in tables(alines)
                      if sec == "## Decided questions" for r in rs if row_id(alines[r])}
        out += _check_qt_folder(questions_dir, live_q_idx, arch_q_idx, STATUSES["## Open questions"], "Decided")

    if rulings_dir is not None:
        rdirs = _folders(rulings_dir)
        if len(rdirs) > 1:
            by_dir = [(d, set(folder_ids(d))) for d in rdirs]
            for i in range(len(by_dir)):
                for j in range(i + 1, len(by_dir)):
                    for ident in sorted(by_dir[i][1] & by_dir[j][1], key=lambda x: key(f"| {x} |")):
                        out.append(f"{ident} is in both {by_dir[i][0]} and {by_dir[j][0]}")
        entries = read_entries(rulings_dir)
        live_idx = {row_id(lines[r]): (sec, g) for h, hc, rs, sec, g in tables(lines)
                    if sec in ("## Principles", "## Decisions") for r in rs if row_id(lines[r])}
        arch_idx = {row_id(alines[r]): sec for h, hc, rs, sec, g in tables(alines)
                    if sec == "## Superseded decisions" for r in rs if row_id(alines[r])}
        principles_set = {ident for ident, e in entries.items()
                          if kind_of(ident) == "G" and e["meta"].get("Status") in ("Active", "Tentative")}
        for ident, e in sorted(entries.items(), key=lambda kv: key(f"| {kv[0]} |")):
            if ident in skip_ids:
                continue
            st = e["meta"].get("Status", "")
            if st not in ("Active", "Tentative", "Superseded"):
                out.append(f"{ident}: status '{st}' in {rulings_dir}/{ident}.md isn't Active, Tentative, or Superseded")
            elif st in ("Active", "Tentative"):
                if ident not in live_idx:
                    out.append(f"{ident}: ruling file exists without an index line in {LIVE}")
                if kind_of(ident) != "G":
                    subj = e["meta"].get("Subject", "")
                    if subj not in index:
                        out.append(f"{ident}: subject '{subj}' isn't in ## Subjects")
                    pcell = e["meta"].get("Principles", "")
                    if not pcell:
                        out.append(f"{ident}: no principle named (write {NONE} if none fits yet)")
                    for p in re.findall(CITE, pcell):
                        if p not in principles_set:
                            out.append(f"{ident} names principle {p}, which isn't an Active/Tentative principle")
            elif st == "Superseded":
                if ident not in arch_idx:
                    out.append(f"{ident}: Superseded ruling file exists without an index line in {ARCHIVE}")
        for ident in sorted(set(live_idx) | set(arch_idx), key=lambda x: key(f"| {x} |")):
            if ident in skip_ids:
                continue
            if ident not in entries:
                out.append(f"{ident} is in the index without a ruling file in {rulings_dir}")
        return out

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


def _read_queue_jobs(root):
    """Read live queue jobs from git-common-dir/napkin-jobs.json if available, else {}."""
    candidates = []
    try:
        r = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=root, capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            cdir = os.path.realpath(os.path.join(root, r.stdout.strip()))
            candidates.append(os.path.join(cdir, "napkin-jobs.json"))
    except OSError:
        pass
    candidates.append(os.path.join(root, ".git", "napkin-jobs.json"))
    for p in candidates:
        try:
            data = json.load(open(p, encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("jobs"), dict):
                return data["jobs"]
        except (OSError, ValueError):
            pass
    return {}


def _entry_author_fields(text):
    meta_line = next((l for l in text.splitlines() if l.startswith("Author:")), "")
    fields = {}
    for part in meta_line.split(" | "):
        if ":" in part:
            k, v = part.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields


def _entry_items(text, head_line):
    items = re.findall(r"\bT\d+\b", head_line or "")
    for line in text.splitlines():
        if re.match(r"^(?:#{1,6}[ \t]+Response\b|\*\*Response\b|Response (?:—|from\b))", line):
            break
        if line.startswith("Author:") and " | " in line:
            for part in line.split(" | "):
                if part.strip().startswith(("Item:", "Completes:")):
                    items.extend(re.findall(r"\bT\d+\b", part))
        elif line.startswith(("Item:", "Completes:")):
            items.extend(re.findall(r"\bT\d+\b", line))
    return items


def _handoff_entry_state(fields, jid, queue_jobs):
    live = queue_jobs.get(jid)
    if isinstance(live, dict):
        qstate = live.get("state")
        who = live.get("agent", "?")
        if qstate in ("in progress", "waiting"):
            return f"in progress ({who})"
        if qstate == "done":
            return "for review"
        if qstate == "returned":
            return "ready"
    st = fields.get("Status", "").lower()
    if st.startswith("answered"):
        return "for review"
    if st.startswith("queued"):
        return "queued"
    if st.startswith("open"):
        return "ready"
    if st.startswith("in progress"):
        return "in progress"
    return None


def _archive_entry_state(text):
    res_lines = [l[len("Resolution:"):].strip() for l in text.splitlines() if l.startswith("Resolution:")]
    last_res = res_lines[-1] if res_lines else ""
    if re.match(r"^merged\b", last_res, re.I):
        m = re.search(r"(?m)^Result:\s*([0-9a-f]{7,})\b", text)
        if not m:
            m = re.search(r"^merged\s+([0-9a-f]{7,})\b", last_res, re.I)
        if m:
            return f"merged {m.group(1)[:7]}"
        return "merged"
    return "dropped"


def _handoff_item_jobs(root, queue_jobs=None):
    """Map Work list ID -> {job ID: state} from docs/handoff/ and docs/handoff-archive.md."""
    out = {}
    qjobs = queue_jobs if queue_jobs is not None else _read_queue_jobs(root)
    handoff_dir = os.path.join(root, "docs", "handoff")
    active_jids = set()
    if os.path.isdir(handoff_dir):
        for name in sorted(os.listdir(handoff_dir)):
            if not name.endswith(".md"):
                continue
            text = open(os.path.join(handoff_dir, name), encoding="utf-8").read()
            fields = _entry_author_fields(text)
            if fields.get("For", "").lower() not in ("claude", "codex", "gemini", "either"):
                continue
            head_m = re.search(r"(?m)^###\s+([A-Z]+\d+[a-z]*|[A-Z]+-new-\d+[a-z]*)\b(.*)$", text)
            jid = head_m.group(1) if head_m else name.split("-")[0]
            state = _handoff_entry_state(fields, jid, qjobs)
            if state is None:
                continue
            active_jids.add(jid)
            for tid in _entry_items(text, head_m.group(0) if head_m else ""):
                out.setdefault(tid, {})[jid] = state
    arch_path = os.path.join(root, "docs", "handoff-archive.md")
    if os.path.isfile(arch_path):
        arch_text = open(arch_path, encoding="utf-8").read()
        for chunk in re.split(r"(?m)^(?=### [A-Z]+\d+[a-z]*\b)", arch_text):
            head_m = re.match(r"(?m)^###\s+([A-Z]+\d+[a-z]*)\b(.*)$", chunk)
            if not head_m:
                continue
            jid = head_m.group(1)
            if jid in active_jids:
                continue
            fields = _entry_author_fields(chunk)
            if fields.get("For", "").lower() not in ("claude", "codex", "gemini", "either"):
                continue
            state = _archive_entry_state(chunk)
            for tid in _entry_items(chunk, head_m.group(0)):
                out.setdefault(tid, {})[jid] = state
    return out


def board_statuses(root, queue_state=None):
    """Sync Work list Status and Jobs lines from docs/handoff/, docs/handoff-archive.md, and queue state; returns changed descriptions."""
    wdir = os.path.join(root, WORK_DIR)
    if not os.path.isdir(wdir):
        return []
    qjobs = queue_state.get("jobs", {}) if isinstance(queue_state, dict) and "jobs" in queue_state else queue_state
    item_jobs = _handoff_item_jobs(root, queue_jobs=qjobs)
    changed = []
    for ident in folder_ids(wdir):
        path = os.path.join(wdir, f"{ident}.md")
        raw = open(path, encoding="utf-8").read()
        entry = parse_entry(raw, ident=ident)
        status = entry["meta"].get("Status", "")
        old_jobs = entry["meta"].get("Jobs", "")
        jobs_map = item_jobs.get(ident, {})
        ordered_jobs = sorted(jobs_map.items(), key=lambda kv: key(f"| {kv[0]} |"))
        new_jobs = " · ".join(f"{jid} {st}" for jid, st in ordered_jobs)
        new_status = status
        if status == "Open" or PICKED_UP.match(status) or ON_BOARD.match(status) or LEGACY_QUEUED.match(status):
            unfinished = [jid for jid, st in ordered_jobs if not st.startswith("merged") and st != "dropped"]
            if unfinished:
                new_status = f"On the board ({', '.join(unfinished)})"
            else:
                new_status = "Open"
        if new_status != status or new_jobs != old_jobs:
            new_raw = format_work(
                ident,
                entry["body"],
                new_status,
                covers=entry["meta"].get("Covers", ""),
                jobs=new_jobs,
                result=entry["result"],
                details=entry["details"],
            )
            if new_raw != raw:
                open(path, "w", encoding="utf-8").write(new_raw)
                changed.append(f"{ident}: {new_status}" if new_status != status else f"{ident}: jobs updated")
    if changed:
        live_p = os.path.join(root, LIVE)
        arch_p = os.path.join(root, ARCHIVE)
        if os.path.isfile(live_p) and os.path.isfile(arch_p):
            rdir = os.path.join(root, RULINGS_DIR)
            qdir = os.path.join(root, QUESTIONS_DIR)
            l2, a2 = tidy(
                open(live_p, encoding="utf-8").read(),
                open(arch_p, encoding="utf-8").read(),
                rulings_dir=ruling_dirs(root) if (os.path.isdir(rdir) or comitatus_rulings_dir(root)) else None,
                work_dir=wdir,
                questions_dir=qdir if os.path.isdir(qdir) else None,
            )
            open(live_p, "w", encoding="utf-8").write(l2)
            open(arch_p, "w", encoding="utf-8").write(a2)
    return changed


def check_files(live, archive=None, rulings_dir=None, work_dir=None, questions_dir=None, notes=None):
    """Every problem with the log (both files when there's an archive)."""
    if archive is None:
        out = [] if sort_text(live) == live else [f"{LIVE} is not sorted by ID: run python3 02_Habits/WHEN_THE_LOG_IS_COMMITTED_TIDY_IT.py"]
        return out + details_problems(live) + status_problems(live)
    preserve = _branch_comitatus_skips(live, archive, rulings_dir, notes=notes)
    out = []
    for folder, sections in ((rulings_dir, RULING_SECTIONS), (work_dir, WORK_SECTIONS), (questions_dir, QUESTION_SECTIONS)):
        if folder is None:
            continue
        existing = set(folder_ids(folder))
        for name, text in ((LIVE, live), (ARCHIVE, archive)):
            for _, _, _, _, ident in _legacy_rows_in(text, sections):
                if ident in existing:
                    out.append(f"{ident} is in both {name} and {folder}/{ident}.md")
                else:
                    out.append(f"{ident} is still a table row in {name}: run python3 02_Habits/WHEN_THE_LOG_IS_COMMITTED_TIDY_IT.py")
    l2, a2 = tidy(live, archive, rulings_dir=rulings_dir, work_dir=work_dir, questions_dir=questions_dir, dry_run=True, _preserve=preserve)
    if l2 != live:
        out.append(f"{LIVE} is not tidy: run python3 02_Habits/WHEN_THE_LOG_IS_COMMITTED_TIDY_IT.py")
    if a2 != archive:
        out.append(f"{ARCHIVE} is not tidy: run python3 02_Habits/WHEN_THE_LOG_IS_COMMITTED_TIDY_IT.py")
    for name, text in ((LIVE, live), (ARCHIVE, archive)):
        out += [f"{name}: {p}" for p in details_problems(text) + status_problems(text)]
    return out + layout_problems(live, archive, rulings_dir=rulings_dir, work_dir=work_dir, questions_dir=questions_dir, skip_ids=set(preserve))


def move_process_rulings(root, out=print):
    """Move numbered Subject: Process rulings from Napkin's rulings/ to comitatus's rulings/ and commit+push there."""
    org, _ = comitatus_root(root)
    if not org:
        return []
    rdir = os.path.join(root, RULINGS_DIR)
    cdir = os.path.join(org, RULINGS_DIR)
    if not os.path.isdir(rdir) or os.path.realpath(rdir) == os.path.realpath(cdir):
        return []
    moved = []
    for ident in folder_ids(rdir):
        if "-new-" in ident:
            continue
        entry = read_entry(rdir, ident)
        if entry and entry["meta"].get("Subject") == "Process":
            os.makedirs(cdir, exist_ok=True)
            shutil.move(os.path.join(rdir, f"{ident}.md"), os.path.join(cdir, f"{ident}.md"))
            moved.append(ident)
    if moved:
        import comitatus_commit
        rels = [os.path.join(RULINGS_DIR, f"{ident}.md") for ident in moved]
        comitatus_commit.commit(org, rels, f"Move Process rulings: {', '.join(moved)}", out=out, push=True)
        out(f"moved Process rulings to comitatus: {', '.join(moved)}")
    return moved


def main():
    if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
        print(__doc__)
        return
    args = [a for a in sys.argv[1:] if a not in ("--check", "--move-process")]
    live_path = args[0] if args else LIVE
    arch_path = args[1] if len(args) > 1 else os.path.join(os.path.dirname(live_path), os.path.basename(ARCHIVE))
    base_dir = os.path.dirname(os.path.abspath(live_path))
    root = os.path.dirname(base_dir)
    if "--move-process" in sys.argv:
        move_process_rulings(root)
        return
    rulings_dir = os.path.join(base_dir, "rulings")
    if os.path.realpath(base_dir) == os.path.realpath(os.path.join(root, "03_Past_Decisions")):
        cdir = comitatus_rulings_dir(root)
        rulings_arg = [rulings_dir, cdir] if (cdir and os.path.realpath(cdir) != os.path.realpath(rulings_dir)) else rulings_dir
    else:
        rulings_arg = rulings_dir
    work_dir = os.path.join(base_dir, "work")
    questions_dir = os.path.join(base_dir, "questions")
    live = open(live_path, encoding="utf-8").read()
    archive = open(arch_path, encoding="utf-8").read() if os.path.isfile(arch_path) else None
    if "--check" in sys.argv:
        notes = []
        problems = check_files(
            live, archive,
            rulings_dir=rulings_arg if archive is not None else None,
            work_dir=work_dir if archive is not None else None,
            questions_dir=questions_dir if archive is not None else None,
            notes=notes,
        )
        for n in notes:
            print(n)
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
    notes = []
    l2, a2 = tidy(live, archive, rulings_dir=rulings_arg, work_dir=work_dir, questions_dir=questions_dir, notes=notes)
    for n in notes:
        print(n)
    for path, old, new in ((live_path, live, l2), (arch_path, archive, a2)):
        if new != old:
            open(path, "w", encoding="utf-8").write(new)
            print(f"tidied {path}")


if __name__ == "__main__":
    main()
