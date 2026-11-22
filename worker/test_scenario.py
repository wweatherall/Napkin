"""T48 scenario test: one session, one busy fixture model, many operations against it.

  TESTDIR=/tmp/scenario freecadcmd worker/test_scenario.py

The fixture (tests/scenario_fixture.json: a carcass with a mirror group, pin-hole array, through-hole, linked
shelf, paint) is built once. Each step syncs fixture + its ops, checks its own answer by name, then syncs back to
the fixture (FreeCAD undo, A23) and checks the model is exactly the fixture again, so one failing step can't spoil
the next. A cumulative story at the end chains several steps and must equal a fresh build and survive a reopen.
Exceptions are caught per step (freecadcmd reruns a script that raises)."""
import json
import os
import sys
import time
import traceback

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_load  # Configure the FreeCAD test runtime before loading worker modules.
from export import material_of, write_glb
from session import Session

T0 = time.perf_counter()
TESTDIR = os.environ.get("TESTDIR", "/tmp/shopsketch-scenario")
os.makedirs(TESTDIR, exist_ok=True)
FIX = json.load(open(os.path.join(HERE, "..", "tests", "scenario_fixture.json")))["ops"]
R = [0, 0]


def check(name, cond, detail=""):
    R[0 if cond else 1] += 1
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"), flush=True)


def shown_in_freecad(m, obj):
    """What FreeCAD's window would show of this board (T28, T29): the board itself, and its current solid alone
    among its steps (FreeCAD's undo doesn't take back Visibility, so the worker sets it after each sync)."""
    dfn = m.definition(obj)
    steps = [o.Name for o in getattr(dfn, "Group", []) if o.isDerivedFrom("Part::Feature") and o.Visibility]
    tip = getattr(dfn, "Tip", None)
    return (bool(obj.Visibility), steps == ([tip.Name] if tip is not None else steps))


def snap(sess):
    """Every board: volume, world box, material, grain (in its own frame); and every group's members."""
    m = sess.model
    out = {}
    for bid, obj in m.bodies().items():
        sh = m.world_shape(obj)
        bb = sh.BoundBox
        g = m.grain_local(m.definition(obj))
        out[bid] = {"vol": round(sh.Volume, 2),
                    "box": tuple(round(v, 3) for v in (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)),
                    "mat": material_of(m, obj), "grain": tuple(round(abs(v), 3) for v in (g.x, g.y, g.z)),
                    "hidden": bool(getattr(obj, "SSHidden", False)), "shown": shown_in_freecad(m, obj)}
    groups = {k: sorted(getattr(o, "BodyId", "") for o in g.Group) for k, g in m.assemblies().items()}
    return {"boards": out, "groups": groups}


def face(body, normal, point):
    return {"body": body, "normal": list(normal), "point": list(point)}


def on_rect(rid, body, normal, point, size):
    return {"id": rid, "type": "rect", "plane": {"on": face(body, normal, point)}, "size": size}


def fix_with(op_id, **changes):
    """The fixture with one of its own ops retyped (an amend, like typing a new count right after)."""
    return [dict(o, **changes) if o["id"] == op_id else o for o in FIX]


def diff(a, b):
    """Boards whose snapshot differs: {id: (before, after)}."""
    ids = set(a["boards"]) | set(b["boards"])
    return {i: (a["boards"].get(i), b["boards"].get(i)) for i in ids if a["boards"].get(i) != b["boards"].get(i)}


# ---------- the fixture ----------
S = Session(os.path.join(TESTDIR, "scenario.FCStd"), fresh=True)
S.sync(FIX)
bad = [(e["id"], e.get("message")) for e in S.status() if e["status"] != "ok"]
check("fixture: every op accepted", not bad, bad)
S0 = snap(S)
B0 = S0["boards"]
check("fixture: five boards", set(B0) == {"left", "right", "bottom", "shelf", "shelf2"}, sorted(B0))
PIN = 6 * 6 * 12
check("fixture: left side has five pin holes", abs(B0["left"]["vol"] - (18 * 400 * 720 - 5 * PIN)) < 0.1, B0["left"])
check("fixture: right side mirrors the left (same volume, x 582..600)",
      B0["right"]["vol"] == B0["left"]["vol"] and B0["right"]["box"][0] == 582 and B0["right"]["box"][3] == 600, B0["right"])
