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


def _resolve_py_module(
    rel_path: str, mod_name: str | None, level: int, py_set: set[str]
) -> str | None:
    """Resolve a Python module name (with optional relative level) to a repo .py file."""
    folder_parts = Path(rel_path).parent.parts
    if level > 0:
        up = level - 1
        base_parts = folder_parts[:-up] if up > 0 and up <= len(folder_parts) else folder_parts
        base_folder = "/".join(base_parts)
        if not mod_name:
            return None
        parts = mod_name.split(".")
        cand = f"{base_folder}/" + "/".join(parts) + ".py" if base_folder else "/".join(parts) + ".py"
        return cand if cand in py_set else None

    if not mod_name:
        return None
    parts = mod_name.split(".")
    base_folder = Path(rel_path).parent.as_posix()
    if len(parts) == 1:
        cand = f"{base_folder}/{parts[0]}.py" if base_folder != "." else f"{parts[0]}.py"
        if cand in py_set:
            return cand
    cand_root = "/".join(parts) + ".py"
    if cand_root in py_set:
        return cand_root
    cand_local = f"{base_folder}/" + "/".join(parts) + ".py" if base_folder != "." else cand_root
    if cand_local in py_set:
        return cand_local
    return None


def _py_attr_chain(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _py_attr_chain(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


def _python_callers_in_file(
    root: Path,
    rel_path: str,
    target_file: str,
    func_name: str,
    py_set: set[str],
    local_defs: set[str],
) -> tuple[list[tuple[str, int, str]], list[tuple[str, int, str]]]:
    """Return (resolved, unresolved) call sites of target_file:func_name in a Python file."""
    text = (root / rel_path).read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text, filename=rel_path)
    except SyntaxError:
        return [], []
    lines = text.splitlines()
    resolved: list[tuple[str, int, str]] = []
    unresolved: list[tuple[str, int, str]] = []
    seen_lines: set[tuple[str, int]] = set()

    def record(bucket: list[tuple[str, int, str]], tag: str, lineno: int) -> None:
        key = (tag, lineno)
        if key in seen_lines or not (1 <= lineno <= len(lines)):
            return
        seen_lines.add(key)
        bucket.append((rel_path, lineno, lines[lineno - 1]))

    def visit(
        node: ast.AST,
        mods: dict[str, str],
        syms: dict[str, tuple[str, str]],
        types: dict[str, str],
        class_types: dict[str, str] | None = None,
    ) -> None:
        if isinstance(node, ast.ClassDef):
            mods = dict(mods)
            syms = dict(syms)
            types = dict(types)
            class_types = {}
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            mods = dict(mods)
            syms = dict(syms)
            types = dict(types)
            if class_types:
                types.update(class_types)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                mod_file = _resolve_py_module(rel_path, alias.name, 0, py_set)
                mods[bound] = mod_file if mod_file else f"<ext:{alias.name}>"
        elif isinstance(node, ast.ImportFrom):
            mod_file = _resolve_py_module(rel_path, node.module, node.level, py_set)
            for alias in node.names:
                bound = alias.asname or alias.name
                if mod_file:
                    syms[bound] = (mod_file, alias.name)
                else:
                    sub_name = f"{node.module}.{alias.name}" if node.module else alias.name
                    sub_file = _resolve_py_module(rel_path, sub_name, node.level, py_set)
                    if sub_file:
                        mods[bound] = sub_file
                    else:
                        syms[bound] = (f"<ext:{node.module or ''}>", alias.name)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Name) and node.value.func.id in syms:
                src_file, _sym = syms[node.value.func.id]
                for tgt in node.targets:
                    chain = _py_attr_chain(tgt)
                    if chain:
                        types[chain] = src_file
                        if class_types is not None and chain.startswith("self."):
                            class_types[chain] = src_file
        elif isinstance(node, ast.AnnAssign) and isinstance(node.annotation, ast.Name):
            if node.annotation.id in syms:
                src_file, _sym = syms[node.annotation.id]
                chain = _py_attr_chain(node.target)
                if chain:
                    types[chain] = src_file
                    if class_types is not None and chain.startswith("self."):
                        class_types[chain] = src_file
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id == func_name:
                if func_name in syms:
                    src_file, orig_name = syms[func_name]
                    if src_file == target_file and orig_name == func_name:
                        record(resolved, "res", node.lineno)
                elif rel_path == target_file:
                    record(resolved, "res", node.lineno)
            elif isinstance(fn, ast.Attribute) and fn.attr == func_name:
                val = fn.value
                if isinstance(val, ast.Name):
                    if val.id in mods:
                        if mods[val.id] == target_file:
                            record(resolved, "res", node.lineno)
                    elif val.id in types:
                        if types[val.id] == target_file:
                            record(resolved, "res", node.lineno)
                    elif val.id in ("self", "cls"):
                        if rel_path == target_file:
                            record(resolved, "res", node.lineno)
                        elif rel_path not in local_defs:
                            record(unresolved, "unres", node.lineno)
                    else:
                        record(unresolved, "unres", node.lineno)
                elif isinstance(val, ast.Attribute):
                    chain = _py_attr_chain(val)
                    if chain and (chain in types or (class_types and chain in class_types)):
                        tfile = types.get(chain) or (class_types.get(chain) if class_types else None)
                        if tfile == target_file:
                            record(resolved, "res", node.lineno)
                    else:
                        record(unresolved, "unres", node.lineno)
                elif (
                    isinstance(val, ast.Call)
                    and isinstance(val.func, ast.Name)
                    and val.func.id == "__import__"
                    and val.args
                    and isinstance(val.args[0], ast.Constant)
                    and isinstance(val.args[0].value, str)
                ):
                    mod_file = _resolve_py_module(rel_path, val.args[0].value, 0, py_set)
                    if mod_file == target_file:
                        record(resolved, "res", node.lineno)
                else:
                    record(unresolved, "unres", node.lineno)

        for child in ast.iter_child_nodes(node):
            visit(child, mods, syms, types, class_types)

    visit(tree, {}, {}, {})
    return resolved, unresolved


