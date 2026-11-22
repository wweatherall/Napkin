"""11. group two boards and move the group (T76)."""
from scenario.context import diff, ok, only

requires = ()

def run(ctx):
    FIX = ctx.FIX
    step = ctx.step

    # 11. group two boards and move the group
    ASM = [{"id": "s11a", "type": "make_assembly", "targets": ["bottom", "shelf"], "new_id": "a1"},
           {"id": "s11", "type": "move", "targets": ["a1"], "vector": [0, 0, 10]}]
    step("assemble bottom and shelf, lift 10", FIX + ASM, lambda st, a, b: [
        ok(st, 2),
        ("both members lifted 10", all(b["boards"][k]["box"][2] == a["boards"][k]["box"][2] + 10 for k in ("bottom", "shelf")),
         {k: b["boards"][k]["box"] for k in ("bottom", "shelf")}),
        ("the group exists", b["groups"].get("a1") == ["bottom", "shelf"], b["groups"]),
        ("the sides didn't move", all(b["boards"][k] == a["boards"][k] for k in ("left", "right")), "")])

    # 11b. I47 (William, 2026-11-21): copying a whole assembly makes a new assembly of linked copies; the original
    # keeps its members. Assembly rows have their own checks in 99_assembly_rows.py.
    ASM_COPY = FIX + ASM[:1] + [{"id": "s11c", "type": "move", "targets": ["bottom", "shelf"], "vector": [0, 600, 0],
                                 "copy": True, "selection": True, "groups": {"a1": "a2"}, "new_ids": ["c1", "c2"]}]
    step("copy a whole assembly: a new assembly of linked copies", ASM_COPY, lambda st, a, b: [
        ok(st, 2), only(a, b, {"c1", "c2"}),
        ("the copy is its own assembly", b["groups"].get("a2") == ["c1", "c2"] and b["groups"].get("a1") == ["bottom", "shelf"], b["groups"]),
        ("copies sit 600 along y, same shapes", all(b["boards"][c]["vol"] == a["boards"][k]["vol"]
            and b["boards"][c]["box"][1] == a["boards"][k]["box"][1] + 600 for k, c in [("bottom", "c1"), ("shelf", "c2")]), diff(a, b))])
    ctx.actions.update(ASM=ASM)
