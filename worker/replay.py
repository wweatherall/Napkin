"""Shop Sketch worker: keeps a live FreeCAD document and edits it with native features.

The FreeCAD file is the model (A21). Every Shop Sketch action becomes ordinary FreeCAD
features inside it - Part::Plane, Part::Extrusion, Part::Cut / Part::MultiFuse, App::Part
placements, App::Link, Part::Mirroring - committed as one FreeCAD undo transaction.
All Shop Sketch state lives on those objects (BodyId / SSRole / RectId ... properties),
so FreeCAD's undo, a save, a reopen or an edit made in FreeCAD all stay consistent.

Run with:
  SERVE_PORT=7878 freecadcmd replay.py            long-running worker (newline JSON over TCP)
  OPLOG=ops.json OUTDIR=out freecadcmd replay.py  one-off: build out/model.FCStd from an op log

Writes beside the model:
  model.FCStd                the document (autosaved atomically after every change)
  model.shopsketch.json      journal: the op list, statuses, revision, file hash
and into the output folder:
  bodies.json  status.json  meshes/<board>-<key>.bin (one per board, rewritten only when it changes)
  model.glb at each autosave (views.json when a drawing is asked for)
"""
import hashlib
import json
import os
import struct
import time

import sys

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import materials as wood                      # the wood library (T15): cards for FreeCAD, materials.json for the viewport

_MATERIALS = {"installed": False, "outdirs": set()}


def material_card(key):
    """FreeCAD's material for a library key (installing the cards the first time), or None."""
    import Materials
    if key not in wood.SPECIES:
        return None
    mm = Materials.MaterialManager()
    if not _MATERIALS["installed"]:
        _MATERIALS["installed"] = True
        try:
            if wood.install(os.path.join(App.getUserAppDataDir(), "Material"),
                            os.path.join(HERE, "..", "materials", "textures")):
                mm.refresh()
        except OSError as e:
            print(f"WORKER could not install the wood cards: {e}", flush=True)
    try:
        return mm.getMaterial(wood.material_uuid(key))
    except Exception:
        mm.refresh()
        try:
            return mm.getMaterial(wood.material_uuid(key))
        except Exception:
            return None

V = App.Vector
TOL = 1e-3          # mm, for face matching
NORMAL_TOL = 0.999  # cosine
JOURNAL_FORMAT = "shopsketch-journal/0.1"

# FreeCAD keeps 20 undo steps per document. Only its GUI applies the MaxUndoSize preference, and there is no
# Python call to change it, so in freecadcmd it stays 20 (checked on 1.1.3 and 1.1.4). Undoing further back
# rebuilds the document from the journal (Session.sync: "rebuilt"); the viewport shows the remembered state
# meanwhile, so you can keep undoing (T10).


class OpError(Exception):
    pass


def vec(a):
    return V(float(a[0]), float(a[1]), float(a[2]))


def unit(v):
    if v.Length < 1e-12:
        raise OpError("zero-length vector")
    return V(v).normalize()


def rotation_from(x, y, z):
    return App.Rotation(x, y, z, "ZXY")


def add_props(obj, **props):
    """All Shop Sketch properties are added when an object is created (adding them later
    inside an undo transaction is not reliably undone)."""
    kinds = {str: "App::PropertyString", bool: "App::PropertyBool", int: "App::PropertyInteger",
             float: "App::PropertyFloat", App.Vector: "App::PropertyVector"}
    for name, value in props.items():
        if name == "Tip":
            obj.addProperty("App::PropertyLinkChild", "Tip", "ShopSketch", "the feature that is this board's current solid")
            obj.Tip = value
            continue
        obj.addProperty(kinds[type(value)], name, "ShopSketch", "")
        setattr(obj, name, value)
    return obj


class Frame:
    """World -> a board's own (container) frame, possibly through mirrors and component links.
    Kept as steps so it can map points, directions and whole shapes (mirrors flip handedness)."""

    def __init__(self):
        self.steps = []

    def mirror(self, base, normal):
        self.steps.append(("mirror", V(base), unit(V(normal))))

    def into(self, placement):
        self.steps.append(("into", placement.inverse()))

    def pt(self, p):
        p = V(p)
        for s in self.steps:
            if s[0] == "mirror":
                p = p - s[2] * (2 * (p - s[1]).dot(s[2]))
            else:
                p = s[1].multVec(p)
        return p

    def dir(self, d):
        d = V(d)
        for s in self.steps:
            if s[0] == "mirror":
                d = d - s[2] * (2 * d.dot(s[2]))
            else:
                d = s[1].Rotation.multVec(d)
        return d

    def shape(self, sh):
        sh = sh.copy()
        for s in self.steps:
            if s[0] == "mirror":
                sh = sh.mirror(s[1], s[2])
            else:
                sh.transformShape(s[1].toMatrix())
        return sh


