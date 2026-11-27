"""Session: one live document bound to one .FCStd file; sync, undo, journal, saving (A23, A24).

Owns `IdRegistry` (`accept`, `seed_native` from BodyId/RectId/SSOp/AssemblyId/SSLineId), display units (`set_units`,
`ShopSketchUnits` Meta), save generations (`save()`: `glb_dirty`, disables `CreateBackupFiles`, `Session.drawing`
one-shot flag never latched on open/reload, `<model>.saving.FCStd` -> `.prev.FCStd` -> atomic rename), recovery
(`recover_generation()`), and outside-save reload (`reload_outside()` with `validate_project` snapshot and
`<model>.floor.FCStd` via `_write_floor_copy`; `copy_outside_aside`, `aside_name`).
Entry points: sync, _apply, _open_existing, export, save, recover_generation, reload_outside, copy_outside_aside."""
import FreeCAD as App
from contextlib import contextmanager
from copy import copy, deepcopy
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET
import time
import materials as wood
from common import JOURNAL_FORMAT, OpError, unit
from export import (
    add_drawing_page,
    board_mesh_file,
    component_of,
    cuts_of,
    material_color,
    material_of,
    remove_drawing_pages,
    shape_key,
    write_glb,
)
from common import _MATERIALS
from export import _ENTRY_CACHE
from model import Model
from plane_fit import snapshot as stock_snapshot


def id_strings(value):
    """Conservative migration: legacy identifiers can be arbitrary strings, including map keys."""
    if isinstance(value, str):
        return {value} if value else set()
    if isinstance(value, dict):
        return set().union(set(value), *(id_strings(v) for v in value.values()))
    if isinstance(value, (list, tuple)):
        return set().union(*(id_strings(v) for v in value))
    return set()


def creations(op):
    """Stable ownership across typed amendments: payload changes do not create another entity."""
    oid = op.get("id", "")
    yield oid, "op:" + str(op.get("type", ""))
    if op.get("type") == "push_pull" and op.get("body"):
        yield op["body"], "body:" + oid
    for i, bid in enumerate(op.get("new_ids", [])):
        yield bid, f"body:{oid}:{i}"
    if op.get("type") == "make_assembly":
        yield op.get("new_id", ""), "assembly:" + oid
    if op.get("group"):
        yield op["group"], "group:" + oid
    for source, groups in op.get("groups", {}).items():
        for i, aid in enumerate(groups if isinstance(groups, list) else [groups]):
            yield aid, f"group:{oid}:{source}:{i}"


class IdRegistry:
    """Document-wide reservations, independent of the selected op path and FreeCAD's undo stack."""
    def __init__(self):
        self.reserved = set()
        self.owners = {}

    def accept(self, ops, reserved=(), legacy=False):
        owners = dict(self.owners)
        seen = set()
        for op in ops:
            for identity, owner in creations(op):
                if not identity:
                    continue
                # Historic fixtures/clients used serial IDs as mutable slots. Preserve their semantics;
                # all new allocations have 128 random bits and are checked strictly.
                modern = bool(re.fullmatch(r"[a-z]+[0-9]+_[0-9a-f]{32}", identity))
                if modern and not legacy:
                    if identity in seen or (identity in owners and owners[identity] != owner):
                        raise OpError(f"ID collision: {identity}")
                seen.add(identity)
                owners[identity] = owner
        self.owners = owners
        self.reserved.update(id_strings(ops))
        self.reserved.update(reserved)

    def seed_native(self, doc):
        for obj in doc.Objects:
            for prop in ("BodyId", "RectId", "SSOp", "AssemblyId", "SSLineId"):
                value = getattr(obj, prop, "")
                if value:
                    self.reserved.add(str(value))


_HIDDEN_IN_FREECAD = {"App::Origin", "App::Line", "App::Plane", "App::Point", "TechDraw::DrawPage"}


def write_gui_document(fcstd, previous=None):
    """Add the part of the file FreeCAD's window reads (GuiDocument.xml). freecadcmd never writes it, and without
    it FreeCAD opens the model with every object hidden. Each object shows as the model says (a board's current
    solid shown, its steps hidden); board axes and planes and the drawing page stay hidden. View settings FreeCAD
    saved in the previous file (colours, line widths, the camera) are kept."""
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


