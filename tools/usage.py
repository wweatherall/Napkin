#!/usr/bin/env python3
"""usage.py: Passive usage & token benchmarker for Shop Sketch jobs (Claude & Gemini).

Combines:
  1. Quota % deltas from claude-usage/history.jsonl and agy-usage-monitor/history.jsonl
  2. Per-session telemetry from claude-usage/sessions.jsonl and AGY brain transcripts
  3. Job lifecycle & brief metadata from fretchup (.git/shopsketch-jobs.json, docs/handoff*, git)
  4. Fast `orient` / `bench` / `holes` / `overhead` / `viz` diagnostics.

Zero external dependencies (Python 3 standard library only).
"""

import argparse
import collections
import datetime
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time

ANSI = {
    "reset": "\x1b[0m",
    "bold": "\x1b[1m",
    "dim": "\x1b[2m",
    "red": "\x1b[31m",
    "green": "\x1b[32m",
    "yellow": "\x1b[33m",
    "blue": "\x1b[34m",
    "magenta": "\x1b[35m",
    "cyan": "\x1b[36m",
    "white": "\x1b[37m",
}
SPARK_BLOCKS = " ▁▂▃▄▅▆▇█"

_THIS_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REPO = os.environ.get("FRETCHUP_REPO", _THIS_REPO)
DEFAULT_CLAUDE_DIR = os.environ.get("CLAUDE_USAGE_DIR", "/Users/Will/Sites/claude-usage")
DEFAULT_AGY_DIR = os.environ.get("AGY_USAGE_DIR", "/Users/Will/Sites/agy-usage-monitor")
DEFAULT_AGY_BRAIN = os.environ.get(
    "AGY_BRAIN_DIR", os.path.expanduser("~/.gemini/antigravity-cli/brain")
)

TRACKED_AGENTS = ("claude", "gemini")
PROVIDER_BUCKETS = {
    "claude": ("claude-5h", "claude-7d"),
    "gemini": ("gemini-5h", "gemini-weekly"),
}

# Jump larger than this upward in remaining_fraction is treated as a quota window reset.
RESET_JUMP_THRESHOLD = 0.02
# Brief downward dip larger than this that rebounds within a few samples is filtered as noise.
DOWN_GLITCH_THRESHOLD = 0.002


# ---- Helpers ----

def git(root, *args):
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return subprocess.CompletedProcess(["git", *args], 1, "", "")


def common_git_dir(repo):
    dotgit = os.path.join(repo, ".git")
    if os.path.isdir(dotgit):
        return os.path.realpath(dotgit)
    r = git(repo, "rev-parse", "--git-common-dir")
    if r.returncode == 0 and r.stdout.strip():
        return os.path.realpath(os.path.join(repo, r.stdout.strip()))
    return os.path.realpath(repo)


def jobs_state_path(repo):
    return os.path.join(common_git_dir(repo), "shopsketch-jobs.json")


def default_ledger_path(repo):
    return os.path.join(common_git_dir(repo), "shopsketch-usage.jsonl")


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load_jsonl(path):
    rows = []
    if not path:
        return rows
    try:
        if not os.path.isfile(path):
            return rows
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        rows.append(obj)
                except ValueError:
                    continue
    except OSError:
        return rows
    return rows


def append_jsonl(path, record):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def ts_sec(val):
    """Normalize epoch seconds or milliseconds to float seconds."""
    if val is None:
        return None
    try:
        v = float(val)
    except (TypeError, ValueError):
        return None
    return v / 1000.0 if v > 1e11 else v


