#!/usr/bin/env python3
"""Sort the decision log's tables by ID, so the file reads in order: A01, A02 ... A06, A06a, A07 ... then
D, I, M, P, W; Q1 ... Q31; T1 ... T49 (numbers in number order, a letter after a number comes after it).

  python3 tools/sort_decision_log.py [file]       default docs/decision-log.md; rewrites it only if it changes
  python3 tools/sort_decision_log.py --check      exit 1 if the file isn't sorted

Tables whose first column isn't an ID (Tunables: setting names, grouped by what they tune) keep their order.
Under "## Details", each "### <ID>" section (the full text of a long decision) is sorted the same way, and
--check also fails when a row says "(Details below.)" without a section, or a section has no such row.
The pre-commit hook (.githooks/pre-commit) runs this whenever docs/decision-log.md is committed."""
import re
import sys

ID = re.compile(r"^([A-Z]+)(\d+)([a-z]*)$")


def key(row):
    m = ID.match(row.split("|")[1].strip())
    return (m.group(1), int(m.group(2)), m.group(3))


def sort_text(text):
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        # a table: a header row, a |---| row, then rows that start with "|"
        if lines[i].startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1]):
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            rows = lines[i + 2:j]
            if rows and all(ID.match(r.split("|")[1].strip()) for r in rows):
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
    while body and body[-1] == "":
        body.pop()
    return "\n".join(lines[:first] + body) + ("\n" if text.endswith("\n") else "")


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
    "## Decisions": {"Active", "Tentative"},
    "## Superseded decisions": {"Superseded"},
    "## Open questions": {"Open", "Decided", "Parked"},
    "## Work list": {"Open", "In progress", "Done", "Parked", "Split"},
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


def main():
    args = [a for a in sys.argv[1:] if a != "--check"]
    path = args[0] if args else "docs/decision-log.md"
    text = open(path, encoding="utf-8").read()
    new = sort_text(text)
    if "--check" in sys.argv:
        if new != text:
            print(f"{path} is not sorted by ID: run python3 tools/sort_decision_log.py")
            sys.exit(1)
        problems = details_problems(text) + status_problems(text)
        if problems:
            print("\n".join(problems))
            sys.exit(1)
        return
    if new != text:
        open(path, "w", encoding="utf-8").write(new)
        print(f"sorted {path} by ID")


if __name__ == "__main__":
    main()
