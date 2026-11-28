extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 5. Move: along an axis, copy into an array, endpoint inference, a hole moved and copied (I14, I18, I21)
	await harness._fresh("move", harness._plank(1, Vector3.ZERO, Vector3(100, 50, 18)) + harness._plank(2, Vector3(300, 200, 0), Vector3(100, 50, 18)))
	await harness._view(Vector3(200, 100, 0), -30, -45, 1.6)
	await harness._grab(Vector3(0, 25, 18))
	await harness._drag_to(Vector3(80, 25, 18), 6)
	var asked := m.length_id
	await harness._type("5in + 23mm\n")
	await harness._wait_wave()
	harness._ok("moved 150 along red", harness._bbox(harness.id("b1")).slice(0, 2) == [150.0, 0.0], harness._bbox(harness.id("b1")))
	harness._ok("arithmetic in a typed length is worked out at once, the way FreeCAD would", m.length_id == asked, [asked, m.length_id])
	await harness._grab(Vector3(150, 25, 18))
	await harness._key(KEY_ALT)
	await harness._key(KEY_LEFT)                          # lock green
	await harness._drag_to(Vector3(150, 80, 18), 6)
	asked = m.length_id
	await harness._type("60mm^1\n")                      # a unit power: the local evaluator declines, FreeCAD answers 60
	harness._ok("what the local evaluator declines is worked out by FreeCAD", m.length_id == asked + 1, [asked, m.length_id])
	await harness._frames(4)
	await harness._type("3x\n")
	await harness._wait_wave()
	var last: String = harness._shown_ids().back()
	harness._ok("copied into a row of 3 at 60 mm", harness._shown_ids().size() == 5 and harness._bbox(last).slice(0, 2) == [150.0, 180.0], [harness._shown_ids(), harness._bbox(last)])
	m.set_tool("move"); m.tools["move"].reset()
	await harness._grab(Vector3(300, 200, 18))
	await harness._drag_to(Vector3(250, 50, 18), 8)
	var kind: String = m.move_state.get("kind", "")
	await harness._press()
	await harness._wait_wave()
	harness._ok("a corner dragged onto another board's corner snaps to it", kind == "endpoint" and harness._bbox(harness.id("b2")).slice(0, 2) == [250.0, 50.0], [kind, harness._bbox(harness.id("b2"))])

	# Pre-click array preview (xN / /N) and post-click amend (T123 / I66)
	await harness._fresh("move_array_preview", harness._plank(1, Vector3.ZERO, Vector3(100, 50, 18)))
	await harness._view(Vector3(300, 25, 0), -30, -45, 2.0)
	await harness._grab(Vector3(0, 25, 18))
	await harness._key(KEY_RIGHT)
	await harness._drag_to(Vector3(150, 25, 18), 6)
	await harness._type("x4\n")
	var mv_vec: Vector3 = m.move_state.get("vec", Vector3.ZERO)
	var single_count: int = m.body_tris[harness.id("b1")].size()
	var preview_verts: PackedVector3Array = m.overlay.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX] if m.overlay.mesh != null else PackedVector3Array()
	var preview_xs := []
	if preview_verts.size() == 4 * single_count and single_count > 0:
		for ci in 4:
			var min_x := INF
			for vi in range(ci * single_count, (ci + 1) * single_count):
				min_x = minf(min_x, preview_verts[vi].x * 1000.0)
			preview_xs.append(min_x)
	var preview_ok := preview_xs.size() == 4
	if preview_ok:
		for ci in 4:
			if absf(preview_xs[ci] - (ci + 1) * mv_vec.x) > 0.5:
				preview_ok = false
	harness._ok("typing x4 before clicking stays active, enables copy, and previews 4 shifted copies",
		m.tools["move"].in_gesture() and m.tools["move"].copy and m.move_state.get("count", 0) == 4 and preview_ok,
		[m.tools["move"].in_gesture(), m.tools["move"].copy, m.move_state.get("count", 0), preview_xs, mv_vec.x])
	await harness._press()
	await harness._wait_wave()
	var ids_x4 := harness._shown_ids()
	var last_x4: String = ids_x4.back()
	harness._ok("clicking after x4 preview commits all 4 copies in one op",
		ids_x4.size() == 5 and m.ops.back().get("count", 0) == 4 and absf(harness._bbox(last_x4)[0] - 4.0 * mv_vec.x) < 1.0,
		[ids_x4, m.ops.back(), harness._bbox(last_x4)])

	# Amend pre-previewed x4 down to x2 after clicking
	await harness._type("x2\n")
	await harness._wait_wave()
	harness._ok("typing x2 after clicking a pre-previewed x4 array amends it to 2 copies",
		harness._shown_ids().size() == 3 and m.ops.back().get("count", 0) == 2,
		[harness._shown_ids(), m.ops.back()])

	# Pre-click /3 + typed distance 300
	await harness._fresh("move_divide_preview", harness._plank(1, Vector3.ZERO, Vector3(100, 50, 18)))
	await harness._view(Vector3(200, 25, 0), -30, -45, 1.8)
	await harness._grab(Vector3(0, 25, 18))
	await harness._key(KEY_ALT)
	await harness._key(KEY_RIGHT)
	await harness._drag_to(Vector3(150, 25, 18), 6)
	await harness._type("/3\n")
	harness._ok("typing /3 before clicking enables divide preview",
		m.tools["move"].in_gesture() and m.move_state.get("divide", false) and m.move_state.get("count", 0) == 3,
		[m.tools["move"].in_gesture(), m.move_state.get("divide", false), m.move_state.get("count", 0)])
	await harness._type("300\n")
	await harness._wait_wave()
	var div_xs := []
	for bid in harness._shown_ids():
		if bid != harness.id("b1"):
			div_xs.append(harness._bbox(bid)[0])
	div_xs.sort()
	harness._ok("typing 300 after /3 preview commits 3 evenly distributed copies at 100, 200, 300 mm",
		div_xs == [100.0, 200.0, 300.0], [harness._shown_ids(), div_xs])

	# Pre-click x3 + click, then amend spacing to 250
	await harness._fresh("move_array_amend_dist", harness._plank(1, Vector3.ZERO, Vector3(100, 50, 18)))
	await harness._view(Vector3(400, 25, 0), -30, -45, 2.2)
	await harness._grab(Vector3(0, 25, 18))
	await harness._key(KEY_RIGHT)
	await harness._drag_to(Vector3(150, 25, 18), 6)
	await harness._type("x3\n")
	await harness._press()
	await harness._wait_wave()
	await harness._type("250\n")
	await harness._wait_wave()
	var amend_xs := []
	for bid in harness._shown_ids():
		if bid != harness.id("b1"):
			amend_xs.append(harness._bbox(bid)[0])
	amend_xs.sort()
	harness._ok("typing 250 after clicking a pre-previewed x3 array amends spacing to 250 mm keeping 3 copies",
		amend_xs == [250.0, 500.0, 750.0], [harness._shown_ids(), amend_xs])

	for form in ["5x", "x5", "*5", "5*", "/5"]:
		await _begin_copy()
		var distance: float = m.move_state["vec"].x
		var length_id_before := m.length_id
		await _type_measurement(form)
		var divide: bool = form == "/5"
		var preview_ok_for_form: bool = m.tools["move"].in_gesture() and not m.tools["move"].mirror \
			and m.move_state.get("count") == 5 and m.move_state.get("divide") == divide and m.length_id == length_id_before
		await harness._press()
		await _check_copies("%s during a copy-move previews and commits five copies" % form, divide, distance, preview_ok_for_form)

		await _begin_copy()
		await harness._press()
		var copy_op: Dictionary = m.ops.back()
		length_id_before = m.length_id
		await _type_measurement(form)
		var amended: bool = m.ops.back()["id"] == copy_op["id"] and not m.tools["move"].mirror and m.length_id == length_id_before
		await _check_copies("%s after a copy-move amends it to five copies" % form, divide, copy_op["vector"][0], amended)

	await _begin_copy()
	await harness._key(KEY_ALT)
	var length_id := m.length_id
	await _type_measurement("50*2")
	await harness._wait_wave()
	var moved := harness._bbox(harness.id("b1"))
	harness._ok("50*2 during a move is a 100 mm distance",
		moved.slice(0, 2) == [100.0, 0.0] and not m.ops.back().get("copy", true) and m.length_id == length_id,
		[moved, m.ops.back(), length_id, m.length_id])