def parse_iso_ts(val):
    """Parse an ISO-8601 timestamp string (e.g. '...Z') or numeric timestamp to epoch seconds."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return ts_sec(val)
    if not isinstance(val, str) or not val.strip():
        return None
    s = val.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def human_model_name(raw):
    """Turn a model slug like 'gemini-4-neon-medium' into a concise human-readable label."""
    if not raw:
        return "-"
    s = str(raw).strip()
    low = s.lower()
    m = re.match(r"^gemini-(\d+(?:\.\d+)?)-([a-z0-9]+)-(low|medium|high)$", low)
    if m:
        effort = {"low": "Low", "medium": "Med", "high": "High"}[m.group(3)]
        return f"Gemini {m.group(1)} {m.group(2).title()} ({effort})"
    m = re.match(r"^gemini-(\d+(?:\.\d+)?)-([a-z0-9-]+)$", low)
    if m:
        rest = " ".join(p.title() for p in m.group(2).split("-"))
        return f"Gemini {m.group(1)} {rest}"
    m = re.match(r"^claude-([a-z]+)-(\d+(?:-\d+)?)", low)
    if m:
        ver = m.group(2).replace("-", ".")
        return f"Claude {m.group(1).title()} {ver}"
    return s


def weighted_tokens(fresh_in, cache_read, out):
    """Cache-discounted, output-weighted token proxy for rough 5h quota calibration."""
    return (fresh_in or 0) + 0.1 * (cache_read or 0) + 4.0 * (out or 0)


def fmt_dur(seconds):
    if seconds is None or seconds < 0:
        return "-"
    s = int(round(seconds))
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def fmt_pct(frac, signed=False):
    if frac is None:
        return "-"
    pct = frac * 100.0
    if signed:
        return f"{pct:+.2f}%"
    return f"{pct:.2f}%"


def fmt_tokens(n):
    if n is None:
        return "-"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(int(n))


def fmt_usd(val):
    if val is None:
        return "-"
    return f"${val:.3f}"


# ---- Quota Delta Calculation ----

def load_quota_history(claude_dir, agy_dir):
    """Return {provider: sorted list of (ts_sec, buckets_dict)}."""
    out = {}
    for provider, base_dir in (("claude", claude_dir), ("gemini", agy_dir)):
        path = os.path.join(base_dir, "history.jsonl") if base_dir else ""
        samples = []
        for row in load_jsonl(path):
            t = ts_sec(row.get("ts"))
            b = row.get("buckets")
            if t is not None and isinstance(b, dict):
                samples.append((t, b))
        samples.sort(key=lambda x: x[0])
        out[provider] = samples
    return out


def compute_bucket_burn(
    samples,
    bucket_key,
    start_s,
    end_s,
    pad_before=120.0,
    pad_after=60.0,
    next_event_s=None,
):
    """Compute fraction of quota burned in [start_s, end_s] for one bucket.

    Handles:
      - Mid-window quota resets (upward jump > RESET_JUMP_THRESHOLD splits segments)
      - Transient upward spike glitches (e.g. AGY briefly reporting 1.0 then snapping back)
      - Transient downward rebound dips (prev - cur > 0.002 then rebounding back toward prev)
      - Clamping pad_after against next_event_s so an immediately following session doesn't bleed in
      - Small measurement jitter (~0.0003 oscillation in AGY polling)

    Returns (burn_fraction_or_None, sample_count).
    """
    if not samples or start_s is None or end_s is None or end_s < start_s:
        return None, 0

    max_after_t = end_s + pad_after
    if next_event_s is not None:
        max_after_t = max(end_s, min(max_after_t, next_event_s))

    before = None
    in_window = []
    after = None
    for t, b in samples:
        if bucket_key not in b or not isinstance(b[bucket_key], (int, float)):
            continue
        val = float(b[bucket_key])
        if t < start_s:
            if start_s - t <= pad_before:
                before = (t, val)
        elif t <= end_s:
            in_window.append((t, val))
        else:
            if t <= max_after_t and after is None:
                after = (t, val)
            break

    pts = []
    if before is not None:
        pts.append(before)
    pts.extend(in_window)
    if after is not None and (not in_window or end_s - in_window[-1][0] > 10.0):
        pts.append(after)

    if len(pts) < 2:
        return None, len(pts)

    # Filter transient API glitches:
    # 1. Upward spike (e.g. AGY briefly reporting 1.0 then snapping back near prev)
    # 2. Downward rebound dip (prev - cur > 0.002 then rebounding back toward prev)
    cleaned = [pts[0]]
    i = 1
    while i < len(pts):
        prev_val = cleaned[-1][1]
        cur_val = pts[i][1]
        if cur_val - prev_val > RESET_JUMP_THRESHOLD:
            snap_back = None
            for k in range(i + 1, min(len(pts), i + 11)):
                if abs(pts[k][1] - prev_val) <= RESET_JUMP_THRESHOLD:
                    snap_back = k
                    break
            if snap_back is not None:
                i = snap_back
                continue
        elif prev_val - cur_val > DOWN_GLITCH_THRESHOLD:
            rebound = None
            for k in range(i + 1, min(len(pts), i + 6)):
                kval = pts[k][1]
                if (
                    kval - cur_val > DOWN_GLITCH_THRESHOLD
                    and kval <= prev_val + RESET_JUMP_THRESHOLD
                    and (prev_val - kval) < (prev_val - cur_val) * 0.7
                ):
                    rebound = k
                    break
            if rebound is not None:
                i = rebound
                continue
        cleaned.append(pts[i])
        i += 1

    if len(cleaned) < 2:
        return None, len(cleaned)

    # Split into monotonic segments separated by genuine quota resets
    segments = []
    seg_start = cleaned[0][1]
    prev = cleaned[0][1]
    for _, val in cleaned[1:]:
        if val - prev > RESET_JUMP_THRESHOLD:
            segments.append((seg_start, prev))
            seg_start = val
        prev = val
    segments.append((seg_start, prev))

    total_burn = 0.0
    for s_val, e_val in segments:
        drop = s_val - e_val
        if drop > 0:
            total_burn += drop

    return round(total_burn, 6), len(cleaned)


def compute_quota_deltas(
    history_by_provider, provider, start_s, end_s, pad_before=120.0, pad_after=60.0, next_event_s=None
):
    """Return dict of {bucket: burn_fraction} and total sample count."""
    samples = history_by_provider.get(provider, [])
    buckets = PROVIDER_BUCKETS.get(provider, ())
    deltas = {}
    max_samples = 0
    for key in buckets:
        burn, n = compute_bucket_burn(
            samples, key, start_s, end_s, pad_before=pad_before, pad_after=pad_after, next_event_s=next_event_s
        )
        if burn is not None:
            deltas[key] = burn
        max_samples = max(max_samples, n)
    return deltas, max_samples


# ---- Claude Per-Session Telemetry ----

def load_claude_sessions(claude_dir):
    """Load sessions.jsonl rows normalized with float ts_sec."""
    if not claude_dir:
        return []
    rows = load_jsonl(os.path.join(claude_dir, "sessions.jsonl"))
    out = []
    for r in rows:
        t = ts_sec(r.get("ts"))
        if t is None:
            continue
        r = dict(r)
        r["_ts"] = t
        out.append(r)
    out.sort(key=lambda x: x["_ts"])
    return out


def classify_claude_role(row, repo):
    """Classify a Claude session row as ('integrator', None) or ('worker', job_id) or ('other', None)."""
    cwd = os.path.realpath(row.get("cwd") or "") if row.get("cwd") else ""
    repo_real = os.path.realpath(repo)
    jobs_dir = os.path.realpath(os.path.join(os.path.dirname(repo_real), os.path.basename(repo_real) + "-jobs"))
    if not cwd:
        return "unknown", None
    if cwd == repo_real or cwd.startswith(repo_real + os.sep):
        return "integrator", None
    if cwd == jobs_dir or cwd.startswith(jobs_dir + os.sep):
        rel = os.path.relpath(cwd, jobs_dir).split(os.sep)[0]
        m = re.match(r"^(h\d+)$", rel, re.I)
        return "worker", (m.group(1).upper() if m else rel.upper())
    base = os.path.basename(cwd)
    m = re.match(r"^fretchup-(h\d+)$", base, re.I)
    if m:
        return "worker", m.group(1).upper()
    return "other", None


def summarize_claude_session(session_rows, session_id=None, worktree=None, start_s=None, end_s=None):
    """Aggregate exact token/cost/context metrics for a Claude session (optionally bounded by time)."""
    matched = []
    wt_real = os.path.realpath(worktree) if worktree else None
    for r in session_rows:
        sid_match = session_id and r.get("session_id") == session_id
        cwd_match = wt_real and r.get("cwd") and os.path.realpath(r["cwd"]) == wt_real
        if not (sid_match or cwd_match):
            continue
        if start_s is not None and r["_ts"] < start_s - 60:
            continue
        if end_s is not None and r["_ts"] > end_s + 120:
            continue
        matched.append(r)

    if not matched:
        return None

    baseline = None
    if start_s is not None and session_id:
        prior = [r for r in session_rows if r.get("session_id") == session_id and r["_ts"] < start_s - 5]
        if prior:
            baseline = prior[-1]

    def session_counter(key):
        vals = [r[key] for r in matched if isinstance(r.get(key), (int, float))]
        if not vals:
            return None
        end_v = vals[-1]
        if baseline and isinstance(baseline.get(key), (int, float)):
            return max(0, end_v - baseline[key])
        return end_v

    ctx_vals = [r["context_used_pct"] for r in matched if isinstance(r.get("context_used_pct"), (int, float))]
    models = [r["model"] for r in matched if r.get("model")]
    transcripts = [r["transcript_path"] for r in matched if r.get("transcript_path")]

    return {
        "model": models[-1] if models else None,
        "turns": len(matched),
        "input_tokens": session_counter("total_input_tokens"),
        "output_tokens": session_counter("total_output_tokens"),
        "cost_usd": session_counter("cost_usd"),
        "peak_context_pct": round(max(ctx_vals), 1) if ctx_vals else None,
        "end_context_pct": round(ctx_vals[-1], 1) if ctx_vals else None,
        "transcript_path": transcripts[-1] if transcripts else None,
    }


# ---- AGY (Gemini) Transcript Scanning & Telemetry ----

def list_agy_transcripts(agy_brain, min_mtime=None, max_mtime=None, max_files=None):
    """Return [(mtime, conv_id, transcript_path)] sorted newest-first; fail-open if unreadable."""
    if not agy_brain:
        return []
    try:
        entries = os.listdir(agy_brain)
    except OSError:
        return []
    found = []
    for entry in entries:
        tpath = os.path.join(agy_brain, entry, ".system_generated", "logs", "transcript.jsonl")
        try:
            st = os.stat(tpath)
        except OSError:
            continue
        mt = st.st_mtime
        if min_mtime is not None and mt < min_mtime:
            continue
        if max_mtime is not None and mt > max_mtime:
            continue
        found.append((mt, entry, tpath))
    found.sort(key=lambda x: x[0], reverse=True)
    if max_files is not None:
        found = found[:max_files]
    return found


def summarize_agy_session(transcript_path, start_s=None, end_s=None):
    """Aggregate exact token/context metrics from an AGY transcript.jsonl."""
    rows = load_jsonl(transcript_path)
    if not rows:
        return None
    turns = 0
    inp_tot = 0
    cache_tot = 0
    out_tot = 0
    peak_ctx = 0
    model = None
    for row in rows:
        if row.get("type") != "PLANNER_RESPONSE":
            continue
        t = parse_iso_ts(row.get("created_at"))
        if t is not None:
            if start_s is not None and t < start_s - 60:
                continue
            if end_s is not None and t > end_s + 120:
                continue
        inp = int(row.get("input_tokens") or 0)
        cr = int(row.get("cache_read_tokens") or 0)
        out = int(row.get("output_tokens") or 0)
        if row.get("model"):
            model = row["model"]
        if inp or cr or out:
            turns += 1
            inp_tot += inp
            cache_tot += cr
            out_tot += out
            peak_ctx = max(peak_ctx, inp + cr)
    if turns == 0:
        return None
    return {
        "model": model,
        "turns": turns,
        "input_tokens": inp_tot,
        "cache_read_tokens": cache_tot,
        "output_tokens": out_tot,
        "peak_context": peak_ctx,
        "transcript_path": transcript_path,
    }


def _extract_agy_tool_strings(row):
    parts = []
    for tc in row.get("tool_calls") or []:
        if not isinstance(tc, dict):
            continue
        args = tc.get("args")
        if isinstance(args, dict):
            for v in args.values():
                if isinstance(v, str):
                    parts.append(v)
        elif args is not None:
            parts.append(str(args))
    return " ".join(parts)


def classify_agy_transcript(path, conv_id=None):
    """Classify an AGY transcript as integrator/worker/other and return turn timestamps + totals."""
    rows = load_jsonl(path)
    if not rows:
        return None
    is_integrator = False
    is_worker = False
    turn_ts = []
    turns = 0
    inp_tot = 0
    cache_tot = 0
    out_tot = 0
    peak_ctx = 0
    model = None
    session_name = None

    for row in rows:
        rtype = row.get("type")
        if rtype == "USER_INPUT":
            content = str(row.get("content") or "")
            if "integrator" in content.lower():
                is_integrator = True
        elif rtype == "PLANNER_RESPONSE":
            t = parse_iso_ts(row.get("created_at"))
            if t is not None:
                turn_ts.append(t)
            if row.get("model"):
                model = row["model"]
            inp = int(row.get("input_tokens") or 0)
            cr = int(row.get("cache_read_tokens") or 0)
            out = int(row.get("output_tokens") or 0)
            if inp or cr or out:
                turns += 1
                inp_tot += inp
                cache_tot += cr
                out_tot += out
                peak_ctx = max(peak_ctx, inp + cr)
            tstr = _extract_agy_tool_strings(row)
            if "integrator.py take" in tstr or "--role integrator" in tstr:
                is_integrator = True
                m = re.search(r"(gemini-[a-z0-9-]+)", tstr)
                if m:
                    session_name = m.group(1)
            if "job.py take" in tstr or "fretchup-jobs/" in tstr:
                is_worker = True
                if not session_name:
                    m = re.search(r"--session\s+(gemini-[a-z0-9-]+)", tstr)
                    if m:
                        session_name = m.group(1)

    if is_integrator and not is_worker:
        role = "integrator"
    elif is_integrator and is_worker:
        # An integrator may inspect worktrees in fretchup-jobs/; integrator.py take / --role integrator wins
        role = "integrator"
    elif is_worker:
        role = "worker"
    else:
        role = "other"

    if not conv_id:
        parts = os.path.normpath(path).split(os.sep)
        conv_id = parts[-4] if len(parts) >= 4 else os.path.basename(path)

    return {
        "conv_id": conv_id,
        "path": path,
        "role": role,
        "session": session_name,
        "model": model,
        "turns": turns,
        "input_tokens": inp_tot,
        "cache_read_tokens": cache_tot,
        "output_tokens": out_tot,
        "peak_context": peak_ctx,
        "turn_ts": turn_ts,
        "start_ts": min(turn_ts) if turn_ts else None,
        "end_ts": max(turn_ts) if turn_ts else None,
    }


def load_agy_sessions(agy_brain, max_files=200, min_mtime=None):
    """Load classified AGY sessions from agy_brain; fail-open if unreadable."""
    out = []
    for _, conv_id, path in list_agy_transcripts(agy_brain, min_mtime=min_mtime, max_files=max_files):
        info = classify_agy_transcript(path, conv_id=conv_id)
        if info:
            out.append(info)
    return out


# ---- Brief & Git Metadata ----

def load_archive_index(repo):
    """Parse docs/handoff-archive.md into {H0NN: entry_text}."""
    path = os.path.join(repo, "docs", "handoff-archive.md")
    if not os.path.isfile(path):
        return {}
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return {}
    entries = {}
    parts = re.split(r"(?m)^(?=### H\d+\b)", text)
    for part in parts:
        m = re.match(r"^### (H\d+)\b", part)
        if m:
            entries[m.group(1)] = part
    return entries


def read_handoff_text(repo, jid, handoff_name=None, archive_index=None):
    """Find handoff markdown text in docs/handoff/ or docs/handoff-archive.md."""
    folder = os.path.join(repo, "docs", "handoff")
    if handoff_name:
        p = os.path.join(folder, handoff_name)
        if os.path.isfile(p):
            try:
                return open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                pass
    if os.path.isdir(folder):
        prefix = jid.upper() + "-"
        for fn in os.listdir(folder):
            if fn.upper().startswith(prefix) and fn.endswith(".md"):
                try:
                    return open(os.path.join(folder, fn), encoding="utf-8", errors="replace").read()
                except OSError:
                    pass
    if archive_index is not None and jid.upper() in archive_index:
        return archive_index[jid.upper()]
    return ""


def parse_brief_meta(text):
    """Extract brief structure signals (size, Touches count, Reading path, What can fail)."""
    if not text:
        return {}
    resp_split = re.split(r"(?m)^[#*\s]*Response\b", text, maxsplit=1)
    brief = resp_split[0]
    response = resp_split[1] if len(resp_split) > 1 else ""

    touches_count = 0
    m = re.search(r"(?m)^Touches:\s*(.+?)(?:\n\n|\Z)", brief, re.S)
    if m:
        touches_block = re.sub(r"\([^)]*\)", "", m.group(1))
        items = [x.strip() for x in re.split(r",\s*", touches_block) if x.strip()]
        touches_count = len(items)

    return {
        "brief_words": len(brief.split()),
        "brief_lines": len([l for l in brief.splitlines() if l.strip()]),
        "touches_count": touches_count,
        "has_reading_path": bool(re.search(r"(?m)^Reading path:", brief)),
        "has_what_can_fail": bool(re.search(r"(?im)^(#+\s*)?What can fail\b", brief)),
        "response_words": len(response.split()) if response else 0,
    }


def git_diff_stats(repo, commit_sha, branch=None):
    """Return {files_changed, insertions, deletions} for the full job branch (via its merge commit) or commit."""
    if not commit_sha:
        return {}
    merge_sha = None
    r_m = git(repo, "log", "--merges", "--format=%H %P", "--ancestry-path", f"{commit_sha}..HEAD")
    if r_m.returncode == 0:
        for line in r_m.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[2].startswith(commit_sha[:12]):
                merge_sha = parts[0]
                break

    if merge_sha:
        r = git(repo, "diff", "--numstat", f"{merge_sha}^1", f"{merge_sha}^2")
    else:
        r = git(repo, "show", "--numstat", "--format=", commit_sha)

    if r.returncode != 0 or not r.stdout.strip():
        return {}
    files = 0
    ins = 0
    dels = 0
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        path = parts[2]
        if path.startswith("docs/handoff"):
            continue
        files += 1
        if parts[0].isdigit():
            ins += int(parts[0])
        if parts[1].isdigit():
            dels += int(parts[1])
    return {"files_changed": files, "insertions": ins, "deletions": dels}


# ---- Concurrency / Solo Detection ----

def detect_concurrency(
    all_jobs,
    jid,
    agent,
    start_s,
    end_s,
    claude_sessions=None,
    repo=None,
    agy_sessions=None,
    agy_brain=None,
):
    """Determine whether other jobs or the integrator overlapped [start_s, end_s] on the same provider.

    Returns (mode_str, overlap_ids_list) where mode_str is one of:
      'solo', 'shared-worker', 'shared-int', 'shared-both'
    """
    if start_s is None or end_s is None:
        return "unknown", []

    overlapping_workers = []
    for other_id, oj in all_jobs.items():
        if other_id == jid:
            continue
        if oj.get("agent") != agent:
            continue
        o_start = oj.get("taken")
        o_end = oj.get("done") or oj.get("beat") or time.time()
        if o_start is None:
            continue
        if o_start < end_s and o_end > start_s:
            overlapping_workers.append(other_id)

    integrator_active = False
    if agent == "claude" and claude_sessions and repo:
        for r in claude_sessions:
            if start_s <= r["_ts"] <= end_s:
                role, _ = classify_claude_role(r, repo)
                if role == "integrator":
                    integrator_active = True
                    break
    elif agent == "gemini":
        if agy_sessions is None and agy_brain:
            agy_sessions = load_agy_sessions(agy_brain)
        if agy_sessions:
            for s in agy_sessions:
                if s.get("role") != "integrator":
                    continue
                for t in s.get("turn_ts") or ():
                    if start_s <= t <= end_s:
                        integrator_active = True
                        break
                if integrator_active:
                    break

    if overlapping_workers and integrator_active:
        return "shared-both", sorted(overlapping_workers)
    if overlapping_workers:
        return "shared-worker", sorted(overlapping_workers)
    if integrator_active:
        return "shared-int", []
    return "solo", []


# ---- Record Builder ----

def build_job_record(
    jid,
    job_data,
    all_jobs,
    repo,
    quota_history,
    claude_sessions,
    archive_index=None,
    event="backfill",
    agy_brain=None,
    agy_sessions=None,
):
    agent = (job_data.get("agent") or "unknown").lower()
    taken = job_data.get("taken")
    done = job_data.get("done")
    merged = job_data.get("merged")
    end_s = done or job_data.get("beat")

    duration_s = round(end_s - taken, 1) if (taken and end_s and end_s >= taken) else None
    review_s = round(merged - done, 1) if (done and merged and merged >= done) else None

    quota_deltas, quota_samples = ({}, 0)
    if agent in TRACKED_AGENTS and taken and end_s:
        quota_deltas, quota_samples = compute_quota_deltas(quota_history, agent, taken, end_s)

    mode, overlaps = detect_concurrency(
        all_jobs,
        jid,
        agent,
        taken,
        end_s,
        claude_sessions=claude_sessions,
        repo=repo,
        agy_sessions=agy_sessions,
        agy_brain=agy_brain,
    )

    session_metrics = None
    if agent == "claude" and claude_sessions:
        session_metrics = summarize_claude_session(
            claude_sessions,
            session_id=job_data.get("session"),
            worktree=job_data.get("worktree"),
            start_s=taken,
            end_s=end_s,
        )
    elif agent == "gemini" and agy_brain:
        probe = {
            "job": jid,
            "agent": "gemini",
            "session": job_data.get("session"),
            "worktree": job_data.get("worktree"),
            "taken": taken,
            "done": end_s,
        }
        tpath, _ = discover_transcript(probe, agy_brain=agy_brain)
        if tpath:
            session_metrics = summarize_agy_session(tpath, start_s=taken, end_s=end_s)

    handoff_text = read_handoff_text(repo, jid, job_data.get("handoff"), archive_index)
    brief_meta = parse_brief_meta(handoff_text)
    diff_meta = git_diff_stats(repo, job_data.get("commit"))

    return {
        "ts": time.time(),
        "event": event,
        "job": jid,
        "agent": agent,
        "model": (session_metrics or {}).get("model"),
        "session": job_data.get("session"),
        "state": job_data.get("state"),
        "taken": taken,
        "done": done,
        "merged": merged,
        "duration_s": duration_s,
        "review_s": review_s,
        "returned": bool(job_data.get("returned")),
        "had_question": bool(job_data.get("question")),
        "concurrency": mode,
        "overlaps": overlaps,
        "quota_deltas": quota_deltas,
        "quota_samples": quota_samples,
        "session_metrics": session_metrics,
        "brief": brief_meta,
        "diff": diff_meta,
        "handoff": job_data.get("handoff"),
        "worktree": job_data.get("worktree"),
        "commit": job_data.get("commit"),
    }


def latest_records_by_job(ledger_path):
    """Read ledger JSONL and return {jid: latest_record} sorted by taken timestamp."""
    by_job = {}
    for r in load_jsonl(ledger_path):
        jid = r.get("job")
        if not jid:
            continue
        prev = by_job.get(jid)
        if prev is None or (r.get("ts") or 0) >= (prev.get("ts") or 0):
            by_job[jid] = r
    return dict(sorted(by_job.items(), key=lambda kv: (kv[1].get("taken") or 0, kv[0])))


# ---- Transcript "Holes" Analyzer ----

def discover_transcript(record, agy_brain=None):
    """Best-effort discovery of a Claude Code or AGY transcript file for a job record."""
    sm = record.get("session_metrics") or {}
    agent = (record.get("agent") or "").lower()
    if sm.get("transcript_path"):
        try:
            if os.path.isfile(sm["transcript_path"]):
                return sm["transcript_path"], ("agy" if agent == "gemini" else "claude")
        except OSError:
            pass

    sid = record.get("session")
    home = os.path.expanduser("~")

    if agent == "claude" and sid:
        claude_projects = os.path.join(home, ".claude", "projects")
        try:
            if os.path.isdir(claude_projects):
                for dirpath, _, filenames in os.walk(claude_projects):
                    target = f"{sid}.jsonl"
                    if target in filenames:
                        return os.path.join(dirpath, target), "claude"
        except OSError:
            pass

    if agent == "gemini":
        brain = agy_brain if agy_brain is not None else DEFAULT_AGY_BRAIN
        if not brain:
            return None, None
        # 1. Direct UUID match
        if sid:
            direct = os.path.join(brain, sid, ".system_generated", "logs", "transcript.jsonl")
            try:
                if os.path.isfile(direct):
                    return direct, "agy"
            except OSError:
                return None, None
        # 2. Scan recent AGY transcripts filtered by mtime near [taken, done]
        taken = record.get("taken")
        done = record.get("done") or record.get("merged") or taken
        min_mt = (taken - 3600) if taken else None
        max_mt = (done + 86400 * 2) if done else None
        candidates = list_agy_transcripts(brain, min_mtime=min_mt, max_mtime=max_mt, max_files=200)
        if not candidates and taken:
            candidates = list_agy_transcripts(brain, max_files=200)

        jid = (record.get("job") or "").strip()
        worktree = (record.get("worktree") or "").strip()
        best_score = 0
        best_path = None
        for _, _, tpath in candidates:
            try:
                with open(tpath, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            score = 0
            if sid and (f"--session {sid}" in text or sid in text):
                score += 10
            if worktree and worktree in text:
                score += 6
            if jid:
                jl = jid.lower()
                ju = jid.upper()
                if f"fretchup-jobs/{jl}" in text or f"fretchup-jobs/{ju}" in text:
                    score += 5
                elif (ju in text or jl in text) and ("job.py take" in text or "job.py done" in text):
                    score += 3
            if score > best_score:
                best_score = score
                best_path = tpath
                if score >= 10:
                    break
        if best_path:
            return best_path, "agy"

    return None, None


def _extract_tool_target(tinput):
    if not isinstance(tinput, dict):
        return ""
    for key in (
        "file_path",
        "path",
        "Path",
        "TargetFile",
        "AbsolutePath",
        "command",
        "CommandLine",
        "pattern",
        "Query",
        "SearchPath",
        "DirectoryPath",
    ):
        val = tinput.get(key)
        if val:
            s = str(val)
            return s[:87] + "..." if len(s) > 90 else s
    return ""


def analyze_transcript(path):
    """Analyze a Claude Code or AGY JSONL transcript for token sinks and repeated reads."""
    rows = load_jsonl(path)
    if not rows:
        return {"error": f"No readable JSONL entries in {path}"}

    input_toks = 0
    output_toks = 0
    cache_read = 0
    cache_create = 0
    turns = 0
    ctx_curve = []

    tool_uses = {}  # Claude: tool_use_id -> (name, target)
    pending_agy_tools = collections.deque()  # AGY: FIFO of (name, target)
    tool_outputs = []  # (chars, tool_name, target)
    file_reads = collections.Counter()
    file_read_chars = collections.Counter()

    for row in rows:
        rtype = row.get("type")

        # AGY format: PLANNER_RESPONSE + GENERIC rows
        if rtype == "USER_INPUT":
            pending_agy_tools.clear()
            continue
        if rtype == "PLANNER_RESPONSE":
            inp = int(row.get("input_tokens") or 0)
            out = int(row.get("output_tokens") or 0)
            cr = int(row.get("cache_read_tokens") or 0)
            if inp or out or cr:
                turns += 1
                input_toks += inp
                output_toks += out
                cache_read += cr
                ctx_curve.append(inp + cr)
            for tc in row.get("tool_calls") or []:
                if not isinstance(tc, dict):
                    continue
                tname = tc.get("name") or "tool"
                target = _extract_tool_target(tc.get("args"))
                pending_agy_tools.append((tname, target))
                if tname.lower() in ("read", "read_file", "view_file") and target:
                    file_reads[target] += 1
            continue
        if rtype == "GENERIC":
            rc = row.get("content")
            chars = len(rc) if isinstance(rc, str) else len(json.dumps(rc))
            tname, target = pending_agy_tools.popleft() if pending_agy_tools else ("tool_output", "")
            tool_outputs.append((chars, tname, target))
            if tname.lower() in ("read", "read_file", "view_file") and target:
                file_read_chars[target] += chars
            continue

        # Claude Code format: message.usage + tool_use/tool_result content blocks
        msg = row.get("message") if isinstance(row.get("message"), dict) else row
        usage = msg.get("usage") or row.get("usage")
        if isinstance(usage, dict):
            inp = int(usage.get("input_tokens") or 0)
            out = int(usage.get("output_tokens") or 0)
            cr = int(usage.get("cache_read_input_tokens") or 0)
            cc = int(usage.get("cache_creation_input_tokens") or 0)
            if inp or out or cr or cc:
                turns += 1
                input_toks += inp
                output_toks += out
                cache_read += cr
                cache_create += cc
                ctx_curve.append(inp + cr + cc)

        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "tool_use":
                    tid = block.get("id")
                    tname = block.get("name") or "tool"
                    target = _extract_tool_target(block.get("input"))
                    if tid:
                        tool_uses[tid] = (tname, target)
                    if tname.lower() in ("read", "read_file", "view_file") and target:
                        file_reads[target] += 1
                elif btype == "tool_result":
                    tid = block.get("tool_use_id")
                    tname, target = tool_uses.get(tid, ("tool_result", ""))
                    rc = block.get("content")
                    chars = len(rc) if isinstance(rc, str) else len(json.dumps(rc))
                    tool_outputs.append((chars, tname, target))
                    if tname.lower() in ("read", "read_file", "view_file") and target:
                        file_read_chars[target] += chars

    tool_outputs.sort(reverse=True)
    repeated_reads = [
        (fp, count, file_read_chars[fp])
        for fp, count in file_reads.most_common()
        if count >= 2
    ]

    total_prompt = input_toks + cache_read + cache_create
    cache_hit_pct = (cache_read / total_prompt * 100.0) if total_prompt > 0 else None

    flags = []
    for fp, count, chars in repeated_reads[:5]:
        flags.append(f"Re-read {os.path.basename(fp)} {count}x (~{fmt_tokens(chars // 4)} est tokens)")
    for chars, tname, target in tool_outputs[:3]:
        est_tok = chars // 4
        if est_tok >= 4000:
            flags.append(f"Large {tname} output (~{fmt_tokens(est_tok)} est tokens): {target or '(no target)'}")
    if cache_hit_pct is not None and cache_hit_pct < 60.0 and turns >= 5:
        flags.append(f"Low cache hit rate ({cache_hit_pct:.1f}%) across {turns} turns — check prompt churn")

    return {
        "path": path,
        "turns": turns,
        "input_tokens": input_toks,
        "output_tokens": output_toks,
        "cache_read_tokens": cache_read,
        "cache_create_tokens": cache_create,
        "cache_hit_pct": round(cache_hit_pct, 1) if cache_hit_pct is not None else None,
        "ctx_start": ctx_curve[0] if ctx_curve else None,
        "ctx_median": int(statistics.median(ctx_curve)) if ctx_curve else None,
        "ctx_peak": max(ctx_curve) if ctx_curve else None,
        "top_tool_outputs": [
            {"chars": c, "est_tokens": c // 4, "tool": n, "target": t}
            for c, n, t in tool_outputs[:10]
        ],
        "repeated_reads": [
            {"file": fp, "count": cnt, "est_tokens": ch // 4}
            for fp, cnt, ch in repeated_reads[:10]
        ],
        "flags": flags,
    }


# ---- Integrator Orientation & Calibration ----

def parse_agy_orient(path, conv_id=None):
    """Detect integrator orientation on ANY USER_INPUT turn of an AGY transcript."""
    rows = load_jsonl(path)
    if not rows:
        return None

    turns = []  # list of {"user": row, "planners": [row, ...]}
    current = None
    for row in rows:
        rtype = row.get("type")
        if rtype == "USER_INPUT":
            current = {"user": row, "planners": []}
            turns.append(current)
        elif rtype == "PLANNER_RESPONSE":
            if current is None:
                current = {"user": None, "planners": []}
                turns.append(current)
            current["planners"].append(row)

    orient_idx = None
    for idx, turn in enumerate(turns):
        user_txt = str((turn["user"] or {}).get("content") or "")
        tools_txt = " ".join(_extract_agy_tool_strings(p) for p in turn["planners"])
        if (
            "--role integrator" in tools_txt
            or "integrator.py take" in tools_txt
            or "docs/integrator.md" in tools_txt
            or "integrator" in user_txt.lower()
        ):
            orient_idx = idx
            break

    if orient_idx is None:
        return None

    oturn = turns[orient_idx]
    planners = oturn["planners"]
    if not planners:
        return None

    session_name = None
    for p in planners:
        tstr = _extract_agy_tool_strings(p)
        if "integrator.py take" in tstr:
            m = re.search(r"(gemini-[a-z0-9-]+)", tstr)
            if m:
                session_name = m.group(1)
                break
    if not session_name:
        for turn in turns[orient_idx:]:
            for p in turn["planners"]:
                tstr = _extract_agy_tool_strings(p)
                if "integrator.py take" in tstr:
                    m = re.search(r"(gemini-[a-z0-9-]+)", tstr)
                    if m:
                        session_name = m.group(1)
                        break
            if session_name:
                break

    inp = sum(int(r.get("input_tokens") or 0) for r in planners)
    cache = sum(int(r.get("cache_read_tokens") or 0) for r in planners)
    out = sum(int(r.get("output_tokens") or 0) for r in planners)
    peak_ctx = max((int(r.get("input_tokens") or 0) + int(r.get("cache_read_tokens") or 0)) for r in planners)
    model = next((r.get("model") for r in planners if r.get("model")), None)

    warmup_turns = orient_idx
    warmup_tokens = 0
    for wt in turns[:orient_idx]:
        for p in wt["planners"]:
            warmup_tokens += (
                int(p.get("input_tokens") or 0)
                + int(p.get("cache_read_tokens") or 0)
                + int(p.get("output_tokens") or 0)
            )

    user_row = oturn["user"] or {}
    ts_str = user_row.get("created_at") or planners[0].get("created_at") or ""
    start_s = parse_iso_ts(ts_str) or parse_iso_ts(planners[0].get("created_at"))
    end_s = parse_iso_ts(planners[-1].get("created_at")) or start_s
    next_event_s = None
    if orient_idx + 1 < len(turns):
        nxt_user = turns[orient_idx + 1]["user"] or {}
        nxt_planners = turns[orient_idx + 1]["planners"]
        next_event_s = parse_iso_ts(nxt_user.get("created_at")) or (
            parse_iso_ts(nxt_planners[0].get("created_at")) if nxt_planners else None
        )

    user_content = str(user_row.get("content") or "")
    snippet = user_content.split("<USER_REQUEST>")[-1].split("</USER_REQUEST>")[0].strip()
    snippet = re.sub(r"\s+", " ", snippet)[:80]

    if not conv_id:
        parts = os.path.normpath(path).split(os.sep)
        conv_id = parts[-4] if len(parts) >= 4 else os.path.basename(path)

    return {
        "agent": "gemini",
        "conv_id": conv_id,
        "path": path,
        "ts": ts_str,
        "start_s": start_s,
        "end_s": end_s,
        "next_event_s": next_event_s,
        "session": session_name or conv_id[:8],
        "model": model,
        "model_display": human_model_name(model),
        "turn_index": orient_idx + 1,
        "warmup_turns": warmup_turns,
        "warmup_tokens": warmup_tokens,
        "prompt": snippet,
        "planner_calls": len(planners),
        "input_tokens": inp,
        "cache_read_tokens": cache,
        "total_prompt_tokens": inp + cache,
        "output_tokens": out,
        "peak_context": peak_ctx,
        "weighted_tokens": weighted_tokens(inp, cache, out),
    }


def collect_orientations(
    repo,
    claude_dir,
    agy_dir,
    agy_brain,
    last=7,
    days=None,
    agent_filter=None,
    quota_history=None,
    all_jobs=None,
):
    """Collect recent integrator orientations (AGY + Claude) with measured/estimated 5h burn."""
    if quota_history is None:
        quota_history = load_quota_history(claude_dir, agy_dir)
    if all_jobs is None:
        st = load_json(jobs_state_path(repo), {})
        all_jobs = st.get("jobs", {})

    min_mtime = (time.time() - days * 86400.0) if days else None
    rows = []

    if agent_filter in (None, "gemini") and agy_brain:
        # Sort by mtime desc; stop once we have plenty of integrator sessions to slice by timestamp
        target_hits = max(last * 2, 16) if last else None
        for _, conv_id, path in list_agy_transcripts(agy_brain, min_mtime=min_mtime):
            rec = parse_agy_orient(path, conv_id=conv_id)
            if rec:
                rows.append(rec)
                if target_hits and len(rows) >= target_hits:
                    break

    if agent_filter in (None, "claude") and claude_dir:
        csessions = load_claude_sessions(claude_dir)
        by_sid = collections.defaultdict(list)
        for r in csessions:
            role, _ = classify_claude_role(r, repo)
            if role == "integrator":
                sid = r.get("session_id") or f"claude-{int(r['_ts'])}"
                by_sid[sid].append(r)
        for sid, srows in by_sid.items():
            srows.sort(key=lambda x: x["_ts"])
            first = srows[0]
            if min_mtime and first["_ts"] < min_mtime:
                continue
            inp = int(first.get("total_input_tokens") or 0)
            out = int(first.get("total_output_tokens") or 0)
            model = first.get("model")
            ts_str = datetime.datetime.fromtimestamp(first["_ts"], tz=datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            nxt = srows[1]["_ts"] if len(srows) > 1 else None
            rows.append({
                "agent": "claude",
                "conv_id": sid,
                "path": first.get("transcript_path") or "",
                "ts": ts_str,
                "start_s": first["_ts"] - 30.0,
                "end_s": first["_ts"],
                "next_event_s": nxt,
                "session": sid[:12],
                "model": model,
                "model_display": human_model_name(model),
                "turn_index": 1,
                "warmup_turns": 0,
                "warmup_tokens": 0,
                "prompt": "(claude integrator)",
                "planner_calls": 1,
                "input_tokens": inp,
                "cache_read_tokens": 0,
                "total_prompt_tokens": inp,
                "output_tokens": out,
                "peak_context": inp,
                "weighted_tokens": weighted_tokens(inp, 0, out),
            })

    rows.sort(key=lambda r: (r.get("start_s") or 0.0, r.get("ts") or ""))

    # Attach measured 5h quota delta + concurrency check
    for r in rows:
        agent = r["agent"]
        bkey = PROVIDER_BUCKETS[agent][0]
        samples = quota_history.get(agent, [])
        meas, n = compute_bucket_burn(
            samples,
            bkey,
            r.get("start_s"),
            r.get("end_s"),
            pad_before=120.0,
            pad_after=45.0,
            next_event_s=r.get("next_event_s"),
        )
        r["meas_5h"] = meas
        r["quota_samples"] = n
        # Check if any worker job of the same provider overlapped [start_s, end_s]
        mode, overlaps = detect_concurrency(
            all_jobs, "__orient__", agent, r.get("start_s"), r.get("end_s")
        )
        r["concurrency"] = mode
        r["overlaps"] = overlaps

    # Calibrate ~% per 100k weighted tokens per model from solo measured runs
    rates = calibrate_model_rates(rows, [])
    for r in rows:
        mkey = r.get("model") or r["agent"]
        rate = rates.get(mkey)
        if rate and r.get("weighted_tokens"):
            r["est_5h"] = round(rate * (r["weighted_tokens"] / 100_000.0), 6)
        else:
            r["est_5h"] = None

    if last:
        rows = rows[-last:]
    return rows, rates


def calibrate_model_rates(orient_rows, job_records):
    """Return {model_key: median_5h_frac_per_100k_weighted_tokens} from solo measured samples."""
    by_model = collections.defaultdict(list)
    for r in orient_rows:
        if r.get("concurrency") == "solo" and r.get("meas_5h") and r["meas_5h"] > 0 and r.get("weighted_tokens", 0) > 0:
            mkey = r.get("model") or r.get("agent")
            by_model[mkey].append(r["meas_5h"] / (r["weighted_tokens"] / 100_000.0))
    for r in job_records:
        if r.get("concurrency") != "solo":
            continue
        q5, _ = primary_quota(r)
        sm = r.get("session_metrics") or {}
        if not q5 or q5 <= 0 or not sm:
            continue
        wt = weighted_tokens(sm.get("input_tokens"), sm.get("cache_read_tokens"), sm.get("output_tokens"))
        if wt > 0:
            mkey = r.get("model") or sm.get("model") or r.get("agent")
            by_model[mkey].append(q5 / (wt / 100_000.0))
    return {k: statistics.median(v) for k, v in by_model.items() if v}


# ---- CLI Commands ----

def cmd_snapshot(args):
    """Passive lifecycle hook (called by job.py / integrate.py)."""
    try:
        st = load_json(jobs_state_path(args.repo), {})
        all_jobs = st.get("jobs", {})
        jid = args.job.upper()
        job_data = dict(all_jobs.get(jid, {}))
        if args.agent:
            job_data["agent"] = args.agent
        if args.session:
            job_data["session"] = args.session
        if not job_data.get("taken"):
            job_data["taken"] = time.time()
        if args.event == "done" and not job_data.get("done"):
            job_data["done"] = time.time()
        if args.event == "merge" and not job_data.get("merged"):
            job_data["merged"] = time.time()

        quota_history = load_quota_history(args.claude_dir, args.agy_dir)
        claude_sessions = load_claude_sessions(args.claude_dir)
        archive_index = load_archive_index(args.repo)
        rec = build_job_record(
            jid,
            job_data,
            all_jobs,
            args.repo,
            quota_history,
            claude_sessions,
            archive_index=archive_index,
            event=args.event,
            agy_brain=args.agy_brain,
        )
        append_jsonl(args.ledger, rec)
        if not args.quiet:
            q_str = ", ".join(f"{k} -{fmt_pct(v)}" for k, v in rec["quota_deltas"].items()) or "no quota sample"
            sm = rec.get("session_metrics") or {}
            tok_str = ""
            if sm.get("input_tokens") is not None or sm.get("output_tokens") is not None:
                in_tot = (sm.get("input_tokens") or 0) + (sm.get("cache_read_tokens") or 0)
                out_tot = sm.get("output_tokens") or 0
                tok_str = f" | {fmt_tokens(in_tot)} in / {fmt_tokens(out_tot)} out"
            print(f"[usage] {jid} ({args.event}, {rec['agent']}, {rec['concurrency']}): {q_str}{tok_str}")
    except Exception as exc:
        if args.strict:
            raise
        if not args.quiet:
            print(f"[usage] warning (non-fatal): {exc}", file=sys.stderr)
    return 0


def cmd_backfill(args):
    """Correlate all historical jobs in shopsketch-jobs.json with existing monitor logs."""
    st = load_json(jobs_state_path(args.repo), {})
    all_jobs = st.get("jobs", {})
    if not all_jobs:
        print(f"No jobs found in {jobs_state_path(args.repo)}", file=sys.stderr)
        return 1

    quota_history = load_quota_history(args.claude_dir, args.agy_dir)
    claude_sessions = load_claude_sessions(args.claude_dir)
    agy_sessions = load_agy_sessions(args.agy_brain)
    archive_index = load_archive_index(args.repo)

    existing = latest_records_by_job(args.ledger) if not args.rebuild else {}
    records = []
    skipped = 0
    for jid, jdata in sorted(all_jobs.items(), key=lambda kv: (kv[1].get("taken") or 0, kv[0])):
        agent = (jdata.get("agent") or "").lower()
        if not args.all_agents and agent not in TRACKED_AGENTS:
            skipped += 1
            continue
        if not args.rebuild and jid in existing and existing[jid].get("event") in ("merge", "done"):
            continue
        rec = build_job_record(
            jid,
            jdata,
            all_jobs,
            args.repo,
            quota_history,
            claude_sessions,
            archive_index=archive_index,
            event="backfill",
            agy_brain=args.agy_brain,
            agy_sessions=agy_sessions,
        )
        records.append(rec)

    if args.rebuild:
        os.makedirs(os.path.dirname(os.path.abspath(args.ledger)), exist_ok=True)
        with open(args.ledger, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, sort_keys=True) + "\n")
    else:
        for rec in records:
            append_jsonl(args.ledger, rec)

    with_quota = sum(1 for r in records if r["quota_deltas"])
    with_tokens = sum(1 for r in records if r["session_metrics"])
    print(
        f"Backfilled {len(records)} jobs into {args.ledger} "
        f"({with_quota} with quota deltas, {with_tokens} with exact session tokens; "
        f"{skipped} non-Claude/Gemini skipped)."
    )
    return 0


def format_table(headers, rows, alignments=None):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    aligns = alignments or ["<"] * len(headers)

    def fmt_row(vals):
        return "  ".join(f"{str(v):{aligns[i]}{widths[i]}}" for i, v in enumerate(vals))

    lines = [fmt_row(headers), "  ".join("-" * w for w in widths)]
    for row in rows:
        lines.append(fmt_row(row))
    return "\n".join(lines)


def primary_quota(rec):
    qd = rec.get("quota_deltas") or {}
    if rec.get("agent") == "claude":
        return qd.get("claude-5h"), qd.get("claude-7d")
    if rec.get("agent") == "gemini":
        return qd.get("gemini-5h"), qd.get("gemini-weekly")
    return None, None


def _session_total_tokens(sm):
    if not sm:
        return None
    if sm.get("input_tokens") is None and sm.get("output_tokens") is None and sm.get("cache_read_tokens") is None:
        return None
    return (sm.get("input_tokens") or 0) + (sm.get("cache_read_tokens") or 0) + (sm.get("output_tokens") or 0)


def _session_peak_ctx_str(sm):
    if not sm:
        return "-"
    if sm.get("peak_context_pct") is not None:
        return f"{sm['peak_context_pct']:.0f}%"
    if sm.get("peak_context") is not None:
        return fmt_tokens(sm["peak_context"])
    return "-"


def cmd_report(args):
    records = list(latest_records_by_job(args.ledger).values())
    if not records:
        print(f"No records in {args.ledger}. Run `tools/usage.py backfill` first.")
        return 0

    if args.agent:
        records = [r for r in records if r.get("agent") == args.agent.lower()]
    if args.solo:
        records = [r for r in records if r.get("concurrency") == "solo"]
    if args.only_measured:
        records = [r for r in records if r.get("quota_deltas") or r.get("session_metrics")]
    if args.last:
        records = records[-args.last :]

    if args.json:
        print(json.dumps(records, indent=2))
        return 0

    headers = ["Job", "Agent", "Mode", "Dur", "5h Δ", "7d/Wk Δ", "Tokens", "Peak Ctx", "Brief", "Diff", "Ret"]
    aligns = ["<", "<", "<", ">", ">", ">", ">", ">", ">", ">", ">"]
    rows = []
    for r in records:
        q5, q7 = primary_quota(r)
        sm = r.get("session_metrics") or {}
        toks = _session_total_tokens(sm)
        brief = r.get("brief") or {}
        diff = r.get("diff") or {}
        brief_s = f"{brief.get('brief_words', 0)}w" if brief else "-"
        if brief.get("has_reading_path"):
            brief_s += "*"
        diff_s = f"+{diff.get('insertions', 0)}/-{diff.get('deletions', 0)}" if diff else "-"
        rows.append([
            r["job"],
            r.get("agent", "?"),
            r.get("concurrency", "?"),
            fmt_dur(r.get("duration_s")),
            fmt_pct(q5),
            fmt_pct(q7),
            fmt_tokens(toks),
            _session_peak_ctx_str(sm),
            brief_s,
            diff_s,
            "yes" if r.get("returned") else "",
        ])

    print(format_table(headers, rows, aligns))
    print("\nNotes: Brief `*` = includes Reading path. Mode `solo` = clean window (no same-provider overlap).")
    return 0


def cmd_overhead(args):
    """Compare Worker vs. Integrator token usage for both Claude and Gemini."""
    printed_any = False

    # 1. Claude (sessions.jsonl)
    sessions = load_claude_sessions(args.claude_dir)
    if sessions:
        printed_any = True
        by_sid = collections.defaultdict(list)
        for r in sessions:
            sid = r.get("session_id") or f"anon-{r.get('cwd')}"
            by_sid[sid].append(r)

        totals = collections.defaultdict(
            lambda: {"sessions": 0, "turns": 0, "in": 0, "out": 0, "usd": 0.0, "peak_ctx": []}
        )
        for _, srows in by_sid.items():
            role, _ = classify_claude_role(srows[-1], args.repo)
            t = totals[role]
            t["sessions"] += 1
            t["turns"] += len(srows)
            ins = [r["total_input_tokens"] for r in srows if isinstance(r.get("total_input_tokens"), (int, float))]
            outs = [r["total_output_tokens"] for r in srows if isinstance(r.get("total_output_tokens"), (int, float))]
            usds = [r["cost_usd"] for r in srows if isinstance(r.get("cost_usd"), (int, float))]
            ctxs = [r["context_used_pct"] for r in srows if isinstance(r.get("context_used_pct"), (int, float))]
            if ins:
                t["in"] += max(ins)
            if outs:
                t["out"] += max(outs)
            if usds:
                t["usd"] += max(usds)
            if ctxs:
                t["peak_ctx"].append(max(ctxs))

        print("=== Claude Overhead (sessions.jsonl) ===")
        headers = ["Role", "Sessions", "Turns", "Input", "Output", "Cost", "Med Peak Ctx"]
        aligns = ["<", ">", ">", ">", ">", ">", ">"]
        rows = []
        grand_toks = sum(v["in"] + v["out"] for v in totals.values())
        for role in ("worker", "integrator", "other", "unknown"):
            if role not in totals:
                continue
            v = totals[role]
            med_ctx = f"{statistics.median(v['peak_ctx']):.0f}%" if v["peak_ctx"] else "-"
            rows.append([
                role,
                v["sessions"],
                v["turns"],
                fmt_tokens(v["in"]),
                fmt_tokens(v["out"]),
                fmt_usd(v["usd"]) if v["usd"] > 0 else "-",
                med_ctx,
            ])
        print(format_table(headers, rows, aligns))
        if grand_toks > 0 and "integrator" in totals:
            int_toks = totals["integrator"]["in"] + totals["integrator"]["out"]
            print(f"Integrator share of tracked Claude tokens: {int_toks / grand_toks * 100:.1f}%")

    # 2. Gemini (AGY brain transcripts)
    agy_sessions = load_agy_sessions(args.agy_brain)
    if agy_sessions:
        if printed_any:
            print()
        printed_any = True
        gtotals = collections.defaultdict(
            lambda: {"sessions": 0, "turns": 0, "in": 0, "cache": 0, "out": 0, "peak_ctx": []}
        )
        for s in agy_sessions:
            t = gtotals[s["role"]]
            t["sessions"] += 1
            t["turns"] += s["turns"]
            t["in"] += s["input_tokens"]
            t["cache"] += s["cache_read_tokens"]
            t["out"] += s["output_tokens"]
            if s["peak_context"]:
                t["peak_ctx"].append(s["peak_context"])

        print("=== Gemini Overhead (AGY transcripts) ===")
        headers = ["Role", "Sessions", "Turns", "Fresh In", "Cache", "Output", "Med Peak Ctx"]
        aligns = ["<", ">", ">", ">", ">", ">", ">"]
        rows = []
        grand_toks = sum(v["in"] + v["cache"] + v["out"] for v in gtotals.values())
        for role in ("worker", "integrator", "other"):
            if role not in gtotals:
                continue
            v = gtotals[role]
            med_ctx = fmt_tokens(int(statistics.median(v["peak_ctx"]))) if v["peak_ctx"] else "-"
            rows.append([
                role,
                v["sessions"],
                v["turns"],
                fmt_tokens(v["in"]),
                fmt_tokens(v["cache"]),
                fmt_tokens(v["out"]),
                med_ctx,
            ])
        print(format_table(headers, rows, aligns))
        if grand_toks > 0 and "integrator" in gtotals:
            v = gtotals["integrator"]
            int_toks = v["in"] + v["cache"] + v["out"]
            print(f"Integrator share of tracked Gemini tokens: {int_toks / grand_toks * 100:.1f}%")

    if not printed_any:
        print(
            f"No readable Claude sessions ({args.claude_dir}) or AGY transcripts ({args.agy_brain}). "
            "Run outside sandbox or pass --claude-dir / --agy-brain."
        )
    return 0


def cmd_compare(args):
    """Compare Claude vs. Gemini on solo jobs, plus brief-trait correlations."""
    records = list(latest_records_by_job(args.ledger).values())
    if not records:
        print(f"No records in {args.ledger}. Run `tools/usage.py backfill` first.")
        return 0

    print("=== Claude vs. Gemini (Solo Jobs with Quota Data) ===")
    headers = ["Agent", "Jobs", "Med Dur", "Med 5h Δ", "Max 5h Δ", "Med Wk Δ", "Returned%"]
    aligns = ["<", ">", ">", ">", ">", ">", ">"]
    rows = []
    for agent in TRACKED_AGENTS:
        subset = [
            r for r in records
            if r.get("agent") == agent and r.get("concurrency") == "solo" and r.get("quota_deltas")
        ]
        if not subset:
            rows.append([agent, 0, "-", "-", "-", "-", "-"])
            continue
        durs = [r["duration_s"] for r in subset if r.get("duration_s") is not None]
        q5s = [primary_quota(r)[0] for r in subset if primary_quota(r)[0] is not None]
        q7s = [primary_quota(r)[1] for r in subset if primary_quota(r)[1] is not None]
        ret_pct = sum(1 for r in subset if r.get("returned")) / len(subset) * 100.0
        rows.append([
            agent,
            len(subset),
            fmt_dur(statistics.median(durs)) if durs else "-",
            fmt_pct(statistics.median(q5s)) if q5s else "-",
            fmt_pct(max(q5s)) if q5s else "-",
            fmt_pct(statistics.median(q7s)) if q7s else "-",
            f"{ret_pct:.0f}%",
        ])
    print(format_table(headers, rows, aligns))

    measured_solo = [r for r in records if r.get("concurrency") == "solo" and r.get("quota_deltas") and r.get("brief")]
    if measured_solo:
        print("\n=== Brief Traits vs. 5h Quota Burn (Solo Jobs) ===")
        b_headers = ["Slice", "Jobs", "Med Dur", "Med 5h Δ", "Med Brief Words", "Med Touches"]
        b_aligns = ["<", ">", ">", ">", ">", ">"]
        slices = [
            ("Has Reading path", [r for r in measured_solo if r["brief"].get("has_reading_path")]),
            ("No Reading path", [r for r in measured_solo if not r["brief"].get("has_reading_path")]),
            ("Brief <= 400w", [r for r in measured_solo if r["brief"].get("brief_words", 0) <= 400]),
            ("Brief > 400w", [r for r in measured_solo if r["brief"].get("brief_words", 0) > 400]),
            ("Returned (rework)", [r for r in measured_solo if r.get("returned")]),
            ("Clean first pass", [r for r in measured_solo if not r.get("returned")]),
        ]
        b_rows = []
        for label, sub in slices:
            if not sub:
                continue
            durs = [r["duration_s"] for r in sub if r.get("duration_s") is not None]
            q5s = [primary_quota(r)[0] for r in sub if primary_quota(r)[0] is not None]
            bws = [r["brief"].get("brief_words", 0) for r in sub]
            tcs = [r["brief"].get("touches_count", 0) for r in sub]
            b_rows.append([
                label,
                len(sub),
                fmt_dur(statistics.median(durs)) if durs else "-",
                fmt_pct(statistics.median(q5s)) if q5s else "-",
                int(statistics.median(bws)),
                int(statistics.median(tcs)),
            ])
        print(format_table(b_headers, b_rows, b_aligns))
    return 0


def cmd_holes(args):
    """Inspect a job's transcript (or an explicit JSONL transcript) for token sinks."""
    tpath = args.transcript
    label = tpath or ""
    if not tpath:
        if not args.job:
            print("Provide a job ID (e.g. `holes H109`) or `--transcript <path>`.", file=sys.stderr)
            return 1
        records = latest_records_by_job(args.ledger)
        rec = records.get(args.job.upper())
        if not rec:
            print(f"Job {args.job.upper()} not found in {args.ledger}. Run `backfill` first.", file=sys.stderr)
            return 1
        tpath, kind = discover_transcript(rec, agy_brain=args.agy_brain)
        label = f"{args.job.upper()} ({rec.get('agent')}, {kind or 'unknown'})"
        if not tpath:
            print(
                f"No transcript found for {label}.\n"
                "Tip: pass `--transcript /path/to/transcript.jsonl`, or run outside sandbox so "
                f"{args.agy_brain} / ~/.claude/projects are readable."
            )
            return 1

    res = analyze_transcript(tpath)
    if "error" in res:
        print(res["error"], file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(res, indent=2))
        return 0

    print(f"=== Token Holes: {label} ===")
    print(f"Transcript: {res['path']}")
    print(
        f"Turns: {res['turns']} | Input: {fmt_tokens(res['input_tokens'])} | "
        f"Output: {fmt_tokens(res['output_tokens'])} | "
        f"Cache read: {fmt_tokens(res['cache_read_tokens'])} | "
        f"Cache create: {fmt_tokens(res['cache_create_tokens'])} | "
        f"Cache hit: {res['cache_hit_pct']}%"
    )
    if res["ctx_peak"] is not None:
        print(
            f"Context curve: start {fmt_tokens(res['ctx_start'])} -> "
            f"median {fmt_tokens(res['ctx_median'])} -> peak {fmt_tokens(res['ctx_peak'])}"
        )

    if res["flags"]:
        print("\nFlags:")
        for f in res["flags"]:
            print(f"  - {f}")

    if res["top_tool_outputs"]:
        print("\nTop Tool Outputs:")
        rows = [
            [fmt_tokens(x["est_tokens"]), x["tool"], x["target"] or "-"]
            for x in res["top_tool_outputs"][:8]
        ]
        print(format_table(["Est Tok", "Tool", "Target"], rows, [">", "<", "<"]))

    if res["repeated_reads"]:
        print("\nRepeated File Reads:")
        rows = [
            [x["count"], fmt_tokens(x["est_tokens"]), x["file"]]
            for x in res["repeated_reads"][:8]
        ]
        print(format_table(["Reads", "Est Tok", "File"], rows, [">", ">", "<"]))

    return 0


