#!/usr/bin/env python3
"""Sort the decision-log copy's tables by ID, so the file reads in order: A01, A02 ... A06, A06a, A07 ... then
D, I, M, P, W; Q1 ... Q31; T1 ... T49 (numbers in number order, a letter after a number comes after it).

  python3 tools/sort_decision_log.py [file]       default docs/decision-log.md; rewrites it only if it changes
  python3 tools/sort_decision_log.py --check      exit 1 if the file isn't sorted

Tables whose first column isn't an ID (Tunables: setting names, grouped by what they tune) keep their order.
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
    return "\n".join(out)


def main():
    args = [a for a in sys.argv[1:] if a != "--check"]
    path = args[0] if args else "docs/decision-log.md"
    text = open(path, encoding="utf-8").read()
    new = sort_text(text)
    if "--check" in sys.argv:
        if new != text:
            print(f"{path} is not sorted by ID: run python3 tools/sort_decision_log.py")
            sys.exit(1)
        return
    if new != text:
        open(path, "w", encoding="utf-8").write(new)
        print(f"sorted {path} by ID")


if __name__ == "__main__":
    main()