check("fixture: bottom has its through-hole", abs(B0["bottom"]["vol"] - (564 * 400 - 1600) * 18) < 0.1, B0["bottom"])
check("fixture: linked shelf copy 180 mm above", B0["shelf2"]["box"][2] == B0["shelf"]["box"][2] + 180, B0["shelf2"])
check("fixture: bottom is white oak", B0["bottom"]["mat"] == "white-oak", B0["bottom"]["mat"])
check("fixture: sides form a mirror group", S0["groups"].get("sides") == ["left", "right"], S0["groups"])
T_FIX = time.perf_counter() - T0


def step(name, ops, expect):
    """Run fixture-relative ops, hand (statuses, before, after) to `expect`, which returns [(check, cond, detail)];
    then go back to the fixture and check nothing is left over."""
    t = time.perf_counter()
    try:
        S.sync(ops)
        st = S.status()
        for sub, cond, detail in expect(st, S0, snap(S)):
            check(f"{name}: {sub}", cond, detail)
    except Exception:
        check(f"{name}: ran without an error", False, traceback.format_exc(limit=3))
    try:
        how, _ = S.sync(FIX)
        after = snap(S)
        check(f"{name}: back to the fixture by undo", after == S0 and how != "rebuilt", (how, diff(S0, after)))
    except Exception:
        check(f"{name}: back to the fixture", False, traceback.format_exc(limit=3))
    STEP_MS.append((name, round((time.perf_counter() - t) * 1000)))


def ok(st, n):
    """The last n ops were accepted."""
    tail = st[-n:]
    return ("accepted", all(e["status"] == "ok" for e in tail), [(e["id"], e["status"], e.get("message")) for e in tail])


def only(before, after, ids):
    """Every board not in ids is untouched."""
    others = {k: v for k, v in diff(before, after).items() if k not in ids}
    return ("nothing else changed", not others, others)


STEP_MS = []

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

# 1. push a face of a plain board
FRONT = {"id": "s1", "type": "push_pull", "target": {"face": face("bottom", [0, -1, 0], [300, 0, 9])}, "distance": 20}
step("push the bottom's front edge out 20", FIX + [FRONT], lambda st, a, b: [
    ok(st, 1), only(a, b, {"bottom"}),
    ("bottom 20 mm deeper", b["boards"]["bottom"]["box"][1] == -20, b["boards"]["bottom"]["box"]),
    ("volume grew by the strip", abs(b["boards"]["bottom"]["vol"] - a["boards"]["bottom"]["vol"] - 564 * 18 * 20) < 0.1,
     b["boards"]["bottom"]["vol"])])

# 2. pushing the holed top face up: the push carries the hole with it (the face it extrudes has the hole in it)
THICK = {"id": "s2", "type": "push_pull", "target": {"face": face("bottom", [0, 0, 1], [100, 100, 18])}, "distance": 6}
step("push the bottom's holed top face up 6", FIX + [THICK], lambda st, a, b: [
    ok(st, 1), only(a, b, {"bottom"}),
    ("the hole stays open through the new 6 mm", abs(b["boards"]["bottom"]["vol"] - (564 * 400 - 1600) * 24) < 0.1,
     b["boards"]["bottom"]["vol"])])

# 2b. the board made thicker by its own FreeCAD value (the Properties panel, T46): the through-hole follows (I24)
BOTTOM_EXT = next(o.Name for o in S.doc.Objects if getattr(o, "SSOp", "") == "p_bottom" and o.TypeId == "Part::Extrusion")
THICK_PROP = {"id": "s2b", "type": "property_edit", "body": "bottom", "object": BOTTOM_EXT, "property": "LengthFwd",
              "value": "24mm", "mode": "value"}
