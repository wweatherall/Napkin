"""Tests for plane_fit.py: T163 (flip/mirror target), I75 ({normal, point}), I76 (rotation pause/resume), I77 (detach on cut/delete + Undo)."""
import json
import math
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import test_load  # noqa: E402
import FreeCAD as App  # noqa: E402
import plane_fit  # noqa: E402
from session import Session  # noqa: E402

R = [0, 0]


def check(name, cond, detail=""):
    R[0 if cond else 1] += 1
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  ({detail})"), flush=True)


def _board(bid, origin, size, normal=(0, 0, 1)):
    rid = f"r_{bid}"
    nbid = f"nb_{bid}"
    return [
        {"id": rid, "type": "rect", "plane": {"origin": list(origin), "normal": list(normal)}, "size": list(size[:2])},
        {"id": nbid, "type": "new_board", "target": {"rect": rid}, "distance": size[2], "body": bid},
    ]


def _cut(cid, body, origin, size, depth):
    return [
        {"id": cid + "r", "type": "rect", "plane": {"on": {"body": body, "normal": [0, 0, 1], "point": list(origin)}}, "size": list(size)},
        {"id": cid + "p", "type": "push_pull", "target": {"rect": cid + "r"}, "distance": -depth},
    ]


def _bodies_json(session, outdir):
    session.export(outdir)
    with open(os.path.join(outdir, "bodies.json"), encoding="utf-8") as f:
        return {b["id"]: b for b in json.load(f)}


def _rotate_around(obj, pivot, axis_vec, deg, base_placement=None):
    base = base_placement if base_placement is not None else App.Placement()
    rot = App.Placement(pivot, App.Rotation(axis_vec, deg)).multiply(App.Placement(-pivot, App.Rotation()))
    obj.Placement = rot.multiply(base)


def _refit(session, fn):
    before = plane_fit.refit_inputs(session.model)
    fn()
    session.doc.recompute()
    plane_fit.refit_changed(session.model, before)
    session.doc.recompute()


