"""Shop Sketch worker: keeps a live FreeCAD document and edits it with native features.

The FreeCAD file is the model (A21). Every Shop Sketch action becomes ordinary FreeCAD
features inside it - Part::Plane, Part::Extrusion, Part::Cut / Part::MultiFuse, App::Part
placements, App::Link, Part::Mirroring - committed as one FreeCAD undo transaction.
All Shop Sketch state lives on those objects (BodyId / SSRole / RectId ... properties),
so FreeCAD's undo, a save, a reopen or an edit made in FreeCAD all stay consistent.

Run with:
  SERVE_PORT=7878 freecadcmd replay.py            long-running worker (newline JSON over TCP)
  SERVE_PORT=0 SERVE_PORT_FILE=f freecadcmd replay.py   on a free port it picks itself, written to f (T47)
  OPLOG=ops.json OUTDIR=out freecadcmd replay.py  one-off: build out/model.FCStd from an op log

Writes beside the model:
  model.FCStd                the document (autosaved atomically after every change)
  model.shopsketch.json      journal: the op list, statuses, revision, file hash
and into the output folder:
  bodies.json  status.json  meshes/<board>-<key>.bin (one per board, rewritten only when it changes)
  model.glb at each autosave (views.json when a drawing is asked for)

The code is split by job (T42): common.py (shared basics), model.py (the document and building blocks), one file
per kind of action (push.py, move.py, ...: found by model.action_mixins), export.py (what the viewport reads),
session.py (sync, undo, journal, saves) and serve.py (the connection loop). This file only starts it.
"""
import os
import sys

sys.dont_write_bytecode = True     # no __pycache__ beside the scripts (inside the signed app bundle)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from serve import main  # noqa: E402

main()