step("make the bottom 24 thick in its FreeCAD value", FIX + [THICK_PROP], lambda st, a, b: [
    ok(st, 1), only(a, b, {"bottom"}),
    ("the through-hole still goes through", abs(b["boards"]["bottom"]["vol"] - (564 * 400 - 1600) * 24) < 0.1,
     b["boards"]["bottom"]["vol"])])

# 3. draw on a linked board: its copy changes too
BUMP = [on_rect("s3r", "shelf", [0, 0, 1], [100, 100, 378], [50, 50]),
        {"id": "s3", "type": "push_pull", "target": {"rect": "s3r"}, "distance": 30}]
step("add a block on the linked shelf", FIX + BUMP, lambda st, a, b: [
    ok(st, 2), only(a, b, {"shelf", "shelf2"}),
    ("shelf grew by the block", abs(b["boards"]["shelf"]["vol"] - a["boards"]["shelf"]["vol"] - 50 * 50 * 30) < 0.1,
     b["boards"]["shelf"]["vol"]),
    ("its linked copy grew the same", b["boards"]["shelf2"]["vol"] == b["boards"]["shelf"]["vol"], b["boards"]["shelf2"])])

# 4. make the copy unique first: the original stays as it was
UNIQUE = {"id": "s4u", "type": "make_unique", "targets": ["shelf2"]}
BUMP2 = [on_rect("s4r", "shelf2", [0, 0, 1], [100, 100, 558], [50, 50]),
         {"id": "s4", "type": "push_pull", "target": {"rect": "s4r"}, "distance": 30}]
step("make the shelf copy unique, then add a block", FIX + [UNIQUE] + BUMP2, lambda st, a, b: [
    ok(st, 3), only(a, b, {"shelf2"}),
    ("the copy grew", abs(b["boards"]["shelf2"]["vol"] - a["boards"]["shelf2"]["vol"] - 50 * 50 * 30) < 0.1,
     b["boards"]["shelf2"]["vol"])])

# 5. move one side of the mirror group: the other follows, reflected (A11b)
MOVE_L = {"id": "s5", "type": "move", "targets": ["left"], "vector": [-50, 0, 0]}
step("move the left side out 50", FIX + [MOVE_L], lambda st, a, b: [
    ok(st, 1), only(a, b, {"left", "right"}),
    ("left at x -50", b["boards"]["left"]["box"][0] == -50, b["boards"]["left"]["box"]),
    ("right followed to x 650", b["boards"]["right"]["box"][3] == 650, b["boards"]["right"]["box"])])

# 5b. move the mirrored copy instead: its original moves the reflected way
MOVE_R = {"id": "s5b", "type": "move", "targets": ["right"], "vector": [30, 0, 0]}
step("move the right side (the mirror) out 30", FIX + [MOVE_R], lambda st, a, b: [
    ok(st, 1), only(a, b, {"left", "right"}),
    ("right at x 612..630", b["boards"]["right"]["box"][0::3] == (612, 630), b["boards"]["right"]["box"]),
    ("left moved the other way, to x -30", b["boards"]["left"]["box"][0] == -30, b["boards"]["left"]["box"])])

# 6. move the whole pin-hole row up 64
MOVE_PINS = {"id": "s6", "type": "move", "targets": [], "cut": {"body": "left", "op": "p_pin"}, "vector": [0, 0, 64], "copy": False}
step("move the pin-hole row up 64", FIX + [MOVE_PINS], lambda st, a, b: [
    ok(st, 1), only(a, b, {"left", "right"}),
    ("same volume (still five holes)", b["boards"]["left"]["vol"] == a["boards"]["left"]["vol"], b["boards"]["left"]["vol"]),
    ("the mirror's holes still match", b["boards"]["right"]["vol"] == b["boards"]["left"]["vol"], b["boards"]["right"]["vol"])])

