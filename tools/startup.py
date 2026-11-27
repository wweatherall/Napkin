#!/usr/bin/env python3
"""Session startup report (T56): run this instead of reading the big documents.

  python3 tools/startup.py                     full report plus a --role tip
  python3 tools/startup.py --role integrator   full report plus open integrator notes and checklist
  python3 tools/startup.py --role worker       lean worker report (checkout, recent main, board, queue, checklist)
  python3 tools/startup.py [--role R] T54 ...  also each Work list row asked for, with the rows its Covers column cites
  python3 tools/startup.py --space <name> ...  also the last ten lines of that member's Log and Journal (T134;
                                               the integrator's, opus-integrator, are shown without it)

Read-only. Works from any worktree: the board and the decision log are read from main (`git show main:<path>`),
since a worktree's copy can be stale."""
import json
import re
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sort_decision_log as s

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
        return name[7:].startswith(("claude/", "codex/", "gemini/"))
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


BRANCH = re.compile(r"(?<![\w/.-])((?:claude|codex|gemini)/[\w.-]*[\w])")


def gone_branches(entries, names):
    """[(handoff file, branch)] for each claude/* or codex/* branch an open handoff names that no longer exists (local
    or origin/): a note that still points at it is out of date."""
    have = set(names) | {n.removeprefix("origin/") for n in names}
    return [(f, b) for f, text in sorted(entries.items()) for b in sorted(set(BRANCH.findall(text))) if b not in have]


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


def queued_jobs(board):
    """Board's Jobs rows whose Status is Queued -> [(job, for, item, waits_for)]."""
    out = []
    for line in section(board, "Jobs"):
        if not line.startswith("|"):
            continue
        c = cells(line)
        if len(c) < 4 or c[2] != "Queued":
            continue
        out.append((c[0], c[1], c[3], c[5] if len(c) > 5 else ""))
    return out


def notes(board, n=3):
    return [l for l in section(board, "Notes") if l.strip()][:n]


def find_row(log, ident):
    """The first table row in the log whose first cell is ident, or None."""
    for line in log.splitlines():
        if line.startswith("|") and cells(line)[0] == ident:
            return line
    return None


def work_list_ids(log, heading="Work list"):
    return {cells(l)[0] for l in section(log, heading) if l.startswith("| ") and not l.startswith("| #")}


def cited_ids(row):
    """IDs in a Work list row's Covers column (4th cell)."""
    c = cells(row)
    return ID_RE.findall(c[3]) if len(c) > 3 else []


def shorten(row, n=SHORT):
    row = row.strip()
    return row if len(row) <= n else row[: n - 3] + "..."


def details_note(row):
    return "  (has a ### section under Details)" if "(Details below.)" in row else ""


ARCHIVE_NOTE = "  [in the archive]"


def find_either(log, archive, ident):
    """(row, note) from the live log, else the archive (P23), else (None, "")."""
    row = find_row(log, ident)
    if row is not None:
        return row, ""
    row = find_row(archive, ident)
    return (row, ARCHIVE_NOTE) if row is not None else (None, "")


def _ruling_line(raw, ident):
    """Format a ruling file into a compact summary line (no longer than a table row)."""
    e = s.parse_entry(raw, ident=ident)
    status = e["meta"].get("Status", "")
    note = ARCHIVE_NOTE if status == "Superseded" else ""
    det = "  (has ## Details)" if e["details"] else ""
    parts = [f"Status: {status}"]
    if e["meta"].get("Subject"):
        parts.append(f"Subject: {e['meta']['Subject']}")
    if e["meta"].get("Principles") and e["meta"]["Principles"] != "—":
        parts.append(f"Principles: {e['meta']['Principles']}")
    summary = shorten(f"{e['title']} [{'; '.join(parts)}]", SHORT) + det
    return note, summary


