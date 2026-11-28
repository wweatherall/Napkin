"""Move and copy: moving boards and holes, linked copies and arrays (A22c, T12), detach and make unique.

Auto-discovered `MoveActions`: `op_make_unique` detaches inherited `PlaneFit` ties while preserving geometry and
hands `SSSourceBodyId` driving duty to a surviving sibling. Copying a plain board converts it to an `App::Link`
component; array holders are `App::Placement` objects with expression-driven member placements."""
import FreeCAD as App
from common import OpError, TOL, V, add_props, board_label, unit, vec


class MoveActions:
    """Part of Model (model.py): works through self on the FreeCAD document."""

    def op_make_component(self, op):
        bid = op["body"]
        obj = self.body(bid)
        if self.is_instance(obj):
            raise OpError(f"'{bid}' is already a component instance", about=[bid])
        if self.is_mirror(obj) or obj.TypeId != "App::Part":
            raise OpError(f"'{bid}' can't be made a component", about=[bid])
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
        link.Label = board_label(bid)
        add_props(link, BodyId=bid, SSRole="body", SSHidden=bool(getattr(obj, "SSHidden", False)))
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
        link.Label = board_label(nid)
        add_props(link, BodyId=nid, SSRole="body", SSArray=array, SSArrayIndex=index, SSHidden=False)
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

    def copy_assembly_mirror(self, obj, nid, step, arr=None, index=0):
        """Copy a mirrored assembly member as live native mirrors of linked hidden sources.

        The placed hidden source keeps its own frame, so editing either the original
        or a copy reaches the same definition through the existing mirror edit frame.
        """
        origin = arr.Origin if arr is not None else V(0, 0, 0)

        def follow(target, path, base):
            if arr is None:
                return
            for c in "xyz":
                offset = getattr(base - origin, c)
                target.setExpression(f"{path}.{c}",
                                     f"{arr.Name}.Origin.{c} + {arr.Name}.Step.{c} * {index} + ({offset:.17g})")

        def clone(source, visible=False):
            if self.is_mirror(source):
                child = clone(self.mirror_source(source))
                result = self.doc.addObject("Part::Mirroring", "Mirror")
                result.Source = self.mirror_input(child, nid)
                result.Base = source.Base + step
                result.Normal = source.Normal
                # A copied mirror owns its hidden source for movement, like a flip.
                add_props(result, BodyId=nid if visible else "", SSRole="body" if visible else "source",
                          Replaced=True, SSHidden=False, SSArray=arr.Name if arr is not None and visible else "",
                          SSArrayIndex=index)
                follow(result, "Base", source.Base)
            else:
                source = self.as_component(source)
                result = self.new_link(self.definition(source), "", App.Placement(source.Placement.Base + step, source.Placement.Rotation))
                result.SSRole = "source"
                follow(result, "Placement.Base", source.Placement.Base)
            result.Label = board_label(nid) if visible else f"{nid} (linked mirror source)"
            result.Visibility = visible
            return result

        return clone(obj, True)

    def cutter_of(self, container, oid):
        """The Cut that holds the hole made by push/pull `oid`, and the tool that makes it there."""
        for o in container.Group:
            if o.TypeId != "Part::Cut":
                continue
            for t in self.tools_of(o):
                src = t.Base if self.is_array(t) else t
                if getattr(src, "SSOp", None) == oid:
                    return o, t
        raise OpError(f"no cut from '{oid}' on this board", about=[oid])

    @staticmethod
    def shift(obj, v):
        obj.Placement = App.Placement(obj.Placement.Base + v, obj.Placement.Rotation)

    def move_cut(self, op):
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
            return self.move_cut(op)
        if op.get("selection") and not op.get("copy", False):
            return self.move_selection(op)
        vecv = vec(op["vector"])
        copy = op.get("copy", False)
        count = int(op.get("count", 1))
        divide = op.get("divide", False)
        changed = []
        new_ids = list(op.get("new_ids", []))
        groups, made_groups = op.get("groups", {}), {}   # copying whole assemblies: old AssemblyId -> new one (I47)
        # A group id per copy, in the same order as each board's generated ids. Keep the
        # original string form readable for journals containing a single assembly copy.
        destinations = set()
        for home, ids in groups.items():
            if not isinstance(ids, list):
                ids = [ids]
            if len(ids) != count or len(set(ids)) != count or destinations.intersection(ids):
                raise OpError("each copied assembly needs its own assembly id")
            destinations.update(ids)
        assembly_arrays = {}
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
            home = getattr(self.assembly_of(obj), "AssemblyId", "")
            obj = self.as_component(obj)             # a plain board becomes a component first, once (A22c)
            arr = self.new_array(obj, vecv, count, divide, op["id"]) if (count > 1 or divide) and (not self.is_mirror(obj) or home in groups) else None
            if arr is not None and home in groups:
                master = assembly_arrays.setdefault(home, arr)
                if master is not arr:
                    # Each board retains its own origin, but all boards of an assembly
                    # share one editable spacing/span/count relationship.
                    arr.setExpression("Count", f"{master.Name}.Count")
                    for c in "xyz":
                        arr.setExpression(f"Step.{c}", f"{master.Name}.Step.{c}")
                        arr.setExpression(f"Span.{c}", f"{master.Name}.Span.{c}")
            for i in range(1, count + 1):
                step = vecv * (i / count) if divide else vecv * i
                nid = new_ids.pop(0) if new_ids else f"{t}_{i + 1}"
                if home in groups and self.is_mirror(obj):
                    self.copy_assembly_mirror(obj, nid, step, arr, i)
                else:
                    self.copy_body(obj, nid, step, arr, i)
                if groups.get(home):
                    ids = groups[home]
                    self.copy_into_assembly(nid, ids[i - 1] if isinstance(ids, list) else ids, made_groups)
                changed.append(nid)
            if arr is not None:
                changed.append(t)
        return changed

    def op_detach(self, op):
        """Detach from array (Q29): the board keeps where it is and stops following the row."""
        for t in op["targets"]:
            obj = self.body(t)
            if not getattr(obj, "SSArray", ""):
                raise OpError(f"'{t}' isn't a copy in an array", about=[t])
            if self.is_mirror(obj):
                source = obj
                while self.is_mirror(source):
                    for c in "xyz": source.setExpression(f"Base.{c}", None)
                    source = self.mirror_source(source)
                for c in "xyz": source.setExpression(f"Placement.Base.{c}", None)
            else:
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
                raise OpError(f"'{t}' isn't linked to anything", about=[t])
            dfn = link.LinkedObject
            copy = self.doc.copyObject(dfn, True)
            for g in copy.InList:
                if g.TypeId == "App::DocumentObjectGroup":
                    g.removeObject(copy)
            copy.Label = board_label(t)
            copy.SSRole = "body"
            copy.BodyId = t
            copy.ComponentName = ""
            copy.Visibility = True
            copy.Placement = link.Placement
            if hasattr(getattr(copy, "Tip", None), "SSStock"):
                copy.Tip.SSTargetId = ""
                copy.Tip.SSFitResult = "Detached · shape kept"
                if hasattr(copy.Tip, "SSSourceBodyId"):
                    copy.Tip.SSSourceBodyId = ""
            add_props(copy, SSArray=getattr(link, "SSArray", ""), SSArrayIndex=int(getattr(link, "SSArrayIndex", 0)))
            if not hasattr(copy, "SSHidden"):           # (a definition from a file older than T28)
                add_props(copy, SSHidden=False)
            copy.SSHidden = bool(getattr(link, "SSHidden", False))
            if copy.SSArray:
                self.array_follow(copy, self.doc.getObject(copy.SSArray), copy.SSArrayIndex)
            link.BodyId = ""
            link.SSRole = "unique-replaced"
            self.doc.removeObject(link.Name)
            if hasattr(getattr(dfn, "Tip", None), "SSStock") and getattr(dfn.Tip, "SSSourceBodyId", "") == t:
                siblings = [bid for bid, obj in self.bodies().items()
                            if self.is_instance(obj) and obj.LinkedObject == dfn]
                if siblings:
                    dfn.Tip.SSSourceBodyId = siblings[0]
                else:
                    dfn.Tip.SSSourceBodyId = ""
                    dfn.Tip.SSTargetId = ""
            changed.append(t)
        return changed

    def move_selection(self, op):
        members = {t: self.body(t) for t in op["targets"]}
        for obj in list(members.values()):
            if op.get("detach") and getattr(obj, "SSArray", ""):
                self.op_detach({"targets": [obj.BodyId]})
            for arr in self.arrays_of(obj):
                members[arr.SSSource] = self.body(arr.SSSource)
                members.update({b: o for b, o in self.bodies().items()
                                if getattr(o, "SSArray", "") == arr.Name})
        return self.move_members(list(members.values()), vec(op["vector"]), allow_external=True)
