"""Assemblies (T20): grouping boards and moving a group with its arrays."""
import FreeCAD as App
from common import OpError, add_props, unit


class AssemblyActions:
    """Part of Model (model.py): works through self on the FreeCAD document."""

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

    def copy_into_assembly(self, bid, aid, made):
        """A copy of a board in a wholly copied assembly goes into that copy's new assembly (I47), not the old one."""
        g = made.get(aid)
        if g is None:
            if aid in self.assemblies():
                raise OpError(f"assembly '{aid}' already exists")
            g = made[aid] = self.doc.addObject("App::DocumentObjectGroup", "Assembly")
            g.Label = aid
            add_props(g, SSRole="assembly", AssemblyId=aid)
        obj = self.body(bid)
        for other in obj.InList:
            if other.TypeId == "App::DocumentObjectGroup" and getattr(other, "SSRole", "") == "assembly":
                other.removeObject(obj)
        g.addObject(obj)

    def move_assembly(self, g, vecv):
        """Move everything in an assembly by vecv. Each real board moves once (a flipped board's hidden original
        moves by the reflected vector); each mirror's plane shifts by what keeps its image moving with the rest."""
        return self.move_members([o for o in g.Group if getattr(o, "SSRole", None) == "body"], vecv)

    def move_members(self, members, vecv, allow_external=False):
        mirrors = [o for o in members if self.is_mirror(o)]
        refl = lambda v, n: v - n * (2 * v.dot(n))
        moves = {o.Name: vecv for o in members}          # how far each object's own shape moves
        hidden = []
        for o in mirrors:
            src = self.mirror_source(o)
            if (allow_external or getattr(o, "Replaced", False)) and src.Name not in moves:
                moves[src.Name] = refl(moves[o.Name], unit(o.Normal))
                hidden.append(src)
                if self.is_mirror(src):
                    mirrors.append(src)  # resolve a nested mirror's root exactly once
                elif getattr(src, "SSArray", ""):
                    self.op_detach({"targets": [src.BodyId]})
        for o in mirrors:
            src = self.mirror_source(o)
            if src.Name not in moves:
                raise OpError(f"'{o.BodyId}' mirrors a board outside its assembly: move them separately")
            n = unit(o.Normal)
            rest = moves[o.Name] - refl(moves[src.Name], n)        # what the plane has to supply; it can only push along n
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
            if self.is_mirror(o):
                continue  # its plane was adjusted above
            o.Placement = App.Placement(o.Placement.Base + moves[o.Name], o.Placement.Rotation)
        return list(dict.fromkeys(o.BodyId for o in members + hidden if getattr(o, "SSRole", "") == "body"))
