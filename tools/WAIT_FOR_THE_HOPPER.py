#!/usr/bin/env python3
"""Wait for the next hopper wake condition (H196) and exit when one arrives, without launching anything."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import job

sys.exit(job.main(["hopper-wait", *sys.argv[1:]]))
