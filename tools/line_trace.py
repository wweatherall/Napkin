#!/usr/bin/env python3
# runner: none
"""Run a Python test script under sys.settrace and record executed lines and functions.

Traces only files under worker/ and tools/ of the repository (excluding this script),
so FreeCAD's own Python modules and stdlib are never line-traced. Also follows child
Python processes via a temporary sitecustomize.py on PYTHONPATH and child freecadcmd
processes via a FREECAD wrapper script, merging their <out>.child-<pid>.json files
into the parent trace.

Usage:
  python3 tools/line_trace.py --out trace.json worker/test_drawing_ids.py
  freecadcmd -u user.cfg -s system.cfg tools/line_trace.py --pass --out trace.json worker/test_arrays.py
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import re
import runpy
import signal
import stat
import subprocess
import sys
import time
import types

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FREECAD = "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
_CHILD_PID_RE = re.compile(r"\.child-(\d+)\.json$")

_SITECUSTOMIZE_SRC = """\
import atexit
import json
import os
from pathlib import Path
import sys
import time

_child_base = os.environ.get("NAPKIN_TRACE_CHILD_BASE")
_parent_pid = os.environ.get("NAPKIN_TRACE_PARENT_PID")
_root_str = os.environ.get("NAPKIN_TRACE_ROOT")
_mode = os.environ.get("NAPKIN_TRACE_MODE", "line")

if _child_base and _root_str and str(os.getpid()) != _parent_pid and sys.gettrace() is None:
    _tools_dir = str(Path(_root_str) / "tools")
    if _tools_dir not in sys.path:
        sys.path.insert(0, _tools_dir)
    try:
        import line_trace as _lt
    except Exception:
        _lt = None
    if _lt is not None:
        _root = Path(_root_str)
        _tracer = _lt.LineTracer(root=_root, mode=_mode)
        _t0 = time.monotonic()
        sys.settrace(_tracer.trace_call)

        def _napkin_flush_child_trace():
            sys.settrace(None)
            _elapsed = time.monotonic() - _t0
            _out = Path(f"{_child_base}.child-{os.getpid()}.json")
            _script = sys.argv[0] if sys.argv else "<child>"
            try:
                _rel = Path(_script).resolve().relative_to(_root.resolve()).as_posix()
            except Exception:
                _rel = str(_script)
            _payload = _lt.build_trace_payload(_rel, _tracer, _elapsed, root=_root)
            _out.parent.mkdir(parents=True, exist_ok=True)
            _out.write_text(json.dumps(_payload, indent=2) + "\\n", encoding="utf-8")

        atexit.register(_napkin_flush_child_trace)
"""

_FREECAD_WRAPPER_SRC = """\
#!/bin/bash
REAL_FC="${NAPKIN_REAL_FREECAD:-/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd}"
if [ -z "$NAPKIN_TRACE_CHILD_BASE" ] || [ -z "$NAPKIN_TRACE_ROOT" ]; then
  exec "$REAL_FC" "$@"
fi
ARGS=()
SCRIPT=""
for a in "$@"; do
  if [[ "$a" == *.py ]] && [ -z "$SCRIPT" ]; then
    SCRIPT="$a"
    ARGS+=("$NAPKIN_TRACE_ROOT/tools/line_trace.py")
  else
    ARGS+=("$a")
  fi
done
if [ -z "$SCRIPT" ]; then
  exec "$REAL_FC" "$@"
