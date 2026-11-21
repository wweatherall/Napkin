extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	m.cursor2d.position = Vector2(900, 650)
	await harness._view(Vector3(350, 250, 150), 30, -28, 3.0)
	await harness._rect(Vector3(0, 0, 0), Vector3(15, 200, 0), "20,300")
	await harness._push(Vector3(10, 150, 0), Vector3(10, 150, 250), "400")
	await harness._rect(Vector3(300, 0, 0), Vector3(400, 100, 0), "300,300")
	await harness._push(Vector3(450, 150, 0), Vector3(450, 150, 10), "20")
	await harness._wait_wave()
	# T5a: move the slab 13 mm along red (typed) so it sits off the 10 mm grid
	await harness._grab(Vector3(303, 3, 20))
	await harness._key(KEY_RIGHT)
	await harness._drag_to(Vector3(330, 0, 20), 8)
	await harness._type("13\n")
	await harness._checkpoint("I0_slab_off_grid")
	# T5b: free diagonal move over open floor: distance travelled snaps, so the 3 mm offset survives
	await harness._grab(Vector3(316, 3, 20))
	await harness._drag_to(Vector3(516, 207, 20), 14)
	harness._log_move("T5b"); await harness._shot("I1_free_diagonal")
	await harness._press()
	await harness._checkpoint("I2_slab_moved")
	# T1: grab the panel's top corner, drag over open floor along red: soft red inference, no sinking
	await harness._grab(Vector3(3, 3, 400))
	await harness._drag_to(Vector3(150, 0, 400), 14)
	harness._log_move("T1"); await harness._shot("I3_soft_red")
	await harness._press()
	await harness._checkpoint("I4_moved_red")
	# T2: drag straight up on screen: soft blue inference
	await harness._grab(Vector3(153, 3, 400))
	await harness._drag_to(Vector3(150, 0, 600), 14)
	harness._log_move("T2"); await harness._shot("I5_soft_blue")
	await harness._press()
	await harness._checkpoint("I6_moved_blue")
	# T3: grab the bottom front corner and land it on the slab's top front edge midpoint
	var slab := {}
	for b in JSON.parse_string(FileAccess.get_file_as_string(m.out_dir.path_join("bodies.json"))):
		if b["id"] == "b2": slab = b
	var bb: Array = slab["world_bbox"]
	var mid := Vector3((bb[0] + bb[3]) * 0.5, bb[1], bb[5])
	await harness._grab(Vector3(152, 2, 202))
	await harness._drag_to(mid, 16)
	harness._log_move("T3"); await harness._shot("I7_midpoint")
	await harness._press()
	await harness._checkpoint("I8_on_midpoint")
	# T4: tap Right twice -> green/blue plane lock; drag well off to the side; red must not change
	var pb := {}
	for b in JSON.parse_string(FileAccess.get_file_as_string(m.out_dir.path_join("bodies.json"))):
		if b["id"] == "b1": pb = b
	var top := Vector3(pb["world_bbox"][0], pb["world_bbox"][1], pb["world_bbox"][5])
	await harness._grab(top + Vector3(2, 2, 0))
	await harness._key(KEY_RIGHT); await harness._key(KEY_RIGHT)
	await harness._drag_to(top + Vector3(400, 300, 100), 14)
	harness._log_move("T4"); await harness._shot("I9_plane_lock")
	await harness._press()
	await harness._checkpoint("I10_plane_locked")
	# T6: the full cycle: axis -> plane -> free (grab the panel where it is now)
	for b in JSON.parse_string(FileAccess.get_file_as_string(m.out_dir.path_join("bodies.json"))):
		if b["id"] == "b1": pb = b
	top = Vector3(pb["world_bbox"][0], pb["world_bbox"][1], pb["world_bbox"][5])
	await harness._view(top + Vector3(10, 150, -200), 30, -28, 2.5)
	await harness._grab(top + Vector3(2, 2, 0))
	var modes := []
	for i in 3:
		await harness._key(KEY_RIGHT); modes.append(m.move_state["lock_mode"])
	print("INFER cycle ", modes)
	await harness._key(KEY_ESCAPE)
	print("INFERTEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	harness.get_tree().quit()
