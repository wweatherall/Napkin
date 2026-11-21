extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# a block with a pocket, its top face highlighted, seen from many angles and distances
	await harness._view(Vector3(150, 100, 50), -35, -40, 1.0)
	await harness._rect(Vector3(0, 0, 0), Vector3(300, 200, 0), "300,200")
	await harness._push(Vector3(150, 100, 0), Vector3(150, 100, 100), "100")
	await harness._wait_wave()
	await harness._rect(Vector3(150, 60, 100), Vector3(250, 140, 100), "100,80")
	await harness._push(Vector3(200, 100, 100), Vector3(200, 100, 60), "-60")
	await harness._wait_wave()
	await harness._key(KEY_P)
	var outer := [Vector3(0, 0, 100), Vector3(300, 0, 100), Vector3(300, 200, 100), Vector3(0, 200, 100)]
	var hole := [Vector3(150, 60, 100), Vector3(250, 60, 100), Vector3(250, 140, 100), Vector3(150, 140, 100)]
	var info := []
	var k := 0
	for d in [0.45, 0.9, 1.8, 3.5]:
		for yaw_d in [-60.0, -25.0, 15.0]:
			for pitch_d in [-30.0, -55.0, -75.0]:
				m.target = Main.m2g(Vector3(150, 100, 50)); m.yaw = deg_to_rad(yaw_d); m.pitch = deg_to_rad(pitch_d); m.dist = d
				m._update_camera()
				await harness._drag_to(Vector3(40, 30, 100), 2)
				await harness._frames(2)
				var tag := "zf_%02d" % k
				var o2 := []; var h2 := []
				for q in outer: var sp := m.cam.unproject_position(Main.m2g(q)); o2.append([sp.x, sp.y])
				for q in hole: var sp := m.cam.unproject_position(Main.m2g(q)); h2.append([sp.x, sp.y])
				info.append({"tag": tag, "outer": o2, "hole": h2, "hover": not m.hover.is_empty()})
				harness.get_viewport().get_texture().get_image().save_png(m.shots_dir.path_join(tag + ".png"))
				k += 1
	var f := FileAccess.open(m.shots_dir.path_join("zfight.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(info)); f.close()
	print("ZFIGHTTEST done, shots: ", k, " bias: ", m.overlay_bias)
	harness.get_tree().quit()
