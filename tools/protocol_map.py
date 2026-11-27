#!/usr/bin/env python3
"""Generate and check the protocol message table and references in docs/protocol.md (H169).

  python3 tools/protocol_map.py          rebuild the marked section in docs/protocol.md
  python3 tools/protocol_map.py --check  exit 1 if stale, out of sync with code, or examples/refs fail
"""
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROTOCOL_DOC = "docs/protocol.md"
SERVE_PY = "worker/serve.py"
START = "<!-- protocol map: built by tools/protocol_map.py; don't edit by hand -->"
END = "<!-- end protocol map -->"


@dataclass
class MessageSpec:
    name: str
    kind: str  # "command" or "event"
    req_fields: list[str] = field(default_factory=list)
    reply_keys: list[str] = field(default_factory=list)
    spreads: dict[str, set[str]] = field(default_factory=dict)
    handler: str = ""
    reply_builder: str = ""
    accepts_delay: bool = False


def _str_const(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _int_const(node: ast.AST) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    return None


def _collect_py_symbols(tree: ast.Module) -> tuple[dict[str, ast.AST], set[str]]:
    """Return (qualified_fn_nodes, all_symbol_names) for a Python AST."""
    fns: dict[str, ast.AST] = {}
    symbols: set[str] = set()

    def visit(node: ast.AST, prefix: str = "") -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qname = f"{prefix}.{child.name}" if prefix else child.name
                fns[qname] = child
                symbols.add(child.name)
                symbols.add(qname)
                visit(child, qname)
            elif isinstance(child, ast.ClassDef):
                qname = f"{prefix}.{child.name}" if prefix else child.name
                symbols.add(child.name)
                symbols.add(qname)
                visit(child, qname)
            elif isinstance(child, ast.Assign):
                for t in child.targets:
                    if isinstance(t, ast.Name):
                        qname = f"{prefix}.{t.id}" if prefix else t.id
                        symbols.add(t.id)
                        symbols.add(qname)
                    elif isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name):
                        symbols.add(f"{t.value.id}.{t.attr}")
            elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                symbols.add(child.target.id)

    visit(tree)
    return fns, symbols


def _find_protocol_version(tree: ast.Module) -> int | None:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "PROTOCOL_VERSION":
                    val = _int_const(node.value)
                    if val is not None:
                        return val
    return None


def _find_imports(tree: ast.Module, base_dir: Path) -> dict[str, Path]:
    """Map imported local module names to their .py paths."""
    mods: dict[str, Path] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                cand = base_dir / f"{alias.name}.py"
                if cand.is_file():
                    mods[alias.asname or alias.name] = cand
        elif isinstance(node, ast.ImportFrom) and node.module:
            cand = base_dir / f"{node.module}.py"
            if cand.is_file():
                for alias in node.names:
                    mods[alias.asname or alias.name] = cand
    return mods


def _merge_key(keys: list[str], seen_keys: set[str], key: str) -> None:
    if key not in seen_keys:
        seen_keys.add(key)
        keys.append(key)


