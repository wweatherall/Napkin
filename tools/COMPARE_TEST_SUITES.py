#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare_suites

sys.exit(compare_suites.main(sys.argv[1:]))
