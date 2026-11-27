"""Exact editable regular polygon profiles (T84): a native constrained sketch, like circle.py's circles.

Auto-discovered `PolygonActions`: Sketcher::SketchObject marked `SSRole = polygon-profile` (distinguished from
circle sketches by push.py). Shares `RectId`.
Entry points: op_polygon, polygon_feature, polygon_world."""
import math
import FreeCAD as App
from ProfileLib.RegularPolygon import makeRegularPolygon
import Sketcher
from common import OpError, TOL, V, add_props, rotation_from, unit, vec

MIN_SIDES, MAX_SIDES = 3, 64      # viewport/tools/polygon_tool.gd has the same range


class PolygonActions:
    def polygon_feature(self, center, x, y, radius, sides, label, existing=None):
        """A regular polygon whose first corner is `radius` along the sketch's x axis from its centre."""
        sketch = existing or self.doc.addObject("Sketcher::SketchObject", "Polygon")
        if existing is None:
            sketch.Label = label
            # edges 0..sides-1, then the construction circle through the corners
            makeRegularPolygon(sketch, sides, V(0, 0, 0), V(radius, 0, 0), False)
            sketch.addConstraint(Sketcher.Constraint("Coincident", sides, 3, -1, 1))   # centre on the origin
            sketch.addConstraint(Sketcher.Constraint("Radius", sides, radius))
            sketch.addConstraint(Sketcher.Constraint("PointOnObject", 0, 1, -1))       # first corner on x: no spin
            add_props(sketch, SSRole="polygon-profile")
        sketch.Placement = App.Placement(center, rotation_from(unit(x), unit(y), unit(x.cross(y))))
        return sketch

    def polygon_world(self, sketch):
        """(centre, x, y, normal, radius, sides) in world coordinates."""
        gp = sketch.Placement
        group = sketch.getParentGeoFeatureGroup()
        while group is not None:
            gp = group.Placement.multiply(gp)
            group = group.getParentGeoFeatureGroup()
        x = gp.Rotation.multVec(V(1, 0, 0))
        y = gp.Rotation.multVec(V(0, 1, 0))
        sides = len(sketch.Geometry) - 1
        return gp.Base, x, y, unit(x.cross(y)), sketch.Geometry[sides].Radius, sides

    def op_polygon(self, op):
        rid = op["id"]
        if self.rect_obj(rid) is not None:
            raise OpError(f"profile id '{rid}' already exists")
        radius = float(op["radius"])
        if not math.isfinite(radius) or radius < TOL:
            raise OpError("polygon radius must be at least 0.001 mm")
        sides = op.get("sides")
        if isinstance(sides, float) and sides.is_integer():      # the viewport's JSON may write 6 as 6.0
            sides = int(sides)
        if type(sides) is not int or not MIN_SIDES <= sides <= MAX_SIDES:
            raise OpError(f"a polygon needs {MIN_SIDES} to {MAX_SIDES} sides")
        origin, x, y, n, on = self.plane_from(op["plane"])
        center = op.get("center", [0, 0])
        at = origin + x * center[0] + y * center[1]
        if op.get("x") is not None:                              # toward the first corner, as rect's "x"
            toward = vec(op["x"])
            toward = toward - n * toward.dot(n)
            if toward.Length < TOL:
                raise OpError("polygon x axis is degenerate")
            x = unit(toward)
            y = unit(n.cross(x))
        sketch = self.polygon_feature(at, x, y, radius, sides, rid)
        add_props(sketch, RectId=rid, OnBody=on)
        self.group("Rectangles", "Rectangles").addObject(sketch)
        self.doc.recompute()
        return []
