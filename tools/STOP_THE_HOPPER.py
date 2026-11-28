#!/usr/bin/env python3
"""Stop the running hopper: the integrator's kill switch (`STOP_THE_HOPPER.py <your session name>`, job.py hopper-stop).
Only the session holding the integrator lock may; workers already running carry on."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import job

sys.exit(job.main(["hopper-stop", *sys.argv[1:]]))