def main():
    folder = os.environ.get("TESTDIR") or tempfile.mkdtemp(prefix="napkin-plane-fit-")
    os.makedirs(folder, exist_ok=True)

    # 1. T163 & I75: integer face rejected; {normal, point} works; flip (mirror replace=True) keeps fit live.
    s = Session(os.path.join(folder, "t163.FCStd"), fresh=True)
    try:
        base = _board("panel", [0, 0, 200], [120, 80, 20]) + _board("shelf", [10, 10, 0], [30, 30, 20])
        s.sync(base + [{"id": "f_int", "type": "fit", "body": "shelf", "target_body": "panel", "axis": 2, "face": 4, "fit_mode": 0}])
        check("I75 integer face in fit op is rejected",
              s.status()[-1]["status"] == "failed", s.status()[-1])

        ops = base + [{"id": "f1", "type": "fit", "body": "shelf", "target_body": "panel", "axis": 2,
                       "face": {"normal": [0, 0, -1], "point": [0, 0, 200]}, "fit_mode": 0}]
        s.sync(ops)
        check("T163 initial fit reaches panel bottom (z=200)",
              abs(s.model.world_shape(s.model.body("shelf")).BoundBox.ZMax - 200.0) < 0.01)

        flip_op = {
            "id": "m_flip", "type": "mirror", "targets": ["panel"],
            "plane": {"point": [0, 0, 210], "normal": [0, 0, 1]}, "replace": True,
        }
        s.sync(ops + [flip_op])
        tip = s.model.body("shelf").Tip
        check("T163 flipped panel keeps fit live",
              tip.SSTargetId == "panel"
              and abs(s.model.world_shape(s.model.body("shelf")).BoundBox.ZMax - 200.0) < 0.01,
              (tip.SSTargetId, tip.SSFitResult, s.model.world_shape(s.model.body("shelf")).BoundBox.ZMax))

        s.sync(ops + [flip_op, {"id": "mv_flip", "type": "move", "targets": ["panel"], "vector": [0, 0, 30]}])
        check("T163 moving flipped panel updates fitted shelf",
              abs(s.model.world_shape(s.model.body("shelf")).BoundBox.ZMax - 230.0) < 0.01,
              s.model.world_shape(s.model.body("shelf")).BoundBox.ZMax)
    finally:
        s.close()

    # 2. I76: rectangular target rotation at 45, 89, 90, 91, 180 deg, save/reopen paused, resume, and both rotated together.
    rot_path = os.path.join(folder, "i76_rot.FCStd")
    s = Session(rot_path, fresh=True)
    try:
        ops = (
            _board("panel", [0, 0, 200], [120, 80, 20])
            + _board("shelf", [45, 25, 0], [30, 30, 20])
            + [{"id": "f1", "type": "fit", "body": "shelf", "target_body": "panel", "axis": 2,
                "face": {"normal": [0, 0, -1], "point": [0, 0, 200]}, "fit_mode": 0}]
        )
        s.sync(ops)
        panel = s.model.body("panel")
        shelf = s.model.body("shelf")
        pivot = App.Vector(60, 40, 210)
        x_ax = App.Vector(1, 0, 0)
        shelf_len = lambda: (shelf.Tip.SSFitCorners[4] - shelf.Tip.SSFitCorners[0]).Length

        # 45 deg: holds original face, live
        _refit(s, lambda: _rotate_around(panel, pivot, x_ax, 45))
        len_45 = shelf_len()
        check("I76 at 45 deg holds face and stays live",
              shelf.Tip.SSTargetId == "panel"
              and not getattr(shelf.Tip, "SSFitPaused", False)
              and len_45 < 200.0,
              (shelf.Tip.SSTargetId, getattr(shelf.Tip, "SSFitPaused", None), len_45))

        # 89 deg: within FIT_PAUSE_DEG (2 deg) of 90 -> paused, keeps length
        _refit(s, lambda: _rotate_around(panel, pivot, x_ax, 89))
        bj = _bodies_json(s, os.path.join(folder, "out_89"))
        check("I76 at 89 deg pauses and keeps length",
              shelf.Tip.SSTargetId == "panel"
              and getattr(shelf.Tip, "SSFitPaused", False) is True
              and abs(shelf_len() - len_45) < 1e-6
              and bj["shelf"]["stock_frame"].get("fit_state") == "paused",
              (shelf.Tip.SSTargetId, getattr(shelf.Tip, "SSFitPaused", None), shelf_len(), len_45))

        # 91 deg: still within 2 deg of 90 -> paused
        _refit(s, lambda: _rotate_around(panel, pivot, x_ax, 91))
        check("I76 at 91 deg stays paused and keeps length",
              shelf.Tip.SSTargetId == "panel"
              and getattr(shelf.Tip, "SSFitPaused", False) is True
              and abs(shelf_len() - len_45) < 1e-6)

        # 180 deg: past pause -> resumes on opposite face (back at z=200)
        _refit(s, lambda: _rotate_around(panel, pivot, x_ax, 180))
        bj180 = _bodies_json(s, os.path.join(folder, "out_180"))
        check("I76 at 180 deg resumes on opposite face",
              shelf.Tip.SSTargetId == "panel"
              and getattr(shelf.Tip, "SSFitPaused", False) is False
              and abs(shelf_len() - 200.0) < 0.01
              and bj180["shelf"]["stock_frame"].get("fit_state") == "live",
              (shelf_len(), bj180["shelf"]["stock_frame"].get("fit_state")))

        # Back to 0, then 90 deg -> save and reopen paused -> rotate on to 100 deg -> resumes!
        _refit(s, lambda: _rotate_around(panel, pivot, x_ax, 0))
        len_0 = shelf_len()
        _refit(s, lambda: _rotate_around(panel, pivot, x_ax, 90))
        check("I76 at 90 deg is paused",
              getattr(shelf.Tip, "SSFitPaused", False) is True and abs(shelf_len() - len_0) < 1e-6)
        s.save()
    finally:
        s.close()

    s = Session(rot_path)
    try:
        panel = s.model.body("panel")
        shelf = s.model.body("shelf")
        bj_reopen = _bodies_json(s, os.path.join(folder, "out_reopen_paused"))
        check("I76 save and reopen preserves paused state and length",
              shelf.Tip.SSTargetId == "panel"
              and getattr(shelf.Tip, "SSFitPaused", False) is True
              and abs((shelf.Tip.SSFitCorners[4] - shelf.Tip.SSFitCorners[0]).Length - 200.0) < 0.01
              and bj_reopen["shelf"]["stock_frame"].get("fit_state") == "paused")

        _refit(s, lambda: _rotate_around(panel, App.Vector(60, 40, 210), App.Vector(1, 0, 0), 100))
        check("I76 rotating past pause after reopen resumes fit",
              shelf.Tip.SSTargetId == "panel"
              and getattr(shelf.Tip, "SSFitPaused", False) is False,
              (shelf.Tip.SSTargetId, getattr(shelf.Tip, "SSFitPaused", None), shelf.Tip.SSFitResult))
    finally:
        s.close()

    # Both boards rotated together by 90 deg -> nothing changes
    s = Session(os.path.join(folder, "i76_together.FCStd"), fresh=True)
    try:
        ops = (
            _board("panel", [0, 0, 200], [120, 80, 20])
            + _board("shelf", [45, 25, 0], [30, 30, 20])
            + [{"id": "f1", "type": "fit", "body": "shelf", "target_body": "panel", "axis": 2,
                "face": {"normal": [0, 0, -1], "point": [0, 0, 200]}, "fit_mode": 0}]
        )
        s.sync(ops)
        panel = s.model.body("panel")
        shelf = s.model.body("shelf")
        pivot = App.Vector(60, 40, 100)
        x_ax = App.Vector(1, 0, 0)

        def rot_both():
            _rotate_around(panel, pivot, x_ax, 90)
            _rotate_around(shelf, pivot, x_ax, 90)

        _refit(s, rot_both)
        len_both = (shelf.Tip.SSFitCorners[4] - shelf.Tip.SSFitCorners[0]).Length
        check("I76 rotating both boards together 90 deg keeps fit live and unchanged",
              shelf.Tip.SSTargetId == "panel"
              and getattr(shelf.Tip, "SSFitPaused", False) is False
              and abs(len_both - 200.0) < 0.01,
              (shelf.Tip.SSTargetId, getattr(shelf.Tip, "SSFitPaused", None), len_both))
    finally:
        s.close()

    # 3. I77: cut away target face -> detaches (no jump, no message, detached in bodies.json), save/reopen detached, Undo restores; delete detaches.
    det_path = os.path.join(folder, "i77_detach.FCStd")
    s = Session(det_path, fresh=True)
    try:
        ops_rm = (
            _board("t3", [100, 0, 0], [40, 40, 20])
            + _board("x_leg", [0, 10, 0], [20, 20, 20])
            + [{"id": "f_x", "type": "fit", "body": "x_leg", "target_body": "t3", "axis": 0,
                "face": {"normal": [1, 0, 0], "point": [140, 0, 0]}, "fit_mode": 0}]
        )
        s.sync(ops_rm)
        check("I77 initial fit reaches x=140",
              abs(s.model.world_shape(s.model.body("x_leg")).BoundBox.XMax - 140.0) < 0.01)

        cut_ops = ops_rm + _cut("c_rm", "t3", [120, 0, 20], [20, 40], depth=20)
        s.sync(cut_ops)
        tip = s.model.body("x_leg").Tip
        bj_cut = _bodies_json(s, os.path.join(folder, "out_cut_detach"))
        check("I77 cutting away fitted face detaches, keeps length, clears message, marks bodies.json",
              tip.SSTargetId == ""
              and tip.SSFitResult == ""
              and abs(s.model.world_shape(s.model.body("x_leg")).BoundBox.XMax - 140.0) < 0.01
              and bj_cut["x_leg"]["stock_frame"].get("fit_state") == "detached",
              (tip.SSTargetId, repr(tip.SSFitResult), bj_cut["x_leg"]["stock_frame"].get("fit_state")))

        s.save()
    finally:
        s.close()

    s = Session(det_path)
    try:
        tip = s.model.body("x_leg").Tip
        bj_det_reopen = _bodies_json(s, os.path.join(folder, "out_det_reopen"))
        check("I77 save and reopen preserves detached fit state and length",
              tip.SSTargetId == ""
              and tip.SSFitResult == ""
              and abs(s.model.world_shape(s.model.body("x_leg")).BoundBox.XMax - 140.0) < 0.01
              and bj_det_reopen["x_leg"]["stock_frame"].get("fit_state") == "detached")

        # Undo the cut -> fit comes back!
        s.sync(ops_rm)
        tip = s.model.body("x_leg").Tip
        bj_undo = _bodies_json(s, os.path.join(folder, "out_undo_cut"))
        check("I77 Undo of the cut brings the fit back",
              tip.SSTargetId == "t3"
              and bj_undo["x_leg"]["stock_frame"].get("fit_state") == "live"
              and abs(s.model.world_shape(s.model.body("x_leg")).BoundBox.XMax - 140.0) < 0.01,
              (tip.SSTargetId, bj_undo["x_leg"]["stock_frame"].get("fit_state")))

        # Delete target -> fit detaches gently
        s.sync(ops_rm + [{"id": "del_t3", "type": "delete", "targets": ["t3"]}])
        tip = s.model.body("x_leg").Tip
        bj_del = _bodies_json(s, os.path.join(folder, "out_del_detach"))
        check("I77 deleting target detaches fit, keeps length, clears message, marks bodies.json",
              tip.SSTargetId == ""
              and tip.SSFitResult == ""
              and abs(s.model.world_shape(s.model.body("x_leg")).BoundBox.XMax - 140.0) < 0.01
              and bj_del["x_leg"]["stock_frame"].get("fit_state") == "detached")
    finally:
        s.close()

    # 4. G04 + I77: a fit to a cut target follows when the target is lengthened (pocket away from fitted face).
    s = Session(os.path.join(folder, "cut_lengthen.FCStd"), fresh=True)
    try:
        from object_properties import inspect
        ops_len = (
            _board("t3", [100, 0, 0], [40, 40, 20])
            + _board("x_leg", [0, 10, 0], [20, 20, 20])
            + [{"id": "f_x", "type": "fit", "body": "x_leg", "target_body": "t3", "axis": 0,
                "face": {"normal": [1, 0, 0], "point": [140, 0, 0]}, "fit_mode": 0}]
            + _cut("c_pkt", "t3", [110, 10, 20], [10, 10], depth=5)
        )
        s.sync(ops_len)
        rect_obj = next(
            ob for ob in inspect(s.model, "t3")["objects"]
            if any(f["path"] == "Length" and f["editable"] for f in ob["fields"])
        )
        len_field = next(f for f in rect_obj["fields"] if f["path"] == "Length")
        s.sync(ops_len + [{
            "id": "pe_len", "type": "property_edit", "body": "t3", "object": rect_obj["name"],
            "property": "Length", "value": "60mm", "mode": "value",
            "expected": {"value": len_field["value"], "expression": len_field["expression"]},
        }])
        tip = s.model.body("x_leg").Tip
        leg_xmax = s.model.world_shape(s.model.body("x_leg")).BoundBox.XMax
        t3_xmax = s.model.world_shape(s.model.body("t3")).BoundBox.XMax
        check("G04 fit follows lengthened cut target and stays live",
              tip.SSTargetId == "t3"
              and abs(t3_xmax - 160.0) < 0.01
              and abs(leg_xmax - 160.0) < 0.01,
              (tip.SSTargetId, t3_xmax, leg_xmax, tip.SSFitResult))
    finally:
        s.close()

    print(f"PLANE FIT TESTS: {R[0]} passed, {R[1]} failed", flush=True)


if __name__ == "__main__" or any(os.path.basename(a) == Path(__file__).name for a in sys.argv):
    main()
