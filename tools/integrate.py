#!/usr/bin/env python3
"""Merge one agent branch into main (P20): the integrator's steps, in one command.

  python3 tools/integrate.py <branch> --as <name> [--status T33=Done ...] [--subject I-new-N=Snapping ...]
                             [--push [--yes]] [--no-gate] [--impact "<reason>"] [--job H0NN]
  python3 tools/integrate.py --continue --as <name> [--push [--yes]] [--impact "<reason>"]
                             after a merge stopped for the map (P28) or a refused commit

Run in the main checkout, on main, clean, holding the integrator lock (tools/integrator.py). In order:
 1. git merge --no-ff --no-commit <branch>
 2. conflicts it knows how to settle: docs/agent-handoff.md (main's text kept; an entry the branch answered inline,
    from before T77, moves into its docs/handoff/ file), the decision log's two files (main's text, plus every row
    and Details section the branch added or changed since it left main; a branch written before P23's layout is
    always settled this way, each new decision placed under its subject: from its Area when that names one
    subject, else from --subject, and when neither does it stops before merging and asks); any other conflict
    stops here, the merge left as it is
 3. tools/number_ids.py (placeholders get numbers, so an H-new-N entry is H0NN from here on: H060)
 4. the handoff entries the branch answered (each known by the ID its ### heading gives): Status resolved, a
    Resolution line, moved to the archive; --status sets a Work list item's status (Done moves it to
    docs/decision-archive.md); then number_ids.py again and the decision-log and handoff checks
 5. tools/gate.sh (the quick and full tests, tests/known_failures.txt); a failing gate stops here, uncommitted
 6. commit ("Merge <branch>: <its subject>"; --impact adds an Architecture-Impact line), then --push pushes main
 7. the job queue (P24, tools/job.py): the job is marked merged, its worktree removed and its branch deleted;
    --job H0NN names the job a scratch branch delivers (main merged into the job's branch first, then that
    scratch branch integrated), so that job, its worktree and its own branch go too
 8. the Work list result (T91): each answered entry's newest "Result: <commit>; <tests>; <what changed>" line
    (docs/agent-handoff.md's rules) is appended to its item's row as "Result (<commit>, merged <merge>): ...", in
    its own commit; the item is the --status T<n> (or the one the entry's heading names). The commit is shown and,
    with --push, it stops before the push until --yes is given. No Result line: left for the integrator, as before
9. follow-ups (P26, T97): each answered entry's "Follow-up: <what>" lines are appended to docs/follow-ups.md as
   "- <H0NN> (<date>): <what>" in the merge commit (one already there isn't added twice); its "For the integrator:
   <what>" lines are printed after the merge, under "for you now:"
10. the map (P28, T100): workers don't edit ARCHITECTURE.md or docs/protocol.md; an answered entry's
   "Architecture: <what>" lines say what the change does to them. With any (and no --impact), it stops before
   step 6, the merge staged, and prints them under "for you now:" marked "map:": write them in (checked against
   the code), then `integrate.py --continue --as <name> [--push [--yes]]` does steps 6-9. A refused merge commit
   (the architecture hook) is left the same way: stage the map or give --impact, then --continue
BOARD.md's job table is generated (tools/job.py board): a conflict in it is settled by rebuilding it. In a BOARD.md
conflict main's Order line, "## Jobs" section (the table) and "## Notes" (the integrator's) are kept; any other
section the branch alone changed is the branch's; both changing one stops the merge (H073).
What it leaves to the integrator: reviewing the branch first, and a Result line a response didn't give."""
import json
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


BOARD_OURS = ("Jobs", "Notes")       # the integrator's sections of BOARD.md (with its Order line): main's always


def board_sections(text):
    """BOARD.md as [(heading, body)]: "" for the text before the first "## " heading (its Order line taken out,
    the integrator's), then each section with its heading line. Returns (sections, Order line)."""
    parts, order = [["", []]], None
    for line in text.split("\n"):
        if line.startswith("## "):
            parts.append([line[3:].strip(), []])
        if line.startswith("Order:") and len(parts) == 1:
            order = line
            parts[0][1].append("\0order")
        else:
            parts[-1][1].append(line)
    return [(h, "\n".join(b)) for h, b in parts], order


