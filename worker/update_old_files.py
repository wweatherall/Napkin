"""One-time updater for pre-H199/H204 saved files (.FCStd and .json) (T159, T139, A43, G09); session.py reads its old-name tables to refuse a file not yet updated.

Rewrites:
- `property_edit` with `mode` in (`plane_fit`, `replace_fit`) -> `fit` / `unfit` (T162)
- `push_pull` with `body` (or free rect/region without `body`) -> `new_board` (`edge_fit` -> `fit`)
- `status.json` `push_pull` entries that created a body -> `new_board`
- `ShopSketch*` Meta keys, `ShopSketchFloor.FCStd`, `shopsketch-journal/0.1`, and `.shopsketch.json` sidecars -> Napkin (T139)

Reports and leaves untouched:
- `push_pull` with `edge_fit` on a face (H198's old shape)
- `push_pull` with `resize_stock` (H200's)

Pure Python (no FreeCAD import required). Writes atomically via temp file + os.replace."""
import hashlib
import json
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATHS = ("examples", "tests/legacy_one_file", "tests/reference", "04_Napkin_Drawings", "models")

META_KEY_RENAMES = {
    "ShopSketchOps": "NapkinOps",
    "ShopSketchRev": "NapkinRev",
    "ShopSketchJournal": "NapkinJournal",
    "ShopSketchUnits": "NapkinUnits",
    "ShopSketchContentSha256": "NapkinContentSha256",
}
ZIP_ENTRY_RENAMES = {
    "ShopSketchFloor.FCStd": "NapkinFloor.FCStd",
}
OLD_SIDECAR_SUFFIX = ".shopsketch.json"


def upgrade_op(op, free_rects=None):
    """Upgrade a single op dict. Returns (new_op, note_or_None)."""
    if not isinstance(op, dict):
        return op, None
    t = op.get("type")
    if t == "property_edit":
        mode = op.get("mode")
        if mode in ("plane_fit", "replace_fit"):
            upgraded = {k: v for k, v in op.items() if k != "mode"}
            upgraded["type"] = "fit" if mode == "plane_fit" else "unfit"
            return upgraded, None
        return op, None

    if t == "push_pull":
        tgt = op.get("target") if isinstance(op.get("target"), dict) else {}
        if op.get("resize_stock"):
            return op, "push_pull with resize_stock left as is"
        if op.get("edge_fit") and "face" in tgt and "region" not in tgt and not op.get("body"):
            return op, "push_pull with edge_fit on face left as is"
        is_free_rect = "rect" in tgt and "region" not in tgt and free_rects is not None and tgt["rect"] in free_rects
        is_free_region = "region" in tgt and "face" not in tgt and "rect" not in tgt
        if op.get("body") or is_free_rect or is_free_region:
            upgraded = {}
            for k, v in op.items():
                if k == "edge_fit":
                    upgraded["fit"] = v
                else:
                    upgraded[k] = v
            upgraded["type"] = "new_board"
            if not upgraded.get("body"):
                upgraded["body"] = f"{op.get('id', 'nb')}_body"
            return upgraded, None
    return op, None


def _free_rects_in(ops):
    free = set()
    for op in ops:
        if isinstance(op, dict) and op.get("type") in ("rect", "circle", "polygon", "line", "arc"):
            pl = op.get("plane")
            if isinstance(pl, dict) and not pl.get("on"):
                if op.get("id"):
                    free.add(op["id"])
    return free


def _upgrade_op_list(ops, path_str, warnings):
    free_rects = _free_rects_in(ops)
    out = []
    changed = False
    for op in ops:
        new_op, note = upgrade_op(op, free_rects=free_rects)
        if note:
            oid = op.get("id", "?") if isinstance(op, dict) else "?"
            warnings.append(f"{path_str}: {oid}: {note}")
        if new_op != op:
            changed = True
        out.append(new_op)
    return out, changed


