extends Node
## Test-mode entry point. Suites share one harness and keep their existing command-line flags.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var m: Main
var harness: Harness


func run() -> void:
	harness = load("res://tests/harness.gd").new()
	harness.m = m
	add_child(harness)
	if not m.fx_test:
		await _suite("model")
		return
	harness._make_fake_cursor()
	if m.fast_test:                               # --fast (T48): the quick test's pacing for any suite
		harness.quick = true
		Engine.time_scale = 5.0
	if not (m.quick_test or m.join_test or m.reject_test or m.snap_test or m.rect_test or m.undo_test or m.shell_test or m.perf_test or m.line_test or m.gesture_test or m.lifecycle_test):
		m.new_board = true; m.ui.update_toggles()     # the scripted suites were recorded with 'New board' on (I04 then)
	if m.breath_test: await _suite("breath")
	elif m.face_test: await _suite("face")
	elif m.orbit_test: await _suite("orbit")
	elif m.mirror_test: await _suite("mirror")
	elif m.move_test: await _suite("move")
	elif m.infer_test: await _suite("infer")
	elif m.heavy_test: await _suite("heavy")
	elif m.zfight_test: await _suite("zfight")
	elif m.hole_test: await _suite("hole")
	elif m.line_test: await _suite("line")
	elif m.undo_test: await _suite("undo")
	elif m.gesture_test: await _suite("gesture")
	elif m.lifecycle_test: await _suite("lifecycle")
	elif m.snap_test: await _suite("snap")
	elif m.rect_test: await _suite("rect")
	elif m.perf_test: await _suite("perf")
	elif m.shell_test: await _suite("shell")
	elif m.join_test: await _suite("join")
	elif m.reject_test: await _suite("reject")
	elif m.quick_test: await _suite("quick")
	else: await _suite("fx")


func _suite(name: String) -> void:
	var path := "res://tests/quick_runner.gd" if name == "quick" else "res://tests/suites/%s.gd" % name
	var suite = load(path).new()
	suite.harness = harness
	await suite.run()