def generation(model_path):
    """The files of one model's save generations (A32): the current pair, the one being written, the one before,
    and the floor copy kept when FreeCAD edits the model (A38)."""
    base, ext = os.path.splitext(model_path)
    return {"file": model_path, "journal": base + ".shopsketch.json",
            "saving_file": base + ".saving" + ext, "saving_journal": base + ".shopsketch.saving.json",
            "prev_file": base + ".prev" + ext, "prev_journal": base + ".shopsketch.prev.json",
            "unmatched_file": base + ".unmatched" + ext, "unmatched_journal": base + ".shopsketch.unmatched.json",
            "floor_file": base + ".floor" + ext}


def upgrade_op(op):
    """Upgrade legacy fit ops saved before protocol 17 to top-level `fit` / `unfit` ops (T162)."""
    if not isinstance(op, dict) or op.get("type") != "property_edit":
        return op
    mode = op.get("mode")
    if mode not in ("plane_fit", "replace_fit"):
        return op
    upgraded = {k: v for k, v in op.items() if k != "mode"}
    upgraded["type"] = "fit" if mode == "plane_fit" else "unfit"
    return upgraded


def _upgrade_dropped(entry):
    if isinstance(entry, dict) and isinstance(entry.get("op"), dict):
        return {**entry, "op": upgrade_op(entry["op"])}
    return upgrade_op(entry)


def read_journal(path):
    try:
        with open(path) as f:
            j = json.load(f)
    except (OSError, ValueError):
        return None
    if not (isinstance(j, dict) and j.get("format") == JOURNAL_FORMAT and j.get("file_sha256")):
        return None
    if isinstance(j.get("ops"), list):
        j["ops"] = [upgrade_op(op) for op in j["ops"]]
    if isinstance(j.get("dropped"), list):
        j["dropped"] = [_upgrade_dropped(d) for d in j["dropped"]]
    return j


def file_rev(path):
    """The ShopSketchRev a .FCStd carries, read from its Document.xml without opening it (None if it has none)."""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("Document.xml").decode("utf-8", "replace")
    except (OSError, KeyError, zipfile.BadZipFile):
        return None
    m = re.search(r'<Item key="ShopSketchRev" value="(\d+)"', xml)
    return int(m.group(1)) if m else None


# Display units saved in doc.Meta["ShopSketchUnits"] (I57, I62): canonical "<format>:<rounding>" strings.
# Unrecognized or absent values read as None so opening never fails (I62).
UNIT_SPECS = {
    "ft-in:1/8", "ft-in:1/16", "ft-in:1/32", "ft-in:1/64",
    "in-frac:1/8", "in-frac:1/16", "in-frac:1/32", "in-frac:1/64",
    "in-dec:0.1", "in-dec:0.01", "in-dec:0.001",
    "m:0.1", "m:0.01", "m:0.001",
    "cm:1", "cm:0.1", "cm:0.01",
    "mm:1", "mm:0.1", "mm:0.01",
}


def parse_units(value):
    """Return the canonical units string if valid, else None (absent or unreadable never stops open, I62)."""
    return value if isinstance(value, str) and value in UNIT_SPECS else None


def keep_aside(path, aside, kept):
    """Move path out of the way to aside, unless a file with the same bytes is among kept (then it's no loss)."""
    if not os.path.exists(path):
        return
    h = sha256(path)
    if any(os.path.exists(k) and sha256(k) == h for k in kept):
        os.remove(path)
    else:
        os.replace(path, aside)


def copy_into_place(src, dst):
    tmp = dst + ".tmp"
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def link_or_copy(src, dst):
    """dst becomes the same bytes as src, atomically: a hard link (instant) where the disk allows, else a copy."""
    tmp = dst + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    try:
        os.link(src, tmp)
    except OSError:
        shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def validate_project(path):
    """FreeCAD may return an empty document on bad XML instead of raising."""
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("Document.xml"))
        if root.tag != "Document":
            raise OpError("Invalid project file: Document.xml has no Document root")
        bad_entry = archive.testzip()
        if bad_entry is not None:
            raise OpError(f"Invalid project file: damaged {bad_entry}")