def _upgrade_journal_obj(data, path_str, warnings):
    """Upgrade a journal/oplog dict in place of a copy. Returns (new_data, changed)."""
    if not isinstance(data, dict) or not isinstance(data.get("ops"), list):
        return data, False

    # status.json format: ops are OpStatus dicts with "status" and "changed"
    if "oplog" in data and all(isinstance(o, dict) and "status" in o for o in data["ops"]):
        seen_bodies = set()
        new_ops = []
        changed = False
        for entry in data["ops"]:
            new_entry = dict(entry)
            if entry.get("type") == "push_pull":
                ch = entry.get("changed") or []
                if any(b not in seen_bodies for b in ch):
                    new_entry["type"] = "new_board"
                    changed = True
                seen_bodies.update(ch)
            elif entry.get("type") in ("new_board", "move", "mirror"):
                seen_bodies.update(entry.get("changed") or [])
            new_ops.append(new_entry)
        if not changed:
            return data, False
        out = dict(data)
        out["ops"] = new_ops
        return out, True

    new_ops, ops_changed = _upgrade_op_list(data["ops"], path_str, warnings)
    changed = ops_changed
    out = dict(data)
    out["ops"] = new_ops
    if out.get("format") == "shopsketch-journal/0.1":
        out["format"] = "napkin-journal/0.1"
        changed = True

    if isinstance(data.get("dropped"), list):
        free_rects = _free_rects_in(data["ops"])
        new_dropped = []
        for entry in data["dropped"]:
            if isinstance(entry, dict) and isinstance(entry.get("op"), dict):
                nop, note = upgrade_op(entry["op"], free_rects=free_rects)
                if note:
                    warnings.append(f"{path_str}: {entry['op'].get('id', '?')}: {note}")
                if nop != entry["op"]:
                    changed = True
                    new_dropped.append({**entry, "op": nop})
                else:
                    new_dropped.append(entry)
            else:
                nop, note = upgrade_op(entry, free_rects=free_rects)
                if note:
                    oid = entry.get("id", "?") if isinstance(entry, dict) else "?"
                    warnings.append(f"{path_str}: {oid}: {note}")
                if nop != entry:
                    changed = True
                new_dropped.append(nop)
        out["dropped"] = new_dropped

    if isinstance(data.get("status"), list) and len(data["status"]) == len(new_ops):
        new_status = []
        for st, op in zip(data["status"], new_ops):
            if isinstance(st, dict) and isinstance(op, dict) and st.get("type") != op.get("type"):
                changed = True
                new_status.append({**st, "type": op["type"]})
            else:
                new_status.append(st)
        out["status"] = new_status

    if isinstance(data.get("id_owners"), dict):
        owners = dict(data["id_owners"])
        all_ops = list(new_ops)
        for d in out.get("dropped", []):
            all_ops.append(d["op"] if isinstance(d, dict) and isinstance(d.get("op"), dict) else d)
        for op in all_ops:
            if isinstance(op, dict) and op.get("id") and op.get("type"):
                oid = op["id"]
                want = "op:" + op["type"]
                if oid in owners and owners[oid] != want:
                    owners[oid] = want
                    changed = True
        out["id_owners"] = owners

    return (out, True) if changed else (data, False)


def _atomic_write_bytes(path, data_bytes):
    path = Path(path)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data_bytes)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _sha256_file(path):
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
            if item.get("key") in ("ShopSketchContentSha256", "NapkinContentSha256"):
                meta_map.remove(item)
        meta_map.set("count", str(len(meta_map.findall("Item"))))
    return ET.canonicalize(ET.tostring(root, encoding="unicode")).encode("utf-8")


def _compute_content_sha256(entries):
    h = hashlib.sha256()
    for name in sorted(entries):
        if name in ("GuiDocument.xml", "ShopSketchFloor.FCStd", "NapkinFloor.FCStd"):
            continue
        data = entries[name]
        if name == "Document.xml":
            data = _strip_content_sha_from_xml(data)
        h.update(name.encode("utf-8") + b"\0" + str(len(data)).encode("ascii") + b"\0" + data)
    return h.hexdigest()


def update_fcstd(path, warnings):
    """Update Napkin/ShopSketch Meta, ops, journal, and floor entry inside a .FCStd file. Returns True if changed."""
    path = Path(path)
    with zipfile.ZipFile(path, "r") as zin:
        infolist = zin.infolist()
        if "Document.xml" not in zin.namelist():
            return False
        entries = {item.filename: zin.read(item.filename) for item in infolist}

    old_sha_matched = False
    root = ET.fromstring(entries["Document.xml"])
    meta_map = root.find("./Properties/Property[@name='Meta']/Map")
    if meta_map is None:
        return False

    changed = False
    old_content_sha = None
    for item in list(meta_map.findall("Item")):
        key = item.get("key")
        if key in ("ShopSketchContentSha256", "NapkinContentSha256"):
            old_content_sha = item.get("value")
    if old_content_sha is not None and old_content_sha == _compute_content_sha256(entries):
        old_sha_matched = True

    new_entries = {}
    for name, data in entries.items():
        if name in ZIP_ENTRY_RENAMES:
            new_entries[ZIP_ENTRY_RENAMES[name]] = data
            changed = True
        else:
            new_entries[name] = data

    for item in list(meta_map.findall("Item")):
        key = item.get("key")
        if key in META_KEY_RENAMES:
            key = META_KEY_RENAMES[key]
            item.set("key", key)
            changed = True
        if key == "NapkinOps" and item.get("value"):
            try:
                ops = json.loads(item.get("value"))
            except ValueError:
                continue
            if isinstance(ops, list):
                new_ops, ops_changed = _upgrade_op_list(ops, str(path), warnings)
                if ops_changed:
                    item.set("value", json.dumps(new_ops, separators=(",", ":")))
                    changed = True
        elif key == "NapkinJournal" and item.get("value"):
            try:
                j = json.loads(item.get("value"))
            except ValueError:
                continue
            new_j, j_changed = _upgrade_journal_obj(j, str(path), warnings)
            if j_changed:
                item.set("value", json.dumps(new_j, separators=(",", ":")))
                changed = True

    if not changed:
        return False

    new_doc_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if old_sha_matched:
        new_entries["Document.xml"] = new_doc_bytes
        csha = _compute_content_sha256(new_entries)
        for item in list(meta_map.findall("Item")):
            if item.get("key") == "NapkinContentSha256":
                item.set("value", csha)
                break
        new_doc_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp_name, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in infolist:
                if item.filename == "Document.xml":
                    zout.writestr("Document.xml", new_doc_bytes)
                elif item.filename in ZIP_ENTRY_RENAMES:
                    zout.writestr(ZIP_ENTRY_RENAMES[item.filename], new_entries[ZIP_ENTRY_RENAMES[item.filename]])
                else:
                    zout.writestr(item, new_entries[item.filename])
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return True


