#!/usr/bin/env python3
"""Merge every done job in stacking order with one review pause and one gate at the end (H185)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integrate

sys.exit(integrate.main(["--batch", *sys.argv[1:]]))