def cmd_orient(args):
    """Benchmark integrator orientation turns across recent AGY and Claude sessions."""
    rows, rates = collect_orientations(
        args.repo,
        args.claude_dir,
        args.agy_dir,
        args.agy_brain,
        last=args.last,
        days=args.days,
        agent_filter=args.agent,
    )
    if args.json:
        print(json.dumps({"orientations": rows, "calibration": rates}, indent=2))
        return 0

    if not rows:
        print(
            f"No integrator orientations found (agy-brain={args.agy_brain}, claude-dir={args.claude_dir}). "
            "If running inside a sandbox, re-run outside sandbox or pass --agy-brain."
        )
        return 0

    headers = [
        "Session", "Model", "Turn", "Calls", "Fresh In", "Cache", "Total In",
        "Out", "Peak Ctx", "5h Δ (meas)", "5h Δ (est)", "Mode",
    ]
    aligns = ["<", "<", "<", ">", ">", ">", ">", ">", ">", ">", ">", "<"]
    trows = []
    for r in rows:
        turn_lbl = f"T{r['turn_index']}" + (f" (+{r['warmup_turns']}w)" if r.get("warmup_turns") else "")
        meas_s = fmt_pct(r.get("meas_5h"))
        if r.get("meas_5h") is not None and r.get("concurrency") not in ("solo", "unknown"):
            meas_s += "*"
        trows.append([
            r["session"],
            r["model_display"],
            turn_lbl,
            r["planner_calls"],
            fmt_tokens(r["input_tokens"]),
            fmt_tokens(r["cache_read_tokens"]),
            fmt_tokens(r["total_prompt_tokens"]),
            fmt_tokens(r["output_tokens"]),
            fmt_tokens(r["peak_context"]),
            meas_s,
            fmt_pct(r.get("est_5h")),
            r.get("concurrency", "-"),
        ])
    print(format_table(headers, trows, aligns))
    print("\nNotes: Turn `T2 (+1w)` = integrator started on turn 2 after 1 warm-up turn; `*` on meas = overlapping session.")
    return 0