def settle_board(ours, base, theirs):
    """A BOARD.md conflict settled (H073): main's Order line, Jobs and Notes; a section only the branch changed is
    the branch's (added or removed too); one both changed is reported. Returns (text, [section names both changed])."""
    (o, order), (b, _), (t, _) = board_sections(ours), board_sections(base), board_sections(theirs)
    od, bd, td = dict(o), dict(b), dict(t)
    out, clashes = [], []
    for h, mine in o:
        if h in BOARD_OURS or td.get(h) == bd.get(h) or td.get(h) == mine:
            pick = mine
        elif mine == bd.get(h):
            pick = td.get(h)                # None: the branch removed it
        else:
            clashes.append(h or "the top (before the first heading)"); pick = mine
        if pick is not None:
            out.append((h, pick))
    for i, (h, theirs_body) in enumerate(t):    # a section the branch added goes after the one it follows there
        if h not in od and h not in bd:
            after = next((j for j in range(i - 1, -1, -1) if t[j][0] in [x for x, _ in out]), None)
            at = [x for x, _ in out].index(t[after][0]) + 1 if after is not None else len(out)
            out.insert(at, (h, theirs_body))
    text = "\n".join(body for _, body in out)
    return text.replace("\0order", order or ""), clashes


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
    hid = entry_id(text, rel)
    handoff.archive(root, hid)
    return hid


def entry_id(text, rel):
    """An entry's ID from its ### heading ("### H037 — ..."), else from its file name (before the first dash)."""
    head = re.search(r"(?m)^### ([A-Z]+\d+[a-z]*|[A-Z]+-new-\d+[a-z]*)\b", text or "")
    return head.group(1) if head else os.path.basename(rel).split("-")[0]


def numbered(text, numbers):
    """text with each placeholder that number_ids.apply() numbered ({"H-new-N": "H069"}) given its number."""
    return number_ids.PLACEHOLDER.sub(
        lambda m: numbers.get(f"{m.group(1)}-new-{m.group(2)}", m.group(1) + "-new-" + m.group(2)) + m.group(3), text)


def job_branch(root, jid):
    """The branch the job queue gave job jid, or None."""
    return (job.read_state(job.state_path(root))["jobs"].get(jid) or {}).get("branch")


RESULT = re.compile(r"(?m)^[-*]?\s*Result:\s*([0-9a-f]{7,40})\s*;\s*(.+?)\s*$")


def result_line(text):
    """The newest "Result: <commit>; <tests>; <what changed>" line in a handoff entry: (commit, rest) or None."""
    found = RESULT.findall(text or "")
    return (found[-1][0][:7], found[-1][1]) if found else None


FOLLOW_UP = re.compile(r"(?m)^[-*]?\s*Follow-up:\s*(.+?)\s*$")
FOR_INTEGRATOR = re.compile(r"(?m)^[-*]?\s*For the integrator:\s*(.+?)\s*$")
ARCHITECTURE_LINE = re.compile(r"(?m)^[-*]?\s*Architecture:\s*(.+?)\s*$")
FOLLOW_UPS = "docs/follow-ups.md"
FOLLOW_UPS_HEADER = """# Follow-ups

Leftovers from merged jobs (P26): a worker writes each one as its own `Follow-up: <what>` line in its handoff
response, and tools/integrate.py copies it here at merge. The integrator removes a line in the commit that does it,
or that turns it into a Work list item. `python3 tools/startup.py` lists the open ones.

## Open

"""
FOLLOW_UP_ROW = re.compile(r"^- (\S+) \([^)]*\): (.+?)\s*$")


def follow_ups(text):
    """A response's "Follow-up: <what>" lines (a leading "- " allowed)."""
    return FOLLOW_UP.findall(text or "")


def for_integrator(text):
    """A response's "For the integrator: <what>" lines."""
    return FOR_INTEGRATOR.findall(text or "")


def architecture(text):
    """A response's "Architecture: <what>" lines (P28): what the change does to the map or the protocol."""
    return ARCHITECTURE_LINE.findall(text or "")


def open_follow_ups(text):
    """The open lines of docs/follow-ups.md ("- H0NN (<date>): <what>")."""
    return [l.rstrip() for l in (text or "").split("\n") if FOLLOW_UP_ROW.match(l)]


