#!/usr/bin/env python3
"""Merge one agent branch into main (P-new-4): the integrator's steps, in one command.

  python3 tools/integrate.py <branch> --as <name> [--status T33=Done ...] [--push] [--no-gate] [--impact "<reason>"]

Run in the main checkout, on main, clean, holding the integrator lock (tools/integrator.py). In order:
 1. git merge --no-ff --no-commit <branch>
 2. conflicts it knows how to settle: docs/agent-handoff.md (main's text kept; an entry the branch answered inline,
    from before T77, moves into its docs/handoff/ file), docs/decision-log.md (main's text, plus every row the
    branch added or changed since it left main); any other conflict stops here, the merge left as it is
 3. the handoff entries the branch answered: Status resolved, a Resolution line, moved to the archive
 4. tools/number_ids.py (placeholders get numbers), then the decision-log and handoff checks
 5. tools/gate.sh (the quick and full tests, tests/known_failures.txt); a failing gate stops here, uncommitted
 6. commit ("Merge <branch>: <its subject>"; --impact adds an Architecture-Impact line), then --push pushes main
What it leaves to the integrator: reviewing the branch first, the Work list result, and BOARD.md."""
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import handoff
import integrator
import number_ids
import sort_decision_log

LOG = "docs/decision-log.md"


def git(*args, check=False, root=None):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r


def rows(text):
    """{ID: (section heading, row)} for every ID-keyed table row."""
    out, section = {}, None
    for line in text.split("\n"):
        if line.startswith("## "):
            section = line
        elif line.startswith("| ") and section:
            key = line.split("|")[1].strip()
            if sort_decision_log.ID.match(key):
                out[key] = (section, line)
    return out


