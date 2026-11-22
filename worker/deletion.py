"""T34: remove instances without destroying definitions read by surviving links and mirrors."""
from common import *


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
        return targets
