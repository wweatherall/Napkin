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


def _has_actions_class(tree):
    return any(
        isinstance(node, ast.ClassDef) and node.name.endswith("Actions")
        for node in tree.body
    )


def _extract_contract(tree, filename):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "CONTRACT":
                    return ast.literal_eval(node.value)
    return None


def collect_contracts(worker_dir=WORKER_DIR):
    """Discover every *Actions module in worker_dir and return {op_type: contract}."""
    worker_dir = Path(worker_dir)
    if not worker_dir.is_dir():
        return {}
    contracts = {}
    for name in sorted(os.listdir(worker_dir)):
        if not name.endswith(".py") or name.startswith("test_") or name == "model.py":
            continue
        path = worker_dir / name
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        if not _has_actions_class(tree):
            continue
        contract = _extract_contract(tree, name)
        if contract is None:
            continue
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
