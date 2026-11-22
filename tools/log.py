#!/usr/bin/env python3
"""Add to and read the decision log (T92, P09, P23) without editing its tables by hand.

  python3 tools/log.py add <kind> "<text>" [options]   add a row; prints the row it wrote
  python3 tools/log.py note <ID> "<text>"              append text to a Work list row's last column
  python3 tools/log.py show <subject|ID> [--top]       print only what you need to read
  python3 tools/log.py show --top                      the log's top: header, Subjects, Principles

add's kind is an ID letter: G (a principle), Q (an open question), T (a Work list item), or any other letter
(A, I, P, M, D, U, W ...) for a decision. Options:
  --subject S       a decision's subject, a row of the Subjects index (required for decisions; --area is the same)
  --principles P    a decision's principles, "G01,G04", or "—" if none fits yet (required for decisions)
  --rel "..."       Replaces / replaced by (a decision), or Covers (a Work list item)
  --why "..."       Why (a decision), or Notes (a question)
  --where "..."     Where in the code (a decision)
  --covers "..."    Covers (a Work list item; same as --rel)
  --result "..."    Result / next step (a Work list item)
  --status S        default Active (decisions, principles) or Open (questions, Work list items)
The row gets the next free number of its kind when run on main (the integrator, counting both files and the
handoff as tools/number_ids.py does), else the kind's next placeholder (I-new-N, T74), which number_ids.py
numbers at merge. Decisions and principles are dated today. The log is tidied with tools/sort_decision_log.py
afterwards, so the row lands in ID order.

show <subject> prints that subject's ### group under ## Decisions (a unique start of the name is enough; case
doesn't matter); with --top, the log's top first. show <ID> prints its row (from whichever file holds it, under
its table's header), its "### <ID>" Details if it has them, and the principles it names. Exit 1 if not found."""
import datetime
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import number_ids
import sort_decision_log as s

LIVE, ARCHIVE = s.LIVE, s.ARCHIVE
# kind -> (section, column order: which option fills each column after ID and the text)
COLUMNS = {
    "G": ("## Principles", ["status", "explains", "date"]),
    "Q": ("## Open questions", ["status", "notes"]),
    "T": ("## Work list", ["status", "covers", "result"]),
}
DECISION = ["status", "rel", "why", "principles", "where", "date"]
KIND = re.compile(r"^[A-Z]$")


class LogError(Exception):
    pass


def read(root, rel):
    path = os.path.join(root, rel)
    return open(path, encoding="utf-8").read() if os.path.isfile(path) else None


def write(root, rel, text):
    open(os.path.join(root, rel), "w", encoding="utf-8").write(text)


def branch(root):
    try:
        return subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def subjects(live):
    lines = live.split("\n")
    return [s.cells(lines[r])[0] for h, hc, rs, sec, g in s.tables(lines) if sec == "## Subjects" for r in rs]


def principles(live):
    lines = live.split("\n")
    return {s.cells(lines[r])[0]: lines[r] for h, hc, rs, sec, g in s.tables(lines) if sec == "## Principles" for r in rs}


def match_subject(live, name):
    """The Subjects index entry that name is (exactly, or a unique start of it, case ignored)."""
    names = subjects(live)
    low = name.strip().lower()
    exact = [n for n in names if n.lower() == low]
    if exact:
        return exact[0]
    start = [n for n in names if n.lower().startswith(low)]
    if len(start) == 1:
        return start[0]
    what = f"'{name}' could be {', '.join(start)}" if start else f"no subject '{name}'"
    raise LogError(f"{what}; the subjects are: {', '.join(names)}")


def next_id(root, kind, on_main):
    """The next free number of the kind on main; else the kind's next placeholder on this branch."""
    if on_main:
        hi, width = number_ids.taken(root).get(kind, (0, 2))
        return f"{kind}{hi + 1:0{width}d}"
    cited = number_ids.plan(root)[1]
    n = max([m for k, m in cited if k == kind], default=0)
    return f"{kind}-new-{n + 1}"


