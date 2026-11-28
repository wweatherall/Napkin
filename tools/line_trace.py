#!/usr/bin/env python3
# runner: none
"""Run a Python test script under sys.settrace and record executed lines and functions.

Traces only files under worker/ and tools/ of the repository (excluding this script),
so FreeCAD's own Python modules and stdlib are never line-traced.

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
import runpy
import sys
import time
import types

ROOT = Path(__file__).resolve().parent.parent


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


def run_traced_script(
    script_path: Path,
    script_args: list[str],
    out_path: Path,
    root: Path = ROOT,
    mode: str = "line",
) -> int:
    """Execute script_path under sys.settrace and write trace JSON to out_path."""
    script_abs = script_path.resolve()
    try:
        test_rel = script_abs.relative_to(root.resolve()).as_posix()
    except ValueError:
        test_rel = str(script_path)

    tracer = LineTracer(root=root, mode=mode)
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
        payload = build_trace_payload(test_rel, tracer, elapsed, root=root)
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
        extra_raw = os.environ.get("NAPKIN_TRACE_ARGS", "")
        script_args = json.loads(extra_raw) if extra_raw else []
    else:
        parser = argparse.ArgumentParser(description="Run a test script under sys.settrace.")
        parser.add_argument("--out", required=True, help="Output JSON path")
        parser.add_argument("--mode", choices=["line", "call"], default="line", help="Tracing mode")
        parser.add_argument("--root", default=str(ROOT), help="Repository root to restrict tracing")
        parser.add_argument("script", help="Path to the Python test script to run")
        parser.add_argument("script_args", nargs=argparse.REMAINDER, help="Arguments passed to the script")
        args = parser.parse_args(raw_args)
        script_arg = args.script
        out_arg = args.out
        mode_arg = args.mode
        root_arg = args.root
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
    )


if __name__ == "__main__" or (
    __name__ == "line_trace"
    and any(Path(a).name == "line_trace.py" for a in sys.argv[1:])
):
    raise SystemExit(main())