def cmd_bench(args):
    """Combined worker + integrator orientation benchmark with model quota calibration."""
    quota_history = load_quota_history(args.claude_dir, args.agy_dir)
    st = load_json(jobs_state_path(args.repo), {})
    all_jobs = st.get("jobs", {})

    records = list(latest_records_by_job(args.ledger).values())
    if args.agent:
        records = [r for r in records if r.get("agent") == args.agent.lower()]
    worker_recent = records[-args.last :] if args.last else records

    orient_rows, _ = collect_orientations(
        args.repo,
        args.claude_dir,
        args.agy_dir,
        args.agy_brain,
        last=args.last,
        agent_filter=args.agent,
        quota_history=quota_history,
        all_jobs=all_jobs,
    )
    rates = calibrate_model_rates(orient_rows, records)

    if args.json:
        print(json.dumps({"workers": worker_recent, "orientations": orient_rows, "calibration": rates}, indent=2))
        return 0

    print("=== Recent Worker Jobs ===")
    if worker_recent:
        headers = ["Job", "Agent", "Model", "Mode", "Dur", "5h Δ", "Tokens", "Peak Ctx"]
        aligns = ["<", "<", "<", "<", ">", ">", ">", ">"]
        wrows = []
        for r in worker_recent:
            q5, _ = primary_quota(r)
            sm = r.get("session_metrics") or {}
            wrows.append([
                r["job"],
                r.get("agent", "?"),
                human_model_name(r.get("model") or sm.get("model")),
                r.get("concurrency", "?"),
                fmt_dur(r.get("duration_s")),
                fmt_pct(q5),
                fmt_tokens(_session_total_tokens(sm)),
                _session_peak_ctx_str(sm),
            ])
        print(format_table(headers, wrows, aligns))
    else:
        print(f"No worker records in {args.ledger}. Run `tools/usage.py backfill` first.")

    print("\n=== Recent Integrator Orientations ===")
    if orient_rows:
        headers = ["Session", "Model", "Turn", "Calls", "Total In", "Out", "Peak Ctx", "5h Δ (meas)", "5h Δ (est)", "Mode"]
        aligns = ["<", "<", "<", ">", ">", ">", ">", ">", ">", "<"]
        orows = []
        for r in orient_rows:
            turn_lbl = f"T{r['turn_index']}" + (f" (+{r['warmup_turns']}w)" if r.get("warmup_turns") else "")
            mkey = r.get("model") or r["agent"]
            est = (rates[mkey] * (r["weighted_tokens"] / 100_000.0)) if (mkey in rates and r.get("weighted_tokens")) else r.get("est_5h")
            orows.append([
                r["session"],
                r["model_display"],
                turn_lbl,
                r["planner_calls"],
                fmt_tokens(r["total_prompt_tokens"]),
                fmt_tokens(r["output_tokens"]),
                fmt_tokens(r["peak_context"]),
                fmt_pct(r.get("meas_5h")),
                fmt_pct(est),
                r.get("concurrency", "-"),
            ])
        print(format_table(headers, orows, aligns))
    else:
        print(f"No readable orientations (agy-brain={args.agy_brain}); run outside sandbox or pass --agy-brain.")

    if rates:
        print("\n=== Calibration (Solo Measured Runs) ===")
        for mkey, rate in sorted(rates.items()):
            print(f"  {human_model_name(mkey)}: ~{rate * 100.0:.2f}% 5h quota per 100k weighted tokens")
    return 0