def add_follow_ups(root, items, date=None):
    """Append each (hid, what) to docs/follow-ups.md, made with its header if missing; a line already there (same
    entry and text, any date) isn't added twice. Returns the lines added."""
    p = os.path.join(root, FOLLOW_UPS)
    text = open(p, encoding="utf-8").read() if os.path.isfile(p) else FOLLOW_UPS_HEADER + "(none)\n"
    have = {(m.group(1), m.group(2)) for m in map(FOLLOW_UP_ROW.match, text.split("\n")) if m}
    date = date or time.strftime("%Y-%m-%d")
    added = []
    for hid, what in items:
        what = " ".join(what.split())
        if (hid, what) not in have:
            have.add((hid, what)); added.append(f"- {hid} ({date}): {what}")
    if not added:
        return []
    text = re.sub(r"(?m)^\(none\)\n?", "", text).rstrip("\n") + "\n"
    if not open_follow_ups(text) and not text.endswith("\n\n"):
        text += "\n"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(text + "\n".join(added) + "\n")
    return added


def entry_item(text, statuses):
    """The Work list item an entry's result belongs to: the --status item its heading names, the only --status
    item, or the T<n> its heading names."""
    head = re.search(r"(?m)^### .*$", text or "")
    named = re.findall(r"\bT\d+\b", head.group(0)) if head else []
    hit = [t for t in statuses if t in named]
    if hit:
        return hit[0]
    if len(statuses) == 1:
        return statuses[0]
    return named[0] if named else None


def record_result(root, tid, commit, rest, merge):
    """Append "Result (<commit>, merged <merge>): <rest>" to tid's row, in the live log or the archive.
    Returns (the file changed or None, what happened)."""
    rest = rest.replace("|", "/").rstrip()
    rest = rest if rest.endswith(".") else rest + "."
    for rel in (LOG, ARCHIVE):
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            continue
        lines = open(p, encoding="utf-8").read().split("\n")
        i = sort_decision_log.find_row(lines, tid)
        if i is None:
            continue
        c = sort_decision_log.cells(lines[i])
        if f"Result ({commit}" in c[-1]:
            return None, f"{tid}: result {commit} is already in its row"
        add = f"Result ({commit}, merged {merge}): {rest}"
        c[-1] = f"{c[-1]} {add}" if c[-1] else add
        lines[i] = sort_decision_log.make_row(c)
        open(p, "w", encoding="utf-8").write("\n".join(lines))
        return rel, f"{tid}: added {add[:100]}{'...' if len(add) > 100 else ''}"
    return None, f"{tid}: not in the decision log"


