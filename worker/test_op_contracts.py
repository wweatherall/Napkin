"""H189: verify every handler CONTRACT against op_contracts.json, handler reads/rejections, and session.creations."""
import os
import sys

import FreeCAD as App

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OpError
from field_audit import AuditedDict
from model import Model
import op_contracts
from session import creations

R = [0, 0]


def check(name, condition, detail=""):
    R[0 if condition else 1] += 1
    print(("PASS " if condition else "FAIL ") + name + ("" if condition or not detail else f" ({detail})"), flush=True)


def _sample_value(spec):
    kind = spec["kind"]
    if kind == "Plane":
        return {"origin": [0, 0, 0], "normal": [0, 0, 1]}
    if kind == "number":
        return max(float(spec.get("min", 1.0)) * 10.0, 10.0)
    if kind == "[number, number]":
        return list(spec.get("default", [5.0, 5.0]))
    raise ValueError(f"unsupported contract field kind: {kind!r}")


def _build_op(op_id, contract, include_optional=True):
    op = {"id": op_id, "type": contract["type"]}
    for name, spec in contract["fields"].items():
        if spec.get("required", True) or include_optional:
            op[name] = _sample_value(spec)
    return op


def _resolve_path(op, dotted):
    cur = op
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


check("tests/op_contracts.json is up to date", op_contracts.check_contracts() == [], op_contracts.check_contracts())

contracts = op_contracts.collect_contracts()
check("at least one op contract is registered", bool(contracts))

doc = App.newDocument("OpContractTest")
try:
    m = Model(doc)
    for op_type, contract in sorted(contracts.items()):
        fields = contract["fields"]
        required = {k for k, v in fields.items() if v.get("required", True)}
        all_fields = set(fields.keys())

        # 1. Required-only op succeeds and reads every sent field, none outside contract.fields
        req_op = AuditedDict(_build_op(f"{op_type}_req", contract, include_optional=False))
        try:
            m.apply(req_op)
            req_ok = True
            req_err = ""
        except Exception as e:
            req_ok = False
            req_err = repr(e)
        check(f"{op_type}: required-only op succeeds", req_ok, req_err)
        req_read = set(req_op.read_keys()) - {"id", "type"}
        check(f"{op_type}: required-only op reads all sent fields", required <= req_read, f"read={sorted(req_read)}")
        check(f"{op_type}: required-only op reads no undocumented fields", req_read <= all_fields, f"extra={sorted(req_read - all_fields)}")

        # 2. Full op (with all optional fields) reads every field in contract.fields
        full_op = AuditedDict(_build_op(f"{op_type}_all", contract, include_optional=True))
        try:
            m.apply(full_op)
            full_ok = True
            full_err = ""
        except Exception as e:
            full_ok = False
            full_err = repr(e)
        check(f"{op_type}: full op succeeds", full_ok, full_err)
        full_read = set(full_op.read_keys()) - {"id", "type"}
        check(f"{op_type}: full op reads exact contract fields", full_read == all_fields,
              f"read={sorted(full_read)} expected={sorted(all_fields)}")

        # 3. Missing each required field is rejected
        for req_name in sorted(required):
            bad = _build_op(f"{op_type}_no_{req_name}", contract, include_optional=False)
            del bad[req_name]
            rejected = False
            try:
                m.apply(bad)
            except (OpError, KeyError):
                rejected = True
            check(f"{op_type}: missing required field '{req_name}' is rejected", rejected)

        # 4. Min constraint: at min succeeds, below min is rejected
        for fname, spec in sorted(fields.items()):
            if "min" not in spec:
                continue
            min_val = float(spec["min"])
            at_min = _build_op(f"{op_type}_at_min_{fname}", contract, include_optional=False)
            at_min[fname] = min_val
            try:
                m.apply(at_min)
                at_ok = True
            except OpError:
                at_ok = False
            check(f"{op_type}: {fname} == {min_val} (min) is accepted", at_ok)

            below_min = _build_op(f"{op_type}_below_min_{fname}", contract, include_optional=False)
            below_min[fname] = min_val * 0.5
            below_rejected = False
            try:
                m.apply(below_min)
            except OpError:
                below_rejected = True
            check(f"{op_type}: {fname} < {min_val} (min) is rejected", below_rejected)

        # 5. session.creations yields exactly contract['creates']
        expected_ids = [_resolve_path(full_op, p) for p in contract.get("creates", [])]
        got_ids = [identity for identity, _ in creations(full_op)]
        check(f"{op_type}: creations matches contract.creates", got_ids == expected_ids,
              f"got={got_ids} expected={expected_ids}")
finally:
    App.closeDocument(doc.Name)

print(f"OP CONTRACTS TESTS: {R[0]} passed, {R[1]} failed", flush=True)
sys.exit(1 if R[1] else 0)
