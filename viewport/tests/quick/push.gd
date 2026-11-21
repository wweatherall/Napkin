extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 2. Push/Pull: a new board, join by default (I04b), B for a separate board, the saved indicator (Q22)
	await harness._fresh("push", harness._plank(1, Vector3.ZERO, Vector3(300, 200, 18)))
	await harness._view(Vector3(150, 100, 20), -30, -40, 1.0)
	await harness._rect(Vector3(100, 50, 18), Vector3(150, 100, 18), "50,50")
	m.saved_shown.clear()
	await harness._push(Vector3(125, 75, 18), Vector3(125, 75, 30), "20")
	await harness._wait_wave()
	harness._ok("pushed out from a face, it joins that board", harness._shown_ids() == ["b1"] and not m.ops.back().has("body"), [harness._shown_ids(), m.ops.back()])
	harness._ok("the joined bump adds 50 x 50 x 20", is_equal_approx(harness._bodies()["b1"]["volume_mm3"], 300.0 * 200 * 18 + 50 * 50 * 20), harness._bodies()["b1"]["volume_mm3"])
	var t0 := Time.get_ticks_msec()
	while m.ui_saved.text != "Saved" and Time.get_ticks_msec() - t0 < 3000: await harness._frames(1)
	harness._ok("the save indicator says Saving..., then Saved (T45: however quickly the save lands)",
		m.ui_saved.text == "Saved" and m.saved_shown.slice(-2) == ["Saving…", "Saved"], [m.ui_saved.text, m.saved_shown])
	await harness._key(KEY_B)
	await harness._rect(Vector3(200, 50, 18), Vector3(250, 100, 18), "40,40")
	await harness._push(Vector3(220, 70, 18), Vector3(220, 70, 30), "10")
	await harness._wait_wave()
	harness._ok("with B, a separate board", harness._shown_ids() == ["b1", "b2"], harness._shown_ids())