# 7. retype the pin count right after making it (an amend of a fixture op)
step("retype the pin row as 8 copies", fix_with("pins", count=8), lambda st, a, b: [
    ("accepted", all(e["status"] == "ok" for e in st), [e for e in st if e["status"] != "ok"]),
    ("nine holes in the left side", abs(b["boards"]["left"]["vol"] - (18 * 400 * 720 - 9 * PIN)) < 0.1, b["boards"]["left"]["vol"]),
    ("and in the right", b["boards"]["right"]["vol"] == b["boards"]["left"]["vol"], b["boards"]["right"]["vol"])])

# 8. a move that would take the holes off the board is refused, and leaves the model alone
OFF = {"id": "s8", "type": "move", "targets": [], "cut": {"body": "left", "op": "p_pin"}, "vector": [0, 5000, 0], "copy": False}
step("move the pins off the board (refused)", FIX + [OFF], lambda st, a, b: [
    ("refused", st[-1]["status"] == "failed", st[-1]), only(a, b, set())])

# 9. paint a linked board: both copies change
PAINT = {"id": "s9", "type": "set_material", "targets": ["shelf2"], "material": "black-walnut"}
step("paint the shelf copy walnut", FIX + [PAINT], lambda st, a, b: [
    ok(st, 1), only(a, b, {"shelf", "shelf2"}),
    ("both shelves walnut", b["boards"]["shelf"]["mat"] == b["boards"]["shelf2"]["mat"] == "black-walnut",
     (b["boards"]["shelf"]["mat"], b["boards"]["shelf2"]["mat"]))])

# 10. turn the bottom's grain
GRAIN = {"id": "s10", "type": "turn_grain", "targets": ["bottom"]}
step("turn the bottom's grain", FIX + [GRAIN], lambda st, a, b: [
    ok(st, 1), only(a, b, {"bottom"}),
    ("grain turned 90 degrees", b["boards"]["bottom"]["grain"] != a["boards"]["bottom"]["grain"],
     (a["boards"]["bottom"]["grain"], b["boards"]["bottom"]["grain"]))])

# 11. group two boards and move the group
ASM = [{"id": "s11a", "type": "make_assembly", "targets": ["bottom", "shelf"], "new_id": "a1"},
       {"id": "s11", "type": "move", "targets": ["a1"], "vector": [0, 0, 10]}]
step("assemble bottom and shelf, lift 10", FIX + ASM, lambda st, a, b: [
    ok(st, 2),
    ("both members lifted 10", all(b["boards"][k]["box"][2] == a["boards"][k]["box"][2] + 10 for k in ("bottom", "shelf")),
     {k: b["boards"][k]["box"] for k in ("bottom", "shelf")}),
    ("the group exists", b["groups"].get("a1") == ["bottom", "shelf"], b["groups"]),
    ("the sides didn't move", all(b["boards"][k] == a["boards"][k] for k in ("left", "right")), "")])

# 12. a new board drawn on a face, as a separate board (B)
CAP = [on_rect("s12r", "left", [0, 0, 1], [4, 100, 720], [10, 100]),
       {"id": "s12", "type": "push_pull", "target": {"rect": "s12r"}, "distance": 20, "body": "cap"}]
step("draw a separate cap on the left side", FIX + CAP, lambda st, a, b: [
    ok(st, 2), only(a, b, {"cap"}),
    ("cap sits on top (z 720..740)", b["boards"].get("cap", {}).get("box", (0,) * 6)[2::3] == (720, 740),
     b["boards"].get("cap"))])

# 13. a /N row of new posts
POSTS = [{"id": "s13r", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [700, 0, 0]}, "size": [20, 20]},
         {"id": "s13p", "type": "push_pull", "target": {"rect": "s13r"}, "distance": 100, "body": "post"},
         {"id": "s13", "type": "move", "targets": ["post"], "vector": [300, 0, 0], "copy": True, "count": 3, "divide": True,
          "new_ids": ["post2", "post3", "post4"]}]
step("a post and three copies spread over 300 (/3)", FIX + POSTS, lambda st, a, b: [
    ok(st, 3), only(a, b, {"post", "post2", "post3", "post4"}),
    ("posts at x 700, 800, 900, 1000", [b["boards"].get(k, {}).get("box", (None,))[0] for k in ("post", "post2", "post3", "post4")]
     == [700, 800, 900, 1000], [b["boards"].get(k) for k in ("post2", "post3", "post4")])])

