#!/usr/bin/env python3
"""Checks T95: tools/featuretest.sh finds the test files itself. --list names every test it ran before T95 (and
nothing it shouldn't); in a throwaway copy, a new test file is picked up with no other edit, a `runner:` line is
obeyed, and a file that prints no summary line fails by name.
Summary line: FEATURETEST TESTS: N passed, M failed."""
import os
import shutil
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "tools", "featuretest.sh")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {detail}"))


def run(cwd_script, *args):
    p = subprocess.run(["bash", cwd_script, *args], capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout + p.stderr


# 1. The real list: every file featuretest.sh named by hand before T95, each run the same way.
BEFORE = {
    "worker/test_native.py": "freecadcmd", "worker/test_runs.py": "freecadcmd",
    "worker/test_arrays.py": "freecadcmd", "worker/test_combos.py": "freecadcmd",
    "worker/test_properties.py": "freecadcmd", "worker/test_scenario.py": "freecadcmd",
    "worker/test_length_input.py": "freecadcmd", "worker/test_length_protocol.py": "python3",
    "worker/test_serve.py": "python3", "viewport/test_units.gd": "Godot", "viewport/test_document.gd": "Godot",
    "viewport/test_selection.gd": "Godot", "viewport/test_tools.gd": "Godot",
    "viewport/test_tool_context.gd": "Godot", "tools/test_sort_decision_log.py": "python3",
    "tools/test_log_archive.py": "python3", "tools/test_job.py": "python3", "tools/test_log.py": "python3",
    "tools/test_bookkeeping.py": "python3", "tools/test_number_ids.py": "python3",
    "tools/test_startup.py": "python3", "tools/test_integrator.py": "python3", "tools/test_integrate.py": "python3",
}
rc, out = run(SCRIPT, "--list")
lines = [l for l in out.splitlines() if l.strip()]
for f, runner in BEFORE.items():
    key = "res://" + f[len("viewport/"):] if f.startswith("viewport/") else f
    hit = [l for l in lines if l.endswith(" " + key) or (" " + key + " ") in l or l.endswith(key)]
    check(f"--list runs {f} with {runner}", rc == 0 and hit and runner in hit[0], out)
for helper in ("worker/test_load.py", "worker/test_native_common.py", "tools/test_check_architecture.py"):
    check(f"--list leaves out {helper} (runner: none)", not any(l.endswith(helper) for l in lines), out)
found = set()
for l in lines:
    path = l.split()[-1]
    found.add(("viewport/" + path[len("res://"):]) if path.startswith("res://") else path)
# Files added since the hand list (T95 found tools/test_follow_ups.py, never listed): shown, not checked, so a new
# test needs no edit here.
print("found beyond the pre-T95 list: " + ", ".join(sorted(found - set(BEFORE))))

# 2. A throwaway copy: a new file is picked up, a runner line is obeyed, a silent file fails by name.
tmp = tempfile.mkdtemp(prefix="featuretest-")
try:
    for d in ("tools", "worker", "viewport"):
        os.makedirs(os.path.join(tmp, d))
    shutil.copy(SCRIPT, os.path.join(tmp, "tools", "featuretest.sh"))
    with open(os.path.join(tmp, "tools", "test_sample.py"), "w") as f:
        f.write('print("SAMPLE TESTS: 2 passed, 0 failed")\n')
    with open(os.path.join(tmp, "worker", "test_plain.py"), "w") as f:
        f.write('# runner: python3\nprint("PLAIN TESTS: 1 passed, 0 failed")\n')
    with open(os.path.join(tmp, "worker", "test_helper.py"), "w") as f:
        f.write('# runner: none\nraise SystemExit(1)\n')
    fake = os.path.join(tmp, "tools", "featuretest.sh")
    rc, out = run(fake, "--list")
    check("a new tools/test_*.py is listed with no other edit", "python3 tools/test_sample.py" in out, out)
    check("a `runner: python3` line overrides the worker folder's freecadcmd", "python3 worker/test_plain.py" in out, out)
    check("a `runner: none` file is left out", "test_helper" not in out, out)
    outdir = os.path.join(tmp, "out")
    rc, out = run(fake, outdir)
    check("all passing: exit 0 and both summaries in the features line",
          rc == 0 and "SAMPLE TESTS: 2 passed, 0 failed" in out and "PLAIN TESTS: 1 passed, 0 failed" in out, out)
    with open(os.path.join(tmp, "tools", "test_silent.py"), "w") as f:
        f.write('print("all fine, honest")\n')
    rc, out = run(fake, outdir)
    check("a file that prints no summary line fails, by name", rc != 0 and "silent did not finish" in out, out)
    os.remove(os.path.join(tmp, "tools", "test_silent.py"))
    with open(os.path.join(tmp, "tools", "test_broken.py"), "w") as f:
        f.write('print("BROKEN TESTS: 1 passed, 1 failed")\n')
    rc, out = run(fake, outdir)
    check("a summary with failures fails the run", rc != 0 and "BROKEN TESTS: 1 passed, 1 failed" in out, out)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"FEATURETEST TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