def clean(text, what):
    text = " ".join((text or "").split())
    if "|" in text:
        raise LogError(f"{what} can't contain '|' (it splits a table cell)")
    return text


def add(root, kind, text, opts, on_main=None, today=None):
    """Add a row; returns it as written (after tidying)."""
    if not KIND.match(kind or "") or kind == "H":
        raise LogError(f"kind must be one ID letter (G, Q, T or a decision's letter, not H): got '{kind}'")
    live, archive = read(root, LIVE), read(root, ARCHIVE)
    if live is None:
        raise LogError(f"no {LIVE} under {root}")
    on_main = branch(root) == "main" if on_main is None else on_main
    today = today or datetime.date.today().isoformat()
    text = clean(text, "the text")
    if not text:
        raise LogError("the text is empty")
    o = {("subject" if k == "area" else k): clean(v, "--" + k) for k, v in opts.items() if v is not None}
    if kind == "T" and "rel" in o:
        o.setdefault("covers", o.pop("rel"))
    if kind == "Q" and "why" in o:
        o.setdefault("notes", o.pop("why"))
    group = None
    if kind in COLUMNS:
        section, cols = COLUMNS[kind]
        used = set(cols) - {"status", "explains", "date"}
        stray = sorted(set(o) - used - {"status"})
        if stray:
            raise LogError(f"{kind} rows don't take --{', --'.join(stray)} (they take: --{', --'.join(sorted(used | {'status'}))})")
        o.setdefault("status", "Active" if kind == "G" else "Open")
        o.setdefault("explains", s.NONE)
        o["date"] = today
    else:
        section, cols = "## Decisions", DECISION
        if "subject" not in o:
            raise LogError("a decision needs --subject (one of: " + ", ".join(subjects(live)) + ")")
        group = match_subject(live, o.pop("subject"))
        if "principles" not in o:
            raise LogError(f"a decision needs --principles (G01,G04 ... or {s.NONE} if none fits yet)")
        names = re.findall(r"\b[A-Z]+(?:\d+|-new-\d+)[a-z]*\b", o["principles"])
        if not names and o["principles"] != s.NONE:
            raise LogError(f"--principles should name principles (G01,G04) or be {s.NONE}")
        known = principles(live)
        missing = [p for p in names if p not in known and "-new-" not in p]
        if missing:
            raise LogError(f"no principle {', '.join(missing)} (they are: {', '.join(known)})")
        if names:
            o["principles"] = ", ".join(names)
        stray = sorted(set(o) - set(DECISION))
        if stray:
            raise LogError(f"decisions don't take --{', --'.join(stray)}")
        o.setdefault("status", "Active")
        o["date"] = today
    allowed = s.STATUSES[section]
    if o["status"] not in allowed:
        raise LogError(f"status '{o['status']}' isn't one of {', '.join(sorted(allowed))} ({section[3:]})")
    ident = next_id(root, kind, on_main)
    row = s.make_row([ident, text] + [o.get(c, "") for c in cols])
    live = s.insert_row(live, row, section, group)
    if archive is None:
        new_live, new_arch = s.sort_text(live), None
    else:
        new_live, new_arch = s.tidy(live, archive)
        if new_arch != archive:
            write(root, ARCHIVE, new_arch)
    write(root, LIVE, new_live)
    for text_ in (new_live, new_arch or ""):
        lines = text_.split("\n")
        i = s.find_row(lines, ident)
        if i is not None:
            return lines[i]
    return row


def note(root, ident, text):
    """Append text to the last column of a Work list row in the live file; returns the row."""
    live = read(root, LIVE)
    if live is None:
        raise LogError(f"no {LIVE} under {root}")
    text = clean(text, "the note")
    if not text:
        raise LogError("the note is empty")
    lines = live.split("\n")
    i = s.find_row(lines, ident)
    if i is None or s.where(live, ident)[0] != "## Work list":
        held = s.where(live, ident) or s.where(read(root, ARCHIVE) or "", ident)
        raise LogError(f"{ident} isn't in the Work list" + (f" (it's under {held[0][3:]})" if held else ""))
    c = s.cells(lines[i])
    c[-1] = f"{c[-1]} {text}" if c[-1] else text
    lines[i] = s.make_row(c)
    write(root, LIVE, "\n".join(lines))
    return lines[i]


