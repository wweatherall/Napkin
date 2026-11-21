"""Model: Shop Sketch operations on a FreeCAD document. This file reads the document and has the building
blocks (boards, extrusions, booleans); each kind of action is a mixin in its own file."""
from common import *
from push import PushActions
from move import MoveActions
from mirror import MirrorActions
from assembly import AssemblyActions
from paint import PaintActions
from visibility import VisibilityActions


class Model(PushActions, MoveActions, MirrorActions, AssemblyActions, PaintActions, VisibilityActions):
    """Shop Sketch operations on a FreeCAD document. Holds no state of its own."""

    def __init__(self, doc):
        self.doc = doc

    # ---------- reading the document ----------
    def bodies(self):
        out = {}
        for o in self.doc.Objects:
            if getattr(o, "SSRole", None) == "body" and o.BodyId:
                out[o.BodyId] = o
        return out

    def body(self, bid):
        obj = self.bodies().get(bid)
        if obj is None:
            raise OpError(f"unknown body '{bid}'")
        return obj

    def assemblies(self):
        return {o.AssemblyId: o for o in self.doc.Objects if getattr(o, "SSRole", None) == "assembly"}

    def assembly_of(self, obj):
        """The assembly a board is in (a FreeCAD group of boards, T20), or None."""
        for g in obj.InList:
            if getattr(g, "SSRole", None) == "assembly":
                return g
        return None

    def rect_obj(self, rid):
        for o in self.doc.Objects:
            if getattr(o, "RectId", None) == rid:
                return o
        return None

    @staticmethod
    def is_instance(obj):
        return obj.TypeId == "App::Link"

    @staticmethod
    def is_mirror(obj):
        return obj.TypeId == "Part::Mirroring"

    @staticmethod
    def mirror_source(m):
        """The body a mirror reflects, stepping over the wrapper a component instance gets (mirror_input)."""
        s = m.Source
        if getattr(s, "SSRole", None) == "mirror-input":
            s = s.Links[0]
        return s

    @staticmethod
    def world_shape(obj):
        return Part.getShape(obj)

    def definition(self, obj):
        """The board container whose features an edit really changes."""
        while self.is_mirror(obj):
            obj = self.mirror_source(obj)
        return obj.LinkedObject if self.is_instance(obj) else obj

    def edit_frame(self, obj):
        """Container that an edit on `obj` lands in, and the world -> container frame.
        Editing a mirrored copy edits its source with the tool mirrored back (A11 / I-series);
        editing a component instance edits the definition, through the instance's placement."""
        fr = Frame()
        while self.is_mirror(obj):
            fr.mirror(obj.Base, obj.Normal)
            obj = self.mirror_source(obj)
        if self.is_instance(obj):
            fr.into(obj.Placement)
            obj = obj.LinkedObject
        else:
            fr.into(obj.Placement)
        if obj.TypeId != "App::Part" or not hasattr(obj, "Tip"):
            raise OpError(f"'{obj.Label}' is not a Shop Sketch board")
        return obj, fr

    def group(self, name, label):
        g = self.doc.getObject(name)
        if g is None:
            g = self.doc.addObject("App::DocumentObjectGroup", name)
            g.Label = label
        return g

    def resolve_face(self, ref):
        """Find a planar face by geometry: matching outward normal and containing the point."""
        obj = self.body(ref["body"])
        n_want = unit(vec(ref["normal"]))
        p = vec(ref["point"])
        hits = []
        for f in self.world_shape(obj).Faces:
            srf = f.Surface
            if srf.__class__.__name__ != "Plane":
                continue
            if abs((p - srf.Position).dot(srf.Axis)) > TOL:     # cheap: the point isn't on this face's plane
                continue
            u0, u1, v0, v1 = f.ParameterRange
            n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
            if n.dot(n_want) < NORMAL_TOL:
                continue
            if f.distToShape(Part.Vertex(p))[0] < TOL:
                hits.append(f)
        if not hits:
            raise OpError(f"no face of '{ref['body']}' faces {list(ref['normal'])} through {list(ref['point'])}")
        if len(hits) > 1:
            raise OpError(f"{len(hits)} faces of '{ref['body']}' match; reference is ambiguous")
        return obj, hits[0], n_want

    def plane_from(self, spec):
        if "on" in spec:
            self.resolve_face(spec["on"])
            n = unit(vec(spec["on"]["normal"]))
            origin = vec(spec["on"]["point"])
            on = spec["on"]["body"]
        else:
            n = unit(vec(spec["normal"]))
            origin = vec(spec["origin"])
            on = ""
        if "xdir" in spec:
            x = unit(vec(spec["xdir"]))
        elif abs(n.z) > 0.9:
            x = V(1, 0, 0)            # horizontal planes: u along world X
        else:
            x = unit(V(0, 0, 1).cross(n))   # vertical planes: u horizontal, v up
        x = unit(x - n * x.dot(n))
        y = n.cross(x)
        return origin, x, y, n, on

    # ---------- building blocks ----------
    def new_board(self, bid, placement=None):
        if bid in self.bodies():
            raise OpError(f"body id '{bid}' already exists")
        c = self.doc.addObject("App::Part", "Board")
        c.Label = bid
        add_props(c, BodyId=bid, SSRole="body", SSMaterial="", ComponentName="", Tip=None, SSGrain=App.Vector(0, 0, 0),
                  SSHidden=False)
        if placement is not None:
            c.Placement = placement
        return c

    def set_tip(self, container, feat):
        old = container.Tip
        container.addObject(feat)
        if old is not None:
            old.Visibility = False
            if hasattr(old, "ShapeMaterial") and hasattr(feat, "ShapeMaterial") and getattr(container, "SSMaterial", ""):
                feat.ShapeMaterial = old.ShapeMaterial     # FreeCAD sees the material on the board's current solid
        feat.Visibility = True
        container.Tip = feat

    def put_in(self, container, *objs):
        for o in objs:
            for g in o.InList:
                if g.TypeId == "App::DocumentObjectGroup":
                    g.removeObject(o)
            container.addObject(o)
            o.Visibility = False

    def plane_feature(self, p0, ex, ey, label, existing=None):
        """A Part::Plane covering p0 + s*ex + t*ey (0<=s,t<=1)."""
        z = unit(ex.cross(ey))
        x = unit(ex)
        y = z.cross(x)
        pl = existing or self.doc.addObject("Part::Plane", "Rect")
        pl.Length = ex.Length
        pl.Width = ey.Length
        pl.Placement = App.Placement(p0, rotation_from(x, y, z))
        if existing is None:
            pl.Label = label
        return pl

    def face_feature(self, face, label):
        f = self.doc.addObject("Part::Feature", "Face")
        f.Shape = face
        f.Label = label
        return f

    def extrusion(self, base, direction, length, label):
        ex = self.doc.addObject("Part::Extrusion", "Extrude")
        ex.Base = base
        ex.DirMode = "Custom"
        ex.Dir = unit(direction)
        ex.LengthFwd = abs(length)
        ex.Solid = True
        ex.Label = label
        return ex

    def rect_world(self, pl):
        gp = pl.Placement
        grp = pl.getParentGeoFeatureGroup()
        while grp is not None:
            gp = grp.Placement.multiply(gp)
            grp = grp.getParentGeoFeatureGroup()
        r = gp.Rotation
        p0 = gp.Base
        ex = r.multVec(V(1, 0, 0)) * pl.Length.Value
        ey = r.multVec(V(0, 1, 0)) * pl.Width.Value
        n = unit(r.multVec(V(0, 0, 1)))
        return p0, ex, ey, n

    @staticmethod
    def check_result(base, result, distance):
        """Shop Sketch's rejections (I08), judged on what FreeCAD just computed (`result`) against the board
        before this op (`base`); no second boolean of our own. A rejected op's transaction is aborted."""
        if result.isNull() or not result.Solids:
            raise OpError("operation removed the whole body" if distance < 0 else "FreeCAD couldn't compute the merge")
        change = result.Volume - base.Volume
        if distance < 0 and abs(change) < 1e-3:
            raise OpError("the cut doesn't reach the board, so nothing was removed")
        if distance > 0 and change < 1e-3:
            raise OpError("nothing was added: the new piece is entirely inside the board")
        if distance > 0 and len(result.Solids) > len(base.Solids):
            raise OpError("the new piece doesn't touch the board it was drawn on")
        return result.Volume

    @staticmethod
    def is_array(obj):
        return getattr(getattr(obj, "Proxy", None), "__class__", type(None)).__name__ == "Array"

    @staticmethod
    def is_cut_run(obj):
        return obj is not None and obj.TypeId == "Part::Cut" and getattr(obj.Tool, "SSRole", None) == "cutters"

    @staticmethod
    def is_merge_run(obj):
        return obj is not None and obj.TypeId == "Part::MultiFuse" and getattr(obj, "SSRole", None) == "merge-run"

    def tools_of(self, b):
        """The pieces a boolean cuts away (or adds): each is an extrusion, or a Draft array made from one."""
        if self.is_cut_run(b):
            return list(b.Tool.Links)
        if self.is_merge_run(b):
            return list(b.Shapes[1:])
        return [b.Tool] if getattr(b, "Tool", None) is not None else []      # one boolean per op (older files)

    def replace_tool(self, b, old, new):
        if self.is_cut_run(b):
            b.Tool.Links = [new if t == old else t for t in b.Tool.Links]
        elif self.is_merge_run(b):
            b.Shapes = [new if t == old else t for t in b.Shapes]
        else:
            b.Tool = new

    def boolean(self, container, tool_feat, distance, oid):
        """Back-to-back cuts on a board share one Part::Cut whose tool is a compound of all the cutters, and
        back-to-back merges one Part::MultiFuse (Q20). FreeCAD's booleans slow down along a chain (Q18): one
        boolean per run keeps every edit about as fast as the first. Each op is still one undo step."""
        tip = container.Tip
        if distance < 0 and self.is_cut_run(tip):
            tip.Tool.Links = tip.Tool.Links + [tool_feat]
            return tip
        if distance > 0 and self.is_merge_run(tip):
            tip.Shapes = tip.Shapes + [tool_feat]
            return tip
        if distance < 0:
            cutters = self.doc.addObject("Part::Compound", "Cutters")
            cutters.Label = f"{oid} cutters"
            add_props(cutters, SSRole="cutters")
            cutters.Links = [tool_feat]
            b = self.doc.addObject("Part::Cut", "Cut")
            b.Base = tip
            b.Tool = cutters
            b.Label = f"{oid} cuts"
            self.put_in(container, cutters)
        else:
            b = self.doc.addObject("Part::MultiFuse", "Fuse")
            b.Shapes = [tip, tool_feat]
            b.Label = f"{oid} merges"
            add_props(b, SSRole="merge-run")
        b.Refine = True
        add_props(b, SSOp=oid)
        self.set_tip(container, b)
        return b

    HANDLERS = ("rect", "push_pull", "mirror", "make_component", "move", "set_material", "detach", "make_unique",
                "make_assembly", "turn_grain", "property_edit", "hide")

    def op_property_edit(self, op):
        """A native property changed in the Properties panel (T46): see object_properties.apply."""
        from object_properties import apply
        return apply(self, op)

    def apply(self, op):
        if op["type"] not in self.HANDLERS:
            raise OpError(f"unknown op type '{op['type']}'")
        changed = getattr(self, "op_" + op["type"])(op)
        self.doc.recompute()
        bad = [o.Label for o in self.doc.Objects if "Invalid" in o.State or "Error" in o.State]
        if bad:
            raise OpError(f"FreeCAD couldn't recompute: {', '.join(bad[:3])}")
        return changed
