"""Session: one live document bound to one .FCStd file; sync, undo, journal, saving (A23, A42).

Owns `IdRegistry` (`accept`, `seed_native` from BodyId/RectId/SSOp/AssemblyId/SSLineId), display units (`set_units`,
`NapkinUnits` Meta), atomic single-file saves (`save()`: `glb_dirty`, disables `CreateBackupFiles`, `Session.drawing`
one-shot flag never latched on open/reload, `<model>.saving.FCStd` -> atomic rename, `NapkinJournal` and
`NapkinContentSha256` in Meta, `NapkinFloor.FCStd` inside the zip), and outside-save reload (`reload_outside()`
with `validate_project` snapshot; `copy_outside_aside`, `aside_name`).
Entry points: sync, _apply, _open_existing, export, save, reload_outside, copy_outside_aside."""
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
    if op.get("type") == "new_board" and op.get("body"):
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


def _build_gui_document(doc_xml_bytes, previous=None):
    """Build GuiDocument.xml bytes so FreeCAD's window shows each object as the model says (T29)."""
    doc = ET.fromstring(doc_xml_bytes)
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
    return b"<?xml version='1.0' encoding='utf-8'?>\n" + ET.tostring(out)


def write_gui_document(fcstd, previous=None):
    """Add GuiDocument.xml to an .FCStd archive if absent."""
    with zipfile.ZipFile(fcstd) as z:
        if "GuiDocument.xml" in z.namelist():
            return
        doc_bytes = z.read("Document.xml")
    gui_bytes = _build_gui_document(doc_bytes, previous)
    with zipfile.ZipFile(fcstd, "a", zipfile.ZIP_DEFLATED) as z:
        z.writestr("GuiDocument.xml", gui_bytes)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _strip_content_sha_from_xml(doc_xml_bytes):
    root = ET.fromstring(doc_xml_bytes)
    meta_map = root.find("./Properties/Property[@name='Meta']/Map")
    if meta_map is not None:
        for item in list(meta_map.findall("Item")):
            if item.get("key") == "NapkinContentSha256":
                meta_map.remove(item)
        meta_map.set("count", str(len(meta_map.findall("Item"))))
    return ET.canonicalize(ET.tostring(root, encoding="unicode")).encode("utf-8")


def content_sha256(fcstd_path):
    """Hash of the .FCStd zip's contents excluding GuiDocument.xml, NapkinFloor.FCStd, and NapkinContentSha256."""
    h = hashlib.sha256()
    with zipfile.ZipFile(fcstd_path, "r") as z:
        for name in sorted(z.namelist()):
            if name in ("GuiDocument.xml", "NapkinFloor.FCStd"):
                continue
            data = z.read(name)
            if name == "Document.xml":
                data = _strip_content_sha_from_xml(data)
            h.update(name.encode("utf-8") + b"\0" + str(len(data)).encode("ascii") + b"\0" + data)
    return h.hexdigest()


def finalize_fcstd(fcstd_path, previous=None, floor_bytes=None):
    """Inject NapkinContentSha256, GuiDocument.xml, and optional NapkinFloor.FCStd into a saved .FCStd."""
    csha = content_sha256(fcstd_path)
    tmp_zip = fcstd_path + ".zip"
    try:
        with zipfile.ZipFile(fcstd_path, "r") as zin, zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as zout:
            names = zin.namelist()
            doc_bytes = zin.read("Document.xml")
            root = ET.fromstring(doc_bytes)
            meta_map = root.find("./Properties/Property[@name='Meta']/Map")
            if meta_map is not None:
                for item in list(meta_map.findall("Item")):
                    if item.get("key") == "NapkinContentSha256":
                        meta_map.remove(item)
                ET.SubElement(meta_map, "Item", key="NapkinContentSha256", value=csha)
                meta_map.set("count", str(len(meta_map.findall("Item"))))
            new_doc_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            zout.writestr("Document.xml", new_doc_bytes)
            for item in zin.infolist():
                if item.filename in ("Document.xml", "NapkinFloor.FCStd"):
                    continue
                zout.writestr(item, zin.read(item.filename))
            if "GuiDocument.xml" not in names:
                zout.writestr("GuiDocument.xml", _build_gui_document(new_doc_bytes, previous))
            if floor_bytes is not None:
                zout.writestr("NapkinFloor.FCStd", floor_bytes)
        os.replace(tmp_zip, fcstd_path)
    except Exception:
        if os.path.exists(tmp_zip):
            try:
                os.remove(tmp_zip)
            except OSError:
                pass
        raise


