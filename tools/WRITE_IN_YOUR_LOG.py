#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integrator
import personal_space

if len(sys.argv) == 1 or sys.argv[1] in ("-h", "--help"):
    sys.exit(personal_space.main(["--help"]))
if len(sys.argv) == 2:
    sys.exit(integrator.main(["note", sys.argv[1]]))
sys.exit(personal_space.main(["log", *sys.argv[1:]]))
