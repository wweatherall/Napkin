extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# start from a saved session (the stool) so the scene isn't empty
	var d = JSON.parse_string(FileAccess.get_file_as_string(m.preload_path))
	m.ops = d["ops"]
	m._restore_counters()
	m._rebuild_rect_drafts()
	for op in m.ops: m.confirmed_ids[op["id"]] = true
	m.sync()
	await harness._wait_confirm()
	m.target = Main.m2g(Vector3(420, 150, 220)); m.dist = 1.75; m.yaw = deg_to_rad(-36); m.pitch = deg_to_rad(-22)
	m._update_camera()
	m.cursor2d.position = Vector2(1000, 650)
	await harness._frames(15)
	# 1. a tall new board; FreeCAD takes ~4.5 s, then accepts
	await harness._key(KEY_R)
	await harness._drag_to(Vector3(620, 0, 0), 14); await harness._press()
	await harness._drag_to(Vector3(700, 300, 0), 12)
	await harness._type("40,300\n")
	await harness._key(KEY_P)
	await harness._drag_to(Vector3(640, 150, 0), 10); await harness._press()
	await harness._drag_to(Vector3(640, 150, 500), 18)
	m.test_delay_ms = 9000
	m.trace_wave = "pp%d" % (m.counters["pp"] + 1)
	await harness._type("600\n")
	await harness._wait_wave()
	await harness._hold(15)
	# 2. an edit FreeCAD rejects after ~4.5 s: push the stool top down 40 mm (it is 20 thick)
	await harness._key(KEY_P)
	await harness._drag_to(Vector3(330, 220, 420), 14); await harness._press()
	await harness._drag_to(Vector3(330, 220, 395), 10)
	m.test_delay_ms = 9000
	await harness._type("-40\n")
	await harness._wait_wave()
	await harness._hold(20)
	var f := FileAccess.open(m.out_dir.path_join("front_trace.csv"), FileAccess.WRITE)
	f.store_string("tn,progress,velocity,reach_m,state\n" + "\n".join(m.trace_rows))
	f.close()
	print("BREATHTEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	harness.get_tree().quit()
