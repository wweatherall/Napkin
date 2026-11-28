#!/usr/bin/env python3
"""Show the job queue as a three-part ASCII picture (H203): hopper, workbench, integrator's desk.

  python3 tools/SHOW_THE_HOPPER.py [--watch]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import hopper_picture


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "-h" in argv or "--help" in argv:
        print(__doc__.strip())
        return 0
    if "--watch" in argv:
        try:
            hopper_picture.watch(os.getcwd())
        except KeyboardInterrupt:
            return 0
        return 0
    print(hopper_picture.render_root(os.getcwd()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
