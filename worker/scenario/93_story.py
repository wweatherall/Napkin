"""---------- the cumulative story: steps one after another, as a person would ---------- (T76)."""
import json
import os
import traceback
from session import Session
from export import write_glb
from scenario.context import diff, snap

requires = ('20_push.py', '30_linked_edits.py', '60_material_grain.py', '70_assembly.py', '80_new_boards.py', '90_mirrored_hole.py', '92_visibility.py')

def run(ctx):
    FIX = ctx.FIX
    S = ctx.S
    S0 = ctx.S0
    TESTDIR = ctx.TESTDIR
    check = ctx.check
    FRONT = ctx.actions['FRONT']
    THICK = ctx.actions['THICK']
    BUMP = ctx.actions['BUMP']
    PAINT = ctx.actions['PAINT']
    GRAIN = ctx.actions['GRAIN']
    ASM = ctx.actions['ASM']
    POSTS = ctx.actions['POSTS']
    HOLE_L = ctx.actions['HOLE_L']
    HIDE = ctx.actions['HIDE']
    UNHIDE = ctx.actions['UNHIDE']

    # ---------- the cumulative story: steps one after another, as a person would ----------
    STORY = FIX + [FRONT, THICK] + BUMP + [PAINT, GRAIN] + ASM + POSTS + HOLE_L + [HIDE, UNHIDE]
    try:
        S.sync(STORY)
        bad = [(e["id"], e.get("message")) for e in S.status() if e["status"] != "ok"]
        check("story: every action accepted", not bad, bad)
        live = snap(S)
        f = Session(None)
        f.sync(STORY)
        fresh = snap(f)
        f.close()
        check("story: live session equals a fresh build", live == fresh, diff(fresh, live))
        S.save()
        path = S.path
        S.close()
        S = Session(path)
        check("story: reopened file equals the live session", snap(S) == live, diff(live, snap(S)))
        import zipfile
        import xml.etree.ElementTree as ET
        gui = ET.fromstring(zipfile.ZipFile(path).read("GuiDocument.xml"))
        vis = {vp.get("name"): vp.find(".//Property[@name='Visibility']/Bool").get("value") for vp in gui.iter("ViewProvider")}
        names = {bid: o.Name for bid, o in S.model.bodies().items()}
        glb = os.path.join(TESTDIR, "story.glb")
        write_glb(S.model, glb)
        gjs = json.loads(open(glb, "rb").read()[20:20 + int.from_bytes(open(glb, "rb").read()[12:16], "little")])
        in_glb = {n["name"] for n in gjs.get("nodes", [])}
        check("story: the Blender export leaves out the hidden bottom", "bottom" not in in_glb and {"left", "shelf"} <= in_glb, sorted(in_glb))
        check("story: FreeCAD's view part hides the hidden bottom and shows the rest",
              vis.get(names["bottom"]) == "false" and all(vis.get(names[k]) == "true" for k in ("left", "shelf", "shelf2", "post")),
              {k: vis.get(n) for k, n in names.items()})
        check("story: no invalid FreeCAD objects", not [o.Name for o in S.doc.Objects if "Invalid" in o.State])
        how, _ = S.sync(FIX)
        check("story: undo back to the fixture after reopening", snap(S) == S0, (how, diff(S0, snap(S))))
    except Exception:
        check("story: ran without an error", False, traceback.format_exc(limit=3))
    finally:
        ctx.S = S  # Keep the reopened fixture available to later discovered features.
