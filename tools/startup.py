#!/usr/bin/env python3
"""Session startup report (T56): run this instead of reading the big documents.

  python3 tools/startup.py            checkout, worktrees, recent main, unmerged agent branches, Ready board jobs
  python3 tools/startup.py T54 [...]  also each Work list row asked for, with the rows its Covers column cites

Read-only. Works from any worktree: the board and the decision log are read from main (`git show main:<path>`),
since a worktree's copy can be stale."""
import re
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ID_RE = re.compile(r"\b([A-Z]{1,2}\d+[a-z]?)\b")
SHORT = 200


def git(*args, cwd=None):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def parse_worktrees(text):
    """`git worktree list --porcelain` -> [(path, branch)]; branch is '(detached)' when there's none."""
    out, path, branch = [], None, None
    for line in text.splitlines() + [""]:
        if line.startswith("worktree "):
            path, branch = line[9:], "(detached)"
        elif line.startswith("branch "):
            branch = line[7:].removeprefix("refs/heads/")
        elif not line and path:
            out.append((path, branch))
            path = None
    return out


def parse_refs(text):
    """for-each-ref lines 'name|ahead behind|date' -> [(name, ahead, behind, date)]."""
    out = []
    for line in text.splitlines():
        parts = line.split("|")
        if len(parts) != 3 or not parts[1].strip():
            continue
        ahead, behind = (int(n) for n in parts[1].split())
        out.append((parts[0], ahead, behind, parts[2]))
    return out


def is_agent_branch(name):
    """Local branches other than main/small-fixes, and remote claude/* or codex/* (origin/claude/x)."""
    if name in ("main", "small-fixes", "origin") or name.endswith("/HEAD"):  # "origin" is origin/HEAD, shortened
        return False
    if name.startswith("origin/"):
        return name[7:].startswith(("claude/", "codex/"))
    return True


def agent_branches(refs):
    """-> (unmerged [(name, ahead, date)], merged count); a remote copy of a local branch is skipped."""
    local = {n for n, *_ in refs if not n.startswith("origin/")}
    shown, hidden = [], 0
    for name, ahead, _behind, date in refs:
        if not is_agent_branch(name) or (name.startswith("origin/") and name[7:] in local):
            continue
        if ahead:
            shown.append((name, ahead, date))
        else:
            hidden += 1
    return shown, hidden


def section(text, heading):
    """Lines under '## heading' up to the next '## '."""
    lines, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip() == heading
        elif inside:
            lines.append(line)
    return lines


def cells(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def ready_jobs(board, branch_names):
    """Board's Jobs rows whose Status contains Ready -> [(job, for, item, claimed_by or None)]."""
    out = []
    for line in section(board, "Jobs"):
        if not line.startswith("|"):
            continue
        c = cells(line)
        if len(c) < 4 or "Ready" not in c[2]:
            continue
        job = c[0]
        claim = next((b for b in branch_names if job.lower() in b.lower()), None)
        out.append((job, c[1], c[3], claim))
    return out


def notes(board, n=3):
    return [l for l in section(board, "Notes") if l.strip()][:n]


def find_row(log, ident):
    """The first table row in the log whose first cell is ident, or None."""
    for line in log.splitlines():
        if line.startswith("|") and cells(line)[0] == ident:
            return line
    return None


def work_list_ids(log):
    return {cells(l)[0] for l in section(log, "Work list") if l.startswith("| ") and not l.startswith("| #")}


def cited_ids(row):
    """IDs in a Work list row's Covers column (4th cell)."""
    c = cells(row)
    return ID_RE.findall(c[3]) if len(c) > 3 else []


def shorten(row, n=SHORT):
    row = row.strip()
    return row if len(row) <= n else row[: n - 3] + "..."


def details_note(row):
    return "  (has a ### section under Details)" if "(Details below.)" in row else ""


def report_ids(log, ids):
    """Lines for each ID asked for; returns (lines, unknown IDs)."""
    lines, unknown, wl = [], [], work_list_ids(log)
    for ident in ids:
        row = find_row(log, ident)
        if row is None:
            unknown.append(ident)
            lines.append(f"{ident}: not found in docs/decision-log.md")
            continue
        lines.append(f"== {ident}")
        lines.append(row.strip() + details_note(row))
        if ident in wl:
            for cid in cited_ids(row):
                crow = find_row(log, cid)
                lines.append(f"  {cid}: " + (shorten(crow) + details_note(crow) if crow else "not found"))
    return lines, unknown


def main(argv):
    root = git("rev-parse", "--show-toplevel").strip()
    if not root:
        print("startup.py: not inside a git checkout")
        return 1
    branch = git("branch", "--show-current", cwd=root).strip() or "(detached)"
    changed = [l for l in git("status", "--porcelain", cwd=root).splitlines() if l.strip()]
    print(f"This checkout: {root} on {branch}, " + ("clean" if not changed else f"{len(changed)} changed file" + ("s" if len(changed) > 1 else "")))

    refs = parse_refs(git("for-each-ref", "--format=%(refname:short)|%(ahead-behind:main)|%(committerdate:short)",
                          "refs/heads", "refs/remotes", cwd=root))
    merged = {n for n, a, b, _ in refs if a == 0 and b > 0}
    trees = parse_worktrees(git("worktree", "list", "--porcelain", cwd=root))
    shown = [(p, b) for p, b in trees if b not in merged or p == root]
    print(f"Worktrees ({len(trees) - len(shown)} on merged branches hidden):")
    for p, b in shown:
        print(f"  {p}  [{b}]")

    print("Recent main:")
    for l in git("log", "--oneline", "-5", "main", cwd=root).splitlines():
        print("  " + l)

    unmerged, hidden = agent_branches(refs)
    print(f"Branches with commits not on main ({hidden} merged branches hidden):")
    for name, ahead, date in unmerged:
        print(f"  {name}  +{ahead}  last {date}")
    if not unmerged:
        print("  (none)")

    board = git("show", "main:BOARD.md", cwd=root)
    jobs = ready_jobs(board, [n for n, *_ in refs])
    print("Ready on the board (main:BOARD.md):")
    for job, who, item, claim in jobs:
        print(f"  {job} ({who}) {item}" + (f"  - claimed by {claim}" if claim else ""))
    if not jobs:
        print("  (none)")
    for l in notes(board):
        print("  Note: " + l.strip().removeprefix("- "))

    import handoff   # the open jobs' Touches lists, from main (P11): a file two open jobs both list
    names = [l.split("/")[-1] for l in git("ls-tree", "--name-only", "main", "docs/handoff/", cwd=root).splitlines()
             if l.endswith(".md")]
    clash = handoff.overlaps_in({n: git("show", f"main:docs/handoff/{n}", cwd=root) for n in names})
    for path, ids in clash:
        print(f"  OVERLAP: {path} is in {' and '.join(ids)}: only one of them should be open (P11)")

    if argv:
        log = git("show", "main:docs/decision-log.md", cwd=root)
        lines, unknown = report_ids(log, argv)
        print()
        print("Decision log (main:docs/decision-log.md):")
        print("\n".join(lines))
        if unknown:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