class Model:
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
        add_props(c, BodyId=bid, SSRole="body", SSMaterial="", ComponentName="", Tip=None, SSGrain=App.Vector(0, 0, 0))
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
        if "rect" in tgt:
            pl = self.rect_obj(tgt["rect"])
            if pl is None:
                raise OpError(f"unknown rect '{tgt['rect']}'")
            p0, ex, ey, n = self.rect_world(pl)
            on = pl.OnBody
            loose = any(g.TypeId == "App::DocumentObjectGroup" for g in pl.InList)
            world_face = Part.Face(Part.makePolygon([p0, p0 + ex, p0 + ex + ey, p0 + ey, p0]))
        else:
            _, world_face, n = self.resolve_face(tgt["face"])
            on = tgt["face"]["body"]
            pl = None

        if not on or op.get("body"):
            # a free rectangle, or the user asked for a separate board: a new board, world frame
            bid = op.get("body") or f"{oid}_body"
            c = self.new_board(bid)
            if pl is not None:
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
            return [bid]

        # draw-on-face edit: the extrusion lands in the target board's own frame
        target = self.body(on)
        c, fr = self.edit_frame(target)
        if c.Tip is None:
            raise OpError(f"'{on}' has no solid yet")
        if pl is not None:
            lp0, lex, ley = fr.pt(p0), fr.dir(ex), fr.dir(ey)
            if loose:
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

    def op_make_component(self, op):
        bid = op["body"]
        obj = self.body(bid)
        if self.is_instance(obj):
            raise OpError(f"'{bid}' is already a component instance")
        if self.is_mirror(obj) or obj.TypeId != "App::Part":
            raise OpError(f"'{bid}' can't be made a component")
        dfn = obj
        asm = self.assembly_of(obj)
        dfn.SSRole = "definition"
        dfn.ComponentName = op["name"]
        dfn.Label = op["name"]
        self.group("ComponentDefinitions", "Component definitions").addObject(dfn)
        dfn.Visibility = False
        link = self.doc.addObject("App::Link", "Instance")
        link.LinkedObject = dfn
        link.Placement = dfn.Placement
        link.Label = bid
        add_props(link, BodyId=bid, SSRole="body")
        if asm is not None:
            asm.addObject(link)                      # the board stays in its assembly as the link
        return [bid]

    def as_component(self, obj):
        """A plain board about to be copied becomes a component (A22c): its features move into a hidden definition
        and the board itself becomes a link to it, like its copies. One undo step with the copy."""
        if obj.TypeId != "App::Part" or getattr(obj, "SSRole", "") != "body":
            return obj
        bid = obj.BodyId
        self.op_make_component({"body": bid, "name": bid})
        return self.body(bid)

    def new_link(self, dfn, nid, placement, array="", index=0):
        link = self.doc.addObject("App::Link", "Instance")
        link.LinkedObject = dfn
        link.Placement = placement
        link.Label = nid
        add_props(link, BodyId=nid, SSRole="body", SSArray=array, SSArrayIndex=index)
        return link

    def array_follow(self, obj, arr, index):
        """A member's position comes from its array: Origin + Step * index (I25)."""
        for c in "xyz":
            obj.setExpression(f".Placement.Base.{c}", f"{arr.Name}.Origin.{c} + {arr.Name}.Step.{c} * {index}")

    def new_array(self, source, vec, count, divide, oid):
        """The relationship behind Nx and /N copies: a small object FreeCAD can edit (Count, Step, Span). A /N array
        keeps its span and re-spreads; an Nx array keeps its spacing."""
        arr = self.doc.addObject("App::Placement", "Array")
        arr.Label = f"{oid} array"
        add_props(arr, SSRole="array", SSOp=oid, SSSource=source.BodyId, Distributed=bool(divide), Count=int(count),
                  Origin=V(source.Placement.Base), Step=V(vec * (1.0 / count) if divide else vec),
                  Span=V(vec if divide else vec * count))
        if divide:
            for c in "xyz":
                arr.setExpression(f"Step.{c}", f"Span.{c} / Count")
        return arr

    def copy_body(self, obj, nid, step, arr=None, index=0):
        if self.is_instance(obj) or (obj.TypeId == "App::Part" and getattr(obj, "SSRole", "") == "body"):
            obj = self.as_component(obj)
            link = self.new_link(obj.LinkedObject, nid, App.Placement(obj.Placement.Base + step, obj.Placement.Rotation),
                                 arr.Name if arr else "", index)
            asm = self.assembly_of(obj)
            if asm is not None:
                asm.addObject(link)                  # copies made inside an assembly belong to it
            if arr is not None:
                self.array_follow(link, arr, index)
            return
        if self.is_mirror(obj):            # a mirrored copy copied: an independent board of its shape
            c = self.new_board(nid)
            s = self.world_shape(obj).copy()
            s.translate(step)
        else:
            c = self.new_board(nid, App.Placement(obj.Placement.Base + step, obj.Placement.Rotation))
            s = obj.Tip.Shape.copy()
        snap = self.doc.addObject("Part::Feature", "Copy")
        snap.Shape = s
        snap.Label = f"{nid} (copy)"
        self.set_tip(c, snap)
        c.SSMaterial = getattr(self.definition(obj), "SSMaterial", "") or ""

    def cutter_of(self, container, oid):
        """The Cut that holds the hole made by push/pull `oid`, and the tool that makes it there."""
        for o in container.Group:
            if o.TypeId != "Part::Cut":
                continue
            for t in self.tools_of(o):
                src = t.Base if self.is_array(t) else t
                if getattr(src, "SSOp", None) == oid:
                    return o, t
        raise OpError(f"no cut from '{oid}' on this board")

    @staticmethod
    def shift(obj, v):
        obj.Placement = App.Placement(obj.Placement.Base + v, obj.Placement.Rotation)

    def op_move_cut(self, op):
        """Move a hole (or a bump) on its board, or copy it: copies become a Draft OrthoArray of the
        cutter, so FreeCAD makes all the holes in one cut and you can change the count there."""
        ref = op["cut"]
        target = self.body(ref["body"])
        c, fr = self.edit_frame(target)
        b, tool = self.cutter_of(c, ref["op"])
        lv = fr.dir(vec(op["vector"]))
        if lv.Length < TOL:
            raise OpError("distance is zero")
        before = b.Shape.Volume
        is_array = self.is_array(tool)
        if not op.get("copy", False):
            cutter = tool.Base if is_array else tool       # the extrusion; move what it's made from
            self.shift(cutter.Base, lv)
            self.doc.recompute()
            if b.Base.Shape.common(tool.Shape).Volume < 1e-3:
                raise OpError("moved there, it no longer touches the board")
            return [ref["body"]]
        if is_array:
            raise OpError("this hole is already an array: retype the count right after making it")
        count = int(op.get("count", 1))
        step = lv * (1.0 / count) if op.get("divide", False) else lv
        import Draft
        App.setActiveDocument(self.doc.Name)    # Draft builds in the active document, which may be another model's
        arr = Draft.make_ortho_array(tool, v_x=step, v_y=V(0, 1, 0), v_z=V(0, 0, 1),
                                     n_x=count + 1, n_y=1, n_z=1, use_link=False)
        arr.Label = f"{op['id']} array of {ref['op']}"
        add_props(arr, SSOp=op["id"])
        c.addObject(arr)
        tool.Visibility = False
        arr.Visibility = False
        self.replace_tool(b, tool, arr)
        self.doc.recompute()
        if abs(b.Shape.Volume - before) < 1e-3:
            raise OpError("the copies don't reach the board")
        return [ref["body"]]

    def op_move(self, op):
        if op.get("cut"):
            return self.op_move_cut(op)
        vecv = vec(op["vector"])
        copy = op.get("copy", False)
        count = int(op.get("count", 1))
        divide = op.get("divide", False)
        changed = []
        new_ids = list(op.get("new_ids", []))
        for t in op["targets"]:
            if t in self.assemblies() and not copy:
                changed += self.move_assembly(self.assemblies()[t], vecv)
                continue
            obj = self.body(t)
            if op.get("detach") and getattr(obj, "SSArray", ""):
                self.op_detach({"targets": [t]})       # inside an entered array, a copy moves alone (I32)
            if not copy and self.is_mirror(obj):
                # a mirrored copy (or flipped board): its original moves by the vector reflected across the
                # plane, so the pair stays mirrored (A11b). The original may itself be a copy in a row.
                nrm = unit(obj.Normal)
                src_vec = vecv - nrm * (2 * vecv.dot(nrm))
                src = self.mirror_source(obj)
                while self.is_mirror(src):
                    nrm2 = unit(src.Normal)
                    src_vec = src_vec - nrm2 * (2 * src_vec.dot(nrm2))
                    src = self.mirror_source(src)
                if getattr(src, "SSArray", ""):
                    self.op_detach({"targets": [src.BodyId]})
                src.Placement = App.Placement(src.Placement.Base + src_vec, src.Placement.Rotation)
                changed += [t, getattr(src, "BodyId", t)] if getattr(src, "SSRole", "") == "body" else [t]
                continue
            if not copy:
                arrays = self.arrays_of(obj)
                if arrays:                                # a row moves as one, until a member is detached (Q29)
                    src = self.body(arrays[0].SSSource)
                    src.Placement = App.Placement(src.Placement.Base + vecv, src.Placement.Rotation)
                    for arr in arrays:
                        arr.Origin = arr.Origin + vecv
                    changed += [b for b, o in self.bodies().items() if o is src or getattr(o, "SSArray", "") in [a.Name for a in arrays]]
                    continue
                obj.Placement = App.Placement(obj.Placement.Base + vecv, obj.Placement.Rotation)
                changed.append(t)
                continue
            obj = self.as_component(obj)             # a plain board becomes a component first, once (A22c)
            arr = self.new_array(obj, vecv, count, divide, op["id"]) if (count > 1 or divide) and not self.is_mirror(obj) else None
            for i in range(1, count + 1):
                step = vecv * (i / count) if divide else vecv * i
                nid = new_ids.pop(0) if new_ids else f"{t}_{i + 1}"
                self.copy_body(obj, nid, step, arr, i)
                changed.append(nid)
            if arr is not None:
                changed.append(t)
        return changed

    def mirror_input(self, src, label):
        """What a Part::Mirroring reads for `src`. Released FreeCAD 1.1 (checked on 1.1.3 and 1.1.4) mirrors an
        App::Link as if it had no placement: the copy lands where the component's own shape would mirror to,
        and it doesn't follow when the instance moves. A Part::Compound of the instance carries the placement,
        so instances are mirrored through one. Boards and mirrors are read directly."""
        if not self.is_instance(src):
            return src
        c = self.doc.addObject("Part::Compound", "MirrorInput")
        c.Links = [src]
        c.Label = f"{label} (placed)"
        c.Visibility = False
        add_props(c, SSRole="mirror-input")
        return c

    def arrays_of(self, obj):
        """The arrays that move with a board: its own (a copy in a row), or every row copied from it (the original)."""
        name = getattr(obj, "SSArray", "")
        if name:
            arr = self.doc.getObject(name)
            return [a for a in self.doc.Objects if getattr(a, "SSRole", "") == "array" and a.SSSource == arr.SSSource]
        return [a for a in self.doc.Objects if getattr(a, "SSRole", "") == "array" and a.SSSource == getattr(obj, "BodyId", None)]

    def op_make_assembly(self, op):
        """Group boards into an assembly (T20): a FreeCAD group, so the boards keep their own positions (no
        container scope to break mirrors or links); moving the assembly moves them all."""
        aid = op["new_id"]
        if aid in self.assemblies():
            raise OpError(f"assembly '{aid}' already exists")
        g = self.doc.addObject("App::DocumentObjectGroup", "Assembly")
        g.Label = op.get("name", aid)
        add_props(g, SSRole="assembly", AssemblyId=aid)
        for t in op["targets"]:
            obj = self.body(t)
            if self.assembly_of(obj) is not None:
                raise OpError(f"'{t}' is already in an assembly")
            for other in obj.InList:
                if other.TypeId == "App::DocumentObjectGroup":
                    other.removeObject(obj)
            g.addObject(obj)
        return list(op["targets"])

    def move_assembly(self, g, vecv):
        """Move everything in an assembly by vecv. Each real board moves once (a flipped board's hidden original
        moves by the reflected vector); each mirror's plane shifts by what keeps its image moving with the rest."""
        members = [o for o in g.Group if getattr(o, "SSRole", None) == "body"]
        mirrors = [o for o in members if self.is_mirror(o)]
        refl = lambda v, n: v - n * (2 * v.dot(n))
        moves = {o.Name: vecv for o in members}          # how far each object's own shape moves
        hidden = []
        for o in mirrors:
            src = self.mirror_source(o)
            if getattr(o, "Replaced", False) and src.Name not in moves:
                moves[src.Name] = refl(vecv, unit(o.Normal))
                hidden.append(src)
        for o in mirrors:
            src = self.mirror_source(o)
            if src.Name not in moves:
                raise OpError(f"'{o.BodyId}' mirrors a board outside its assembly: move them separately")
            n = unit(o.Normal)
            rest = vecv - refl(moves[src.Name], n)        # what the plane has to supply; it can only push along n
            along = rest.dot(n)
            if (rest - n * along).Length > 1e-6:
                raise OpError(f"'{o.BodyId}' can't move with the rest: its original moves another way")
            o.Base = o.Base + n * (along / 2)
        plain = [o for o in members if not self.is_mirror(o)]
        moved_arrays = set()
        for o in plain:
            for arr in self.arrays_of(o):
                if arr.Name not in moved_arrays:
                    arr.Origin = arr.Origin + vecv
                    moved_arrays.add(arr.Name)
        for o in plain:
            if getattr(o, "SSArray", ""):
                continue                              # placed by its array, which just moved
            o.Placement = App.Placement(o.Placement.Base + vecv, o.Placement.Rotation)
        for o in hidden:
            o.Placement = App.Placement(o.Placement.Base + moves[o.Name], o.Placement.Rotation)
        return [o.BodyId for o in members]

    def op_detach(self, op):
        """Detach from array (Q29): the board keeps where it is and stops following the row."""
        for t in op["targets"]:
            obj = self.body(t)
            if not getattr(obj, "SSArray", ""):
                raise OpError(f"'{t}' isn't a copy in an array")
            for c in "xyz":
                obj.setExpression(f".Placement.Base.{c}", None)
            obj.SSArray = ""
        return list(op["targets"])

    def op_make_unique(self, op):
        """Make unique (I28): the board gets its own copy of the shared features, so editing it no longer changes
        its siblings. It keeps its place in an array (Q29)."""
        changed = []
        for t in op["targets"]:
            link = self.body(t)
            if not self.is_instance(link):
                raise OpError(f"'{t}' isn't linked to anything")
            dfn = link.LinkedObject
            copy = self.doc.copyObject(dfn, True)
            for g in copy.InList:
                if g.TypeId == "App::DocumentObjectGroup":
                    g.removeObject(copy)
            copy.Label = t
            copy.SSRole = "body"
            copy.BodyId = t
            copy.ComponentName = ""
            copy.Visibility = True
            copy.Placement = link.Placement
            add_props(copy, SSArray=getattr(link, "SSArray", ""), SSArrayIndex=int(getattr(link, "SSArrayIndex", 0)))
            if copy.SSArray:
                self.array_follow(copy, self.doc.getObject(copy.SSArray), copy.SSArrayIndex)
            link.BodyId = ""
            link.SSRole = "unique-replaced"
            self.doc.removeObject(link.Name)
            changed.append(t)
        return changed

    def op_mirror(self, op):
        """Mirrored copy across a plane, kept live: it follows every later edit of its source (FreeCAD Part Mirror)."""
        p = vec(op["plane"]["point"])
        n = unit(vec(op["plane"]["normal"]))
        replace = bool(op.get("replace", False))      # flip the board itself instead of making a copy
        new_ids = list(op.get("new_ids", []))
        changed = []
        group = None
        if not replace and op.get("group"):
            outer = [self.assembly_of(self.body(t)) for t in op["targets"]]
            if all(g is None for g in outer):         # (boards already in an assembly: the mirror joins that one)
                group = self.doc.addObject("App::DocumentObjectGroup", "MirrorGroup")
                group.Label = f"Mirrored {', '.join(op['targets'])}"
                add_props(group, SSRole="assembly", AssemblyId=op["group"], SSKind="mirror")
        for t in op["targets"]:
            src = self.body(t)
            nid = t if replace else (new_ids.pop(0) if new_ids else f"{t}_m")
            if nid in self.bodies() and not replace:
                raise OpError(f"body id '{nid}' already exists")
            if replace:
                src.SSRole = "source"
                src.Label = f"{t} (unflipped)"
                src.Visibility = False
            m = self.doc.addObject("Part::Mirroring", "Mirror")
            m.Source = self.mirror_input(src, nid)
            m.Base = p
            m.Normal = n
            m.Label = nid
            add_props(m, BodyId=nid, SSRole="body", Replaced=replace)
            self.doc.recompute()
            if m.Shape.isNull() or not m.Shape.Solids:
                raise OpError(f"could not mirror '{t}'")
            if group is not None:
                for other in src.InList:
                    if other.TypeId == "App::DocumentObjectGroup":
                        other.removeObject(src)
                group.addObject(src); group.addObject(m)
            elif self.assembly_of(src) is not None:
                self.assembly_of(src).addObject(m)    # a mirror (or a flipped board) stays in its assembly
            changed.append(nid)
        return changed

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

    HANDLERS = ("rect", "push_pull", "mirror", "make_component", "move", "set_material", "detach", "make_unique",
                "make_assembly", "turn_grain")

    def apply(self, op):
        if op["type"] not in self.HANDLERS:
            raise OpError(f"unknown op type '{op['type']}'")
        changed = getattr(self, "op_" + op["type"])(op)
        self.doc.recompute()
        bad = [o.Label for o in self.doc.Objects if "Invalid" in o.State or "Error" in o.State]
        if bad:
            raise OpError(f"FreeCAD couldn't recompute: {', '.join(bad[:3])}")
        return changed


