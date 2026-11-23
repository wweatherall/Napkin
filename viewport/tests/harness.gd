extends Node
## One harness per test window: shared viewport, pacing, assertions and quick-section timing.

const Main := preload("res://main.gd")
var m: Main
var quick := false
var _q := [0, 0]
var _q_section := ""
var _q_times := []
var _q_mark := 0
var _q_fresh_ms := 0


func _make_fake_cursor() -> void:
	var layer := CanvasLayer.new(); layer.layer = 10; add_child(layer)
	m.cursor2d = Node2D.new(); layer.add_child(m.cursor2d)
	var pts := PackedVector2Array([Vector2(0, 0), Vector2(0, 22), Vector2(6, 17), Vector2(10, 26), Vector2(14, 24), Vector2(10, 15), Vector2(17, 15)])
	var poly := Polygon2D.new(); poly.polygon = pts; poly.color = Color.WHITE; m.cursor2d.add_child(poly)
	var line := Line2D.new(); line.points = pts; line.add_point(Vector2(0, 0)); line.width = 1.5
	line.default_color = Color.BLACK; m.cursor2d.add_child(line)

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

## menus.gd's run drops a repeat of the same command within 150 ms (the menu and its key both fired). A person's
## two presses are never that close, but a --fast run's can be (T85): wait the filter out before each press.
func _menu_settle() -> void:
	while m.menus.menu_last.values().any(func(t): return Time.get_ticks_msec() - int(t) < 160):
		await get_tree().process_frame

func _menu(tag: String) -> void:
	await _menu_settle()
	m.menus.run(tag)

func _key_state(k: Key, down: bool) -> void:
	var ev := InputEventKey.new(); ev.keycode = k; ev.pressed = down
	Input.parse_input_event(ev)
	await _frames(1)

func _key_cmd(k: Key) -> void:
	await _menu_settle()
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

func _view(target_m: Vector3, yaw_deg: float, pitch_deg: float, d: float) -> void:
	m.camera_rig.target = Main.m2g(target_m)
	m.camera_rig.yaw = deg_to_rad(yaw_deg)
	m.camera_rig.pitch = deg_to_rad(pitch_deg)
	m.camera_rig.dist = d
	m.camera_rig.update_camera()
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

func _grab(p_model: Vector3) -> void:
	await _key(KEY_M)
	await _drag_to(p_model, 10); await _press()

func _log_move(tag: String) -> void:
	print("INFER ", tag, " kind=", m.move_state.get("kind", ""), " vec=", m.move_state.get("vec", Vector3.ZERO), " mode=", m.move_state.get("lock_mode", ""))

func _say(txt: String) -> void:
	if m.caption == null:
		var layer := CanvasLayer.new(); layer.layer = 9; add_child(layer)
		m.caption = Label.new(); layer.add_child(m.caption)
		m.caption.position = Vector2(24, 92)
		m.caption.add_theme_font_size_override("font_size", 26)
		m.caption.add_theme_color_override("font_color", Color(0.12, 0.12, 0.12))
	m.caption.text = txt

func _shown_ids() -> Array:
	var ids := []
	for mi in m.bodies_root.find_children("*", "MeshInstance3D", true, false):
		if mi.has_meta("body_mesh"): ids.append(String(mi.name))
	ids.sort()
	var keys := m.body_tris.keys()
	keys.sort()
	return ids if ids == keys else ["MISMATCH meshes %s vs picking data %s" % [ids, keys]]

func _gesture(ev: InputEvent) -> void:
	ev.position = Vector2(640, 420)
	Input.parse_input_event(ev)
	await _frames(2)

func _screen_of(p_model: Vector3, nudge := Vector2(3, 2)) -> Vector2:
	return m.cam.unproject_position(Main.m2g(p_model)) + nudge

func _button(pressed: bool) -> void:
	var ev := InputEventMouseButton.new()
	ev.button_index = MOUSE_BUTTON_LEFT; ev.pressed = pressed
	ev.position = m.cursor2d.position; ev.global_position = m.cursor2d.position
	Input.parse_input_event(ev)
	await _frames(1)

func _last_rect() -> Array:
	var rs := m.ops.filter(func(o): return o["type"] == "rect")
	return [rs.size(), rs.back()["size"] if not rs.is_empty() else null]

func _board_ops(w: float, h: float) -> Array:
	return [{"id": "r1", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, 0, 0]}, "size": [w, 200]},
		{"id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": h, "body": "b1"}]

func _top() -> float:
	for b in JSON.parse_string(FileAccess.get_file_as_string(m.out_dir.path_join("bodies.json"))):
		if b["id"] == "b1": return b["world_bbox"][5]
	return -1.0

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
	m.new_board = false; m.ui.update_toggles(); m.grid_snap = true
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


# The quick test's sections, in the order one session runs them; --quick-lane=N runs lane N only, in a window
# with its own worker, so tools/quicktest.sh runs the lanes side by side (T49). A section starts from _fresh, so
# any lane order works, except reject -> trackpad -> models -> worker, which carry on from each other.

func _wait_properties() -> void:
	var deadline := Time.get_ticks_msec() + 10000
	while m.properties_seq != m.seq and Time.get_ticks_msec() < deadline:
		await _frames(1)
	_ok("properties reply arrives for the current state", m.properties_seq == m.seq)

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
	await _menu_settle()
	var ev := InputEventKey.new(); ev.keycode = k; ev.pressed = true; ev.shift_pressed = true
	Input.parse_input_event(ev)
	var up := ev.duplicate(); up.pressed = false
	Input.parse_input_event(up)
	await _frames(1)

func _key_cmd_shift(k: Key) -> void:
	await _menu_settle()
	var ev := InputEventKey.new(); ev.keycode = k; ev.pressed = true; ev.meta_pressed = true; ev.shift_pressed = true
	Input.parse_input_event(ev)
	var up := ev.duplicate(); up.pressed = false
	Input.parse_input_event(up)
	await _frames(1)

func _key(k: Key) -> void:
	await _menu_settle()
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


func id(alias: String) -> String:
	# Resolve current-path identities first: reopened reservations also include abandoned futures.
	var current := {}
	_collect_ids(m.ops, current)
	if current.has(alias): return alias
	for identity in current:
		if String(identity).begins_with(alias + "_"): return identity
	for identity in m.doc.reserved_ids:
		if String(identity).begins_with(alias + "_"): return identity
	return alias


func _collect_ids(value, into: Dictionary) -> void:
	if value is String:
		into[value] = true
	elif value is Array:
		for item in value: _collect_ids(item, into)
	elif value is Dictionary:
		for key in value:
			_collect_ids(key, into)
			_collect_ids(value[key], into)