def atomic_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def saving_path(model_path):
    base, ext = os.path.splitext(model_path)
    return base + ".saving" + ext


def legacy_sidecars(model_path):
    """Sidecar files from the pre-A42 file-and-journal layout (removed after the first save, except .unmatched)."""
    base, ext = os.path.splitext(model_path)
    return {
        "journal": base + ".napkin.json",
        "saving_journal": base + ".napkin.saving.json",
        "prev_file": base + ".prev" + ext,
        "prev_journal": base + ".napkin.prev.json",
        "floor_file": base + ".floor" + ext,
    }


def _remove_legacy_sidecars(model_path):
    for p in legacy_sidecars(model_path).values():
        try:
            os.remove(p)
        except OSError:
            pass


OLD_FILE_MSG = "This file was saved by an older Napkin: run tools/UPDATE_OLD_FILES.py on it"


def is_legacy_op(op):
    """True when op uses a pre-split shape that must be rewritten by tools/UPDATE_OLD_FILES.py."""
    if not isinstance(op, dict):
        return False
    t = op.get("type")
    if t == "property_edit" and op.get("mode") in ("plane_fit", "replace_fit"):
        return True
    if t == "push_pull" and (op.get("body") or op.get("edge_fit")):
        return True
    return False


def _dropped_op(entry):
    return entry["op"] if isinstance(entry, dict) and isinstance(entry.get("op"), dict) else entry


def _check_no_legacy_ops(ops, dropped=()):
    if any(is_legacy_op(op) for op in ops) or any(is_legacy_op(_dropped_op(d)) for d in dropped):
        raise OpError(OLD_FILE_MSG)


def _validate_journal_dict(j, require_sha=False):
    if not isinstance(j, dict) or j.get("format") != JOURNAL_FORMAT:
        return None
    if require_sha and not j.get("file_sha256"):
        return None
    return j


def read_journal(path):
    """Read the journal from a .FCStd's NapkinJournal Meta, or from a legacy .napkin.json file."""
    if path.lower().endswith(".fcstd"):
        try:
            with zipfile.ZipFile(path) as z:
                root = ET.fromstring(z.read("Document.xml"))
            meta = {item.get("key"): item.get("value")
                    for item in root.findall("./Properties/Property[@name='Meta']/Map/Item")}
            raw = meta.get("NapkinJournal")
            if not raw:
                return None
            return _validate_journal_dict(json.loads(raw), require_sha=False)
        except (OSError, KeyError, ValueError, zipfile.BadZipFile, ET.ParseError):
            return None
    try:
        with open(path) as f:
            j = json.load(f)
    except (OSError, ValueError):
        return None
    return _validate_journal_dict(j, require_sha=True)


def write_meta_journal(fcstd_path, j, update_sha=True):
    """Update NapkinJournal (and optionally NapkinContentSha256) in a .FCStd's Document.xml Meta."""
    floor_bytes = None
    tmp_zip = fcstd_path + ".meta.tmp"
    with zipfile.ZipFile(fcstd_path, "r") as zin, zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as zout:
        if "NapkinFloor.FCStd" in zin.namelist():
            floor_bytes = zin.read("NapkinFloor.FCStd")
        root = ET.fromstring(zin.read("Document.xml"))
        meta_map = root.find("./Properties/Property[@name='Meta']/Map")
        for item in list(meta_map.findall("Item")):
            if item.get("key") == "NapkinJournal":
                meta_map.remove(item)
        ET.SubElement(meta_map, "Item", key="NapkinJournal", value=json.dumps(j, separators=(",", ":")))
        meta_map.set("count", str(len(meta_map.findall("Item"))))
        new_doc_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        zout.writestr("Document.xml", new_doc_bytes)
        for item in zin.infolist():
            if item.filename == "Document.xml":
                continue
            zout.writestr(item, zin.read(item.filename))
    os.replace(tmp_zip, fcstd_path)
    if update_sha:
        finalize_fcstd(fcstd_path, floor_bytes=floor_bytes)


def file_rev(path):
    """The NapkinRev a .FCStd carries, read from its Document.xml without opening it (None if it has none)."""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("Document.xml").decode("utf-8", "replace")
    except (OSError, KeyError, zipfile.BadZipFile):
        return None
    m = re.search(r'<Item key="NapkinRev" value="(\d+)"', xml)
    return int(m.group(1)) if m else None