def to_world(model, obj, shape):
    """A shape in a board's own frame, as it appears for this body (instance / mirrored copy)."""
    if model.is_mirror(obj):
        return to_world(model, model.mirror_source(obj), shape).mirror(obj.Base, obj.Normal)
    s = shape.copy()
    s.transformShape(obj.Placement.toMatrix())
    return s


def cuts_of(model, obj):
    """Each cut-out / added piece on a board, one entry per solid (an array gives one per copy)."""
    dfn = model.definition(obj)
    out = []
    for f in getattr(dfn, "Group", []):
        # only cut-outs made from a drawn rectangle (holes, pockets, dados) can be grabbed and moved:
        # a whole face pushed in or out, or an added piece, is the board itself as far as Move is concerned
        if f.TypeId != "Part::Cut" or not getattr(f, "SSOp", ""):
            continue
        for tool in model.tools_of(f):
            if tool is None or tool.Shape.isNull():
                continue
            cutter = tool.Base if model.is_array(tool) else tool
            if getattr(getattr(cutter, "Base", None), "TypeId", "") != "Part::Plane":
                continue
            board_bb = model.world_shape(obj).BoundBox
            for sol in to_world(model, obj, tool.Shape).Solids:
                bb = sol.BoundBox
                if bb.intersect(board_bb):
                    bb = bb.intersected(board_bb)
                out.append({"op": getattr(cutter, "SSOp", "") or f.SSOp, "kind": "cut",
                            "lo": [bb.XMin, bb.YMin, bb.ZMin], "hi": [bb.XMax, bb.YMax, bb.ZMax]})
    return out


