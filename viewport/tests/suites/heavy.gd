extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# a real model opened from its FreeCAD file: an 18 mm panel with 32 through-holes
	var t0 := Time.get_ticks_msec()
	while m.ops.is_empty() and Time.get_ticks_msec() - t0 < 20000:
		await harness._frames(1)
	await harness._wait_confirm()
	print("HEAVYTEST opened %s with %d ops" % [m.model_path.get_file(), m.ops.size()])
	m.camera_rig.target = Main.m2g(Vector3(560, 300, 0))
	m.camera_rig.dist = 1.9
	m.camera_rig.yaw = deg_to_rad(-28)
	m.camera_rig.pitch = deg_to_rad(-38)
	m.camera_rig.update_camera()
	m.cursor2d.position = Vector2(900, 700)
	harness._say("Opened model.FCStd: an 18 mm panel with 32 holes, each a real FreeCAD cut")
	await harness._hold(70)
	# 1. something light first: a new block on the floor (FreeCAD answers in a few ms)
	harness._say("A light action: new block on the floor")
	await harness._key(KEY_R)
	await harness._drag_to(Vector3(1300, 100, 0), 14); await harness._press()
	await harness._drag_to(Vector3(1400, 250, 0), 12)
	await harness._type("100,150\n")
	await harness._key(KEY_P)
	await harness._drag_to(Vector3(1350, 175, 0), 10); await harness._press()
	await harness._drag_to(Vector3(1350, 175, 150), 16)
	var ta := Time.get_ticks_msec()
	await harness._type("150\n")
	await harness._wait_wave()
	print("HEAVYTEST light action confirmed after %d ms wall" % (Time.get_ticks_msec() - ta))
	await harness._hold(30)
	# 2. the heavy one: push the panel's holed top face down 6 mm
	harness._say("A heavy action: push the holed top face down 6 mm")
	await harness._key(KEY_P)
	await harness._drag_to(Vector3(120, 130, 18), 16); await harness._press()
	await harness._drag_to(Vector3(120, 130, 12), 12)
	var tb := Time.get_ticks_msec()
	await harness._type("-6\n")
	await harness._wait_wave()
	print("HEAVYTEST heavy action confirmed after %d ms wall | %s" % [Time.get_ticks_msec() - tb, m.ui_sync.text])
	harness._say("FreeCAD confirmed: %s" % m.ui_sync.text.replace("✓ FreeCAD confirmed  ", ""))
	await harness._hold(90)
	print("HEAVYTEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	harness.get_tree().quit()
