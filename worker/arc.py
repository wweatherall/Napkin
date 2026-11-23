"""Saved circular drawings (T83)."""
import math

import FreeCAD as App
import Part
import Sketcher

from common import OpError, TOL, V, add_props, rotation_from, vec


class ArcActions:
    def op_arc(self, op):
        spec = op["plane"]
        src = spec.get("on", spec)
        start = vec(src["point"] if "on" in spec else src["origin"])
        normal = vec(src["normal"])
        mid, end = vec(op["mid"]), vec(op["end"])
        if any(not math.isfinite(c) for p in (start, normal, mid, end) for c in p):
            raise OpError("arc needs finite points and normal")
        origin, x, y, n, on = self.plane_from(spec)
        u, v = mid - origin, end - origin
        if abs(u.dot(n)) > TOL or abs(v.dot(n)) > TOL:
            raise OpError("arc points must lie on the drawing plane")
        # Use the same on-face projection and local sketch axes as Line.
        if on:
            _, source, _ = self.resolve_face(src)
            anchor = source.Vertexes[0].Point
            origin -= n * (origin - anchor).dot(n)
        u = V(u.dot(x), u.dot(y), 0)
        v = V(v.dot(x), v.dot(y), 0)
        if min(u.Length, v.Length, (v - u).Length) < TOL:
            raise OpError("arc needs three distinct points")
        if u.cross(v).Length < TOL * v.Length:
            raise OpError("arc points must not be collinear")

        geometry = Part.Arc(V(0, 0, 0), u, v)
        sketch = self.doc.addObject("Sketcher::SketchObject", "Arc")
        sketch.Label = op["id"]
        sketch.Placement = App.Placement(origin, rotation_from(x, y, n))
        sketch.addGeometry(geometry, False)
        sketch.addConstraint(Sketcher.Constraint("Block", 0))
        add_props(sketch, SSLineId=op["id"], OnBody=on)
        self.group("Lines", "Lines").addObject(sketch)
        self.doc.recompute()
        return []
