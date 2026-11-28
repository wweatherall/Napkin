#!/usr/bin/env python3
"""Run the hopper (H185): launch one worker at a time, wake the integrator when the batch is done or needs help."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import job

sys.exit(job.main(["hopper", *sys.argv[1:]]))
