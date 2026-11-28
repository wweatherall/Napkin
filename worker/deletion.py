"""T34, I46: Delete. A board leaves the FreeCAD file with everything only it used, unless a surviving link, mirror or
array still builds from it: then it stays, hidden (SSRole 'deleted'), until that goes too.

Auto-discovered `DeleteActions`: `remove_unneeded` removes dependencies before dependents so FreeCAD undo keeps
expression links. `Model.bodies()` excludes `SSRole=deleted` from picking metadata, GLB, drawings and cut lists.
For a deleted row source, a surviving member is detached as the new original and holders update `SSSource`."""


CONTRACT = {
    "type": "delete",
    "fields": {
        "targets": {"required": True, "kind": "[string]"},
    },
    "refers_to": ["targets"],
    "creates": ["id"],
    "tool": "viewport/selection.gd",
}


class DeleteActions:
    def op_delete(self, op):
        targets = list(dict.fromkeys(op["targets"]))
        objects = [self.body(t) for t in targets]  # validate before changing anything
        for obj in objects:
            # A row's original is an instance too. Promote a surviving member, leaving the
            # row's origin and indices untouched so spacing, expressions and positions survive.
            arrays = [a for a in self.doc.Objects
                      if getattr(a, "SSRole", "") == "array" and a.SSSource == obj.BodyId]
            if arrays:
                names = {a.Name for a in arrays}
                survivors = sorted((o for b, o in self.bodies().items()
                                    if b not in targets and getattr(o, "SSArray", "") in names),
                                   key=lambda o: (o.SSArrayIndex, o.BodyId))
                if survivors:
                    heir = survivors[0]
                    self.op_detach({"targets": [heir.BodyId]})
                    for arr in arrays:
                        arr.SSSource = heir.BodyId
            dfn = self.definition(obj)
            if dfn is not obj and getattr(dfn, "BodyId", "") == obj.BodyId:
                survivors = sorted((o for b, o in self.bodies().items()
                                    if b not in targets and self.definition(o) is dfn), key=lambda o: o.BodyId)
                if survivors:
                    dfn.BodyId = survivors[0].BodyId
            for group in list(obj.InList):
                if getattr(group, "SSRole", "") == "assembly":
                    group.removeObject(obj)
            obj.SSRole = "deleted"
        self.remove_unneeded()
        return targets

    def remove_unneeded(self):
        """Take every deleted board nothing else needs out of the document, with the objects only it used
        (features, a component's definition, a mirror's placed input, an array whose members are all gone)."""
        doomed = set()
        frontier = [o for o in self.doc.Objects if getattr(o, "SSRole", "") == "deleted"]
        while frontier:                                   # grow to a fixed point: removing one can free another
            grew = False
            for o in list(frontier):
                if o.Name in doomed or not self._free(o, doomed):
                    continue
                doomed.add(o.Name)
                grew = True
                frontier += [c for c in o.OutList if c.Name not in doomed and self._removable(c)]
            if not grew:
                break
        # What others depend on goes first, its dependents after. The other way round, FreeCAD 1.1.4's undo brings
        # the objects back but not their expression links (a through-hole would stop following its board, I24).
        while doomed:
            doomed = {n for n in doomed if self.doc.getObject(n) is not None}   # a Part takes its Origin with it
            if not doomed:
                break
            ready = [n for n in doomed if not any(d.Name in doomed for d in self.doc.getObject(n).OutList if d.Name != n)]
            for n in ready or list(doomed):
                self.doc.removeObject(n)
                doomed.discard(n)

    @staticmethod
    def _removable(o):
        """Living boards and assemblies (and the document's folders) are never removed with something else."""
        return o.TypeId != "App::DocumentObjectGroup" and getattr(o, "SSRole", "") not in ("body", "assembly")

    @staticmethod
    def _free(o, doomed):
        """Nothing outside what's being removed uses `o` (folders don't count: they only list it)."""
        return all(d.Name in doomed or d is o or d.TypeId == "App::DocumentObjectGroup" for d in o.InList)
