extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	m.cursor2d.position = Vector2(900, 650)
	await harness._view(Vector3(150, 150, 200), -38, -24, 1.7)
	await harness._rect(Vector3(0, 0, 0), Vector3(15, 200, 0), "20,300")
	await harness._push(Vector3(10, 150, 0), Vector3(10, 150, 250), "400")
	await harness._wait_wave()
	# start a rectangle on the +x side face, then orbit round so that face is hidden, then finish by typing
	await harness._view(Vector3(150, 150, 200), 45, -10, 1.6)
	await harness._key(KEY_R)
	await harness._drag_to(Vector3(20, 3, 203), 10); await harness._press()
	await harness._drag_to(Vector3(20, 120, 215), 10)
	await harness._orbit_by(-110, 20)          # now looking at the -x side: the face we're drawing on faces away
	await harness._shot("O1_rect_started_then_orbited")
	await harness._type("300,20\n")
	# start Push/Pull on it from a visible angle, orbit away mid-drag, finish by typing
	await harness._orbit_by(110, 20)
	await harness._key(KEY_P)
	await harness._drag_to(Vector3(20, 150, 210), 10); await harness._press()
	await harness._drag_to(Vector3(120, 150, 210), 10)
	await harness._orbit_by(-110, 20)
	await harness._shot("O2_push_started_then_orbited")
	await harness._type("250\n")
	await harness._wait_wave()
	DirAccess.copy_absolute(m.out_dir.path_join("bodies.json"), m.shots_dir.path_join("orbit_bodies.json"))
	await harness._shot("O3_result")
	print("ORBITTEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	harness.get_tree().quit()