def _extract_dict_from_expr(
    expr: ast.AST,
    env_dicts: dict[str, tuple[list[str], dict[str, set[str]]]],
    fn_map: dict[str, ast.AST],
    mod_fns: dict[str, tuple[Path, dict[str, ast.AST]]],
    visited_fns: set[str],
) -> tuple[list[str], dict[str, set[str]], str]:
    """Extract (ordered_keys, spread_map, unresolvable_builder) from a dict-building AST expression."""
    keys: list[str] = []
    seen: set[str] = set()
    spreads: dict[str, set[str]] = {}
    builder = ""

    if isinstance(expr, ast.Dict):
        for k, v in zip(expr.keys, expr.values):
            if k is None:
                if isinstance(v, ast.Name):
                    _merge_key(keys, seen, f"**{v.id}")
                    spreads.setdefault(v.id, set()).update(env_dicts.get(v.id, ([], {}))[0])
                elif isinstance(v, ast.Call):
                    sub_k, sub_s, sub_b = _extract_dict_from_expr(v, env_dicts, fn_map, mod_fns, visited_fns)
                    for sk in sub_k:
                        _merge_key(keys, seen, sk)
                    spreads.update(sub_s)
                    if sub_b and not sub_k:
                        builder = sub_b
            else:
                s = _str_const(k)
                if s is not None:
                    _merge_key(keys, seen, s)
        return keys, spreads, builder

    if isinstance(expr, ast.Name):
        if expr.id in env_dicts:
            ek, es = env_dicts[expr.id]
            for k in ek:
                _merge_key(keys, seen, k)
            spreads.update(es)
        return keys, spreads, builder

    if isinstance(expr, ast.Call):
        func = expr.func
        if isinstance(func, ast.Name) and func.id == "dict":
            if expr.args:
                ak, as_, ab = _extract_dict_from_expr(expr.args[0], env_dicts, fn_map, mod_fns, visited_fns)
                for k in ak:
                    _merge_key(keys, seen, k)
                spreads.update(as_)
                if ab and not ak:
                    builder = ab
            for kw in expr.keywords:
                if kw.arg is None:
                    if isinstance(kw.value, ast.Name):
                        _merge_key(keys, seen, f"**{kw.value.id}")
                        spreads.setdefault(kw.value.id, set()).update(
                            env_dicts.get(kw.value.id, ([], {}))[0]
                        )
                    elif isinstance(kw.value, ast.Call):
                        sk, ss, _ = _extract_dict_from_expr(kw.value, env_dicts, fn_map, mod_fns, visited_fns)
                        for k in sk:
                            _merge_key(keys, seen, k)
                        spreads.update(ss)
                else:
                    _merge_key(keys, seen, kw.arg)
            return keys, spreads, builder

        fn_name = None
        target_fn = None
        target_map = fn_map
        if isinstance(func, ast.Name) and func.id in fn_map:
            fn_name = func.id
            target_fn = fn_map[fn_name]
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            mod_name = func.value.id
            if mod_name in mod_fns:
                _, m_fns = mod_fns[mod_name]
                if func.attr in m_fns:
                    fn_name = f"{mod_name}.{func.attr}"
                    target_fn = m_fns[func.attr]
                    target_map = m_fns

        if target_fn is not None and fn_name is not None:
            if fn_name in visited_fns:
                return keys, spreads, fn_name
            fk, fs = _extract_fn_return_keys(target_fn, target_map, mod_fns, visited_fns | {fn_name})
            if fk:
                for k in fk:
                    _merge_key(keys, seen, k)
                spreads.update(fs)
            else:
                builder = fn_name
            return keys, spreads, builder

        if isinstance(func, ast.Name):
            return keys, spreads, func.id
        if isinstance(func, ast.Attribute):
            return keys, spreads, func.attr

    return keys, spreads, builder


def _extract_fn_return_keys(
    fn_node: ast.AST,
    fn_map: dict[str, ast.AST],
    mod_fns: dict[str, tuple[Path, dict[str, ast.AST]]],
    visited_fns: set[str],
) -> tuple[list[str], dict[str, set[str]]]:
    """Collect keys of dict literals returned by a function, marking conditional subscripts with `?`."""
    keys: list[str] = []
    seen: set[str] = set()
    spreads: dict[str, set[str]] = {}
    env_dicts: dict[str, tuple[list[str], dict[str, set[str]]]] = {}

    def walk_stmts(stmts: list[ast.stmt], in_if: bool = False) -> None:
        for st in stmts:
            if isinstance(st, ast.Assign):
                if len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
                    vname = st.targets[0].id
                    dk, ds, _ = _extract_dict_from_expr(st.value, env_dicts, fn_map, mod_fns, visited_fns)
                    if dk:
                        env_dicts[vname] = (dk, ds)
                for t in st.targets:
                    subs = [t] if isinstance(t, ast.Subscript) else (
                        list(t.elts) if isinstance(t, ast.Tuple) else []
                    )
                    for sub in subs:
                        if isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name):
                            k = _str_const(sub.slice)
                            if k is not None and sub.value.id in env_dicts:
                                ek, es = env_dicts[sub.value.id]
                                label = f"{k}?" if in_if and k not in ek else k
                                if k not in ek and label not in ek:
                                    ek.append(label)
                                env_dicts[sub.value.id] = (ek, es)
            elif isinstance(st, ast.Return) and st.value is not None:
                rk, rs, _ = _extract_dict_from_expr(st.value, env_dicts, fn_map, mod_fns, visited_fns)
                for k in rk:
                    _merge_key(keys, seen, k)
                spreads.update(rs)
            elif isinstance(st, ast.If):
                walk_stmts(st.body, True)
                walk_stmts(st.orelse, True)
            elif isinstance(st, ast.Try):
                walk_stmts(st.body, in_if)
                for h in st.handlers:
                    walk_stmts(h.body, True)
                walk_stmts(st.orelse, in_if)
                walk_stmts(st.finalbody, in_if)
            elif isinstance(st, (ast.For, ast.While, ast.With)):
                walk_stmts(st.body, True)

    walk_stmts(getattr(fn_node, "body", []), False)
    return keys, spreads


