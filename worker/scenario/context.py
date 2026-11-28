"""T48 scenario test: one session, one busy fixture model, many operations against it.

  TESTDIR=/tmp/scenario freecadcmd worker/test_scenario.py

The fixture (tests/scenario_fixture.json: a carcass with a mirror group, pin-hole array, through-hole, linked
shelf, paint) is built once. Each step syncs fixture + its ops, checks its own answer by name, then syncs back to
the fixture (FreeCAD undo, A23) and checks the model is exactly the fixture again, so one failing step can't spoil
the next. A cumulative story at the end chains several steps and must equal a fresh build and survive a reopen.
Exceptions are caught per step (freecadcmd reruns a script that raises)."""
import json
import os
import sys
import time
import traceback

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from export import material_of
from session import Session

def shown_in_freecad(m, obj):
    """What FreeCAD's window would show of this board (T28, T29): the board itself, and its current solid alone
    among its steps (FreeCAD's undo doesn't take back Visibility, so the worker sets it after each sync)."""
    dfn = m.definition(obj)
    steps = [o.Name for o in getattr(dfn, "Group", []) if o.isDerivedFrom("Part::Feature") and o.Visibility]
    tip = getattr(dfn, "Tip", None)
    return (bool(obj.Visibility), steps == ([tip.Name] if tip is not None else steps))

def snap(sess):
    """Every board: volume, world box, material, grain (in its own frame); and every group's members."""
    m = sess.model
    out = {}
    for bid, obj in m.bodies().items():
        sh = m.world_shape(obj)
        bb = sh.BoundBox
        g = m.grain_local(m.definition(obj))
        out[bid] = {"vol": round(sh.Volume, 2),
                    "box": tuple(round(v, 3) for v in (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)),
                    "mat": material_of(m, obj), "grain": tuple(round(abs(v), 3) for v in (g.x, g.y, g.z)),
                    "hidden": bool(getattr(obj, "SSHidden", False)), "shown": shown_in_freecad(m, obj)}
    groups = {k: sorted(getattr(o, "BodyId", "") for o in g.Group) for k, g in m.assemblies().items()}
    return {"boards": out, "groups": groups}

def face(body, normal, point):
    return {"body": body, "normal": list(normal), "point": list(point)}

def on_rect(rid, body, normal, point, size):
    return {"id": rid, "type": "rect", "plane": {"on": face(body, normal, point)}, "size": size}

def diff(a, b):
    """Boards whose snapshot differs: {id: (before, after)}."""
    ids = set(a["boards"]) | set(b["boards"])
    return {i: (a["boards"].get(i), b["boards"].get(i)) for i in ids if a["boards"].get(i) != b["boards"].get(i)}

def ok(st, n):
    """The last n ops were accepted."""
    tail = st[-n:]
    return ("accepted", all(e["status"] == "ok" for e in tail), [(e["id"], e["status"], e.get("message")) for e in tail])

def only(before, after, ids):
    """Every board not in ids is untouched."""
    others = {k: v for k, v in diff(before, after).items() if k not in ids}
    return ("nothing else changed", not others, others)

class Scenario:
    """One fixture, live session, assertion totals and explicitly shared story actions."""

    def __init__(self):
        self.T0 = time.perf_counter()
        self.TESTDIR = os.environ.get("TESTDIR", "/tmp/napkin-scenario")
        os.makedirs(self.TESTDIR, exist_ok=True)
        self.FIX = json.load(open(os.path.join(HERE, "..", "tests", "scenario_fixture.json")))["ops"]
        self.R = [0, 0]

        # ---------- the fixture ----------
        self.S = Session(os.path.join(self.TESTDIR, "scenario.FCStd"), fresh=True)
        self.S.sync(self.FIX)
        bad = [(e["id"], e.get("message")) for e in self.S.status() if e["status"] != "ok"]
        self.check("fixture: every op accepted", not bad, bad)
        self.S0 = snap(self.S)
        self.B0 = self.S0["boards"]
        self.check("fixture: five boards", set(self.B0) == {"left", "right", "bottom", "shelf", "shelf2"}, sorted(self.B0))
        self.PIN = 6 * 6 * 12
        self.check("fixture: left side has five pin holes", abs(self.B0["left"]["vol"] - (18 * 400 * 720 - 5 * self.PIN)) < 0.1, self.B0["left"])
        self.check("fixture: right side mirrors the left (same volume, x 582..600)",
              self.B0["right"]["vol"] == self.B0["left"]["vol"] and self.B0["right"]["box"][0] == 582 and self.B0["right"]["box"][3] == 600, self.B0["right"])
        self.check("fixture: bottom has its through-hole", abs(self.B0["bottom"]["vol"] - (564 * 400 - 1600) * 18) < 0.1, self.B0["bottom"])
        self.check("fixture: linked shelf copy 180 mm above", self.B0["shelf2"]["box"][2] == self.B0["shelf"]["box"][2] + 180, self.B0["shelf2"])
        self.check("fixture: bottom is white oak", self.B0["bottom"]["mat"] == "white-oak", self.B0["bottom"]["mat"])
        self.check("fixture: sides form a mirror group", self.S0["groups"].get("sides") == ["left", "right"], self.S0["groups"])
        self.T_FIX = time.perf_counter() - self.T0

        self.STEP_MS = []
        self.actions = {}

    def check(self, name, cond, detail=""):
        self.R[0 if cond else 1] += 1
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"), flush=True)

    def fix_with(self, op_id, **changes):
        """The fixture with one of its own ops retyped (an amend, like typing a new count right after)."""
        return [dict(o, **changes) if o["id"] == op_id else o for o in self.FIX]

    def step(self, name, ops, expect):
        """Run fixture-relative ops, hand (statuses, before, after) to `expect`, which returns [(check, cond, detail)];
        then go back to the fixture and check nothing is left over."""
        t = time.perf_counter()
        try:
            self.S.sync(ops)
            st = self.S.status()
            for sub, cond, detail in expect(st, self.S0, snap(self.S)):
                self.check(f"{name}: {sub}", cond, detail)
        except Exception:
            self.check(f"{name}: ran without an error", False, traceback.format_exc(limit=3))
        try:
            how, _ = self.S.sync(self.FIX)
            after = snap(self.S)
            self.check(f"{name}: back to the fixture by undo", after == self.S0 and how != "rebuilt", (how, diff(self.S0, after)))
        except Exception:
            self.check(f"{name}: back to the fixture", False, traceback.format_exc(limit=3))
        self.STEP_MS.append((name, round((time.perf_counter() - t) * 1000)))
