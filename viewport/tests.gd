extends Node
## Scripted viewport tests: each drives the real UI through simulated input (a fake cursor, typed keys) and
## writes checkpoints or prints results. Run with `-- --<suite>`; see CLAUDE.md. Split out of main.gd (T4).
## `m` is the viewport (main.gd); everything the tests touch goes through it.

const Main := preload("res://main.gd")
var m: Main


func run() -> void:
	if not m.fx_test:
		await _run_test()
		return
	_make_fake_cursor()
	if m.fast_test:                               # --fast (T48): the quick test's pacing for any suite
		quick = true
		Engine.time_scale = 5.0
	if not (m.quick_test or m.join_test or m.reject_test or m.snap_test or m.rect_test or m.undo_test or m.shell_test or m.perf_test or m.line_test or m.gesture_test or m.lifecycle_test):
		m.new_board = true; m._update_toggles()     # the scripted suites were recorded with 'New board' on (I04 then)
	if m.breath_test: await _run_breath_test()
	elif m.face_test: await _run_face_test()
	elif m.orbit_test: await _run_orbit_test()
	elif m.mirror_test: await _run_mirror_test()
	elif m.move_test: await _run_move_test()
	elif m.infer_test: await _run_infer_test()
	elif m.heavy_test: await _run_heavy_test()
	elif m.zfight_test: await _run_zfight_test()
	elif m.hole_test: await _run_hole_test()
	elif m.line_test: await _run_line_test()
	elif m.undo_test: await _run_undo_test()
	elif m.gesture_test: await _run_gesture_test()
	elif m.lifecycle_test: await _run_lifecycle_test()
	elif m.snap_test: await _run_snap_test()
	elif m.rect_test: await _run_rect_test()
	elif m.perf_test: await _run_perf_test()
	elif m.shell_test: await _run_shell_test()
	elif m.join_test: await _run_join_test()
	elif m.reject_test: await _run_reject_test()
	elif m.quick_test: await _run_quick_test()
	else: await _run_fx_test()

# ---------------- fx test (--fxtest): records nicely with --write-movie ----------------
func _make_fake_cursor() -> void:
	var layer := CanvasLayer.new(); layer.layer = 10; add_child(layer)
	m.cursor2d = Node2D.new(); layer.add_child(m.cursor2d)
	var pts := PackedVector2Array([Vector2(0, 0), Vector2(0, 22), Vector2(6, 17), Vector2(10, 26), Vector2(14, 24), Vector2(10, 15), Vector2(17, 15)])
	var poly := Polygon2D.new(); poly.polygon = pts; poly.color = Color.WHITE; m.cursor2d.add_child(poly)
	var line := Line2D.new(); line.points = pts; line.add_point(Vector2(0, 0)); line.width = 1.5
	line.default_color = Color.BLACK; m.cursor2d.add_child(line)


var quick := false        # quick test: fewer frames per drag, faster waves


func _drag_to(p_model: Vector3, frames: int) -> void:
	if quick: frames = 2                         # quick test: start and end are what the tools act on (T48)
	var a: Vector2 = m.cursor2d.position
	var b := m.cam.unproject_position(Main.m2g(p_model))
	for i in range(1, frames + 1):
		var s := a.lerp(b, ease(float(i) / frames, -2.0))
		var ev := InputEventMouseMotion.new(); ev.position = s; ev.global_position = s
		Input.parse_input_event(ev)
		m.cursor2d.position = s
		await _frames(1)


func _press() -> void:
	var s: Vector2 = m.cursor2d.position
	for pressed in [true, false]:
		var ev := InputEventMouseButton.new()
		ev.button_index = MOUSE_BUTTON_LEFT; ev.pressed = pressed
		ev.position = s; ev.global_position = s
		Input.parse_input_event(ev)
	await _frames(1)


func _click_at(p_model: Vector3) -> void:
	await _drag_to(p_model, 6); await _press()


func _double_click_at(p_model: Vector3) -> void:
	await _drag_to(p_model, 6)
	var s: Vector2 = m.cursor2d.position
	var ev := InputEventMouseButton.new()
	ev.button_index = MOUSE_BUTTON_LEFT; ev.pressed = true; ev.double_click = true
	ev.position = s; ev.global_position = s
	Input.parse_input_event(ev)
	var up := ev.duplicate(); up.pressed = false; up.double_click = false
	Input.parse_input_event(up)
	await _frames(1)


func _key_state(k: Key, down: bool) -> void:
	var ev := InputEventKey.new(); ev.keycode = k; ev.pressed = down
	Input.parse_input_event(ev)
	await _frames(1)


func _key_cmd(k: Key) -> void:
	var ev := InputEventKey.new(); ev.keycode = k; ev.pressed = true; ev.meta_pressed = true
	Input.parse_input_event(ev)
	var up := ev.duplicate(); up.pressed = false
	Input.parse_input_event(up)
	await _frames(1)


func _hold(frames: int) -> void:
	await _frames(frames)


func _wait_wave() -> void:
	await _wait_confirm()
	while not m.op_waves.is_empty() or m.dirty or m.in_flight:
		await _frames(1)
	await _frames(2 if quick else 12)            # quick test: the checks read state, not pixels (T48)


