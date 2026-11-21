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
	# a cleat on the +x side, so the board isn't symmetric
	await harness._key(KEY_B)
	await harness._view(Vector3(60, 150, 110), 50, 0, 1.3)
	await harness._rect(Vector3(20, 3, 103), Vector3(20, 120, 115), "300,20")
	await harness._push(Vector3(20, 150, 110), Vector3(60, 150, 110), "30")
	await harness._wait_wave()
	# MIRROR across an X plane: click the +x face, slide the plane, type 300 past the board
	await harness._view(Vector3(350, 150, 200), 40, -22, 2.3)
	await harness._key(KEY_M)
	await harness._drag_to(Vector3(20, 150, 300), 10); await harness._press()
	await harness._key(KEY_CTRL)
	await harness._key(KEY_SHIFT)
	await harness._drag_to(Vector3(300, 150, 0), 14)
	await harness._shot("M0_plane_and_ghost")
	await harness._type("300\n")
	await harness._checkpoint("M1_mirrored")
	await harness._key(KEY_SPACE)                          # the pair is a mirror group now (A11b): enter it to edit
	await harness._double_click_at(Vector3(20, 150, 300))
	# edit the ORIGINAL: pull its -x face out 10
	await harness._view(Vector3(0, 150, 250), -60, -15, 1.3)
	await harness._push(Vector3(0, 150, 300), Vector3(-30, 150, 300), "10")
	await harness._checkpoint("M2_edit_original")
	# edit the COPY: pull its top up 20 (should flow back to the original)
	await harness._view(Vector3(400, 150, 380), 35, -40, 2.2)
	await harness._push(Vector3(635, 150, 400), Vector3(635, 150, 430), "20")
	await harness._checkpoint("M3_edit_copy")
	# arrow key: start parallel to the +x face, switch to the green (Y) axis with Left
	await harness._view(Vector3(20, 450, 200), -25, -25, 2.8)
	await harness._key(KEY_M)
	await harness._drag_to(Vector3(-10, 150, 300), 10); await harness._press()
	await harness._key(KEY_CTRL)
	await harness._key(KEY_SHIFT)
	await harness._key(KEY_LEFT)
	await harness._drag_to(Vector3(-10, 450, 300), 14)     # along the locked green line, as a hand would
	await harness._shot("M4_green_plane")
	await harness._type("200\n")
	await harness._checkpoint("M5_mirrored_on_y")
	# flip the original in place (Shift only, no copy) across x = -100: grab its -x face, type 90
	await harness._view(Vector3(-150, 150, 250), -60, -18, 2.0)
	await harness._key(KEY_M)
	await harness._drag_to(Vector3(-10, 150, 300), 10); await harness._press()
	await harness._key(KEY_SHIFT)
	await harness._drag_to(Vector3(-150, 150, 300), 12)
	await harness._shot("M5b_flip_in_place")
	await harness._type("90\n")
	await harness._checkpoint("M5c_flipped")
	# move the flipped board +100 along red
	await harness._key(KEY_M)
	await harness._drag_to(Vector3(-205, 150, 420), 10); await harness._press()
	await harness._key(KEY_RIGHT)
	await harness._drag_to(Vector3(-100, 0, 420), 10)
	await harness._type("100\n")
	await harness._checkpoint("M5d_flipped_moved")
	print("MIRRORTEST inside ", m.context)
	await harness._key(KEY_ESCAPE)
	await harness._view(Vector3(350, 450, 200), 30, -30, 3.0)
	await harness._shot("M6_overview")
	var f := FileAccess.open(m.shots_dir.path_join("draft_bboxes.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(m.draft_bboxes)); f.close()
	print("MIRRORTEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	harness.get_tree().quit()
