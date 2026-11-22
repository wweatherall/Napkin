# runner: none (a helper the worker tests import, not a test)
"""Configure the FreeCAD test runtime before tests import worker modules explicitly.

freecadcmd does not put a script's folder on sys.path; callers add worker/ first.
Named test_* so this helper stays out of the worker's hash and the app bundle.
"""
import sys

sys.dont_write_bytecode = True