def cmd_export(args):
    """Print a Markdown summary table suitable for pasting into docs/handoffs."""
    records = list(latest_records_by_job(args.ledger).values())
    if args.only_measured:
        records = [r for r in records if r.get("quota_deltas") or r.get("session_metrics")]
    if args.last:
        records = records[-args.last :]

    print("| Job | Agent | Mode | Duration | 5h Δ | Weekly/7d Δ | Tokens | Brief | Diff | Returned |")
    print("|---|---|---|---|---:|---:|---:|---:|---:|---|")
    for r in records:
        q5, q7 = primary_quota(r)
        sm = r.get("session_metrics") or {}
        toks = _session_total_tokens(sm)
        brief = r.get("brief") or {}
        diff = r.get("diff") or {}
        brief_s = f"{brief.get('brief_words', 0)}w" if brief else "-"
        diff_s = f"+{diff.get('insertions', 0)}/-{diff.get('deletions', 0)}" if diff else "-"
        print(
            f"| {r['job']} | {r.get('agent', '?')} | {r.get('concurrency', '?')} | "
            f"{fmt_dur(r.get('duration_s'))} | {fmt_pct(q5)} | {fmt_pct(q7)} | "
            f"{fmt_tokens(toks)} | {brief_s} | {diff_s} | {'yes' if r.get('returned') else ''} |"
        )
    return 0


