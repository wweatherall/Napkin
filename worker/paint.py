"""Paint and grain (T15, M03): materials on a board definition, grain directions."""
from common import *
from export import PALETTE


class PaintActions:
    """Part of Model (model.py): works through self on the FreeCAD document."""

    def op_set_material(self, op):
        """Paint (T15): the material goes on the board's definition (so linked copies share it) and, as a FreeCAD
        material card, on its current solid (ShapeMaterial), where FreeCAD's FEM and renderers read it."""
        key = op["material"]
        card = material_card(key) if key else None
        if key and card is None and key not in PALETTE:
            raise OpError(f"unknown material '{key}'")
        changed = []
        for t in op["targets"]:
            dfn = self.definition(self.body(t))
            if not hasattr(dfn, "SSMaterial"):
                raise OpError(f"'{t}' has no material field")
            dfn.SSMaterial = key
            tip = getattr(dfn, "Tip", None)
            if card is not None and tip is not None and hasattr(tip, "ShapeMaterial"):
                tip.ShapeMaterial = card
            changed += [b for b, o in self.bodies().items() if self.definition(o) is dfn]
        return changed

    def grain_local(self, dfn):
        """The board's grain in its own frame: as set, else along its longest edge (M03)."""
        g = getattr(dfn, "SSGrain", None)
        if g is not None and g.Length > 1e-9:
            return g
        return self.board_axes(dfn)[0]

    @staticmethod
    def board_axes(dfn):
        tip = getattr(dfn, "Tip", None)
        bb = tip.Shape.BoundBox if tip is not None else Part.getShape(dfn).BoundBox
        axes = sorted([(bb.XLength, App.Vector(1, 0, 0)), (bb.YLength, App.Vector(0, 1, 0)), (bb.ZLength, App.Vector(0, 0, 1))],
                      key=lambda a: -a[0])
        return [a[1] for a in axes]

    def op_turn_grain(self, op):
        """Turn the grain 90 degrees in the board's face (Q30): between its longest and its middle edge."""
        changed = []
        for t in op["targets"]:
            dfn = self.definition(self.body(t))
            if not hasattr(dfn, "SSGrain"):
                raise OpError(f"'{t}' was made before grain direction existed: make it unique or redraw it")
            long_ax, mid_ax, _ = self.board_axes(dfn)
            g = self.grain_local(dfn)
            dfn.SSGrain = mid_ax if abs(g.dot(long_ax)) > 0.9 else long_ax
            changed += [b for b, o in self.bodies().items() if self.definition(o) is dfn]
        return changed

    def across_local(self, dfn):
        """Across the board's width: the one of its two long edges the grain doesn't run along."""
        long_ax, mid_ax, _ = self.board_axes(dfn)
        return mid_ax if abs(self.grain_local(dfn).dot(long_ax)) > 0.9 else long_ax

    def grain_world(self, obj, which="grain"):
        """The grain (or across-the-width) direction as the board appears, through instances and mirrors."""
        if self.is_mirror(obj):
            g = self.grain_world(self.mirror_source(obj), which)
            n = unit(obj.Normal)
            return g - n * (2 * g.dot(n))
        dfn = self.definition(obj)
        return obj.Placement.Rotation.multVec(self.grain_local(dfn) if which == "grain" else self.across_local(dfn))
