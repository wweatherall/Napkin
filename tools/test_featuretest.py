#!/usr/bin/env python3
"""Checks T95: tools/featuretest.sh finds the test files itself. --list names every test it ran before T95 (and
nothing it shouldn't); in a throwaway copy, a new test file is picked up with no other edit, a `runner:` line is
obeyed, and a file that prints no summary line fails by name.
Summary line: FEATURETEST TESTS: N passed, M failed."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "tools", "featuretest.sh")
RESULTS = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    if not ok or VERBOSE:
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
    folder = f.split("/", 1)[0]
    expected_name = f"{folder}-{os.path.splitext(os.path.basename(f))[0].removeprefix('test_')}"
    hit = [l for l in lines if l.endswith(" " + key) or (" " + key + " ") in l or l.endswith(key)]
    check(f"--list runs {f} with {runner}", rc == 0 and hit and hit[0].split()[0] == expected_name and runner in hit[0], out)
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
    shutil.copy(os.path.join(ROOT, "tools", "gate.sh"), os.path.join(tmp, "tools"))
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
    check("a file that prints no summary line fails, by name", rc != 0 and "tools-silent did not finish" in out, out)
    os.remove(os.path.join(tmp, "tools", "test_silent.py"))
    with open(os.path.join(tmp, "tools", "test_broken.py"), "w") as f:
        f.write('print("BROKEN TESTS: 1 passed, 1 failed")\n')
    rc, out = run(fake, outdir)
    check("a summary with failures fails the run", rc != 0 and "BROKEN TESTS: 1 passed, 1 failed" in out, out)
    os.remove(os.path.join(tmp, "tools", "test_broken.py"))
    with open(os.path.join(tmp, "tools", "test_exit.py"), "w") as f:
        f.write('import sys\nprint("EXAMPLE TESTS: 1 passed, 0 failed")\nsys.exit(7)\n')
    rc, out = run(fake, outdir)
    check("a passing summary with a non-zero exit fails, by name", rc != 0 and "[tools-exit] exited 7" in out, out)
    os.remove(os.path.join(tmp, "tools", "test_exit.py"))
    # Stand-in pair of the same basename in worker/ and viewport/ keeps two separate logs (H123).
    with open(os.path.join(tmp, "worker", "test_same.py"), "w") as f:
        f.write('# runner: python3\nprint("WORKER SAME TESTS: 1 passed, 0 failed")\n')
    with open(os.path.join(tmp, "viewport", "test_same.gd"), "w") as f:
        f.write('# runner: python3\nprint("VIEWPORT SAME TESTS: 2 passed, 0 failed")\n')
    rc, out = run(fake, "--list")
    check("stand-in pair gets distinct folder-prefixed names in --list",
          rc == 0 and "worker-same " in out and "viewport-same " in out, out)
    pair_out = os.path.join(tmp, "pair-out")
    rc, out = run(fake, pair_out)
    check("stand-in pair keeps two separate logs and reports both summaries",
          rc == 0 and "WORKER SAME TESTS: 1 passed, 0 failed" in out
          and "VIEWPORT SAME TESTS: 2 passed, 0 failed" in out
          and os.path.isfile(os.path.join(pair_out, "worker-same.log"))
          and os.path.isfile(os.path.join(pair_out, "viewport-same.log")), out)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# 3. T106: exercise the real shell entry points with stand-ins for Godot and FreeCAD.
# The stand-in reads the gate's redirected output before it can finish its stage.
def executable(path, body):
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(0o755)


with tempfile.TemporaryDirectory(prefix="script-tests-", dir=os.environ.get("TESTDIR")) as folder:
    base = Path(folder).resolve()
    main, job, custom = base / "main", base / "job", base / "custom temp"
    main.mkdir()
    custom.mkdir()
    scripts = main / "tools"
    scripts.mkdir()
    for name in ("gate", "quicktest", "fulltest", "featuretest", "parsecheck"):
        source = (Path(ROOT) / "tools" / (name + ".sh")).read_text()
        source = re.sub(r"^GD=/Applications/.*$", "GD=tools/fake-godot", source, flags=re.M)
        source = re.sub(r"^FC=/Applications/.*$", "FC=tools/fake-worker", source, flags=re.M)
        executable(scripts / (name + ".sh"), source)
    (scripts / "job.py").write_text("")
    (scripts / "compare_suites.py").write_text("")
    (scripts / "test_sample.py").write_text('print("SAMPLE TESTS: 2 passed, 0 failed")')
    executable(scripts / "fake-worker", 'echo 1234 > "$SERVE_PORT_FILE"\nexec sleep 30\n')
    executable(scripts / "fake-godot", """case " $* " in
  *" --headless "*) exit 0 ;;
  *" --quicktest "*) stage="quick: viewport tests started" ;;
  *) stage="full: viewport suites started" ;;
