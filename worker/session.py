"""Session: one live document bound to one .FCStd file; sync, undo, journal, saving (A23, A24)."""
import FreeCAD as App
import hashlib
import json
import os
import re
import shutil
import zipfile
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
                    if identity in self.reserved and identity not in owners:
                        raise OpError(f"ID already reserved: {identity}")
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


def generation(model_path):
    """The files of one model's save generations (A32): the current pair, the one being written, the one before."""
    base, ext = os.path.splitext(model_path)
    return {"file": model_path, "journal": base + ".shopsketch.json",
            "saving_file": base + ".saving" + ext, "saving_journal": base + ".shopsketch.saving.json",
            "prev_file": base + ".prev" + ext, "prev_journal": base + ".shopsketch.prev.json",
            "unmatched_file": base + ".unmatched" + ext, "unmatched_journal": base + ".shopsketch.unmatched.json"}


def read_journal(path):
    try:
        with open(path) as f:
            j = json.load(f)
    except (OSError, ValueError):
        return None
    return j if isinstance(j, dict) and j.get("format") == JOURNAL_FORMAT and j.get("file_sha256") else None


def file_rev(path):
    """The ShopSketchRev a .FCStd carries, read from its Document.xml without opening it (None if it has none)."""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("Document.xml").decode("utf-8", "replace")
    except (OSError, KeyError, zipfile.BadZipFile):
        return None
    m = re.search(r'<Item key="ShopSketchRev" value="(\d+)"', xml)
    return int(m.group(1)) if m else None


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


def recover_generation(model_path):
    """Opening (A37): finish an identifiable interrupted save, preserving newer outside work.
    Only a missing or unreadable main file permits fallback to .prev. Displaced bytes are kept aside.
    Returns {"from", "rev", "why"} or None (an ordinary open, including outside edits).
    """
    import xml.etree.ElementTree as ET

    def readable(path):
        try:
            with zipfile.ZipFile(path) as z:
                ET.fromstring(z.read("Document.xml"))
                return z.testzip() is None
        except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError):
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
        self.ids = IdRegistry()
        self.undo_floor = 0
        self.external = False
        self.rev = 0
        self.dirty = False
        self.drawing = False
        self.session_base = 0
        self.doc = None
        self.file_sig = None
        self.file_sha = None       # the sha256 of the file as we last read or wrote it: an outside save differs (A36)
        self.rev_ops = {}          # rev -> the applied entries that revision of the file holds (what a reload keeps)
        self.dropped = []          # actions an outside save didn't have, taken out by a reload (A36; T65 offers them)
        self.recovered = None      # {"from", "rev", "why"}: opening fell back to the newest whole save (A32)
        if self.path and not fresh:
            self.recovered = recover_generation(self.path)
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

    def _load_file(self):
        """Open the file as the live document (opening, and reloading an outside save)."""
        self.doc = App.openDocument(self.path)
        self.doc.UndoMode = 1
        self.drawing = remove_drawing_pages(self.doc) or self.drawing
        self.doc.recompute()
        self.model = Model(self.doc)
        self.model.add_hidden_props()           # boards saved before hiding existed (T28)

    def _open_existing(self):
        self._load_file()
        self.rev = int(self.doc.Meta.get("ShopSketchRev", "0") or 0)
        self.file_sha = sha256(self.path)
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
            self.external = not (same_rev and j.get("file_sha256") == self.file_sha)
            self.dropped = list(j.get("dropped", []))
            self.ids.owners.update(j.get("id_owners", {}))
            self.ids.accept(j["ops"] + self.dropped, j.get("reserved_ids", []), legacy=True)
        else:
            self.external = True     # not written by Shop Sketch (stage 3 will adopt foreign solids)
        self.ids.seed_native(self.doc)
        # undo stops at a FreeCAD change: one since the journal, or one a reload took in earlier (the journal's floor)
        floor = min(int((j or {}).get("floor", 0) or 0), len(self.applied))
        self.undo_floor = len(self.applied) if self.external else floor
        self.session_base = len(self.applied)
        self.rev_ops = {self.rev: list(self.applied)}
        self.doc.clearUndos()
        self.file_sig = self.disk_sig()

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

    def _file_ops(self, frev):
        """The ops the file's revision frev holds: known for revisions this session opened or saved; else the .prev
        journal's, if it is that revision; else none (every action counts as dropped)."""
        if frev in self.rev_ops:
            return list(self.rev_ops[frev])
        pj = read_journal(generation(self.path)["prev_journal"])
        if frev is not None and pj and int(pj.get("rev", -1)) == frev:
            return [{"op": o, "key": canon(o), "id": o.get("id"), "type": o.get("type"), **st}
                    for o, st in zip(pj["ops"], pj["status"]) if st.get("status") == "ok"]
        return []

    def reload_outside(self):
        """FreeCAD saved the file (A36): it becomes the live document. Actions the file doesn't hold (made since
        the revision FreeCAD opened) leave the list and are kept in the journal as dropped (T65); undo stops at the
        FreeCAD change, in this session and the next (the journal's floor). Returns {changed, removed, dropped}."""
        before = self.board_marks()
        frev = file_rev(self.path)
        kept = self._file_ops(frev)
        held = {e["key"] for e in kept}
        when = time.strftime("%Y-%m-%dT%H:%M:%S")
        gone = [{"op": e["op"], "after_rev": frev, "at": when} for e in self.applied
                if e["status"] == "ok" and e["key"] not in held]
        if self.doc is not None:
            App.closeDocument(self.doc.Name)
        self._load_file()
        self.ids.seed_native(self.doc)
        self.applied = kept
        self.undo_floor = self.session_base = len(kept)
        self.external = False                   # the journal written below names this file
        self.dirty = False
        self.dropped += gone
        file_meta_rev = int(self.doc.Meta.get("ShopSketchRev", "0") or 0)
        self.rev = max(self.rev, file_meta_rev)       # our next save goes on counting up
        self.file_sha = sha256(self.path)
        self.rev_ops = {file_meta_rev: list(kept)}
        self.doc.clearUndos()
        atomic_json(journal_path(self.path), self._journal(file_meta_rev, self.file_sha))
        self.file_sig = self.disk_sig()
        self.model.show_as_hidden()
        after = self.board_marks()
        changed = sorted(b for b in after if before.get(b) != after[b])
        return {"changed": changed, "removed": sorted(b for b in before if b not in after),
                "dropped": [d["op"] for d in gone]}     # no "rev": the reply's is the session's (open_reply)

    def _journal(self, rev, file_sha):
        return {"format": JOURNAL_FORMAT, "rev": rev, "file_sha256": file_sha,
                "model": os.path.basename(self.path), "name": os.path.splitext(os.path.basename(self.path))[0],
                "ops": [e["op"] for e in self.applied],
                "status": [{k: e[k] for k in ("status", "changed", "message", "ms") if k in e} for e in self.applied],
                "floor": self.undo_floor, "dropped": self.dropped,
                "reserved_ids": sorted(self.ids.reserved), "id_owners": self.ids.owners}

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
        g = generation(self.path)
        try:
            self._write(g, outdir)
        except Exception:
            self.rev -= 1           # a failed save leaves the revision where it was: the retry saves this one (T79)
            meta["ShopSketchRev"] = str(self.rev)
            self.doc.Meta = meta
            for k in ("saving_file", "saving_journal"):
                try:
                    os.remove(g[k])
                except OSError:
                    pass
            raise
        self.dirty = False
        self.file_sig = self.disk_sig()
        self.rev_ops[self.rev] = list(self.applied)
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
