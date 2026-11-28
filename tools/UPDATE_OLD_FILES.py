"""One-time updater for pre-H199 saved files (.FCStd and .json).

Usage:
  python3 tools/UPDATE_OLD_FILES.py [paths...]
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
from update_old_files import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