def recover_generation(model_path):
    """Opening (A37): finish an identifiable interrupted save, preserving newer outside work.
    Only a missing or unreadable main file permits fallback to .prev. Displaced bytes are kept aside.
    Returns {"from", "rev", "why"} or None (an ordinary open, including outside edits).
    """
    def readable(path):
        try:
            validate_project(path)
            return True
        except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError, OpError):
            return False

    g = generation(model_path)
    have_file = os.path.exists(g["file"])
    main_readable = readable(g["file"])
    j = read_journal(g["journal"])
    if main_readable and j:
        main_hash = sha256(g["file"])
        if main_hash in (j["file_sha256"], j.get("outside_sha256")):
            return None                                 # our whole save, or a known outside edit
    files = [k for k in ("file", "saving_file", "prev_file") if readable(g[k])]
    journals = [(k, read_journal(g[k])) for k in ("journal", "saving_journal", "prev_journal")]
    hashes = {k: sha256(g[k]) for k in files}
    pairs = [(int(jj.get("rev", 0)), fk == "file", jk == "journal", fk, jk)
             for fk in files for jk, jj in journals if jj and jj["file_sha256"] == hashes[fk]]
    if main_readable:
        # Contents identify our interrupted save; dates only veto replacing newer work.
        next_rev = j and file_rev(g["file"]) == int(j.get("rev", -1)) + 1
        pairs = [pair for pair in pairs
                 if (pair[3] == "file" and pair[4] == "saving_journal")
                 or (next_rev and pair[3] == "saving_file" and pair[4] == "saving_journal"
                     and pair[0] == file_rev(g["file"])
                     and os.stat(g["saving_file"]).st_mtime_ns >= os.stat(g["file"]).st_mtime_ns)]
    if not pairs:
        return None
    rev, _, _, fk, jk = max(pairs)
    if not have_file:
        why = "the file was missing"
    elif not main_readable:
        why = "the file was unreadable"
    elif not j:
        why = "the journal was missing"
    else:
        why = f"the file (rev {file_rev(g['file'])}) and its journal (rev {j.get('rev')}) didn't match"
    if fk != "file":
        keep_aside(g["file"], g["unmatched_file"], [g["saving_file"], g["prev_file"]])
        copy_into_place(g[fk], g["file"])
    if jk != "journal":
        keep_aside(g["journal"], g["unmatched_journal"], [g["saving_journal"], g["prev_journal"]])
        copy_into_place(g[jk], g["journal"])
    new = fk.startswith("saving") or jk.startswith("saving") or (fk == "file" and jk == "journal")
    return {"from": "new" if new else "prev", "rev": rev,
            "why": why + ("; finished the save that stopped part way" if new else "; opened the save before it")}


def aside_name(model_path, when=None):
    """Where 'Keep Shop Sketch's' puts FreeCAD's save first (A36): <model>.freecad-<time>.FCStd, never an existing file."""
    base, ext = os.path.splitext(model_path)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(when))
    name, n = f"{base}.freecad-{stamp}{ext}", 2
    while os.path.exists(name):
        name, n = f"{base}.freecad-{stamp}-{n}{ext}", n + 1
    return name


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


@contextmanager
def no_backups():
    """Disable FreeCAD's .FCBak backups only for our own saves, restoring the user's setting (A41)."""
    prefs = App.ParamGet("User parameter:BaseApp/Preferences/Document")
    had = "CreateBackupFiles" in prefs.GetBools()
    prev = prefs.GetBool("CreateBackupFiles", True)
    prefs.SetBool("CreateBackupFiles", False)
    try:
        yield
    finally:
        if had:
            prefs.SetBool("CreateBackupFiles", prev)
        else:
            prefs.RemBool("CreateBackupFiles")