def update_json(path, warnings, fcstd_sha_map=None):
    """Update a journal or status .json file. Returns True if changed."""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return False

    new_data, changed = _upgrade_journal_obj(data, str(path), warnings)
    dest_path = path
    for old_suf, new_suf in (
        (".shopsketch.json", ".napkin.json"),
        (".shopsketch.prev.json", ".napkin.prev.json"),
        (".shopsketch.saving.json", ".napkin.saving.json"),
    ):
        if path.name.endswith(old_suf):
            dest_path = path.with_name(path.name[:-len(old_suf)] + new_suf)
            changed = True
            break

    if fcstd_sha_map and isinstance(new_data, dict) and "file_sha256" in new_data:
        stem = str(dest_path)
        if stem.endswith(".napkin.json"):
            fcstd_path = Path(stem[:-len(".napkin.json")] + ".FCStd")
            if fcstd_path in fcstd_sha_map:
                old_sha, new_sha = fcstd_sha_map[fcstd_path]
                if new_data.get("file_sha256") == old_sha and new_sha != old_sha:
                    new_data = dict(new_data)
                    new_data["file_sha256"] = new_sha
                    changed = True
            floor_path = Path(stem[:-len(".napkin.json")] + ".floor.FCStd")
            if floor_path in fcstd_sha_map and isinstance(new_data.get("floor_copy"), dict):
                old_fsha, new_fsha = fcstd_sha_map[floor_path]
                if new_data["floor_copy"].get("sha256") == old_fsha and new_fsha != old_fsha:
                    new_data = dict(new_data)
                    new_data["floor_copy"] = {**new_data["floor_copy"], "sha256": new_fsha}
                    changed = True

    if not changed:
        return False

    indent = 1 if "\n " in raw else None
    text = json.dumps(new_data, indent=indent) + ("\n" if raw.endswith("\n") else "")
    _atomic_write_bytes(dest_path, text.encode("utf-8"))
    if dest_path != path:
        try:
            os.unlink(path)
        except OSError:
            pass
    return True


def iter_target_files(paths):
    """Yield sorted .FCStd and .json files under the given paths."""
    seen = set()
    fcstds = []
    jsons = []
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        if p.is_file():
            candidates = [p]
        else:
            candidates = sorted(p.rglob("*"))
        for c in candidates:
            if not c.is_file():
                continue
            rc = c.resolve()
            if rc in seen:
                continue
            seen.add(rc)
            if c.name.lower().endswith(".fcstd"):
                fcstds.append(c)
            elif c.name.lower().endswith(".json"):
                jsons.append(c)
    return fcstds + jsons


def update_paths(paths=None, out=None, err=None):
    """Update all .FCStd and .json files in paths. Returns (changed_files, warnings)."""
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    if not paths:
        paths = [ROOT / p for p in DEFAULT_PATHS]
    files = iter_target_files(paths)
    fcstds = [f for f in files if f.name.lower().endswith(".fcstd")]
    jsons = [f for f in files if f.name.lower().endswith(".json")]

    changed_files = []
    warnings = []
    fcstd_sha_map = {}

    for f in fcstds:
        old_sha = _sha256_file(f)
        if update_fcstd(f, warnings):
            new_sha = _sha256_file(f)
            fcstd_sha_map[f] = (old_sha, new_sha)
            changed_files.append(f)
            print(f"updated {f}", file=out)

    for f in jsons:
        if update_json(f, warnings, fcstd_sha_map=fcstd_sha_map):
            changed_files.append(f)
            print(f"updated {f}", file=out)

    for w in warnings:
        print(f"warning: {w}", file=err)

    return changed_files, warnings


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    update_paths(args or None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