def material_of(model, obj):
    return getattr(model.definition(obj), "SSMaterial", "") or ""


def component_of(model, obj):
    if model.is_mirror(obj):
        base = component_of(model, model.mirror_source(obj))
        return f"{base} (mirrored)" if base else None
    return (getattr(obj.LinkedObject, "ComponentName", "") or None) if model.is_instance(obj) else None


# ---------- glTF writer (pure python, flat-shaded, mm -> m, Z-up -> Y-up) ----------
PALETTE = {
    "white oak": (0.78, 0.64, 0.45),
    "western red cedar": (0.66, 0.38, 0.24),
    "": (0.82, 0.80, 0.76),
}


def material_color(key):
    if key in wood.SPECIES:
        return wood.SPECIES[key][10]
    return PALETTE.get(key, (0.7, 0.7, 0.7) if key else PALETTE[""])


_MESH_CACHE = {}


def shape_key(obj):
    """Identity of a board's world geometry, from FreeCAD's own shape handles: it changes exactly
    when a feature recomputes or a placement moves (about 10 us, versus ms for any geometric check)."""
    t = obj.TypeId
    if t == "App::Link":
        lo = obj.LinkedObject
        return ("L", shape_key(lo)[1:] if lo is not None else None, str(obj.Placement))
    if t == "App::Part":
        tip = getattr(obj, "Tip", None)
        return ("P", obj.Name, tip.Name if tip is not None else None,
                tip.Shape.hashCode() if tip is not None else 0, str(obj.Placement))
    shp = getattr(obj, "Shape", None)
    return ("S", obj.Name, shp.hashCode() if shp is not None else 0, str(getattr(obj, "Placement", "")))


_ENTRY_CACHE = {}


def mesh_of(bid, obj, model):
    """Tessellate a board only when its world shape changed since the last export."""
    sig = shape_key(obj)
    hit = _MESH_CACHE.get(bid)
    if hit and hit[0] == sig:
        return hit[1]
    verts, tris = model.world_shape(obj).tessellate(0.1)
    pos, nor = [], []
    for a, b, c in tris:
        pa, pb, pc = verts[a], verts[b], verts[c]
        n = (pb - pa).cross(pc - pa)
        n = n.normalize() if n.Length > 1e-12 else V(0, 0, 1)
        for p in (pa, pb, pc):
            pos += [p.x / 1000, p.z / 1000, -p.y / 1000]
            nor += [n.x, n.z, -n.y]
    packed = None
    if pos:
        xs, ys, zs = pos[0::3], pos[1::3], pos[2::3]
        packed = (struct.pack(f"<{len(pos)}f", *pos), struct.pack(f"<{len(nor)}f", *nor), len(pos) // 3,
                  [min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)])
    _MESH_CACHE[bid] = (sig, packed)
    return packed


# ---------- per-board mesh files for the viewport (T3) ----------
_MESH_FILES = {}    # (outdir, board id) -> the file currently describing it


def _pv3(points):
    """Points as a Godot PackedVector3Array in Godot's own binary format (var_to_bytes): the viewport reads
    it with one native call. Type 36, count, then float32 x y z."""
    flat = []
    for p in points:
        flat += (p[0], p[1], p[2])
    return struct.pack("<II", 36, len(points)) + struct.pack(f"<{len(flat)}f", *flat)


