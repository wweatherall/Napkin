"""Rectangles and Push/Pull: new boards, cuts and joins, through-cuts (I24)."""
import Part
from common import OpError, TOL, add_props, unit, vec


class PushActions:
    """Part of Model (model.py): works through self on the FreeCAD document."""

    # ---------- operations ----------
    @staticmethod
    def through_all(ext, plane, run_base, direction, level_pt):
        """A cut pushed to the opposite face (I24): its length follows the board instead of a number. It runs to
        the far side of the board (as it was before this run of cuts) plus 1 mm, and back past the face it was
        drawn on by as much as the board has grown on that side since. Make the board thicker or thinner in
        FreeCAD and the hole stays through. Only for axis-aligned pushes (all of them, today)."""
        u = unit(direction)
        axis = next((i for i in range(3) if abs(abs(u[i]) - 1.0) < 1e-6), None)
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

    def op_rect(self, op):
        rid = op["id"]
        if self.rect_obj(rid) is not None:
            raise OpError(f"rect id '{rid}' already exists")
        origin, x, y, n, on = self.plane_from(op["plane"])
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
        if fit and "face" in tgt and "region" not in tgt:
            import plane_fit
            board, _, normal = self.resolve_face(tgt["face"])
            source_id = tgt["face"]["body"]
            frame = plane_fit.stock(self.body(source_id))
            if not frame:
                raise OpError("Source is no longer rectangular stock")
            axis = next((i for i,v in enumerate(frame[2]) if abs(v.dot(normal)) > 0.9999), None)
            if axis is None:
                raise OpError("Source face no longer matches the chosen dimension")
            return plane_fit.apply(self, dict(body=source_id, target_body=fit["target_body"],
                                   axis=axis, face=fit["face"], fit_mode=fit.get("fit_mode", 0), reverse=frame[2][axis].dot(normal)<0))
        if "face" in tgt and not fit and "region" not in tgt:
            import plane_fit
            board = self.body(tgt["face"]["body"])
            if plane_fit.fitted_end(board) is not None:      # pushing a tied end again detaches it (I26b, I40)
                if plane_fit.push_fitted_end(self, board, unit(vec(tgt["face"]["normal"])), vec(tgt["face"]["point"]), d):
                    return [board.BodyId]
        if op.get("resize_stock") and "face" in tgt and "region" not in tgt:
            import plane_fit
            board, _, normal = self.resolve_face(tgt["face"])
            if plane_fit.resize_face(self,board,normal,d):
                return [board.BodyId]
        if "rect" in tgt:
            pl = self.rect_obj(tgt["rect"])
            if pl is None:
                raise OpError(f"unknown rect '{tgt['rect']}'")
            polygonal = getattr(pl, "SSRole", "") == "line-profile"
            circular = pl.TypeId == "Sketcher::SketchObject"
            if polygonal:
                world_face = pl.Shape.Faces[0]
                n = world_face.normalAt(0, 0)
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
            source = world_face
            world_face, region_n = self.region_face(tgt["region"])
            if n.dot(region_n) < 0.999999:
                raise OpError("region normal differs from target plane")
            if "face" in tgt or "rect" in tgt:
                world_face = self.native_region(source, world_face, tgt["region"])
                if abs(source.common(world_face).Area - world_face.Area) > max(TOL, world_face.Area * 1e-6):
                    raise OpError("region leaves its target face")
            known = {getattr(o, "SSLineId", "") for o in self.doc.Objects}
            if any(lid not in known for lid in tgt["region"].get("lines", [])):
                raise OpError("region refers to a missing drawing")
            pl = None  # materialize this region, never extrude the whole source profile

        if not on or op.get("body"):
            # a free rectangle, or the user asked for a separate board: a new board, world frame
            bid = op.get("body") or f"{oid}_body"
            c = self.new_board(bid)
            if pl is not None:
                if polygonal:
                    base = self.face_feature(world_face, f"{tgt['rect']} outline")
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
                    raise OpError(f"unknown assembly '{op['assembly']}'")
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
            raise OpError(f"'{on}' has no solid yet")
        if pl is not None:
            if polygonal:
                base = self.face_feature(fr.shape(world_face), f"{tgt['rect']} outline")
            else:
                lp0, lex, ley = fr.pt(p0), fr.dir(ex), fr.dir(ey)
                if circular:
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
        add_props(ext, SSOp=oid, **({"SSThrough": True} if through else {}))
        self.put_in(c, base, ext)
        if through:
            self.through_all(ext, base, run_base, fr.dir(n * d), fr.pt(world_face.CenterOfMass))
        b = self.boolean(c, ext, d, oid)
        self.doc.recompute()
        self.check_result(before, b.Shape, d)
        return [on]