def _work_line(raw, ident):
    """Format a Work list file into (archive_note, compact summary, cited_ids)."""
    e = s.parse_entry(raw, ident=ident)
    status = e["meta"].get("Status", "")
    note = ARCHIVE_NOTE if status == "Done" else ""
    det = "  (has ## Details)" if e["details"] else ""
    covers = e["meta"].get("Covers", "")
    parts = [f"Status: {status}"]
    if covers and covers != s.NONE:
        parts.append(f"Covers: {covers}")
    if e["result"]:
        parts.append(f"Result: {e['result']}")
    summary = shorten(f"{e['title']} [{'; '.join(parts)}]", SHORT) + det
    cids = ID_RE.findall(covers) if covers and covers != s.NONE else []
    return note, summary, cids


def _question_line(raw, ident):
    """Format a question file into (archive_note, compact summary)."""
    e = s.parse_entry(raw, ident=ident)
    status = e["meta"].get("Status", "")
    note = ARCHIVE_NOTE if status == "Decided" else ""
    det = "  (has ## Details)" if e["details"] else ""
    parts = [f"Status: {status}"]
    if e["notes"]:
        parts.append(f"Notes: {e['notes']}")
    summary = shorten(f"{e['title']} [{'; '.join(parts)}]", SHORT) + det
    return note, summary


def _lookup_entry_line(cid, log, archive, read_ruling=None, read_work=None, read_question=None):
    """Compact one-line summary for a cited ID from entry files or log/archive tables."""
    if read_ruling and s.is_ruling_id(cid):
        raw = read_ruling(cid)
        if raw:
            cnote, csum = _ruling_line(raw, cid)
            return csum + cnote
    if read_work and s.is_work_id(cid):
        raw = read_work(cid)
        if raw:
            cnote, csum, _ = _work_line(raw, cid)
            return csum + cnote
    if read_question and s.is_question_id(cid):
        raw = read_question(cid)
        if raw:
            cnote, csum = _question_line(raw, cid)
            return csum + cnote
    crow, cnote = find_either(log, archive, cid)
    return (shorten(crow) + details_note(crow) + cnote) if crow else "not found"


def report_ids(log, ids, archive="", read_ruling=None, read_work=None, read_question=None):
    """Lines for each ID asked for, from entry files or decision-log/decision-archive; returns (lines, unknown IDs)."""
    lines, unknown, wl = [], [], work_list_ids(log) | work_list_ids(archive, "Done work")
    for ident in ids:
        raw = read_ruling(ident) if read_ruling and s.is_ruling_id(ident) else None
        if raw:
            note, summary = _ruling_line(raw, ident)
            lines.append(f"== {ident}" + note)
            lines.append(summary)
            continue
        wraw = read_work(ident) if read_work and s.is_work_id(ident) else None
        if wraw:
            note, summary, cids = _work_line(wraw, ident)
            lines.append(f"== {ident}" + note)
            lines.append(summary)
            jobs = s.parse_entry(wraw, ident=ident)["meta"].get("Jobs", "")
            if jobs:
                lines.append(f"  Jobs: {jobs}")
            for cid in cids:
                lines.append(f"  {cid}: " + _lookup_entry_line(cid, log, archive, read_ruling, read_work, read_question))
            continue
        qraw = read_question(ident) if read_question and s.is_question_id(ident) else None
        if qraw:
            note, summary = _question_line(qraw, ident)
            lines.append(f"== {ident}" + note)
            lines.append(summary)
            continue
        row, note = find_either(log, archive, ident)
        if row is None:
            unknown.append(ident)
            lines.append(f"{ident}: not found in 03_Past_Decisions/decision-log.md or 03_Past_Decisions/decision-archive.md")
            continue
        lines.append(f"== {ident}" + note)
        lines.append(row.strip() + details_note(row))
        if ident in wl:
            for cid in cited_ids(row):
                lines.append(f"  {cid}: " + _lookup_entry_line(cid, log, archive, read_ruling, read_work, read_question))
    return lines, unknown