class Session:
    """One live document bound to one .FCStd file.

    applied: one entry per op the document has seen, in order: {op, key, status, message, changed, ms}.
    Each ok op is exactly one FreeCAD undo transaction; failed ops were aborted and left none.
    undo_floor: ops before this index can't be taken back with FreeCAD's undo (they came from the
    file); taking them back means rebuilding from the journal, which is only safe when nobody
    else has edited the file (external == False)."""

    def __init__(self, model_path, fresh=False, outside_reload=False):
        self.path = os.path.abspath(model_path) if model_path else None
        self.applied = []
        self.ids = IdRegistry()
        self.undo_floor = 0
        self.floor_copy = None     # {"sha256", "ops"} of <model>.floor.FCStd when the floor came from FreeCAD (A38)
        self.external = False
        self.rev = 0
        self.units = None          # saved display units (doc.Meta["ShopSketchUnits"], I57); kept across rebuilds
        self.dirty = False
        self.glb_dirty = True
        self.drawing = False
        self.session_base = 0
        self.doc = None
        self.file_sig = None
        self.file_sha = None       # the sha256 of the file as we last read or wrote it: an outside save differs (A36)
        self.rev_ops = {}          # rev -> the applied entries that revision of the file holds (what a reload keeps)
        self.dropped = []          # actions an outside save didn't have, taken out by a reload (A36; T65 offers them)
        self.recovered = None      # {"from", "rev", "why"}: opening fell back to the newest whole save (A32)
        if self.path and not fresh and not outside_reload:
            self.recovered = recover_generation(self.path)
        if self.path and os.path.exists(self.path) and not fresh:
            self._open_existing(outside_reload)
        else:
            self._new_doc()

    # ----- document lifecycle -----
    def _doc_label(self):
        return os.path.splitext(os.path.basename(self.path))[0] if self.path else "ShopSketch"

    def _new_doc(self):
        if self.doc is not None:
            App.closeDocument(self.doc.Name)
        self.doc = App.newDocument("ShopSketch")
        self.doc.Label = self._doc_label()
        self.doc.UndoMode = 1
        self.model = Model(self.doc)
        self.glb_dirty = True

    def _load_file(self, path=None):
        """Open the file as the live document (opening or rebuilding from the floor copy)."""
        self.doc, self.model, _ = self._open_document(path or self.path)
        if self.path:
            self.doc.Label = self._doc_label()

    @staticmethod
    def _open_document(path):
        doc = App.openDocument(path)
        try:
            doc.UndoMode = 1
            drawing = remove_drawing_pages(doc)
            doc.recompute()
            model = Model(doc)
            model.add_hidden_props()           # boards saved before hiding existed (T28)
        except Exception:
            App.closeDocument(doc.Name)
            raise
        return doc, model, drawing

    def _write_floor_copy(self, floor_path=None):
        """Write a floor snapshot atomically from the document at the floor (A38)."""
        floor_path = floor_path or generation(self.path)["floor_file"]
        base, ext = os.path.splitext(floor_path)
        tmp = base + ".tmp" + ext
        try:
            with no_backups():
                self.doc.saveCopy(tmp)
            digest = sha256(tmp)
            os.replace(tmp, floor_path)
        except Exception:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            raise
        self.floor_copy = {"sha256": digest, "ops": self.undo_floor}

    def _open_existing(self, outside_reload=False):
        if outside_reload:
            validate_project(self.path)
        self._load_file()
        file_meta_rev = int(self.doc.Meta.get("ShopSketchRev", "0") or 0)
        self.rev = file_meta_rev
        self.units = parse_units(self.doc.Meta.get("ShopSketchUnits"))
        self.file_sha = sha256(self.path)
        jp = journal_path(self.path)
        j = None
        if os.path.exists(jp):
            with open(jp) as f:
                j = json.load(f)
        if j and j.get("format") == JOURNAL_FORMAT:
            upgraded_ops = [upgrade_op(op) for op in j["ops"]]
            for op, st in zip(upgraded_ops, j["status"]):
                if st.get("status") == "ok":           # failed ops left nothing in the file
                    self.applied.append({"op": op, "key": canon(op), "id": op.get("id"), "type": op.get("type"), **st})
            journal_rev = int(j.get("rev", -1))
            self.external = not (journal_rev == file_meta_rev and j.get("file_sha256") == self.file_sha)
            if outside_reload and journal_rev > file_meta_rev:
                self.rev = journal_rev
                self.rev_ops[journal_rev] = self.applied
                self.applied = self._file_ops(self.path, file_meta_rev)
            self.dropped = [_upgrade_dropped(d) for d in j.get("dropped", [])]
            self.ids.owners.update(j.get("id_owners", {}))
            self.ids.accept(upgraded_ops + self.dropped, j.get("reserved_ids", []), legacy=True)
        else:
            self.external = True     # not written by Shop Sketch (stage 3 will adopt foreign solids)
        self.ids.seed_native(self.doc)
        # undo stops at a FreeCAD change: one since the journal, or one a reload took in earlier (the journal's floor)
        floor = min(int((j or {}).get("floor", 0) or 0), len(self.applied))
        self.undo_floor = len(self.applied) if self.external else floor
        self.session_base = len(self.applied)
        self.rev_ops[file_meta_rev] = list(self.applied)
        self.doc.clearUndos()
        if self.external and not outside_reload:
            self._write_floor_copy()
        else:
            fc = (j or {}).get("floor_copy")
            self.floor_copy = dict(fc) if isinstance(fc, dict) else None
        self.file_sig = self.disk_sig()
        self.glb_dirty = True

    def disk_sig(self):
        try:
            st = os.stat(self.path)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def changed_on_disk(self):
        """True when someone else wrote the file since we last read or saved it (an open reloads it)."""
        return self.path is not None and self.file_sig is not None and self.disk_sig() != self.file_sig

    # ----- outside saves (A36, T64) -----
    def outside_sig(self):
        """The file's (mtime, size) when it isn't what we last read or wrote, else None (a cheap stat)."""
        sig = self.disk_sig() if self.path and self.file_sig is not None else None
        return sig if sig is not None and sig != self.file_sig else None

    def same_bytes(self, sig):
        """The file was touched but holds the bytes we last read or wrote (a copy back, a touch): not an outside
        save. Then sig is ours from now on."""
        if self.file_sha is not None and sha256(self.path) == self.file_sha:
            self.file_sig = sig
            return True
        return False

    def mark_outside(self):
        """Note FreeCAD's save in the journal at once (A36), so if the worker stops before the reload, opening the
        file doesn't take it for a save of ours that stopped part way (recover_generation)."""
        jp = journal_path(self.path)
        try:
            with open(jp) as f:
                j = json.load(f)
            j["outside_sha256"] = sha256(self.path)
            atomic_json(jp, j)
        except (OSError, ValueError):
            pass

    def copy_outside_aside(self):
        """'Keep Shop Sketch's' (A36): FreeCAD's file is copied to <model>.freecad-<time>.FCStd before ours goes
        over it. Returns the copy's path."""
        aside = aside_name(self.path)
        shutil.copy2(self.path, aside)
        return aside

    def board_marks(self):
        """What each board looks like, to tell which boards a reload changed: its box, volume, area, wood, hidden."""
        m = self.model
        out = {}
        for bid, obj in m.bodies().items():
            ws = m.world_shape(obj)
            bb = ws.BoundBox
            out[bid] = (tuple(round(v, 3) for v in (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)),
                        round(ws.Volume, 1), round(ws.Area, 1), material_of(m, obj),
                        bool(getattr(obj, "SSHidden", False)))
        return out

    def _file_ops(self, path, frev):
        """Read the ops from the file itself, then try the session's history and the previous journal."""
        if frev is not None:
            try:
                with zipfile.ZipFile(path) as archive:
                    root = ET.fromstring(archive.read("Document.xml"))
                meta = {item.get("key"): item.get("value")
                        for item in root.findall("./Properties/Property[@name='Meta']/Map/Item")}
                if int(meta["ShopSketchRev"]) == frev:
                    ops = json.loads(meta["ShopSketchOps"])
                    if isinstance(ops, list) and all(
                            isinstance(op, dict) and isinstance(op.get("type"), str) and op["type"]
                            and (op.get("id") is None or isinstance(op["id"], str)) for op in ops):
                        ops = [upgrade_op(op) for op in ops]
                        return [{"op": op, "key": canon(op), "id": op.get("id"), "type": op["type"], "status": "ok"}
                                for op in ops]
            except (OSError, zipfile.BadZipFile, ET.ParseError, KeyError, TypeError, ValueError,
                    OverflowError, RecursionError):
                pass  # Old or damaged metadata leaves the historical fallbacks available.
        if frev in self.rev_ops:
            return list(self.rev_ops[frev])
        pj = read_journal(generation(self.path)["prev_journal"])
        if frev is not None and pj and int(pj.get("rev", -1)) == frev:
            return [{"op": o, "key": canon(o), "id": o.get("id"), "type": o.get("type"), **st}
                    for o, st in zip(pj["ops"], pj["status"]) if st.get("status") == "ok"]
        return []

    @staticmethod
    def _exported_boards(outdir):
        """The last boards the window saw, for a retry after the worker holding them stopped."""
        try:
            with open(os.path.join(outdir, "bodies.json")) as f:
                return {b["id"]: b for b in json.load(f)}
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def reload_outside(self, outdir=None, resumed=False):
        """FreeCAD saved the file (A36): it becomes the live document. Actions the file doesn't hold (made since
        the revision FreeCAD opened) leave the list and are kept in the journal as dropped (T65); undo stops at the
        FreeCAD change, in this session and the next (the journal's floor). Returns {changed, removed, dropped}."""
        before = self.board_marks()
        last_export = self._exported_boards(outdir) if resumed and outdir else None
        sig = self.disk_sig()
        folder = os.path.dirname(self.path)
        files = generation(self.path)
        with tempfile.TemporaryDirectory(dir=folder, prefix=".shopsketch-reload-") as stage:
            # FreeCAD returns the live document for the same path; load a sibling snapshot instead.
            with tempfile.NamedTemporaryFile(dir=folder, prefix=".shopsketch-reload-", suffix=".FCStd") as snapshot:
                shutil.copyfile(self.path, snapshot.name)
                validate_project(snapshot.name)
                digest = sha256(snapshot.name)
                frev = file_rev(snapshot.name)
                kept = self._file_ops(snapshot.name, frev)
                doc, model, _ = self._open_document(snapshot.name)
            try:
                staged = copy(self)
                staged.doc, staged.model = doc, model
                doc.FileName = self.path
                doc.Label = os.path.splitext(os.path.basename(self.path))[0]
                staged.glb_dirty = True
                staged.ids = deepcopy(self.ids)
                staged.ids.seed_native(doc)
                file_meta_rev = int(doc.Meta.get("ShopSketchRev", "0") or 0)
                kept_keys = {e["key"] for e in kept}
                prior_ops = self.applied
                if self.rev > int(self.doc.Meta.get("ShopSketchRev", "0") or 0) and self.rev in self.rev_ops:
                    prior_ops = self.rev_ops[self.rev]
                when = time.strftime("%Y-%m-%dT%H:%M:%S")
                gone = [{"op": e["op"], "after_rev": frev, "at": when} for e in prior_ops
                        if e["status"] == "ok" and e["key"] not in kept_keys]
                staged.applied = kept
                staged.undo_floor = staged.session_base = len(kept)
                staged.external = staged.dirty = False
                staged.dropped = self.dropped + gone
                staged.rev = max(self.rev, file_meta_rev)
                staged.units = parse_units(doc.Meta.get("ShopSketchUnits"))
                staged.file_sha = digest
                staged.file_sig = sig
                staged.rev_ops = {file_meta_rev: list(kept)}
                doc.clearUndos()
                staged.model.show_as_hidden()
                after = staged.board_marks()

                floor = os.path.join(stage, "floor.FCStd")
                journal = os.path.join(stage, "journal.json")
                staged._write_floor_copy(floor)
                atomic_json(journal, staged._journal(file_meta_rev, digest))

                # Publish both recovery files before exposing the replacement boards.
                published = []
                try:
                    for candidate, destination in ((floor, files["floor_file"]), (journal, files["journal"])):
                        previous = None
                        if os.path.isfile(destination):
                            previous = candidate + ".previous"
                            link_or_copy(destination, previous)
                        os.replace(candidate, destination)
                        published.append((destination, previous))
                    if outdir:
                        staged.export(outdir)
                        if last_export is not None:
                            current_export = self._exported_boards(outdir)
                            if current_export is not None:
                                before, after = last_export, current_export
                except Exception:
                    for destination, previous in reversed(published):
                        if previous is None:
                            os.remove(destination)
                        else:
                            os.replace(previous, destination)
                    raise
            except Exception:
                App.closeDocument(doc.Name)
                if self.doc is not None:
                    App.setActiveDocument(self.doc.Name)
                raise
            if self.doc is not None:
                App.closeDocument(self.doc.Name)
            self.__dict__.update(vars(staged))
        return {"changed": sorted(b for b in after if before.get(b) != after[b]),
                "removed": sorted(b for b in before if b not in after),
                "dropped": [d["op"] for d in gone]}     # no "rev": the reply's is the session's (open_reply)

    def _journal(self, rev, file_sha):
        j = {"format": JOURNAL_FORMAT, "rev": rev, "file_sha256": file_sha,
             "model": os.path.basename(self.path), "name": os.path.splitext(os.path.basename(self.path))[0],
             "ops": [e["op"] for e in self.applied],
             "status": [{k: e[k] for k in ("status", "changed", "message", "ms") if k in e} for e in self.applied],
             "floor": self.undo_floor, "dropped": self.dropped,
             "reserved_ids": sorted(self.ids.reserved), "id_owners": self.ids.owners}
        if self.floor_copy is not None:
            j["floor_copy"] = dict(self.floor_copy)
        return j

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
        if self.undo_floor == 0:
            self._new_doc()
            self.applied = []
            self.session_base = 0
            self.undo_floor = 0
            for op in ops:
                self._apply(op)
            return
        floor_path = generation(self.path)["floor_file"] if self.path else None
        fc = self.floor_copy
        try:
            floor_sha = sha256(floor_path) if floor_path and os.path.exists(floor_path) else None
        except OSError:
            floor_sha = None
        if not (isinstance(fc, dict) and floor_sha is not None
                and fc.get("ops") == self.undo_floor and fc.get("sha256") == floor_sha):
            raise OpError("can't undo past the FreeCAD edit: its copy is missing")
        if self.doc is not None:
            App.closeDocument(self.doc.Name)
            self.doc = None
        self._load_file(floor_path)
        self.doc.clearUndos()
        self.applied = list(self.applied[:self.undo_floor])
        self.session_base = self.undo_floor
        for op in ops[self.undo_floor:]:
            self._apply(op)

    def sync(self, ops, reserved_ids=()):
        """Make the document match `ops`: keep the common prefix, take back the rest with FreeCAD's
        undo, apply the new ops as transactions. Returns how it got there."""
        t0 = time.perf_counter()
        old_reserved = len(self.ids.reserved)
        self.ids.accept(ops, reserved_ids)
        if len(self.ids.reserved) != old_reserved:
            self.dirty = True
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
        if how == "nothing" and len(self.ids.reserved) != old_reserved:
            how = "reserved IDs"
        if how != "nothing":
            self.dirty = True
            if how != "reserved IDs":
                self.glb_dirty = True
            self.model.show_as_hidden()         # FreeCAD's undo doesn't take Visibility back (T28)
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
            bodies.append(dict(hit[1], stock_frame=stock_snapshot(obj), mesh=board_mesh_file(bid, obj, m, outdir),
                               color=list(material_color(mat)), family=m.definition(obj).Name,
                               array=getattr(obj, "SSArray", "") or "",
                               assembly=getattr(m.assembly_of(obj), "AssemblyId", "") if m.assembly_of(obj) else "",
                               row=(m.arrays_of(obj)[0].SSSource if m.arrays_of(obj) else ""),
                               hidden=bool(getattr(obj, "SSHidden", False)),
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

    def set_units(self, units):
        """Set the model's display units (I57): not an op (undo leaves it), saved in Meta on the next save."""
        parsed = parse_units(units)
        if parsed is None:
            raise OpError(f"unknown units '{units}'")
        missing_on_disk = bool(self.path) and not os.path.exists(self.path)
        meta_matches = self.doc is not None and self.doc.Meta.get("ShopSketchUnits") == parsed
        changed = parsed != self.units or not meta_matches or missing_on_disk
        self.units = parsed
        if changed:
            self.dirty = True
        return changed

    def save(self, outdir=None):
        """Atomic autosave: write a copy beside the file, then swap it in. With a drawing wanted, generate
        views.json from a throwaway in-memory copy without saving a TechDraw page into model.FCStd (I68)."""
        if not self.path:
            return None
        t0 = time.perf_counter()
        if outdir:
            glb_path = os.path.join(outdir, "model.glb")
            if self.glb_dirty or not os.path.exists(glb_path):
                write_glb(self.model, glb_path)     # the whole model, for renders (A07)
                self.glb_dirty = False
        saved_ops = [e for e in self.applied if e["status"] == "ok"]
        meta = self.doc.Meta
        prev_meta = dict(meta)
        meta["ShopSketchOps"] = json.dumps([e["op"] for e in saved_ops], separators=(",", ":"))
        self.rev += 1
        meta["ShopSketchRev"] = str(self.rev)
        if self.units is not None:
            meta["ShopSketchUnits"] = self.units
        self.doc.Meta = meta
        g = generation(self.path)
        try:
            self._write(g, outdir)
        except Exception:
            self.rev -= 1           # a failed save leaves the revision where it was: the retry saves this one (T79)
            self.doc.Meta = prev_meta
            for k in ("saving_file", "saving_journal"):
                try:
                    os.remove(g[k])
                except OSError:
                    pass
            raise
        self.dirty = False
        if self.drawing and outdir:
            self.drawing = False
        self.file_sig = self.disk_sig()
        self.rev_ops[self.rev] = saved_ops
        for old in sorted(self.rev_ops)[:-50]:        # the last 50 revisions are plenty for FreeCAD's open copy
            del self.rev_ops[old]
        self.external = False   # the file is exactly our journal again; the undo floor stays (the journal keeps it)
        return round((time.perf_counter() - t0) * 1000, 1)

    def _write(self, g, outdir):
        """save()'s writing, one generation (A32): the new file and its journal under the .saving names; the current
        pair kept as .prev; then the new pair renamed into place. A whole pair is on disk at every step (opening
        finds it: recover_generation). Raises if any of it fails."""
        tmp = g["saving_file"]
        folder = os.path.dirname(self.path)
        os.makedirs(folder, exist_ok=True)
        if not os.access(folder, os.W_OK):          # FreeCAD would only say "Failed to open file" (T79)
            raise PermissionError(f"the folder {os.path.basename(folder) or folder} is read-only")
        self.doc.Label = self._doc_label()
        with no_backups():
            self.doc.saveCopy(tmp)
        if self.drawing and outdir:
            d2 = App.openDocument(tmp)
            try:
                objs = [o for o in d2.Objects if getattr(o, "SSRole", None) == "body"]
                _, views = add_drawing_page(d2, objs)
                import TechDraw
                atomic_json(os.path.join(outdir, "views.json"),
                            {name: TechDraw.viewPartAsSvg(v) for name, v in views.items()})
            finally:
                App.closeDocument(d2.Name)
                if self.doc is not None:
                    App.setActiveDocument(self.doc.Name)
        write_gui_document(tmp, self.path)          # what FreeCAD's window shows (T29)
        new_sha = sha256(tmp)
        atomic_json(g["saving_journal"], self._journal(self.rev, new_sha))
        if os.path.exists(g["file"]) and os.path.exists(g["journal"]):
            link_or_copy(g["journal"], g["prev_journal"])
            link_or_copy(g["file"], g["prev_file"])
        os.replace(tmp, g["file"])
        self.file_sha = new_sha
        os.replace(g["saving_journal"], g["journal"])

    def close(self):
        if self.doc is not None:
            App.closeDocument(self.doc.Name)
            self.doc = None
