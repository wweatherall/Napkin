extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	m.camera_rig.target = Main.m2g(Vector3(230, 150, 210))
	m.camera_rig.dist = 1.35
	m.camera_rig.yaw = deg_to_rad(-40)
	m.camera_rig.pitch = deg_to_rad(-24)
	m.camera_rig.update_camera()
	m.cursor2d.position = Vector2(900, 650)
	await harness._frames(10)
	# 1. side panel: drag a rectangle, pull it up, click to finish on the top face
	await harness._key(KEY_R)
	await harness._drag_to(Vector3(0, 0, 0), 14); await harness._press()
	await harness._drag_to(Vector3(20, 300, 0), 16); await harness._press()
	await harness._key(KEY_P)
	await harness._drag_to(Vector3(10, 150, 0), 12); await harness._press()
	await harness._drag_to(Vector3(10, 150, 400), 26)
	await harness._type("400\n")
	await harness._wait_wave()
	# 2. second panel
	await harness._key(KEY_R)
	await harness._drag_to(Vector3(440, 0, 0), 14); await harness._press()
	await harness._drag_to(Vector3(460, 300, 0), 14); await harness._press()
	await harness._key(KEY_P)
	await harness._drag_to(Vector3(450, 150, 0), 10); await harness._press()
	await harness._drag_to(Vector3(450, 150, 400), 20)
	await harness._type("400\n")
	await harness._wait_wave()
	# 3. top board, started from the corner, finished near the front-left corner
	await harness._key(KEY_R)
	await harness._drag_to(Vector3(3, 4, 400), 14); await harness._press()
	await harness._drag_to(Vector3(460, 300, 400), 18)
	await harness._type("460,300\n")
	await harness._key(KEY_P)
	await harness._drag_to(Vector3(40, 30, 400), 12); await harness._press()
	await harness._drag_to(Vector3(40, 30, 420), 10)
	await harness._type("20\n")
	await harness._wait_wave()
	# 4. hand slot: the wave starts inside the cut
	await harness._key(KEY_R)
	await harness._drag_to(Vector3(170, 140, 420), 14); await harness._press()
	await harness._drag_to(Vector3(290, 160, 420), 12)
	await harness._type("120,20\n")
	await harness._key(KEY_P)
	await harness._drag_to(Vector3(230, 150, 420), 10); await harness._press()
	await harness._drag_to(Vector3(230, 150, 405), 8)
	await harness._type("-20\n")
	await harness._wait_wave()
	# 5. a new board that FreeCAD rejects (forced with a test hook)
	await harness._key(KEY_R)
	await harness._drag_to(Vector3(620, 0, 0), 14); await harness._press()
	await harness._drag_to(Vector3(760, 200, 0), 12)
	await harness._type("140,200\n")
	await harness._key(KEY_P)
	m.force_reject_next = true
	await harness._drag_to(Vector3(690, 100, 0), 10); await harness._press()
	await harness._drag_to(Vector3(690, 100, 250), 14)
	await harness._type("250\n")
	await harness._wait_wave()
	await harness._key(KEY_ESCAPE)
	# 6. an edit FreeCAD rejects for real: push the top board's face down 40 mm (it's only 20 thick)
	await harness._key(KEY_P)
	await harness._drag_to(Vector3(380, 220, 420), 14); await harness._press()
	await harness._drag_to(Vector3(380, 220, 390), 10)
	await harness._type("-40\n")
	await harness._wait_wave()
	await harness._hold(20)
	print("FXTEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	harness.get_tree().quit()