def _strip_gd_comments_and_strings(text: str) -> list[str]:
    """Blank out GDScript comments and string contents while preserving line numbers."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "#":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
        elif text.startswith('"""', i) or text.startswith("'''", i):
            quote = text[i : i + 3]
            out.extend([" ", " ", " "])
            i += 3
            while i < n and not text.startswith(quote, i):
                if text[i] == "\\" and i + 1 < n:
                    out.append(" ")
                    out.append("\n" if text[i + 1] == "\n" else " ")
                    i += 2
                else:
                    out.append("\n" if text[i] == "\n" else " ")
                    i += 1
            if i < n:
                out.extend([" ", " ", " "])
                i += 3
        elif ch in ('"', "'"):
            quote = ch
            out.append(" ")
            i += 1
            while i < n and text[i] != quote and text[i] != "\n":
                if text[i] == "\\" and i + 1 < n:
                    out.append(" ")
                    out.append("\n" if text[i + 1] == "\n" else " ")
                    i += 2
                else:
                    out.append(" ")
                    i += 1
            if i < n and text[i] == quote:
                out.append(" ")
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out).splitlines()


GD_EXTENDS_PATH_RE = re.compile(r'^\s*extends\s+["\'](res://[^"\']+)["\']', re.M)
GD_VAR_TYPE_RE = re.compile(r"^\s*var\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_\.]*)")
GD_VAR_NEW_RE = re.compile(
    r"^\s*(?:var\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=]+)?=\s*([A-Za-z_][A-Za-z0-9_\.]*)\.new\(",
    re.M,
)
GD_VAR_LOAD_NEW_RE = re.compile(
    r'^\s*(?:var\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=]+)?=\s*(?:preload|load)\(\s*["\'](res://[^"\']+)["\']\s*\)\.new\(',
    re.M,
)
GD_PARAM_TYPE_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_\.]*)")
GD_INNER_CLASS_RE = re.compile(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)\b")
GD_DICT_PAIR_RE = re.compile(r'["\']([A-Za-z_][A-Za-z0-9_]*)["\']\s*:\s*([A-Za-z_][A-Za-z0-9_]*)')
GD_PARTS_GET_RE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*parts\.get\(\s*["\']([A-Za-z_][A-Za-z0-9_]*)["\']')
GD_METHOD_FWD_RE = re.compile(
    r"^\s*(?:static\s+)?func\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*(?:->\s*[^:]+)?:\s*(?:\n\s+)?return\s+([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.M,
)


def _build_gd_env(
    root: Path,
    gd_files: list[str],
    forwarders: tuple[dict[str, str], dict[str, str], dict[str, str]],
) -> dict[str, dict]:
    """Build per-file GDScript type/alias environments, inheritance, and capability forwarders."""
    class_map = _gd_class_names(root, gd_files)
    envs: dict[str, dict] = {}
    raw_texts: dict[str, str] = {}

    for rel in gd_files:
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
        raw_texts[rel] = text
        aliases: dict[str, str] = {}
        for m in PRELOAD_ALIAS_RE.finditer(text):
            aliases[m.group(1)] = _res_to_rel(m.group(2))

        parent: str | None = None
        m_ext = GD_EXTENDS_PATH_RE.search(text)
        if m_ext:
            parent = _res_to_rel(m_ext.group(1))
        else:
            m_cls = EXTENDS_CLASS_RE.search(text)
            if m_cls and m_cls.group(1) in class_map:
                parent = class_map[m_cls.group(1)]

        inner_classes: set[str] = set()
        for line in text.splitlines():
            m_ic = GD_INNER_CLASS_RE.match(line)
            if m_ic:
                inner_classes.add(m_ic.group(1))

        envs[rel] = {
            "aliases": aliases,
            "parent": parent,
            "inner_classes": inner_classes,
            "vars": {},  # var_name -> rel_file or (rel_file, inner_class)
            "cap_forwards": {},  # (inner_class, func_name) -> target_file
        }

    def resolve_type(rel: str, type_expr: str) -> str | tuple[str, str] | None:
        env = envs[rel]
        if "." in type_expr:
            outer, inner = type_expr.split(".", 1)
            outer_file = env["aliases"].get(outer) or class_map.get(outer)
            if outer_file and outer_file in envs and inner in envs[outer_file]["inner_classes"]:
                return (outer_file, inner)
            return None
        if type_expr in env["inner_classes"]:
            return (rel, type_expr)
        if type_expr in env["aliases"]:
            return env["aliases"][type_expr]
        if type_expr in class_map:
            return class_map[type_expr]
        return None

    for rel, text in raw_texts.items():
        vars_map = envs[rel]["vars"]
        for m in GD_VAR_TYPE_RE.finditer(text):
            resolved = resolve_type(rel, m.group(2))
            if resolved:
                vars_map[m.group(1)] = resolved
        for m in GD_VAR_NEW_RE.finditer(text):
            resolved = resolve_type(rel, m.group(2))
            if resolved:
                vars_map[m.group(1)] = resolved
        for m in GD_VAR_LOAD_NEW_RE.finditer(text):
            vars_map[m.group(1)] = _res_to_rel(m.group(2))
        for m in GD_PARAM_TYPE_RE.finditer(text):
            resolved = resolve_type(rel, m.group(2))
            if resolved:
                vars_map.setdefault(m.group(1), resolved)

    # Infer capability parts mapping from ToolContext.new({...}) / Capability.new({...})
    parts_key_types: dict[str, str] = {}
    for rel, text in raw_texts.items():
        vars_map = envs[rel]["vars"]
        for m in GD_DICT_PAIR_RE.finditer(text):
            key, val_var = m.group(1), m.group(2)
            t = vars_map.get(val_var)
            if isinstance(t, str):
                parts_key_types.setdefault(key, t)

    # Resolve inner class capability forwarders (e.g. DocumentCapability._doc -> document.gd)
    for rel, text in raw_texts.items():
        lines = text.splitlines()
        cur_inner: str | None = None
        inner_vars: dict[str, str] = {}
        block_lines: list[str] = []
        for line in lines + ["class _END"]:
            m_ic = GD_INNER_CLASS_RE.match(line)
            if m_ic:
                if cur_inner:
                    block_text = "\n".join(_strip_gd_comments_and_strings("\n".join(block_lines)))
                    for m_fwd in GD_METHOD_FWD_RE.finditer(block_text):
                        fn_name, obj_var, tgt_fn = m_fwd.groups()
                        if obj_var in inner_vars and fn_name == tgt_fn:
                            envs[rel]["cap_forwards"][(cur_inner, fn_name)] = inner_vars[obj_var]
                cur_inner = m_ic.group(1)
                inner_vars = {}
                block_lines = []
                continue
            if cur_inner:
                block_lines.append(line)
                m_pg = GD_PARTS_GET_RE.match(line)
                if m_pg and m_pg.group(2) in parts_key_types:
                    inner_vars[m_pg.group(1)] = parts_key_types[m_pg.group(2)]
                    envs[rel]["vars"].setdefault(m_pg.group(1), parts_key_types[m_pg.group(2)])

    return envs


def _gd_lookup_var(envs: dict[str, dict], rel: str, name: str) -> str | tuple[str, str] | None:
    cur: str | None = rel
    seen: set[str] = set()
    while cur and cur in envs and cur not in seen:
        seen.add(cur)
        env = envs[cur]
        if name in env["vars"]:
            return env["vars"][name]
        if name in env["aliases"]:
            return env["aliases"][name]
        cur = env["parent"]
    return None


def _gd_extends(envs: dict[str, dict], rel: str, target_file: str) -> bool:
    cur: str | None = rel
    seen: set[str] = set()
    while cur and cur in envs and cur not in seen:
        if cur == target_file:
            return True
        seen.add(cur)
        cur = envs[cur]["parent"]
    return False


def _gd_callers_in_file(
    root: Path,
    rel_path: str,
    target_file: str,
    func_name: str,
    envs: dict[str, dict],
    forwarders: tuple[dict[str, str], dict[str, str], dict[str, str]],
) -> tuple[list[tuple[str, int, str]], list[tuple[str, int, str]]]:
    text = (root / rel_path).read_text(encoding="utf-8", errors="replace")
    raw_lines = text.splitlines()
    stripped_lines = _strip_gd_comments_and_strings(text)
    def_pat = _def_pattern(rel_path, func_name)
    esc = re.escape(func_name)
    call_re = re.compile(rf"(?:([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\.)?\b{esc}\s*\(")

    subobjects, forwarded_props, forwarded_funcs = forwarders
    resolved: list[tuple[str, int, str]] = []
    unresolved: list[tuple[str, int, str]] = []

    for lineno, sline in enumerate(stripped_lines, 1):
        if def_pat and def_pat.match(raw_lines[lineno - 1]):
            continue
        for m in call_re.finditer(sline):
            receiver = m.group(1)
            if receiver is None and m.start() > 0 and sline[m.start() - 1] == ".":
                unresolved.append((rel_path, lineno, raw_lines[lineno - 1]))
                break

            status: str | None = None  # "resolved", "unresolved", "ignore"
            if receiver is None or receiver == "self":
                status = "resolved" if _gd_extends(envs, rel_path, target_file) else "ignore"
            elif receiver.startswith("m.") and rel_path != "viewport/main.gd":
                parts = receiver.split(".")
                attr = parts[1]
                tgt = subobjects.get(attr) or forwarded_props.get(attr) or forwarded_funcs.get(attr)
                if tgt:
                    status = "resolved" if tgt == target_file else "ignore"
                else:
                    status = "unresolved"
            elif "." not in receiver:
                typ = _gd_lookup_var(envs, rel_path, receiver)
                if isinstance(typ, str):
                    status = "resolved" if typ == target_file else "ignore"
                elif isinstance(typ, tuple):
                    cap_file, cap_cls = typ
                    fwd_tgt = envs.get(cap_file, {}).get("cap_forwards", {}).get((cap_cls, func_name))
                    if fwd_tgt == target_file or cap_file == target_file:
                        status = "resolved"
                    else:
                        status = "ignore"
                else:
                    status = "unresolved"
            else:
                parts = receiver.split(".")
                if len(parts) == 2:
                    base, prop = parts
                    base_typ = _gd_lookup_var(envs, rel_path, base)
                    if isinstance(base_typ, str) and base_typ in envs:
                        prop_typ = _gd_lookup_var(envs, base_typ, prop)
                        if isinstance(prop_typ, str):
                            status = "resolved" if prop_typ == target_file else "ignore"
                        elif isinstance(prop_typ, tuple):
                            cap_file, cap_cls = prop_typ
                            fwd_tgt = envs.get(cap_file, {}).get("cap_forwards", {}).get((cap_cls, func_name))
                            if fwd_tgt == target_file or cap_file == target_file:
                                status = "resolved"
                            else:
                                status = "ignore"
                        else:
                            status = "unresolved"
                    else:
                        status = "unresolved"
                else:
                    status = "unresolved"

            if status == "resolved":
                resolved.append((rel_path, lineno, raw_lines[lineno - 1]))
                break
            if status == "unresolved":
                unresolved.append((rel_path, lineno, raw_lines[lineno - 1]))
                break

    return resolved, unresolved


def find_callers(
    root: Path, target_file: str, func_name: str
) -> tuple[dict[str, list[int]], list[tuple[str, int, str]], list[tuple[str, int, str]]]:
    """Return (defs_by_file, resolved_calls, unresolved_calls) for target_file:func_name."""
    target_path = root / target_file
    if not target_path.is_file():
        raise FileNotFoundError(f"file not found: {target_file}")

    files = repo_code_and_test_files(root)
    if target_file not in files:
        files = sorted(set(files) | {target_file})

    defs_by_file = find_definitions(root, func_name, files)
    if target_file not in defs_by_file:
        raise ValueError(f"{func_name!r} is not defined in {target_file}")

    resolved: list[tuple[str, int, str]] = []
    unresolved: list[tuple[str, int, str]] = []

    if target_file.endswith(".py"):
        py_files = [f for f in files if f.endswith(".py")]
        py_set = set(py_files)
        local_defs = set(defs_by_file)
        for rel in py_files:
            res, unres = _python_callers_in_file(root, rel, target_file, func_name, py_set, local_defs)
            resolved.extend(res)
            unresolved.extend(unres)
    elif target_file.endswith(".gd"):
        gd_files = [f for f in files if f.endswith(".gd")]
        forwarders = parse_main_forwarders(root)
        envs = _build_gd_env(root, gd_files, forwarders)
        for rel in gd_files:
            res, unres = _gd_callers_in_file(root, rel, target_file, func_name, envs, forwarders)
            resolved.extend(res)
            unresolved.extend(unres)

    return defs_by_file, resolved, unresolved


def _shared_def_note(target_file: str, func_name: str, defs_by_file: dict[str, list[int]]) -> str | None:
    if len(defs_by_file) <= 1:
        return None
    names = ", ".join(sorted(defs_by_file))
    return (
        f"note: '{func_name}' is defined in {len(defs_by_file)} files ({names}); "
        f"showing qualified calls to {target_file}."
    )


def cmd_callers(root: Path, spec: str) -> int:
    try:
        target_file, func_name = _parse_spec(spec)
        defs_by_file, resolved, unresolved = find_callers(root, target_file, func_name)
    except (ValueError, FileNotFoundError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    note = _shared_def_note(target_file, func_name, defs_by_file)
    if note:
        print(note)
    for rel, lineno, line in resolved:
        print(f"{rel}:{lineno}: {line.strip()}")
    if unresolved:
        print("Unresolved (check by hand):")
        for rel, lineno, line in unresolved:
            print(f"  {rel}:{lineno}: {line.strip()}")
    return 0


def cmd_touches(root: Path, specs: list[str]) -> int:
    code_funcs: dict[str, list[str]] = {}
    test_funcs: dict[str, list[str]] = {}
    unres_lines: dict[str, dict[str, list[int]]] = {}
    notes: list[str] = []

    def add_func(bucket: dict[str, list[str]], rel: str, func: str) -> None:
        items = bucket.setdefault(rel, [])
        if func not in items:
            items.append(func)

    for spec in specs:
        try:
            target_file, func_name = _parse_spec(spec)
            defs_by_file, resolved, unresolved = find_callers(root, target_file, func_name)
        except (ValueError, FileNotFoundError) as err:
            print(f"error: {err}", file=sys.stderr)
            return 1

        note = _shared_def_note(target_file, func_name, defs_by_file)
        if note and note not in notes:
            notes.append(note)

        add_func(test_funcs if is_test_file(target_file) else code_funcs, target_file, func_name)
        for rel, _lineno, _line in resolved:
            add_func(test_funcs if is_test_file(rel) else code_funcs, rel, func_name)
        for rel, lineno, _line in unresolved:
            unres_lines.setdefault(rel, {}).setdefault(func_name, []).append(lineno)

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
    if unres_lines:
        unres_parts = []
        for rel, fn_map in unres_lines.items():
            fn_strs = [f"`{fn}`:" + ",".join(str(n) for n in nums) for fn, nums in fn_map.items()]
            unres_parts.append(f"{rel} ({', '.join(fn_strs)})")
        print("Unresolved (check by hand): " + ", ".join(unres_parts))
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
