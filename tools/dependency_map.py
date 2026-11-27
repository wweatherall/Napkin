#!/usr/bin/env python3
"""Generate and check docs/dependency-map.md, and find callers / Touches lines.

  python3 tools/dependency_map.py                           rebuild docs/dependency-map.md
  python3 tools/dependency_map.py --check                   exit 1 if docs/dependency-map.md is missing or stale
  python3 tools/dependency_map.py callers <file>:<func>     list word-boundary call sites across code & tests
  python3 tools/dependency_map.py touches <file>:<func>...  print a ready Touches line (and Tests line)
"""
import ast
import os
import re
import sys
from pathlib import Path

OUTPUT = "docs/dependency-map.md"
HEADER = "<!-- dependency map: built by tools/dependency_map.py; don't edit by hand -->"
FOLDERS = ("viewport", "viewport/tools", "worker", "tools")
EXTENSIONS = {".gd", ".py"}
ALL_CAPS_STEM = re.compile(r"^[A-Z][A-Z0-9_]*$")
MAX_BYTES = 8 * 1024

RES_PATH_RE = re.compile(r'["\'](res://[^"\']+)["\']')
EXTENDS_CLASS_RE = re.compile(r"^\s*extends\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.M)
CLASS_NAME_RE = re.compile(r"^\s*class_name\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.M)
PRELOAD_ALIAS_RE = re.compile(
    r'^\s*const\s+([A-Za-z_][A-Za-z0-9_]*)\s*:?=\s*(?:preload|load)\(\s*["\'](res://[^"\']+)["\']\s*\)',
    re.M,
)
SUBOBJ_NEW_RE = re.compile(
    r"^\s*var\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*([A-Za-z_][A-Za-z0-9_]*))?\s*:?=\s*([A-Za-z_][A-Za-z0-9_]*)\.new\(",
    re.M,
)
SUBOBJ_LOAD_RE = re.compile(
    r'^\s*var\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=]+)?=\s*load\(\s*["\'](res://[^"\']+)["\']\s*\)\.new\(',
    re.M,
)
PROP_FORWARD_RE = re.compile(
    r"^\s*var\s+([A-Za-z_][A-Za-z0-9_]*)\s*:[^\n]*\n\s+get:\s*return\s+([A-Za-z_][A-Za-z0-9_]*)\.",
    re.M,
)
FUNC_FORWARD_RE = re.compile(
    r"^\s*(?:static\s+)?func\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*(?:->\s*[^:]+)?:\s*(?:return\s+)?([A-Za-z_][A-Za-z0-9_]*)\.",
    re.M,
)
M_ATTR_RE = re.compile(r"\bm\.([A-Za-z_][A-Za-z0-9_]*)")


def is_all_caps_wrapper(rel_path: str) -> bool:
    p = Path(rel_path)
    return p.parent.as_posix() == "tools" and bool(ALL_CAPS_STEM.match(p.stem))


def code_files(root: Path) -> list[str]:
    """Return non-test, non-wrapper .gd and .py files in FOLDERS, grouped by folder and sorted."""
    out = []
    for folder in FOLDERS:
        d = root / folder
        if not d.is_dir():
            continue
        items = []
        for f in sorted(d.iterdir(), key=lambda p: p.as_posix()):
            if not f.is_file() or f.suffix not in EXTENSIONS:
                continue
            if f.name.startswith("test_"):
                continue
            rel = f.relative_to(root).as_posix()
            if is_all_caps_wrapper(rel):
                continue
            items.append(rel)
        out.extend(items)
    return out


def repo_code_and_test_files(root: Path) -> list[str]:
    """Return all .gd, .py, and .sh files under viewport/, worker/, and tools/ (including tests)."""
    out = []
    vp = root / "viewport"
    if vp.is_dir():
        for dirpath, dirnames, filenames in os.walk(vp):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for name in sorted(filenames):
                if name.endswith(".gd"):
                    out.append((Path(dirpath) / name).relative_to(root).as_posix())
    for folder in ("worker", "tools"):
        d = root / folder
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir(), key=lambda p: p.as_posix()):
            if f.is_file() and f.suffix in {".py", ".sh"}:
                out.append(f.relative_to(root).as_posix())
    return sorted(out)


def is_test_file(rel_path: str) -> bool:
    name = Path(rel_path).name
    return name.startswith("test_") or rel_path.startswith("viewport/tests/") or rel_path == "viewport/tests.gd"


def short_names(files: list[str]) -> dict[str, str]:
    """Return basename when unique across files, else full relative path."""
    counts: dict[str, int] = {}
    for rel in files:
        base = Path(rel).name
        counts[base] = counts.get(base, 0) + 1
    return {rel: (Path(rel).name if counts[Path(rel).name] == 1 else rel) for rel in files}


def _res_to_rel(res_path: str) -> str:
    return "viewport/" + res_path[len("res://"):]


def parse_main_forwarders(root: Path) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Resolve viewport/main.gd's sub-objects, property forwarders, and function forwarders."""
    main_path = root / "viewport/main.gd"
    if not main_path.is_file():
        return {}, {}, {}
    text = main_path.read_text(encoding="utf-8", errors="replace")

    preload_aliases: dict[str, str] = {}
    for m in PRELOAD_ALIAS_RE.finditer(text):
        preload_aliases[m.group(1)] = _res_to_rel(m.group(2))

    subobjects: dict[str, str] = {}
    for m in SUBOBJ_NEW_RE.finditer(text):
        var_name, _type_ann, cls_name = m.groups()
        if cls_name in preload_aliases:
            subobjects[var_name] = preload_aliases[cls_name]
    for m in SUBOBJ_LOAD_RE.finditer(text):
        var_name, res_path = m.groups()
        subobjects[var_name] = _res_to_rel(res_path)

    forwarded_props: dict[str, str] = {}
    for m in PROP_FORWARD_RE.finditer(text):
        prop_name, target = m.groups()
        if target in subobjects:
            forwarded_props[prop_name] = subobjects[target]

    forwarded_funcs: dict[str, str] = {}
    for m in FUNC_FORWARD_RE.finditer(text):
        func_name, target = m.groups()
        if target in subobjects:
            forwarded_funcs[func_name] = subobjects[target]
        elif target in preload_aliases:
            forwarded_funcs[func_name] = preload_aliases[target]

    return subobjects, forwarded_props, forwarded_funcs


def _python_imports(root: Path, rel_path: str, code_set: set[str]) -> set[str]:
    path = root / rel_path
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text, filename=rel_path)
    except SyntaxError:
        return set()

    folder = Path(rel_path).parent.as_posix()
    deps: set[str] = set()

    def try_resolve(mod_name: str, base_folder: str) -> None:
        parts = mod_name.split(".")
        if len(parts) == 1:
            cand = f"{base_folder}/{parts[0]}.py"
            if cand in code_set:
                deps.add(cand)
        else:
            cand = "/".join(parts) + ".py"
            if cand in code_set:
                deps.add(cand)
            cand_in_folder = f"{base_folder}/" + "/".join(parts) + ".py"
            if cand_in_folder in code_set:
                deps.add(cand_in_folder)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                try_resolve(alias.name, folder)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                if node.module:
                    try_resolve(node.module, folder)
                else:
                    for alias in node.names:
                        try_resolve(alias.name, folder)
            elif node.module:
                try_resolve(node.module, folder)
                for alias in node.names:
                    try_resolve(f"{node.module}.{alias.name}", folder)
    deps.discard(rel_path)
    return deps