# --- Waiting on William (T93): read from main's log, handoffs and board, so nobody keeps the list by hand.
DECISION_ID = re.compile(r"\b[IAUDMWPG]\d+[a-z]?\b")   # a logged decision (not a Q question or T item)
YOUR_CALL = re.compile(r"your call(?!, \d{4}-)", re.I)    # "Your call, 2026-11-21: ..." records an answer
ASK = re.compile(r"\bask William\b", re.I)
ANSWERED = re.compile(r"William's answer", re.I)


def sentence_at(text, i, n=90):
    """The sentence around position i, on one line, shortened to n characters."""
    cuts = [j + 2 for j in (text.rfind(". ", 0, i), text.rfind("\n\n", 0, i)) if j >= 0]
    start = max(cuts, default=0)
    end = text.find(". ", i)
    out = " ".join(text[start:end + 1 if end >= 0 else len(text)].split())
    return out if len(out) <= n else out[: n - 3] + "..."


def waiting_rows(log, work_entries=None):
    """Open Work list items whose Result / next step leaves something as "your call" with no decision ID after it."""
    out = []
    if work_entries is not None:
        for ident in sorted(work_entries, key=lambda x: s.key(f"| {x} |")):
            val = work_entries[ident]
            e = s.parse_entry(val, ident=ident) if isinstance(val, str) else val
            if e["meta"].get("Status") != "Open":
                continue
            res = e["result"]
            marks = list(YOUR_CALL.finditer(res))
            if marks and not DECISION_ID.search(res, marks[-1].end()):
                out.append((ident, sentence_at(res, marks[-1].start())))
        return out
    for line in section(log, "Work list"):
        if not line.startswith("| ") or line.startswith("| #"):
            continue
        c = cells(line)
        if len(c) < 5 or c[2] != "Open":
            continue
        marks = list(YOUR_CALL.finditer(c[-1]))
        if marks and not DECISION_ID.search(c[-1], marks[-1].end()):
            out.append((c[0], sentence_at(c[-1], marks[-1].start())))
    return out


def tentative_principles(log):
    return [(c[0], shorten(c[1], 90)) for c in (cells(l) for l in section(log, "Principles") if l.startswith("| G"))
            if len(c) > 2 and c[2] == "Tentative"]


def waiting_handoffs(entries):
    """Open or queued handoffs with an "Ask William" sentence and no answer after it: a "William's answers" line, or
    a Response line that names a logged decision."""
    out = []
    for name, text in sorted(entries.items()):
        status = re.search(r"\| Status: ([^|\n]*)", text)
        if not status or not status.group(1).strip().startswith(("open", "queued")):
            continue
        ask = ASK.search(text)
        if not ask:
            continue
        rest = text[ask.end():]
        if ANSWERED.search(rest) or any(l.startswith("Response") and DECISION_ID.search(l) for l in rest.splitlines()):
            continue
        out.append((name.split("-")[0], sentence_at(text, ask.start())))
    return out


def william_notes(board):
    return [l.strip().removeprefix("- ") for l in section(board, "Notes")
            if re.match(r"-?\s*(for )?William\b", l.strip().removeprefix("- "), re.I)]


def waiting_on_william(log, entries, board, lock_held, work_entries=None):
    """The report's lines: one per thing that waits on William, with its ID and a short reason."""
    lines = [f"  {i} (Work list): {why}" for i, why in waiting_rows(log, work_entries=work_entries)]
    lines += [f"  {i} (principle, Tentative): {text}" for i, text in tentative_principles(log)]
    lines += [f"  {i} (handoff): {why}" for i, why in waiting_handoffs(entries)]
    lines += [f"  Board note: {shorten(n, 150)}" for n in william_notes(board)]
    if not lines:
        lines = ["  (nothing)"]
    if lock_held:
        lines.append("  Integrator: after a clear, re-arm the queue watch: job.py watch --next in the background (docs/integrator.md); no timed check-ins")
    return lines


