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
        pts = [p - n * (p - pts[0]).dot(n) for p in pts]
        face = Part.Face(Part.makePolygon(pts + [pts[0]]))
        if not face.isValid() or face.Area < TOL * TOL:
            raise OpError("outline must enclose a simple face")
        if face.normalAt(0, 0).dot(n) < 0: face.reverse()
        return face

    def region_face(self, spec):
        n = unit(vec(spec["normal"]))
        outer = self.polygon_face(spec["outline"], n)
        result = outer
        for points in spec.get("holes", []):
            hole = self.polygon_face(points, n)
            if abs((hole.CenterOfMass - outer.CenterOfMass).dot(n)) > TOL:
                raise OpError("region holes must lie on the outline plane")
            if abs(outer.common(hole).Area - hole.Area) > TOL:
                raise OpError("region hole leaves its outline")
            result = result.cut(hole)
        if len(result.Faces) != 1 or result.Area < TOL * TOL or not result.isValid():
            raise OpError("region must enclose one valid face")
        face = result.Faces[0]
        if face.normalAt(0, 0).dot(n) < 0: face.reverse()
        return face, n

    def native_region(self, source, predicted, spec):
        """Refine the selected tessellated cell against native curved boundaries and drawings."""
        ids = set(spec.get("lines", []))
        drawings = [edge for obj in self.doc.Objects if getattr(obj, "SSLineId", "") in ids
                    for edge in Part.getShape(obj).Edges]
        if not drawings or all(isinstance(e.Curve, Part.Line) for e in [*source.Edges, *drawings]):
            return predicted
        from BOPTools.SplitAPI import slice
        tools = []
        span = source.BoundBox.DiagonalLength * 2 + 1
        for edge in drawings:
            if not isinstance(edge.Curve, Part.Line):
                tools.append(edge)
                continue
            a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
            direction = unit(b - a)
            tools.append(Part.makeLine(a - direction * span, b + direction * span))
        pieces = slice(source, tools, "Split", TOL).Faces
        chosen = [f for f in pieces if f.common(predicted).Area > f.Area * 0.5]
        if not chosen:
            raise OpError("region no longer matches the native curved face")
        result = chosen[0]
        for f in chosen[1:]: result = result.fuse(f)
        result = result.removeSplitter()
        # The existing 0.1 mm export deflection and 64-segment circle preview bound the expected difference.
        discrepancy = result.cut(predicted).Area + predicted.cut(result).Area
        if len(result.Faces) != 1 or discrepancy > max(TOL, source.Length * 0.2, source.Area * 0.005):
            raise OpError("region differs from its native curved boundary")
        face = result.Faces[0]
        if face.normalAt(0, 0).dot(vec(spec["normal"])) < 0: face.reverse()
        return face

    def op_line(self, op):
        origin, x, y, n, on = self.plane_from(op["plane"])
        end = vec(op["end"])
        delta = end - origin
        if any(not math.isfinite(c) for c in end) or delta.Length < TOL or abs(delta.dot(n)) > TOL:
            raise OpError("line needs a finite nonzero endpoint on its plane")
        if on:
            _, source, _ = self.resolve_face(op["plane"]["on"])
            anchor = source.Vertexes[0].Point
            origin -= n * (origin - anchor).dot(n)
            end -= n * (end - anchor).dot(n)
            delta = end - origin
        sketch = self.doc.addObject("Sketcher::SketchObject", "Line")
        sketch.Label = op["id"]
        sketch.Placement = App.Placement(origin, rotation_from(x, y, n))
        sketch.addGeometry(Part.LineSegment(V(0, 0, 0), V(delta.dot(x), delta.dot(y), 0)), False)
        sketch.addConstraint(Sketcher.Constraint("Block", 0))
        add_props(sketch, SSLineId=op["id"], OnBody=on)
        self.group("Lines", "Lines").addObject(sketch)
        if op.get("outline"):
            # Self-crossing chains remain valid drawings; their bounded cells are found by the viewport.
            try:
                face = self.polygon_face([p - n * (p - origin).dot(n) for p in map(vec, op["outline"])], n)
            except (OpError, Part.OCCError):
                face = None
            if face is not None:
                profile = self.face_feature(face, op["id"] + " outline")
                add_props(profile, RectId=op["id"], OnBody=on, SSRole="line-profile")
                self.group("Rectangles", "Rectangles").addObject(profile)
        self.doc.recompute()
        return []