def _gd_class_names(root: Path, files: list[str]) -> dict[str, str]:
    classes: dict[str, str] = {}
    for rel in files:
        if not rel.endswith(".gd"):
            continue
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
        for m in CLASS_NAME_RE.finditer(text):
            classes[m.group(1)] = rel
    return classes


def _gd_imports(
    root: Path,
    rel_path: str,
    code_set: set[str],
    class_map: dict[str, str],
    forwarders: tuple[dict[str, str], dict[str, str], dict[str, str]],
) -> set[str]:
    text = (root / rel_path).read_text(encoding="utf-8", errors="replace")
    deps: set[str] = set()

    for m in RES_PATH_RE.finditer(text):
        cand = _res_to_rel(m.group(1))
        if cand in code_set:
            deps.add(cand)

    for m in EXTENDS_CLASS_RE.finditer(text):
        cls = m.group(1)
        if cls in class_map:
            deps.add(class_map[cls])

    for cls, target in class_map.items():
        if target != rel_path and re.search(rf"\b{re.escape(cls)}\b", text):
            deps.add(target)

    if rel_path != "viewport/main.gd":
        subobjects, forwarded_props, forwarded_funcs = forwarders
        for m in M_ATTR_RE.finditer(text):
            attr = m.group(1)
            for table in (subobjects, forwarded_props, forwarded_funcs):
                target = table.get(attr)
                if target and target in code_set:
                    deps.add(target)
                    break

    deps.discard(rel_path)
    return deps