def _extract_req_fields(
    nodes: list[ast.AST],
    req_names: set[str],
    fn_map: dict[str, ast.AST],
    mod_fns: dict[str, tuple[Path, dict[str, ast.AST]]],
    visited: set[str] | None = None,
) -> list[str]:
    """Find req.get('x') and req['x'] fields in statements, following helper calls that take req."""
    if visited is None:
        visited = set()
    fields: list[str] = []
    seen: set[str] = set()

    def add(name: str, optional: bool) -> None:
        if name == "cmd":
            return
        label = f"{name}?" if optional else name
        # Upgrade optional to required if seen as required, or keep first seen
        if name in seen:
            if not optional and f"{name}?" in fields:
                fields[fields.index(f"{name}?")] = name
            return
        seen.add(name)
        fields.append(label)

    for root_node in nodes:
        for node in ast.walk(root_node):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in req_names
                and node.args
            ):
                k = _str_const(node.args[0])
                if k is not None:
                    add(k, True)
            elif (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and node.value.id in req_names
            ):
                k = _str_const(node.slice)
                if k is not None:
                    add(k, False)
            elif isinstance(node, ast.Call):
                # Follow calls passing req
                passes_req = any(isinstance(a, ast.Name) and a.id in req_names for a in node.args)
                if not passes_req:
                    continue
                target_fn = None
                t_name = None
                t_map = fn_map
                if isinstance(node.func, ast.Name) and node.func.id in fn_map:
                    t_name = node.func.id
                    target_fn = fn_map[t_name]
                elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    mname = node.func.value.id
                    if mname in mod_fns and node.func.attr in mod_fns[mname][1]:
                        t_name = f"{mname}.{node.func.attr}"
                        t_map = mod_fns[mname][1]
                        target_fn = t_map[node.func.attr]
                if target_fn is not None and t_name not in visited:
                    visited.add(t_name)
                    arg_names = {
                        p.arg
                        for p, a in zip(target_fn.args.args, node.args)
                        if isinstance(a, ast.Name) and a.id in req_names
                    }
                    if arg_names:
                        for f in _extract_req_fields(target_fn.body, arg_names, t_map, mod_fns, visited):
                            add(f.rstrip("?"), f.endswith("?"))
    return fields


def _match_cmd_condition(test: ast.AST) -> list[str]:
    """Match `cmd == 'x'` or `cmd in ('a', 'b')`."""
    if isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "cmd":
        if len(test.ops) == 1 and len(test.comparators) == 1:
            op = test.ops[0]
            comp = test.comparators[0]
            if isinstance(op, ast.Eq):
                s = _str_const(comp)
                return [s] if s is not None else []
            if isinstance(op, ast.In) and isinstance(comp, (ast.Tuple, ast.List, ast.Set)):
                vals = [_str_const(e) for e in comp.elts]
                if all(v is not None for v in vals):
                    return [v for v in vals if v is not None]
    return []


