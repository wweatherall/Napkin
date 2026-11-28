#!/usr/bin/env python3
"""Measure observable repository reads in saved worker transcripts (H216)."""

import argparse
import ast
from collections import defaultdict, deque
from dataclasses import dataclass, field
import datetime as dt
from functools import lru_cache
import importlib.util
import itertools
import json
import os
from pathlib import Path
import re
import shlex
from statistics import median
import subprocess
import sys
from tempfile import NamedTemporaryFile
import warnings
from urllib.parse import unquote


# Native tool names, plus the command names handled by shell_calls. Unknown names
# or shell commands are recorded as other. Shell wrappers are parsed separately.
TOOL_ACTION = {
    **dict.fromkeys(("read", "read_file", "view_file", "cat", "sed", "head", "tail", "nl"), "read"),
    **dict.fromkeys(("grep", "rg", "grep_search"), "search"),
    **dict.fromkeys(("edit", "write", "multiedit", "edit_file", "write_file",
                     "write_to_file", "replace_file_content", "multi_replace_file_content",
                     "notebookedit", "apply_patch", "filechange", "tee", "touch", "mv", "cp",
                     "rm", "truncate"), "edit"),
    **dict.fromkeys(("bash", "exec_command", "run_command", "execute_command",
                     "run_shell_command", "commandexecution", "shell"), "shell"),
}
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = "tests/reading_cost.json"
CATEGORIES = ("code", "tests", "docs", "other")
KINDS = ("worker op", "viewport tool", "tools/process", "docs only", "mixed", "unknown")
CLAIM = re.compile(r"(?m)^took (H\d+) \((?:new|resumed[^)]*)\): branch (\w+)/[^,]+, worktree (\S+)")
CLAIM_CMD = re.compile(r"(?:^|[\s/])(?:GET_A_JOB\.py\b|job\.py\s+take\b)")
WORKTREE = re.compile(r"(?:^|/)(?:\.worktrees/(?:Napkin|ShopSketch|fretchup)/|"
                      r"(?:fretchup|shopsketch|napkin)-jobs/|fretchup-)"
                      r"h(\d+)(?:-[^/\s]+)?(?:/|[\s;]|$)", re.I)
SUBMIT_CMD = re.compile(r"(?:^|[\s/])(?:SUBMIT_JOB\.py\b|job\.py\s+done\b)")
TRUNCATION = re.compile(r"^(?:…\d+ lines? truncated|\.\.\.[ ]*\d+ lines? truncated|\[truncated)", re.I)


def timestamp(value):
    if isinstance(value, (int, float)):
        return value
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def json_rows(path):
    try:
        with Path(path).open(encoding="utf-8", errors="replace") as source:
            for line in source:
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        yield row
                except ValueError:
                    continue
    except OSError:
        return


def string(value):
    # AGY serializes individual string arguments as JSON values inside JSON.
    if isinstance(value, str) and value.startswith('"'):
        try:
            return json.loads(value)
        except ValueError:
            pass
    return value


