extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# grid, axes and board edges where plain GL lines used to vanish: shallow angles, far away, close up
	m.cursor2d.visible = false
	var views := [["low", 0.0, 2.0, -40.0, -6.0], ["low_far", 0.0, 6.0, -40.0, -10.0], ["far", 0.0, 12.0, -30.0, -35.0],
		["top_far", 0.0, 9.0, 0.0, -89.0], ["along_x", 0.0, 3.0, -90.0, -8.0]]
	for v in views:
		m.target = Main.m2g(Vector3(300, 200, 0)); m.dist = v[2]; m.yaw = deg_to_rad(v[3]); m.pitch = deg_to_rad(v[4])
		m._update_camera()
		await harness._frames(3)
		harness.get_viewport().get_texture().get_image().save_png(m.shots_dir.path_join("L_%s.png" % v[0]))
	m.cursor2d.visible = true
	await harness._view(Vector3(150, 100, 50), -35, -40, 1.0)
	await harness._rect(Vector3(0, 0, 0), Vector3(600, 18, 0), "600,18")
	await harness._push(Vector3(300, 9, 0), Vector3(300, 9, 100), "300")
	await harness._wait_wave()
	m.cursor2d.visible = false
	for v in [["board_grazing", 1.2, -2.0, -3.0], ["board_edge_on", 0.8, -89.0, -20.0], ["board_far", 7.0, -35.0, -25.0]]:
		m.target = Main.m2g(Vector3(300, 9, 150)); m.dist = v[1]; m.yaw = deg_to_rad(v[2]); m.pitch = deg_to_rad(v[3])
		m._update_camera()
		await harness._frames(3)
		harness.get_viewport().get_texture().get_image().save_png(m.shots_dir.path_join("L_%s.png" % v[0]))
	print("LINETEST done")
	harness.get_tree().quit()
