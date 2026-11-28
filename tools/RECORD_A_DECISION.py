#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import log

args = sys.argv[1:]
if args[:1] == ["add"]:     # `RECORD_A_DECISION.py add tunable ...` means the same as without the `add` (H201)
    args = args[1:]
sys.exit(log.main(["add", *args]))