# ---- CLI Visualizer ----

def make_styler(use_color):
    def c(code, text):
        if not use_color or not code:
            return str(text)
        return f"{ANSI[code]}{text}{ANSI['reset']}"
    return c


def render_bar(value, max_val, width, color_fn, color_name="cyan"):
    if value is None or max_val <= 0 or width <= 0:
        return color_fn("dim", "░" * max(0, width))
    ratio = max(0.0, min(1.0, value / max_val))
    filled = int(round(ratio * width))
    if value > 0 and filled == 0:
        filled = 1
    return color_fn(color_name, "█" * filled) + color_fn("dim", "░" * (width - filled))


def burn_color(q5):
    if q5 is None:
        return "dim"
    pct = q5 * 100.0
    if pct >= 15.0:
        return "red"
    if pct >= 8.0:
        return "yellow"
    return "green"


def render_sparkline(values, color_fn):
    if not values:
        return ""
    vmax = max((v for v in values if v is not None), default=0.0)
    if vmax <= 0:
        return color_fn("dim", "▁" * len(values))
    chars = []
    for v in values:
        if v is None:
            chars.append(color_fn("dim", "·"))
            continue
        idx = int(round((v / vmax) * (len(SPARK_BLOCKS) - 1)))
        idx = max(1, min(len(SPARK_BLOCKS) - 1, idx)) if v > 0 else 0
        chars.append(color_fn(burn_color(v), SPARK_BLOCKS[idx]))
    return "".join(chars)