def main(argv):
    if argv and argv[0] == "--continue":
        return resume(argv[1:])
    if not argv or argv[0].startswith("-") or "--as" not in argv:
        print(__doc__)
        return 2
    branch, name = argv[0], argv[argv.index("--as") + 1]
    jid = argv[argv.index("--job") + 1] if "--job" in argv and argv.index("--job") + 1 < len(argv) else None
    impact = argv[argv.index("--impact") + 1] if "--impact" in argv else None
    root = git("rev-parse", "--show-toplevel").stdout.strip()
    say = lambda s: print("integrate: " + s)
    if not integrator.touch(integrator.lock_path(root), name, out=say):
        return 1
    if git("branch", "--show-current", root=root).stdout.strip() != "main":
        say("run this in the checkout that has main"); return 1
    if git("status", "--porcelain", "--untracked-files=no", root=root).stdout.strip():
        say("main has uncommitted changes: commit or put them away first"); return 1
    delivers = None
    if jid:
        delivers = job_branch(root, jid)
        if not delivers:
            say(f"--job {jid}: no such job in the queue (nothing merged)"); return 1
        if delivers != branch and git("merge-base", "--is-ancestor", delivers, branch, root=root).returncode:
            say(f"--job {jid}: its branch {delivers} isn't all in {branch} (nothing merged)"); return 1
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
        text, clashes = settle_board(git("show", f"HEAD:{job.BOARD}", root=root).stdout,
                                     git("show", f"{base}:{job.BOARD}", root=root).stdout,
                                     git("show", f"{branch}:{job.BOARD}", root=root).stdout)
        if clashes:
            say(f"BOARD.md: main and the branch both changed {', '.join(repr(c) for c in clashes)}: settle it by hand "
                "(the merge is left in progress)"); return 1
        open(os.path.join(root, job.BOARD), "w", encoding="utf-8").write(text)
        say("settled BOARD.md (main's Order line, job table and Notes, the branch's other sections; the table is rebuilt below)")
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
    statuses = [argv[i + 1].split("=", 1) for i, a in enumerate(argv)
                if a == "--status" and i + 1 < len(argv) and "=" in argv[i + 1]]
    results, missing = [], []           # read before resolve() moves the entries to the archive
    later, now = [], []                 # P26: its Follow-up lines (to docs/follow-ups.md) and For the integrator lines
    maps = []                           # P28: its Architecture lines, for the integrator to write into the map
    answered = answered_by(root, branch, base)
    # Number first (H060): an entry named H-new-N-slug.md is H0NN by the time its Result and follow-ups are recorded.
    numbers = number_ids.apply(root, out=lambda s: say(s) if s != "no placeholders" else None)
    answered = [numbered(rel, numbers) for rel in answered]
    statuses = [[numbered(t, numbers), s] for t, s in statuses]
    for rel in answered:
        text = open(os.path.join(root, rel), encoding="utf-8").read()
        hid, got, tid = entry_id(text, rel), result_line(text), entry_item(text, [t for t, _ in statuses])
        later += [(hid, w) for w in follow_ups(text)]
        now += [(hid, w) for w in for_integrator(text)]
        maps += [(hid, w) for w in architecture(text)]
        if got and tid:
            results.append((hid, tid) + got)
        else:
            missing.append(f"{hid} ({'no Result line in its response' if not got else 'no Work list item: give --status T<n>=...'})")
        say(f"resolved and archived {resolve(root, rel)}")
    added = add_follow_ups(root, later)
    if added:
        say(f"follow-ups: {len(added)} added to {FOLLOW_UPS}")
    for tid, status in statuses:        # --status T33=Done: the integrator's verdict for the item the branch did
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
    state = {"branch": branch, "job_branch": delivers if delivers != branch else None, "msg": msg, "results": results, "missing": missing, "now": now, "maps": maps}
    if maps and not impact and not map_staged(root):
        save_state(root, state)         # P28: the map goes in the merge commit, written from the lines below
        say("for you now:")
        for hid, what in now:
            print(f"  {hid}: {what}")
        for hid, what in maps:
            print(f"  {hid}: map: {what}")
        say("the merge is staged, not committed (P28): write these into ARCHITECTURE.md / docs/protocol.md, checked "
            "against the code, `git add` them, then: python3 tools/integrate.py --continue --as " + name
            + (" --push" if "--push" in argv else ""))
        return 0
    return commit_and_finish(root, state, name, impact, argv, say)


STATE = "shopsketch-integrate.json"     # a merge stopped for the map (P28), beside the job queue's state


def state_file(root):
    common = git("rev-parse", "--git-common-dir", root=root).stdout.strip()
    return os.path.join(root, common, STATE) if not os.path.isabs(common) else os.path.join(common, STATE)


MAP_FILES = ("ARCHITECTURE.md", "docs/protocol.md")


def save_state(root, state):
    state.setdefault("tree", git("write-tree", root=root).stdout.strip())   # what the gate passed on
    with open(state_file(root), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)


def map_staged(root):
    """ARCHITECTURE.md or docs/protocol.md changed in the index (the merge in progress)."""
    return bool(git("diff", "--cached", "--name-only", "HEAD", "--", "ARCHITECTURE.md", "docs/protocol.md",
                    root=root).stdout.strip())


