"""15. undo into the fixture itself and redo (sync to a shorter prefix, then back) (T76)."""

requires = ()

def run(ctx):
    FIX = ctx.FIX
    step = ctx.step

    # 15. undo into the fixture itself and redo (sync to a shorter prefix, then back)
    def short_prefix(st, a, b):
        return [("shelf copy gone", "shelf2" not in b["boards"] and "shelf" in b["boards"], sorted(b["boards"])),
                ("bottom unpainted", b["boards"]["bottom"]["mat"] == "", b["boards"]["bottom"]["mat"]),
                ("FreeCAD shows the shelf again (copying had hidden it as a definition)", b["boards"]["shelf"]["shown"] == (True, True),
                 b["boards"]["shelf"]["shown"])]
    step("undo the last two fixture actions", FIX[:-2], short_prefix)
