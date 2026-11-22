extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	m.cursor2d.position = Vector2(900, 650)
	# S1: upright panel b1, 20 x 300 x 400
	await harness._view(Vector3(150, 150, 200), -38, -24, 1.7)
	await harness._rect(Vector3(0, 0, 0), Vector3(15, 200, 0), "20,300")
	await harness._push(Vector3(10, 150, 0), Vector3(10, 150, 250), "400")
	await harness._checkpoint("S1_panel")
	# S2: rectangle on the panel's +x side face -> new board sticking out sideways (New board ON)
	await harness._view(Vector3(150, 150, 200), 45, -22, 1.6)
	await harness._rect(Vector3(20, 3, 203), Vector3(20, 120, 215), "300,20")
	await harness._push(Vector3(20, 150, 210), Vector3(120, 150, 210), "250")
	await harness._checkpoint("S2_side_face_new_board")
	# S3: same face, New board OFF -> merges into the panel
	await harness._key(KEY_B)
	await harness._view(Vector3(60, 150, 110), 50, 0, 1.3)     # level camera: the shelf above no longer hides this spot
	await harness._rect(Vector3(20, 3, 103), Vector3(20, 120, 115), "300,20")
	await harness._push(Vector3(20, 150, 110), Vector3(60, 150, 110), "30")
	await harness._checkpoint("S3_side_face_merge")
	# S4: pocket in the top face of the shelf (cut 10 deep)
	await harness._view(Vector3(150, 150, 220), 30, -50, 1.4)
	await harness._rect(Vector3(100, 100, 220), Vector3(130, 120, 220), "60,40")
	await harness._push(Vector3(130, 120, 220), Vector3(130, 120, 212), "-10")
	await harness._checkpoint("S4_pocket_top_face")
	# S5: through-hole from the panel's -x side face
	await harness._view(Vector3(0, 150, 250), -60, -15, 1.3)
	await harness._rect(Vector3(0, 147, 303), Vector3(0, 120, 315), "100,40")
	await harness._push(Vector3(0, 100, 320), Vector3(-30, 100, 320), "-20")
	await harness._checkpoint("S5_through_hole_side_face")
	# S6: rectangle that overhangs the shelf's end face, merged (New board still OFF)
	await harness._view(Vector3(270, 150, 210), 60, -18, 1.3)
	await harness._rect(Vector3(270, 3, 203), Vector3(270, 100, 215), "300,40")
	await harness._push(Vector3(270, 150, 210), Vector3(300, 150, 210), "20")
	await harness._checkpoint("S6_overhang_merge")
	# S7: chain onto a draft: make a post, then immediately draw on its top before FreeCAD confirms
	await harness._key(KEY_B)   # New board back ON for the post
	await harness._view(Vector3(420, 20, 160), -38, -24, 1.5)
	await harness._rect(Vector3(400, 0, 0), Vector3(420, 20, 0), "40,40")
	await harness._push(Vector3(420, 20, 0), Vector3(420, 20, 200), "300")
	await harness._key(KEY_B)   # OFF: merge the cap into the (still draft) post
	await harness._rect(Vector3(403, 3, 300), Vector3(430, 30, 300), "40,40")
	await harness._push(Vector3(420, 20, 300), Vector3(420, 20, 310), "20")
	await harness._checkpoint("S7_chain_on_draft")
	await harness._view(Vector3(220, 150, 180), 35, -28, 1.9)
	await harness._shot("S8_overview")
	var f := FileAccess.open(m.shots_dir.path_join("draft_bboxes.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(m.draft_bboxes)); f.close()
	print("FACETEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	harness.get_tree().quit()
