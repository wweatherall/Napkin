#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handoff

sys.argv[1:1] = ["archive"]
handoff.main()
