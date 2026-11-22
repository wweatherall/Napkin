#!/usr/bin/env python3
"""Merge one agent branch into main (P20): the integrator's steps, in one command.

  python3 tools/integrate.py <branch> --as <name> [--status T33=Done ...] [--subject I-new-N=Snapping ...]
                             [--push] [--no-gate] [--impact "<reason>"]

Run in the main checkout, on main, clean, holding the integrator lock (tools/integrator.py). In order:
 1. git merge --no-ff --no-commit <branch>
 2. conflicts it knows how to settle: docs/agent-handoff.md (main's text kept; an entry the branch answered inline,
    from before T77, moves into its docs/handoff/ file), the decision log's two files (main's text, plus every row
    and Details section the branch added or changed since it left main; a branch written before P23's layout is
    always settled this way, each new decision placed under its subject: from its Area when that names one
    subject, else from --subject, and when neither does it stops before merging and asks); any other conflict
    stops here, the merge left as it is
 3. the handoff entries the branch answered: Status resolved, a Resolution line, moved to the archive;
    --status sets a Work list item's status (Done moves it to docs/decision-archive.md)
 4. tools/number_ids.py (placeholders get numbers), then the decision-log and handoff checks
 5. tools/gate.sh (the quick and full tests, tests/known_failures.txt); a failing gate stops here, uncommitted
 6. commit ("Merge <branch>: <its subject>"; --impact adds an Architecture-Impact line), then --push pushes main
 7. the job queue (P24, tools/job.py): the job is marked merged, its worktree removed and its branch deleted
BOARD.md's job table is generated (tools/job.py board): a conflict in it is settled by rebuilding it.
What it leaves to the integrator: reviewing the branch first, and the Work list result."""
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import handoff
import integrator
import job
import number_ids
import sort_decision_log

LOG = sort_decision_log.LIVE
ARCHIVE = sort_decision_log.ARCHIVE
# an old-layout row's Area -> its subject, where the Area names exactly one ("Interaction" doesn't: ask)
AREA_SUBJECT = {"Architecture": "Architecture", "Process": "Process", "Wave": "Feedback", "Materials": "Materials",
                "Drawings": "Output", "Saving": "Files, saving and undo", "Undo": "Files, saving and undo",
                "Measurements": "Measurements", "Drawing": "Drawing tools", "Product": "Product"}


def git(*args, check=False, root=None):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r


def has_markers(path):
    """A file still holding git conflict markers."""
    try:
        text = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        return False
    return bool(re.search(r"^(<<<<<<< |>>>>>>> )", text, re.M))


VERSION_FILES = {"worker/serve.py": r"^PROTOCOL_VERSION = (\d+)$", "viewport/main.gd": r"^const PROTOCOL_VERSION := (\d+)$"}
PROTOCOL_DOC = "docs/protocol.md"


def protocol_version(text, pattern):
    m = re.search(pattern, text or "", re.M)
    return int(m.group(1)) if m else None


def renumber_protocol(root, base, branch):
    """A35: if the branch bumped the protocol version and main bumped it too since the branch left, the branch's
    bump goes on top of main's (main 3 + a branch's 2 -> 3 becomes 4), in both constants and the protocol doc.
    Returns (old, new) when it renumbered, else None."""
    rel, pat = "worker/serve.py", VERSION_FILES["worker/serve.py"]
    b = protocol_version(git("show", f"{base}:{rel}", root=root).stdout, pat)
    t = protocol_version(git("show", f"{branch}:{rel}", root=root).stdout, pat)
    m = protocol_version(git("show", f"HEAD:{rel}", root=root).stdout, pat)
    if None in (b, t, m) or t == b or m == b:
        return None
    new = m + (t - b)
    for f, p in VERSION_FILES.items():
        path = os.path.join(root, f)
        if os.path.isfile(path):
            text = open(path, encoding="utf-8").read()
            text = re.sub(p, lambda x: x.group(0).replace(x.group(1), str(new)), text, flags=re.M)
            open(path, "w", encoding="utf-8").write(text)
    doc = os.path.join(root, PROTOCOL_DOC)
    if os.path.isfile(doc):
        text = open(doc, encoding="utf-8").read()
        text = re.sub(r"version is \*\*%d\*\*" % t, f"version is **{new}**", text)
        text = re.sub(r"currently %d\b" % t, f"currently {new}", text)
        open(doc, "w", encoding="utf-8").write(text)
    return (t, new)


