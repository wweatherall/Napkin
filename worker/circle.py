"""Exact editable circle profiles (T81); only the viewport tessellates them.

Auto-discovered `CircleActions`: shares legacy `RectId` identity.
Entry points: op_circle, circle_feature, circle_world."""
import math
import FreeCAD as App
import Part
import Sketcher
from common import OpError, TOL, V, add_props, rotation_from, unit


class CircleActions:
    def circle_feature(self, center, x, y, radius, label, existing=None):
        sketch = existing or self.doc.addObject("Sketcher::SketchObject", "Circle")
        if existing is None:
            sketch.Label = label
            sketch.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), radius), False)
            sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 3, -1, 1))
            sketch.addConstraint(Sketcher.Constraint("Radius", 0, radius))
        sketch.Placement = App.Placement(center, rotation_from(unit(x), unit(y), unit(x.cross(y))))
        return sketch

    def circle_world(self, sketch):
        gp = sketch.Placement
        group = sketch.getParentGeoFeatureGroup()
        while group is not None:
            gp = group.Placement.multiply(gp)
            group = group.getParentGeoFeatureGroup()
        x = gp.Rotation.multVec(V(1, 0, 0))
        y = gp.Rotation.multVec(V(0, 1, 0))
        return gp.Base, x, y, unit(x.cross(y)), sketch.Geometry[0].Radius

    def op_circle(self, op):
        rid = op["id"]
        if self.rect_obj(rid) is not None:
            raise OpError(f"profile id '{rid}' already exists")
        radius = float(op["radius"])
        if not math.isfinite(radius) or radius < TOL:
            raise OpError("circle radius must be at least 0.001 mm")
        origin, x, y, _, on = self.plane_from(op["plane"])
        center = op.get("center", [0, 0])
        sketch = self.circle_feature(origin + x * center[0] + y * center[1], x, y, radius, rid)
        # RectId and target.rect are the existing profile identity path, shared with rectangles.
        add_props(sketch, RectId=rid, OnBody=on)
        self.group("Rectangles", "Rectangles").addObject(sketch)
        self.doc.recompute()
        return []
