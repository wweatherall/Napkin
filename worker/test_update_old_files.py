"""Tests for worker/update_old_files.py (H199, A43, G09)."""
import io
import json
import os
import shutil
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import update_old_files as uof

R = [0, 0]


def check(name, cond, detail=""):
    R[0 if cond else 1] += 1
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"), flush=True)


def _make_fcstd(path, meta_items):
    root = ET.Element("Document", SchemaVersion="4")
    props = ET.SubElement(root, "Properties", Count="1")
    meta = ET.SubElement(props, "Property", name="Meta", type="App::PropertyMap")
    mmap = ET.SubElement(meta, "Map", count=str(len(meta_items)))
    for k, v in meta_items.items():
        ET.SubElement(mmap, "Item", key=k, value=v)
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Document.xml", xml_bytes)
        z.writestr("Dummy.bin", b"hello-fcstd")


def run():
    # 1. Pure op upgrades
    op_fit, note = uof.upgrade_op({"id": "f1", "type": "property_edit", "mode": "plane_fit", "body": "b1", "axis": 0, "face": 1})
    check("property_edit plane_fit -> fit", op_fit == {"id": "f1", "type": "fit", "body": "b1", "axis": 0, "face": 1} and note is None, op_fit)

    op_unfit, note = uof.upgrade_op({"id": "u1", "type": "property_edit", "mode": "replace_fit", "body": "b1", "axis": 0, "value": "100mm"})
    check("property_edit replace_fit -> unfit", op_unfit == {"id": "u1", "type": "unfit", "body": "b1", "axis": 0, "value": "100mm"} and note is None, op_unfit)

    op_nb, note = uof.upgrade_op({
        "id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": 18, "body": "b1",
        "edge_fit": {"target_body": "b2", "face": 5, "fit_mode": 1},
    })
    check("push_pull with body + edge_fit -> new_board + fit",
          op_nb == {"id": "pp1", "type": "new_board", "target": {"rect": "r1"}, "distance": 18, "body": "b1",
                    "fit": {"target_body": "b2", "face": 5, "fit_mode": 1}} and note is None, op_nb)

    op_rs, note = uof.upgrade_op({"id": "pp_rs", "type": "push_pull", "target": {"face": {"body": "b1"}}, "distance": 5, "resize_stock": True})
    check("push_pull resize_stock left as is with note", op_rs["type"] == "push_pull" and note is not None, (op_rs, note))

    op_ef, note = uof.upgrade_op({"id": "pp_ef", "type": "push_pull", "target": {"face": {"body": "b1"}}, "distance": 5, "edge_fit": {"target_body": "b2", "face": 0}})
    check("push_pull edge_fit on face left as is with note", op_ef["type"] == "push_pull" and note is not None, (op_ef, note))

    with tempfile.TemporaryDirectory(prefix="uof-test-") as td:
        td_path = Path(td)

        # 2. FCStd + companion .shopsketch.json + status.json (with ShopSketchFloor.FCStd)
        ops = [
            {"id": "r1", "type": "rect", "plane": {"origin": [0, 0, 0], "normal": [0, 0, 1]}, "size": [100, 50]},
            {"id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": 18, "body": "b1"},
            {"id": "pp2", "type": "push_pull", "target": {"face": {"body": "b1"}}, "distance": 5},
        ]
        journal = {
            "format": "shopsketch-journal/0.1",
            "rev": 1,
            "ops": ops,
            "status": [{"id": "r1", "type": "rect", "status": "ok"},
                       {"id": "pp1", "type": "push_pull", "status": "ok"},
                       {"id": "pp2", "type": "push_pull", "status": "ok"}],
            "dropped": [{"op": {"id": "pp_d", "type": "push_pull", "target": {"rect": "r1"}, "distance": 10, "body": "bd"}}],
            "id_owners": {"pp1": "op:push_pull", "b1": "body:pp1", "pp_d": "op:push_pull"},
        }
        fcstd = td_path / "m.FCStd"
        _make_fcstd(fcstd, {
            "ShopSketchOps": json.dumps(ops),
            "ShopSketchRev": "1",
            "ShopSketchJournal": json.dumps(journal),
        })
        with zipfile.ZipFile(fcstd, "a", zipfile.ZIP_DEFLATED) as z:
            z.writestr("ShopSketchFloor.FCStd", b"floor-bytes")
        with zipfile.ZipFile(fcstd, "r") as z:
            init_entries = {n: z.read(n) for n in z.namelist()}
        _make_fcstd(fcstd, {
            "ShopSketchOps": json.dumps(ops),
            "ShopSketchRev": "1",
            "ShopSketchJournal": json.dumps(journal),
            "ShopSketchContentSha256": uof._compute_content_sha256(init_entries),
        })
        with zipfile.ZipFile(fcstd, "a", zipfile.ZIP_DEFLATED) as z:
            z.writestr("ShopSketchFloor.FCStd", b"floor-bytes")
        old_sha = uof._sha256_file(fcstd)
        old_sidecar = td_path / "m.shopsketch.json"
        sidecar = td_path / "m.napkin.json"
        old_sidecar.write_text(json.dumps({**journal, "file_sha256": old_sha}, indent=1), encoding="utf-8")

        status_file = td_path / "status.json"
        status_file.write_text(json.dumps({
            "oplog": "test",
            "ops": [
                {"id": "r1", "type": "rect", "status": "ok", "changed": []},
                {"id": "pp1", "type": "push_pull", "status": "ok", "changed": ["b1"]},
                {"id": "pp2", "type": "push_pull", "status": "ok", "changed": ["b1"]},
            ],
        }, indent=1), encoding="utf-8")

        warn_file = td_path / "warn.json"
        warn_file.write_text(json.dumps({
            "ops": [{"id": "pp_w", "type": "push_pull", "target": {"face": {"body": "b1"}}, "distance": 5, "resize_stock": True}],
        }), encoding="utf-8")

        out1, err1 = io.StringIO(), io.StringIO()
        changed1, warnings1 = uof.update_paths([td_path], out=out1, err=err1)
        check("first run updates 3 files and warns on 1",
              len(changed1) == 3 and len(warnings1) == 1 and "pp_w" in warnings1[0],
              (changed1, warnings1))

        new_sha = uof._sha256_file(fcstd)
        sc_data = json.loads(sidecar.read_text(encoding="utf-8"))
        check("sidecar renamed to .napkin.json and format, file_sha256, ops, dropped, status, id_owners updated",
              not old_sidecar.exists()
              and sc_data["format"] == "napkin-journal/0.1"
              and sc_data["file_sha256"] == new_sha
              and sc_data["ops"][1]["type"] == "new_board"
              and sc_data["ops"][2]["type"] == "push_pull"
              and sc_data["status"][1]["type"] == "new_board"
              and sc_data["dropped"][0]["op"]["type"] == "new_board"
              and sc_data["id_owners"]["pp1"] == "op:new_board"
              and sc_data["id_owners"]["pp_d"] == "op:new_board",
              sc_data)

        st_data = json.loads(status_file.read_text(encoding="utf-8"))
        check("status.json upgrades only body-creating push_pull",
              st_data["ops"][1]["type"] == "new_board" and st_data["ops"][2]["type"] == "push_pull",
              st_data)

        # Verify FCStd NapkinOps, NapkinRev, NapkinJournal, NapkinFloor.FCStd, and NapkinContentSha256
        with zipfile.ZipFile(fcstd) as z:
            root = ET.fromstring(z.read("Document.xml"))
            entries = {n: z.read(n) for n in z.namelist()}
        meta = {i.get("key"): i.get("value") for i in root.findall("./Properties/Property[@name='Meta']/Map/Item")}
        check("FCStd Napkin* Meta keys, NapkinFloor.FCStd, and ContentSha256 updated",
              "ShopSketchOps" not in meta and "ShopSketchJournal" not in meta
              and "ShopSketchFloor.FCStd" not in entries and "NapkinFloor.FCStd" in entries
              and meta.get("NapkinRev") == "1"
              and json.loads(meta["NapkinOps"])[1]["type"] == "new_board"
              and json.loads(meta["NapkinJournal"])["format"] == "napkin-journal/0.1"
              and json.loads(meta["NapkinJournal"])["ops"][1]["type"] == "new_board"
              and meta["NapkinContentSha256"] == uof._compute_content_sha256(entries),
              meta)

        # 3. Idempotency
        mtimes_before = {p: p.stat().st_mtime_ns for p in (fcstd, sidecar, status_file)}
        out2, err2 = io.StringIO(), io.StringIO()
        changed2, _ = uof.update_paths([td_path], out=out2, err=err2)
        mtimes_after = {p: p.stat().st_mtime_ns for p in (fcstd, sidecar, status_file)}
        check("second run is a no-op and preserves mtimes",
              changed2 == [] and out2.getvalue() == "" and mtimes_before == mtimes_after,
              (changed2, out2.getvalue()))

        # 4. Atomic write / interrupted mid-write leaves original intact
        int_json = td_path / "interrupt.json"
        orig_json_bytes = json.dumps({"ops": [{"id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": 18, "body": "b1"}]}).encode("utf-8")
        int_json.write_bytes(orig_json_bytes)

        int_fcstd = td_path / "interrupt.FCStd"
        _make_fcstd(int_fcstd, {"ShopSketchOps": json.dumps([{"id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": 18, "body": "b1"}])})
        orig_fcstd_bytes = int_fcstd.read_bytes()

        real_replace = os.replace

        def fail_replace(src, dst):
            raise RuntimeError("simulated crash")

        uof.os.replace = fail_replace
        try:
            for target in (int_json, int_fcstd):
                crashed = False
                try:
                    uof.update_paths([target], out=io.StringIO(), err=io.StringIO())
                except RuntimeError:
                    crashed = True
                check(f"interrupted write on {target.name} raises and leaves original intact",
                      crashed and (target.read_bytes() == (orig_json_bytes if target == int_json else orig_fcstd_bytes)))
            leftover = [p.name for p in td_path.iterdir() if ".tmp" in p.name]
            check("interrupted write leaves no temp files behind", leftover == [], leftover)
        finally:
            uof.os.replace = real_replace

    print(f"UPDATE OLD FILES TESTS: {R[0]} passed, {R[1]} failed", flush=True)
    return 1 if R[1] else 0


sys.exit(run())
