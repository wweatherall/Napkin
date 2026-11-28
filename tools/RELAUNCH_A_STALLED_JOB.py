#!/usr/bin/env python3
"""Relaunch a stalled job's session with full permissions (P79): `<job id> <your session>`; the lock holder only."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import job

sys.exit(job.main(["relaunch", *sys.argv[1:]]))