def render_4row_chart(buckets_vals, color_fn):
    """Render a 4-row Unicode block chart (matching agy-usage / claude-usage style)."""
    rows = 4
    vmax = max(buckets_vals) if buckets_vals else 0.0
    if vmax <= 0:
        return [color_fn("dim", "▁" * len(buckets_vals))]
    lines = []
    for r in range(rows - 1, -1, -1):
        row_chars = []
        lo = r / rows
        hi = (r + 1) / rows
        for v in buckets_vals:
            norm = v / vmax
            if norm <= lo:
                row_chars.append(" ")
            elif norm >= hi:
                row_chars.append(color_fn(burn_color(v), "█"))
            else:
                frac = (norm - lo) / (hi - lo)
                idx = max(1, min(len(SPARK_BLOCKS) - 1, int(round(frac * (len(SPARK_BLOCKS) - 1)))))
                row_chars.append(color_fn(burn_color(v), SPARK_BLOCKS[idx]))
        lines.append("".join(row_chars))
    return lines


def viz_single_job(rec, args, c, term_w):
    """Render a detailed CLI timeline & breakdown for one job."""
    jid = rec["job"]
    agent = rec.get("agent", "?")
    q5, q7 = primary_quota(rec)
    mode = rec.get("concurrency", "?")
    brief = rec.get("brief") or {}
    diff = rec.get("diff") or {}

    rule = c("dim", "─" * min(term_w, 88))
    print(rule)
    print(
        f"{c('bold', jid)}  {c('cyan' if agent == 'gemini' else 'magenta', agent)}  "
        f"{c('green' if mode == 'solo' else 'yellow', mode)}  "
        f"dur {c('bold', fmt_dur(rec.get('duration_s')))}  "
        f"5h {c(burn_color(q5), fmt_pct(q5))}  "
        f"wk {c('white', fmt_pct(q7))}"
    )
    print(
        f"Brief: {brief.get('brief_words', '-')}w | "
        f"Touches: {brief.get('touches_count', '-')} | "
        f"Reading path: {'yes' if brief.get('has_reading_path') else 'no'} | "
        f"Diff: +{diff.get('insertions', 0)}/-{diff.get('deletions', 0)} | "
        f"Returned: {'yes' if rec.get('returned') else 'no'}"
    )
    print(rule)

    taken = rec.get("taken")
    end_s = rec.get("done") or rec.get("taken")
    if agent in TRACKED_AGENTS and taken and end_s and end_s > taken:
        hist = load_quota_history(args.claude_dir, args.agy_dir).get(agent, [])
        bkey = PROVIDER_BUCKETS[agent][0]
        pts = [
            (t, float(b[bkey]))
            for t, b in hist
            if taken - 60 <= t <= end_s + 60 and bkey in b and isinstance(b[bkey], (int, float))
        ]
        nbins = max(16, min(56, term_w - 20))
        span = end_s - taken
        bin_burns = [0.0] * nbins
        for i in range(1, len(pts)):
            t0, v0 = pts[i - 1]
            t1, v1 = pts[i]
            drop = v0 - v1
            if drop > 0.0005 and drop < 0.5:
                mid = max(taken, min(end_s, (t0 + t1) / 2.0))
                bi = min(nbins - 1, max(0, int((mid - taken) / span * nbins)))
                bin_burns[bi] += drop

        if any(v > 0 for v in bin_burns):
            peak = max(bin_burns)
            print(f"{c('bold', '5h Burn Spikes Across Job')}  {c('dim', f'(peak bin {fmt_pct(peak)}, {nbins} bins)')}")
            for line in render_4row_chart(bin_burns, c):
                print("  " + line)
            left_lbl = "0s"
            mid_lbl = fmt_dur(span / 2.0)
            right_lbl = fmt_dur(span)
            gap1 = max(1, nbins // 2 - len(left_lbl) - len(mid_lbl) // 2)
            gap2 = max(1, nbins - len(left_lbl) - gap1 - len(mid_lbl) - len(right_lbl))
            print("  " + c("dim", f"{left_lbl}{' ' * gap1}{mid_lbl}{' ' * gap2}{right_lbl}"))
        else:
            print(c("dim", "No intra-job 5h burn samples recorded in this window."))
    else:
        print(c("dim", "No quota timeline available for this job."))

    sm = rec.get("session_metrics")
    if sm:
        print(
            f"\n{c('bold', f'{agent.title()} Session:')} model={human_model_name(sm.get('model'))} | "
            f"turns={sm.get('turns') or '-'} | "
            f"in={fmt_tokens((sm.get('input_tokens') or 0) + (sm.get('cache_read_tokens') or 0))} | "
            f"out={fmt_tokens(sm.get('output_tokens'))} | "
            f"peak ctx={_session_peak_ctx_str(sm)}"
            + (f" | cost={fmt_usd(sm.get('cost_usd'))}" if sm.get("cost_usd") is not None else "")
        )
    print(rule)
    return 0


def cmd_viz(args):
    """Render an ANSI terminal dashboard of job usage, burn bars, sparkline, and comparisons."""
    use_color = (not args.no_color) and (sys.stdout.isatty() or args.color)
    c = make_styler(use_color)
    term_w = args.width or shutil.get_terminal_size((96, 24)).columns
    term_w = max(68, min(term_w, 120))

    records = list(latest_records_by_job(args.ledger).values())
    if not records:
        print(f"No records in {args.ledger}. Run `tools/usage.py backfill` first.")
        return 0

    if args.job:
        rec = next((r for r in records if r["job"].upper() == args.job.upper()), None)
        if not rec:
            print(f"Job {args.job.upper()} not found in {args.ledger}.", file=sys.stderr)
            return 1
        return viz_single_job(rec, args, c, term_w)

    measured = [r for r in records if r.get("quota_deltas") or r.get("session_metrics")]
    if args.agent:
        measured = [r for r in measured if r.get("agent") == args.agent.lower()]
    if args.solo:
        measured = [r for r in measured if r.get("concurrency") == "solo"]

    if not measured:
        print("No measured jobs match the filter. Run `tools/usage.py backfill` first.")
        return 0

    chrono = list(measured)
    if args.sort == "burn":
        measured.sort(key=lambda r: primary_quota(r)[0] or 0.0, reverse=True)
    elif args.sort == "dur":
        measured.sort(key=lambda r: r.get("duration_s") or 0.0, reverse=True)

    if args.last:
        measured = measured[-args.last :] if args.sort == "time" else measured[: args.last]

    rule = c("dim", "═" * term_w)
    subrule = c("dim", "─" * term_w)

    solo_recs = [r for r in chrono if r.get("concurrency") == "solo"]
    solo_q5 = [primary_quota(r)[0] for r in solo_recs if primary_quota(r)[0] is not None]
    all_q5 = [primary_quota(r)[0] for r in measured if primary_quota(r)[0] is not None]
    max_q5 = max(all_q5) if all_q5 else 0.01

    print(rule)
    title = c("bold", "JOB USAGE DASHBOARD")
    kpi = (
        f"  {c('cyan', len(chrono))} measured  ·  "
        f"{c('green', len(solo_recs))} solo  ·  "
        f"med solo 5h: {c('bold', fmt_pct(statistics.median(solo_q5)) if solo_q5 else '-')}"
    )
    print(title + kpi)
    print(subrule)

    bar_w = max(14, min(32, term_w - 58))
    print(c("bold", "Per-Job 5h Quota Burn") + c("dim", f"  (sorted by {args.sort}; * = Reading path, RET = returned)"))
    for r in measured:
        q5, q7 = primary_quota(r)
        agent_tag = c("cyan", "gem") if r.get("agent") == "gemini" else c("magenta", "cld")
        mode_tag = c("green", "solo") if r.get("concurrency") == "solo" else c("dim", "shr ")
        bar = render_bar(q5, max_q5, bar_w, c, burn_color(q5))
        brief = r.get("brief") or {}
        bw = f"{brief.get('brief_words', 0)}w" + ("*" if brief.get("has_reading_path") else " ")
        ret = c("red", " RET") if r.get("returned") else ""
        jid_txt = f"{r['job']:<4}"
        q5_txt = f"{fmt_pct(q5):>7}"
        q7_txt = f"{fmt_pct(q7):>6}"
        bw_txt = f"{bw:>6}"
        print(
            f"  {c('bold', jid_txt)} {agent_tag} {mode_tag}  {bar}  "
            f"{c(burn_color(q5), q5_txt)}  {c('dim', q7_txt)} wk  "
            f"{fmt_dur(r.get('duration_s')):>6}  {c('dim', bw_txt)}{ret}"
        )

    spark_vals = [primary_quota(r)[0] for r in chrono]
    span_lbl = f"({chrono[0]['job']} .. {chrono[-1]['job']})"
    print()
    print(
        f"{c('bold', 'Burn Trend (oldest -> newest):')}  {render_sparkline(spark_vals, c)}  "
        f"{c('dim', span_lbl)}"
    )

    if solo_recs:
        print(subrule)
        print(c("bold", "Solo Patterns (Median 5h Quota Burn)"))
        groups = [
            ("Has Reading path", [r for r in solo_recs if (r.get("brief") or {}).get("has_reading_path")]),
            ("No Reading path", [r for r in solo_recs if not (r.get("brief") or {}).get("has_reading_path")]),
            ("Clean first pass", [r for r in solo_recs if not r.get("returned")]),
            ("Returned (rework)", [r for r in solo_recs if r.get("returned")]),
        ]
        meds = []
        for label, sub in groups:
            vals = [primary_quota(r)[0] for r in sub if primary_quota(r)[0] is not None]
            if vals:
                meds.append((label, len(sub), statistics.median(vals)))
        gmax = max((m[2] for m in meds), default=0.01)
        gbar_w = max(14, min(28, term_w - 44))
        for label, cnt, med in meds:
            bar = render_bar(med, gmax, gbar_w, c, burn_color(med))
            med_txt = f"{fmt_pct(med):>7}"
            print(f"  {label:<18} ({cnt:>2})  {bar}  {c(burn_color(med), med_txt)}")

    sessions = load_claude_sessions(args.claude_dir)
    if sessions:
        by_sid = collections.defaultdict(list)
        for r in sessions:
            by_sid[r.get("session_id") or f"anon-{r.get('cwd')}"].append(r)
        role_toks = collections.Counter()
        for srows in by_sid.values():
            role, _ = classify_claude_role(srows[-1], args.repo)
            ins = [r["total_input_tokens"] for r in srows if isinstance(r.get("total_input_tokens"), (int, float))]
            outs = [r["total_output_tokens"] for r in srows if isinstance(r.get("total_output_tokens"), (int, float))]
            role_toks[role] += (max(ins) if ins else 0) + (max(outs) if outs else 0)
        tot = role_toks["worker"] + role_toks["integrator"]
        if tot > 0:
            print(subrule)
            w_pct = role_toks["worker"] / tot
            i_pct = role_toks["integrator"] / tot
            sw = max(20, min(48, term_w - 30))
            wf = int(round(w_pct * sw))
            stacked = c("cyan", "█" * wf) + c("magenta", "▓" * (sw - wf))
            print(
                f"{c('bold', 'Claude Split:')}  [{stacked}]  "
                f"{c('cyan', f'worker {w_pct*100:.0f}%')} / {c('magenta', f'integrator {i_pct*100:.0f}%')}"
            )

    print(rule)
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="tools/usage.py",
        description="Passive usage & token benchmarker for Shop Sketch jobs (Claude & Gemini).",
    )
    p.add_argument("--repo", default=DEFAULT_REPO, help=f"Path to fretchup checkout (default: {DEFAULT_REPO})")
    p.add_argument("--claude-dir", default=DEFAULT_CLAUDE_DIR, help=f"Path to claude-usage dir (default: {DEFAULT_CLAUDE_DIR})")
    p.add_argument("--agy-dir", default=DEFAULT_AGY_DIR, help=f"Path to agy-usage-monitor dir (default: {DEFAULT_AGY_DIR})")
    p.add_argument("--agy-brain", default=DEFAULT_AGY_BRAIN, help=f"Path to AGY brain dir (default: {DEFAULT_AGY_BRAIN})")
    p.add_argument("--ledger", default=None, help="Path to usage JSONL ledger (default: <git-common-dir>/shopsketch-usage.jsonl)")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("snapshot", help="Record a passive job lifecycle usage snapshot (for job.py / integrate.py)")
    sp.add_argument("--event", required=True, choices=("take", "done", "return", "merge"))
    sp.add_argument("--job", required=True, help="Job ID (e.g. H109)")
    sp.add_argument("--agent", default=None, help="Override agent name")
    sp.add_argument("--session", default=None, help="Override session ID")
    sp.add_argument("--quiet", action="store_true", help="Suppress stdout summary")
    sp.add_argument("--strict", action="store_true", help="Raise errors instead of failing open")
    sp.set_defaults(func=cmd_snapshot)

    bp = sub.add_parser("backfill", help="Correlate existing jobs in shopsketch-jobs.json with monitor histories")
    bp.add_argument("--rebuild", action="store_true", help="Rewrite ledger from scratch")
    bp.add_argument("--all-agents", action="store_true", help="Include agents beyond claude & gemini (e.g. codex)")
    bp.set_defaults(func=cmd_backfill)

    rp = sub.add_parser("report", help="Show per-job usage table")
    rp.add_argument("--agent", choices=TRACKED_AGENTS, default=None)
    rp.add_argument("--solo", action="store_true", help="Only show solo (non-overlapping) jobs")
    rp.add_argument("--only-measured", action="store_true", help="Hide jobs with no quota or token data")
    rp.add_argument("--last", type=int, default=None, help="Show only the last N jobs")
    rp.add_argument("--json", action="store_true", help="Output raw JSON")
    rp.set_defaults(func=cmd_report)

    op = sub.add_parser("overhead", help="Compare Worker vs. Integrator token usage (Claude & Gemini)")
    op.set_defaults(func=cmd_overhead)

    cp = sub.add_parser("compare", help="Compare Claude vs. Gemini (solo jobs) and brief traits vs. burn")
    cp.set_defaults(func=cmd_compare)

    hp = sub.add_parser("holes", help="Inspect a transcript for token sinks and repeated reads")
    hp.add_argument("job", nargs="?", default=None, help="Job ID (e.g. H109)")
    hp.add_argument("--transcript", default=None, help="Explicit path to a Claude/AGY JSONL transcript")
    hp.add_argument("--json", action="store_true")
    hp.set_defaults(func=cmd_holes)

    orp = sub.add_parser("orient", help="Benchmark integrator startup orientation (tokens, peak ctx, 5h burn)")
    orp.add_argument("--last", type=int, default=7, help="Show last N integrator orientations (default: 7)")
    orp.add_argument("--days", type=float, default=None, help="Only scan transcripts modified within the last D days")
    orp.add_argument("--agent", choices=TRACKED_AGENTS, default=None)
    orp.add_argument("--json", action="store_true")
    orp.set_defaults(func=cmd_orient)

    bnp = sub.add_parser("bench", help="Combined worker + integrator orientation benchmark & model calibration")
    bnp.add_argument("--last", type=int, default=7, help="Show last N items per section (default: 7)")
    bnp.add_argument("--agent", choices=TRACKED_AGENTS, default=None)
    bnp.add_argument("--json", action="store_true")
    bnp.set_defaults(func=cmd_bench)

    ep = sub.add_parser("export", help="Export Markdown summary table")
    ep.add_argument("--only-measured", action="store_true")
    ep.add_argument("--last", type=int, default=None)
    ep.set_defaults(func=cmd_export)

    vp = sub.add_parser("viz", help="Terminal visualizer (burn bars, sparkline, solo patterns, per-job spike chart)")
    vp.add_argument("--job", default=None, help="Drill into a single job's burn-over-time spike chart (e.g. H098)")
    vp.add_argument("--agent", choices=TRACKED_AGENTS, default=None)
    vp.add_argument("--solo", action="store_true", help="Only show solo jobs")
    vp.add_argument("--sort", choices=("time", "burn", "dur"), default="time", help="Sort order (default: time)")
    vp.add_argument("--last", type=int, default=None, help="Limit to N jobs")
    vp.add_argument("--width", type=int, default=None, help="Override terminal width")
    vp.add_argument("--color", action="store_true", help="Force ANSI colors even when piped")
    vp.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    vp.set_defaults(func=cmd_viz)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.ledger:
        args.ledger = default_ledger_path(args.repo)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
