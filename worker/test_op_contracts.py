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


def _sample_value(spec, fname=""):
    kind = spec["kind"]
    if kind == "Plane":
        return {"origin": [0, 0, 0], "normal": [0, 0, 1]}
    if kind == "number":
        return max(float(spec.get("min", 1.0)) * 10.0, 10.0)
    if kind == "integer":
        return int(spec.get("min", 1))
    if kind == "bool":
        return not bool(spec.get("default", False))
    if kind == "string":
        if fname == "material":
            return "white-oak"
        if fname == "value":
            return "150mm"
        return "sample_str"
    if kind == "[string]":
        return ["sample_id"]
    if kind == "[number, number]":
        return list(spec.get("default", [5.0, 5.0]))
    if kind == "[number, number, number]":
        if fname == "mid":
            return [5.0, 5.0, 0.0]
        return [10.0, 0.0, 0.0]
    if kind == "[[number, number, number]]":
        return [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0]]
    raise ValueError(f"unsupported contract field kind: {kind!r}")


_SEQ = [0]


def _next_tag(prefix):
    _SEQ[0] += 1
    return f"{prefix}_{_SEQ[0]}"


def _make_board(m, prefix="b", origin_x=0.0):
    rid = _next_tag(f"r_{prefix}")
    bid = _next_tag(prefix)
    m.apply({"id": rid, "type": "rect", "plane": {"origin": [origin_x, 0, 0], "normal": [0, 0, 1]}, "size": [100, 100]})
    m.apply({"id": _next_tag(f"pp_{prefix}"), "type": "push_pull", "target": {"rect": rid}, "distance": 18, "body": bid})
    return bid


def _prepare_op(m, op_id, contract, include_optional, shared):
    op_type = contract["type"]
    op = {"id": op_id, "type": op_type}
    for name, spec in contract["fields"].items():
        if spec.get("required", True) or include_optional:
            op[name] = _sample_value(spec, name)
    if op_type in ("set_material", "turn_grain", "hide"):
        if "plain" not in shared:
            shared["plain"] = _make_board(m, "plain")
        op["targets"] = [shared["plain"]]
    elif op_type in ("delete", "make_component"):
        bid = _make_board(m, op_type)
        if "targets" in op:
            op["targets"] = [bid]
        if "body" in op:
            op["body"] = bid
    elif op_type == "make_assembly":
        op["targets"] = [_make_board(m, "asm")]
        op["new_id"] = _next_tag("asm")
    elif op_type == "detach":
        src = _make_board(m, "arr")
        c1, c2 = _next_tag("arr_c"), _next_tag("arr_c")
        m.apply({"id": _next_tag("mv"), "type": "move", "targets": [src], "vector": [200, 0, 0],
                 "copy": True, "count": 2, "new_ids": [c1, c2]})
        op["targets"] = [c1]
    elif op_type == "make_unique":
        src = _make_board(m, "comp")
        c1 = _next_tag("comp_c")
        m.apply({"id": _next_tag("mv"), "type": "move", "targets": [src], "vector": [200, 0, 0],
                 "copy": True, "count": 1, "new_ids": [c1]})
        op["targets"] = [c1]
    elif op_type == "unfit":
        ba = _make_board(m, "fit_a", origin_x=0.0)
        bb = _make_board(m, "fit_b", origin_x=200.0)
        m.apply({"id": _next_tag("fit"), "type": "fit", "body": ba, "target_body": bb,
                 "axis": 0, "face": 0, "fit_mode": 0})
        op["body"] = ba
        op["axis"] = 0
        op["value"] = "150mm"
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
    shared = {}
    for op_type, contract in sorted(contracts.items()):
        fields = contract["fields"]
        required = {k for k, v in fields.items() if v.get("required", True)}
        handler_fields = {k for k, v in fields.items() if not v.get("viewport_only", False)}

        # 1. Required-only op succeeds and reads every sent field, none outside contract.fields
        req_op = AuditedDict(_prepare_op(m, f"{op_type}_req", contract, False, shared))
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
        check(f"{op_type}: required-only op reads no undocumented fields", req_read <= handler_fields, f"extra={sorted(req_read - handler_fields)}")

        # 2. Full op (with all optional fields) reads every handler field in contract.fields
        full_op = AuditedDict(_prepare_op(m, f"{op_type}_all", contract, True, shared))
        try:
            m.apply(full_op)
            full_ok = True
            full_err = ""
        except Exception as e:
            full_ok = False
            full_err = repr(e)
        check(f"{op_type}: full op succeeds", full_ok, full_err)
        full_read = set(full_op.read_keys()) - {"id", "type"}
        check(f"{op_type}: full op reads exact contract fields", full_read == handler_fields,
              f"read={sorted(full_read)} expected={sorted(handler_fields)}")

        # 3. Missing each required field is rejected
        for req_name in sorted(required):
            bad = _prepare_op(m, f"{op_type}_no_{req_name}", contract, False, shared)
            del bad[req_name]
            rejected = False
            try:
                m.apply(bad)
            except (OpError, KeyError):
                rejected = True
            check(f"{op_type}: missing required field '{req_name}' is rejected", rejected)

        # 4. Min/max constraints: at bound succeeds, beyond bound is rejected
        for fname, spec in sorted(fields.items()):
            is_int = spec.get("kind") == "integer"
            if "min" in spec:
                min_val = int(spec["min"]) if is_int else float(spec["min"])
                at_min = _prepare_op(m, f"{op_type}_at_min_{fname}", contract, False, shared)
                at_min[fname] = min_val
                try:
                    m.apply(at_min)
                    at_ok = True
                except OpError:
                    at_ok = False
                check(f"{op_type}: {fname} == {min_val} (min) is accepted", at_ok)

                below_min = _prepare_op(m, f"{op_type}_below_min_{fname}", contract, False, shared)
                below_min[fname] = min_val - 1 if is_int else min_val * 0.5
                below_rejected = False
                try:
                    m.apply(below_min)
                except OpError:
                    below_rejected = True
                check(f"{op_type}: {fname} < {min_val} (min) is rejected", below_rejected)

            if "max" in spec:
                max_val = int(spec["max"]) if is_int else float(spec["max"])
                at_max = _prepare_op(m, f"{op_type}_at_max_{fname}", contract, False, shared)
                at_max[fname] = max_val
                try:
                    m.apply(at_max)
                    at_max_ok = True
                except OpError:
                    at_max_ok = False
                check(f"{op_type}: {fname} == {max_val} (max) is accepted", at_max_ok)

                above_max = _prepare_op(m, f"{op_type}_above_max_{fname}", contract, False, shared)
                above_max[fname] = max_val + 1 if is_int else max_val * 2.0
                above_rejected = False
                try:
                    m.apply(above_max)
                except OpError:
                    above_rejected = True
                check(f"{op_type}: {fname} > {max_val} (max) is rejected", above_rejected)

        # 5. session.creations yields exactly contract['creates']
        expected_ids = []
        for p in contract.get("creates", []):
            val = _resolve_path(full_op, p)
            if isinstance(val, list):
                expected_ids.extend(val)
            elif val is not None:
                expected_ids.append(val)
        got_ids = [identity for identity, _ in creations(full_op)]
        check(f"{op_type}: creations matches contract.creates", got_ids == expected_ids,
              f"got={got_ids} expected={expected_ids}")
finally:
    App.closeDocument(doc.Name)

print(f"OP CONTRACTS TESTS: {R[0]} passed, {R[1]} failed", flush=True)
sys.exit(1 if R[1] else 0)