# Display units saved in doc.Meta["NapkinUnits"] (I57, I62): canonical "<format>:<rounding>" strings.
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


def validate_project(path):
    """FreeCAD may return an empty document on bad XML instead of raising."""
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("Document.xml"))
        if root.tag != "Document":
            raise OpError("Invalid project file: Document.xml has no Document root")
        bad_entry = archive.testzip()
        if bad_entry is not None:
            raise OpError(f"Invalid project file: damaged {bad_entry}")


def aside_name(model_path, when=None):
    """Where 'Keep Napkin's' puts FreeCAD's save first (A36): <model>.freecad-<time>.FCStd, never an existing file."""
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
        self.floor_copy = None     # {"sha256", "ops"} of NapkinFloor.FCStd when the floor came from FreeCAD (A38)
        self._floor_bytes = None   # bytes of the floor snapshot, embedded in .FCStd on save (A42)
        self.external = False
        self.rev = 0
        self.units = None          # saved display units (doc.Meta["NapkinUnits"], I57); kept across rebuilds
        self.dirty = False
        self.glb_dirty = True
        self.drawing = False
        self.session_base = 0
        self.doc = None
        self.file_sig = None
        self.file_sha = None       # the sha256 of the file as we last read or wrote it: an outside save differs (A36)
        self.rev_ops = {}          # rev -> the applied entries that revision of the file holds (what a reload keeps)
        self.dropped = []          # actions an outside save didn't have, taken out by a reload (A36; T65 offers them)
        self.recovered = None      # kept for open_reply compatibility; single-file saves are atomic
        if self.path and not fresh and not outside_reload:
            sp = saving_path(self.path)
            if os.path.exists(sp):
                try:
                    os.remove(sp)
                except OSError:
                    pass
        if self.path and os.path.exists(self.path) and not fresh:
            self._open_existing(outside_reload)
        else:
            self._new_doc()

    # ----- document lifecycle -----
    def _doc_label(self):
        return os.path.splitext(os.path.basename(self.path))[0] if self.path else "Napkin"

    def _new_doc(self):
        if self.doc is not None:
            App.closeDocument(self.doc.Name)
        self.doc = App.newDocument("Napkin")
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

    def _capture_floor_bytes(self):
        """Capture a floor snapshot in memory from the live document at the floor (A38, A42)."""
        with tempfile.TemporaryDirectory(prefix="napkin-floor-") as td:
            tmp = os.path.join(td, "floor.FCStd")
            with no_backups():
                self.doc.saveCopy(tmp)
            with open(tmp, "rb") as f:
                data = f.read()
        self._floor_bytes = data
        self.floor_copy = {"sha256": sha256_bytes(data), "ops": self.undo_floor}

    def _open_existing(self, outside_reload=False):
        if outside_reload:
            validate_project(self.path)
        self._load_file()
        from update_old_files import META_KEY_RENAMES, OLD_SIDECAR_SUFFIX
        base = os.path.splitext(self.path)[0]
        if any(k in self.doc.Meta for k in META_KEY_RENAMES) or os.path.exists(base + OLD_SIDECAR_SUFFIX):
            self.close()
            raise OpError(OLD_FILE_MSG)
        file_meta_rev = int(self.doc.Meta.get("NapkinRev", "0") or 0)
        self.rev = file_meta_rev
        self.units = parse_units(self.doc.Meta.get("NapkinUnits"))
        self.file_sha = sha256(self.path)
        sidecars = legacy_sidecars(self.path)
        legacy_jp = sidecars["journal"]
        using_legacy = os.path.exists(legacy_jp)
        j = None
        if using_legacy:
            try:
                with open(legacy_jp) as f:
                    raw_j = json.load(f)
                if isinstance(raw_j, dict) and raw_j.get("format") == JOURNAL_FORMAT:
                    j = _validate_journal_dict(raw_j, require_sha=False)
            except (OSError, ValueError):
                j = None
            if j:
                journal_rev = int(j.get("rev", -1))
                self.external = not (journal_rev == file_meta_rev and j.get("file_sha256") == self.file_sha)
            else:
                self.external = True
        else:
            raw_meta_j = self.doc.Meta.get("NapkinJournal")
            if raw_meta_j:
                try:
                    j = _validate_journal_dict(json.loads(raw_meta_j), require_sha=False)
                except ValueError:
                    j = None
            csha = self.doc.Meta.get("NapkinContentSha256")
            content_ok = bool(csha and csha == content_sha256(self.path))
            if j:
                journal_rev = int(j.get("rev", -1))
                self.external = not (content_ok and journal_rev == file_meta_rev)
            else:
                self.external = True     # not written by Napkin (stage 3 will adopt foreign solids)
        try:
            raw_meta_ops = self.doc.Meta.get("NapkinOps")
            if raw_meta_ops:
                try:
                    parsed_meta_ops = json.loads(raw_meta_ops)
                except ValueError:
                    parsed_meta_ops = None
                if isinstance(parsed_meta_ops, list):
                    _check_no_legacy_ops(parsed_meta_ops)
            if j:
                upgraded_ops = list(j.get("ops", []))
                _check_no_legacy_ops(upgraded_ops, j.get("dropped", []))
        except OpError:
            self.close()
            raise
        if j:
            for op, st in zip(upgraded_ops, j.get("status", [])):
                if st.get("status") == "ok":           # failed ops left nothing in the file
                    self.applied.append({"op": op, "key": canon(op), "id": op.get("id"), "type": op.get("type"), **st})
            if outside_reload and int(j.get("rev", -1)) > file_meta_rev:
                self.rev = int(j["rev"])
                self.rev_ops[self.rev] = self.applied
                self.applied = self._file_ops(self.path, file_meta_rev)
            self.dropped = list(j.get("dropped", []))
            self.ids.owners.update(j.get("id_owners", {}))
            self.ids.accept(upgraded_ops + self.dropped, j.get("reserved_ids", []), legacy=True)
        self.ids.seed_native(self.doc)
        # undo stops at a FreeCAD change: one since the journal, or one a reload took in earlier (the journal's floor)
        floor = min(int((j or {}).get("floor", 0) or 0), len(self.applied))
        self.undo_floor = len(self.applied) if self.external else floor
        self.session_base = len(self.applied)
        self.rev_ops[file_meta_rev] = list(self.applied)
        self.doc.clearUndos()
        if self.external and not outside_reload:
            self._capture_floor_bytes()
        else:
            fc = (j or {}).get("floor_copy")
            self.floor_copy = dict(fc) if isinstance(fc, dict) else None
            self._floor_bytes = None
            if isinstance(self.floor_copy, dict) and not self.external:
                want_sha = self.floor_copy.get("sha256")
                if using_legacy:
                    fp = sidecars["floor_file"]
                    if os.path.exists(fp):
                        try:
                            with open(fp, "rb") as f:
                                data = f.read()
                            if sha256_bytes(data) == want_sha:
                                self._floor_bytes = data
                        except OSError:
                            pass
                else:
                    try:
                        with zipfile.ZipFile(self.path, "r") as z:
                            if "NapkinFloor.FCStd" in z.namelist():
                                data = z.read("NapkinFloor.FCStd")
                                if sha256_bytes(data) == want_sha:
                                    self._floor_bytes = data
                    except (OSError, zipfile.BadZipFile):
                        pass
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

    def copy_outside_aside(self):
        """'Keep Napkin's' (A36): FreeCAD's file is copied to <model>.freecad-<time>.FCStd before ours goes
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
        """Read the ops from the file itself (NapkinOps, then NapkinJournal), then the session's history."""
        if frev is not None:
            meta = {}
            try:
                with zipfile.ZipFile(path) as archive:
                    root = ET.fromstring(archive.read("Document.xml"))
                meta = {item.get("key"): item.get("value")
                        for item in root.findall("./Properties/Property[@name='Meta']/Map/Item")}
                if int(meta["NapkinRev"]) == frev:
                    ops = json.loads(meta["NapkinOps"])
                    if isinstance(ops, list) and all(
                            isinstance(op, dict) and isinstance(op.get("type"), str) and op["type"]
                            and (op.get("id") is None or isinstance(op["id"], str)) for op in ops):
                        _check_no_legacy_ops(ops)
                        return [{"op": op, "key": canon(op), "id": op.get("id"), "type": op["type"], "status": "ok"}
                                for op in ops]
            except (OSError, zipfile.BadZipFile, ET.ParseError, KeyError, TypeError, ValueError,
                    OverflowError, RecursionError):
                pass  # Old or damaged metadata leaves the historical fallbacks available.
            if meta.get("NapkinJournal"):
                try:
                    mj = _validate_journal_dict(json.loads(meta["NapkinJournal"]), require_sha=False)
                    if mj and int(mj.get("rev", -1)) == frev:
                        _check_no_legacy_ops(mj.get("ops", []), mj.get("dropped", []))
                        return [{"op": o, "key": canon(o), "id": o.get("id"), "type": o.get("type"), **st}
                                for o, st in zip(mj["ops"], mj["status"]) if st.get("status") == "ok"]
                except (ValueError, TypeError, KeyError):
                    pass
        if frev in self.rev_ops:
            return list(self.rev_ops[frev])
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
        # FreeCAD returns the live document for the same path; load a sibling snapshot instead.
        with tempfile.NamedTemporaryFile(dir=folder, prefix=".napkin-reload-", suffix=".FCStd") as snapshot:
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
            file_meta_rev = int(doc.Meta.get("NapkinRev", "0") or 0)
            kept_keys = {e["key"] for e in kept}
            prior_ops = self.applied
            if self.rev > int(self.doc.Meta.get("NapkinRev", "0") or 0) and self.rev in self.rev_ops:
                prior_ops = self.rev_ops[self.rev]
            when = time.strftime("%Y-%m-%dT%H:%M:%S")
            gone = [{"op": e["op"], "after_rev": frev, "at": when} for e in prior_ops
                    if e["status"] == "ok" and e["key"] not in kept_keys]
            staged.applied = kept
            staged.undo_floor = staged.session_base = len(kept)
            staged.external = staged.dirty = False
            staged.dropped = self.dropped + gone
            staged.rev = max(self.rev, file_meta_rev)
            staged.units = parse_units(doc.Meta.get("NapkinUnits"))
            staged.file_sha = digest
            staged.file_sig = sig
            staged.rev_ops = {file_meta_rev: list(kept)}
            doc.clearUndos()
            staged.model.show_as_hidden()
            after = staged.board_marks()
            staged._capture_floor_bytes()
            if outdir:
                staged.export(outdir)
                if last_export is not None:
                    current_export = self._exported_boards(outdir)
                    if current_export is not None:
                        before, after = last_export, current_export
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

    def _journal(self, rev):
        j = {"format": JOURNAL_FORMAT, "rev": rev,
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
            if isinstance(e, OpError) and e.about:
                entry["about"] = list(e.about)
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
        fc = self.floor_copy
        if not (isinstance(fc, dict) and self._floor_bytes is not None
                and fc.get("ops") == self.undo_floor
                and sha256_bytes(self._floor_bytes) == fc.get("sha256")):
            raise OpError("can't undo past the FreeCAD edit: its copy is missing")
        if self.doc is not None:
            App.closeDocument(self.doc.Name)
            self.doc = None
        with tempfile.NamedTemporaryFile(suffix=".FCStd") as tmp:
            tmp.write(self._floor_bytes)
            tmp.flush()
            self._load_file(tmp.name)
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
            s = {k: e[k] for k in ("id", "type", "status", "changed", "message", "about", "ms") if k in e}
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
        meta_matches = self.doc is not None and self.doc.Meta.get("NapkinUnits") == parsed
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
        meta["NapkinOps"] = json.dumps([e["op"] for e in saved_ops], separators=(",", ":"))
        self.rev += 1
        meta["NapkinRev"] = str(self.rev)
        if self.units is not None:
            meta["NapkinUnits"] = self.units
        meta["NapkinJournal"] = json.dumps(self._journal(self.rev), separators=(",", ":"))
        meta.pop("NapkinContentSha256", None)
        self.doc.Meta = meta
        tmp = saving_path(self.path)
        try:
            self._write(tmp, outdir)
        except Exception:
            self.rev -= 1           # a failed save leaves the revision where it was: the retry saves this one (T79)
            self.doc.Meta = prev_meta
            try:
                os.remove(tmp)
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

    def _write(self, tmp, outdir):
        """save()'s writing: one atomic step (<model>.saving.FCStd -> rename). Raises if any of it fails."""
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
        floor_bytes = self._floor_bytes if self.undo_floor > 0 else None
        finalize_fcstd(tmp, previous=self.path, floor_bytes=floor_bytes)
        os.replace(tmp, self.path)
        self.file_sha = sha256(self.path)
        _remove_legacy_sidecars(self.path)

    def close(self):
        if self.doc is not None:
            App.closeDocument(self.doc.Name)
            self.doc = None
