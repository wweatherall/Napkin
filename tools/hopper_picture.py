#!/usr/bin/env python3
"""Draw the job queue as a three-part ASCII picture (H203): hopper, workbench, integrator's desk."""
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import job

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def clip(text, width):
    """Collapse whitespace and truncate `text` to `width` characters using `…`."""
    clean = " ".join(str(text or "").split())
    if width <= 0:
        return ""
    if len(clean) <= width:
        return clean
    if width == 1:
        return "…"
    return clean[: width - 1].rstrip() + "…"


def _box_header(title, width):
    label = f" {title} "
    if len(label) + 2 >= width:
        return "+" + clip(label, width - 2).center(width - 2, "-") + "+"
    left = (width - 2 - len(label)) // 2
    right = width - 2 - len(label) - left
    return "+" + ("-" * left) + label + ("-" * right) + "+"


def _box_line(content, width):
    inner = width - 4
    text = str(content or "")
    if len(text) > inner:
        text = clip(text, inner)
    return f"| {text:<{inner}} |"


def _centered_line(content, width):
    inner = width - 4
    return f"| {clip(content, inner):^{inner}} |"


def _format_duration(seconds):
    secs = max(0, int(seconds))
    mins = secs // 60
    if mins < 60:
        return f"{mins}m"
    hours, rem = divmod(mins, 60)
    return f"{hours}h{rem:02d}m"


def _format_worker(entry):
    agent = entry.get("agent") or "?"
    session = entry.get("session") or ""
    if not session or session == agent or UUID_RE.match(session):
        return agent
    return clip(session, 20)


def _batch_order_done(st, order):
    """Order done jobs in batch order: base jobs before stacked jobs, then BOARD.md Order."""
    done_jobs = {jid: j for jid, j in st.get("jobs", {}).items() if j.get("state") == "done"}
    branch_to_jid = {j["branch"]: jid for jid, j in done_jobs.items() if j.get("branch")}
    parent_of = {
        jid: branch_to_jid.get(j.get("base")) if j.get("base") in branch_to_jid else None
        for jid, j in done_jobs.items()
    }
    order_pos = {jid: i for i, jid in enumerate(order)}
    planned, placed, remaining = [], set(), set(done_jobs)
    while remaining:
        ready = [jid for jid in remaining if parent_of[jid] is None or parent_of[jid] in placed]
        if not ready:
            ready = list(remaining)
        pick = min(ready, key=lambda jid: (order_pos.get(jid, len(order_pos)), jid))
        planned.append((pick, done_jobs[pick]))
        placed.add(pick)
        remaining.remove(pick)
    return planned


def _last_merged(st):
    """Return (jid, timestamp) for the most recently merged job, or (None, None)."""
    merged = [
        (j.get("merged") or 0, jid)
        for jid, j in st.get("jobs", {}).items()
        if j.get("state") == "merged"
    ]
    if merged:
        ts, jid = max(merged)
        return jid, ts
    for ev in reversed(st.get("events", [])):
        if ev.get("kind") == "merged" and ev.get("job"):
            return ev["job"], ev.get("at")
    return None, None


def _render_hopper(st, resolved_jobs, order, titles, width):
    lines = [_box_header("HOPPER", width)]
    job_states = st.get("jobs", {})
    launched = st.get("launched", {})
    spout_ids = [
        jid for jid in launched
        if job_states.get(jid, {}).get("state") not in ("in progress", "waiting", "done", "merged")
    ]
    order_pos = {jid: i for i, jid in enumerate(order)}
    ordered_jobs = sorted(
        resolved_jobs,
        key=lambda j: (order_pos.get(j["id"], len(order_pos)),
                       job.handoff.order(j["name"]) if "name" in j else (0, j["id"])),
    )
    in_hopper = [
        j for j in ordered_jobs
        if job_states.get(j["id"], {}).get("state") not in ("in progress", "waiting", "done", "merged")
        and j["id"] not in spout_ids
    ]
    inner = width - 4
    if not in_hopper:
        lines.append(_centered_line("(empty)", width))
    else:
        for j in in_hopper:
            jid = j["id"]
            state = job_states.get(jid, {}).get("state")
            tag = ""
            if state == "returned":
                tag = "[returned]"
            elif j.get("kind") == "queued" and j.get("waits"):
                tag = f"[waits: {j['waits']}]"
            title = j.get("item") or titles.get(jid, "")
            if tag:
                avail = max(8, inner - len(jid) - 1 - len(tag) - 2)
                left = f"{jid} {clip(title, avail)}"
                line = f"{left:<{inner - len(tag)}}{tag}"
            else:
                avail = max(8, inner - len(jid) - 1)
                line = f"{jid} {clip(title, avail)}"
            lines.append(_box_line(line, width))
    lines.append("\\" + ("_" * (width - 2)) + "/")
    lines.append("\\    /".center(width))
    if spout_ids:
        spout = f"|{clip(spout_ids[0], 6):^4}|"
        lines.append(spout.center(width))
        lines.append("v".center(width))
    else:
        lines.append("|    |".center(width))
    return lines