def follow_up_lines(text, limit=None):
    """The report's lines for docs/follow-ups.md (P26, T97): one per open follow-up, or "(none)"."""
    rows = [l for l in (text or "").split("\n") if re.match(r"^- \S+ \([^)]*\): ", l)]
    if not rows:
        return ["  (none)"]
    if limit is not None and len(rows) > limit:
        older = len(rows) - limit
        return [f"  ... ({older} earlier in docs/follow-ups.md)"] + [
            "  " + l.removeprefix("- ").rstrip() for l in rows[-limit:]
        ]
    return ["  " + l.removeprefix("- ").rstrip() for l in rows]


def journal_lines(root, limit=20):
    """Last `limit` lines of the rolling integrator journal in git-common-dir (read-only)."""
    common = git("rev-parse", "--git-common-dir", cwd=root).strip()
    if not common:
        return []
    path = os.path.join(common if os.path.isabs(common) else os.path.join(root, common),
                        "shopsketch-integrator-journal.log")
    if not os.path.isfile(path):
        return []
    try:
        lines = [l.rstrip() for l in open(path, encoding="utf-8").read().splitlines() if l.strip()]
    except OSError:
        return []
    return lines[-limit:]


ROLES = ("integrator", "worker")


def parse_args(argv):
    """Split [--role <name> | --role=<name>] from positional IDs -> (role or None, ids, error or None)."""
    role, ids, i = None, [], 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--role":
            if i + 1 >= len(argv):
                return None, [], f"startup.py: --role needs a value (use: {', '.join(ROLES)})"
            role = argv[i + 1].strip().lower()
            i += 2
        elif arg.startswith("--role="):
            role = arg.split("=", 1)[1].strip().lower()
            i += 1
        else:
            ids.append(arg)
            i += 1
    if role is not None and role not in ROLES:
        return None, [], f"startup.py: unknown role {role!r} (use: {', '.join(ROLES)})"
    return role, ids, None


def integrator_notes(entries):
    """Open handoff entries addressed to the integrator -> [(heading, 'docs/handoff/<file>')]."""
    out = []
    for name, text in sorted(entries.items()):
        status = re.search(r"\| Status: ([^|\n]*)", text, re.I)
        who = re.search(r"\| For: ([^|\n]*)", text, re.I)
        if not status or not who:
            continue
        if not status.group(1).strip().lower().startswith("open"):
            continue
        if who.group(1).strip().lower() not in ("the integrator", "integrator"):
            continue
        heading = next((l.lstrip("#").strip() for l in text.splitlines() if l.startswith("### ")), name[:-3])
        out.append((heading, f"docs/handoff/{name}"))
    return out


def is_state_note(name, text):
    """True when an integrator handoff is a pre-/clear state note whose body should be surfaced inline."""
    return "integrator-state" in name.lower() or "archive it once read" in text.lower()


def state_note_body(text, max_lines=60):
    """Body lines of an integrator state note, omitting the ### heading and Author/Touches boilerplate."""
    lines = []
    for line in text.splitlines():
        if not lines and (not line.strip() or line.startswith("### ") or line.startswith(("Author:", "Touches:"))):
            continue
        lines.append(line)
    while lines and not lines[-1].strip():
        lines.pop()
    if len(lines) > max_lines:
        return lines[:max_lines] + [f"... ({len(lines) - max_lines} more lines; read the file for the rest)"]
    return lines