def board_mesh_file(bid, obj, model, outdir):
    """The board's file, written only when its shape changed: triangles and normals (model mm, Z-up; listed
    clockwise from outside, as Godot draws front faces), then FreeCAD's own edges and corners for snapping."""
    key = hashlib.sha1(repr(shape_key(obj)).encode()).hexdigest()[:16]
    name = f"{bid}-{key}.bin"
    folder = os.path.join(outdir, "meshes")
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        ws = model.world_shape(obj)
        verts, tris = ws.tessellate(0.1)
        pos, nor = [], []
        for a, b, c in tris:
            pa, pb, pc = verts[a], verts[b], verts[c]
            n = (pb - pa).cross(pc - pa)
            n = n.normalize() if n.Length > 1e-12 else V(0, 0, 1)
            pos += (pa, pc, pb)
            nor += (n, n, n)
        edges = []
        for e in ws.Edges:
            if isinstance(e.Curve, Part.Line) and len(e.Vertexes) == 2:
                pts = [e.Vertexes[0].Point, e.Vertexes[1].Point]
            else:
                pts = e.discretize(Deflection=0.1)
            for i in range(len(pts) - 1):
                edges += (pts[i], pts[i + 1])
        corners = [v.Point for v in ws.Vertexes]
        os.makedirs(folder, exist_ok=True)
        with open(path + ".tmp", "wb") as f:
            f.write(_pv3(pos) + _pv3(nor) + _pv3(edges) + _pv3(corners))
        os.replace(path + ".tmp", path)
    old = _MESH_FILES.get((outdir, bid))
    if old and old != name:
        try:
            os.remove(os.path.join(folder, old))
        except OSError:
            pass
    _MESH_FILES[(outdir, bid)] = name
    return name


def write_glb(model, path):
    bin_parts, accessors, views, meshes, nodes, mats = [], [], [], [], [], []
    mat_index = {}
    offset = 0

    def add_view(data, target):
        nonlocal offset
        pad = (-len(data)) % 4
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(data), "target": target})
        bin_parts.append(data + b"\x00" * pad)
        offset += len(data) + pad
        return len(views) - 1

    for bid, obj in model.bodies().items():
        mesh = mesh_of(bid, obj, model)
        if mesh is None:
            continue
        pdata, ndata, count, lo, hi = mesh
        pv = add_view(pdata, 34962)
        accessors.append({"bufferView": pv, "componentType": 5126, "count": count, "type": "VEC3",
                          "min": lo, "max": hi})
        pa_i = len(accessors) - 1
        nv = add_view(ndata, 34962)
        accessors.append({"bufferView": nv, "componentType": 5126, "count": count, "type": "VEC3"})
        na_i = len(accessors) - 1
        m = material_of(model, obj)
        if m not in mat_index:
            r, g, b = material_color(m)
            mat = {"name": m or "unassigned",
                   "pbrMetallicRoughness": {"baseColorFactor": [r, g, b, 1], "metallicFactor": 0, "roughnessFactor": 0.8}}
            if m in wood.SPECIES:                     # for a Blender set-up: the textures and their real size (T15)
                sp = wood.SPECIES[m]
                tdir = os.path.normpath(os.path.join(HERE, "..", "materials", "textures"))
                mat["extras"] = {"wood": sp[0], "texture": os.path.join(tdir, sp[7] + ".jpg"),
                                 "texture_grain_along": sp[8], "texture_size_mm": sp[9],
                                 "end_texture": os.path.join(tdir, m + "_end.jpg"), "end_size_mm": wood.END_SIZE_MM}
            mats.append(mat)
            mat_index[m] = len(mats) - 1
        meshes.append({"name": bid, "primitives": [{"attributes": {"POSITION": pa_i, "NORMAL": na_i},
                                                    "material": mat_index[m]}]})
        nodes.append({"name": bid, "mesh": len(meshes) - 1,
                      "extras": {"body_id": bid, "material": m, "component": component_of(model, obj),
                                 "grain_zup": list(model.grain_world(obj)), "across_zup": list(model.grain_world(obj, "across")),
                                 "state": "confirmed"}})

    tmp = path + ".tmp"
    if not nodes:  # nothing solid yet (e.g. only rectangles): valid, empty glTF
        js = json.dumps({"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": []}]}).encode()
        js += b" " * ((-len(js)) % 4)
        with open(tmp, "wb") as f:
            f.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js)))
            f.write(struct.pack("<I4s", len(js), b"JSON")); f.write(js)
        os.replace(tmp, path)
        return
    gltf = {"asset": {"version": "2.0", "generator": "Shop Sketch worker 0.2"},
            "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}],
            "nodes": nodes, "meshes": meshes, "materials": mats,
            "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": offset}]}
    js = json.dumps(gltf).encode()
    js += b" " * ((-len(js)) % 4)
    binblob = b"".join(bin_parts)
    total = 12 + 8 + len(js) + 8 + len(binblob)
    with open(tmp, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(js), b"JSON")); f.write(js)
        f.write(struct.pack("<I4s", len(binblob), b"BIN\x00")); f.write(binblob)
    os.replace(tmp, path)


# ---------- TechDraw page ----------
def add_drawing_page(doc, objs):
    import TechDraw  # noqa: F401  (registers types)
    import glob
    page = doc.addObject("TechDraw::DrawPage", "Drawing")
    tpl = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
    cands = glob.glob(os.path.join(App.getResourceDir(), "Mod/TechDraw/Templates/**/A3_Landscape_blank.svg"),
                      recursive=True)
    if cands:
        tpl.Template = cands[0]
    page.Template = tpl
    views = {}
    for name, direction, xdir, pos in [
        ("Front", V(0, -1, 0), V(1, 0, 0), (150, 190)),
        ("Top", V(0, 0, 1), V(1, 0, 0), (150, 90)),
        ("Right", V(1, 0, 0), V(0, 1, 0), (330, 190)),
        ("Iso", V(1, -1, 1), V(1, 1, 0), (330, 90)),
    ]:
        v = doc.addObject("TechDraw::DrawViewPart", name)
        page.addView(v)
        v.Source = objs
        v.Direction = direction
        v.XDirection = xdir
        v.Scale = 1.0
        v.X, v.Y = pos
        views[name] = v
    doc.recompute()
    return page, views


def remove_drawing_pages(doc):
    """Drawing pages are regenerated in the saved copy; the live document stays model-only."""
    # Views first, then templates, then pages, by name, skipping any already gone: FreeCAD 1.1.4 deletes a page's
    # views and template along with it, and removing an object that's already deleted crashes FreeCAD (bus error).
    rank = lambda o: 2 if o.TypeId == "TechDraw::DrawPage" else 1 if "Template" in o.TypeId else 0
    doomed = [o.Name for o in sorted((o for o in doc.Objects if o.TypeId.startswith("TechDraw::")), key=rank)]
    for name in doomed:
        if doc.getObject(name) is None:
            continue
        try:
            doc.removeObject(name)
        except Exception:
            pass
    return bool(doomed)


_HIDDEN_IN_FREECAD = {"App::Origin", "App::Line", "App::Plane", "App::Point", "TechDraw::DrawPage"}


