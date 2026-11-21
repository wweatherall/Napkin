"""For the worker tests: every worker module's public names in one place, as the single replay.py used to give.

  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  from test_load import *

(freecadcmd doesn't put a script's folder on sys.path, hence the first line.) Named test_* so it stays out of the
worker's hash and the app bundle."""
import sys

sys.dont_write_bytecode = True
from common import *    # noqa: E402,F401,F403
from push import *      # noqa: E402,F401,F403
from move import *      # noqa: E402,F401,F403
from mirror import *    # noqa: E402,F401,F403
from assembly import *  # noqa: E402,F401,F403
from paint import *     # noqa: E402,F401,F403
from model import *     # noqa: E402,F401,F403
from export import *    # noqa: E402,F401,F403
from session import *   # noqa: E402,F401,F403
from serve import *     # noqa: E402,F401,F403
