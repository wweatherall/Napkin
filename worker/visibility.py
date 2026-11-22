"""Hide and unhide (T28, I37): SketchUp-style hiding, kept as a board property so it is undoable and saved."""
from common import *


class VisibilityActions:
    """Part of Model (model.py): works through self on the FreeCAD document.

    A hidden board has SSHidden = True. FreeCAD's undo takes SSHidden back but not Visibility (FreeCAD doesn't
    record Visibility in its transactions), so Visibility is never set by an op: show_as_hidden() works it out
    from SSHidden after every sync, and the saved file then shows exactly the boards that aren't hidden."""

    def op_hide(self, op):
        hidden = bool(op.get("hidden", True))
        for t in op["targets"]:
            obj = self.body(t)
            if not hasattr(obj, "SSHidden"):
                raise OpError(f"'{t}' can't be hidden (the file was made before hiding existed; reopen it)")
            obj.SSHidden = hidden
        return list(op["targets"])

    def add_hidden_props(self):
        """Boards from files saved before T28 get SSHidden. Call outside any transaction (on opening a file)."""
        for obj in self.bodies().values():
            if not hasattr(obj, "SSHidden"):
                add_props(obj, SSHidden=False)

    def show_as_hidden(self):
        """Each board's Visibility from SSHidden (a board without it is shown)."""
        for obj in self.doc.Objects:
            if getattr(obj, "SSRole", "") not in ("body", "deleted"):
                continue
            want = obj.SSRole == "body" and not bool(getattr(obj, "SSHidden", False))
            if obj.Visibility != want:
                obj.Visibility = want
