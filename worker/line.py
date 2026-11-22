"""Saved, editable straight drawings and polygon profiles (T82)."""
import math
import FreeCAD as App
import Part
import Sketcher
from common import OpError, TOL, V, add_props, rotation_from, unit, vec


class LineActions:
    def polygon_face(self, points, normal):
        pts = [vec(p) for p in points]
        if len(pts) < 3 or any(not math.isfinite(c) for p in pts for c in p):
            raise OpError("outline needs at least three finite points")
        n = unit(normal)
        if any(abs((p - pts[0]).dot(n)) > TOL for p in pts):
            raise OpError("outline points must lie on the drawing plane")
        face = Part.Face(Part.makePolygon(pts + [pts[0]]))
        if not face.isValid() or face.Area < TOL * TOL:
            raise OpError("outline must enclose a simple face")
        if face.normalAt(0, 0).dot(n) < 0: face.reverse()
        return face

    def op_line(self, op):
        origin, x, y, n, on = self.plane_from(op["plane"])
        end = vec(op["end"])
        delta = end - origin
        if any(not math.isfinite(c) for c in end) or delta.Length < TOL or abs(delta.dot(n)) > TOL:
            raise OpError("line needs a finite nonzero endpoint on its plane")
        sketch = self.doc.addObject("Sketcher::SketchObject", "Line")
        sketch.Label = op["id"]
        sketch.Placement = App.Placement(origin, rotation_from(x, y, n))
        sketch.addGeometry(Part.LineSegment(V(0, 0, 0), V(delta.dot(x), delta.dot(y), 0)), False)
        sketch.addConstraint(Sketcher.Constraint("Block", 0))
        add_props(sketch, SSLineId=op["id"], OnBody=on)
        self.group("Lines", "Lines").addObject(sketch)
        if op.get("outline"):
            profile = self.face_feature(self.polygon_face(op["outline"], n), op["id"] + " outline")
            add_props(profile, RectId=op["id"], OnBody=on, SSRole="line-profile")
            self.group("Rectangles", "Rectangles").addObject(profile)
        self.doc.recompute()
        return []