def parse_interrupted_merge(state, merge_head, state_path=""):
    """Describe any paused integrate.py merge or raw MERGE_HEAD -> dict or None (pure, read-only)."""
    if state and merge_head:
        reasons = []
        if state.get("maps"):
            reasons.append(f"map updates ({len(state['maps'])})")
        if state.get("changed"):
            reasons.append(f"brief changes ({len(state['changed'])})")
        if not reasons:
            reasons.append("paused commit")
        return {
            "kind": "paused",
            "branch": state.get("branch", "?"),
            "reasons": reasons,
            "summary": f"paused merge on {state.get('branch', '?')} waiting for {', '.join(reasons)}",
            "action": "python3 tools/integrate.py --continue --as <session> --push --yes",
        }
    if merge_head:
        return {
            "kind": "git_merge",
            "branch": merge_head,
            "reasons": ["MERGE_HEAD"],
            "summary": f"git merge in progress (MERGE_HEAD={merge_head[:12]}) with no integrate.py state file",
            "action": "inspect `git status` and finish or `git merge --abort`",
        }
    if state:
        where = state_path or "shopsketch-integrate.json"
        return {
            "kind": "stale_state",
            "branch": state.get("branch", "?"),
            "reasons": ["stale state file"],
            "summary": f"stale paused-merge state for {state.get('branch', '?')} with no MERGE_HEAD ({where})",
            "action": f"inspect and remove {where} if that merge was already finished or aborted",
        }
    return None


def interrupted_merge(root):
    """Read-only check for an interrupted merge (integrate.py state file and/or MERGE_HEAD)."""
    common = git("rev-parse", "--git-common-dir", cwd=root).strip()
    state_path = os.path.join(common if os.path.isabs(common) else os.path.join(root, common),
                              "shopsketch-integrate.json") if common else ""
    state = None
    if state_path and os.path.isfile(state_path):
        try:
            state = json.load(open(state_path, encoding="utf-8"))
        except (OSError, ValueError):
            state = {"branch": "(unreadable state file)"}
    merge_head = git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=root).strip()
    return parse_interrupted_merge(state, merge_head, state_path)


def worker_job_context(root, branch, entries):
    """If inside a job worktree/branch matching an open handoff, return (id, heading, path, touches_line) else None."""
    m = re.search(r"\b(h\d+)\b", branch or "", re.I) or re.search(r"\b(h\d+)\b", os.path.basename(root or ""), re.I)
    if not m:
        return None
    jid = m.group(1).upper()
    for name, text in sorted(entries.items()):
        if not name.upper().startswith(jid + "-"):
            continue
        heading = next((l.lstrip("#").strip() for l in text.splitlines() if l.startswith("### ")), name[:-3])
        touches = next((l.strip() for l in text.splitlines() if l.startswith("Touches:")), "")
        return jid, heading, f"docs/handoff/{name}", touches
    return None


def integrator_next_actions(lock_holder, state_note_ids, merge_info, live_jobs, ready_count):
    """Concrete next actions for an integrator, derived read-only from live repo/queue state."""
    actions = []
    archive_flags = "".join(f" --archive {hid}" for hid in state_note_ids) + (" --push" if state_note_ids else "")
    take_cmd = f"python3 tools/integrator.py take <session>{' --william' if lock_holder else ''}{archive_flags}"
    lead = (f"Lock is held by {lock_holder}" if lock_holder else "No integrator lock held")
    if state_note_ids:
        notes_csv = ", ".join(state_note_ids)
        actions.append(
            f"{lead} (reading this brief does not grant authority): if William named you integrator, read {notes_csv} "
            f"above (already inline; no need to open its file or BOARD.md) and take the lock + archive/commit/push "
            f"in one step (writes .git/, run outside sandbox / BypassSandbox: true): {take_cmd}"
        )
    else:
        actions.append(
            f"{lead} (reading this brief does not grant authority): if William named you integrator, take the lock "
            f"(writes .git/, run outside sandbox / BypassSandbox: true): {take_cmd}"
        )
    if merge_info:
        actions.append(f"Interrupted merge: {merge_info['summary']} -> {merge_info['action']}")
    for jid, info in live_jobs:
        st = info.get("state")
        if st == "waiting":
            actions.append(f"Answer waiting worker {jid}: {info.get('label', '')} -> python3 tools/job.py answer {jid} \"<answer>\"")
        elif st == "done":
            actions.append(f"Review and integrate {jid} ({info.get('branch', '?')}): python3 tools/integrate.py {info.get('branch', '?')} --as <session> --push --yes")
        elif st == "stale":
            actions.append(f"Inspect stale job {jid} ({info.get('branch', '?')} in {info.get('worktree', '?')})")
        elif st == "returned":
            actions.append(f"Returned job {jid} waits for a {info.get('agent', '?')} worker")
    actions.append("Arm queue watch in the background: python3 tools/job.py watch --next (no timed check-ins, P39)")
    if ready_count and not live_jobs:
        noun = "job" if ready_count == 1 else "jobs"
        actions.append(f"{ready_count} Ready {noun} on BOARD.md (spin up workers on William's word)")
    return actions


