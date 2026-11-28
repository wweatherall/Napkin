"""Rectangles and Push/Pull: new boards, cuts and joins, through-cuts (I24), pocket-floor ties (T59).

Auto-discovered `PushActions`: handles rect, rectangle/circle/polygon/line-profile/region pushes, through-cuts
(`SSThrough`, `through_all`; does not imply arbitrary face-attachment), pocket-floor ties (`_find_floor_cutter`,
`tie_to_floor`, `SSTiedTo`, `_detach_floor_cuts`), `edge_fit`, and `resize_stock` (returning sibling `BodyId`s via
`plane_fit.family_bodies`). Consecutive cuts share `Part::Cut` with compound cutters; consecutive additions use
`Part::MultiFuse` (older per-op chains remain supported). Cutter identity follows `SSOp` (`cutter_of`/`tools_of`)."""
import math
import Part
from common import NORMAL_TOL, OpError, TOL, add_props, unit, vec


class PushActions:
    """Part of Model (model.py): works through self on the FreeCAD document."""

    # ---------- helpers ----------
    @staticmethod
    def _axis_of(u):
        return next((i for i in range(3) if abs(abs(u[i]) - 1.0) < 1e-6), None)

    @staticmethod
    def _has_expr(obj, prop):
        return any(path.lstrip(".") == prop for path, _ in getattr(obj, "ExpressionEngine", []))

    @staticmethod
    def _cut_far_level(src, axis, sign):
        edge = "XYZ"[axis] + ("Max" if sign > 0 else "Min")
        return getattr(src.Base.Shape.BoundBox, edge) + sign * src.LengthFwd.Value

    # ---------- operations ----------
    @staticmethod
    def through_all(ext, plane, run_base, direction, level_pt):
        """A cut pushed to the opposite face (I24): its length follows the board instead of a number. It runs to
        the far side of the board (as it was before this run of cuts) plus 1 mm, and back past the face it was
        drawn on by as much as the board has grown on that side since. Make the board thicker or thinner in
        FreeCAD and the hole stays through. Only for axis-aligned pushes (all of them, today)."""
        u = unit(direction)
        axis = PushActions._axis_of(u)
        if axis is None:
            return
        A = "XYZ"[axis]
        bb = run_base.Shape.BoundBox
        lo, hi = getattr(bb, A + "Min"), getattr(bb, A + "Max")
        level = level_pt[axis]
        P, B = plane.Name, run_base.Name
        if u[axis] < 0:            # cutting toward the board's low side
            fwd = f"({P}.Shape.BoundBox.{A}Min - {B}.Shape.BoundBox.{A}Min) * 1mm + 1mm"
            grown = f"{B}.Shape.BoundBox.{A}Max - {P}.Shape.BoundBox.{A}Max - {hi - level!r}"
        else:
            fwd = f"({B}.Shape.BoundBox.{A}Max - {P}.Shape.BoundBox.{A}Max) * 1mm + 1mm"
            grown = f"{P}.Shape.BoundBox.{A}Min - {B}.Shape.BoundBox.{A}Min - {level - lo!r}"
        ext.setExpression("LengthFwd", fwd)
        ext.setExpression("LengthRev", f"(({grown}) > 0 ? ({grown}) : 0) * 1mm")

    @staticmethod
    def tie_to_floor(ext, plane, floor_ext, direction):
        """A cut made up to a pocket's floor (T59, I26b): its length follows the floor cutter's depth."""
        u = unit(direction)
        axis = PushActions._axis_of(u)
        if axis is None:
            return
        A = "XYZ"[axis]
        NB, FB, FE = plane.Name, floor_ext.Base.Name, floor_ext.Name
        if u[axis] < 0:
            fwd = f"({NB}.Shape.BoundBox.{A}Min - {FB}.Shape.BoundBox.{A}Min) * 1mm + {FE}.LengthFwd"
        else:
            fwd = f"({FB}.Shape.BoundBox.{A}Max - {NB}.Shape.BoundBox.{A}Max) * 1mm + {FE}.LengthFwd"
        ext.setExpression("LengthFwd", fwd)

    def _find_floor_cutter(self, container, direction, face_normal, point):
        """Find the first Part::Extrusion cutter in container whose far end is the floor at (point, face_normal)."""
        u = unit(direction)
        axis = self._axis_of(u)
        if axis is None:
            return None
        if unit(face_normal).dot(u) > -NORMAL_TOL:
            return None
        sign = 1.0 if u[axis] > 0 else -1.0
        for b in container.Group:
            if b.TypeId != "Part::Cut":
                continue
            for t in self.tools_of(b):
                src = t.Base if self.is_array(t) else t
                if src is None or src.TypeId != "Part::Extrusion" or src.Base is None:
                    continue
                if getattr(src, "SSThrough", False) or self._has_expr(src, "LengthRev"):
                    continue
                if src.Base.Shape.isNull() or t.Shape.isNull() or src.Dir.Length < 1e-12:
                    continue
                sd = unit(src.Dir)
                if self._axis_of(sd) != axis or (sd - u).Length > 1e-6:
                    continue
                if abs(self._cut_far_level(src, axis, sign) - point[axis]) <= TOL and t.Shape.isInside(point, TOL, True):
                    return src
        return None

    def _detach_floor_cuts(self, board, face_normal, point):
        """Pushing a tied pocket's floor again detaches it, keeping its current depth (I26b)."""
        c, fr = self.edit_frame(board)
        p = fr.pt(point)
        fn = unit(fr.dir(face_normal))
        for b in c.Group:
            if b.TypeId != "Part::Cut":
                continue
            for t in self.tools_of(b):
                src = t.Base if self.is_array(t) else t
                if src is None or src.TypeId != "Part::Extrusion" or src.Base is None:
                    continue
                if not getattr(src, "SSTiedTo", ""):
                    continue
                if src.Base.Shape.isNull() or t.Shape.isNull() or src.Dir.Length < 1e-12:
                    continue
                sd = unit(src.Dir)
                axis = self._axis_of(sd)
                if axis is None or fn.dot(sd) > -NORMAL_TOL:
                    continue
                sign = 1.0 if sd[axis] > 0 else -1.0
                if abs(self._cut_far_level(src, axis, sign) - p[axis]) <= TOL and t.Shape.isInside(p, TOL, True):
                    val = src.LengthFwd.Value
                    src.setExpression("LengthFwd", None)
                    src.LengthFwd = val
                    src.SSTiedTo = ""

    def op_rect(self, op):
        rid = op["id"]
        if self.rect_obj(rid) is not None:
            raise OpError(f"rect id '{rid}' already exists", about=[rid])
        origin, x, y, n, on = self.plane_from(op["plane"])
        if op.get("x") is not None:
            rx = vec(op["x"])
            rx = rx - n * rx.dot(n)
            if rx.Length < TOL:
                raise OpError("rect x axis is degenerate")
            x = unit(rx)
            y = unit(n.cross(x))
        u, v = op.get("corner", [0, 0])
        w, h = op["size"]
        if w <= 0 or h <= 0:
            raise OpError("rect size must be positive")
        pl = self.plane_feature(origin + x * u + y * v, x * w, y * h, rid)
        add_props(pl, RectId=rid, OnBody=on)
        self.group("Rectangles", "Rectangles").addObject(pl)
        return []

    def op_push_pull(self, op):
        d = float(op["distance"])
        if abs(d) < TOL:
            raise OpError("distance is zero")
        tgt = op["target"]
        oid = op["id"]
        fit = op.get("edge_fit")
        to_face = op.get("to_face")
        if to_face is not None and (d >= 0 or op.get("through") or fit or op.get("resize_stock") or op.get("body")):
            raise OpError("to_face is only for a cut into a board")
        if fit and "face" in tgt and "region" not in tgt:
            import plane_fit
            board, _, normal = self.resolve_face(tgt["face"])
            source_id = tgt["face"]["body"]
            src_board = self.body(source_id)
            frame = plane_fit.source_frame(src_board)
            if not frame:
                raise OpError("Source has no extrudable stock")
            axis = next((i for i,v in enumerate(frame[2]) if abs(v.dot(normal)) > 0.9999), None)
            if axis is None or (plane_fit.stock(src_board) is None and axis != 2):
                raise OpError("Source face no longer matches the chosen dimension")
            return plane_fit.apply(self, dict(body=source_id, target_body=fit["target_body"],
                                   axis=axis, face=fit["face"], fit_mode=fit.get("fit_mode", 0), reverse=frame[2][axis].dot(normal)<0))
        if "face" in tgt and not fit and "region" not in tgt:
            import plane_fit
            board = self.body(tgt["face"]["body"])
            if plane_fit.fitted_end(board) is not None:      # pushing a tied end again detaches it (I26b, I40)
                if plane_fit.push_fitted_end(self, board, unit(vec(tgt["face"]["normal"])), vec(tgt["face"]["point"]), d):
                    if to_face is not None:
                        raise OpError("to_face is only for a cut into a board")
                    return plane_fit.family_bodies(self, board)
            if not op.get("body"):
                self._detach_floor_cuts(board, vec(tgt["face"]["normal"]), vec(tgt["face"]["point"]))
        if op.get("resize_stock") and "face" in tgt and "region" not in tgt:
            import plane_fit
            board, _, normal = self.resolve_face(tgt["face"])
            if plane_fit.resize_face(self,board,normal,d):
                return plane_fit.family_bodies(self, board)
        if "rect" in tgt:
            pl = self.rect_obj(tgt["rect"])
            if pl is None:
                raise OpError(f"unknown rect '{tgt['rect']}'", about=[tgt["rect"]])
            polygonal = getattr(pl, "SSRole", "") == "line-profile"
            ngon = getattr(pl, "SSRole", "") == "polygon-profile"
            circular = pl.TypeId == "Sketcher::SketchObject" and not ngon
            if polygonal:
                world_face = pl.Shape.Faces[0]
                n = world_face.normalAt(0, 0)
            elif ngon:
                p0, ex, ey, n, radius, sides = self.polygon_world(pl)
                corners = [p0 + (ex * math.cos(2 * math.pi * i / sides) + ey * math.sin(2 * math.pi * i / sides)) * radius
                           for i in range(sides)]
                world_face = Part.Face(Part.makePolygon(corners + corners[:1]))
            elif circular:
                p0, ex, ey, n, radius = self.circle_world(pl)
                world_face = Part.Face(Part.Wire([Part.makeCircle(radius, p0, n)]))
            else:
                p0, ex, ey, n = self.rect_world(pl)
                world_face = Part.Face(Part.makePolygon([p0, p0 + ex, p0 + ex + ey, p0 + ey, p0]))
            on = pl.OnBody
            loose = any(g.TypeId == "App::DocumentObjectGroup" for g in pl.InList)
        elif "face" in tgt:
            _, world_face, n = self.resolve_face(tgt["face"])
            on = tgt["face"]["body"]
            pl = None
        elif "region" in tgt:
            world_face, n = self.region_face(tgt["region"])
            on, pl = "", None
        else:
            raise OpError("push needs a profile, face or closed region")

        if "region" in tgt:
            known = {getattr(o, "SSLineId", "") for o in self.doc.Objects}
            if any(lid not in known for lid in tgt["region"].get("lines", [])):
                raise OpError("region refers to a missing drawing")
            source = world_face
            if "face" in tgt or "rect" in tgt:     # a region alone is already world_face, built above
                world_face, region_n = self.region_face(tgt["region"])
                if n.dot(region_n) < 0.999999:
                    raise OpError("region normal differs from target plane")
                world_face = self.native_region(source, world_face, tgt["region"])
                if abs(source.common(world_face).Area - world_face.Area) > max(TOL, world_face.Area * 1e-6):
                    raise OpError("region leaves its target face")
            else:
                ids = set(tgt["region"].get("lines", []))
                drawings = [edge for obj in self.doc.Objects if getattr(obj, "SSLineId", "") in ids
                            for edge in Part.getShape(obj).Edges]
                if any(not isinstance(e.Curve, Part.Line) for e in drawings):
                    sheet = self.ground_region_sheet(world_face, n, drawings)
                    world_face = self.native_region(sheet, world_face, tgt["region"], is_ground=True)
            pl = None  # materialize this region, never extrude the whole source profile

        if not on or op.get("body"):
            if to_face is not None:
                raise OpError("to_face is only for a cut into a board")
            # a free rectangle, or the user asked for a separate board: a new board, world frame
            bid = op.get("body") or f"{oid}_body"
            c = self.new_board(bid)
            if pl is not None:
                if polygonal:
                    base = self.face_feature(world_face, f"{tgt['rect']} outline")
                elif ngon:
                    base = self.polygon_feature(p0, ex, ey, radius, sides, f"{tgt['rect']} again",
                                                existing=pl if loose else None)
                elif circular:
                    base = self.circle_feature(p0, ex, ey, radius, f"{tgt['rect']} again", existing=pl if loose else None)
                else:
                    base = pl if loose else self.plane_feature(p0, ex, ey, f"{tgt['rect']} again")
                    if loose:
                        self.plane_feature(p0, ex, ey, "", existing=pl)
            else:
                base = self.face_feature(world_face, f"{oid} face")
            self.put_in(c, base)
            ext = self.extrusion(base, n * d, d, f"{oid} push")
            add_props(ext, SSOp=oid)
            self.set_tip(c, ext)
            if op.get("assembly"):                   # drawn inside an entered assembly: it joins it (T20)
                asm = self.assemblies().get(op["assembly"])
                if asm is None:
                    raise OpError(f"unknown assembly '{op['assembly']}'", about=[op["assembly"]])
                asm.addObject(c)
            self.doc.recompute()
            if not Part.getShape(c).Solids:
                raise OpError("the push didn't make a solid")
            if fit:
                import plane_fit
                return plane_fit.apply(self, dict(body=bid,target_body=fit["target_body"],axis=2,face=fit["face"],fit_mode=fit.get("fit_mode", 0)))
            return [bid]

        # draw-on-face edit: the extrusion lands in the target board's own frame
        target = self.body(on)
        c, fr = self.edit_frame(target)
        if c.Tip is None:
            raise OpError(f"'{on}' has no solid yet", about=[on])
        if pl is not None:
            if polygonal:
                base = self.face_feature(fr.shape(world_face), f"{tgt['rect']} outline")
            else:
                lp0, lex, ley = fr.pt(p0), fr.dir(ex), fr.dir(ey)
                if ngon:
                    base = self.polygon_feature(lp0, lex, ley, radius, sides, f"{tgt['rect']} again",
                                                existing=pl if loose else None)
                elif circular:
                    base = self.circle_feature(lp0, lex, ley, radius, f"{tgt['rect']} again", existing=pl if loose else None)
                elif loose:
                    base = self.plane_feature(lp0, lex, ley, "", existing=pl)
                else:
                    base = self.plane_feature(lp0, lex, ley, f"{tgt['rect']} again")
        else:
            base = self.face_feature(fr.shape(world_face), f"{oid} face")
        before = c.Tip.Shape
        run_base = c.Tip.Base if (d < 0 and self.is_cut_run(c.Tip)) else c.Tip
        ext = self.extrusion(base, fr.dir(n * d), d, f"{oid} push")
        through = bool(op.get("through")) and d < 0
        floor_ext = None
        if to_face is not None:
            floor_ext = self._find_floor_cutter(
                c, fr.dir(n * d), fr.dir(vec(to_face["normal"])), fr.pt(vec(to_face["point"])))
        tied_to = (getattr(floor_ext, "SSOp", "") or floor_ext.Name) if floor_ext is not None else ""
        add_props(ext, SSOp=oid, SSTiedTo=tied_to, **({"SSThrough": True} if through else {}))
        self.put_in(c, base, ext)
        if through:
            self.through_all(ext, base, run_base, fr.dir(n * d), fr.pt(world_face.CenterOfMass))
        elif floor_ext is not None:
            self.tie_to_floor(ext, base, floor_ext, fr.dir(n * d))
        b = self.boolean(c, ext, d, oid)
        self.doc.recompute()
        self.check_result(before, b.Shape, d)
        return [on]