def top(live):
    lines = live.split("\n")
    end = lines.index("## Decisions") if "## Decisions" in lines else len(lines)
    while end and lines[end - 1] == "":
        end -= 1
    return "\n".join(lines[:end])


def subject_group(live, name):
    lines = live.split("\n")
    rng = s.section_range(lines, "## Decisions")
    head = "### " + name
    a = next(k for k in range(*rng) if lines[k] == head)
    b = next((k for k in range(a + 1, rng[1]) if lines[k].startswith("### ")), rng[1])
    body = lines[a:b]
    while body and body[-1] == "":
        body.pop()
    return "\n".join(body)


def show_id(root, ident):
    """Its row under its table's header, its Details, and the principles it names."""
    live = read(root, LIVE) or ""
    for rel in (LIVE, ARCHIVE):
        text = read(root, rel)
        if not text:
            continue
        lines = text.split("\n")
        for h, hc, rs, sec, g in s.tables(lines):
            for r in rs:
                if s.row_id(lines[r]) != ident:
                    continue
                out = [f"{rel}: {sec[3:]}" + (f" / {g}" if g else ""), "", lines[h], lines[h + 1], lines[r]]
                details = s.details_sections(text).get(ident)
                if details:
                    out += [""] + details
                if "Principles" in hc or "Area" in hc:
                    col = hc.index("Principles") if "Principles" in hc else hc.index("Area")
                    c = s.cells(lines[r])
                    known = principles(live)
                    named = [p for p in re.findall(s.CITE, c[col] if col < len(c) else "") if p in known]
                    if named:
                        out += ["", "Principles it names:", ""] + [known[p] for p in named]
                return "\n".join(out)
    raise LogError(f"no row {ident} in {LIVE} or {ARCHIVE}")


def show(root, what, with_top=False):
    live = read(root, LIVE)
    if live is None:
        raise LogError(f"no {LIVE} under {root}")
    parts = [top(live)] if with_top else []
    if what:
        if s.ROW.match(what):
            parts.append(show_id(root, what))
        else:
            parts.append(subject_group(live, match_subject(live, what)))
    elif not with_top:
        raise LogError("show what? a subject, an ID, or --top")
    return "\n\n".join(parts)


def parse(argv):
    """(positional args, {option: value}, flags)."""
    pos, opts, flags, i = [], {}, set(), 0
    while i < len(argv):
        a = argv[i]
        if a == "--top":
            flags.add("top")
        elif a.startswith("--"):
            name = a[2:]
            if "=" in name:
                name, val = name.split("=", 1)
            elif i + 1 < len(argv):
                i += 1
                val = argv[i]
            else:
                raise LogError(f"{a} needs a value")
            name = "subject" if name == "area" else name
            if name not in {"subject", "principles", "rel", "why", "where", "covers", "result", "notes", "status"}:
                raise LogError(f"unknown option {a}")
            opts[name] = val
        else:
            pos.append(a)
        i += 1
    return pos, opts, flags


def root_dir():
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    return out or os.getcwd()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        pos, opts, flags = parse(argv)
        if not pos:
            raise LogError(__doc__.split("\n\n")[1])
        cmd, rest, root = pos[0], pos[1:], root_dir()
        if cmd == "add":
            if len(rest) != 2:
                raise LogError('usage: log.py add <kind> "<text>" [options]')
            print(add(root, rest[0], rest[1], opts))
        elif cmd == "note":
            if len(rest) != 2 or opts:
                raise LogError('usage: log.py note <ID> "<text>"')
            print(note(root, rest[0], rest[1]))
        elif cmd == "show":
            if len(rest) > 1 or opts:
                raise LogError("usage: log.py show <subject|ID> [--top], or log.py show --top")
            print(show(root, rest[0] if rest else None, "top" in flags))
        else:
            raise LogError(f"unknown command '{cmd}' (add, note, show)")
    except LogError as e:
        print(f"log.py: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