def write_gui_document(fcstd, previous=None):
    """Add the part of the file FreeCAD's window reads (GuiDocument.xml). freecadcmd never writes it, and without
    it FreeCAD opens the model with every object hidden. Each object shows as the model says (a board's current
    solid shown, its steps hidden); board axes and planes and the drawing page stay hidden. View settings FreeCAD
    saved in the previous file (colours, line widths, the camera) are kept."""
    import zipfile
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(fcstd) as z:
        if "GuiDocument.xml" in z.namelist():
            return
        doc = ET.fromstring(z.read("Document.xml"))
    kinds = {o.get("name"): o.get("type") for o in doc.find("Objects").findall("Object")}
    shown = {}
    for o in doc.find("ObjectData").findall("Object"):
        v = [p for p in o.iter("Property") if p.get("name") == "Visibility"]
        shown[o.get("name")] = bool(v) and v[0].find("Bool").get("value") == "true"
    old, camera = {}, None
    if previous and os.path.exists(previous):
        try:
            with zipfile.ZipFile(previous) as z:
                if "GuiDocument.xml" in z.namelist():
                    g = ET.fromstring(z.read("GuiDocument.xml"))
                    old = {vp.get("name"): vp for vp in g.iter("ViewProvider")}
                    camera = g.find("Camera")
        except (zipfile.BadZipFile, ET.ParseError, OSError):
            pass
    out = ET.Element("Document", SchemaVersion="1", HasExpansion="1")
    ET.SubElement(out, "Expand")
    data = ET.SubElement(out, "ViewProviderData", Count=str(len(kinds)))
    for name, kind in kinds.items():
        vp = old.get(name)
        if vp is None:
            vp = ET.Element("ViewProvider", name=name, expanded="0")
            ET.SubElement(vp, "Properties", Count="0", TransientCount="0")
        props = vp.find("Properties")
        vis = [p for p in props.findall("Property") if p.get("name") == "Visibility"]
        if vis:
            prop = vis[0]
        else:
            prop = ET.SubElement(props, "Property", name="Visibility", type="App::PropertyBool", status="1")
            ET.SubElement(prop, "Bool", value="false")
            props.set("Count", str(len(props.findall("Property"))))
        on = shown.get(name, False) and kind not in _HIDDEN_IN_FREECAD
        prop.find("Bool").set("value", "true" if on else "false")
        data.append(vp)
    if camera is not None:
        out.append(camera)
    with zipfile.ZipFile(fcstd, "a", zipfile.ZIP_DEFLATED) as z:
        z.writestr("GuiDocument.xml", b"<?xml version='1.0' encoding='utf-8'?>\n" + ET.tostring(out))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def journal_path(model_path):
    base, _ = os.path.splitext(model_path)
    return base + ".shopsketch.json"


def _norm(v):
    """Numbers compare by value: Godot hands 18 back as 18.0, and float noise isn't a different op."""
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        r = round(float(v), 9)
        return int(r) if r == int(r) else r
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    return v


def canon(op):
    return json.dumps(_norm(op), sort_keys=True, separators=(",", ":"))


class Session:
    """One live document bound to one .FCStd file.

    applied: one entry per op the document has seen, in order: {op, key, status, message, changed, ms}.
    Each ok op is exactly one FreeCAD undo transaction; failed ops were aborted and left none.
    undo_floor: ops before this index can't be taken back with FreeCAD's undo (they came from the
    file); taking them back means rebuilding from the journal, which is only safe when nobody
    else has edited the file (external == False)."""

    def __init__(self, model_path, fresh=False):
        self.path = os.path.abspath(model_path) if model_path else None
        self.applied = []
        self.undo_floor = 0
        self.external = False
        self.rev = 0
        self.dirty = False
        self.drawing = False
        self.session_base = 0
        self.doc = None
        self.file_sig = None
        if self.path and os.path.exists(self.path) and not fresh:
            self._open_existing()
        else:
            self._new_doc()

    # ----- document lifecycle -----
    def _new_doc(self):
        if self.doc is not None:
            App.closeDocument(self.doc.Name)
        self.doc = App.newDocument("ShopSketch")
        self.doc.UndoMode = 1
        self.model = Model(self.doc)

    def _open_existing(self):
        self.doc = App.openDocument(self.path)
        self.doc.UndoMode = 1
        self.drawing = remove_drawing_pages(self.doc)
        self.doc.recompute()
        self.model = Model(self.doc)
        self.rev = int(self.doc.Meta.get("ShopSketchRev", "0") or 0)
        jp = journal_path(self.path)
        j = None
        if os.path.exists(jp):
            with open(jp) as f:
                j = json.load(f)
        if j and j.get("format") == JOURNAL_FORMAT:
            for op, st in zip(j["ops"], j["status"]):
                if st.get("status") == "ok":           # failed ops left nothing in the file
                    self.applied.append({"op": op, "key": canon(op), "id": op.get("id"), "type": op.get("type"), **st})
            same_rev = int(j.get("rev", -1)) == self.rev
            self.external = not (same_rev and j.get("file_sha256") == sha256(self.path))
        else:
            self.external = True     # not written by Shop Sketch (stage 3 will adopt foreign solids)
        self.undo_floor = len(self.applied) if self.external else 0
        self.session_base = len(self.applied)
        self.doc.clearUndos()
        self.file_sig = self.disk_sig()

    def disk_sig(self):
        try:
            st = os.stat(self.path)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def changed_on_disk(self):
        """True when someone else wrote the file since we last read or saved it (stage 2 will merge;
        for now an open simply reloads it)."""
        return self.path is not None and self.file_sig is not None and self.disk_sig() != self.file_sig

    # ----- applying ops -----
    def _apply(self, op):
        t0 = time.perf_counter()
        entry = {"op": op, "key": canon(op), "id": op.get("id"), "type": op.get("type")}
        self.doc.openTransaction(str(op.get("id", "op")))
        try:
            changed = self.model.apply(op)
            self.doc.commitTransaction()
            entry.update(status="ok", changed=changed)
        except Exception as e:
            self.doc.abortTransaction()
            self.doc.recompute()
            msg = str(e) if isinstance(e, OpError) else f"{type(e).__name__}: {e}"
            entry.update(status="failed", message=msg)
            print(f"WORKER op failed: {canon(op)} -> {msg}", flush=True)
        entry["ms"] = round((time.perf_counter() - t0) * 1000, 1)
        self.applied.append(entry)

    def _rebuild(self, ops):
        self._new_doc()
        self.applied = []
        self.session_base = 0
        self.undo_floor = 0
        for op in ops:
            self._apply(op)

    def sync(self, ops):
        """Make the document match `ops`: keep the common prefix, take back the rest with FreeCAD's
        undo, apply the new ops as transactions. Returns how it got there."""
        t0 = time.perf_counter()
        keys = [canon(o) for o in ops]
        k = 0
        while k < len(self.applied) and k < len(keys) and self.applied[k]["key"] == keys[k]:
            k += 1
        if k < self.undo_floor:
            raise OpError(f"can't take back ops before {self.undo_floor}: the file was changed in FreeCAD "
                          f"after they were made (watch & merge is stage 2)")
        tail = self.applied[k:]
        n_undo = sum(1 for e in tail if e["status"] == "ok")
        how = "nothing"
        if tail and (k < self.session_base or n_undo > self.doc.UndoCount):
            self._rebuild(ops)
            how = "rebuilt"
        else:
            for _ in range(n_undo):
                self.doc.undo()
            if n_undo:
                self.doc.recompute()
            del self.applied[k:]
            for op in ops[k:]:
                self._apply(op)
            if tail or len(ops) > k:
                how = f"undid {n_undo}, applied {len(ops) - k}"
        if how != "nothing":
            self.dirty = True
        return how, round((time.perf_counter() - t0) * 1000, 1)

    # ----- outputs -----
    def status(self):
        out = []
        for e in self.applied:
            s = {k: e[k] for k in ("id", "type", "status", "changed", "message", "ms") if k in e}
            s.setdefault("id", e["op"].get("id"))
            s.setdefault("type", e["op"].get("type"))
            out.append(s)
        return out

    def export(self, outdir):
        """bodies.json plus a mesh file per board that changed (the viewport rebuilds only those, T3)."""
        os.makedirs(outdir, exist_ok=True)
        t0 = time.perf_counter()
        m = self.model
        bodies = []
        for bid, obj in m.bodies().items():
            key = (shape_key(obj), material_of(m, obj), component_of(m, obj),
                   tuple(round(c, 6) for c in m.grain_world(obj)))
            hit = _ENTRY_CACHE.get(bid)
            if not hit or hit[0] != key:
                ws = m.world_shape(obj)
                bb = ws.BoundBox
                dfn = m.definition(obj)
                lb = (dfn.Tip.Shape if getattr(dfn, "Tip", None) is not None else ws).BoundBox
                hit = (key, {"id": bid, "material": key[1], "component": key[2], "grain": list(key[3]),
                             "across": [round(c, 6) for c in m.grain_world(obj, "across")],
                             "world_bbox": [bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax],
                             "size": sorted([round(lb.XLength, 2), round(lb.YLength, 2), round(lb.ZLength, 2)]),
                             "volume_mm3": round(ws.Volume, 1), "cuts": cuts_of(m, obj)})
                _ENTRY_CACHE[bid] = hit
            mat = hit[1]["material"]
            bodies.append(dict(hit[1], mesh=board_mesh_file(bid, obj, m, outdir),
                               color=list(material_color(mat)), family=m.definition(obj).Name,
                               array=getattr(obj, "SSArray", "") or "",
                               assembly=getattr(m.assembly_of(obj), "AssemblyId", "") if m.assembly_of(obj) else "",
                               row=(m.arrays_of(obj)[0].SSSource if m.arrays_of(obj) else ""),
                               mirror_plane=([list(obj.Base), list(unit(obj.Normal))] if m.is_mirror(obj) else [])))
        shared = {}
        for e in bodies:
            shared[e["family"]] = shared.get(e["family"], 0) + 1
        for e in bodies:                         # boards that share a definition: the viewport tints them while editing
            if shared[e["family"]] < 2:
                e["family"] = ""
        atomic_json(os.path.join(outdir, "bodies.json"), bodies)
        if outdir not in _MATERIALS["outdirs"]:             # the paint list, once per output folder
            _MATERIALS["outdirs"].add(outdir)
            wood.write_library(os.path.join(outdir, "materials.json"))
        return round((time.perf_counter() - t0) * 1000, 1)

    def save(self, outdir=None):
        """Atomic autosave: write a copy beside the file, then swap it in. With a drawing wanted, the
        copy gets a fresh TechDraw page (the live document never carries one)."""
        if not self.path:
            return None
        t0 = time.perf_counter()
        if outdir:
            write_glb(self.model, os.path.join(outdir, "model.glb"))     # the whole model, for renders (A07)
        self.rev += 1
        meta = self.doc.Meta
        meta["ShopSketchRev"] = str(self.rev)
        self.doc.Meta = meta
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".saving.FCStd"
        self.doc.saveCopy(tmp)
        if self.drawing:
            d2 = App.openDocument(tmp)
            try:
                objs = [o for o in d2.Objects if getattr(o, "SSRole", None) == "body"]
                page, views = add_drawing_page(d2, objs)
                if outdir:
                    import TechDraw
                    atomic_json(os.path.join(outdir, "views.json"),
                                {name: TechDraw.viewPartAsSvg(v) for name, v in views.items()})
                d2.save()
            finally:
                App.closeDocument(d2.Name)
        write_gui_document(tmp, self.path)          # what FreeCAD's window shows (T29)
        os.replace(tmp, self.path)
        atomic_json(journal_path(self.path), {
            "format": JOURNAL_FORMAT, "rev": self.rev, "file_sha256": sha256(self.path),
            "model": os.path.basename(self.path), "name": os.path.splitext(os.path.basename(self.path))[0],
            "ops": [e["op"] for e in self.applied],
            "status": [{k: e[k] for k in ("status", "changed", "message", "ms") if k in e} for e in self.applied]})
        self.dirty = False
        self.file_sig = self.disk_sig()
        self.external = False
        self.undo_floor = 0     # the file is now exactly our journal again
        return round((time.perf_counter() - t0) * 1000, 1)

    def close(self):
        if self.doc is not None:
            App.closeDocument(self.doc.Name)
            self.doc = None


