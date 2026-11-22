"""T48/T76 scenario entry point; numbered feature files run in lexical order.

Add worker/scenario/NN_feature.py with run(ctx). Declare requires = ("NN_other.py",)
when reading ctx.actions from an earlier feature; discovery validates every dependency
before opening the fixture. No shared feature list needs editing.
"""
import importlib.util
from pathlib import Path
import sys
import time
import traceback

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_load  # Configure FreeCAD before loading the scenario runtime.
from scenario.context import Scenario


def discover(folder):
    paths = sorted(folder.glob("[0-9][0-9]_*.py"))
    if not paths:
        raise ValueError("no numbered scenario feature files found")
    modules = []
    seen = set()
    for path in paths:
        spec = importlib.util.spec_from_file_location("scenario." + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for required in getattr(module, "requires", ()):
            if required not in seen:
                raise ValueError(f"{path.name}: required earlier feature {required} is missing or out of order")
        if not callable(getattr(module, "run", None)):
            raise ValueError(f"{path.name}: missing run(ctx)")
        seen.add(path.name)
        modules.append(module)
    return modules


def main():
    ctx = None
    try:
        modules = discover(HERE / "scenario")
        ctx = Scenario()
        for module in modules:
            module.run(ctx)
        total = time.perf_counter() - ctx.T0
        slow = sorted(ctx.STEP_MS, key=lambda x: -x[1])[:3]
        print(f"timing: fixture {ctx.T_FIX:.1f} s, {len(ctx.STEP_MS)} steps {sum(ms for _, ms in ctx.STEP_MS) / 1000:.1f} s, total {total:.1f} s; slowest {slow}")
    except Exception:
        if ctx is None:
            print("FAIL scenario discovery/setup: " + traceback.format_exc(limit=4), flush=True)
            print("SCENARIO TESTS: 0 passed, 1 failed")
            return
        ctx.check("scenario runner: ran without an error", False, traceback.format_exc(limit=4))
    finally:
        if ctx is not None:
            ctx.S.close()
    print(f"SCENARIO TESTS: {ctx.R[0]} passed, {ctx.R[1]} failed")


main()