esac
for ((i=0; i<100; i++)); do
  if grep -Fxq "$stage" "$PROGRESS"; then echo "QUICK 1 passed, 0 failed in 0.1 s"; exit 0; fi
  sleep 0.05
done
exit 1
""")
    # Record actual allocations, including the parse folder that parsecheck removes before returning.
    executable(scripts / "mktemp", f'''dir=$("{shutil.which("mktemp")}" "$@") || exit 1
echo "$dir" >> "$ALLOCATIONS"
echo "$dir"
''')
    def git(*args):
        subprocess.run(["git", *args], cwd=main, check=True, capture_output=True)

    git("init", "-q")
    git("add", "tools")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
    git("worktree", "add", "-q", "--detach", str(job))
    defaults = subprocess.run(
        ["bash", "-c", 'unset TMPDIR; . tools/gate.sh; set_test_tmpdir /tmp; echo "$TEST_TMPDIR"; '
                       'set_test_tmpdir; echo "$TEST_TMPDIR"; test -z "$TMPDIR"'],
        cwd=main, capture_output=True, text=True)
    platform_tmp = subprocess.run(["getconf", "DARWIN_USER_TEMP_DIR"], capture_output=True, text=True)
    check("with TMPDIR unset the main gate and its children keep their original defaults",
          defaults.returncode == 0 and defaults.stdout.splitlines() == ["/tmp", platform_tmp.stdout.strip() or "/tmp"],
          defaults.stdout)
    nested = job / "scratch" / "custom temp"
    nested.mkdir(parents=True)
    for checkout, tmpdir, expected in ((main, custom, custom), (job, custom, job / "scratch"), (job, nested, nested)):
        progress, allocations = base / "progress", base / "allocations"
        allocations.write_text("")
        env = dict(os.environ, TMPDIR=str(tmpdir), PROGRESS=str(progress), ALLOCATIONS=str(allocations),
                   PATH=str(checkout / "tools") + os.pathsep + os.environ["PATH"])
        with progress.open("w") as log:
            gate = subprocess.run(["tools/gate.sh"], cwd=checkout, env=env, stdout=log,
                                  stderr=subprocess.STDOUT, timeout=45)
        output = progress.read_text()
        label = f"{checkout.name}, TMPDIR={tmpdir.relative_to(base)}"
        stages = re.findall(r"^gate: .+$", output, re.M)
        check(f"gate stages arrive live and in order ({label})",
              gate.returncode == 0 and re.fullmatch(
                  r"gate: quick test started\ngate: quick test passed in \d+ s\n"
                  r"gate: full test started\ngate: full test passed in \d+ s", "\n".join(stages)), output)
        gate_dirs = list(map(Path, allocations.read_text().splitlines()))
        gate_dir = next(d for d in gate_dirs if d.name.startswith("shopsketch-gate."))
        quick_last = (gate_dir / "quick.log").read_text().splitlines()[-1]
        full_last = (gate_dir / "full.log").read_text().splitlines()[-1]
        check(f"quick, full and gate keep their final summaries ({label})",
              quick_last.startswith("features: SAMPLE TESTS: 2 passed, 0 failed | viewport: QUICK 3 passed, 0 failed")
              and full_last.startswith("full check logs: ") and output.splitlines()[-1].startswith(
                  "GATE PASS: full test passes; QUICK 3 passed, 0 failed"), output)
        standalone = subprocess.run(["tools/featuretest.sh"], cwd=checkout, env=env,
                                    capture_output=True, text=True, timeout=30)
        paths = list(map(Path, allocations.read_text().splitlines()))
        check(f"all five script folders use the expected parent ({label})",
              standalone.returncode == 0 and {d.name.split(".")[0] for d in paths} ==
              {"shopsketch-" + name for name in ("gate", "parse", "quick", "full", "feature")}
              and all(d.parent == expected for d in paths), paths)

print(f"FEATURETEST TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
raise SystemExit(0 if all(RESULTS) else 1)   # a failed check fails the run, not only its summary