def build_dependency_graph(root: Path) -> tuple[list[str], dict[str, set[str]], dict[str, set[str]]]:
    """Return (files, uses, used_by) for all non-test code files."""
    files = code_files(root)
    code_set = set(files)
    class_map = _gd_class_names(root, files)
    forwarders = parse_main_forwarders(root)

    uses: dict[str, set[str]] = {f: set() for f in files}
    used_by: dict[str, set[str]] = {f: set() for f in files}

    for rel in files:
        if rel.endswith(".py"):
            uses[rel] = _python_imports(root, rel, code_set)
        elif rel.endswith(".gd"):
            uses[rel] = _gd_imports(root, rel, code_set, class_map, forwarders)
        for target in uses[rel]:
            used_by[target].add(rel)

    return files, uses, used_by


def render_map(root: Path) -> str:
    """Render the full docs/dependency-map.md text."""
    files, uses, used_by = build_dependency_graph(root)
    names = short_names(files)

    by_folder: dict[str, list[str]] = {f: [] for f in FOLDERS}
    for rel in files:
        folder = Path(rel).parent.as_posix()
        u_str = ", ".join(sorted((names[d] for d in uses[rel]), key=str.lower)) or "none"
        ub_str = ", ".join(sorted((names[d] for d in used_by[rel]), key=str.lower)) or "none"
        by_folder[folder].append(f"- `{rel}` — uses: {u_str} — used by: {ub_str}")

    sections = [
        HEADER,
        "",
        "# Dependency Map",
        "",
        "Generated by `tools/dependency_map.py`. Covers non-test `.gd` and `.py` files in `viewport/`, `viewport/tools/`, `worker/`, and `tools/` (tests excluded; use `callers` or `touches` to include tests).",
    ]
    for folder in FOLDERS:
        if by_folder[folder]:
            sections.extend(["", f"## {folder}/", "", *by_folder[folder]])
    return "\n".join(sections) + "\n"


