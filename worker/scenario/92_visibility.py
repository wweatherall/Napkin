"""16. hide two boards (T28, I37): an undoable property; FreeCAD shows them hidden; a linked copy stays shown (T76)."""
from scenario.context import ok, only

requires = ()

def run(ctx):
    FIX = ctx.FIX
    step = ctx.step

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
    ctx.actions.update(HIDE=HIDE, UNHIDE=UNHIDE)