def run_sync(session, req):
    ops = req["oplog"]["ops"] if "oplog" in req else req["ops"]
    if req.get("oplog", {}).get("units", "mm") != "mm":
        raise OpError("only mm supported")
    if req.get("drawing"):
        session.drawing = True
    how, ms = session.sync(ops)
    outdir = req.get("outdir") or os.path.dirname(session.path)
    export_ms = session.export(outdir)
    status = session.status()
    result = {"oplog": req.get("name", "live"), "total_ms": ms, "export_ms": export_ms, "how": how,
              "ops": status, "rev": session.rev + (1 if session.dirty else 0), "model": session.path}
    atomic_json(os.path.join(outdir, "status.json"), result)
    return result, outdir


def worker_identity():
    """What a window compares before sharing this worker: the script it runs (same file contents = same worker)."""
    return hashlib.md5(open(os.path.abspath(__file__), "rb").read()).hexdigest()


def serve(port):
    """Long-running worker: newline-delimited JSON over localhost TCP. One worker serves every Shop Sketch window,
    each on its own FreeCAD document; a model belongs to one window at a time (W13).
      {"cmd": "hello"} -> {"ok", "cmd": "hello", "app": "shopsketch", "worker": <md5 of this script>, "pid"}
      {"cmd": "open", "model": ".../model.FCStd", "fresh": false}
          -> {"ok", "cmd": "open", "ops", "undo_floor", "external", "rev"}
          -> {"ok": false, "cmd": "open", "error": "already_open", "model"} when another window has it; that window
             is sent {"cmd": "focus", "model"} so it can come to the front
      {"cmd": "sync", "model": "...", "oplog": {...}, "outdir": "...", "seq": n, "drawing": false}
          -> {"ok", "cmd": "sync", "result": {...status...}, "outdir" (bodies.json, meshes/), "seq", "wall_ms"}
      {"cmd": "replay", ...}  same as sync on a fresh document (one-shot rebuild)
      {"cmd": "flush"}  save everything now;  {"cmd": "bye"}  save this window's model and let it go
      {"cmd": "quit"}   save, and stop if no other window is connected (else just this window leaves)
    The reply goes out first; the autosave waits until every window has been quiet for IDLE_SAVE_S, so quick
    successive actions never queue behind a save. When a save lands the window that owns the model is told:
          {"cmd": "saved", "model": "...", "rev": n}   (the viewport's quiet 'Saved' indicator, Q22)
    SERVE_IDLE_EXIT=<s>: save and exit that long after the last window leaves (the shared worker windows start)."""
    import select
    import socket
    sessions = {}
    to_save = {}          # session path -> (session, outdir)
    owners = {}           # model path -> the connection (window) that has it open
    clients = {}          # connection -> {"buf": bytes, "models": set of paths}
    IDLE_SAVE_S = 0.25
    idle_exit = float(os.environ.get("SERVE_IDLE_EXIT", "0") or 0)
    me = worker_identity()
    clock = {"active": time.monotonic(), "alone": None}

    def send(conn, obj):
        try:
            conn.sendall((json.dumps(obj) + "\n").encode())
        except OSError:
            pass

    def save_pending(paths=None):
        for path, (sess, od) in list(to_save.items()):
            if paths is not None and path not in paths:
                continue
            try:
                save_ms = sess.save(od)
                print(f"WORKER saved rev {sess.rev} in {save_ms} ms", flush=True)
                if owners.get(path) in clients:
                    send(owners[path], {"ok": True, "cmd": "saved", "model": sess.path, "rev": sess.rev})
            except Exception as e:
                print(f"WORKER save failed: {type(e).__name__}: {e}", flush=True)
            to_save.pop(path, None)

    def session_for(path, fresh=False, reload=False):
        path = os.path.abspath(path)
        if path in sessions and (fresh or (reload and sessions[path].changed_on_disk())):
            sessions.pop(path).close()
        if path not in sessions:
            sessions[path] = Session(path, fresh=fresh)
        return sessions[path]

    def let_go(conn, paths):
        save_pending(set(paths))                    # whatever it changed is saved before anyone else can open it
        for p in paths:
            clients[conn]["models"].discard(p)
            if owners.get(p) is conn:
                owners.pop(p)

    def release(conn):
        if conn in clients:
            let_go(conn, list(clients[conn]["models"]))
            clients.pop(conn)
        try:
            conn.close()
        except OSError:
            pass
        if not clients:
            clock["alone"] = time.monotonic()

    def claim(conn, path):
        """This window takes the model (leaving the one it had). Returns the other window if it's taken."""
        other = owners.get(path)
        if other is not None and other is not conn and other in clients:
            return other
        let_go(conn, [p for p in clients[conn]["models"] if p != path])
        owners[path] = conn
        clients[conn]["models"].add(path)
        return None

    def handle(conn, line):
        t0 = time.perf_counter()
        after = None
        seq = cmd = None
        try:
            req = json.loads(line)
            cmd = req.get("cmd")
            seq = req.get("seq")
            if cmd == "hello":
                send(conn, {"ok": True, "cmd": "hello", "app": "shopsketch", "worker": me, "pid": os.getpid()})
                return None
            if cmd == "quit":
                if len(clients) > 1:                # other windows still use this worker: only this one leaves
                    send(conn, {"ok": True, "cmd": "quit", "stopped": False})
                    release(conn)
                    return None
                save_pending()
                send(conn, {"ok": True, "cmd": "quit", "stopped": True})
                return "stop"
            if cmd == "bye":
                let_go(conn, list(clients[conn]["models"]))
                send(conn, {"ok": True, "cmd": "bye"})
                release(conn)
                return None
            if cmd == "flush":              # save now (tests, quitting the app)
                save_pending()
                send(conn, {"ok": True, "cmd": "flush", "seq": seq})
                return None
            if req.get("delay_ms"):        # test hook: simulate a slow FreeCAD calculation
                time.sleep(float(req["delay_ms"]) / 1000.0)
            if cmd == "open":
                path = os.path.abspath(req["model"])
                other = claim(conn, path)
                if other is not None:
                    send(other, {"ok": True, "cmd": "focus", "model": path})
                    resp = {"ok": False, "cmd": "open", "error": "already_open", "model": path}
                else:
                    s = session_for(path, fresh=req.get("fresh", False), reload=True)
                    resp = {"ok": True, "cmd": "open", "model": s.path, "rev": s.rev,
                            "ops": [e["op"] for e in s.applied], "undo_floor": s.undo_floor,
                            "external": s.external}
            elif cmd in ("sync", "replay"):
                model = os.path.abspath(req.get("model") or os.path.join(req["outdir"], "model.FCStd"))
                if claim(conn, model) is not None:
                    raise OpError(f"{os.path.basename(model)} is open in another window")
                s = session_for(model, fresh=(cmd == "replay"))
                res, outdir = run_sync(s, req)
                resp = {"ok": True, "cmd": "sync", "result": res, "outdir": outdir,
                        "seq": seq, "wall_ms": round((time.perf_counter() - t0) * 1000, 1)}
                if s.dirty or req.get("drawing"):
                    after = (s, outdir)
            else:
                raise OpError(f"unknown cmd '{cmd}'")
        except Exception as e:
            resp = {"ok": False, "cmd": cmd, "error": f"{type(e).__name__}: {e}", "seq": seq}
        send(conn, resp)
        if after:
            to_save[after[0].path] = after
        print(f"WORKER {cmd} seq={seq} {resp.get('wall_ms')} ms "
              f"{resp.get('result', {}).get('how', '') if resp.get('ok') else resp.get('error')}"
              f"  [{len(clients)} window{'s' if len(clients) != 1 else ''}]", flush=True)
        return None

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(16)
    print(f"WORKER listening on 127.0.0.1:{port}" + (f" (exits {idle_exit:g} s after the last window)" if idle_exit else ""),
          flush=True)
    while True:
        readable, _, _ = select.select([srv] + list(clients), [], [], IDLE_SAVE_S)
        now = time.monotonic()
        if not readable:
            if to_save and now - clock["active"] >= IDLE_SAVE_S:
                save_pending()
            if idle_exit and not clients and clock["alone"] is not None and now - clock["alone"] >= idle_exit:
                save_pending()
                print("WORKER no windows left: stopping", flush=True)
                return
            continue
        for sock in readable:
            if sock is srv:
                conn, _ = srv.accept()
                clients[conn] = {"buf": b"", "models": set()}
                clock["alone"] = None
                continue
            if sock not in clients:
                continue
            try:
                chunk = sock.recv(65536)
            except OSError:
                chunk = b""
            if not chunk:                   # the window went away: its last change still gets saved
                release(sock)
                continue
            clock["active"] = now
            st = clients[sock]
            st["buf"] += chunk
            while sock in clients and b"\n" in st["buf"]:
                line, st["buf"] = st["buf"].split(b"\n", 1)
                if line.strip() and handle(sock, line) == "stop":
                    return
            clock["active"] = time.monotonic()     # the quiet before an autosave counts from the last reply


def main():
    if os.environ.get("SERVE_PORT"):
        serve(int(os.environ["SERVE_PORT"]))
        return
    oplog_path = os.environ["OPLOG"]
    with open(oplog_path) as f:
        log = json.load(f)
    outdir = os.environ["OUTDIR"]
    s = Session(os.path.join(outdir, "model.FCStd"), fresh=True)
    res, _ = run_sync(s, {"oplog": log, "outdir": outdir, "drawing": True, "name": os.path.basename(oplog_path)})
    s.save(outdir)
    ok = sum(1 for e in res["ops"] if e["status"] == "ok")
    print(f"REPLAY: {ok}/{len(res['ops'])} ops ok in {res['total_ms']} ms")
    for e in res["ops"]:
        if e["status"] != "ok":
            print(f"REPLAY FAILED {e['id']}: {e['message']}")
    s.close()


main()