def arguments(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def cmd_arg(args):
    return string(args.get("cmd") or args.get("command") or args.get("CommandLine") or "")


def output_text(content):
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return content if isinstance(content, str) else ""


@dataclass
class Call:
    name: str
    args: dict = field(default_factory=dict)
    cwd: str = ""
    when: float = None
    match: tuple = ()
    submitted: bool = False
    result_lines: int = None
    numbered_matches: int = 0
    failed: bool = False

    @property
    def action(self):
        return TOOL_ACTION.get(self.name.lower().split(".")[-1], "other")

    def result(self, content, failed=False):
        output = output_text(content)
        command = cmd_arg(self.args)
        status = re.search(r"(?im)^(?:Process exited with code|Command exited with code) (\d+)", output)
        self.failed = failed or bool(status and status[1] != "0")
        if command and CLAIM_CMD.search(command):
            match = CLAIM.search(output)
            if match:
                self.match = match.groups()
        if command and SUBMIT_CMD.search(command):
            self.submitted = not self.failed and bool(re.search(
                r"(?m)^H\d+ done(?::| on )", output))
        for marker in ("\nCommand output:\n", "\nFinal output:\n", "\nOutput:\n"):
            if marker in output:
                output = output.split(marker, 1)[1]
                break
        # AGY can join a result's absolute target name and actual match lines.
        lines = output.splitlines()
        self.result_lines = sum(1 for line in lines if not TRUNCATION.match(line))
        self.numbered_matches = sum(bool(re.match(r"^[^:\s][^:]*:\d+:(?:\d+:)?", line)) for line in lines)


@dataclass
class Turn:
    when: float
    tokens: int = None
    model: str = None


@dataclass
class Transcript:
    agent: str
    session: str
    events: list

    @property
    def claims(self):
        return [(i, event) for i, event in enumerate(self.events) if isinstance(event, Call) and event.match]


def per_response_tokens(usage, cache_keys):
    keys = ("input_tokens", "output_tokens", *cache_keys)
    return sum(usage.get(k) or 0 for k in keys) if any(k in usage for k in keys) else None


def read_claude(rows, sid):
    events, responses, calls = [], {}, {}
    for row in rows:
        message = row.get("message") or {}
        if row.get("isSidechain") or not isinstance(message, dict):
            continue
        when = timestamp(row.get("timestamp"))
        sid = row.get("sessionId") or sid
        if row.get("type") == "assistant":
            model, usage = message.get("model"), message.get("usage") or {}
            tokens = per_response_tokens(usage, ("cache_read_input_tokens", "cache_creation_input_tokens"))
            request = message.get("id") or row.get("requestId")
            turn = responses.get(request)
            if turn:
                if tokens is not None:
                    turn.tokens = max(turn.tokens or 0, tokens)
            else:
                turn = Turn(when, tokens, model)
                events.append(turn)
                if request:
                    responses[request] = turn
        content = message.get("content")
        for block in content if isinstance(content, list) else ():
            if block.get("type") == "tool_use":
                key = block.get("id")
                if key and key in calls:
                    continue
                call = Call(block.get("name", ""), arguments(block.get("input")), row.get("cwd", ""), when)
                events.append(call)
                if key:
                    calls[key] = call
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                calls[block["tool_use_id"]].result(block.get("content"), block.get("is_error", False))
    return Transcript("claude", sid, events)


def read_gemini(rows, sid):
    events, pending = [], deque()
    for row in rows:
        kind = row.get("type")
        when = timestamp(row.get("created_at") or row.get("timestamp"))
        if kind == "PLANNER_RESPONSE":
            events.append(Turn(when, per_response_tokens(row, ("cache_read_tokens",)), row.get("model")))
            for tool in row.get("tool_calls") or ():
                call = Call(tool.get("name", ""), arguments(tool.get("args")), when=when)
                pending.append(call)
                events.append(call)
        elif kind == "GENERIC" and pending:
            pending.popleft().result(row.get("content"), row.get("status") in ("ERROR", "FAILED"))
        elif kind == "USER_INPUT":
            pending.clear()
    return Transcript("gemini", sid, events)


def codex_command(value):
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value
        if not isinstance(parsed, list):
            return value
        value = parsed
    if isinstance(value, list):
        if len(value) == 3 and re.fullmatch(r"-[a-z]*c", value[1]):
            return value[2]
        return shlex.join(value)
    return ""


def read_codex(rows, sid):
    events, legacy, modern = [], {}, []
    cwd, model, previous = "", None, 0
    for row in rows:
        kind, payload = row.get("type"), row.get("payload") or {}
        event = payload.get("type")
        when = timestamp(row.get("timestamp"))
        if kind == "session_meta":
            sid = payload.get("id") or sid
            cwd = payload.get("cwd", cwd)
            model = payload.get("model", model)
        elif kind == "turn_context":
            cwd = payload.get("cwd", cwd)
            model = payload.get("model", model)
        elif kind == "token_usage_record" or event == "token_count":
            data = (payload.get("thread_token_usage") if kind == "token_usage_record" else
                    (payload.get("info") or {}).get("total_token_usage"))
            if data:
                total = data.get("total_tokens", (data.get("input_tokens") or 0) + (data.get("output_tokens") or 0))
                # The modern log emits the same cumulative count twice. A new
                # counter epoch can follow a resumed or compacted rollout.
                if kind == "token_usage_record" or total != previous:
                    events.append(Turn(when, total - previous if total >= previous else total, model))
                    previous = total
        elif kind == "response_item" and event in ("function_call", "custom_tool_call"):
            raw = payload.get("arguments") or payload.get("input")
            call = Call(payload.get("name", ""), arguments(raw), cwd, when)
            legacy[payload.get("call_id")] = call
            events.append(call)
        elif kind == "response_item" and event in ("function_call_output", "custom_tool_call_output"):
            call = legacy.get(payload.get("call_id"))
            if call:
                call.result(payload.get("output"))
        elif event == "item_completed":
            item = payload.get("item") or {}
            name = item.get("type")
            started = payload.get("started_at_ms")
            started = started / 1000 if started is not None else when
            if name == "CommandExecution":
                where = item.get("cwd") or cwd
                call = Call(name, {"cmd": codex_command(item.get("command"))}, where, started)
                call.result(item.get("aggregated_output"), item.get("exit_code") not in (None, 0, "0"))
                modern.append(call)
            elif name == "FileChange":
                modern.append(Call(name, cwd=cwd, when=started, failed=item.get("status") == "failed"))
    if modern:
        # Structured items describe the commands inside functions.exec, whose
        # outer custom tool call is JavaScript and may batch several commands.
        legacy_names = {"exec", "exec_command", "apply_patch"}
        events = [e for e in events if not isinstance(e, Call) or e.name.lower() not in legacy_names]
        # Completion events can be out of order when calls run in parallel.
        events = sorted(events + modern, key=lambda e: e.when or 0)
    return Transcript("codex", sid, events)


PARSERS = {"claude": read_claude, "gemini": read_gemini, "codex": read_codex}


def parse(path, agent):
    path = Path(path)
    sid = path.parent.parent.parent.name if agent == "gemini" else path.stem
    return PARSERS[agent](json_rows(path), sid)


def decode_path(value):
    if value.startswith("file://"):
        return unquote(value[7:])
    return value


def repo_path(path, cwd, root, old_roots=()):
    if not path or re.search(r"[$*?]", path) or path.startswith(("~", "-")):
        return None
    # Some older sessions ran before the checkout was renamed and relocated.
    path = decode_path(path)
    cwd = decode_path(cwd or str(root))
    full = Path(os.path.normpath(os.path.join(cwd, path))) if os.path.isabs(cwd) else root / cwd / path
    full = Path(os.path.normpath(full))
    match = WORKTREE.search(full.as_posix())
    if match:
        tail = full.as_posix()[match.end():]
        if tail and not tail.startswith((".git/", "scratch/")):
            return tail
        return None
    for base in (root, *old_roots):
        if full.is_relative_to(base):
            tail = full.relative_to(base).as_posix()
            if tail != "." and not tail.startswith((".git/", "scratch/")):
                return tail
    return None


def category(path):
    p = Path(path)
    if p.suffix.lower() == ".md" or p.parts[0] == "03_Past_Decisions":
        return "docs"
    if (p.parts[0] == "tests" or any(part in ("tests", "scenario") for part in p.parts[:-1])
            or p.name.startswith("test_") or p.name == "tests.gd"):
        return "tests"
    if p.suffix in (".py", ".gd", ".sh", ".swift", ".js", ".ts", ".c", ".h", ".cpp", ".command"):
        return "code"
    return "other"


@dataclass
class Read:
    path: str
    start: int = 1
    end: int = None  # Inclusive, None means EOF, negative start counts from EOF.


def number(value):
    try:
        return int(string(value))
    except (TypeError, ValueError):
        return None


def native_read(args):
    path = next((string(args[k]) for k in ("file_path", "path", "Path", "AbsolutePath", "TargetFile")
                 if args.get(k)), None)
    if not isinstance(path, str):
        return None
    start = number(args.get("StartLine", args.get("start_line", args.get("offset")))) or 1
    end = number(args.get("EndLine", args.get("end_line")))
    limit = number(args.get("limit"))
    if end is None and limit is not None:
        end = start + limit - 1
    return Read(path, start, end)


def shell_words(command):
    # Separate only shell syntax. Quoted expressions, file names with spaces,
    # and pipes inside regexes stay with their command.
    if command.startswith('"') and command.endswith('"'):
        command = string(command)
    if not isinstance(command, str):
        return [], None
    heredoc = re.search(r"<<-?\s*['\"]?([A-Za-z_]\w*)['\"]?[^\n]*\n", command)
    script = None
    if heredoc:
        end = re.search(r"(?m)^\s*" + re.escape(heredoc[1]) + r"\s*$", command[heredoc.end():])
        if end:
            script = command[heredoc.end():heredoc.end() + end.start()]
            command = command[:heredoc.start()] + "\n" + command[heredoc.end() + end.end():]
    # shlex does not retain newlines as tokens. Standalone newlines outside
    # quotes are command separators.
    lexer = shlex.shlex(command, posix=True, punctuation_chars="|;&<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        return list(lexer), script
    except ValueError:
        return [], script


def python_writes(script):
    if not script:
        return False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(script)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", getattr(node.func, "id", ""))
        if name in ("write_text", "write_bytes", "unlink", "rename"):
            return True
        if name == "open":
            index = 1 if isinstance(node.func, ast.Name) else 0
            mode = next((k.value for k in node.keywords if k.arg == "mode"),
                        node.args[index] if len(node.args) > index else None)
            if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and set(mode.value) & set("wax+"):
                return True
    return False


def sed_reads(args):
    quiet = ("-n", "-ne", "-en", "--quiet", "--silent")
    if not any(arg in quiet for arg in args):
        return []
    args = [arg for arg in args if arg not in (*quiet, "-e", "--")]
    ranges = []
    while args:
        parts = args[0].strip("; ").split(";")
        matches = [re.fullmatch(r"\s*(\d+)(?:,\s*(\d+|\$))?\s*p\s*", part) for part in parts]
        if not all(matches):
            break
        ranges.extend((int(m[1]), None if m[2] == "$" else int(m[2] or m[1])) for m in matches)
        args.pop(0)
    return [Read(path, first, last) for path in args if not path.startswith("-") for first, last in ranges]


def head_tail_reads(name, args):
    n = "10"
    if len(args) >= 2 and args[0] in ("-n", "--lines"):
        n, args = args[1], args[2:]
    elif args and re.fullmatch(r"-\d+", args[0]):
        n, args = args[0][1:], args[1:]
    elif args and re.fullmatch(r"(?:-n|--lines=)[+-]?\d+", args[0]):
        n, args = re.sub(r"^(?:-n|--lines=)", "", args[0]), args[1:]
    count = number(n)
    if count is None or not count or any(arg.startswith("-") and arg != "--" for arg in args):
        return []
    if name == "head" and count < 0:
        return []  # GNU head's all-but-last form is not used by the macOS head.
    first, last = (1, count) if name == "head" else (count if n.startswith("+") else -abs(count), None)
    return [Read(path, first, last) for path in args if path != "--"]


def shell_calls(command, cwd):
    """Yield (action, cwd, reads) for recognizable simple shell commands."""
    words, script = shell_words(command)
    group = []
    # A pipe can provide a file operand to a range filter.
    piped_reads = []
    for token in (*words, ";"):
        if not re.fullmatch(r"[|;&\n]+", token):
            group.append(token)
            continue
        if not group:
            continue
        original, group = group, []
        args = list(original)
        redirects = [i for i, arg in enumerate(args) if arg in (">", ">>", "<", ">&", ">|", "&>")]
        if redirects and redirects[0] > 0 and args[redirects[0] - 1].isdigit():
            del args[redirects[0] - 1]
            redirects = [i - 1 for i in redirects]
        if any(i + 1 < len(args) and args[i] in (">", ">>", ">|", "&>") and not args[i + 1].startswith("/dev/")
               for i in redirects):
            yield "edit", cwd, []
        if redirects:
            args = args[:redirects[0]]
        while args and (re.match(r"^[A-Za-z_]\w*=", args[0]) or args[0] in ("command", "env")):
            args.pop(0)
        if not args:
            continue
        name, *args = args
        name = Path(name).name
        if name == "cd" and args:
            cwd = os.path.normpath(os.path.join(decode_path(cwd), args[0]))
            continue
        action = TOOL_ACTION.get(name, "other")
        reads = []
        if name == "git" and len(args) == 2 and args[0] == "show" and ":" in args[1]:
            path = args[1].split(":", 1)[1]
            action, reads = "read", [Read(path)]
        elif name == "git" and args[:1] == ["apply"]:
            action = "edit" if "--check" not in args else "other"
        elif name == "sed":
            reads = sed_reads(args)
            if not reads and piped_reads:
                reads = sed_reads(args + [read.path for read in piped_reads])
            if any(arg == "-i" or arg.startswith("-i.") for arg in args):
                action = "edit"
        elif name == "perl" and any(arg.startswith("-") and "i" in arg[1:] for arg in args[:2]):
            action = "edit"
        elif name in ("head", "tail"):
            reads = head_tail_reads(name, args)
            if not reads and piped_reads:
                reads = head_tail_reads(name, args + [read.path for read in piped_reads])
        elif name in ("cat", "nl"):
            if name == "nl" and args[:2] == ["-b", "a"]:
                args = args[2:]
            reads = [Read(arg) for arg in args if not arg.startswith("-")]
        elif re.fullmatch(r"python(?:3(?:\.\d+)?)?", name):
            code = args[1] if len(args) >= 2 and args[0] == "-c" else script
            if python_writes(code):
                action = "edit"
        if action == "shell":
            action = "other"
        if action == "read" and token.strip() == "|" and reads:
            piped_reads = reads
        elif piped_reads and name in ("sed", "head", "tail") and reads:
            yield action, cwd, reads
            piped_reads = []
        else:
            if piped_reads:
                yield "read", cwd, piped_reads
                piped_reads = []
            # Passthrough filters on search outputs do not emit a second result.
            if name not in ("head", "tail", "sed") or reads or token.strip() == "|":
                yield action if reads or action != "read" else "other", cwd, reads
    if piped_reads:
        yield "read", cwd, piped_reads


def read_actions(call, cwd):
    cwd = string(call.args.get("workdir") or call.args.get("Cwd") or call.cwd or cwd)
    if call.action == "shell":
        return list(shell_calls(cmd_arg(call.args), cwd)) or [("other", cwd, [])]
    if call.action == "read":
        read = native_read(call.args)
        return [("read", cwd, [read] if read else [])]
    return [(call.action, cwd, [])]


def union_size(ranges):
    end = total = 0
    for first, last in sorted(ranges):
        if last >= first:
            total += max(0, last - max(first - 1, end))
            end = max(end, last)
    return total


def spans(transcript, job, record):
    """Select this job's portions of a session, sharing no turns across claims."""
    claims = transcript.claims
    if claims:
        pieces = []
        left = 0
        for n, (index, call) in enumerate(claims):
            right = claims[n + 1][0] if n + 1 < len(claims) else len(transcript.events)
            if n + 1 < len(claims) and transcript.agent != "codex":
                # Claude/Gemini record the turn that called GET_A_JOB before
                # the tool. It belongs to the incoming job when there is one.
                if right > index + 1 and isinstance(transcript.events[right - 1], Turn):
                    right -= 1
            if call.match[0] == job:
                piece = transcript.events[left:right]
                submit = next((i for i, e in enumerate(piece) if isinstance(e, Call) and e.submitted), None)
                if submit is not None:
                    # A legacy Codex cumulative token sample follows its tool result.
                    aftermath = piece[submit + 1:submit + 2] if transcript.agent == "codex" else []
                    piece = piece[:submit + 1] + [e for e in aftermath if isinstance(e, Turn)]
                pieces.extend(piece)
            left = right
        return pieces
    if not record:
        return transcript.events
    start = record.get("taken")
    end = record.get("done") or record.get("merged")
    # Allow the startup just before the queue claim when its output is missing.
    first = next((e.when for e in transcript.events if e.when is not None), None)
    begin = start - 300 if start and first and first < start - 300 else None
    return [event for event in transcript.events
            if event.when is None or (not begin or event.when >= begin) and (not end or event.when <= end)]


def git(root, *args, binary=False):
    result = subprocess.run(("git", *args), cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=not binary, encoding=None if binary else "utf-8",
                            errors=None if binary else "replace")
    return result.stdout if result.returncode == 0 else None


class Repository:
    def __init__(self, root):
        self.root = Path(root).resolve()
        common = git(self.root, "rev-parse", "--git-common-dir")
        if not common:
            raise ValueError("reading_cost.py needs a Git checkout")
        self.common = (self.root / common.strip()).resolve()
        self.main = self.common.parent
        # Historical checkout paths retained in the transcripts after the rename.
        self.old_roots = (self.main, self.main.parent / "ShopSketch",
                          Path.home() / "Sites" / "fretchup", Path.home() / "Sites" / "shopsketch")
        self.history = {}
        for line in (git(self.root, "log", "--first-parent", "--format=%H%x09%cs%x09%s", "main") or "").splitlines():
            rev, date, subject = line.split("\t", 2)
            self.history[rev] = (date, subject)
        self.merges, self.merge_refs = {}, {}
        for rev, (date, subject) in self.history.items():
            branch = re.match(r"Merge (claude|codex|gemini)/h(\d+)\b", subject, re.I)
            if branch:
                self.merges.setdefault("H" + branch[2], (rev, date, branch[1].lower()))
            result = re.search(r"\b(H\d+)\): Work list result, merged ([a-f0-9]{7,40})\b", subject)
            if result:
                self.merge_refs.setdefault(*result.groups())

    @lru_cache(maxsize=None)
    def line_count(self, rev, path):
        data = git(self.root, "cat-file", "blob", f"{rev}:{path}", binary=True) if rev else None
        fallback = data is None and bool(rev)
        if data is None:
            try:
                data = (self.root / path).read_bytes()
            except OSError:
                return None, False
        if b"\x00" in data:
            return None, False
        return data.count(b"\n") + bool(data and not data.endswith(b"\n")), fallback

    def diff(self, job, brief, record):
        rev, date, agent = self.merges.get(job, (None, None, None))
        resolution = re.search(r"(?m)^Resolution: (.+)", brief)
        if not rev:
            refs = [ref for ref in (self.merge_refs.get(job), record.get("commit")) if ref]
            if resolution and "merged" in resolution[1].lower():
                refs.extend(re.findall(r"\b[0-9a-f]{7,40}\b", resolution[1]))
            for ref in refs:
                rev = next((commit for commit in self.history if commit.startswith(ref)), None)
                if rev:
                    date, _ = self.history[rev]
                    break
        if not date and record.get("merged"):
            date = dt.datetime.fromtimestamp(record["merged"], dt.timezone.utc).date().isoformat()
        if not date and resolution:
            stamp = re.search(r"\b\d{4}-\d\d-\d\d\b", resolution[1])
            date = stamp[0] if stamp else None
        stats = git(self.root, "show", "--first-parent", "--format=", "--numstat", "-z", "--no-renames", rev) if rev else None
        files = {}
        if stats is not None:
            for part in stats.split("\0"):
                if part:
                    a, d, path = part.split("\t", 2)
                    files[path] = int(a) + int(d) if a.isdigit() and d.isdigit() else None
        return rev, date, agent, files if stats is not None else None


def classify_job(files):
    if files is None:
        return "unknown"
    bookkeeping = {"BOARD.md", "docs/agent-handoff.md", "docs/handoff-archive.md", "docs/worker-feedback.md",
                   "ARCHITECTURE.md", "docs/dependency-map.md"}
    content = {p for p in files if p not in bookkeeping and not p.startswith("docs/handoff/")}
    domains = set()
    for path in content:
        if category(path) == "docs":
            continue
        part = path.split("/", 1)[0]
        if part != "tests":
            domains.add({"worker": "worker op", "viewport": "viewport tool"}.get(part, "tools/process"))
    if not domains and all(category(path) == "docs" for path in content):
        return "docs only"
    if len(domains) > 1:
        return "mixed"
    return next(iter(domains), "tools/process")


def chronological(sources):
    if len(sources) == 1:
        return sources[0]
    timed = []
    for events in sources:
        when = next((e.when for e in events if e.when is not None), 0)
        for event in events:
            if event.when is not None:
                when = max(when, event.when)
            timed.append((when, event))
    return [event for _, event in sorted(timed, key=lambda pair: pair[0])]


def measure(sources, repository, rev, cwd):
    ranges = defaultdict(list)
    counts = {c: {"files": 0, "unique": 0, "repeated": 0} for c in CATEGORIES}
    calls = dict.fromkeys(("read", "search", "edit", "other"), 0)
    fallback_paths, unresolved = set(), set()
    total, before_edit, token_seen, first_edit, searches, missing_search = 0, None, False, False, 0, 0
    models = {}
    for event in chronological(sources):
        if isinstance(event, Turn):
            if event.tokens is not None:
                total += event.tokens
                token_seen = True
            if event.model and event.model != "<synthetic>":
                models[event.model] = None
            continue
        actions = read_actions(event, cwd)
        search_count = sum(action == "search" for action, _, _ in actions)
        if search_count:
            if event.result_lines is not None and all(action == "search" for action, _, _ in actions):
                searches += 0 if event.failed else event.result_lines
            else:
                # A combined result cannot be split exactly. Numbered grep
                # matches retain their path, so count the identifiable part.
                searches += event.numbered_matches
                missing_search += search_count
        for action, where, reads in actions:
            calls[action] += 1
            if action == "edit" and not first_edit:
                before_edit = total if token_seen else None
                first_edit = True
            if event.failed:
                continue
            for read in reads:
                path = repo_path(read.path, where, repository.root, repository.old_roots)
                if not path:
                    continue
                size, fallback = repository.line_count(rev, path)
                if size is None:
                    unresolved.add(path)
                    continue
                if fallback:
                    fallback_paths.add(path)
                first = max(1, read.start if read.start >= 0 else size + read.start + 1)
                last = size if read.end is None else min(size, read.end)
                ranges[path].append((first, last))
    for path, intervals in sorted(ranges.items()):
        unique = union_size(intervals)
        group = counts[category(path)]
        group["files"] += 1
        group["unique"] += unique
        group["repeated"] += sum(max(0, end - start + 1) for start, end in intervals) - unique
    return dict(files_read=sorted(ranges), reads=counts, search_output_lines=searches,
                searches_with_unattributed_output=missing_search,
                tokens_before_first_edit=before_edit, tokens_total=total if token_seen else None,
                first_edit_observed=first_edit, calls=calls, models=list(models),
                current_file_fallbacks=sorted(fallback_paths), unresolved_read_paths=len(unresolved))


def load_usage(repository):
    # Same location as job.py's _usage_tool, resolved through the Git common dir.
    path = repository.main.parents[1] / "09_Tools" / "MEASURE_TOKEN_USE.py"
    if not path.is_file():
        raise ValueError(f"Cannot find the comitatus usage tool at {path}")
    spec = importlib.util.spec_from_file_location("napkin_usage", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Sessions:
    def __init__(self, usage):
        self.usage = usage
        self.by_id = {}
        self.by_claim = defaultdict(list)
        self.parsed = {}
        home = Path.home()
        codex_dir = Path(os.environ.get("CODEX_SESSIONS_DIR", home / ".codex" / "sessions")).expanduser()
        brain = usage.DEFAULT_AGY_BRAIN
        paths = {
            "codex": sorted(codex_dir.rglob("rollout-*.jsonl")),
            "claude": sorted((home / ".claude" / "projects").glob("*/*.jsonl")),
            "gemini": sorted(Path(path) for _, _, path in usage.list_agy_transcripts(brain)) if brain else [],
        }
        # Explicit successful take output recovers archived jobs pruned from
        # the queue and ledger. The session's real ID still comes from the log.
        for agent, items in paths.items():
            for path in items:
                streamed = json_rows(path)
                if agent == "codex":
                    meta = next(streamed, {})
                    if meta.get("type") != "session_meta":
                        continue
                    sid = (meta.get("payload") or {}).get("id")
                elif agent == "claude":
                    sid = path.stem
                else:
                    sid = path.parent.parent.parent.name
                if sid:
                    self.by_id[agent, sid] = path
                try:
                    with path.open("rb") as source:
                        has_claim = any(b"took H" in line for line in source)
                except OSError:
                    continue
                if has_claim:
                    parsed = self.get(agent, path)
                    for _, call in parsed.claims:
                        jid, branch_agent, _ = call.match
                        if branch_agent.lower() == agent:
                            self.by_claim[jid].append((agent, path))

    def get(self, agent, path):
        key = agent, Path(path).resolve()
        if key not in self.parsed:
            self.parsed[key] = parse(path, agent)
        return self.parsed[key]

    def find(self, jid, records, queue_ids):
        candidates = {}
        for record in records:
            agent, sid = record.get("agent"), record.get("session")
            if agent not in PARSERS:
                continue
            path = self.by_id.get((agent, sid))
            if agent != "codex" and not path and (sid or (record.get("session_metrics") or {}).get("transcript_path")):
                path, _ = self.usage.discover_transcript(record)
            if path:
                key = agent, Path(path).resolve()
                if key not in candidates or record.get("done"):
                    candidates[key] = "ledger or queue", record
        for sid in queue_ids:
            for agent in PARSERS:
                path = self.by_id.get((agent, sid))
                if path:
                    candidates.setdefault((agent, Path(path).resolve()), ("queue session history", {}))
        for agent, path in self.by_claim[jid]:
            candidates.setdefault((agent, path.resolve()), ("successful claim", {}))
        found = []
        for (agent, path), (match, record) in candidates.items():
            parsed = self.get(agent, path)
            if parsed.claims:
                if not any(call.match[0] == jid for _, call in parsed.claims):
                    continue
            elif parsed.session != record.get("session") and parsed.session not in queue_ids:
                if not worker_evidence(parsed, jid):
                    continue
            found.append((parsed, record, match))
        return sorted(found, key=lambda row: (
            next((event.when for event in row[0].events if event.when is not None), 0),
            row[0].agent, row[0].session))


def worker_evidence(transcript, job):
    """Validate heuristic ledger matches against tool calls, not prompt text."""
    seen_job_tree = False
    for event in transcript.events:
        if not isinstance(event, Call):
            continue
        command = cmd_arg(event.args)
        if re.search(r"\bintegrator\.py\s+take\b|--role\s+integrator\b", command):
            return False
        where = [event.cwd, string(event.args.get("workdir") or "")]
        read = native_read(event.args) if event.action == "read" else None
        if read:
            where.append(read.path)
        where.extend(re.findall(r"(?:^|[;&]\s*)cd\s+([^;&\n ]+)", command))
        for value in where:
            match = WORKTREE.search(value)
            if match and "H" + match[1] == job:
                seen_job_tree = True
    return seen_job_tree


def collect(repository, wanted=None):
    usage = load_usage(repository)
    archive = usage.load_archive_index(repository.root)
    queue = usage.load_json(usage.jobs_state_path(repository.root), {}) or {}
    ledger = next((repository.common / name for name in ("napkin-usage.jsonl", "shopsketch-usage.jsonl")
                   if (repository.common / name).is_file()), None)
    latest = usage.latest_records_by_job(ledger)
    records = defaultdict(list)
    for row in json_rows(ledger) if ledger else ():
        if row.get("job"):
            records[row["job"]].append(row)
    queue_ids = defaultdict(list)
    for sid, jobs in queue.get("sessions", {}).items():
        for jid in jobs:
            queue_ids[jid].append(sid)
    jobs = archive if wanted is None else {wanted: archive.get(wanted, "")}
    if wanted and wanted not in archive and wanted not in latest and wanted not in queue.get("jobs", {}):
        raise ValueError(f"No archived or queued job {wanted}")
    index = Sessions(usage)
    rows = []
    for jid, brief in sorted(jobs.items()):
        current = queue.get("jobs", {}).get(jid, {})
        record = {**latest.get(jid, {}), **{k: v for k, v in current.items() if v is not None}}
        rev, date, merged_agent, files = repository.diff(jid, brief, record)
        agent = record.get("agent") or merged_agent
        row = dict(job=jid, merge_date=date, merge_commit=rev, agent=agent, model=record.get("model"),
                   kind=classify_job(files), files_changed=files,
                   changed_file_count=len(files) if files is not None else None,
                   lines_changed=sum(n or 0 for n in files.values()) if files is not None else None)
        sources = index.find(jid, records[jid] + [current | {"job": jid}], queue_ids[jid])
        source_rows, events = [], []
        for transcript, attempt, match in sources:
            portion = spans(transcript, jid, attempt)
            if not portion:
                continue
            events.append(portion)
            source_rows.append(dict(agent=transcript.agent, session=transcript.session, matched_by=match,
                                    claims=len(transcript.claims),
                                    split_at_claim=len({call.match[0] for _, call in transcript.claims}) > 1))
        row["sessions"] = source_rows
        represented = {s["session"] for s in source_rows}
        expected = set(queue_ids[jid]) | {r["session"] for r in [current, *records[jid]] if r.get("session")}
        # Older queue strings were worker launch labels; report actual session IDs.
        real_ids = {sid for sid in expected if re.fullmatch(r"[0-9a-fA-F-]{36}", sid)}
        row["unmatched_recorded_sessions"] = sorted(real_ids - represented)
        if source_rows:
            row.update(measure(events, repository, rev, record.get("worktree") or str(repository.main)))
            row["agent"] = " + ".join(dict.fromkeys(s["agent"] for s in source_rows))
            if row["models"]:
                row["model"] = " + ".join(row["models"])
        else:
            row["missing_transcript"] = ("recorded session or transcript unavailable" if expected or record
                                         else "no ledger entry, queue session or transcript claim")
        rows.append(row)
    return {"jobs": rows}


def display_number(value):
    if value is None:
        return "–"
    return f"{value:,.0f}" if value == int(value) else f"{value:,.1f}"


def report(data):
    rows = data["jobs"]
    measured = [row for row in rows if "reads" in row]
    missing = [row for row in rows if "missing_transcript" in row]
    print(f"Reading cost: {len(measured)}/{len(rows)} jobs measured, {len(missing)} missing transcripts")
    print("Reads use requested ranges; search lines are separate. Tokens include cached input and output.")
    print("Day medians use the measured jobs with each metric. Δ lines are added + deleted.")
    print("Search counts are lower bounds when search results share a combined tool output.")
    for kind in KINDS:
        jobs = sorted((r for r in measured if r["kind"] == kind), key=lambda r: (r["merge_date"] or "9999", r["job"]))
        if not jobs:
            continue
        print(f"\n{kind} ({len(jobs)})")
        print("Date        Job / agent            Files  Unique  Repeat  Search  Pre-edit tokens  Total tokens  Δ files  Δ lines")
        for date, group in itertools.groupby(jobs, key=lambda row: row["merge_date"]):
            values = []
            for row in group:
                stats = [sum(r[key] for r in row["reads"].values()) for key in ("files", "unique", "repeated")]
                stats.extend([row["search_output_lines"], row["tokens_before_first_edit"], row["tokens_total"],
                              row["changed_file_count"], row["lines_changed"]])
                values.append(stats)
                marker = ("+" if len(row["sessions"]) > 1 else "") + (
                    "*" if any(s["split_at_claim"] for s in row["sessions"]) else "") + (
                    "?" if row["unmatched_recorded_sessions"] else "")
                label = f'{row["job"]}{marker} {row["agent"]}'
                print(f'{date or "unknown":<11} {label:<20} ' + format_stats(stats))
            medians = [median(present) if (present := [v for v in column if v is not None]) else None
                       for column in zip(*values)]
            print(f'{"":11} {"median (" + str(len(values)) + ")":<20} ' + format_stats(medians))
    print("\n+ multiple sessions, * shared transcript split at claim, ? recorded session unavailable")
    print("Highest docs / code (unique lines; both present)")
    print_ratios(measured, lambda r: r["reads"]["docs"]["unique"], lambda r: r["reads"]["code"]["unique"])
    print("Highest code / changed line (unique code lines; changes present)")
    print_ratios(measured, lambda r: r["reads"]["code"]["unique"], lambda r: r["lines_changed"])
    if missing:
        print("\nMissing transcript")
        for reason, jobs in itertools.groupby(sorted(missing, key=lambda r: r["missing_transcript"]),
                                               key=lambda row: row["missing_transcript"]):
            print(f"{reason}: " + ", ".join(r["job"] for r in jobs))


def format_stats(stats):
    widths = (5, 7, 7, 7, 16, 13, 8, 8)
    return " ".join(f"{display_number(value):>{width}}" for value, width in zip(stats, widths))


def print_ratios(rows, numer, denom):
    ratios = []
    for row in rows:
        if (n := numer(row)) and (d := denom(row)):
            ratios.append((n / d, row["job"], n, d))
    for ratio, jid, n, d in sorted(ratios, reverse=True)[:5]:
        print(f"  {jid:<5} {ratio:8.2f}  ({n:,} / {d:,})")


def save_snapshot(path, data):
    scratch = path.parents[1] / "scratch"
    scratch.mkdir(exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=scratch, prefix="reading-cost-",
                            suffix=".json", delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(data, output, indent=2)
            output.write("\n")
            output.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("job", nargs="?", help="Measure one job and print its JSON row")
    group.add_argument("--all", action="store_true", help=f"Measure archived jobs and write {OUTPUT}")
    group.add_argument("--report", action="store_true", help="Print the saved snapshot")
    args = parser.parse_args(argv)
    output = ROOT / OUTPUT
    try:
        if args.report:
            report(json.loads(output.read_text(encoding="utf-8")))
            return 0
        data = collect(Repository(ROOT), args.job.upper() if args.job else None)
        if args.all:
            save_snapshot(output, data)
            print(f"Wrote {OUTPUT} ({len(data['jobs'])} archived jobs)")
        else:
            print(json.dumps(data["jobs"][0], indent=2))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
