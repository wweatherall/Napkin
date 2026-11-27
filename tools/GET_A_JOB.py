#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import job

sys.exit(job.main(["take", *sys.argv[1:]]))