# 14. a hole into the side that the mirror carries across
HOLE_L = [on_rect("s14r", "left", [-1, 0, 0], [0, 200, 100], [30, 30]),
          {"id": "s14", "type": "push_pull", "target": {"rect": "s14r"}, "distance": -18, "through": True}]
step("cut a through-hole in the left side", FIX + HOLE_L, lambda st, a, b: [
    ok(st, 2), only(a, b, {"left", "right"}),
    ("left lost 30 x 30 x 18", abs(a["boards"]["left"]["vol"] - b["boards"]["left"]["vol"] - 30 * 30 * 18) < 0.1,
     b["boards"]["left"]["vol"]),
    ("the mirror has it too", b["boards"]["right"]["vol"] == b["boards"]["left"]["vol"], b["boards"]["right"]["vol"])])

# 15. undo into the fixture itself and redo (sync to a shorter prefix, then back)
def short_prefix(st, a, b):
    return [("shelf copy gone", "shelf2" not in b["boards"] and "shelf" in b["boards"], sorted(b["boards"])),
            ("bottom unpainted", b["boards"]["bottom"]["mat"] == "", b["boards"]["bottom"]["mat"]),
            ("FreeCAD shows the shelf again (copying had hidden it as a definition)", b["boards"]["shelf"]["shown"] == (True, True),
             b["boards"]["shelf"]["shown"])]
step("undo the last two fixture actions", FIX[:-2], short_prefix)

# 16. hide two boards (T28, I37): an undoable property; FreeCAD shows them hidden; a linked copy stays shown
HIDE = {"id": "s16", "type": "hide", "targets": ["bottom", "shelf"], "hidden": True}
step("hide the bottom and the shelf", FIX + [HIDE], lambda st, a, b: [
    ok(st, 1), only(a, b, {"bottom", "shelf"}),
    ("both hidden", b["boards"]["bottom"]["hidden"] and b["boards"]["shelf"]["hidden"], (b["boards"]["bottom"], b["boards"]["shelf"])),
    ("FreeCAD hides them", not b["boards"]["bottom"]["shown"][0] and not b["boards"]["shelf"]["shown"][0],
     (b["boards"]["bottom"]["shown"], b["boards"]["shelf"]["shown"])),
    ("the shelf's linked copy stays shown", not b["boards"]["shelf2"]["hidden"] and b["boards"]["shelf2"]["shown"] == (True, True),
     b["boards"]["shelf2"]),
    ("shapes unchanged", all(b["boards"][k]["vol"] == a["boards"][k]["vol"] for k in ("bottom", "shelf")), "")])

# 16b. unhide one of them again
UNHIDE = {"id": "s16b", "type": "hide", "targets": ["shelf"], "hidden": False}
step("hide two, unhide the shelf", FIX + [HIDE, UNHIDE], lambda st, a, b: [
    ok(st, 2), only(a, b, {"bottom"}),
    ("shelf shown again", not b["boards"]["shelf"]["hidden"] and b["boards"]["shelf"]["shown"][0], b["boards"]["shelf"]),
    ("bottom still hidden", b["boards"]["bottom"]["hidden"] and not b["boards"]["bottom"]["shown"][0], b["boards"]["bottom"])])

# 16c. a hidden board flipped in place stays hidden; making a hidden copy unique keeps it hidden
FLIP = {"id": "s16c", "type": "mirror", "targets": ["bottom"], "plane": {"point": [300, 0, 0], "normal": [1, 0, 0]}, "replace": True}
HIDE2 = {"id": "s16d", "type": "hide", "targets": ["shelf2"], "hidden": True}
UNIQ2 = {"id": "s16e", "type": "make_unique", "targets": ["shelf2"]}
step("flip a hidden board; make a hidden copy unique", FIX + [HIDE, FLIP, HIDE2, UNIQ2], lambda st, a, b: [
    ok(st, 4),
    ("the flipped bottom is still hidden", b["boards"]["bottom"]["hidden"] and not b["boards"]["bottom"]["shown"][0], b["boards"]["bottom"]),
    ("the unique shelf copy is still hidden", b["boards"]["shelf2"]["hidden"] and not b["boards"]["shelf2"]["shown"][0], b["boards"]["shelf2"])])

