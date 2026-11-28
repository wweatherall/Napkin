"""Shared by every worker module: FreeCAD, units and tolerances, OpError, Frame, the wood cards.

Worker modules import the shared names they use explicitly (T50).
Entry points: material_card, Frame, vec, unit, add_props."""
import os
import re

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
JOURNAL_FORMAT = "napkin-journal/0.1"

# FreeCAD keeps 20 undo steps per document. Only its GUI applies the MaxUndoSize preference, and there is no
# Python call to change it, so in freecadcmd it stays 20 (checked on 1.1.3 and 1.1.4). Undoing further back
# rebuilds the document from the journal (Session.sync: "rebuilt"); the viewport shows the remembered state
# meanwhile, so you can keep undoing (T10).


class OpError(Exception):
    def __init__(self, message, about=()):
        super().__init__(message)
        self.about = tuple(about)


def vec(a):
    return V(float(a[0]), float(a[1]), float(a[2]))


def unit(v):
    if v.Length < 1e-12:
        raise OpError("zero-length vector")
    return V(v).normalize()


def rotation_from(x, y, z):
    return App.Rotation(x, y, z, "ZXY")


def board_label(bid):
    """Readable per-document Board numbers (I42); the random suffix is internal identity, never a name."""
    match = re.fullmatch(r"b([0-9]+)(?:_[0-9a-f]{32})?", bid)
    return f"Board {match[1]}" if match else bid


def add_props(obj, **props):
    """All Napkin properties are added when an object is created (adding them later
    inside an undo transaction is not reliably undone)."""
    kinds = {str: "App::PropertyString", bool: "App::PropertyBool", int: "App::PropertyInteger",
             float: "App::PropertyFloat", App.Vector: "App::PropertyVector"}
    for name, value in props.items():
        if name == "Tip":
            obj.addProperty("App::PropertyLinkChild", "Tip", "Napkin", "the feature that is this board's current solid")
            obj.Tip = value
            continue
        obj.addProperty(kinds[type(value)], name, "Napkin", "")
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