func _run_fx_test() -> void:
	m.target = Main.m2g(Vector3(230, 150, 210)); m.dist = 1.35; m.yaw = deg_to_rad(-40); m.pitch = deg_to_rad(-24)
	m._update_camera()
	m.cursor2d.position = Vector2(900, 650)
	await _frames(10)
	# 1. side panel: drag a rectangle, pull it up, click to finish on the top face
	await _key(KEY_R)
	await _drag_to(Vector3(0, 0, 0), 14); await _press()
	await _drag_to(Vector3(20, 300, 0), 16); await _press()
	await _key(KEY_P)
	await _drag_to(Vector3(10, 150, 0), 12); await _press()
	await _drag_to(Vector3(10, 150, 400), 26)
	await _type("400\n")
	await _wait_wave()
	# 2. second panel
	await _key(KEY_R)
	await _drag_to(Vector3(440, 0, 0), 14); await _press()
	await _drag_to(Vector3(460, 300, 0), 14); await _press()
	await _key(KEY_P)
	await _drag_to(Vector3(450, 150, 0), 10); await _press()
	await _drag_to(Vector3(450, 150, 400), 20)
	await _type("400\n")
	await _wait_wave()
	# 3. top board, started from the corner, finished near the front-left corner
	await _key(KEY_R)
	await _drag_to(Vector3(3, 4, 400), 14); await _press()
	await _drag_to(Vector3(460, 300, 400), 18)
	await _type("460,300\n")
	await _key(KEY_P)
	await _drag_to(Vector3(40, 30, 400), 12); await _press()
	await _drag_to(Vector3(40, 30, 420), 10)
	await _type("20\n")
	await _wait_wave()
	# 4. hand slot: the wave starts inside the cut
	await _key(KEY_R)
	await _drag_to(Vector3(170, 140, 420), 14); await _press()
	await _drag_to(Vector3(290, 160, 420), 12)
	await _type("120,20\n")
	await _key(KEY_P)
	await _drag_to(Vector3(230, 150, 420), 10); await _press()
	await _drag_to(Vector3(230, 150, 405), 8)
	await _type("-20\n")
	await _wait_wave()
	# 5. a new board that FreeCAD rejects (forced with a test hook)
	await _key(KEY_R)
	await _drag_to(Vector3(620, 0, 0), 14); await _press()
	await _drag_to(Vector3(760, 200, 0), 12)
	await _type("140,200\n")
	await _key(KEY_P)
	m.force_reject_next = true
	await _drag_to(Vector3(690, 100, 0), 10); await _press()
	await _drag_to(Vector3(690, 100, 250), 14)
	await _type("250\n")
	await _wait_wave()
	await _key(KEY_ESCAPE)
	# 6. an edit FreeCAD rejects for real: push the top board's face down 40 mm (it's only 20 thick)
	await _key(KEY_P)
	await _drag_to(Vector3(380, 220, 420), 14); await _press()
	await _drag_to(Vector3(380, 220, 390), 10)
	await _type("-40\n")
	await _wait_wave()
	await _hold(20)
	print("FXTEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	get_tree().quit()


func _run_breath_test() -> void:
	# start from a saved session (the stool) so the scene isn't empty
	var d = JSON.parse_string(FileAccess.get_file_as_string(m.preload_path))
	m.ops = d["ops"]
	m._restore_counters()
	m._rebuild_rect_drafts()
	for op in m.ops: m.confirmed_ids[op["id"]] = true
	m.sync()
	await _wait_confirm()
	m.target = Main.m2g(Vector3(420, 150, 220)); m.dist = 1.75; m.yaw = deg_to_rad(-36); m.pitch = deg_to_rad(-22)
	m._update_camera()
	m.cursor2d.position = Vector2(1000, 650)
	await _frames(15)
	# 1. a tall new board; FreeCAD takes ~4.5 s, then accepts
	await _key(KEY_R)
	await _drag_to(Vector3(620, 0, 0), 14); await _press()
	await _drag_to(Vector3(700, 300, 0), 12)
	await _type("40,300\n")
	await _key(KEY_P)
	await _drag_to(Vector3(640, 150, 0), 10); await _press()
	await _drag_to(Vector3(640, 150, 500), 18)
	m.test_delay_ms = 9000
	m.trace_wave = "pp%d" % (m.counters["pp"] + 1)
	await _type("600\n")
	await _wait_wave()
	await _hold(15)
	# 2. an edit FreeCAD rejects after ~4.5 s: push the stool top down 40 mm (it is 20 thick)
	await _key(KEY_P)
	await _drag_to(Vector3(330, 220, 420), 14); await _press()
	await _drag_to(Vector3(330, 220, 395), 10)
	m.test_delay_ms = 9000
	await _type("-40\n")
	await _wait_wave()
	await _hold(20)
	var f := FileAccess.open(m.out_dir.path_join("front_trace.csv"), FileAccess.WRITE)
	f.store_string("tn,progress,velocity,reach_m,state\n" + "\n".join(m.trace_rows))
	f.close()
	print("BREATHTEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	get_tree().quit()


func _view(target_m: Vector3, yaw_deg: float, pitch_deg: float, d: float) -> void:
	m.target = Main.m2g(target_m); m.yaw = deg_to_rad(yaw_deg); m.pitch = deg_to_rad(pitch_deg); m.dist = d
	m._update_camera()
	await _frames(3)


func _rect(start_m: Vector3, toward_m: Vector3, dims: String) -> void:
	await _key(KEY_R)
	await _drag_to(start_m, 10); await _press()
	await _drag_to(toward_m, 10)
	await _type(dims + "\n")


func _push(at_m: Vector3, toward_m: Vector3, dist_txt: String) -> void:
	await _key(KEY_P)
	await _drag_to(at_m, 10); await _press()
	await _drag_to(toward_m, 10)
	await _type(dist_txt + "\n")


func _checkpoint(tag: String) -> void:
	await _wait_wave()
	DirAccess.copy_absolute(m.out_dir.path_join("bodies.json"), m.shots_dir.path_join(tag + "_bodies.json"))
	await _shot(tag)


func _run_face_test() -> void:
	m.cursor2d.position = Vector2(900, 650)
	# S1: upright panel b1, 20 x 300 x 400
	await _view(Vector3(150, 150, 200), -38, -24, 1.7)
	await _rect(Vector3(0, 0, 0), Vector3(15, 200, 0), "20,300")
	await _push(Vector3(10, 150, 0), Vector3(10, 150, 250), "400")
	await _checkpoint("S1_panel")
	# S2: rectangle on the panel's +x side face -> new board sticking out sideways (New board ON)
	await _view(Vector3(150, 150, 200), 45, -22, 1.6)
	await _rect(Vector3(20, 3, 203), Vector3(20, 120, 215), "300,20")
	await _push(Vector3(20, 150, 210), Vector3(120, 150, 210), "250")
	await _checkpoint("S2_side_face_new_board")
	# S3: same face, New board OFF -> merges into the panel
	await _key(KEY_B)
	await _view(Vector3(60, 150, 110), 50, 0, 1.3)     # level camera: the shelf above no longer hides this spot
	await _rect(Vector3(20, 3, 103), Vector3(20, 120, 115), "300,20")
	await _push(Vector3(20, 150, 110), Vector3(60, 150, 110), "30")
	await _checkpoint("S3_side_face_merge")
	# S4: pocket in the top face of the shelf (cut 10 deep)
	await _view(Vector3(150, 150, 220), 30, -50, 1.4)
	await _rect(Vector3(100, 100, 220), Vector3(130, 120, 220), "60,40")
	await _push(Vector3(130, 120, 220), Vector3(130, 120, 212), "-10")
	await _checkpoint("S4_pocket_top_face")
	# S5: through-hole from the panel's -x side face
	await _view(Vector3(0, 150, 250), -60, -15, 1.3)
	await _rect(Vector3(0, 147, 303), Vector3(0, 120, 315), "100,40")
	await _push(Vector3(0, 100, 320), Vector3(-30, 100, 320), "-20")
	await _checkpoint("S5_through_hole_side_face")
	# S6: rectangle that overhangs the shelf's end face, merged (New board still OFF)
	await _view(Vector3(270, 150, 210), 60, -18, 1.3)
	await _rect(Vector3(270, 3, 203), Vector3(270, 100, 215), "300,40")
	await _push(Vector3(270, 150, 210), Vector3(300, 150, 210), "20")
	await _checkpoint("S6_overhang_merge")
	# S7: chain onto a draft: make a post, then immediately draw on its top before FreeCAD confirms
	await _key(KEY_B)   # New board back ON for the post
	await _view(Vector3(420, 20, 160), -38, -24, 1.5)
	await _rect(Vector3(400, 0, 0), Vector3(420, 20, 0), "40,40")
	await _push(Vector3(420, 20, 0), Vector3(420, 20, 200), "300")
	await _key(KEY_B)   # OFF: merge the cap into the (still draft) post
	await _rect(Vector3(403, 3, 300), Vector3(430, 30, 300), "40,40")
	await _push(Vector3(420, 20, 300), Vector3(420, 20, 310), "20")
	await _checkpoint("S7_chain_on_draft")
	await _view(Vector3(220, 150, 180), 35, -28, 1.9)
	await _shot("S8_overview")
	var f := FileAccess.open(m.shots_dir.path_join("draft_bboxes.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(m.draft_bboxes)); f.close()
	print("FACETEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	get_tree().quit()


func _orbit_by(dyaw_deg: float, steps: int) -> void:
	# real orbit input: right-button drag, so the tool sees exactly what a person's hand would send
	var press := InputEventMouseButton.new(); press.button_index = MOUSE_BUTTON_RIGHT; press.pressed = true
	press.position = m.cursor2d.position; Input.parse_input_event(press)
	for i in steps:
		var ev := InputEventMouseMotion.new()
		ev.relative = Vector2(-dyaw_deg / steps / rad_to_deg(0.008), 0)
		ev.position = m.cursor2d.position
		Input.parse_input_event(ev)
		await _frames(1)
	var rel := InputEventMouseButton.new(); rel.button_index = MOUSE_BUTTON_RIGHT; rel.pressed = false
	rel.position = m.cursor2d.position; Input.parse_input_event(rel)
	await _frames(2)


func _run_orbit_test() -> void:
	m.cursor2d.position = Vector2(900, 650)
	await _view(Vector3(150, 150, 200), -38, -24, 1.7)
	await _rect(Vector3(0, 0, 0), Vector3(15, 200, 0), "20,300")
	await _push(Vector3(10, 150, 0), Vector3(10, 150, 250), "400")
	await _wait_wave()
	# start a rectangle on the +x side face, then orbit round so that face is hidden, then finish by typing
	await _view(Vector3(150, 150, 200), 45, -10, 1.6)
	await _key(KEY_R)
	await _drag_to(Vector3(20, 3, 203), 10); await _press()
	await _drag_to(Vector3(20, 120, 215), 10)
	await _orbit_by(-110, 20)          # now looking at the -x side: the face we're drawing on faces away
	await _shot("O1_rect_started_then_orbited")
	await _type("300,20\n")
	# start Push/Pull on it from a visible angle, orbit away mid-drag, finish by typing
	await _orbit_by(110, 20)
	await _key(KEY_P)
	await _drag_to(Vector3(20, 150, 210), 10); await _press()
	await _drag_to(Vector3(120, 150, 210), 10)
	await _orbit_by(-110, 20)
	await _shot("O2_push_started_then_orbited")
	await _type("250\n")
	await _wait_wave()
	DirAccess.copy_absolute(m.out_dir.path_join("bodies.json"), m.shots_dir.path_join("orbit_bodies.json"))
	await _shot("O3_result")
	print("ORBITTEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	get_tree().quit()


func _run_mirror_test() -> void:
	m.cursor2d.position = Vector2(900, 650)
	await _view(Vector3(150, 150, 200), -38, -24, 1.7)
	await _rect(Vector3(0, 0, 0), Vector3(15, 200, 0), "20,300")
	await _push(Vector3(10, 150, 0), Vector3(10, 150, 250), "400")
	await _wait_wave()
	# a cleat on the +x side, so the board isn't symmetric
	await _key(KEY_B)
	await _view(Vector3(60, 150, 110), 50, 0, 1.3)
	await _rect(Vector3(20, 3, 103), Vector3(20, 120, 115), "300,20")
	await _push(Vector3(20, 150, 110), Vector3(60, 150, 110), "30")
	await _wait_wave()
	# MIRROR across an X plane: click the +x face, slide the plane, type 300 past the board
	await _view(Vector3(350, 150, 200), 40, -22, 2.3)
	await _key(KEY_M)
	await _drag_to(Vector3(20, 150, 300), 10); await _press()
	await _key(KEY_CTRL)
	await _key(KEY_SHIFT)
	await _drag_to(Vector3(300, 150, 0), 14)
	await _shot("M0_plane_and_ghost")
	await _type("300\n")
	await _checkpoint("M1_mirrored")
	await _key(KEY_SPACE)                          # the pair is a mirror group now (A11b): enter it to edit
	await _double_click_at(Vector3(20, 150, 300))
	# edit the ORIGINAL: pull its -x face out 10
	await _view(Vector3(0, 150, 250), -60, -15, 1.3)
	await _push(Vector3(0, 150, 300), Vector3(-30, 150, 300), "10")
	await _checkpoint("M2_edit_original")
	# edit the COPY: pull its top up 20 (should flow back to the original)
	await _view(Vector3(400, 150, 380), 35, -40, 2.2)
	await _push(Vector3(635, 150, 400), Vector3(635, 150, 430), "20")
	await _checkpoint("M3_edit_copy")
	# arrow key: start parallel to the +x face, switch to the green (Y) axis with Left
	await _view(Vector3(20, 450, 200), -25, -25, 2.8)
	await _key(KEY_M)
	await _drag_to(Vector3(-10, 150, 300), 10); await _press()
	await _key(KEY_CTRL)
	await _key(KEY_SHIFT)
	await _key(KEY_LEFT)
	await _drag_to(Vector3(-10, 450, 300), 14)     # along the locked green line, as a hand would
	await _shot("M4_green_plane")
	await _type("200\n")
	await _checkpoint("M5_mirrored_on_y")
	# flip the original in place (Shift only, no copy) across x = -100: grab its -x face, type 90
	await _view(Vector3(-150, 150, 250), -60, -18, 2.0)
	await _key(KEY_M)
	await _drag_to(Vector3(-10, 150, 300), 10); await _press()
	await _key(KEY_SHIFT)
	await _drag_to(Vector3(-150, 150, 300), 12)
	await _shot("M5b_flip_in_place")
	await _type("90\n")
	await _checkpoint("M5c_flipped")
	# move the flipped board +100 along red
	await _key(KEY_M)
	await _drag_to(Vector3(-205, 150, 420), 10); await _press()
	await _key(KEY_RIGHT)
	await _drag_to(Vector3(-100, 0, 420), 10)
	await _type("100\n")
	await _checkpoint("M5d_flipped_moved")
	print("MIRRORTEST inside ", m.context)
	await _key(KEY_ESCAPE)
	await _view(Vector3(350, 450, 200), 30, -30, 3.0)
	await _shot("M6_overview")
	var f := FileAccess.open(m.shots_dir.path_join("draft_bboxes.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(m.draft_bboxes)); f.close()
	print("MIRRORTEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	get_tree().quit()


func _run_move_test() -> void:
	m.cursor2d.position = Vector2(900, 650)
	await _view(Vector3(400, 400, 200), 30, -30, 3.2)
	await _rect(Vector3(0, 0, 0), Vector3(15, 200, 0), "20,300")
	await _push(Vector3(10, 150, 0), Vector3(10, 150, 250), "400")
	await _wait_wave()
	# 1. MOVE: pick up the top corner, lock red (Right arrow), type 200
	await _key(KEY_M)
	await _drag_to(Vector3(18, 3, 400), 10); await _press()
	await _key(KEY_RIGHT)
	await _drag_to(Vector3(150, 0, 400), 12)
	await _shot("MV0_moving")
	await _type("200\n")
	await _checkpoint("MV1_moved")
	# 2. COPY + ARRAY: Ctrl toggles copy, type 100, then 4x
	await _key(KEY_M)
	await _key(KEY_CTRL)
	await _drag_to(Vector3(218, 3, 400), 10); await _press()
	await _key(KEY_RIGHT)
	await _drag_to(Vector3(300, 0, 400), 12)
	await _type("100\n")
	await _frames(4)
	await _type("4x\n")
	await _checkpoint("MV2_array_4x")
	# 3. COPY + DIVIDE: lock green (Left), type 600, then /3
	await _key(KEY_M)
	await _key(KEY_CTRL)
	await _drag_to(Vector3(218, 3, 400), 10); await _press()
	await _key(KEY_LEFT)
	await _drag_to(Vector3(220, 300, 400), 12)
	await _type("600\n")
	await _frames(4)
	await _type("/3\n")
	await _checkpoint("MV3_divide_3")
	# 4. AMEND: move a copy up (blue), type 50, then change your mind: 80
	await _key(KEY_M)
	await _drag_to(Vector3(618, 3, 400), 10); await _press()
	await _key(KEY_UP)
	await _drag_to(Vector3(620, 0, 450), 10)
	await _type("50\n")
	await _frames(4)
	await _type("80\n")
	await _checkpoint("MV4_amended_80")
	# 5. MIRROR (Shift+M): typed distance is from the face you clicked to the plane
	await _view(Vector3(330, 150, 200), 25, -20, 2.4)
	await _key(KEY_M)
	await _drag_to(Vector3(220, 150, 200), 10); await _press()
	await _key(KEY_CTRL)
	await _key(KEY_SHIFT)
	await _drag_to(Vector3(330, 150, 0), 12)
	await _shot("MV5_mirror_tooltip")
	await _type("100\n")
	await _checkpoint("MV6_mirrored")
	await _view(Vector3(400, 400, 200), 30, -30, 3.4)
	await _shot("MV7_overview")
	var f := FileAccess.open(m.shots_dir.path_join("draft_bboxes.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(m.draft_bboxes)); f.close()
	print("MOVETEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	get_tree().quit()


func _grab(p_model: Vector3) -> void:
	await _key(KEY_M)
	await _drag_to(p_model, 10); await _press()


func _log_move(tag: String) -> void:
	print("INFER ", tag, " kind=", m.move_state.get("kind", ""), " vec=", m.move_state.get("vec", Vector3.ZERO), " mode=", m.move_state.get("lock_mode", ""))


func _run_infer_test() -> void:
	m.cursor2d.position = Vector2(900, 650)
	await _view(Vector3(350, 250, 150), 30, -28, 3.0)
	await _rect(Vector3(0, 0, 0), Vector3(15, 200, 0), "20,300")
	await _push(Vector3(10, 150, 0), Vector3(10, 150, 250), "400")
	await _rect(Vector3(300, 0, 0), Vector3(400, 100, 0), "300,300")
	await _push(Vector3(450, 150, 0), Vector3(450, 150, 10), "20")
	await _wait_wave()
	# T5a: move the slab 13 mm along red (typed) so it sits off the 10 mm grid
	await _grab(Vector3(303, 3, 20))
	await _key(KEY_RIGHT)
	await _drag_to(Vector3(330, 0, 20), 8)
	await _type("13\n")
	await _checkpoint("I0_slab_off_grid")
	# T5b: free diagonal move over open floor: distance travelled snaps, so the 3 mm offset survives
	await _grab(Vector3(316, 3, 20))
	await _drag_to(Vector3(516, 207, 20), 14)
	_log_move("T5b"); await _shot("I1_free_diagonal")
	await _press()
	await _checkpoint("I2_slab_moved")
	# T1: grab the panel's top corner, drag over open floor along red: soft red inference, no sinking
	await _grab(Vector3(3, 3, 400))
	await _drag_to(Vector3(150, 0, 400), 14)
	_log_move("T1"); await _shot("I3_soft_red")
	await _press()
	await _checkpoint("I4_moved_red")
	# T2: drag straight up on screen: soft blue inference
	await _grab(Vector3(153, 3, 400))
	await _drag_to(Vector3(150, 0, 600), 14)
	_log_move("T2"); await _shot("I5_soft_blue")
	await _press()
	await _checkpoint("I6_moved_blue")
	# T3: grab the bottom front corner and land it on the slab's top front edge midpoint
	var slab := {}
	for b in JSON.parse_string(FileAccess.get_file_as_string(m.out_dir.path_join("bodies.json"))):
		if b["id"] == "b2": slab = b
	var bb: Array = slab["world_bbox"]
	var mid := Vector3((bb[0] + bb[3]) * 0.5, bb[1], bb[5])
	await _grab(Vector3(152, 2, 202))
	await _drag_to(mid, 16)
	_log_move("T3"); await _shot("I7_midpoint")
	await _press()
	await _checkpoint("I8_on_midpoint")
	# T4: tap Right twice -> green/blue plane lock; drag well off to the side; red must not change
	var pb := {}
	for b in JSON.parse_string(FileAccess.get_file_as_string(m.out_dir.path_join("bodies.json"))):
		if b["id"] == "b1": pb = b
	var top := Vector3(pb["world_bbox"][0], pb["world_bbox"][1], pb["world_bbox"][5])
	await _grab(top + Vector3(2, 2, 0))
	await _key(KEY_RIGHT); await _key(KEY_RIGHT)
	await _drag_to(top + Vector3(400, 300, 100), 14)
	_log_move("T4"); await _shot("I9_plane_lock")
	await _press()
	await _checkpoint("I10_plane_locked")
	# T6: the full cycle: axis -> plane -> free (grab the panel where it is now)
	for b in JSON.parse_string(FileAccess.get_file_as_string(m.out_dir.path_join("bodies.json"))):
		if b["id"] == "b1": pb = b
	top = Vector3(pb["world_bbox"][0], pb["world_bbox"][1], pb["world_bbox"][5])
	await _view(top + Vector3(10, 150, -200), 30, -28, 2.5)
	await _grab(top + Vector3(2, 2, 0))
	var modes := []
	for i in 3:
		await _key(KEY_RIGHT); modes.append(m.move_state["lock_mode"])
	print("INFER cycle ", modes)
	await _key(KEY_ESCAPE)
	print("INFERTEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	get_tree().quit()


# ---------------- scripted test (--test) ----------------
func _say(txt: String) -> void:
	if m.caption == null:
		var layer := CanvasLayer.new(); layer.layer = 9; add_child(layer)
		m.caption = Label.new(); layer.add_child(m.caption)
		m.caption.position = Vector2(24, 92)
		m.caption.add_theme_font_size_override("font_size", 26)
		m.caption.add_theme_color_override("font_color", Color(0.12, 0.12, 0.12))
	m.caption.text = txt


func _run_hole_test() -> void:
	# a shelf-pin row: one hole, then Move-copy it along red and make it an array
	m.cursor2d.position = Vector2(900, 650)
	await _view(Vector3(300, 150, 0), -20, -50, 1.3)
	await _rect(Vector3(0, 0, 0), Vector3(600, 300, 0), "600,300")
	await _push(Vector3(300, 150, 0), Vector3(300, 150, 18), "18")
	await _wait_wave()
	await _rect(Vector3(30, 30, 18), Vector3(50, 50, 18), "20,20")
	await _push(Vector3(40, 40, 18), Vector3(40, 40, 0), "-18")
	await _checkpoint("H1_one_hole")
	# 1. hover the hole with Move: it highlights the hole, not the board
	await _key(KEY_M)
	await _drag_to(Vector3(40, 50, 9), 10)        # on the hole's far wall (faces the camera)
	await _shot("H2_hover_hole")
	print("HOLETEST hover shows hole: ", m.overlay.mesh != null and (m.overlay.mesh.surface_get_material(0) == m.mat_cut_hl))
	# 2. copy it along red, 60 mm, then 5x
	await _key(KEY_CTRL)
	await _press()
	print("HOLETEST grabbed: ", m.move_state.get("cut", {}))
	await _key(KEY_RIGHT)
	await _drag_to(Vector3(100, 30, 9), 12)
	await _shot("H3_dragging_copy")
	await _type("60\n")
	await _frames(4)
	await _type("5x\n")
	await _checkpoint("H4_array_5x")
	# 3. move the whole row up the board (green), 100 mm
	await _key(KEY_M)
	await _drag_to(Vector3(160, 30, 9), 10); await _press()
	await _key(KEY_LEFT)
	await _drag_to(Vector3(160, 120, 9), 12)
	await _type("100\n")
	await _checkpoint("H5_row_moved")
	# 4. undo the move, and the array
	m.undo()
	await _checkpoint("H6_undo_move")
	print("HOLETEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	get_tree().quit()


func _run_zfight_test() -> void:
	# a block with a pocket, its top face highlighted, seen from many angles and distances
	await _view(Vector3(150, 100, 50), -35, -40, 1.0)
	await _rect(Vector3(0, 0, 0), Vector3(300, 200, 0), "300,200")
	await _push(Vector3(150, 100, 0), Vector3(150, 100, 100), "100")
	await _wait_wave()
	await _rect(Vector3(150, 60, 100), Vector3(250, 140, 100), "100,80")
	await _push(Vector3(200, 100, 100), Vector3(200, 100, 60), "-60")
	await _wait_wave()
	await _key(KEY_P)
	var outer := [Vector3(0, 0, 100), Vector3(300, 0, 100), Vector3(300, 200, 100), Vector3(0, 200, 100)]
	var hole := [Vector3(150, 60, 100), Vector3(250, 60, 100), Vector3(250, 140, 100), Vector3(150, 140, 100)]
	var info := []
	var k := 0
	for d in [0.45, 0.9, 1.8, 3.5]:
		for yaw_d in [-60.0, -25.0, 15.0]:
			for pitch_d in [-30.0, -55.0, -75.0]:
				m.target = Main.m2g(Vector3(150, 100, 50)); m.yaw = deg_to_rad(yaw_d); m.pitch = deg_to_rad(pitch_d); m.dist = d
				m._update_camera()
				await _drag_to(Vector3(40, 30, 100), 2)
				await _frames(2)
				var tag := "zf_%02d" % k
				var o2 := []; var h2 := []
				for q in outer: var sp := m.cam.unproject_position(Main.m2g(q)); o2.append([sp.x, sp.y])
				for q in hole: var sp := m.cam.unproject_position(Main.m2g(q)); h2.append([sp.x, sp.y])
				info.append({"tag": tag, "outer": o2, "hole": h2, "hover": not m.hover.is_empty()})
				get_viewport().get_texture().get_image().save_png(m.shots_dir.path_join(tag + ".png"))
				k += 1
	var f := FileAccess.open(m.shots_dir.path_join("zfight.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(info)); f.close()
	print("ZFIGHTTEST done, shots: ", k, " bias: ", m.overlay_bias)
	get_tree().quit()


func _run_line_test() -> void:
	# grid, axes and board edges where plain GL lines used to vanish: shallow angles, far away, close up
	m.cursor2d.visible = false
	var views := [["low", 0.0, 2.0, -40.0, -6.0], ["low_far", 0.0, 6.0, -40.0, -10.0], ["far", 0.0, 12.0, -30.0, -35.0],
		["top_far", 0.0, 9.0, 0.0, -89.0], ["along_x", 0.0, 3.0, -90.0, -8.0]]
	for v in views:
		m.target = Main.m2g(Vector3(300, 200, 0)); m.dist = v[2]; m.yaw = deg_to_rad(v[3]); m.pitch = deg_to_rad(v[4])
		m._update_camera()
		await _frames(3)
		get_viewport().get_texture().get_image().save_png(m.shots_dir.path_join("L_%s.png" % v[0]))
	m.cursor2d.visible = true
	await _view(Vector3(150, 100, 50), -35, -40, 1.0)
	await _rect(Vector3(0, 0, 0), Vector3(600, 18, 0), "600,18")
	await _push(Vector3(300, 9, 0), Vector3(300, 9, 100), "300")
	await _wait_wave()
	m.cursor2d.visible = false
	for v in [["board_grazing", 1.2, -2.0, -3.0], ["board_edge_on", 0.8, -89.0, -20.0], ["board_far", 7.0, -35.0, -25.0]]:
		m.target = Main.m2g(Vector3(300, 9, 150)); m.dist = v[1]; m.yaw = deg_to_rad(v[2]); m.pitch = deg_to_rad(v[3])
		m._update_camera()
		await _frames(3)
		get_viewport().get_texture().get_image().save_png(m.shots_dir.path_join("L_%s.png" % v[0]))
	print("LINETEST done")
	get_tree().quit()


func _shown_ids() -> Array:
	var ids := []
	for mi in m.bodies_root.find_children("*", "MeshInstance3D", true, false):
		if mi.has_meta("body_mesh"): ids.append(String(mi.name))
	ids.sort()
	var keys := m.body_tris.keys()
	keys.sort()
	return ids if ids == keys else ["MISMATCH meshes %s vs picking data %s" % [ids, keys]]


func _run_undo_test() -> void:
	# T10: undo shows the remembered state at once, even past FreeCAD's 20-step history (it rebuilds meanwhile)
	m.cursor2d.visible = false
	await _view(Vector3(600, 25, 0), -30, -35, 2.5)
	var seen := {0: []}            # ops count -> boards on screen once FreeCAD confirmed it
	var full := []
	for i in 11:
		m.ops.append({"id": "r%d" % (i + 1), "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [120.0 * i, 0, 0]}, "size": [100, 50]})
		m.sync(); await _wait_confirm(); seen[m.ops.size()] = _shown_ids()
		m.ops.append({"id": "pp%d" % (i + 1), "type": "push_pull", "target": {"rect": "r%d" % (i + 1)}, "distance": 18 + 4 * i, "body": "b%d" % (i + 1)})
		m.sync(); await _wait_confirm(); seen[m.ops.size()] = _shown_ids()
	full = m.ops.duplicate(true)
	print("UNDOTEST built %d ops, %d boards" % [m.ops.size(), seen[m.ops.size()].size()])
	# 1. one Ctrl+Z at a time; FreeCAD answers 300 ms late, so right after Ctrl+Z the screen shows the remembered state
	var instant_bad := []; var after_bad := []; var reloads := 0; var rebuilt := []
	for n in range(m.ops.size(), 0, -1):
		m.test_delay_ms = 100 if quick else 300      # late enough: the check below runs in the same frame (T48)
		m.undo()
		if _shown_ids() != seen[n - 1]: instant_bad.append([n - 1, _shown_ids(), seen[n - 1]])
		var sc: Node = m.bodies_root.get_child(0) if m.bodies_root.get_child_count() > 0 else null
		await _wait_confirm()
		if m.ui_sync.text.contains("rebuilt"): rebuilt.append(full.size() - (n - 1))
		if _shown_ids() != seen[n - 1]: after_bad.append([n - 1, _shown_ids(), seen[n - 1]])
		if m.bodies_root.get_child_count() > 0 and m.bodies_root.get_child(0) != sc: reloads += 1
	print("UNDOTEST one at a time: shown at once right %s %s | right after FreeCAD %s %s | reloads after FreeCAD answered: %d | FreeCAD rebuilt at undo no. %s" % [
		instant_bad.is_empty(), instant_bad.slice(0, 2), after_bad.is_empty(), after_bad.slice(0, 2), reloads, rebuilt])
	# 2. all of it again, then 22 Ctrl+Z as fast as you can press them
	m.ops = full.duplicate(true)
	m.sync(); await _wait_confirm()
	var fast_bad := []
	var t0 := Time.get_ticks_msec()
	for n in range(m.ops.size(), 0, -1):
		m.undo()
		if _shown_ids() != seen[n - 1]: fast_bad.append([n - 1, _shown_ids()])
		await _frames(1)
	var t_all := Time.get_ticks_msec() - t0
	await _wait_confirm()
	print("UNDOTEST fast: 22 undos shown at once %s %s in %d ms of frames | after FreeCAD: %s, ops %d | %s" % [
		fast_bad.is_empty(), fast_bad.slice(0, 2), t_all, _shown_ids(), m.ops.size(), m.ui_sync.text])
	print("UNDOTEST done")
	get_tree().quit()


func _gesture(ev: InputEvent) -> void:
	ev.position = Vector2(640, 420)
	Input.parse_input_event(ev)
	await _frames(2)


func _run_gesture_test() -> void:
	# T7: trackpad gestures move the camera like the mouse does
	await _view(Vector3(0, 0, 0), -30, -30, 2.0)
	var y0 := m.yaw; var p0 := m.pitch
	var pan := InputEventPanGesture.new(); pan.delta = Vector2(100.0 / Main.TRACKPAD_PX, 0.0)
	await _gesture(pan)
	var orbit_ok := is_equal_approx(m.yaw, y0 - 100 * 0.008) and is_equal_approx(m.pitch, p0)
	var mouse := InputEventMouseMotion.new(); mouse.relative = Vector2(100, 0); mouse.position = m.cursor2d.position
	m.orbiting = true; m._unhandled_input(mouse); m.orbiting = false            # the same 100 px with the middle button
	var same_as_mouse := is_equal_approx(m.yaw, y0 - 2 * 100 * 0.008)
	var t0 := m.target
	var span := InputEventPanGesture.new(); span.delta = Vector2(0.0, 50.0 / Main.TRACKPAD_PX); span.shift_pressed = true
	await _gesture(span)
	var pan_ok := m.target.distance_to(t0) > 0.01 and is_equal_approx(m.yaw, y0 - 2 * 100 * 0.008)
	var d0 := m.dist
	var pinch := InputEventMagnifyGesture.new(); pinch.factor = 1.25
	await _gesture(pinch)
	var zoom_in := m.dist < d0
	var d1 := m.dist
	var spread := InputEventMagnifyGesture.new(); spread.factor = 0.8
	await _gesture(spread)
	# T23: a wheel zooms by the amount scrolled (a smooth-scrolling mouse sends many small amounts)
	var dz := m.dist
	var notch := InputEventMouseButton.new(); notch.button_index = MOUSE_BUTTON_WHEEL_UP; notch.pressed = true; notch.factor = 1.0
	notch.position = m.cursor2d.position; m._unhandled_input(notch)
	var after_notch := m.dist
	m.dist = dz; m._update_camera()
	for i in 10:
		var tiny := InputEventMouseButton.new(); tiny.button_index = MOUSE_BUTTON_WHEEL_UP; tiny.pressed = true; tiny.factor = 0.1
		tiny.position = m.cursor2d.position; m._unhandled_input(tiny)
	var after_tiny := m.dist
	print("GESTURETEST wheel: one notch %.3f -> %.3f | ten 0.1 steps -> %.3f (same as one notch: %s)" % [dz, after_notch, after_tiny,
		is_equal_approx(after_notch, after_tiny)])
	print("GESTURETEST two-finger orbit %s | same as a mouse drag %s | Shift+two-finger pan %s | pinch out zooms in %s (%.2f -> %.2f) | pinch in zooms out %s" % [
		orbit_ok, same_as_mouse, pan_ok, zoom_in, d0, d1, m.dist > d1])
	print("GESTURETEST done")
	get_tree().quit()


func _run_lifecycle_test() -> void:
	# T6: the app starts its own worker; kill it mid-session and keep working; quitting stops the worker
	m.cursor2d.visible = false
	var t0 := Time.get_ticks_msec()
	while not m.opened and Time.get_ticks_msec() - t0 < 60000: await _frames(1)
	print("LIFECYCLETEST started worker pid %d port %d, opened %s in %d ms" % [m.worker_pid, m.worker_port, m.opened, Time.get_ticks_msec() - t0])
	m.ops.append({"id": "r1", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, 0, 0]}, "size": [300, 200]})
	m.ops.append({"id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": 18, "body": "b1"})
	m.sync(); await _wait_confirm()
	var first := _shown_ids()
	var pid1 := m.worker_pid
	OS.kill(pid1)                                   # the worker crashes
	await _frames(2)
	m.ops.append({"id": "r2", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [400, 0, 0]}, "size": [300, 200]})
	m.ops.append({"id": "pp2", "type": "push_pull", "target": {"rect": "r2"}, "distance": 25, "body": "b2"})
	var t1 := Time.get_ticks_msec()
	m.sync(); await _wait_confirm()
	print("LIFECYCLETEST before crash %s | after crash: new pid %s (was %d), running %s, boards %s, confirmed after %d ms | %s" % [
		first, m.worker_pid, pid1, OS.is_process_running(m.worker_pid), _shown_ids(), Time.get_ticks_msec() - t1, m.ui_sync.text])
	print("LIFECYCLETEST worker pid at quit %d" % m.worker_pid)
	get_tree().quit()


func _screen_of(p_model: Vector3, nudge := Vector2(3, 2)) -> Vector2:
	return m.cam.unproject_position(Main.m2g(p_model)) + nudge


func _run_snap_test() -> void:
	# Q16: Rectangle and Push/Pull snap like Move (endpoint > midpoint > on edge > grid; push to a point)
	m.cursor2d.visible = false
	m.ops.append({"id": "r1", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, 0, 0]}, "size": [300, 200]})
	m.ops.append({"id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": 18, "body": "b1"})
	m.ops.append({"id": "r2", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [400, 0, 0]}, "size": [100, 100]})
	m.ops.append({"id": "pp2", "type": "push_pull", "target": {"rect": "r2"}, "distance": 50, "body": "b2"})
	m.counters["r"] = 2; m.counters["pp"] = 2; m.counters["b"] = 2
	m.sync(); await _wait_confirm()
	await _view(Vector3(250, 100, 20), -30, -35, 1.1)
	m.set_tool("rect")
	var mid := m.snap(m.pick(_screen_of(Vector3(150, 0, 18))), _screen_of(Vector3(150, 0, 18)))
	var mid_ok: bool = mid.get("snap", "") == "midpoint" and mid["point"].is_equal_approx(Vector3(150, 0, 18))
	var on_edge := m.snap(m.pick(_screen_of(Vector3(64, 0, 18), Vector2(0, 2))), _screen_of(Vector3(64, 0, 18), Vector2(0, 2)))
	var edge_ok: bool = on_edge.get("snap", "") == "on edge" and on_edge["point"].is_equal_approx(Vector3(60, 0, 18))
	var near_corner := _screen_of(Vector3(296, 196, 18), Vector2.ZERO)      # on the face, a few pixels from its corner
	var corner := m.snap(m.pick(near_corner), near_corner)
	var corner_ok: bool = corner.get("snap", "") == "endpoint" and corner["point"].is_equal_approx(Vector3(300, 200, 18))
	var inside := m.snap(m.pick(_screen_of(Vector3(121, 93, 18), Vector2.ZERO)), _screen_of(Vector3(121, 93, 18), Vector2.ZERO))
	var grid_ok: bool = inside.get("snap", "") == "grid" and inside["point"].is_equal_approx(Vector3(120, 90, 18))
	print("SNAPTEST rectangle: midpoint %s %s | on edge, on the grid %s %s | endpoint %s | grid inside a face %s %s" % [
		mid_ok, mid.get("snap"), edge_ok, on_edge.get("point"), corner_ok, grid_ok, inside.get("point")])
	# push b1's top up to the level of b2's top corner
	m.set_tool("push")
	var push = m.tools["push"]
	push.click(_screen_of(Vector3(150, 100, 18), Vector2.ZERO))
	push.mouse_moved(_screen_of(Vector3(150, 200, 18), Vector2(0, 2)))     # over the pushed face's own far edge
	var own_edge_ignored: bool = push.state.get("snap", "") == ""
	if not own_edge_ignored: print("SNAPTEST own-edge hover snapped: %s, distance %s" % [push.state.get("snap"), push.state.get("dist")])
	push.mouse_moved(_screen_of(Vector3(400, 0, 50)))
	var dist: float = push.state.get("dist", -1)
	var kind: String = push.state.get("snap", "")
	push.click(_screen_of(Vector3(400, 0, 50)))
	await _wait_wave()
	var top := -1.0
	for b in JSON.parse_string(FileAccess.get_file_as_string(m.out_dir.path_join("bodies.json"))):
		if b["id"] == "b1": top = b["world_bbox"][5]
	print("SNAPTEST push to a point: distance %s (want 32) by %s | b1's top now at %s mm (want 50) | own face's edges ignored %s" % [
		dist, kind, top, own_edge_ignored])
	# pushing in: the back face snaps (a through-hole) even though you can't see it; elsewhere, no snap
	m.set_tool("push")
	push.click(_screen_of(Vector3(450, 50, 50), Vector2.ZERO))
	push.mouse_moved(_screen_of(Vector3(450, 50, 3), Vector2.ZERO))
	var through: float = push.state.get("dist", 0); var through_kind: String = push.state.get("snap", "")
	push.mouse_moved(_screen_of(Vector3(450, 50, 22), Vector2.ZERO))
	var free: float = push.state.get("dist", 0); var free_kind: String = push.state.get("snap", "")
	m.set_tool("push")
	print("SNAPTEST push in near the back: %s by %s (want -50 by back face) | at -28: %s, snap '%s' (want about -28, none)" % [
		through, through_kind, free, free_kind])
	# a real hole: rectangle on b2's top, pushed in to the back face -> a through cut FreeCAD keeps through (I24)
	var rop := {"id": "r3", "type": "rect", "plane": {"on": {"body": "b2", "normal": [0, 0, 1], "point": [440, 40, 50]}}, "size": [20, 20]}
	m.ops.append(rop); m._register_rect(rop); m.counters["r"] = 3
	m.sync(); await _wait_confirm()
	m.set_tool("push")
	push.click(_screen_of(Vector3(450, 50, 50), Vector2.ZERO))
	push.mouse_moved(_screen_of(Vector3(450, 50, 2), Vector2.ZERO))
	push.click(_screen_of(Vector3(450, 50, 2), Vector2.ZERO))
	var hole_op: Dictionary = m.ops.back()
	await _wait_wave()
	var b2_vol := -1.0
	for b in JSON.parse_string(FileAccess.get_file_as_string(m.out_dir.path_join("bodies.json"))):
		if b["id"] == "b2": b2_vol = b["volume_mm3"]
	print("SNAPTEST through-hole: op %s through=%s distance %s | b2 volume %s (want %s)" % [
		hole_op["id"], hole_op.get("through", false), hole_op.get("distance"), b2_vol, 100 * 100 * 50 - 20 * 20 * 50])
	print("SNAPTEST done")
	get_tree().quit()


func _button(pressed: bool) -> void:
	var ev := InputEventMouseButton.new()
	ev.button_index = MOUSE_BUTTON_LEFT; ev.pressed = pressed
	ev.position = m.cursor2d.position; ev.global_position = m.cursor2d.position
	Input.parse_input_event(ev)
	await _frames(1)


func _last_rect() -> Array:
	var rs := m.ops.filter(func(o): return o["type"] == "rect")
	return [rs.size(), rs.back()["size"] if not rs.is_empty() else null]


func _run_rect_test() -> void:
	# a rectangle started with a click ends with a click; started with press-and-drag, it ends on release
	await _view(Vector3(300, 200, 0), -30, -50, 1.4)
	m.set_tool("rect")
	# 1. press, drag, release
	await _drag_to(Vector3(0, 0, 0), 4)
	await _button(true)
	await _drag_to(Vector3(200, 100, 0), 12)
	await _button(false)
	var drag := _last_rect()
	# 2. click, move, click (no button held while moving)
	await _drag_to(Vector3(300, 0, 0), 6)
	await _button(true); await _button(false)
	await _drag_to(Vector3(400, 150, 0), 12)
	var before_second := _last_rect()
	await _button(true); await _button(false)
	var click := _last_rect()
	# 3. a click that wobbles 3 px between press and release is still a click
	await _drag_to(Vector3(0, 300, 0), 6)
	await _button(true)
	m.cursor2d.position += Vector2(3, 0)
	var wob := InputEventMouseMotion.new(); wob.position = m.cursor2d.position; wob.global_position = m.cursor2d.position
	Input.parse_input_event(wob); await _frames(1)
	await _button(false)
	await _drag_to(Vector3(100, 400, 0), 10)
	var wobble_waiting: bool = _last_rect()[0] == 2 and m.tools["rect"].state.get("active", false)
	await _button(true); await _button(false)
	var wobble := _last_rect()
	print("RECTTEST drag: %d rect, size %s (want 1, [200, 100]) | click: after first click and move %d rects (want 1), after second %d, size %s (want [100, 150]) | wobbly click still waiting %s, then size %s (want [100, 100])" % [
		drag[0], drag[1], before_second[0], click[0], click[1], wobble_waiting, wobble[1]])
	print("RECTTEST done")
	get_tree().quit()


func _run_perf_test() -> void:
	# T3: the freeze when FreeCAD's answer arrives, on 40 panels with 24 holes each; one more hole in one panel
	m.cursor2d.visible = false
	var o := [{"id": "r1", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, 0, 0]}, "size": [1200, 600]},
		{"id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": 18, "body": "b1"}]
	for k in 24:
		o.append({"id": "r%d" % (k + 2), "type": "rect", "plane": {"on": {"body": "b1", "normal": [0, 0, 1],
			"point": [50 + (k % 8) * 140, 50 + (k / 8) * 180, 18]}}, "size": [20, 20]})
		o.append({"id": "pp%d" % (k + 2), "type": "push_pull", "target": {"rect": "r%d" % (k + 2)}, "distance": -18})
	var copies := []
	for i in 39: copies.append("b%d" % (i + 2))
	o.append({"id": "mv1", "type": "move", "targets": ["b1"], "vector": [0, 0, 100], "copy": true, "count": 39, "new_ids": copies})
	m.ops = o
	m.counters["r"] = 25; m.counters["pp"] = 25; m.counters["b"] = 40; m.counters["mv"] = 1
	m.sync(); await _wait_confirm()
	await _view(Vector3(600, 300, 2000), -30, -20, 6.0)
	await _frames(20)
	var worst := []
	for trial in 3:
		var n: int = m.counters["r"] + 1
		m.ops.append({"id": "r%d" % n, "type": "rect", "plane": {"on": {"body": "b1", "normal": [0, 0, 1],
			"point": [120 + trial * 140, 140, 18]}}, "size": [20, 20]})
		m.ops.append({"id": "pp%d" % n, "type": "push_pull", "target": {"rect": "r%d" % n}, "distance": -18})
		m.counters["r"] = n; m.counters["pp"] = n
		m.sync()
		var w := 0
		var t := Time.get_ticks_usec()
		while m.dirty or m.in_flight:
			await get_tree().process_frame
			var now := Time.get_ticks_usec(); w = maxi(w, now - t); t = now
		for f in 5:
			await get_tree().process_frame
			var now := Time.get_ticks_usec(); w = maxi(w, now - t); t = now
		worst.append(w / 1000.0)
	print("PERFTEST %d boards on screen | worst frame while each of 3 answers is applied: %s ms" % [m.body_tris.size(), worst])
	print("PERFTEST done")
	get_tree().quit()


func _board_ops(w: float, h: float) -> Array:
	return [{"id": "r1", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, 0, 0]}, "size": [w, 200]},
		{"id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": h, "body": "b1"}]


func _top() -> float:
	for b in JSON.parse_string(FileAccess.get_file_as_string(m.out_dir.path_join("bodies.json"))):
		if b["id"] == "b1": return b["world_bbox"][5]
	return -1.0


func _run_shell_test() -> void:
	# T8: switching models (File > New / Open) clears the viewport and adopts the other file's history
	m.cursor2d.visible = false
	var t0 := Time.get_ticks_msec()
	while not m.opened and Time.get_ticks_msec() - t0 < 30000: await _frames(1)
	var a: String = m.model_path
	m.ops.append_array(_board_ops(300, 18)); m.counters["r"] = 1; m.counters["pp"] = 1; m.counters["b"] = 1
	m.sync(); await _wait_confirm()
	var a_top := _top()
	var b: String = m.out_dir.path_join("other.FCStd")
	m.switch_model(b, true)
	while not m.opened: await _frames(1)
	await _wait_confirm()
	var b_empty: bool = m.ops.is_empty() and _shown_ids().is_empty()
	m.ops.append_array(_board_ops(150, 40)); m.counters["r"] = 1; m.counters["pp"] = 1; m.counters["b"] = 1
	m.sync(); await _wait_confirm()
	var b_top := _top()
	await _frames(30)                   # let the worker autosave
	m.switch_model(a)
	while not m.opened: await _frames(1)
	await _wait_confirm()
	var back := _top()
	print("SHELLTEST A has a board %s mm tall | new model B starts empty %s, its board %s mm | back to A: %d ops, boards %s, top %s mm (want 18) | B saved %s | menus %s" % [
		a_top, b_empty, b_top, m.ops.size(), _shown_ids(), back, FileAccess.file_exists(b), m._menus.keys()])
	print("SHELLTEST done")
	get_tree().quit()


func _run_join_test() -> void:
	# I04b: a rectangle drawn on a board's face and pushed out joins that board by default; with B, a new board
	await _view(Vector3(150, 100, 20), -30, -40, 1.0)
	m.ops.append_array(_board_ops(300, 18)); m.counters["r"] = 1; m.counters["pp"] = 1; m.counters["b"] = 1
	m.sync(); await _wait_confirm()
	var default_join: bool = not m.new_board
	await _rect(Vector3(100, 50, 18), Vector3(150, 100, 18), "50,50")
	await _push(Vector3(125, 75, 18), Vector3(125, 75, 30), "20")
	await _wait_wave()
	var joined: Dictionary = m.ops.back()
	var boards_after_join := _shown_ids()
	await _key(KEY_B)
	await _rect(Vector3(200, 50, 18), Vector3(250, 100, 18), "40,40")
	m.saved_shown.clear()                          # what the indicator says from here on (T45)
	await _push(Vector3(220, 70, 18), Vector3(220, 70, 30), "10")
	await _wait_wave()
	var separate: Dictionary = m.ops.back()
	var t0 := Time.get_ticks_msec()
	while m.ui_saved.text != "Saved" and Time.get_ticks_msec() - t0 < 5000: await _frames(1)
	print("JOINTEST save indicator: %s, now '%s' after %d ms (rev %d)" % [" then ".join(m.saved_shown), m.ui_saved.text,
		Time.get_ticks_msec() - t0, m.saved_rev])
	print("JOINTEST default joins %s | pushed out from b1's top: %s, boards %s (want 1) | with B: %s, boards %s (want 2)" % [
		default_join, "joined" if not joined.has("body") else "new board " + joined["body"], boards_after_join,
		"new board " + separate.get("body", "?") if separate.has("body") else "joined", _shown_ids()])
	print("JOINTEST done")
	get_tree().quit()


func _run_reject_test() -> void:
	# Q7 / T16: a rejection takes the actions that built on it, in one wave and one message; other work stays
	await _view(Vector3(300, 150, 30), -30, -40, 1.6)
	m.ops.append_array(_board_ops(300, 18)); m.counters["r"] = 1; m.counters["pp"] = 1; m.counters["b"] = 1
	m.sync(); await _wait_confirm()
	m.test_delay_ms = 1500                       # FreeCAD sits on its next answer while we keep working
	m.force_reject_next = true                   # ...and that answer rejects the new board
	await _rect(Vector3(400, 0, 0), Vector3(500, 100, 0), "100,100")
	await _push(Vector3(450, 50, 0), Vector3(450, 50, 50), "50")             # b2, to be rejected
	var root: String = m.ops.back()["id"]
	await _rect(Vector3(420, 20, 50), Vector3(480, 80, 50), "60,60")      # drawn on b2's draft
	await _push(Vector3(450, 50, 50), Vector3(450, 50, 70), "20")            # built on b2
	await _rect(Vector3(0, 300, 0), Vector3(100, 400, 0), "100,100")      # unrelated
	await _push(Vector3(50, 350, 0), Vector3(50, 350, 30), "30")
	var notes := {}
	var t0 := Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 8000:
		if m.ui_sync.text.begins_with("✗"): notes[m.ui_sync.text] = true
		if not notes.is_empty() and not m.dirty and not m.in_flight: break    # rejected and settled (T48)
		await _frames(1)
	await _wait_wave()
	var left := []
	for op in m.ops: left.append(op["id"])
	print("REJECTTEST rejected %s | ops left %s | boards %s | messages %s" % [root, left, _shown_ids(), notes.keys()])
	print("REJECTTEST done")
	get_tree().quit()


# ---------------- quick test (--quicktest): every feature once, in one session, checking its own answers ----------------
var _q := [0, 0]
var _q_section := ""
var _q_times := []          # [section, ms since the previous section started]
var _q_mark := 0
var _q_fresh_ms := 0        # time spent opening fresh models


func _ok(name: String, cond: bool, detail = "") -> void:
	_q[0 if cond else 1] += 1
	if not cond: print("QUICK FAIL [%s] %s  %s" % [_q_section, name, str(detail)])


func _bodies() -> Dictionary:
	var out := {}
	for b in JSON.parse_string(FileAccess.get_file_as_string(m.out_dir.path_join("bodies.json"))):
		out[b["id"]] = b
	return out


func _bbox(bid: String) -> Array:
	var b: Dictionary = _bodies().get(bid, {})
	var out := []
	for v in b.get("world_bbox", []): out.append(snappedf(v, 0.01))
	return out


func _fresh(name: String, ops := [], own_file := false) -> void:
	"""A clean start for a section, optionally with some ops already in it. Sections share one model (T48): the
	window forgets the last section's state and syncs the new ops, and the worker takes the rest back with FreeCAD
	undo (or rebuilds). own_file = a model of its own (File > New), for checks about switching models."""
	_q_lap(name)
	var shared := m.out_dir.path_join("quick_shared.FCStd")
	if own_file or m.model_path != shared:
		m.switch_model(shared if not own_file else m.out_dir.path_join("quick_%s.FCStd" % name), true)
		var t0 := Time.get_ticks_msec()
		while not m.opened and Time.get_ticks_msec() - t0 < 20000: await _frames(1)
	else:
		m._reset_model_state()
	m.new_board = false; m._update_toggles(); m.grid_snap = true
	m.ops.append_array(ops)
	m._restore_counters()
	m.sync()
	await _wait_confirm()
	m.set_tool("rect")
	_q_fresh_ms += Time.get_ticks_msec() - _q_mark


func _q_lap(name: String) -> void:
	"""Start timing a new section (the quick test prints where its time goes)."""
	var now := Time.get_ticks_msec()
	if _q_section != "": _q_times.append([_q_section, now - _q_mark])
	_q_section = name
	_q_mark = now


func _plank(i: int, origin: Vector3, size: Vector3) -> Array:
	return [{"id": "r%d" % i, "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [origin.x, origin.y, origin.z]}, "size": [size.x, size.y]},
		{"id": "pp%d" % i, "type": "push_pull", "target": {"rect": "r%d" % i}, "distance": size.z, "body": "b%d" % i}]


func _run_quick_test() -> void:
	quick = true
	Engine.time_scale = 5.0                       # waves and breathing run 5x faster; the checks don't depend on them
	var t_start := Time.get_ticks_msec()
	while not m.opened: await _frames(1)

	# 0. The worker's hello hash is the one the window computes from the worker's files (W13, T42: all modules)
	var theirs := m._probe_worker(m.worker_port)
	_ok("the window and its worker agree on the worker's hash", theirs != "" and theirs == m._worker_identity(), [theirs, m._worker_identity()])

	# 1. Rectangle: click-click, press-drag-release, a wobbly click (I29)
	await _fresh("rect")
	await _view(Vector3(300, 200, 0), -30, -50, 1.4)
	m.set_tool("rect")
	await _drag_to(Vector3(0, 0, 0), 4); await _button(true)
	await _drag_to(Vector3(200, 100, 0), 9); await _button(false)
	var r: Array = _last_rect()
	_ok("press-drag-release draws a 200 x 100", r[0] == 1 and r[1] == [200.0, 100.0], r)
	await _drag_to(Vector3(300, 0, 0), 4); await _button(true); await _button(false)
	await _drag_to(Vector3(400, 150, 0), 9)
	_ok("after one click and a move, nothing is made yet", _last_rect()[0] == 1, _last_rect())
	await _button(true); await _button(false)
	r = _last_rect()
	_ok("the second click finishes a 100 x 150", r[0] == 2 and r[1] == [100.0, 150.0], r)

	# 2. Push/Pull: a new board, join by default (I04b), B for a separate board, the saved indicator (Q22)
	await _fresh("push", _plank(1, Vector3.ZERO, Vector3(300, 200, 18)))
	await _view(Vector3(150, 100, 20), -30, -40, 1.0)
	await _rect(Vector3(100, 50, 18), Vector3(150, 100, 18), "50,50")
	m.saved_shown.clear()
	await _push(Vector3(125, 75, 18), Vector3(125, 75, 30), "20")
	await _wait_wave()
	_ok("pushed out from a face, it joins that board", _shown_ids() == ["b1"] and not m.ops.back().has("body"), [_shown_ids(), m.ops.back()])
	_ok("the joined bump adds 50 x 50 x 20", is_equal_approx(_bodies()["b1"]["volume_mm3"], 300.0 * 200 * 18 + 50 * 50 * 20), _bodies()["b1"]["volume_mm3"])
	var t0 := Time.get_ticks_msec()
	while m.ui_saved.text != "Saved" and Time.get_ticks_msec() - t0 < 3000: await _frames(1)
	_ok("the save indicator says Saving..., then Saved (T45: however quickly the save lands)",
		m.ui_saved.text == "Saved" and m.saved_shown.slice(-2) == ["Saving…", "Saved"], [m.ui_saved.text, m.saved_shown])
	await _key(KEY_B)
	await _rect(Vector3(200, 50, 18), Vector3(250, 100, 18), "40,40")
	await _push(Vector3(220, 70, 18), Vector3(220, 70, 30), "10")
	await _wait_wave()
	_ok("with B, a separate board", _shown_ids() == ["b1", "b2"], _shown_ids())

	# 3. Faces: a pocket, a through-hole in a side face, a bump on another side face
	await _fresh("faces", _plank(1, Vector3.ZERO, Vector3(300, 200, 18)))
	await _view(Vector3(150, 100, 9), -35, -30, 1.0)
	await _rect(Vector3(50, 50, 18), Vector3(150, 130, 18), "100,80")
	await _push(Vector3(100, 90, 18), Vector3(100, 90, 8), "-10")
	await _wait_wave()
	await _rect(Vector3(200, 0, 4), Vector3(220, 0, 14), "20,10")
	await _push(Vector3(210, 0, 9), Vector3(210, 30, 9), "-200")
	await _wait_wave()
	var thru: Dictionary = m.ops.back()
	_ok("a cut typed to the far face is a through-cut (I24)", thru.get("through", false), thru)
	await _view(Vector3(300, 100, 9), 40, -25, 0.8)
	await _rect(Vector3(300, 50, 2), Vector3(300, 100, 12), "50,10")
	await _push(Vector3(300, 75, 7), Vector3(330, 75, 7), "30")
	await _wait_wave()
	var v: float = _bodies().get("b1", {}).get("volume_mm3", -1)
	_ok("pocket, through-hole and bump add up", is_equal_approx(v, 300.0 * 200 * 18 - 100 * 80 * 10 - 20 * 10 * 200 + 50 * 10 * 30), v)
	_ok("still one board", _shown_ids() == ["b1"], _shown_ids())

	# 4. Snapping (I03b, I23): midpoint, on edge on the grid, push to a point, the back face
	await _fresh("snap", _plank(1, Vector3.ZERO, Vector3(300, 200, 18)) + _plank(2, Vector3(400, 0, 0), Vector3(100, 100, 50)))
	await _view(Vector3(250, 100, 20), -30, -35, 1.1)
	m.set_tool("rect")
	var mid := m.snap(m.pick(_screen_of(Vector3(150, 0, 18))), _screen_of(Vector3(150, 0, 18)))
	_ok("a rectangle corner snaps to an edge's midpoint", mid.get("snap", "") == "midpoint" and mid["point"].is_equal_approx(Vector3(150, 0, 18)), mid)
	var oe := m.snap(m.pick(_screen_of(Vector3(64, 0, 18), Vector2(0, 2))), _screen_of(Vector3(64, 0, 18), Vector2(0, 2)))
	_ok("on an edge, it lands on the grid", oe.get("snap", "") == "on edge" and oe["point"].is_equal_approx(Vector3(60, 0, 18)), oe)
	m.set_tool("push")
	var push = m.tools["push"]
	push.click(_screen_of(Vector3(150, 100, 18), Vector2.ZERO))
	push.mouse_moved(_screen_of(Vector3(400, 0, 50)))
	_ok("a push snaps to another board's corner height", push.state.get("dist", 0) == 32.0 and push.state.get("snap", "") == "endpoint", push.state.get("dist"))
	m.set_tool("push")
	push.click(_screen_of(Vector3(450, 50, 50), Vector2.ZERO))
	push.mouse_moved(_screen_of(Vector3(450, 50, 3), Vector2.ZERO))
	_ok("pushing in snaps to the hidden back face", push.state.get("dist", 0) == -50.0 and push.state.get("snap", "") == "back face", push.state.get("dist"))
	m.set_tool("rect")

	# 5. Move: along an axis, copy into an array, endpoint inference, a hole moved and copied (I14, I18, I21)
	await _fresh("move", _plank(1, Vector3.ZERO, Vector3(100, 50, 18)) + _plank(2, Vector3(300, 200, 0), Vector3(100, 50, 18)))
	await _view(Vector3(200, 100, 0), -30, -45, 1.6)
	await _grab(Vector3(0, 25, 18))
	await _drag_to(Vector3(80, 25, 18), 6)
	var asked := m.length_id
	await _type("5in + 23mm\n")
	await _wait_wave()
	_ok("moved 150 along red", _bbox("b1").slice(0, 2) == [150.0, 0.0], _bbox("b1"))
	_ok("arithmetic in a typed length is worked out at once, the way FreeCAD would", m.length_id == asked, [asked, m.length_id])
	await _grab(Vector3(150, 25, 18))
	await _key(KEY_ALT)
	await _key(KEY_LEFT)                          # lock green
	await _drag_to(Vector3(150, 80, 18), 6)
	asked = m.length_id
	await _type("60mm^1\n")                      # a unit power: the local evaluator declines, FreeCAD answers 60
	_ok("what the local evaluator declines is worked out by FreeCAD", m.length_id == asked + 1, [asked, m.length_id])
	await _frames(4)
	await _type("3x\n")
	await _wait_wave()
	var last: String = _shown_ids().back()
	_ok("copied into a row of 3 at 60 mm", _shown_ids().size() == 5 and _bbox(last).slice(0, 2) == [150.0, 180.0], [_shown_ids(), _bbox(last)])
	m.set_tool("move"); m.tools["move"].reset()
	await _grab(Vector3(300, 200, 18))
	await _drag_to(Vector3(250, 50, 18), 8)
	var kind: String = m.move_state.get("kind", "")
	await _press()
	await _wait_wave()
	_ok("a corner dragged onto another board's corner snaps to it", kind == "endpoint" and _bbox("b2").slice(0, 2) == [250.0, 50.0], [kind, _bbox("b2")])

	await _fresh("hole", [{"id": "r1", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, 0, 0]}, "size": [600, 300]},
		{"id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": 18, "body": "b1"},
		{"id": "r2", "type": "rect", "plane": {"on": {"body": "b1", "normal": [0, 0, 1], "point": [30, 30, 18]}}, "size": [20, 20]},
		{"id": "pp2", "type": "push_pull", "target": {"rect": "r2"}, "distance": -18}])
	await _view(Vector3(300, 150, 0), -20, -50, 1.3)
	await _grab(Vector3(40, 50, 9))
	_ok("grabbing a hole's wall picks the hole", m.move_state.get("cut", {}).get("op", "") == "pp2", m.move_state.get("cut"))
	await _key(KEY_ALT)
	await _key(KEY_RIGHT)
	await _drag_to(Vector3(100, 30, 9), 6)
	await _type("60\n")
	await _frames(4)
	await _type("5x\n")
	await _wait_wave()
	var holes: Array = _bodies()["b1"]["cuts"].filter(func(c): return c["op"] == "pp2")
	_ok("the hole copied into a row of 6", holes.size() == 6 and is_equal_approx(_bodies()["b1"]["volume_mm3"], 600.0 * 300 * 18 - 6 * 20 * 20 * 18), [holes.size(), _bodies()["b1"]["volume_mm3"]])

	# 5b. Linked copies (T12): a row of linked copies, the tint while editing, a hole on one shows on all, U, Detach
	await _fresh("linked", _plank(1, Vector3.ZERO, Vector3(100, 50, 18)))
	await _view(Vector3(250, 25, 0), -25, -50, 1.6)
	await _grab(Vector3(0, 25, 18))
	await _key(KEY_ALT)
	await _key(KEY_RIGHT)                         # lock red
	await _drag_to(Vector3(80, 25, 18), 6)
	await _type("150\n")
	await _frames(4)
	await _type("3x\n")
	await _wait_wave()
	var row: Array = _shown_ids()
	var fams := {}
	for b in row: fams[m.body_family.get(b, "")] = true
	_ok("a 3x copy makes 4 linked boards", row.size() == 4 and fams.size() == 1 and not fams.has(""), [row, m.body_family])
	var copy_b: String = row[2]
	m.set_tool("push")
	await _drag_to(Vector3(325, 25, 18), 4)
	_ok("hovering a copy tints its 3 siblings and the tooltip counts 4", m._siblings_of(copy_b).size() == 3 and m.ui_tip.text.contains("changes 4 linked boards"),
		[m.hover_body, m._siblings_of(copy_b), m.ui_tip.text])
	await _view(Vector3(350, 25, 18), -25, -50, 0.8)          # close enough that the start isn't within snapping range
	await _rect(Vector3(338, 18, 18), Vector3(358, 38, 18), "20,20")
	await _push(Vector3(348, 28, 18), Vector3(348, 28, 8), "-18")
	await _view(Vector3(250, 25, 0), -25, -50, 1.6)
	await _wait_wave()
	var vols := {}
	for b in row: vols[snappedf(_bodies()[b]["volume_mm3"], 0.1)] = true
	_ok("a hole cut in one copy is in all four", vols.keys() == [100.0 * 50 * 18 - 20 * 20 * 18], vols.keys())
	m.set_tool("push")
	await _drag_to(Vector3(475, 25, 18), 4)
	await _key(KEY_U)
	await _wait_wave()
	var uniq: String = m.hover_body
	_ok("U makes the board under the cursor its own", uniq != "" and m.body_family.get(uniq, "x") == "", [uniq, m.body_family])
	await _drag_to(Vector3(175, 25, 18), 4)
	var det: String = m.hover_body
	m._menu("detach")
	await _wait_wave()
	_ok("Edit > Detach from array takes it out of the row", m.body_array.get(det, "x") == "" and m.body_family.get(det, "") != "", [det, m.body_array, m.body_family])

	# 5c. Assemblies you enter (T20, I32): select two boards, Cmd+G, move them as one, enter, draw inside, leave
	await _fresh("assembly", _plank(1, Vector3.ZERO, Vector3(100, 50, 18)) + _plank(2, Vector3(0, 100, 0), Vector3(100, 50, 18))
		+ _plank(3, Vector3(300, 0, 0), Vector3(100, 50, 18)))
	await _view(Vector3(200, 75, 0), -25, -50, 1.4)
	await _key(KEY_SPACE)
	await _click_at(Vector3(50, 25, 18))
	await _key_state(KEY_SHIFT, true)
	await _click_at(Vector3(50, 125, 18))
	await _key_state(KEY_SHIFT, false)
	_ok("Select: click, then Shift-click adds", m.selection == ["b1", "b2"], m.selection)
	await _key_cmd(KEY_G)
	await _wait_wave()
	_ok("Cmd+G makes an assembly of them", m.body_assembly.get("b1", "") != "" and m.body_assembly["b1"] == m.body_assembly.get("b2", "")
		and m.body_assembly.get("b3", "") == "", m.body_assembly)
	_ok("from outside, a board stands for its assembly", m.unit_of("b1")["bodies"].size() == 2, m.unit_of("b1"))
	m.set_tool("move")
	await _grab(Vector3(50, 25, 18))
	await _key(KEY_UP)
	await _drag_to(Vector3(50, 25, 60), 6)
	await _type("100\n")
	await _wait_wave()
	_ok("moving one of its boards moves the whole assembly", _bbox("b1")[2] == 100.0 and _bbox("b2")[2] == 100.0 and _bbox("b3")[2] == 0.0,
		[_bbox("b1"), _bbox("b2"), _bbox("b3")])
	m.set_tool("rect")
	var n_rects: int = m.rects.size()
	await _click_at(Vector3(50, 25, 118))
	_ok("from outside, drawing on an assembly's board is refused with a hint", m.rects.size() == n_rects and not m.tools["rect"].state.get("active", false),
		m.ui_sync.text)
	await _key(KEY_ESCAPE)
	m.set_tool("select")
	await _double_click_at(Vector3(50, 25, 118))
	_ok("double-click enters the assembly", m.context == "assembly:" + m.body_assembly["b1"] and not m.in_context("b3"), m.context)
	m.set_tool("rect")
	await _rect(Vector3(20, 10, 118), Vector3(60, 40, 118), "40,30")
	await _push(Vector3(40, 25, 118), Vector3(40, 25, 108), "-18")
	await _wait_wave()
	_ok("inside, a hole on its board works", _bodies()["b1"]["volume_mm3"] == 100.0 * 50 * 18 - 40 * 30 * 18, _bodies()["b1"]["volume_mm3"])
	await _key(KEY_ESCAPE)
	await _key(KEY_ESCAPE)
	_ok("Esc leaves", m.context == "", m.context)

	# 5d. Mirror groups (T26, A11b): a mirrored copy makes a group; inside, the plane shows and moving the copy
	# moves its original the mirrored way
	await _fresh("mirrorgroup", _plank(1, Vector3.ZERO, Vector3(100, 50, 18)))
	await _view(Vector3(150, 25, 0), -25, -50, 1.2)
	await _grab(Vector3(50, 25, 18))
	await _key(KEY_ALT)                            # copy
	await _key(KEY_SHIFT)                          # mirror
	await _key(KEY_RIGHT)                          # across a red-axis plane (else it's parallel to the grabbed top)
	await _drag_to(Vector3(250, 25, 18), 6)
	await _press()
	await _wait_wave()
	var pair: Array = _shown_ids()
	var grp: String = m.body_assembly.get("b1", "")
	_ok("a mirrored copy makes a mirror group with its original", pair.size() == 2 and grp != "" and m.body_assembly.get(pair[1], "") == grp,
		[pair, m.body_assembly])
	var mir_b: String = pair[1]
	m.set_tool("select")
	await _double_click_at(Vector3(50, 25, 18))
	_ok("inside the mirror group its plane shows", m.context == "assembly:" + grp and m._plane_node.mesh != null, m.context)
	var x0: float = _bbox("b1")[0]
	var mx: float = (_bbox(mir_b)[0] + _bbox(mir_b)[3]) * 0.5
	await _grab(Vector3(mx, 25, 18))
	await _key(KEY_RIGHT)
	await _drag_to(Vector3(mx + 40, 25, 18), 6)
	await _type("50\n")
	await _wait_wave()
	_ok("moving the copy 50 out moves the original 50 the other way", absf(_bbox("b1")[0] - (x0 - 50)) < 0.01, [x0, _bbox("b1"), _bbox(mir_b)])
	await _key(KEY_ESCAPE); await _key(KEY_ESCAPE)

	# 5e. Mirror across another board's face (T27, Q12): point at the face while mirroring
	await _fresh("faceplane", _plank(1, Vector3.ZERO, Vector3(100, 50, 18)) + _plank(2, Vector3(300, 0, 0), Vector3(18, 50, 60)))
	await _view(Vector3(150, 25, 30), -25, -50, 1.2)
	await _grab(Vector3(50, 25, 18))
	await _key(KEY_ALT)
	await _key(KEY_SHIFT)
	await _drag_to(Vector3(309, 25, 60), 6)
	_ok("pointing at b2's top while mirroring snaps the plane to it", m.tools["move"].state.get("mir_face", "") == "b2" and m.ui_tip.text.contains("b2's face"),
		[m.tools["move"].state.get("mir_face", ""), m.ui_tip.text])
	await _press()
	await _wait_wave()
	var fp_ids: Array = _shown_ids()
	var fp_new: String = fp_ids.back() if fp_ids.size() == 3 else ""
	_ok("the copy lands mirrored across b2's top: z 102..120", fp_new != "" and _bbox(fp_new)[2] == 102.0 and _bbox(fp_new)[5] == 120.0,
		[fp_ids, _bbox(fp_new) if fp_new != "" else []])
	await _grab(Vector3(50, 25, 18))
	await _key(KEY_ALT)
	await _key(KEY_SHIFT)
	await _drag_to(Vector3(309, 10, 60), 6)
	await _type("20\n")
	await _wait_wave()
	fp_ids = _shown_ids()
	fp_new = fp_ids.back() if fp_ids.size() == 4 else ""
	_ok("typing 20 stands the plane 20 off the face: z 142..160", fp_new != "" and _bbox(fp_new)[2] == 142.0, [fp_ids, _bbox(fp_new) if fp_new != "" else []])

	# 5f. Wood (T15): pick a wood, paint a board, the board shows it; T turns its grain
	await _fresh("wood", _plank(1, Vector3.ZERO, Vector3(600, 90, 19)))
	await _view(Vector3(560, 45, 10), -50, -25, 0.5)
	m.set_paint_material("black-walnut")
	_ok("picking a wood switches to Paint", m.tool == "paint", m.tool)
	await _click_at(Vector3(300, 45, 19))
	await _wait_wave()
	await _frames(30)
	var wb: Dictionary = _bodies().get("b1", {})
	var node: MeshInstance3D = m.bodies_root.get_node_or_null("b1")
	var smat = node.mesh.surface_get_material(0) if node != null else null
	_ok("painted walnut: FreeCAD has it, the board shows the wood shader", wb.get("material", "") == "black-walnut"
		and smat is ShaderMaterial and smat.shader == m.WOOD, [wb.get("material", ""), smat])
	await _drag_to(Vector3(700, 300, 0), 3)       # off the board: no hover highlight
	await _shot("wood_walnut")
	await _view(Vector3(600, 45, 10), 60, -12, 0.13)
	await _drag_to(Vector3(700, 300, 0), 2)
	await _shot("wood_walnut_end")
	await _view(Vector3(560, 45, 10), -50, -25, 0.5)
	await _drag_to(Vector3(500, 45, 19), 3)
	await _key(KEY_T)
	await _wait_wave()
	_ok("T turns the grain across the board", _bodies()["b1"].get("grain", []) == [0.0, 1.0, 0.0], _bodies()["b1"].get("grain", []))
	await _drag_to(Vector3(700, 300, 0), 2)
	await _frames(20)
	await _shot("wood_walnut_turned")

	# 6. Undo (A28): every undo shows at once, the 21st rebuilds in FreeCAD
	await _fresh("undo")
	var seen := {0: []}
	for i in 11:
		m.ops.append_array(_plank(i + 1, Vector3(120.0 * i, 0, 0), Vector3(100, 50, 18 + 4 * i)))
		m.sync(); await _wait_confirm(); seen[m.ops.size()] = _shown_ids()
	m._restore_counters()
	var bad := []
	var rebuilt := false
	for n in range(m.ops.size(), 0, -1):
		m.test_delay_ms = 60
		m.undo()
		if _shown_ids() != seen.get(n - 1, _shown_ids()) and n % 2 == 1: bad.append(n - 1)
		await _wait_confirm()
		rebuilt = rebuilt or m.ui_sync.text.contains("rebuilt")
	_ok("each undo shows the earlier boards at once", bad.is_empty(), bad)
	_ok("undoing past FreeCAD's 20 steps rebuilds", rebuilt)
	_ok("everything undone", m.ops.is_empty() and _shown_ids().is_empty(), [m.ops.size(), _shown_ids()])

	# 7. A rejection takes what built on it (Q7)
	await _fresh("reject", _plank(1, Vector3.ZERO, Vector3(300, 200, 18)))
	await _view(Vector3(300, 150, 30), -30, -40, 1.6)
	m.test_delay_ms = 600
	m.last_reject_note = ""
	m.force_reject_next = true
	await _rect(Vector3(400, 0, 0), Vector3(500, 100, 0), "100,100")
	await _push(Vector3(450, 50, 0), Vector3(450, 50, 50), "50")
	await _rect(Vector3(420, 20, 50), Vector3(480, 80, 50), "60,60")
	await _push(Vector3(450, 50, 50), Vector3(450, 50, 70), "20")
	await _rect(Vector3(0, 300, 0), Vector3(100, 400, 0), "100,100")
	await _push(Vector3(50, 350, 0), Vector3(50, 350, 30), "30")
	t0 = Time.get_ticks_msec()
	while m.last_reject_note == "" and Time.get_ticks_msec() - t0 < 5000: await _frames(1)   # until the red wave's message (T48)
	await _wait_wave()
	var note: String = m.last_reject_note
	var ids: Array = m.ops.map(func(o): return o["id"])
	_ok("the rejected board and the 2 actions built on it go; the rest stays",
		ids == ["r1", "pp1", "r2", "r4", "pp4"] and _shown_ids() == ["b1", "b3"], [ids, _shown_ids()])
	_ok("one message for all three", note.contains("2 actions that built on it"), note)

	# 8. Trackpad and wheel (I22, I30)
	await _view(Vector3.ZERO, -30, -30, 2.0)
	var y0 := m.yaw
	var pan := InputEventPanGesture.new(); pan.delta = Vector2(100.0 / Main.TRACKPAD_PX, 0.0)
	await _gesture(pan)
	_ok("two fingers orbit like a 100 px drag", is_equal_approx(m.yaw, y0 - 0.8), m.yaw - y0)
	var d0 := m.dist
	for i in 10:
		var tiny := InputEventMouseButton.new(); tiny.button_index = MOUSE_BUTTON_WHEEL_UP; tiny.pressed = true; tiny.factor = 0.1
		tiny.position = m.cursor2d.position; m._unhandled_input(tiny)
	_ok("ten small wheel steps zoom like one notch", is_equal_approx(m.dist, d0 * Main.ZOOM_STEP), m.dist / d0)

	# 9. Switching models (T8)
	_q_lap("models")
	var a: String = m.model_path
	await _fresh("models_b", _plank(1, Vector3.ZERO, Vector3(150, 200, 40)), true)
	m.switch_model(a)
	while not m.opened: await _frames(1)
	await _wait_confirm()
	_ok("switching back reopens the other model's boards", _shown_ids() == ["b1", "b3"] and m.ops.size() == 5, [_shown_ids(), m.ops.size()])
	_ok("the menus exist", m._menus.keys() == ["File", "Edit", "Tools", "View"] or not NativeMenu.has_feature(NativeMenu.FEATURE_GLOBAL_MENU), m._menus.keys())

	# 10. The worker stops: Shop Sketch starts it again and carries on (A27)
	_q_lap("worker")
	if m.worker_pid > 0:
		var pid1: int = m.worker_pid
		OS.kill(pid1)
		await _frames(2)
		m.ops.append_array(_plank(9, Vector3(0, 600, 0), Vector3(50, 50, 10)))
		m._restore_counters()
		m.sync(); await _wait_confirm()
		_ok("a new worker took over and confirmed the next board", m.worker_pid != pid1 and OS.is_process_running(m.worker_pid) and "b9" in _shown_ids(), [m.worker_pid, _shown_ids()])
	else:
		_ok("the quick test runs with its own worker (no --port)", false)


	# Native property panel: inspect -> expression edit -> updated geometry -> undo.
	await _fresh("properties", _plank(1, Vector3.ZERO, Vector3(100, 50, 20)))
	m.properties_panel.show()
	m.set_selection(["b1"])
	await _wait_properties()
	await _shot("properties_board")
	var snapshot: Dictionary = m.properties_panel.data
	_ok("native features appear in the Properties panel", snapshot.get("objects", []).size() >= 3, snapshot.keys())
	var plane: Dictionary = {}
	var width: Dictionary = {}
	for feature in snapshot.get("objects", []):
		if feature.type == "Part::Plane":
			plane = feature
			for entry in feature.fields:
				if entry.path == "Length": width = entry
	_ok("the native rectangle length is editable", width.get("editable", false))
	if not width.is_empty():
		m.properties_panel.object_picker.select(snapshot.objects.find(plane))
		m.properties_panel._show_feature()
		await _shot("properties_dimensions")
		for field_box in m.properties_panel.fields.get_children():
			if field_box is VBoxContainer and field_box.get_child_count() >= 3 and field_box.get_child(0) is Label and field_box.get_child(0).text == "Length":
				field_box.get_child(1).text = "150 mm"
				field_box.get_child(2).get_child(0).select(1)
				field_box.get_child(2).get_child(2).pressed.emit()
				break
		await _wait_confirm()
		await _wait_properties()
		_ok("property edit changes confirmed geometry", is_equal_approx(float(_bodies().b1.volume_mm3), 150000.0))
		_ok("property edits are journal actions", m.ops.back().type == "property_edit")
		m.undo()
		await _wait_confirm()
		await _wait_properties()
		_ok("undo restores native property geometry", is_equal_approx(float(_bodies().b1.volume_mm3), 100000.0))
	m.properties_panel.hide()

	_q_lap("")
	var laps := ""
	for t in _q_times: laps += "%s %.1f  " % [t[0], t[1] / 1000.0]
	print("QUICK timing (s): " + laps + "| opening fresh models %.1f" % (_q_fresh_ms / 1000.0))
	Engine.time_scale = 1.0
	print("QUICK %d passed, %d failed in %.1f s" % [_q[0], _q[1], (Time.get_ticks_msec() - t_start) / 1000.0])
	get_tree().quit(1 if _q[1] > 0 else 0)


func _wait_properties() -> void:
	var deadline := Time.get_ticks_msec() + 10000
	while m.properties_seq != m.seq and Time.get_ticks_msec() < deadline:
		await _frames(1)
	_ok("properties reply arrives for the current state", m.properties_seq == m.seq)


func _run_heavy_test() -> void:
	# a real model opened from its FreeCAD file: an 18 mm panel with 32 through-holes
	var t0 := Time.get_ticks_msec()
	while m.ops.is_empty() and Time.get_ticks_msec() - t0 < 20000:
		await _frames(1)
	await _wait_confirm()
	print("HEAVYTEST opened %s with %d ops" % [m.model_path.get_file(), m.ops.size()])
	m.target = Main.m2g(Vector3(560, 300, 0)); m.dist = 1.9; m.yaw = deg_to_rad(-28); m.pitch = deg_to_rad(-38)
	m._update_camera()
	m.cursor2d.position = Vector2(900, 700)
	_say("Opened model.FCStd: an 18 mm panel with 32 holes, each a real FreeCAD cut")
	await _hold(70)
	# 1. something light first: a new block on the floor (FreeCAD answers in a few ms)
	_say("A light action: new block on the floor")
	await _key(KEY_R)
	await _drag_to(Vector3(1300, 100, 0), 14); await _press()
	await _drag_to(Vector3(1400, 250, 0), 12)
	await _type("100,150\n")
	await _key(KEY_P)
	await _drag_to(Vector3(1350, 175, 0), 10); await _press()
	await _drag_to(Vector3(1350, 175, 150), 16)
	var ta := Time.get_ticks_msec()
	await _type("150\n")
	await _wait_wave()
	print("HEAVYTEST light action confirmed after %d ms wall" % (Time.get_ticks_msec() - ta))
	await _hold(30)
	# 2. the heavy one: push the panel's holed top face down 6 mm
	_say("A heavy action: push the holed top face down 6 mm")
	await _key(KEY_P)
	await _drag_to(Vector3(120, 130, 18), 16); await _press()
	await _drag_to(Vector3(120, 130, 12), 12)
	var tb := Time.get_ticks_msec()
	await _type("-6\n")
	await _wait_wave()
	print("HEAVYTEST heavy action confirmed after %d ms wall | %s" % [Time.get_ticks_msec() - tb, m.ui_sync.text])
	_say("FreeCAD confirmed: %s" % m.ui_sync.text.replace("✓ FreeCAD confirmed  ", ""))
	await _hold(90)
	print("HEAVYTEST done, ops: ", m.ops.size(), " | ", m.ui_sync.text)
	get_tree().quit()


func _frames(n := 2) -> void:
	for i in n:
		if not (quick and m.quick_test): await get_tree().physics_frame   # --fast keeps it: picking a fresh draft needs one
		await get_tree().process_frame


func _shot(name: String) -> void:
	await RenderingServer.frame_post_draw
	if m.shots_dir != "":
		get_viewport().get_texture().get_image().save_png(m.shots_dir.path_join(name + ".png"))
		print("SHOT ", name, "  | ", m.ui_sync.text)


func _mouse_to(p_model: Vector3) -> Vector2:
	var s := m.cam.unproject_position(Main.m2g(p_model))
	var ev := InputEventMouseMotion.new()
	ev.position = s; ev.global_position = s
	Input.parse_input_event(ev)
	await _frames(1)
	return s


func _click(p_model: Vector3) -> void:
	var s: Vector2 = await _mouse_to(p_model)
	for pressed in [true, false]:
		var ev := InputEventMouseButton.new()
		ev.button_index = MOUSE_BUTTON_LEFT; ev.pressed = pressed
		ev.position = s; ev.global_position = s
		Input.parse_input_event(ev)
	await _frames(1)


func _type(txt: String) -> void:
	for ch in txt:
		var ev := InputEventKey.new()
		ev.pressed = true
		if ch == "\n": ev.keycode = KEY_ENTER
		else: ev.unicode = ch.unicode_at(0); ev.keycode = OS.find_keycode_from_string(ch.to_upper())
		Input.parse_input_event(ev)
		var up := ev.duplicate(); up.pressed = false
		Input.parse_input_event(up)
	await _frames(1)

	var deadline := Time.get_ticks_msec() + 10000
	while not m.length_pending.is_empty() and Time.get_ticks_msec() < deadline:
		await _frames(1)
	if not m.length_pending.is_empty():
		_ok("a typed length came back from FreeCAD within 10 s", false, txt)


func _key_shift(k: Key) -> void:
	var ev := InputEventKey.new(); ev.keycode = k; ev.pressed = true; ev.shift_pressed = true
	Input.parse_input_event(ev)
	var up := ev.duplicate(); up.pressed = false
	Input.parse_input_event(up)
	await _frames(1)


func _key(k: Key) -> void:
	var ev := InputEventKey.new(); ev.keycode = k; ev.pressed = true
	Input.parse_input_event(ev)
	var up := ev.duplicate(); up.pressed = false
	Input.parse_input_event(up)
	await _frames(1)


func _wait_confirm() -> void:
	var t0 := Time.get_ticks_msec()
	while m.dirty or m.in_flight:
		await get_tree().process_frame
		if Time.get_ticks_msec() - t0 > 90000: print("TIMEOUT waiting for worker"); return
	await _frames(3)


func _run_test() -> void:
	m.target = Main.m2g(Vector3(230, 150, 200)); m.dist = 1.6
	m._update_camera()
	await _frames(5)
	# 1. side panel: rectangle on the ground, push up
	await _key(KEY_R)
	await _click(Vector3(0, 0, 0))
	await _mouse_to(Vector3(15, 200, 0))
	await _shot("01_rect_dragging")
	await _type("20,300\n")
	await _key(KEY_P)
	await _click(Vector3(10, 150, 0))
	await _mouse_to(Vector3(10, 150, 250))
	await _shot("02_push_preview")
	await _type("400\n")
	await _shot("03_panel_draft_before_freecad")
	await _wait_confirm()
	await _shot("04_panel_confirmed")
	# 2. second panel
	await _key(KEY_R)
	await _click(Vector3(440, 0, 0))
	await _mouse_to(Vector3(455, 200, 0))
	await _type("20,300\n")
	await _key(KEY_P)
	await _click(Vector3(450, 150, 0))
	await _mouse_to(Vector3(450, 150, 200))
	await _type("400\n")
	# 3. top board, starting from the panel's corner (endpoint snap from a few mm away)
	await _key(KEY_R)
	await _click(Vector3(3, 4, 400))
	await _mouse_to(Vector3(200, 150, 400))
	await _shot("05_top_rect_snapped")
	await _type("460,300\n")
	await _key(KEY_P)
	await _click(Vector3(230, 150, 400))
	await _mouse_to(Vector3(230, 150, 420))
	await _type("20\n")
	await _shot("06_three_boards_some_draft")
	await _wait_confirm()
	await _shot("07_three_boards_confirmed")
	# 4. hand slot: rectangle on the top board, push -20 to cut through
	await _key(KEY_R)
	await _click(Vector3(170, 140, 420))
	await _mouse_to(Vector3(200, 150, 420))
	await _type("120,20\n")
	await _key(KEY_P)
	await _click(Vector3(230, 150, 420))
	await _mouse_to(Vector3(230, 150, 410))
	await _shot("08_cut_preview")
	await _type("-20\n")
	await _wait_confirm()
	# 5. push an existing confirmed face: pull the front edge of the top board out 40 mm
	await _key(KEY_P)
	await _click(Vector3(300, 0, 410))
	await _mouse_to(Vector3(300, -30, 410))
	await _shot("09_face_push_preview")
	await _type("40\n")
	await _wait_confirm()
	m.yaw = deg_to_rad(-60); m.pitch = deg_to_rad(-32); m.dist = 1.5; m._update_camera()
	await _frames(3)
	await _shot("10_final_confirmed")
	await _key(KEY_D)
	await _wait_confirm()
	await _frames(5)
	print("TEST oplog ops: ", m.ops.size(), "  last round trip ms: ", m.last_sync_ms)
	print("TEST status: ", m.ui_sync.text)
	get_tree().quit()
