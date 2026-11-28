"""Unit tests for worker/field_audit.py and Model.apply field auditing."""
import json
import os
import sys
import tempfile

import FreeCAD as App

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import field_audit
from model import Model, OpError
from test_link import Checks

checks = Checks("FIELD AUDIT")
check = checks.check

# 1. AuditedDict tracks [], get, in, pop, setdefault, whole-dict iteration, and copy()
d = field_audit.AuditedDict({"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6})
check("AuditedDict is a dict", isinstance(d, dict))
check("[] returns value", d["a"] == 1)
check("get returns value", d.get("b") == 2)
check("in returns True", "c" in d)
check("in records missing key too", "missing" not in d)
check("pop returns value", d.pop("d") == 4)
check("setdefault returns value", d.setdefault("e", 99) == 5)
d["g"] = 7
check("mutation works", d["g"] == 7)
d2 = field_audit.AuditedDict({"x": 1, "y": 2})
check("json.dumps works on AuditedDict", json.loads(json.dumps(d2)) == {"x": 1, "y": 2})

clone = d.copy()
check("copy returns AuditedDict", isinstance(clone, field_audit.AuditedDict))
check("copy reads f into shared tracker", clone["f"] == 6)
check(
    "tracked individual reads",
    set(d.read_keys()) == {"a", "b", "c", "missing", "d", "e", "g", "f"},
    str(d.read_keys()),
)

d_all = field_audit.AuditedDict({"k1": 1, "k2": 2})
_ = list(d_all.items())
check("items() marks all keys read", set(d_all.read_keys()) == {"k1", "k2"})

d_keys = field_audit.AuditedDict({"k1": 1, "k2": 2})
_ = list(d_keys.keys())
check("keys() marks all keys read", set(d_keys.read_keys()) == {"k1", "k2"})

d_vals = field_audit.AuditedDict({"k1": 1, "k2": 2})
_ = list(d_vals.values())
check("values() marks all keys read", set(d_vals.read_keys()) == {"k1", "k2"})

# 2. unread_fields and CLI main()
tmp = os.path.abspath(os.environ.get("TESTDIR") or tempfile.mkdtemp(prefix="napkin-audit-"))
os.makedirs(tmp, exist_ok=True)
f1 = os.path.join(tmp, "a1.jsonl")
f2 = os.path.join(tmp, "a2.jsonl")
for p in (f1, f2):
    if os.path.exists(p):
        os.remove(p)

field_audit.append_record(f1, "board", ["id", "type", "w", "h", "typo"], ["type", "w"])
field_audit.append_record(f2, "board", ["id", "type", "w", "h"], ["type", "w", "h"])
field_audit.append_record(f2, "extrude", ["id", "type", "face", "distnace"], ["type", "face"])

unread = field_audit.unread_fields([f1, f2])
check(
    "one run reads h and another run of the same type doesn't -> flagged",
    set(unread.keys()) == {"board", "extrude"}
    and set(unread["board"].keys()) == {"h", "typo"}
    and unread["board"]["h"]["count"] == 1
    and unread["board"]["h"]["example"] == ["h", "id", "type", "typo", "w"]
    and unread["board"]["typo"]["count"] == 1
    and set(unread["extrude"].keys()) == {"distnace"}
    and unread["extrude"]["distnace"]["count"] == 1,
    str(unread),
)
check("main exits 1 when unread fields exist", field_audit.main([f1, f2]) == 1)

f_allow = os.path.join(tmp, "allow.jsonl")
if os.path.exists(f_allow):
    os.remove(f_allow)
field_audit.append_record(f_allow, "move", ["id", "type", "cut", "targets"], ["cut"])
check("move.targets with cut in UNREAD_WHEN passes", field_audit.unread_fields([f_allow]) == {})
check("main exits 0 when unread field matches UNREAD_WHEN", field_audit.main([f_allow]) == 0)

f_no_cut = os.path.join(tmp, "no_cut.jsonl")
if os.path.exists(f_no_cut):
    os.remove(f_no_cut)
field_audit.append_record(f_no_cut, "move", ["id", "type", "targets"], [])
no_cut_unread = field_audit.unread_fields([f_no_cut])
check(
    "move.targets without cut is flagged",
    list(no_cut_unread.keys()) == ["move"] and list(no_cut_unread["move"].keys()) == ["targets"],
    str(no_cut_unread),
)

f_failed = os.path.join(tmp, "failed.jsonl")
if os.path.exists(f_failed):
    os.remove(f_failed)
field_audit.append_record(f_failed, "push_pull", ["id", "type", "rect", "body"], ["rect"], failed=True)
check("failed run with unread fields passes", field_audit.unread_fields([f_failed]) == {})

f_succ = os.path.join(tmp, "succ.jsonl")
if os.path.exists(f_succ):
    os.remove(f_succ)
field_audit.append_record(f_succ, "push_pull", ["id", "type", "rect", "body"], ["rect"], failed=False)
succ_unread = field_audit.unread_fields([f_succ])
check(
    "successful run with unread fields is flagged",
    list(succ_unread.keys()) == ["push_pull"] and list(succ_unread["push_pull"].keys()) == ["body"],
    str(succ_unread),
)

f_clean = os.path.join(tmp, "clean.jsonl")
if os.path.exists(f_clean):
    os.remove(f_clean)
field_audit.append_record(f_clean, "board", ["id", "type", "w"], ["type", "w"])
check("id and type are always considered read", field_audit.unread_fields([f_clean]) == {})
check("main exits 0 when all fields are read", field_audit.main([f_clean]) == 0)

# 3. Model.apply wraps only when SERVE_FIELD_AUDIT is set
doc = App.newDocument("FieldAuditTest")
m = Model(doc)
seen = []
orig_handlers = Model.HANDLERS
Model.HANDLERS = orig_handlers | frozenset({"audit_probe"})
Model.op_audit_probe = lambda self, op: (seen.append((op, type(op), op["used"])), [])[1]
try:
    prev = os.environ.pop("SERVE_FIELD_AUDIT", None)
    try:
        plain_op = {"id": "p1", "type": "audit_probe", "used": 42, "unused": 99}
        m.apply(plain_op)
        check("without SERVE_FIELD_AUDIT, apply passes plain op", seen[-1][0] is plain_op and seen[-1][1] is dict)

        audit_file = os.path.join(tmp, "model_apply.jsonl")
        if os.path.exists(audit_file):
            os.remove(audit_file)
        os.environ["SERVE_FIELD_AUDIT"] = audit_file
        m.apply({"id": "p2", "type": "audit_probe", "used": 42, "unused": 99})
        check("with SERVE_FIELD_AUDIT, apply wraps op in AuditedDict", seen[-1][1] is field_audit.AuditedDict)
        got = field_audit.unread_fields([audit_file])
        check("apply wrote audit record", list(got.keys()) == ["audit_probe"] and list(got["audit_probe"].keys()) == ["unused"], str(got))

        fail_audit = os.path.join(tmp, "model_apply_fail.jsonl")
        if os.path.exists(fail_audit):
            os.remove(fail_audit)
        os.environ["SERVE_FIELD_AUDIT"] = fail_audit
        Model.HANDLERS = orig_handlers | frozenset({"audit_probe", "audit_fail"})
        Model.op_audit_fail = lambda self, op: (_ for _ in ()).throw(OpError("boom"))
        try:
            raised = False
            try:
                m.apply({"id": "p3", "type": "audit_fail", "unused": 1})
            except OpError:
                raised = True
            check("failing handler raises OpError", raised)
            with open(fail_audit, "r", encoding="utf-8") as f:
                rec = json.loads(f.read().strip())
            check("failing handler records failed=True", rec.get("failed") is True, str(rec))
            check("failing handler record passes unread_fields", field_audit.unread_fields([fail_audit]) == {})
        finally:
            delattr(Model, "op_audit_fail")
    finally:
        if prev is None:
            os.environ.pop("SERVE_FIELD_AUDIT", None)
        else:
            os.environ["SERVE_FIELD_AUDIT"] = prev
finally:
    Model.HANDLERS = orig_handlers
    delattr(Model, "op_audit_probe")
    App.closeDocument(doc.Name)

sys.exit(checks.done())