fi
export NAPKIN_TRACE_OUT="${NAPKIN_TRACE_CHILD_BASE}.child-$$.json"
export NAPKIN_TRACE_SCRIPT="$SCRIPT"
unset NAPKIN_TRACE_ARGS
exec "$REAL_FC" "${ARGS[@]}"
"""


def install_trace_hooks(hook_dir: Path, root: Path = ROOT) -> tuple[Path, Path]:
    """Write sitecustomize.py and freecadcmd wrapper into hook_dir.

    Returns (hook_dir, freecad_wrapper_path).
    """
    hook_dir.mkdir(parents=True, exist_ok=True)
    site_path = hook_dir / "sitecustomize.py"
    site_path.write_text(_SITECUSTOMIZE_SRC, encoding="utf-8")
    fc_wrapper = hook_dir / "freecadcmd"
    fc_wrapper.write_text(_FREECAD_WRAPPER_SRC, encoding="utf-8")
    fc_wrapper.chmod(fc_wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook_dir, fc_wrapper


def _resolve_repo_rel(filename: str, root: Path = ROOT) -> str | None:
    """Return 'worker/...' or 'tools/...' relative path if filename is in scope, else None."""
    if not filename or filename.startswith("<"):
        return None
    try:
        resolved = Path(filename).resolve()
        rel = resolved.relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return None
    if not (rel.startswith("worker/") or rel.startswith("tools/")):
        return None
    if rel == "tools/line_trace.py":
        return None
    return rel


def extract_file_structure(path: Path) -> tuple[dict[int, str], dict[int, str], list[str], set[int]]:
    """Return (body_line_to_func, def_line_to_func, all_functions, executable_lines) for a Python file."""
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source, filename=str(path))
    line_to_func: dict[int, str] = {}
    def_line_to_func: dict[int, str] = {}
    all_functions: list[str] = []

    def _visit(node: ast.AST, scope: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                _visit(child, [*scope, child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = ".".join([*scope, child.name])
                all_functions.append(qual)
                def_line_to_func[child.lineno] = qual
                body_start = child.body[0].lineno if child.body else child.lineno
                end = child.end_lineno or body_start
                for ln in range(body_start, end + 1):
                    line_to_func[ln] = qual
                _visit(child, [*scope, child.name])
            else:
                _visit(child, scope)

    _visit(tree, [])

    executable_lines: set[int] = set()
    try:
        code = compile(tree, str(path), "exec")
        stack = [code]
        while stack:
            co = stack.pop()
            for _, _, lineno in co.co_lines():
                if lineno is not None and lineno > 0:
                    executable_lines.add(lineno)
            for const in co.co_consts:
                if isinstance(const, types.CodeType):
                    stack.append(const)
    except SyntaxError:
        pass

    return line_to_func, def_line_to_func, sorted(set(all_functions)), executable_lines


class LineTracer:
    """Fast sys.settrace collector restricted to worker/ and tools/ files."""

    def __init__(self, root: Path = ROOT, mode: str = "line") -> None:
        self.root = root.resolve()
        self.mode = mode
        self._file_cache: dict[str, str | None] = {}
        self.lines_by_file: dict[str, set[int]] = {}
        self.calls_by_file: dict[str, set[int]] = {}
        self._line_tracers: dict[str, object] = {}

    def _get_rel(self, filename: str) -> str | None:
        rel = self._file_cache.get(filename)
        if rel is None and filename not in self._file_cache:
            rel = _resolve_repo_rel(filename, self.root)
            self._file_cache[filename] = rel
        return rel

    def _get_line_tracer(self, rel: str):
        tracer = self._line_tracers.get(rel)
        if tracer is None:
            lines_set = self.lines_by_file.setdefault(rel, set())
            add = lines_set.add

            def _trace_line(frame, event, arg):
                if event == "line":
                    add(frame.f_lineno)
                return _trace_line

            self._line_tracers[rel] = _trace_line
            tracer = _trace_line
        return tracer

    def trace_call(self, frame, event, arg):
        if event != "call":
            return None
        code = frame.f_code
        rel = self._get_rel(code.co_filename)
        if rel is None:
            return None
        if self.mode == "call":
            self.calls_by_file.setdefault(rel, set()).add(code.co_firstlineno)
            return None
        return self._get_line_tracer(rel)


def _sort_lines(lines: set[str] | list[str]) -> list[str]:
    def _key(fl: str) -> tuple[str, int]:
        rel, _, ln = fl.partition(":")
        return (rel, int(ln) if ln.isdigit() else 0)
    return sorted(set(lines), key=_key)


def build_trace_payload(
    test_rel: str,
    tracer: LineTracer,
    elapsed: float,
    root: Path = ROOT,
) -> dict:
    """Convert collected lines/calls into sorted file:line and file:function lists."""
    lines_out: list[str] = []
    funcs_out: set[str] = set()

    source_map = tracer.calls_by_file if tracer.mode == "call" else tracer.lines_by_file
    for rel in sorted(source_map):
        linenos = sorted(source_map[rel])
        if tracer.mode == "line":
            for ln in linenos:
                lines_out.append(f"{rel}:{ln}")
        file_path = root / rel
        if file_path.exists():
            line_to_func, def_line_to_func, _, _ = extract_file_structure(file_path)
            lookup = def_line_to_func if tracer.mode == "call" else line_to_func
            for ln in linenos:
                fn = lookup.get(ln)
                if fn:
                    funcs_out.add(f"{rel}:{fn}")

    return {
        "test": test_rel,
        "mode": tracer.mode,
        "seconds": round(elapsed, 3),
        "line_count": len(lines_out),
        "lines": lines_out,
        "functions": sorted(funcs_out),
    }


def _classify_child_cmd(args: object, root: Path) -> str | None:
    """Return a short label if a subprocess command runs repo/test code, else None.

    Ordinary external tools (git, ls, osascript, etc.) return None so they do not
    trigger children_untraced.
    """
    if isinstance(args, (list, tuple)):
        tokens = [str(a) for a in args]
    elif isinstance(args, (str, os.PathLike)):
        tokens = [str(args)]
    else:
        return None
    if not tokens:
        return None

    exe = Path(tokens[0]).name.lower()
    joined = " ".join(tokens)
    root_str = str(root.resolve())

    if "godot" in exe:
        return "godot"
    if "freecad" in exe:
        return "freecadcmd"
    if exe in ("bash", "sh", "zsh") or tokens[0].endswith(".sh"):
        if ".sh" in joined or "worker/" in joined or "tools/" in joined or "viewport/" in joined:
            return tokens[0] if tokens[0].endswith(".sh") else "shell"
        return None
    if "python" in exe:
        for tok in tokens[1:]:
            if tok.endswith(".py") or "worker/" in tok or "tools/" in tok or root_str in tok:
                return tok
        return None
    if tokens[0].endswith(".py") or tokens[0].endswith(".sh"):
        return tokens[0]
    return None


def merge_child_traces(
    payload: dict,
    child_base: Path,
    spawned_children: list[tuple[int, str]],
) -> dict:
    """Merge <child_base>.child-<pid>.json files into payload and flag untraced children."""
    lines_set = set(payload.get("lines", []))
    funcs_set = set(payload.get("functions", []))
    traced_pids: set[int] = set()

    pattern = f"{child_base.name}.child-*.json"
    for child_path in sorted(child_base.parent.glob(pattern)):
        m = _CHILD_PID_RE.search(child_path.name)
        if m:
            traced_pids.add(int(m.group(1)))
        try:
            child_data = json.loads(child_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        lines_set.update(child_data.get("lines", []))
        funcs_set.update(child_data.get("functions", []))

    untraced = [cmd for pid, cmd in spawned_children if pid not in traced_pids]

    merged = dict(payload)
    merged["lines"] = _sort_lines(lines_set)
    merged["line_count"] = len(merged["lines"])
    merged["functions"] = sorted(funcs_set)
    merged["traced_child_count"] = len(traced_pids)
    if untraced:
        merged["children_untraced"] = True
        merged["untraced_children"] = sorted(set(untraced))
    else:
        merged["children_untraced"] = False
    return merged


def run_traced_script(
    script_path: Path,
    script_args: list[str],
    out_path: Path,
    root: Path = ROOT,
    mode: str = "line",
    hook_dir: Path | None = None,
) -> int:
    """Execute script_path under sys.settrace and write trace JSON to out_path."""
    script_abs = script_path.resolve()
    root_abs = root.resolve()
    try:
        test_rel = script_abs.relative_to(root_abs).as_posix()
    except ValueError:
        test_rel = str(script_path)

    is_child_invocation = bool(_CHILD_PID_RE.search(out_path.name))
    child_base = out_path.with_suffix("")
    spawned_children: list[tuple[int, str]] = []

    saved_env: dict[str, str | None] = {}

    def _set_env(key: str, val: str | None) -> None:
        if key not in saved_env:
            saved_env[key] = os.environ.get(key)
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val

    if not is_child_invocation:
        # Remove stale child traces from previous runs before executing.
        for stale in child_base.parent.glob(f"{child_base.name}.child-*.json"):
            try:
                stale.unlink()
            except OSError:
                pass

        _set_env("NAPKIN_TRACE_CHILD_BASE", str(child_base))
        _set_env("NAPKIN_TRACE_PARENT_PID", str(os.getpid()))
        _set_env("NAPKIN_TRACE_ROOT", str(root_abs))
        _set_env("NAPKIN_TRACE_MODE", mode)

        if hook_dir is not None:
            hook_path, fc_wrapper = install_trace_hooks(hook_dir, root_abs)
            prev_pp = os.environ.get("PYTHONPATH", "")
            pp_parts = [str(hook_path)] + ([prev_pp] if prev_pp else [])
            _set_env("PYTHONPATH", os.pathsep.join(pp_parts))
            if not os.environ.get("NAPKIN_REAL_FREECAD"):
                _set_env("NAPKIN_REAL_FREECAD", os.environ.get("FREECAD", DEFAULT_FREECAD))
            _set_env("FREECAD", str(fc_wrapper))

    orig_popen_init = subprocess.Popen.__init__
    if not is_child_invocation:
        def _tracked_popen_init(self, args, *pargs, **kwargs):
            orig_popen_init(self, args, *pargs, **kwargs)
            label = _classify_child_cmd(args, root_abs)
            if label is not None and getattr(self, "pid", None):
                spawned_children.append((self.pid, label))

        subprocess.Popen.__init__ = _tracked_popen_init

    prev_sigterm = signal.getsignal(signal.SIGTERM)
    if prev_sigterm == signal.SIG_DFL:
        def _handle_sigterm(signum, frame):
            raise SystemExit(128 + signum)
        signal.signal(signal.SIGTERM, _handle_sigterm)

    tracer = LineTracer(root=root_abs, mode=mode)
    old_argv = sys.argv[:]
    script_dir = str(script_abs.parent)
    added_sys_path = False
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
        added_sys_path = True

    sys.argv = [str(script_abs), *script_args]
    exit_code = 0
    t0 = time.monotonic()
    sys.settrace(tracer.trace_call)
    try:
        runpy.run_path(str(script_abs), run_name="__main__")
    except SystemExit as exc:
        if exc.code is None:
            exit_code = 0
        elif isinstance(exc.code, int):
            exit_code = exc.code
        else:
            print(exc.code, file=sys.stderr)
            exit_code = 1
    finally:
        sys.settrace(None)
        elapsed = time.monotonic() - t0
        sys.argv = old_argv
        if added_sys_path and script_dir in sys.path:
            sys.path.remove(script_dir)
        if not is_child_invocation:
            subprocess.Popen.__init__ = orig_popen_init
        if prev_sigterm == signal.SIG_DFL:
            signal.signal(signal.SIGTERM, prev_sigterm)
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

        payload = build_trace_payload(test_rel, tracer, elapsed, root=root_abs)
        if not is_child_invocation:
            payload = merge_child_traces(payload, child_base, spawned_children)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    # freecadcmd keeps its own binary and -u/-s flags in sys.argv before the script path.
    if argv is None:
        self_resolved = Path(__file__).resolve()
        for idx, arg in enumerate(raw_args):
            try:
                if Path(arg).resolve() == self_resolved:
                    raw_args = raw_args[idx + 1:]
                    break
            except OSError:
                continue
    if "--pass" in raw_args:
        raw_args.remove("--pass")

    if not raw_args and os.environ.get("NAPKIN_TRACE_SCRIPT") and os.environ.get("NAPKIN_TRACE_OUT"):
        script_arg = os.environ["NAPKIN_TRACE_SCRIPT"]
        out_arg = os.environ["NAPKIN_TRACE_OUT"]
        mode_arg = os.environ.get("NAPKIN_TRACE_MODE", "line")
        root_arg = os.environ.get("NAPKIN_TRACE_ROOT", str(ROOT))
        hook_arg = os.environ.get("NAPKIN_TRACE_HOOK_DIR")
        extra_raw = os.environ.get("NAPKIN_TRACE_ARGS", "")
        script_args = json.loads(extra_raw) if extra_raw else []
    else:
        parser = argparse.ArgumentParser(description="Run a test script under sys.settrace.")
        parser.add_argument("--out", required=True, help="Output JSON path")
        parser.add_argument("--mode", choices=["line", "call"], default="line", help="Tracing mode")
        parser.add_argument("--root", default=str(ROOT), help="Repository root to restrict tracing")
        parser.add_argument("--hook-dir", default=None, help="Directory for sitecustomize.py and freecadcmd hook")
        parser.add_argument("script", help="Path to the Python test script to run")
        parser.add_argument("script_args", nargs=argparse.REMAINDER, help="Arguments passed to the script")
        args = parser.parse_args(raw_args)
        script_arg = args.script
        out_arg = args.out
        mode_arg = args.mode
        root_arg = args.root
        hook_arg = args.hook_dir
        script_args = list(args.script_args)

    script_path = Path(script_arg)
    if not script_path.is_absolute():
        script_path = (Path.cwd() / script_path).resolve()

    return run_traced_script(
        script_path=script_path,
        script_args=script_args,
        out_path=Path(out_arg),
        root=Path(root_arg),
        mode=mode_arg,
        hook_dir=Path(hook_arg) if hook_arg else None,
    )


if __name__ == "__main__" or (
    __name__ == "line_trace"
    and any(Path(a).name == "line_trace.py" for a in sys.argv[1:])
):
    raise SystemExit(main())
