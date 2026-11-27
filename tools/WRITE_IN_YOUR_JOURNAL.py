#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import personal_space

sys.exit(personal_space.main(["journal", *sys.argv[1:]]))
