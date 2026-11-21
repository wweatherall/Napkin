extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# I04b: a rectangle drawn on a board's face and pushed out joins that board by default; with B, a new board
	await harness._view(Vector3(150, 100, 20), -30, -40, 1.0)
	m.ops.append_array(harness._board_ops(300, 18)); m.counters["r"] = 1; m.counters["pp"] = 1; m.counters["b"] = 1
	m.sync(); await harness._wait_confirm()
	var default_join: bool = not m.new_board
	await harness._rect(Vector3(100, 50, 18), Vector3(150, 100, 18), "50,50")
	await harness._push(Vector3(125, 75, 18), Vector3(125, 75, 30), "20")
	await harness._wait_wave()
	var joined: Dictionary = m.ops.back()
	var boards_after_join := harness._shown_ids()
	await harness._key(KEY_B)
	await harness._rect(Vector3(200, 50, 18), Vector3(250, 100, 18), "40,40")
	m.saved_shown.clear()                          # what the indicator says from here on (T45)
	await harness._push(Vector3(220, 70, 18), Vector3(220, 70, 30), "10")
	await harness._wait_wave()
	var separate: Dictionary = m.ops.back()
	var t0 := Time.get_ticks_msec()
	while m.ui_saved.text != "Saved" and Time.get_ticks_msec() - t0 < 5000: await harness._frames(1)
	print("JOINTEST save indicator: %s, now '%s' after %d ms (rev %d)" % [" then ".join(m.saved_shown), m.ui_saved.text,
		Time.get_ticks_msec() - t0, m.saved_rev])
	print("JOINTEST default joins %s | pushed out from b1's top: %s, boards %s (want 1) | with B: %s, boards %s (want 2)" % [
		default_join, "joined" if not joined.has("body") else "new board " + joined["body"], boards_after_join,
		"new board " + separate.get("body", "?") if separate.has("body") else "joined", harness._shown_ids()])
	print("JOINTEST done")
	harness.get_tree().quit()
