extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# Q7 / T16: a rejection takes the actions that built on it, in one wave and one message; other work stays
	await harness._view(Vector3(300, 150, 30), -30, -40, 1.6)
	m.ops.append_array(harness._board_ops(300, 18)); m.counters["r"] = 1; m.counters["pp"] = 1; m.counters["b"] = 1
	m.sync(); await harness._wait_confirm()
	m.test_delay_ms = 1500                       # FreeCAD sits on its next answer while we keep working
	m.force_reject_next = true                   # ...and that answer rejects the new board
	await harness._rect(Vector3(400, 0, 0), Vector3(500, 100, 0), "100,100")
	await harness._push(Vector3(450, 50, 0), Vector3(450, 50, 50), "50")             # b2, to be rejected
	var root: String = m.ops.back()["id"]
	await harness._rect(Vector3(420, 20, 50), Vector3(480, 80, 50), "60,60")      # drawn on b2's draft
	await harness._push(Vector3(450, 50, 50), Vector3(450, 50, 70), "20")            # built on b2
	await harness._rect(Vector3(0, 300, 0), Vector3(100, 400, 0), "100,100")      # unrelated
	await harness._push(Vector3(50, 350, 0), Vector3(50, 350, 30), "30")
	var notes := {}
	var t0 := Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 8000:
		if m.ui_sync.text.begins_with("✗"): notes[m.ui_sync.text] = true
		if not notes.is_empty() and not m.dirty and not m.in_flight: break    # rejected and settled (T48)
		await harness._frames(1)
	await harness._wait_wave()
	var left := []
	for op in m.ops: left.append(op["id"])
	print("REJECTTEST rejected %s | ops left %s | boards %s | messages %s" % [root, left, harness._shown_ids(), notes.keys()])
	print("REJECTTEST done")
	harness.get_tree().quit()