def _render_workbench(st, titles, now, width):
    lines = [_box_header("WORKBENCH", width)]
    working = [
        (jid, j) for jid, j in st.get("jobs", {}).items()
        if j.get("state") in job.WORKING
    ]
    working.sort(key=lambda pair: (pair[1].get("taken") or 0, pair[0]))
    inner = width - 4
    if not working:
        lines.append(_centered_line("(empty)", width))
    else:
        for jid, j in working:
            mark = "?" if j.get("state") == "waiting" else " "
            who = _format_worker(j)
            since = j.get("taken") or j.get("beat") or j.get("since") or now
            dur = _format_duration(now - since)
            right = f"{who}  {dur}"
            title = titles.get(jid, "") or j.get("branch", "")
            prefix = f"{mark} {jid} "
            avail = max(8, inner - len(prefix) - len(right) - 2)
            left = prefix + clip(title, avail)
            line = f"{left:<{inner - len(right)}}{right}"
            lines.append(_box_line(line, width))
    lines.append("+" + ("-" * (width - 2)) + "+")
    return lines


def _render_desk(st, order, titles, width):
    lines = [_box_header("INTEGRATOR'S DESK", width)]
    done_list = _batch_order_done(st, order)
    inner = width - 4
    if not done_list:
        lines.append(_centered_line("(empty)", width))
    else:
        for jid, j in done_list:
            who = j.get("agent") or "?"
            right = f"({who})"
            title = titles.get(jid, "") or j.get("branch", "")
            prefix = f"[=] {jid} "
            avail = max(8, inner - len(prefix) - len(right) - 2)
            left = prefix + clip(title, avail)
            line = f"{left:<{inner - len(right)}}{right}"
            lines.append(_box_line(line, width))
    last_jid, _ = _last_merged(st)
    if last_jid:
        last_title = titles.get(last_jid, "")
        merged_line = f"last merged: {last_jid}" + (f" {last_title}" if last_title else "")
    else:
        merged_line = "last merged: (none)"
    lines.append(_box_line(merged_line, width))
    lines.append("+" + ("-" * (width - 2)) + "+")
    return lines


def render(st, jobs, order, now=None, width=78):
    """Render the three-part ASCII hopper picture from queue state `st`, `jobs`, and `order`."""
    now = time.time() if now is None else now
    resolved = job.resolve_dependencies(jobs, st)
    titles = {j["id"]: j.get("item", "") for j in resolved}
    lines = []
    lines.extend(_render_hopper(st, resolved, order, titles, width))
    lines.extend(_render_workbench(st, titles, now, width))
    lines.extend(_render_desk(st, order, titles, width))
    return "\n".join(lines)


def render_root(cwd, now=None, width=78):
    """Render the hopper picture for the repo containing `cwd` (read-only)."""
    root = job.main_root(cwd)
    jobs, order = job.main_view(root)
    st = job.read_state(job.state_path(root))
    return render(st, jobs, order, now=now, width=width)


def watch(cwd, poll=None, out=print, sleep=time.sleep, clock=time.time, clear=None, max_iterations=None):
    """Redraw the hopper picture whenever the queue file or rendered picture changes."""
    root = job.main_root(cwd)
    poll = job.WATCH_POLL if poll is None else max(job.WATCH_POLL, poll)
    if clear is None:
        clear = out is print and sys.stdout.isatty()
    qpath = job.state_path(root)
    last_sig = None
    count = 0
    while True:
        try:
            stat = os.stat(qpath)
            mtime = (stat.st_mtime_ns, stat.st_size)
        except OSError:
            mtime = None
        pic = render_root(root, now=clock())
        sig = (mtime, pic)
        if sig != last_sig:
            if clear:
                sys.stdout.write("\033[H\033[J")
                sys.stdout.flush()
            out(pic)
            sys.stdout.flush()
            last_sig = sig
        count += 1
        if max_iterations is not None and count >= max_iterations:
            return
        sleep(poll)