def _extract_sends(
    stmts: list[ast.stmt],
    env_dicts: dict[str, tuple[list[str], dict[str, set[str]]]],
    fn_map: dict[str, ast.AST],
    mod_fns: dict[str, tuple[Path, dict[str, ast.AST]]],
) -> list[tuple[list[str], dict[str, set[str]], str, str | None]]:
    """Find send(conn, payload) and answer(conn, cmd, seq, saves, **extra) calls.
    Returns list of (keys, spreads, builder_name, literal_cmd_if_any).
    """
    out: list[tuple[list[str], dict[str, set[str]], str, str | None]] = []

    def scan(block: list[ast.stmt], local_env: dict[str, tuple[list[str], dict[str, set[str]]]]) -> None:
        for st in block:
            if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
                dk, ds, _ = _extract_dict_from_expr(st.value, local_env, fn_map, mod_fns, set())
                if dk:
                    local_env[st.targets[0].id] = (dk, ds)

            if isinstance(st, ast.If):
                scan(st.body, dict(local_env))
                scan(st.orelse, dict(local_env))
                continue
            if isinstance(st, (ast.For, ast.While, ast.With)):
                scan(st.body, dict(local_env))
                continue
            if isinstance(st, ast.Try):
                scan(st.body, dict(local_env))
                for h in st.handlers:
                    scan(h.body, dict(local_env))
                scan(st.orelse, dict(local_env))
                scan(st.finalbody, dict(local_env))
                continue

            for node in ast.walk(st):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                    continue
                if node.func.id == "send" and len(node.args) >= 2:
                    payload = node.args[1]
                    dk, ds, db = _extract_dict_from_expr(payload, local_env, fn_map, mod_fns, set())
                    lit_cmd = None
                    if isinstance(payload, ast.Dict):
                        for k, v in zip(payload.keys, payload.values):
                            if _str_const(k) == "cmd":
                                lit_cmd = _str_const(v)
                    elif isinstance(payload, ast.Call) and isinstance(payload.func, ast.Name) and payload.func.id == "dict":
                        for kw in payload.keywords:
                            if kw.arg == "cmd":
                                lit_cmd = _str_const(kw.value)
                    out.append((dk, ds, db, lit_cmd))
                elif node.func.id == "answer" and len(node.args) >= 4:
                    # answer(conn, cmd, seq, saves, **extra)
                    ans_fn = fn_map.get("serve.answer")
                    ak, as_ = (
                        _extract_fn_return_keys(ans_fn, fn_map, mod_fns, {"serve.answer"})
                        if ans_fn
                        else (["ok", "cmd", "seq", "**saves", "error?"], {})
                    )
                    # Extract keys from answer's send(conn, resp) if answer doesn't return
                    if not ak and ans_fn is not None:
                        ak, as_ = _extract_answer_keys(ans_fn, fn_map, mod_fns)
                    for kw in node.keywords:
                        if kw.arg and kw.arg not in ak:
                            ak.append(kw.arg)
                    lit_cmd = _str_const(node.args[1])
                    out.append((ak, as_, "", lit_cmd))

    scan(stmts, dict(env_dicts))
    return out


def _extract_answer_keys(
    ans_fn: ast.AST,
    fn_map: dict[str, ast.AST],
    mod_fns: dict[str, tuple[Path, dict[str, ast.AST]]],
) -> tuple[list[str], dict[str, set[str]]]:
    keys: list[str] = []
    seen: set[str] = set()
    spreads: dict[str, set[str]] = {}
    env: dict[str, tuple[list[str], dict[str, set[str]]]] = {}
    for st in getattr(ans_fn, "body", []):
        if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
            dk, ds, _ = _extract_dict_from_expr(st.value, env, fn_map, mod_fns, set())
            if dk:
                env[st.targets[0].id] = (dk, ds)
        elif isinstance(st, ast.If):
            for sub in st.body:
                if isinstance(sub, ast.Assign):
                    for t in sub.targets:
                        if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id in env:
                            k = _str_const(t.slice)
                            if k:
                                env[t.value.id][0].append(f"{k}?")
    for dk, ds in env.values():
        for k in dk:
            _merge_key(keys, seen, k)
        spreads.update(ds)
    return keys, spreads


