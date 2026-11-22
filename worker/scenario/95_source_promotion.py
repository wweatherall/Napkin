"""T34 array source promotion: preserve the native definition and all survivor positions/spacing. (T76)."""
import json
import os
import traceback
from session import Session
from scenario.context import diff, snap

requires = ()

def run(ctx):
    FIX = ctx.FIX
    TESTDIR = ctx.TESTDIR
    check = ctx.check

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
        check("delete: nothing it needed is left behind in the file after reopen (I46)", not deleted, [o.Name for o in deleted])
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
