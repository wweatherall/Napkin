"""---------- a file saved before hiding existed (T28): its boards get SSHidden on opening ---------- (T76)."""
import os
import traceback
from session import Session

requires = ('92_visibility.py',)

def run(ctx):
    FIX = ctx.FIX
    TESTDIR = ctx.TESTDIR
    check = ctx.check
    HIDE = ctx.actions['HIDE']

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
