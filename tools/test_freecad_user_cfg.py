"""H208: FreeCAD subprocesses carry isolated config paths and the app seeds its copy once."""
import ast
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
GODOT = "/Applications/Godot.app/Contents/MacOS/Godot"
passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        print(f"FAIL {name}: {detail}")


# The shell entry points use $FC for FreeCAD. Include command literals as well,
# so a new launch can fail this check without having to be added to a list of lines.
for name in ("common.sh", "tools/featuretest.sh", "tools/fulltest.sh", "tools/RUN_ONE_TEST.sh"):
    commands = re.findall(
        r'(?mi)(?:^[ \t]*|(?<=\$\())(?:"?\$\{?FC\}?"?|"?[^\s"=]*\bfreecadcmd"?)[ \t]+([^\n]+)',
        (ROOT / name).read_text(),
    )
    # common.sh's list of executable candidates also spans several lines.
    commands = [args for args in commands if args.strip() != "\\"]
    check(f"every FreeCAD command in {name} has -u and -s",
          (bool(commands) or name == "tools/RUN_ONE_TEST.sh")
          and all("-u " in args and "-s " in args for args in commands), commands)

# Catch direct FreeCAD argv lists, including new calls that bypass the test helper.
for path in [ROOT / "tools" / name for name in ("length_cases.py", "job.py")] + sorted((ROOT / "worker").glob("test_*.py")):
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, (ast.List, ast.Tuple)) or not node.elts:
            continue
        exe = node.elts[0]
        if not ((isinstance(exe, ast.Name) and exe.id in ("FC", "freecad", "freecad_path"))
                or (isinstance(exe, ast.Constant) and isinstance(exe.value, str)
                    and exe.value.lower().endswith("/freecadcmd"))):
            continue
        literals = {arg.value for arg in node.elts if isinstance(arg, ast.Constant)}
        check(f"FreeCAD argv in {path.name}:{node.lineno} has -u and -s",
              {"-u", "-s"} <= literals, literals)

worker_process = (ROOT / "viewport/worker_process.gd").read_text()
launches = [line.split("#", 1)[0].strip() for line in worker_process.splitlines() if re.search(r"OS\.(create_process|execute)\(", line)]
check("both Godot launch paths use the config argument list",
      launches == ['worker_pid = OS.create_process(freecad_path, args)',
                   'worker_pid = OS.create_process("/bin/sh", shell_args)']
      and 'shell_args.append_array(args)' in worker_process, launches)

# Exercise the actual launcher code and capture the arguments passed to a stand-in
# worker. All paths contain spaces and a quote to exercise the POSIX launch path.
DRIVER = '''
extends SceneTree

class TestWindow extends Node:
	var test_mode := true
	var out_dir := ""
	var client: Node

func _initialize() -> void:
	var folder := OS.get_environment("TESTDIR")
	var window := TestWindow.new()
	window.out_dir = folder
	var worker = load("res://worker_process.gd").new(window)
	worker.worker_log = folder.path_join("worker.log")
	var source := folder.path_join("source.cfg")
	var target := folder.path_join("freecad")
	worker._freecad_config_args(target, source)
	worker._freecad_config_args(target, source)
	print("CONFIG FALLBACK ", DirAccess.dir_exists_absolute(target),
		" ", not FileAccess.file_exists(target.path_join("user.cfg")))

	var file := FileAccess.open(source, FileAccess.WRITE)
	file.store_string("seed from FreeCAD")
	file.close()
	worker._freecad_config_args(target, source)
	print("CONFIG SEED ", FileAccess.get_file_as_string(target.path_join("user.cfg")))

	file = FileAccess.open(source, FileAccess.WRITE)
	file.store_string("new value in FreeCAD")
	file.close()
	worker._freecad_config_args(target, source)
	print("CONFIG RETAINED ", FileAccess.get_file_as_string(target.path_join("user.cfg")))

	worker.freecad_path = folder.path_join("fake worker")
	worker.worker_script = source
	worker._start_worker()
	var deadline := Time.get_ticks_msec() + 3000
	while worker.worker_pid > 0 and OS.is_process_running(worker.worker_pid) and Time.get_ticks_msec() < deadline:
		OS.delay_msec(10)
	quit()
'''

scratch = ROOT / "scratch"
scratch.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="freecad config's copy-", dir=os.environ.get("TESTDIR") or scratch) as directory:
    folder = Path(directory)
    driver = folder / "check.gd"
    driver.write_text(DRIVER)
    fake_worker = folder / "fake worker"
    fake_worker.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$TESTDIR/worker-argv"\n')
    fake_worker.chmod(0o755)
    result = subprocess.run([GODOT, "--headless", "--path", str(ROOT / "viewport"), "--script", str(driver)],
                            env=dict(os.environ, TESTDIR=directory), capture_output=True, text=True, timeout=20)
    output = result.stdout + result.stderr
    check("missing source leaves defaults and creates the empty config folder",
          result.returncode == 0 and "CONFIG FALLBACK true true" in output, output)
    log = folder / "worker.log"
    check("missing source is logged once in worker.log", log.exists()
          and log.read_text().count("couldn't copy FreeCAD user.cfg") == 1
          and "couldn't copy FreeCAD user.cfg" not in output, output)
    check("the first available source is copied", "CONFIG SEED seed from FreeCAD" in output, output)
    check("an existing Napkin copy is kept", "CONFIG RETAINED seed from FreeCAD" in output, output)
    argv = folder / "worker-argv"
    check("the Godot worker receives both configs under its own output folder",
          argv.exists() and argv.read_text().splitlines() == [
              "-u", str(folder / "freecad/user.cfg"), "-s", str(folder / "freecad/system.cfg"), str(folder / "source.cfg")
          ], output)

print(f"FREECAD CONFIG TESTS: {passed} passed, {failed} failed")
raise SystemExit(bool(failed))