def role_summary(lock_holder, state_note_ids, ready_count, merge_info, in_job_id=None):
    """Two-line briefing-officer summary for bare startup.py (read-only; never grants authority)."""
    parts = [f"Integrator lock held by {lock_holder}." if lock_holder else "No integrator lock held."]
    if state_note_ids:
        parts.append(f"Open integrator handoff: {', '.join(state_note_ids)}.")
    parts.append(f"Ready jobs: {ready_count}.")
    parts.append(f"Interrupted merge: {merge_info['summary']}." if merge_info else "No interrupted merges.")
    if in_job_id:
        parts.append(f"Job checkout detected: {in_job_id}.")
    tip = (f"Role tip: pass --role worker for a lean brief on {in_job_id} "
           "(or --role integrator if William named you integrator; read-only, never takes the lock)."
           if in_job_id else
           "Role tip: pass --role integrator (integrator brief, state notes & next actions; read-only, never takes the lock) "
           "or --role worker (lean worker brief).")
    return ["Summary: " + " ".join(parts), tip]


def role_brief(role):
    """Concise checklist lines for a known role."""
    if role == "integrator":
        return [
            "Integrator checklist (docs/integrator.md):",
            "  Guide: read docs/integrator.md only (skip CLAUDE.md and BOARD.md upfront; owns BOARD.md, ARCHITECTURE.md, docs/protocol.md; only you merge/push).",
            "  Lock: python3 tools/integrator.py take <session> --william [--archive <ID> --push] (writes .git/, run outside sandbox / BypassSandbox: true; --role never grants authority).",
            "  Watch: run python3 tools/job.py watch --next in the background (no timed check-ins, P39).",
            "  Notes: pre-/clear notes are printed inline above; archive with take --archive <ID> --push (or python3 tools/handoff.py archive <ID> --push).",
        ]
    if role == "worker":
        return [
            "Worker checklist (BOARD.md):",
            "  Guide: follow BOARD.md (and AGENTS.md / GEMINI.md for your agent); one job per session (P37).",
            "  Take: python3 tools/job.py take --as <claude|codex|gemini> (Gemini without --session: job.py reads its conversation id, GEMINI.md).",
            "  Scope: work only in ../.worktrees/<checkout>/<id> (P63) and only on Touches; ask scope via job.py wait --scope.",
            "  Done: run tools/quicktest.sh, record response + Result:, set Status: answered, run python3 tools/job.py done, tell William.",
        ]
    return []


def collect_live_jobs(root):
    """Read-only snapshot of active queue jobs for next-action synthesis -> [(jid, info)]."""
    try:
        import job
        now = time.time()
        st = job.read_state(job.state_path(root))
        out = []
        for k, j in sorted(st["jobs"].items()):
            s = j.get("state")
            if s not in job.ACTIVE:
                continue
            jcopy = dict(j)
            act = job.refresh(root, jcopy, now)
            state = "stale" if job.stale(jcopy, act, now) else jcopy.get("state")
            label = job.waiting_line(k, jcopy) if state == "waiting" else job.live_label(jcopy, act, now)
            out.append((k, {"state": state, "branch": jcopy.get("branch"), "worktree": jcopy.get("worktree"),
                            "agent": jcopy.get("agent"), "label": label}))
        return out
    except Exception:
        return []


INTEGRATOR_SPACE = "opus-integrator"   # the integrator's personal space (T134), comitatus/04_Personal_Space/<name>


