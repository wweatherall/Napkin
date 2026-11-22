extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# T8: switching models (File > New / Open) clears the viewport and adopts the other file's history
	m.cursor2d.visible = false
	var t0 := Time.get_ticks_msec()
	while not m.opened and Time.get_ticks_msec() - t0 < 30000: await harness._frames(1)
	var a: String = m.model_path
	m.ops.append_array(harness._board_ops(300, 18)); m.counters["r"] = 1; m.counters["pp"] = 1; m.counters["b"] = 1
	m.sync(); await harness._wait_confirm()
	var a_top := harness._top()
	var b: String = m.out_dir.path_join("other.FCStd")
	m.switch_model(b, true)
	while not m.opened: await harness._frames(1)
	await harness._wait_confirm()
	var b_empty: bool = m.ops.is_empty() and harness._shown_ids().is_empty()
	m.ops.append_array(harness._board_ops(150, 40)); m.counters["r"] = 1; m.counters["pp"] = 1; m.counters["b"] = 1
	m.sync(); await harness._wait_confirm()
	var b_top := harness._top()
	await harness._frames(30)                   # let the worker autosave
	m.switch_model(a)
	while not m.opened: await harness._frames(1)
	await harness._wait_confirm()
	var back := harness._top()
	print("SHELLTEST A has a board %s mm tall | new model B starts empty %s, its board %s mm | back to A: %d ops, boards %s, top %s mm (want 18) | B saved %s | menus %s" % [
		a_top, b_empty, b_top, m.ops.size(), harness._shown_ids(), back, FileAccess.file_exists(b), m._menus.keys()])
	print("SHELLTEST done")
	harness.get_tree().quit()
