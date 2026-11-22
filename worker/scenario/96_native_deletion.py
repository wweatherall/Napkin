"""I46 (William, 2026-11-21): Delete takes a board out of the FreeCAD file, features and all, unless a surviving (T76)."""
import os
import traceback
from session import Session
from scenario.context import snap

requires = ('20_push.py',)

def run(ctx):
    FIX = ctx.FIX
    TESTDIR = ctx.TESTDIR
    check = ctx.check
    THICK_PROP = ctx.actions['THICK_PROP']

    # I46 (William, 2026-11-21): Delete takes a board out of the FreeCAD file, features and all, unless a surviving
    # link, mirror or array still builds from it; then it stays, hidden, until that goes too.
    try:
        a = Session(os.path.join(TESTDIR, "delete-native.FCStd"), fresh=True)
        native = lambda: {o.Name for o in a.doc.Objects}
        kept = lambda: [o for o in a.doc.Objects if getattr(o, "SSRole", "") == "deleted"]
        a.sync(FIX)
        before, fixture = native(), snap(a)
        bottom = a.model.body("bottom")
        names = {bottom.Name} | {o.Name for o in bottom.OutListRecursive if o in bottom.Group or bottom in o.InListRecursive}
        left, right = a.model.body("left").Name, a.model.body("right").Name
        a.sync(FIX + [{"id": "d1", "type": "delete", "targets": ["bottom"]}])
        check("delete plain board: it and its features leave the FreeCAD file", a.status()[-1]["status"] == "ok"
              and names <= before - native() and not kept(), [sorted(names - (before - native())), [o.Name for o in kept()]])
        a.sync(FIX)
        check("delete plain board: undo brings it all back", native() == before and snap(a) == fixture)
        a.sync(FIX + [THICK_PROP])
        check("delete plain board, undo, then thicken it: its through-hole still follows (I24)",
              abs(snap(a)["boards"]["bottom"]["vol"] - fixture["boards"]["bottom"]["vol"] * 24 / 18) < 0.1,
              [snap(a)["boards"]["bottom"]["vol"], fixture["boards"]["bottom"]["vol"]])
        a.sync(FIX)
        a.sync(FIX + [{"id": "d1", "type": "delete", "targets": ["left"]}])
        check("delete mirror source: kept hidden while its mirror needs it", [o.Name for o in kept()] == [left]
              and not kept()[0].Visibility and "right" in snap(a)["boards"], [o.Name for o in kept()])
        a.sync(FIX + [{"id": "d1", "type": "delete", "targets": ["left"]}, {"id": "d2", "type": "delete", "targets": ["right"]}])
        check("delete the mirror later: the kept source goes with it", not kept() and left not in native() and right not in native(),
              [o.Name for o in kept()])
        a.sync(FIX + [{"id": "d1", "type": "delete", "targets": ["right", "left"]}])
        check("delete mirror and source together: both leave the file", not kept() and left not in native() and right not in native())
        a.sync(FIX)
        shelf_dfn = a.model.definition(a.model.body("shelf")).Name
        row = FIX + [{"id": "row", "type": "move", "targets": ["shelf"], "copy": True, "vector": [0, 120, 0], "count": 3,
                      "new_ids": ["row1", "row2", "row3"]}]
        a.sync(row + [{"id": "d1", "type": "delete", "targets": ["shelf", "shelf2", "row1", "row2", "row3"]}])
        check("delete every copy of a component: its definition and array leave the file too", a.status()[-1]["status"] == "ok"
              and shelf_dfn not in native() and not [o for o in a.doc.Objects if getattr(o, "SSRole", "") == "array"] and not kept(),
              sorted(native() - before))
        a.sync(row)
        check("delete every copy: undo restores the row", set(snap(a)["boards"]) >= {"shelf", "shelf2", "row1", "row2", "row3"})
        a.close()
    except Exception:
        check("delete removal story: ran without an error", False, traceback.format_exc(limit=4))