def carry_rows(ours, base, theirs):
    """main's log plus the rows the branch added or changed since base (P09: only its own rows)."""
    b, t = rows(base), rows(theirs)
    lines = ours.split("\n")
    have = {l.split("|")[1].strip(): i for i, l in enumerate(lines) if l.startswith("| ") and sort_decision_log.ID.match(l.split("|")[1].strip())}
    for key, (section, row) in t.items():
        if b.get(key, (None, None))[1] == row:
            continue
        if key in have:
            lines[have[key]] = row
            continue
        if section not in lines:
            continue
        s = lines.index(section)
        end = next((k for k in range(s + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
        last = max((k for k in range(s, end) if lines[k].startswith("|")), default=s)
        lines.insert(last + 1, row)
        have = {l.split("|")[1].strip(): i for i, l in enumerate(lines) if l.startswith("| ") and sort_decision_log.ID.match(l.split("|")[1].strip())}
    text = "\n".join(lines)
    bd, td = details(base), details(theirs)
    for key, body in td.items():
        if bd.get(key) == body:
            continue
        od = details(text)
        if key in od:
            text = text.replace(od[key], body, 1)
        elif "\n## Details" in text:
            text = text.rstrip("\n") + "\n\n" + body + "\n"
    return sort_decision_log.sort_text(text)


def details(text):
    """{ID: its whole "### ID" section} under "## Details"."""
    if "\n## Details" not in text:
        return {}
    part = text.split("\n## Details", 1)[1]
    part = part.split("\n## ", 1)[0]
    out = {}
    for m in re.finditer(r"(?ms)^### (\S+)\n.*?(?=^### |\Z)", part):
        out[m.group(1)] = m.group(0).rstrip("\n")
    return out


def settle_handoff(root, branch):
    """Keep main's docs/agent-handoff.md; bring in the branch's inline "### H..." entries, then split them out."""
    git("checkout", "--ours", handoff.HANDOFF, root=root)
    ours = open(os.path.join(root, handoff.HANDOFF), encoding="utf-8").read()
    theirs = git("show", f"{branch}:{handoff.HANDOFF}", root=root).stdout
    stop = theirs.find("\n## Archived")
    inline = re.findall(r"(?ms)^### H\d+ .*?(?=^### |^## )", theirs[:stop if stop > 0 else len(theirs)])
    if inline:
        ours = ours.replace("\n## Archived", "\n" + "\n".join(x.rstrip() + "\n" for x in inline) + "\n## Archived", 1)
        open(os.path.join(root, handoff.HANDOFF), "w", encoding="utf-8").write(ours)
    handoff.split(root)


def answered_by(root, branch, base):
    """docs/handoff/ files the branch changed whose Status is now answered."""
    changed = git("diff", "--name-only", base, branch, "--", handoff.FOLDER, root=root).stdout.split()
    out = []
    for rel in changed:
        p = os.path.join(root, rel)
        if os.path.isfile(p) and re.search(r"\| Status: answered\b", open(p, encoding="utf-8").read()):
            out.append(rel)
    return out


def resolve(root, rel):
    p = os.path.join(root, rel)
    text = open(p, encoding="utf-8").read()
    text = re.sub(r"\| Status: answered\b[^|\n]*", "| Status: resolved ", text, count=1)
    text = text.rstrip("\n") + f"\n\nResolution: merged into main by the integrator, {time.strftime('%Y-%m-%d')}.\n"
    open(p, "w", encoding="utf-8").write(text)
    hid = os.path.basename(rel).split("-")[0]
    handoff.archive(root, hid)
    return hid


def main(argv):
    if not argv or argv[0].startswith("-") or "--as" not in argv:
        print(__doc__)
        return 2
    branch, name = argv[0], argv[argv.index("--as") + 1]
    impact = argv[argv.index("--impact") + 1] if "--impact" in argv else None
    root = git("rev-parse", "--show-toplevel").stdout.strip()
    say = lambda s: print("integrate: " + s)
    if not integrator.touch(integrator.lock_path(root), name, out=say):
        return 1
    if git("branch", "--show-current", root=root).stdout.strip() != "main":
        say("run this in the checkout that has main"); return 1
    if git("status", "--porcelain", "--untracked-files=no", root=root).stdout.strip():
        say("main has uncommitted changes: commit or put them away first"); return 1
    base = git("merge-base", "main", branch, check=True, root=root).stdout.strip()
    subject = git("log", "-1", "--format=%s", branch, root=root).stdout.strip()

    git("merge", "--no-ff", "--no-commit", branch, root=root)
    conflicts = git("diff", "--name-only", "--diff-filter=U", root=root).stdout.split()
    if handoff.HANDOFF in conflicts or os.path.exists(os.path.join(root, handoff.HANDOFF)):
        if handoff.HANDOFF in conflicts:
            settle_handoff(root, branch); say("settled docs/agent-handoff.md (main's, with the branch's entries moved to files)")
        else:
            handoff.split(root)
    if LOG in conflicts:
        ours = git("show", f"HEAD:{LOG}", root=root).stdout
        merged = carry_rows(ours, git("show", f"{base}:{LOG}", root=root).stdout, git("show", f"{branch}:{LOG}", root=root).stdout)
        open(os.path.join(root, LOG), "w", encoding="utf-8").write(merged)
        say("settled docs/decision-log.md (main's, plus the branch's own rows and Details sections)")
    git("add", "-A", root=root)
    left = git("diff", "--name-only", "--diff-filter=U", root=root).stdout.split()
    left = [f for f in left if f not in (handoff.HANDOFF, LOG)]
    if left:
        say(f"conflicts to settle by hand: {', '.join(left)} (the merge is left in progress)"); return 1

    for rel in answered_by(root, branch, base):
        say(f"resolved and archived {resolve(root, rel)}")
    for i, a in enumerate(argv):          # --status T33=Done: the integrator's verdict for the item the branch did
        if a == "--status" and i + 1 < len(argv) and "=" in argv[i + 1]:
            tid, status = argv[i + 1].split("=", 1)
            p = os.path.join(root, LOG)
            lines = open(p, encoding="utf-8").read().split("\n")
            for k, l in enumerate(lines):
                if l.startswith(f"| {tid} "):
                    c = l.split(" | "); c[2] = status; lines[k] = " | ".join(c)
                    say(f"{tid}: {status}")
            open(p, "w", encoding="utf-8").write("\n".join(lines))
    number_ids.apply(root, out=lambda s: say(s) if s != "no placeholders" else None)
    git("add", "-A", root=root)
    problems = sort_decision_log.details_problems(open(os.path.join(root, LOG), encoding="utf-8").read()) + \
        sort_decision_log.status_problems(open(os.path.join(root, LOG), encoding="utf-8").read())
    text = open(os.path.join(root, handoff.HANDOFF), encoding="utf-8").read()
    if handoff.with_list(text, root) != text:
        problems.append("the handoff's open list doesn't match docs/handoff/")
    if problems:
        say("fix these, then commit by hand:\n  " + "\n  ".join(problems)); return 1

    if "--no-gate" not in argv:
        gate = subprocess.run([os.path.join(HERE, "gate.sh")], cwd=root, capture_output=True, text=True)
        verdict = (gate.stdout.strip().split("\n") or [""])[-1]
        say(verdict)
        if gate.returncode != 0:
            print(gate.stdout[-2000:]); say("the merge is left uncommitted"); return 1
    msg = f"Merge {branch}: {subject}\n\nMerged by tools/integrate.py ({name})."
    if impact:
        msg += f"\n\nArchitecture-Impact: none - {impact}"
    msg += "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
    r = subprocess.run(["git", "-c", "core.hooksPath=.githooks", "commit", "-q", "-F", "-"], input=msg, cwd=root,
                       capture_output=True, text=True)
    if r.returncode != 0:
        say("commit refused:\n" + (r.stdout + r.stderr).strip() + "\n(the merge is left staged; add --impact if the hook asks)"); return 1
    say("committed " + git("log", "--oneline", "-1", root=root).stdout.strip())
    if "--push" in argv:
        p = git("push", "-q", "origin", "main", root=root)
        say("pushed main" if p.returncode == 0 else "push failed: " + p.stderr.strip())
        if p.returncode:
            return 1
    say("left for you: the Work list result and BOARD.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
