extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# a shelf-pin row: one hole, then Move-copy it along red and make it an array
	m.cursor2d.position = Vector2(900, 650)
	await harness._view(Vector3(300, 150, 0), -20, -50, 1.3)
	await harness._rect(Vector3(0, 0, 0), Vector3(600, 300, 0), "600,300")
	await harness._push(Vector3(300, 150, 0), Vector3(300, 150, 18), "18")
	await harness._wait_wave()
	await harness._rect(Vector3(30, 30, 18), Vector3(50, 50, 18), "20,20")
	await harness._push(Vector3(40, 40, 18), Vector3(40, 40, 0), "-18")
	await harness._checkpoint("H1_one_hole")
	# 1. hover the hole with Move: it highlights the hole, not the board
	await harness._key(KEY_M)
	await harness._drag_to(Vector3(40, 50, 9), 10)        # on the hole's far wall (faces the camera)
	await harness._shot("H2_hover_hole")
	print("HOLETEST hover shows hole: ", m.overlay.mesh != null and (m.overlay.mesh.surface_get_material(0) == m.mat_cut_hl))
	# 2. copy it along red, 60 mm, then 5x
	await harness._key(KEY_CTRL)
	await harness._press()
	print("HOLETEST grabbed: ", m.move_state.get("cut", {}))
	await harness._key(KEY_RIGHT)
	await harness._drag_to(Vector3(100, 30, 9), 12)
	await harness._shot("H3_dragging_copy")
	await harness._type("60\n")
	await harness._frames(4)
	await harness._type("5x\n")
	await harness._checkpoint("H4_array_5x")
	# 3. move the whole row up the board (green), 100 mm
	await harness._key(KEY_M)
	await harness._drag_to(Vector3(160, 30, 9), 10); await harness._press()
	await harness._key(KEY_LEFT)
	await harness._drag_to(Vector3(160, 120, 9), 12)
	await harness._type("100\n")
	await harness._checkpoint("H5_row_moved")
	# 4. undo the move, and the array
	m.undo()
	await harness._checkpoint("H6_undo_move")
	print("HOLETEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	harness.get_tree().quit()
