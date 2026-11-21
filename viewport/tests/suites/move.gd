extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	m.cursor2d.position = Vector2(900, 650)
	await harness._view(Vector3(400, 400, 200), 30, -30, 3.2)
	await harness._rect(Vector3(0, 0, 0), Vector3(15, 200, 0), "20,300")
	await harness._push(Vector3(10, 150, 0), Vector3(10, 150, 250), "400")
	await harness._wait_wave()
	# 1. MOVE: pick up the top corner, lock red (Right arrow), type 200
	await harness._key(KEY_M)
	await harness._drag_to(Vector3(18, 3, 400), 10); await harness._press()
	await harness._key(KEY_RIGHT)
	await harness._drag_to(Vector3(150, 0, 400), 12)
	await harness._shot("MV0_moving")
	await harness._type("200\n")
	await harness._checkpoint("MV1_moved")
	# 2. COPY + ARRAY: Ctrl toggles copy, type 100, then 4x
	await harness._key(KEY_M)
	await harness._key(KEY_CTRL)
	await harness._drag_to(Vector3(218, 3, 400), 10); await harness._press()
	await harness._key(KEY_RIGHT)
	await harness._drag_to(Vector3(300, 0, 400), 12)
	await harness._type("100\n")
	await harness._frames(4)
	await harness._type("4x\n")
	await harness._checkpoint("MV2_array_4x")
	# 3. COPY + DIVIDE: lock green (Left), type 600, then /3
	await harness._key(KEY_M)
	await harness._key(KEY_CTRL)
	await harness._drag_to(Vector3(218, 3, 400), 10); await harness._press()
	await harness._key(KEY_LEFT)
	await harness._drag_to(Vector3(220, 300, 400), 12)
	await harness._type("600\n")
	await harness._frames(4)
	await harness._type("/3\n")
	await harness._checkpoint("MV3_divide_3")
	# 4. AMEND: move a copy up (blue), type 50, then change your mind: 80
	await harness._key(KEY_M)
	await harness._drag_to(Vector3(618, 3, 400), 10); await harness._press()
	await harness._key(KEY_UP)
	await harness._drag_to(Vector3(620, 0, 450), 10)
	await harness._type("50\n")
	await harness._frames(4)
	await harness._type("80\n")
	await harness._checkpoint("MV4_amended_80")
	# 5. MIRROR (Shift+M): typed distance is from the face you clicked to the plane
	await harness._view(Vector3(330, 150, 200), 25, -20, 2.4)
	await harness._key(KEY_M)
	await harness._drag_to(Vector3(220, 150, 200), 10); await harness._press()
	await harness._key(KEY_CTRL)
	await harness._key(KEY_SHIFT)
	await harness._drag_to(Vector3(330, 150, 0), 12)
	await harness._shot("MV5_mirror_tooltip")
	await harness._type("100\n")
	await harness._checkpoint("MV6_mirrored")
	await harness._view(Vector3(400, 400, 200), 30, -30, 3.4)
	await harness._shot("MV7_overview")
	var f := FileAccess.open(m.shots_dir.path_join("draft_bboxes.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(m.draft_bboxes)); f.close()
	print("MOVETEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	harness.get_tree().quit()
