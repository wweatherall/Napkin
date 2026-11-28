"""Collect per-op CONTRACT dicts from worker handler modules and generate tests/op_contracts.json.

Usage:
  python3 worker/op_contracts.py          write tests/op_contracts.json
  python3 worker/op_contracts.py --check  exit 1 if tests/op_contracts.json is missing or stale
"""
import ast
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKER_DIR = Path(__file__).resolve().parent
CONTRACTS_PATH = ROOT / "tests" / "op_contracts.json"

_CONTRACTS = None


def _get_contracts():
    global _CONTRACTS
    if _CONTRACTS is None:
        _CONTRACTS = collect_contracts()
    return _CONTRACTS


def _is_number(val):
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def _is_integer(val):
    return isinstance(val, int) and not isinstance(val, bool)


def _check_kind(val, kind):
    if kind == "number":
        return _is_number(val), "a number"
    if kind == "integer":
        return _is_integer(val), "an integer"
    if kind == "bool":
        return isinstance(val, bool), "a bool"
    if kind == "string":
        return isinstance(val, str), "a string"
    if kind == "[string]":
        return isinstance(val, list) and all(isinstance(x, str) for x in val), "a list of strings"
    if kind == "[number, number]":
        return (
            isinstance(val, list) and len(val) == 2 and all(_is_number(x) for x in val),
            "a list of two numbers",
        )
    if kind == "[number, number, number]":
        return (
            isinstance(val, list) and len(val) == 3 and all(_is_number(x) for x in val),
            "a list of three numbers",
        )
    if kind == "[[number, number, number]]":
        return (
            isinstance(val, list)
            and all(isinstance(pt, list) and len(pt) == 3 and all(_is_number(x) for x in pt) for pt in val),
            "a list of 3-number lists",
        )
    return isinstance(val, dict), "an object"


def validate(op, contracts=None):
    """Return the first contract problem string for op, or None if valid or uncontracted."""
    if not isinstance(op, dict):
        return None
    if contracts is None:
        contracts = _get_contracts()
    op_type = dict.get(op, "type")
    contract = contracts.get(op_type)
    if contract is None:
        return None
    fields = contract.get("fields", {})
    for fname, spec in fields.items():
        if spec.get("required", True) and not dict.__contains__(op, fname):
            return f"{op_type}: missing {fname}"
    for fname in dict.keys(op):
        if fname not in ("id", "type") and fname not in fields:
            return f"{op_type}: unknown field {fname}"
    for fname, spec in fields.items():
        if not dict.__contains__(op, fname):
            continue
        val = dict.__getitem__(op, fname)
        ok, label = _check_kind(val, spec["kind"])
        if not ok:
            return f"{op_type}: {fname} must be {label}"
        if "min" in spec and val < spec["min"]:
            return f"{op_type}: {fname} must be at least {spec['min']}"
        if "max" in spec and val > spec["max"]:
            return f"{op_type}: {fname} must be at most {spec['max']}"
    return None


def _has_actions_class(tree):
    return any(
        isinstance(node, ast.ClassDef) and node.name.endswith("Actions")
        for node in tree.body
    )


def _extract_contracts(tree, filename):
    found = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("CONTRACT", "CONTRACTS"):
                    val = ast.literal_eval(node.value)
                    found.extend(val if isinstance(val, list) else [val])
    return found


def collect_contracts(worker_dir=WORKER_DIR):
    """Discover every *Actions module (and model.py) in worker_dir and return {op_type: contract}."""
    worker_dir = Path(worker_dir)
    if not worker_dir.is_dir():
        return {}
    contracts = {}
    for name in sorted(os.listdir(worker_dir)):
        if not name.endswith(".py") or name.startswith("test_"):
            continue
        path = worker_dir / name
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        if not (_has_actions_class(tree) or name == "model.py"):
            continue
        for contract in _extract_contracts(tree, name):
            op_type = contract.get("type")
            if not op_type:
                raise ValueError(f"{name}: CONTRACT missing 'type'")
            if op_type in contracts:
                raise ValueError(f"{name}: duplicate CONTRACT for op type '{op_type}'")
            contracts[op_type] = contract
    return contracts


def render_contracts(contracts):
    return json.dumps(contracts, indent=2, sort_keys=True) + "\n"


def check_contracts(worker_dir=WORKER_DIR, out_path=CONTRACTS_PATH):
    """Return a list of error strings if out_path is missing or out of sync with worker_dir."""
    contracts = collect_contracts(worker_dir)
    expected = render_contracts(contracts)
    out_path = Path(out_path)
    if not out_path.is_file():
        return [f"{out_path} is missing; run: python3 worker/op_contracts.py"]
    actual = out_path.read_text(encoding="utf-8")
    if actual != expected:
        return [f"{out_path} is out of date; run: python3 worker/op_contracts.py"]
    return []


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    check_only = "--check" in args
    unknown = [a for a in args if a != "--check"]
    if unknown:
        print("usage: python3 worker/op_contracts.py [--check]", file=sys.stderr)
        return 2
    if check_only:
        problems = check_contracts()
        for p in problems:
            print(p, file=sys.stderr)
        return 1 if problems else 0
    CONTRACTS_PATH.write_text(render_contracts(collect_contracts()), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