def _parse_spec(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise ValueError(f"expected <file>:<function>, got {spec!r}")
    rel_file, func_name = spec.rsplit(":", 1)
    if not rel_file or not func_name:
        raise ValueError(f"expected <file>:<function>, got {spec!r}")
    return rel_file.lstrip("./"), func_name


def _def_pattern(rel_path: str, func_name: str) -> re.Pattern[str] | None:
    esc = re.escape(func_name)
    if rel_path.endswith(".py"):
        return re.compile(rf"^\s*(?:async\s+)?def\s+{esc}\s*\(")
    if rel_path.endswith(".gd"):
        return re.compile(rf"^\s*(?:static\s+)?func\s+{esc}\s*\(")
    return None


def find_definitions(root: Path, func_name: str, files: list[str]) -> dict[str, list[int]]:
    """Return {rel_path: [line_numbers]} for every file defining func_name."""
    defs: dict[str, list[int]] = {}
    for rel in files:
        pat = _def_pattern(rel, func_name)
        if pat is None:
            continue
        lines = (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        hits = [i for i, line in enumerate(lines, 1) if pat.match(line)]
        if hits:
            defs[rel] = hits
    return defs


def find_callers(
    root: Path, target_file: str, func_name: str
) -> tuple[dict[str, list[int]], list[tuple[str, int, str]]]:
    """Return (defs_by_file, [(rel, lineno, line_text)]) for word-boundary matches excluding target_file's def."""
    target_path = root / target_file
    if not target_path.is_file():
        raise FileNotFoundError(f"file not found: {target_file}")

    files = repo_code_and_test_files(root)
    if target_file not in files:
        files = sorted(set(files) | {target_file})

    defs_by_file = find_definitions(root, func_name, files)
    if target_file not in defs_by_file:
        raise ValueError(f"{func_name!r} is not defined in {target_file}")

    target_def_lines = set(defs_by_file[target_file])
    word_re = re.compile(rf"\b{re.escape(func_name)}\b")
    matches: list[tuple[str, int, str]] = []
    for rel in files:
        lines = (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        for lineno, line in enumerate(lines, 1):
            if rel == target_file and lineno in target_def_lines:
                continue
            if word_re.search(line):
                matches.append((rel, lineno, line))
    return defs_by_file, matches


def _shared_def_note(func_name: str, defs_by_file: dict[str, list[int]]) -> str | None:
    if len(defs_by_file) <= 1:
        return None
    names = ", ".join(sorted(defs_by_file))
    return (
        f"note: '{func_name}' is defined in {len(defs_by_file)} files ({names}); "
        "matches below are word-boundary across the repo and may include other definitions."
    )


def cmd_callers(root: Path, spec: str) -> int:
    try:
        target_file, func_name = _parse_spec(spec)
        defs_by_file, matches = find_callers(root, target_file, func_name)
    except (ValueError, FileNotFoundError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    note = _shared_def_note(func_name, defs_by_file)
    if note:
        print(note)
    for rel, lineno, line in matches:
        print(f"{rel}:{lineno}: {line.strip()}")
    return 0


def cmd_touches(root: Path, specs: list[str]) -> int:
    code_funcs: dict[str, list[str]] = {}
    test_funcs: dict[str, list[str]] = {}
    notes: list[str] = []

    def add_func(bucket: dict[str, list[str]], rel: str, func: str) -> None:
        items = bucket.setdefault(rel, [])
        if func not in items:
            items.append(func)

    for spec in specs:
        try:
            target_file, func_name = _parse_spec(spec)
            defs_by_file, matches = find_callers(root, target_file, func_name)
        except (ValueError, FileNotFoundError) as err:
            print(f"error: {err}", file=sys.stderr)
            return 1

        note = _shared_def_note(func_name, defs_by_file)
        if note and note not in notes:
            notes.append(note)

        add_func(test_funcs if is_test_file(target_file) else code_funcs, target_file, func_name)
        for rel, _lineno, _line in matches:
            add_func(test_funcs if is_test_file(rel) else code_funcs, rel, func_name)

    for note in notes:
        print(note)

    def fmt_entries(bucket: dict[str, list[str]]) -> str:
        parts = []
        for rel, funcs in bucket.items():
            fn_list = ", ".join(f"`{fn}`" for fn in funcs)
            parts.append(f"{rel} ({fn_list})")
        return ", ".join(parts)

    print("Touches: " + fmt_entries(code_funcs))
    if test_funcs:
        print("Tests: " + fmt_entries(test_funcs))
    return 0


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path.cwd()

    if args and args[0] == "callers":
        if len(args) != 2:
            print("usage: python3 tools/dependency_map.py callers <file>:<function>", file=sys.stderr)
            return 2
        return cmd_callers(root, args[1])

    if args and args[0] == "touches":
        if len(args) < 2:
            print("usage: python3 tools/dependency_map.py touches <file>:<function> [...]", file=sys.stderr)
            return 2
        return cmd_touches(root, args[1:])

    check_only = "--check" in args
    unknown = [a for a in args if a != "--check"]
    if unknown:
        print("usage: python3 tools/dependency_map.py [--check | callers <f:fn> | touches <f:fn>...]", file=sys.stderr)
        return 2

    rendered = render_map(root)
    out_path = root / OUTPUT
    if check_only:
        if not out_path.is_file() or out_path.read_text(encoding="utf-8") != rendered:
            print(f"{OUTPUT} is out of date; run: python3 tools/dependency_map.py", file=sys.stderr)
            return 1
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not out_path.is_file() or out_path.read_text(encoding="utf-8") != rendered:
        out_path.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