# 16d. hiding a board that isn't there is refused
step("hide a board that doesn't exist (refused)", FIX + [{"id": "s16f", "type": "hide", "targets": ["nope"], "hidden": True}],
     lambda st, a, b: [("refused", st[-1]["status"] == "failed", st[-1]), only(a, b, set())])

T_STEPS = time.perf_counter() - T0 - T_FIX

# ---------- the cumulative story: steps one after another, as a person would ----------
STORY = FIX + [FRONT, THICK] + BUMP + [PAINT, GRAIN] + ASM + POSTS + HOLE_L + [HIDE, UNHIDE]
try:
    S.sync(STORY)
    bad = [(e["id"], e.get("message")) for e in S.status() if e["status"] != "ok"]
    check("story: every action accepted", not bad, bad)
    live = snap(S)
    f = Session(None)
    f.sync(STORY)
    fresh = snap(f)
    f.close()
    check("story: live session equals a fresh build", live == fresh, diff(fresh, live))
    S.save()
    path = S.path
    S.close()
    S = Session(path)
    check("story: reopened file equals the live session", snap(S) == live, diff(live, snap(S)))
    import zipfile
    import xml.etree.ElementTree as ET
    gui = ET.fromstring(zipfile.ZipFile(path).read("GuiDocument.xml"))
    vis = {vp.get("name"): vp.find(".//Property[@name='Visibility']/Bool").get("value") for vp in gui.iter("ViewProvider")}
    names = {bid: o.Name for bid, o in S.model.bodies().items()}
    glb = os.path.join(TESTDIR, "story.glb")
    write_glb(S.model, glb)
    gjs = json.loads(open(glb, "rb").read()[20:20 + int.from_bytes(open(glb, "rb").read()[12:16], "little")])
    in_glb = {n["name"] for n in gjs.get("nodes", [])}
    check("story: the Blender export leaves out the hidden bottom", "bottom" not in in_glb and {"left", "shelf"} <= in_glb, sorted(in_glb))
    check("story: FreeCAD's view part hides the hidden bottom and shows the rest",
          vis.get(names["bottom"]) == "false" and all(vis.get(names[k]) == "true" for k in ("left", "shelf", "shelf2", "post")),
          {k: vis.get(n) for k, n in names.items()})
    check("story: no invalid FreeCAD objects", not [o.Name for o in S.doc.Objects if "Invalid" in o.State])
    how, _ = S.sync(FIX)
    check("story: undo back to the fixture after reopening", snap(S) == S0, (how, diff(S0, snap(S))))
except Exception:
    check("story: ran without an error", False, traceback.format_exc(limit=3))
finally:
    S.close()

# ---------- a file saved before hiding existed (T28): its boards get SSHidden on opening ----------
try:
    old = Session(os.path.join(TESTDIR, "before-t28.FCStd"), fresh=True)
    old.sync(FIX)
    for o in old.model.bodies().values():
        o.removeProperty("SSHidden")
    old.save()
    old.close()
    old = Session(os.path.join(TESTDIR, "before-t28.FCStd"))
    old.sync(FIX + [HIDE])
    check("old file: hiding works after reopening", old.status()[-1]["status"] == "ok" and old.model.body("bottom").SSHidden
          and not old.model.body("bottom").Visibility, old.status()[-1])
    old.close()
except Exception:
    check("old file: ran without an error", False, traceback.format_exc(limit=3))

