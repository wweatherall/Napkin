"""Mirrored copies (Part::Mirroring) and mirror groups (A11b, T26)."""
from common import OpError, add_props, board_label, unit, vec


class MirrorActions:
    """Part of Model (model.py): works through self on the FreeCAD document."""

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
            m.Label = board_label(nid)
            add_props(m, BodyId=nid, SSRole="body", Replaced=replace,
                      SSHidden=bool(getattr(src, "SSHidden", False)) if replace else False)
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