def split_space(argv):
    """[--space <name> | --space=<name>] -> (name or None, the other arguments)."""
    space, rest, i = None, [], 0
    while i < len(argv):
        if argv[i] == "--space" and i + 1 < len(argv):
            space, i = argv[i + 1], i + 2
        elif argv[i].startswith("--space="):
            space, i = argv[i].split("=", 1)[1], i + 1
        else:
            rest.append(argv[i]); i += 1
    return space, rest


def space_lines(root, space):
    """The last ten lines of the member's Log and Journal (T134), or the old journal file when there's no space."""
    try:
        import personal_space
        lines = personal_space.brief_lines(space, 10, personal_space.main_root(root))
    except Exception:
        lines = []
    return lines


def main(argv):
    space, argv = split_space(argv)
    role, ids, err = parse_args(argv)
    if err:
        print(err)
        return 1
    root = git("rev-parse", "--show-toplevel").strip()
    if not root:
        print("startup.py: not inside a git checkout")
        return 1
    branch = git("branch", "--show-current", cwd=root).strip() or "(detached)"
    changed = [l for l in git("status", "--porcelain", cwd=root).splitlines() if l.strip()]
    print(f"This checkout: {root} on {branch}, " + ("clean" if not changed else f"{len(changed)} changed file" + ("s" if len(changed) > 1 else "")))

    refs = parse_refs(git("for-each-ref", "--format=%(refname:short)|%(ahead-behind:main)|%(committerdate:short)",
                          "refs/heads", "refs/remotes", cwd=root))
    import integrator
    lock_info = integrator.read(integrator.lock_path(root))
    lock_holder = lock_info.get("holder") if lock_info else None
    if role != "worker":
        merged = {n for n, a, b, _ in refs if a == 0 and b > 0}
        trees = parse_worktrees(git("worktree", "list", "--porcelain", cwd=root))
        shown = [(p, b) for p, b in trees if b not in merged or p == root]
        print(f"Worktrees ({len(trees) - len(shown)} on merged branches hidden):")
        for p, b in shown:
            print(f"  {p}  [{b}]")

        print(integrator.status_line(integrator.lock_path(root)))

    print("Recent main:")
    for l in git("log", "--oneline", "-5", "main", cwd=root).splitlines():
        print("  " + l)

    if role != "worker":
        unmerged, hidden = agent_branches(refs)
        print(f"Branches with commits not on main ({hidden} merged branches hidden):")
        for name, ahead, date in unmerged:
            print(f"  {name}  +{ahead}  last {date}")
        if not unmerged:
            print("  (none)")

    board = git("show", "main:BOARD.md", cwd=root)
    jobs = ready_jobs(board, [n for n, *_ in refs])
    print("Ready on the board (main:BOARD.md):")
    for job_id, who, item, claim in jobs:
        print(f"  {job_id} ({who}) {item}" + (f"  - claimed by {claim}" if claim else ""))
    if not jobs:
        print("  (none)")
    if role == "integrator":
        qjobs = queued_jobs(board)
        if qjobs:
            print("Queued on the board (main:BOARD.md):")
            for job_id, who, item, waits in qjobs:
                print(f"  {job_id} ({who}) {item}" + (f"  [waits for {waits}]" if waits else ""))
    for l in notes(board):
        print("  Note: " + l.strip().removeprefix("- "))
    try:                     # the live queue (P24): read-only so startup works inside a sandbox too
        import job
        lines = []
        job.status(root, out=lines.append, readonly=True)
        print("Job queue (tools/job.py status):")
        for l in lines:
            print("  " + l)
    except Exception as e:   # the queue is a convenience here; startup still reports the rest
        print(f"Job queue: not read ({type(e).__name__}: {e})")

    names = [l.split("/")[-1] for l in git("ls-tree", "--name-only", "main", "docs/handoff/", cwd=root).splitlines()
             if l.endswith(".md")]
    texts = {n: git("show", f"main:docs/handoff/{n}", cwd=root) for n in names}
    job_ctx = worker_job_context(root, branch, texts)
    merge_info = interrupted_merge(root) if role != "worker" else None

    log = git("show", "main:03_Past_Decisions/decision-log.md", cwd=root) if (role != "worker" or ids) else ""
    if role != "worker":
        import handoff   # the open jobs' Touches lists, from main (P11): a file two open jobs both list
        clash = handoff.overlaps_in(texts)
        for path, overlap_ids in clash:
            print(f"  OVERLAP: {path} is in {' and '.join(overlap_ids)}: only one of them should be open (P11)")
        for f, b in gone_branches(texts, [r[0] for r in refs]):
            print(f"  GONE: {f} names {b}, which no longer exists: update the note")

        work_names = [l.split("/")[-1] for l in git("ls-tree", "--name-only", "main", s.WORK_DIR + "/", cwd=root).splitlines()
                      if l.endswith(".md")]
        work_entries = {n[:-3]: git("show", f"main:{s.WORK_DIR}/{n}", cwd=root) for n in work_names} if work_names else None
        print("Waiting on William (from main):")
        print("\n".join(waiting_on_william(log, texts, board, bool(lock_info), work_entries=work_entries)))
        print("Follow-ups (docs/follow-ups.md, from main):")
        print("\n".join(follow_up_lines(git("show", "main:docs/follow-ups.md", cwd=root), limit=5)))
        inotes = integrator_notes(texts)
        state_note_ids = [h.split()[0] for h, p in inotes if is_state_note(os.path.basename(p), texts.get(os.path.basename(p), ""))]
        if role == "integrator":
            slines = space_lines(root, space or INTEGRATOR_SPACE)
            jlines = [] if slines else journal_lines(root)
            for sl in slines:
                print(sl)
            if jlines:
                print("Integrator journal (last 20 lines):")
                for jl in jlines:
                    print("  " + jl)
            print("Interrupted merges:")
            if merge_info:
                print(f"  {merge_info['summary']} -> {merge_info['action']}")
            else:
                print("  (none)")
            print("Notes for the integrator (main:docs/handoff/):")
            if inotes:
                for heading, path in inotes:
                    fname = os.path.basename(path)
                    print(f"  {heading}  [{path}]")
                    if is_state_note(fname, texts.get(fname, "")):
                        for bline in state_note_body(texts[fname]):
                            print("    " + bline if bline else "")
            else:
                print("  (none)")
            live = collect_live_jobs(root)
            print("Next actions (read-only briefing; does not take the lock):")
            for act in integrator_next_actions(lock_holder, state_note_ids, merge_info, live, len(jobs)):
                print("  - " + act)
            print("\n".join(role_brief("integrator")))
        else:
            print("\n".join(role_summary(lock_holder, state_note_ids, len(jobs), merge_info,
                                         in_job_id=job_ctx[0] if job_ctx else None)))
    else:
        if job_ctx:
            jid, heading, path, touches = job_ctx
            print("Assigned job (from this checkout):")
            print(f"  {heading}  [{path}]")
            if touches:
                print(f"  {touches}")
        print("\n".join(role_brief("worker")))
        if space:
            print("\n".join(space_lines(root, space)))

    if ids:
        archive = git("show", "main:03_Past_Decisions/decision-archive.md", cwd=root)
        lines, unknown = report_ids(
            log, ids, archive,
            read_ruling=lambda ident: git("show", f"main:{s.RULINGS_DIR}/{ident}.md", cwd=root) or None,
            read_work=lambda ident: git("show", f"main:{s.WORK_DIR}/{ident}.md", cwd=root) or None,
            read_question=lambda ident: git("show", f"main:{s.QUESTIONS_DIR}/{ident}.md", cwd=root) or None,
        )
        print()
        print("Decision log (main:03_Past_Decisions/decision-log.md, then main:03_Past_Decisions/decision-archive.md):")
        print("\n".join(lines))
        if unknown:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