def resume(argv):
    """integrate.py --continue --as <name> [--push [--yes]] [--impact "<reason>"]: commit a merge that stopped for
    the map (P28) or a refused commit, then do the rest (the job merged, the Result drafts, the push)."""
    if "--as" not in argv:
        print(__doc__)
        return 2
    name = argv[argv.index("--as") + 1]
    impact = argv[argv.index("--impact") + 1] if "--impact" in argv else None
    root = git("rev-parse", "--show-toplevel").stdout.strip()
    say = lambda s: print("integrate: " + s)
    if not integrator.touch(integrator.lock_path(root), name, out=say):
        return 1
    path = state_file(root)
    if not os.path.isfile(path):
        say("nothing to continue: no merge stopped for the map"); return 1
    if git("rev-parse", "-q", "--verify", "MERGE_HEAD", root=root).returncode:
        say(f"no merge in progress: nothing to commit (remove {path} if that merge was given up)"); return 1
    state = json.load(open(path, encoding="utf-8"))
    git("add", "-u", "--", *MAP_FILES, root=root)     # only the map edits: nothing else joins the merge unseen
    moved = [p for p in git("diff", "--name-only", state.get("tree") or "HEAD", git("write-tree", root=root).stdout.strip(),
                            root=root).stdout.split() if p not in MAP_FILES] if state.get("tree") else []
    if moved:
        say("refused: the merge changed outside the map since the gate passed (" + ", ".join(moved) + "): rerun "
            "the gate (tools/gate.sh) and integrate again, or undo those changes")
        return 1
    if state.get("maps") and not impact and not map_staged(root):
        say("ARCHITECTURE.md / docs/protocol.md aren't changed yet: write the Architecture lines in first (or give "
            "--impact \"<why the map stays as it is>\")")
        for hid, what in state["maps"]:
            print(f"  {hid}: map: {what}")
        return 1
    return commit_and_finish(root, state, name, impact, argv, say)


def commit_and_finish(root, state, name, impact, argv, say):
    """Steps 6-10: the merge commit, then the job merged, the Result drafts, what's for the integrator, the push."""
    branch, msg = state["branch"], state["msg"]
    if impact:
        msg += f"\n\nArchitecture-Impact: none - {impact}"
    msg += "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
    r = subprocess.run(["git", "-c", "core.hooksPath=.githooks", "commit", "-q", "-F", "-"], input=msg, cwd=root,
                       capture_output=True, text=True)
    if r.returncode != 0:
        save_state(root, state)
        say("commit refused:\n" + (r.stdout + r.stderr).strip() + "\n(the merge is left staged: stage the map, or "
            "give --impact, then python3 tools/integrate.py --continue --as " + name + ")"); return 1
    if os.path.isfile(state_file(root)):
        os.remove(state_file(root))
    say("committed " + git("log", "--oneline", "-1", root=root).stdout.strip())
    job.merged(root, branch, out=say)
    if state.get("job_branch"):         # --job: the scratch branch delivered this job's branch (all of it is in main)
        job.merged(root, state["job_branch"], out=say)
    drafted = draft_results(root, [tuple(x) for x in state["results"]], name, say)
    if state["now"]:
        say("for you now:")
        for hid, what in state["now"]:
            print(f"  {hid}: {what}")
    if state["missing"]:
        say("left for you: the Work list result of " + ", ".join(state["missing"]))
    if "--push" in argv:
        if drafted and "--yes" not in argv:
            say("look the result over (above); fix it with `git commit --amend` if needed, then push: "
                "git push origin main (or give --push --yes next time to push without stopping)")
            return 0
        p = git("push", "-q", "origin", "main", root=root)
        say("pushed main" if p.returncode == 0 else "push failed: " + p.stderr.strip())
        if p.returncode:
            return 1
    return 0


def draft_results(root, results, name, say):
    """Step 8: append each Result line to its Work list row and commit it on its own; show the commit. True if made."""
    if not results:
        return False
    merge = git("rev-parse", "--short", "HEAD", root=root).stdout.strip()
    changed, items = set(), []
    for hid, tid, commit, rest in results:
        rel, what = record_result(root, tid, commit, rest, merge)
        say(what)
        if rel:
            changed.add(rel); items.append(f"{tid} ({hid})")
    if not changed:
        return False
    git("add", *sorted(changed), root=root)
    msg = (f"{', '.join(items)}: Work list result, merged {merge}\n\nDrafted by tools/integrate.py ({name}) from the "
           "handoff response's Result line.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    r = subprocess.run(["git", "-c", "core.hooksPath=.githooks", "commit", "-q", "-F", "-"], input=msg, cwd=root,
                       capture_output=True, text=True)
    if r.returncode != 0:
        say("the result commit was refused (left staged):\n" + (r.stdout + r.stderr).strip()); return True
    say("committed " + git("log", "--oneline", "-1", root=root).stdout.strip())
    print(git("show", "--format=", "--word-diff=plain", "HEAD", root=root).stdout.rstrip())
    return True


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
