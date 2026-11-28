#!/usr/bin/env python3
"""Print what the integrator did on William's standing permissions (P79, P80): `--clear` empties it once read;
`add "<line>"` adds one (an answer the integrator gave a worker in William's place, say)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import job

sys.exit(job.main(["digest", *sys.argv[1:]]))