# T34 array source promotion: preserve the native definition and all survivor positions/spacing.
try:
    path = os.path.join(TESTDIR, "selection.FCStd")
    a = Session(path, fresh=True)
    base = FIX + [{"id": "row", "type": "move", "targets": ["shelf"], "copy": True,
                   "vector": [0, 120, 0], "count": 3, "new_ids": ["row1", "row2", "row3"]}]
    a.sync(base)
    original = snap(a)
    removed = base + [{"id": "del1", "type": "delete", "targets": ["shelf", "row1"]}]
    a.sync(removed)
    check("delete row original: accepted", a.status()[-1]["status"] == "ok", a.status()[-1])
    after = snap(a)
    check("delete linked original: shared definition names a surviving original",
          a.model.definition(a.model.body("shelf2")).BodyId in {"shelf2", "row2", "row3"})
    check("delete row original: unselected boards preserved exactly", all(v == after["boards"][k]
          for k, v in original["boards"].items() if k not in {"shelf", "row1"}), diff(original, after))
    arr = next(o for o in a.doc.Objects if getattr(o, "SSRole", "") == "array")
    check("delete row original: first surviving member promoted", arr.SSSource == "row2"
          and not a.model.body("row2").SSArray and bool(a.model.body("row3").SSArray), arr.SSSource)
    moved = removed + [{"id": "after_delete", "type": "move", "targets": ["row3"], "vector": [10, 0, 0]}]
    a.sync(moved)
    check("promoted row: moving survivor moves the row once", all(snap(a)["boards"][k]["box"][0] == after["boards"][k]["box"][0] + 10
          for k in ("row2", "row3")), a.status()[-1])
    a.sync(removed)
    a.export(os.path.join(TESTDIR, "selection-out"))
    entries = json.load(open(os.path.join(TESTDIR, "selection-out", "bodies.json")))
    check("promoted row: exported identity follows the new original", all(e["row"] == "row2" for e in entries if e["id"] in ("row2", "row3")), entries)
    # The deleted linked instance is absent from scene/render outputs, its definition still editable.
    dfn = a.model.definition(a.model.body("row2"))
    plane = next(o for o in dfn.Group if o.TypeId == "Part::Plane")
    edited = removed + [{"id": "edit_survivor", "type": "property_edit", "body": "row2", "object": plane.Name,
                        "property": "Length", "value": "450mm", "mode": "value"}]
    a.sync(edited)
    check("promoted original: native dimensions still edit linked survivors", a.status()[-1]["status"] == "ok"
          and snap(a)["boards"]["row2"]["vol"] == snap(a)["boards"]["row3"]["vol"]
          and snap(a)["boards"]["row2"]["vol"] != after["boards"]["row2"]["vol"], a.status()[-1])
    a.sync(removed)
    a.save(); a.close(); a = Session(path)
    check("delete: saved/reopened model preserves survivors and promoted source", snap(a) == after
          and next(o for o in a.doc.Objects if getattr(o, "SSRole", "") == "array").SSSource == "row2")
    deleted = [o for o in a.doc.Objects if getattr(o, "SSRole", "") == "deleted"]
    a.sync(removed)
    check("delete: native source dependencies remain invisible after reopen", deleted and all(not o.Visibility for o in deleted))
    a.sync(base)
    check("delete: undo after reopen restores original and all members", snap(a) == original)
    a.sync(removed)
    check("delete: redo after reopen removes the same selection", snap(a) == after)
    rebuilt = Session(None); rebuilt.sync(removed)
    check("delete: rebuilt model matches live", snap(rebuilt) == after)
    rebuilt.close()
    a.sync(removed + [{"id": "bad_delete", "type": "delete", "targets": ["row2", "missing"]}])
    check("delete: invalid target aborts the whole action", a.status()[-1]["status"] == "failed" and snap(a) == after, a.status()[-1])
    a.close()
except Exception:
    check("selection story: ran without an error", False, traceback.format_exc(limit=4))

total = time.perf_counter() - T0
slow = sorted(STEP_MS, key=lambda x: -x[1])[:3]
print(f"timing: fixture {T_FIX:.1f} s, {len(STEP_MS)} steps {T_STEPS:.1f} s, total {total:.1f} s; slowest {slow}")
print(f"SCENARIO TESTS: {R[0]} passed, {R[1]} failed")