IGNORED = ("docs/handoff/", "docs/agent-handoff.md", "docs/handoff-archive.md", LOG, ARCHIVE)


def outside_touches(root, branch, base):
    """Files the branch changed that its job's Touches list doesn't name (P11). The job is the docs/handoff/ entry
    the branch changed; coordination files (the handoff, the log) never count."""
    changed = git("diff", "--name-only", base, branch, root=root).stdout.split()
    jobs = [f for f in changed if f.startswith(handoff.FOLDER + "/")]
    listed = set()
    for rel in jobs:
        text = git("show", f"{branch}:{rel}", root=root).stdout
        listed |= handoff.touches(text)
    if not jobs:
        return None
    return [f for f in changed if not f.startswith(IGNORED) and not f.endswith(".uid")
            and not any(handoff._covers(t, f) or t == f for t in listed)]


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


def old_layout(text):
    """A log written before P23: no Subjects index."""
    return "## Subjects" not in text.split("\n")


def all_rows(live, archive):
    """{ID: (file 0 live / 1 archive, section, group, row)} across both files."""
    out = {}
    for n, text in enumerate((live, archive)):
        lines = text.split("\n")
        for h, hc, rs, sec, g in sort_decision_log.tables(lines):
            for r in rs:
                k = sort_decision_log.row_id(lines[r])
                if k:
                    out[k] = (n, sec, g, lines[r])
    return out


def tunable_rows(text):
    """{setting: row} in ## Tunables (not ID-keyed, so carried by name)."""
    lines = text.split("\n")
    return {sort_decision_log.cells(lines[r])[0]: lines[r] for h, hc, rs, sec, g in sort_decision_log.tables(lines)
            if sec == "## Tunables" for r in rs}


def settle_log(ours, base, theirs, subjects=None):
    """Main's two log files plus the rows, Tunables and Details the branch added or changed since base.
    ours, base, theirs: (live, archive) texts (archive "" when that side has none). Returns
    ((live, archive), asks): asks lists (ID, Area, decision) for new old-layout decisions with no clear subject,
    and then nothing should be written."""
    subjects = subjects or {}
    live, arch = ours
    old = old_layout(theirs[0])
    b, t, o = all_rows(*base), all_rows(*theirs), all_rows(*ours)
    S = sort_decision_log
    plan, asks = [], []
    for key, (n, sec, g, row) in t.items():
        if b.get(key, (None,) * 4)[3] == row:
            continue
        c = S.cells(row)
        mine = o.get(key)
        if not old:
            plan.append((key, n, sec, g, row))
        elif sec == "## Decisions":
            if mine and mine[1] == "## Decisions" and mine[0] == 0:
                subject, principles = mine[2], S.cells(mine[3])[5]
            else:
                subject, principles = subjects.get(key) or AREA_SUBJECT.get(c[5] if len(c) > 5 else ""), S.NONE
                if not subject:
                    asks.append((key, c[5] if len(c) > 5 else "", c[1]))
                    continue
            c[5] = principles
            plan.append((key, 0, sec, subject, S.make_row(c)))
        elif sec == "## Superseded decisions":
            if mine and mine[0] == 0 and mine[2]:
                row = S.archived_row(S.make_row(c[:5] + [S.cells(mine[3])[5]] + c[6:]), mine[2])
            plan.append((key, 1, sec, None, row))
        else:
            plan.append((key, 0, sec, None, row))
    if asks:
        return None, asks
    texts = [live, arch]
    for key, n, sec, g, row in plan:
        for k in (0, 1):
            texts[k], _ = S.remove_row(texts[k], key)
        try:
            texts[n] = S.insert_row(texts[n], row, sec, g)
        except ValueError:
            asks.append((key, g or sec, S.cells(row)[1]))
    if asks:
        return None, asks
    bt, tt = tunable_rows(base[0]), tunable_rows(theirs[0])
    for name, row in tt.items():
        if bt.get(name) == row:
            continue
        have = tunable_rows(texts[0])
        texts[0] = texts[0].replace(have[name], row, 1) if name in have else S.insert_row(texts[0], row, "## Tunables")
    bd = {**S.details_sections(base[0]), **S.details_sections(base[1])}
    td = {**S.details_sections(theirs[0]), **S.details_sections(theirs[1])}
    for key, body in td.items():
        if bd.get(key) == body:
            continue
        for k in (0, 1):
            texts[k], _ = S.take_details(texts[k], key)
        texts[0] = S.add_details(texts[0], body)
    return S.tidy(*texts), []