def _known_spreads(root: Path, fn_map: dict[str, ast.AST], mod_fns: dict[str, tuple[Path, dict[str, ast.AST]]]) -> dict[str, set[str]]:
    """Resolve common spread dicts (saves from save_pending, info from Session.reload_outside)."""
    spreads: dict[str, set[str]] = {}
    if "serve.save_pending" in fn_map:
        sk, _ = _extract_fn_return_keys(fn_map["serve.save_pending"], fn_map, mod_fns, set())
        if sk:
            spreads["saves"] = {k.rstrip("?") for k in sk}
    # Check session.py for reload_outside if present
    sess_py = root / "worker/session.py"
    if sess_py.is_file():
        stree = ast.parse(sess_py.read_text(encoding="utf-8"), filename=str(sess_py))
        sfns, _ = _collect_py_symbols(stree)
        if "Session.reload_outside" in sfns:
            rk, _ = _extract_fn_return_keys(sfns["Session.reload_outside"], sfns, {}, set())
            if rk:
                spreads["info"] = {k.rstrip("?") for k in rk}
    return spreads


def extract_protocol(root: Path) -> tuple[int | None, list[MessageSpec], set[str]]:
    """Extract (protocol_version, message_specs, generic_error_keys) from worker/serve.py."""
    serve_path = root / SERVE_PY
    text = serve_path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=SERVE_PY)
    proto_ver = _find_protocol_version(tree)
    fn_map, _ = _collect_py_symbols(tree)
    # Also alias nested serve.* names without the `serve.` prefix for local calls inside serve
    local_map = dict(fn_map)
    for k, v in fn_map.items():
        if k.startswith("serve."):
            local_map.setdefault(k[len("serve."):], v)

    imports = _find_imports(tree, serve_path.parent)
    mod_fns: dict[str, tuple[Path, dict[str, ast.AST]]] = {}
    for mname, mpath in imports.items():
        mtree = ast.parse(mpath.read_text(encoding="utf-8"), filename=str(mpath))
        mfns, _ = _collect_py_symbols(mtree)
        mod_fns[mname] = (mpath, mfns)

    global_spreads = _known_spreads(root, local_map, mod_fns)
    handle_fn = fn_map.get("serve.handle")
    if handle_fn is None:
        raise SystemExit(f"{SERVE_PY}: could not find serve.handle")

    specs: list[MessageSpec] = []
    events: dict[str, MessageSpec] = {}
    generic_err_keys: set[str] = {"ok", "cmd", "error", "seq"}

    # Walk handle's try body
    try_node = next((s for s in getattr(handle_fn, "body", []) if isinstance(s, ast.Try)), None)
    stmts = try_node.body if try_node else getattr(handle_fn, "body", [])

    # Extract generic error envelope from except handler
    if try_node:
        for h in try_node.handlers:
            ek, _ = _extract_fn_return_keys(h, local_map, mod_fns, set())
            # Also check Assign to resp in handler
            for st in h.body:
                if isinstance(st, ast.Assign):
                    dk, _, _ = _extract_dict_from_expr(st.value, {}, local_map, mod_fns, set())
                    generic_err_keys.update(k.rstrip("?") for k in dk)
            generic_err_keys.update(k.rstrip("?") for k in ek)
    for st in getattr(handle_fn, "body", []):
        if isinstance(st, ast.If):
            for sub in st.body:
                if isinstance(sub, ast.Assign):
                    for t in sub.targets:
                        if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == "resp":
                            k = _str_const(t.slice)
                            if k:
                                generic_err_keys.add(k)

    # Walk top-level statements of handle's try block to find `if cmd == ...` chains
    seen_delay = False

    def process_if_chain(if_stmt: ast.If) -> None:
        cmds = _match_cmd_condition(if_stmt.test)
        if cmds:
            req_fields = _extract_req_fields(if_stmt.body, {"req"}, local_map, mod_fns)
            env: dict[str, tuple[list[str], dict[str, set[str]]]] = {}
            reply_keys: list[str] = []
            seen_rk: set[str] = set()
            spreads: dict[str, set[str]] = {}
            builder = ""

            # Track resp = ... anywhere in branch (including nested if/else)
            def scan_resp(block: list[ast.stmt]) -> None:
                nonlocal builder
                for st in block:
                    if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
                        if st.targets[0].id == "resp":
                            dk, ds, db = _extract_dict_from_expr(st.value, env, local_map, mod_fns, set())
                            for k in dk:
                                _merge_key(reply_keys, seen_rk, k)
                            spreads.update(ds)
                            if db and not dk:
                                builder = db
                    elif isinstance(st, ast.If):
                        scan_resp(st.body)
                        scan_resp(st.orelse)
                    elif isinstance(st, (ast.For, ast.While, ast.With)):
                        scan_resp(st.body)
                    elif isinstance(st, ast.Try):
                        scan_resp(st.body)
                        for h in st.handlers:
                            scan_resp(h.body)

            scan_resp(if_stmt.body)

            # Check direct send / answer calls in branch
            for sk, ss, sb, lit_cmd in _extract_sends(if_stmt.body, env, local_map, mod_fns):
                if lit_cmd is not None and lit_cmd not in cmds and not (lit_cmd == "sync" and "replay" in cmds):
                    # Unprompted event sent from inside another command's branch (e.g., focus)
                    events[lit_cmd] = MessageSpec(
                        name=lit_cmd,
                        kind="event",
                        reply_keys=sk,
                        spreads=ss,
                        handler=f"{SERVE_PY}:serve.handle",
                    )
                else:
                    for k in sk:
                        _merge_key(reply_keys, seen_rk, k)
                    spreads.update(ss)
                    if sb and not sk:
                        builder = sb

            # Determine handler location
            handler = f"{SERVE_PY}:serve.handle"
            for node in ast.walk(ast.Module(body=if_stmt.body, type_ignores=[])):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    mname = node.func.value.id
                    if mname in mod_fns:
                        mpath, mfns = mod_fns[mname]
                        if node.func.attr in mfns:
                            rel_mpath = mpath.relative_to(root).as_posix()
                            handler = f"{rel_mpath}:{node.func.attr}"
                            break

            # Include seq? if branch uses seq
            uses_seq = any(isinstance(n, ast.Name) and n.id == "seq" for n in ast.walk(ast.Module(body=if_stmt.body, type_ignores=[])))
            if uses_seq and "seq" not in req_fields and "seq?" not in req_fields:
                req_fields.append("seq?")

            for name in list(spreads):
                if name in global_spreads:
                    spreads[name].update(global_spreads[name])

            for c in cmds:
                specs.append(
                    MessageSpec(
                        name=c,
                        kind="command",
                        req_fields=list(req_fields),
                        reply_keys=list(reply_keys),
                        spreads=dict(spreads),
                        handler=handler,
                        reply_builder=builder,
                        accepts_delay=seen_delay,
                    )
                )

        # Recurse into elif / else
        for sub in if_stmt.orelse:
            if isinstance(sub, ast.If):
                process_if_chain(sub)

    for st in stmts:
        if isinstance(st, ast.If):
            if any(
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == "get"
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "req"
                and n.args
                and _str_const(n.args[0]) == "delay_ms"
                for n in ast.walk(st.test)
            ):
                seen_delay = True
                continue
            process_if_chain(st)

    # Scan other functions in serve(...) for unprompted events
    for qname, fn in fn_map.items():
        if not qname.startswith("serve.") or qname in ("serve.handle", "serve.send", "serve.answer"):
            continue
        for sk, ss, _, lit_cmd in _extract_sends(getattr(fn, "body", []), {}, local_map, mod_fns):
            if lit_cmd and lit_cmd not in events:
                events[lit_cmd] = MessageSpec(
                    name=lit_cmd,
                    kind="event",
                    reply_keys=sk,
                    spreads=ss,
                    handler=f"{SERVE_PY}:{qname}",
                )

    for ev in events.values():
        specs.append(ev)

    return proto_ver, specs, generic_err_keys