func _begin_copy() -> void:
	await harness._fresh("move_copy_counts", harness._plank(1, Vector3.ZERO, Vector3(90, 50, 18)))
	await harness._view(Vector3(240, 25, 0), -30, -45, 2.2)
	await harness._grab(Vector3(0, 25, 18))
	await harness._key(KEY_ALT)
	await harness._key(KEY_RIGHT)
	await harness._drag_to(Vector3(500, 25, 18), 6)


func _type_measurement(txt: String) -> void:
	var star := txt.find("*")
	if star < 0:
		await harness._type(txt + "\n")
		return
	if star > 0:
		await harness._type(txt.left(star))
	# A top-row asterisk includes a real Shift press, which Move also uses for mirror.
	await harness._key_state(KEY_SHIFT, true)
	var key := InputEventKey.new()
	key.keycode = KEY_8
	key.physical_keycode = KEY_8
	key.unicode = "*".unicode_at(0)
	key.shift_pressed = true
	key.pressed = true
	Input.parse_input_event(key)
	var up := key.duplicate()
	up.pressed = false
	Input.parse_input_event(up)
	await harness._key_state(KEY_SHIFT, false)
	await harness._type(txt.substr(star + 1) + "\n")


func _check_copies(name: String, divide: bool, distance: float, action_ok: bool) -> void:
	await harness._wait_wave()
	var op: Dictionary = m.ops.back()
	var positions := []
	for bid in harness._shown_ids():
		if bid != harness.id("b1"):
			positions.append(harness._bbox(bid)[0])
	positions.sort()
	var step := distance / 5.0 if divide else distance
	var expected := []
	for i in range(1, 6):
		expected.append(snappedf(i * step, 0.01))
	harness._ok(name, action_ok and op.get("count") == 5 and op.get("divide") == divide and positions == expected,
		[action_ok, op, positions, expected])
