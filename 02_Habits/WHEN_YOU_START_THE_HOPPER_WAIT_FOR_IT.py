#!/usr/bin/env python3
"""Start the hopper if none is running, then wait for its next pause (William, 2026-11-28).

The integrator runs this in the background instead of RUN_THE_HOPPER.py --window plus WAIT_FOR_THE_HOPPER.py: a
hopper that pauses with no WAIT_FOR_THE_HOPPER running launches a new integrator (P74), and on 2026-11-28 that
started a second integrator beside a live one. Doing both in one command means the wait can't be forgotten.
Run outside the sandbox (it opens a Terminal window and writes .git/). Exits when the hopper's next pause comes;
run it again after each."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import job

root = job.main_root(os.getcwd())
pid = job._running_hopper_pid(root)
if pid is None:
    rc = job.hopper(root, window=True)
    if rc != 0:
        sys.exit(rc)
else:
    print(f"hopper already running (pid {pid})", flush=True)
sys.exit(job.main(["hopper-wait", *sys.argv[1:]]))