def build_map(specs: list[MessageSpec]) -> str:
    lines = [
        "| Message | Kind | Request fields | Reply / payload keys | Handler |",
        "|---|---|---|---|---|",
    ]
    for sp in specs:
        req_str = ", ".join(f"`{f}`" for f in sp.req_fields) if sp.req_fields else "—"
        if sp.reply_keys:
            rep_str = ", ".join(f"`{k}`" for k in sp.reply_keys)
        elif sp.reply_builder:
            rep_str = f"reply: built by `{sp.reply_builder}`"
        else:
            rep_str = "—"
        lines.append(f"| `{sp.name}` | {sp.kind} | {req_str} | {rep_str} | `{sp.handler}` |")
    return "\n".join(lines)


def with_map(text: str, body: str) -> str:
    if START not in text or END not in text:
        raise SystemExit(f"{PROTOCOL_DOC} has no protocol map markers ({START} ... {END})")
    a = text.index(START) + len(START)
    b = text.index(END)
    return text[:a] + "\n\n" + body + "\n\n" + text[b:]


def _commands_and_events_section(text: str) -> str:
    m = re.search(r"^## Commands and events\s*$", text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def _check_sections(section_text: str, specs: list[MessageSpec]) -> list[str]:
    problems: list[str] = []
    headings = re.findall(r"^### (.+)$", section_text, re.M)
    doc_names: list[str] = []
    for h in headings:
        doc_names.extend(re.findall(r"`([^`]+)`", h))

    code_names = {sp.name for sp in specs}
    doc_set = set(doc_names)
    for sp in specs:
        if sp.name not in doc_set:
            problems.append(f"{sp.kind} `{sp.name}` in code has no `### ` section in {PROTOCOL_DOC}")
    for name in doc_names:
        if name not in code_names:
            problems.append(f"`### ` section `{name}` in {PROTOCOL_DOC} is not handled by the code")
    return problems


def _resolve_file_symbols(root: Path, rel_or_name: str, cache: dict[Path, set[str]]) -> tuple[Path | None, set[str]]:
    p = root / rel_or_name
    if not p.is_file() and "/" not in rel_or_name:
        for folder in ("viewport", "worker", "tools"):
            cand = root / folder / rel_or_name
            if cand.is_file():
                p = cand
                break
    if not p.is_file():
        return None, set()
    if p in cache:
        return p, cache[p]

    text = p.read_text(encoding="utf-8", errors="replace")
    syms: set[str] = set()
    if p.suffix == ".py":
        try:
            tree = ast.parse(text, filename=str(p))
            _, syms = _collect_py_symbols(tree)
        except SyntaxError:
            syms = set()
    elif p.suffix == ".gd":
        syms = set(re.findall(r"^(?:static\s+)?func\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.M))
    cache[p] = syms
    return p, syms


def _check_references(root: Path, text: str) -> list[str]:
    problems: list[str] = []
    cache: dict[Path, set[str]] = {}
    link_re = re.compile(r"\[([^\]]+\.(?:py|gd))\]\([^)]+\):")
    inline_re = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|gd)):([A-Za-z_][A-Za-z0-9_.]*)`")

    for lineno, line in enumerate(text.splitlines(), 1):
        if not re.search(r"\b(Sources?|Producer(?:/consumer)?|Consumer)\b", line, re.I):
            continue
        matches = list(link_re.finditer(line))
        for idx, m in enumerate(matches):
            fpath = m.group(1)
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(line)
            rest = line[m.end():end]
            # Strip parenthetical notes like `(decode_u32 ...)` before splitting on `;`/`. `
            cleaned = re.sub(r"\([^)]*\)", "", rest)
            head = re.split(r";|\.\s|\.$", cleaned, maxsplit=1)[0]
            syms = re.findall(r"`([^`]+)`", head)
            if not syms:
                continue
            resolved, defined = _resolve_file_symbols(root, fpath, cache)
            if resolved is None:
                problems.append(f"{PROTOCOL_DOC}:{lineno}: referenced file `{fpath}` does not exist")
                continue
            for sym in syms:
                if sym not in defined:
                    problems.append(f"{PROTOCOL_DOC}:{lineno}: `{fpath}:{sym}` does not exist")
        for m in inline_re.finditer(line):
            fpath, sym = m.group(1), m.group(2)
            resolved, defined = _resolve_file_symbols(root, fpath, cache)
            if resolved is None:
                problems.append(f"{PROTOCOL_DOC}:{lineno}: referenced file `{fpath}` does not exist")
            elif sym not in defined:
                problems.append(f"{PROTOCOL_DOC}:{lineno}: `{fpath}:{sym}` does not exist")
    return problems


def _check_examples(section_text: str, proto_ver: int | None, specs: list[MessageSpec], generic_err: set[str]) -> list[str]:
    problems: list[str] = []
    by_name = {sp.name: sp for sp in specs}

    # Split into ### subsections
    parts = re.split(r"(?m)^### ", section_text)
    for part in parts[1:]:
        heading = part.splitlines()[0].strip()
        is_generic_err = heading.lower().startswith("generic request errors")
        in_json = False
        for line in part.splitlines()[1:]:
            s = line.strip()
            if s.startswith("```"):
                if in_json:
                    in_json = False
                elif s == "```json":
                    in_json = True
                continue
            if not in_json or not s:
                continue
            try:
                obj = json.loads(s)
            except json.JSONDecodeError as e:
                problems.append(f"{PROTOCOL_DOC} ({heading}): invalid JSON example: {e}")
                continue
            if not isinstance(obj, dict) or "cmd" not in obj:
                problems.append(f"{PROTOCOL_DOC} ({heading}): example JSON must be an object with `cmd`")
                continue

            cmd = obj["cmd"]
            is_reply = "ok" in obj

            if is_generic_err:
                allowed = (generic_err | {"request_id"}) if is_reply else {"cmd", "seq", "delay_ms"}
                extra = set(obj.keys()) - allowed
                if extra:
                    problems.append(f"{PROTOCOL_DOC} ({heading}): unexpected keys {sorted(extra)} in generic error example")
                continue

            if cmd not in by_name:
                problems.append(f"{PROTOCOL_DOC} ({heading}): example references unknown cmd `{cmd}`")
                continue

            sp = by_name[cmd]
            if is_reply:
                allowed = {k.rstrip("?") for k in sp.reply_keys if not k.startswith("**")}
                for spread_keys in sp.spreads.values():
                    allowed.update(spread_keys)
                if obj.get("ok") is False:
                    allowed.update(generic_err)
                    if cmd == "inspect_properties":
                        allowed.add("request_id")
                if sp.reply_keys or not sp.reply_builder:
                    extra = set(obj.keys()) - allowed
                    if extra:
                        problems.append(
                            f"{PROTOCOL_DOC} ({heading}): reply example for `{cmd}` has keys {sorted(extra)} not in code ({sorted(allowed)})"
                        )
                if cmd == "hello" and obj.get("ok") is True and "protocol" in obj and proto_ver is not None:
                    if obj["protocol"] != proto_ver:
                        problems.append(
                            f"{PROTOCOL_DOC} ({heading}): `hello` example has protocol={obj['protocol']}, expected {proto_ver}"
                        )
            else:
                allowed = {"cmd"} | {f.rstrip("?") for f in sp.req_fields}
                if sp.accepts_delay:
                    allowed.add("delay_ms")
                extra = set(obj.keys()) - allowed
                if extra:
                    problems.append(
                        f"{PROTOCOL_DOC} ({heading}): request example for `{cmd}` has keys {sorted(extra)} not in code ({sorted(allowed)})"
                    )
    return problems


def check_doc(root: Path) -> list[str]:
    proto_ver, specs, generic_err = extract_protocol(root)
    doc_path = root / PROTOCOL_DOC
    text = doc_path.read_text(encoding="utf-8")
    body = build_map(specs)
    problems: list[str] = []

    if START not in text or END not in text:
        problems.append(f"{PROTOCOL_DOC} has no protocol map markers ({START} ... {END})")
    elif with_map(text, body) != text:
        problems.append(f"{PROTOCOL_DOC} protocol map is out of date; run: python3 tools/protocol_map.py")

    section = _commands_and_events_section(text)
    if not section:
        problems.append(f"{PROTOCOL_DOC} is missing `## Commands and events`")
    else:
        problems.extend(_check_sections(section, specs))
        problems.extend(_check_examples(section, proto_ver, specs, generic_err))

    problems.extend(_check_references(root, text))
    return problems


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    check_only = "--check" in args
    unknown = [a for a in args if a != "--check"]
    if unknown:
        print("usage: python3 tools/protocol_map.py [--check]", file=sys.stderr)
        return 2

    root = Path.cwd()
    if check_only:
        problems = check_doc(root)
        if problems:
            for p in problems:
                print(p, file=sys.stderr)
            return 1
        return 0

    _, specs, _ = extract_protocol(root)
    body = build_map(specs)
    doc_path = root / PROTOCOL_DOC
    text = doc_path.read_text(encoding="utf-8")
    new_text = with_map(text, body)
    if new_text != text:
        doc_path.write_text(new_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