def subject_names(live):
    """The Subjects index's names, in order."""
    lines = live.split("\n")
    return [sort_decision_log.cells(lines[r])[0] for h, hc, rs, sec, g in sort_decision_log.tables(lines)
            if sec == "## Subjects" for r in rs]


def set_status(root, tid, status):
    """The integrator's verdict for a Work list item; a Done item then moves to the archive (P23)."""
    p, a = os.path.join(root, LOG), os.path.join(root, ARCHIVE)
    live = open(p, encoding="utf-8").read()
    arch = open(a, encoding="utf-8").read() if os.path.isfile(a) else None
    texts, found = [live, arch], None
    for n, text in enumerate(texts):
        if text is None:
            continue
        lines = text.split("\n")
        i = sort_decision_log.find_row(lines, tid)
        if i is not None:
            c = sort_decision_log.cells(lines[i]); c[2] = status
            lines[i] = sort_decision_log.make_row(c); texts[n] = "\n".join(lines); found = n
    if found is None:
        return f"{tid}: not in the decision log"
    if arch is None:
        open(p, "w", encoding="utf-8").write(texts[0])
        return f"{tid}: {status}"
    live2, arch2 = sort_decision_log.tidy(texts[0], texts[1])
    open(p, "w", encoding="utf-8").write(live2)
    open(a, "w", encoding="utf-8").write(arch2)
    moved = found == 0 and sort_decision_log.find_row(arch2.split("\n"), tid) is not None
    return f"{tid}: {status}" + (f" (moved to {ARCHIVE})" if moved else "")


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
    subjects = dict(argv[i + 1].split("=", 1) for i, a in enumerate(argv) if a == "--subject" and i + 1 < len(argv))
    show = lambda ref, rel: git("show", f"{ref}:{rel}", root=root).stdout
    log_changed = bool(git("diff", "--name-only", base, branch, "--", LOG, ARCHIVE, root=root).stdout.strip())
    settled = None
    if log_changed and not old_layout(show("HEAD", LOG)):
        settled, asks = settle_log((show("HEAD", LOG), show("HEAD", ARCHIVE)), (show(base, LOG), show(base, ARCHIVE)),
                                   (show(branch, LOG), show(branch, ARCHIVE)), subjects)
        if asks:
            for key, area, text in asks:
                say(f"which subject is {key} ({area}): {text[:90]}")
            say("run again with --subject <ID>=<subject> for each (nothing merged yet); subjects: "
                + ", ".join(subject_names(show("HEAD", LOG))))
            return 1

    git("merge", "--no-ff", "--no-commit", branch, root=root)
    conflicts = git("diff", "--name-only", "--diff-filter=U", root=root).stdout.split()
    if handoff.HANDOFF in conflicts or os.path.exists(os.path.join(root, handoff.HANDOFF)):
        if handoff.HANDOFF in conflicts:
            settle_handoff(root, branch); say("settled docs/agent-handoff.md (main's, with the branch's entries moved to files)")
        else:
            handoff.split(root)
    if settled and (LOG in conflicts or ARCHIVE in conflicts or old_layout(show(branch, LOG))):
        open(os.path.join(root, LOG), "w", encoding="utf-8").write(settled[0])
        open(os.path.join(root, ARCHIVE), "w", encoding="utf-8").write(settled[1])
        say("settled the decision log (main's two files, plus the branch's own rows and Details sections"
            + (", placed by subject from its pre-P23 layout)" if old_layout(show(branch, LOG)) else ")"))
    elif LOG in conflicts:
        ours = git("show", f"HEAD:{LOG}", root=root).stdout
        merged = carry_rows(ours, git("show", f"{base}:{LOG}", root=root).stdout, git("show", f"{branch}:{LOG}", root=root).stdout)
        open(os.path.join(root, LOG), "w", encoding="utf-8").write(merged)
        say("settled docs/decision-log.md (main's, plus the branch's own rows and Details sections)")
    if job.BOARD in conflicts:
        git("checkout", "--ours", job.BOARD, root=root)
        say("settled BOARD.md (main's; its job table is rebuilt below)")
    # Before staging anything: staging clears git's "unmerged" mark even with conflict markers still in a file.
    left = [f for f in conflicts if f not in (handoff.HANDOFF, LOG, ARCHIVE, job.BOARD)]
    if left:
        say(f"conflicts to settle by hand: {', '.join(left)} (the merge is left in progress)"); return 1
    marked = [f for f in conflicts if has_markers(os.path.join(root, f))]
    if marked:
        say(f"conflict markers still in: {', '.join(marked)} (the merge is left in progress)"); return 1
    git("add", "-A", root=root)

    bumped = renumber_protocol(root, base, branch)
    if bumped:
        say(f"protocol version: the branch's {bumped[0]} is {bumped[1]} on main (main moved on since it left; A35)")
    extra = outside_touches(root, branch, base)
    if extra:
        say("OUTSIDE ITS TOUCHES LIST: " + ", ".join(extra) + " (check the job's response says why)")
    for rel in answered_by(root, branch, base):
        say(f"resolved and archived {resolve(root, rel)}")
    for i, a in enumerate(argv):          # --status T33=Done: the integrator's verdict for the item the branch did
        if a == "--status" and i + 1 < len(argv) and "=" in argv[i + 1]:
            tid, status = argv[i + 1].split("=", 1)
            say(set_status(root, tid, status))
    number_ids.apply(root, out=lambda s: say(s) if s != "no placeholders" else None)
    bpath = os.path.join(root, job.BOARD)
    if os.path.isfile(bpath) and job.START in open(bpath, encoding="utf-8").read():
        job.board(root, out=say)
    git("add", "-A", root=root)
    arch = os.path.join(root, ARCHIVE)
    problems = sort_decision_log.check_files(open(os.path.join(root, LOG), encoding="utf-8").read(),
                                             open(arch, encoding="utf-8").read() if os.path.isfile(arch) else None)
    text = open(os.path.join(root, handoff.HANDOFF), encoding="utf-8").read()
    if handoff.with_list(text, root) != text:
        problems.append("the handoff's open list doesn't match docs/handoff/")
    if problems:
        say("fix these, then commit by hand:\n  " + "\n  ".join(problems)); return 1

    if "--no-gate" not in argv:
        gate = subprocess.run([os.path.join(root, "tools", "gate.sh") if os.path.exists(os.path.join(root, "tools", "gate.sh")) else os.path.join(HERE, "gate.sh")], cwd=root, capture_output=True, text=True)
        verdict = (gate.stdout.strip().split("\n") or [""])[-1]
        say(verdict)
        if gate.returncode != 0:
            print(gate.stdout[-2000:]); say("the merge is left uncommitted"); return 1
    msg = f"Merge {branch}: {subject}\n\nMerged by tools/integrate.py ({name})."
    if bumped:
        msg += f" Protocol version {bumped[0]} renumbered to {bumped[1]}."
    if extra:
        msg += "\nOutside its Touches list: " + ", ".join(extra) + "."
    if impact:
        msg += f"\n\nArchitecture-Impact: none - {impact}"
    msg += "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
    r = subprocess.run(["git", "-c", "core.hooksPath=.githooks", "commit", "-q", "-F", "-"], input=msg, cwd=root,
                       capture_output=True, text=True)
    if r.returncode != 0:
        say("commit refused:\n" + (r.stdout + r.stderr).strip() + "\n(the merge is left staged; add --impact if the hook asks)"); return 1
    say("committed " + git("log", "--oneline", "-1", root=root).stdout.strip())
    job.merged(root, branch, out=say)
    if "--push" in argv:
        p = git("push", "-q", "origin", "main", root=root)
        say("pushed main" if p.returncode == 0 else "push failed: " + p.stderr.strip())
        if p.returncode:
            return 1
    say("left for you: the Work list result")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
