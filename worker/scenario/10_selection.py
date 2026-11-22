"""T34: one meaningful action, several native boards, and deletion preserving linked siblings. (T76)."""
from scenario.context import diff, ok, only

requires = ()

def run(ctx):
    FIX = ctx.FIX
    step = ctx.step

    # T34: one meaningful action, several native boards, and deletion preserving linked siblings.
    MULTI = {"id": "multi", "type": "move", "targets": ["bottom", "shelf", "shelf2"],
             "selection": True, "vector": [35, 0, 0]}
    step("multi-board move", FIX + [MULTI], lambda st, a, b: [
        ok(st, 1), only(a, b, {"bottom", "shelf", "shelf2"}),
        ("each selected board moved once", all(b["boards"][k]["box"][0] == a["boards"][k]["box"][0] + 35
            for k in MULTI["targets"]), diff(a, b))])
    step("multi-board copy", FIX + [dict(MULTI, copy=True, new_ids=["c1", "c2", "c3"])], lambda st, a, b: [
        ok(st, 1), only(a, b, {"c1", "c2", "c3"}),
        ("three new boards, same shape and offset", all(b["boards"][c]["vol"] == a["boards"][k]["vol"]
            and b["boards"][c]["box"][0] == a["boards"][k]["box"][0] + 35
            for k, c in zip(MULTI["targets"], ["c1", "c2", "c3"])), diff(a, b))])
    step("multi-board mirror", FIX + [{"id": "multi_mirror", "type": "mirror", "targets": ["bottom", "shelf"],
        "new_ids": ["m1", "m2"], "plane": {"point": [1000, 0, 0], "normal": [1, 0, 0]}}], lambda st, a, b: [
        ok(st, 1), only(a, b, {"m1", "m2"}),
        ("both copies reflected at the same plane", all(b["boards"][c]["box"][0] == 2000 - a["boards"][k]["box"][3]
            for k, c in [("bottom", "m1"), ("shelf", "m2")]), diff(a, b))])
    step("delete original linked shelf", FIX + [{"id": "delete_original", "type": "delete", "targets": ["shelf"]}], lambda st, a, b: [
        ok(st, 1), only(a, b, {"shelf"}),
        ("original gone, linked sibling unchanged", "shelf" not in b["boards"] and b["boards"]["shelf2"] == a["boards"]["shelf2"], diff(a, b))])
    step("delete several boards", FIX + [{"id": "delete_many", "type": "delete", "targets": ["bottom", "shelf2"]}], lambda st, a, b: [
        ok(st, 1), only(a, b, {"bottom", "shelf2"}),
        ("only selected boards gone", set(b["boards"]) == set(a["boards"]) - {"bottom", "shelf2"}, sorted(b["boards"]))])
    step("delete mirror source", FIX + [{"id": "delete_source", "type": "delete", "targets": ["left"]}], lambda st, a, b: [
        ok(st, 1),
        ("source gone, mirrored sibling unchanged", "left" not in b["boards"] and b["boards"]["right"] == a["boards"]["right"], diff(a, b))])

    ROW = {"id": "multi_row", "type": "move", "targets": ["shelf"], "vector": [0, 100, 0],
           "copy": True, "count": 3, "new_ids": ["row1", "row2", "row3"]}
    step("select row original and copies", FIX + [ROW, dict(MULTI, targets=["shelf", "row1", "row2", "row3", "bottom"])], lambda st, a, b: [
        ok(st, 2),
        ("row members and unrelated board move once", all(b["boards"][k]["box"][0] == a["boards"]["shelf"]["box"][0] + 35
            for k in ("shelf", "row1", "row2", "row3")) and b["boards"]["bottom"]["box"][0] == a["boards"]["bottom"]["box"][0] + 35, diff(a, b))])
    step("inside row move selected copies", FIX + [ROW, dict(MULTI, targets=["row1", "row2"], detach=True)], lambda st, a, b: [
        ok(st, 2),
        ("selected copies move, original and other copy stay", b["boards"]["shelf"] == a["boards"]["shelf"]
            and b["boards"]["row3"]["box"][0] == a["boards"]["shelf"]["box"][0]
            and all(b["boards"][k]["box"][0] == a["boards"]["shelf"]["box"][0] + 35 for k in ("row1", "row2")), diff(a, b))])
    EXTRA_MIRROR = {"id": "another_mirror", "type": "mirror", "targets": ["left"], "new_ids": ["right2"],
                    "plane": {"point": [400, 0, 0], "normal": [1, 0, 0]}}
    step("move two mirrors sharing a source", FIX + [EXTRA_MIRROR, dict(MULTI, targets=["right", "right2"])], lambda st, a, b: [
        ok(st, 2),
        ("shared original moves once", b["boards"]["left"]["box"][0] == a["boards"]["left"]["box"][0] - 35
            and b["boards"]["right"]["box"][0] == a["boards"]["right"]["box"][0] + 35
            and b["boards"]["right2"]["box"][0] == 800 - a["boards"]["left"]["box"][3] + 35, diff(a, b))])
