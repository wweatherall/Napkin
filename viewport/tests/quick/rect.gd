extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 1. Rectangle: click-click, press-drag-release, a wobbly click (I43)
	await harness._fresh("rect")
	await harness._view(Vector3(300, 200, 0), -30, -50, 1.4)
	m.set_tool("rect")
	await harness._drag_to(Vector3(0, 0, 0), 4); await harness._button(true)
	await harness._drag_to(Vector3(200, 100, 0), 9); await harness._button(false)
	var r: Array = harness._last_rect()
	harness._ok("press-drag-release draws a 200 x 100", r[0] == 1 and r[1] == [200.0, 100.0], r)
	await harness._drag_to(Vector3(300, 0, 0), 4); await harness._button(true); await harness._button(false)
	await harness._drag_to(Vector3(400, 150, 0), 9)
	harness._ok("after one click and a move, nothing is made yet", harness._last_rect()[0] == 1, harness._last_rect())
	await harness._button(true); await harness._button(false)
	r = harness._last_rect()
	harness._ok("the second click finishes a 100 x 150", r[0] == 2 and r[1] == [100.0, 150.0], r)

	# 2. After-the-fact typed dimensions (I65, T122): amend once, retype a second time, tool switch, undo.
	await harness._fresh("rect_amend")
	await harness._view(Vector3(300, 200, 0), -30, -50, 1.4)
	m.set_tool("rect")
	await harness._drag_to(Vector3(300, 100, 0), 4); await harness._button(true); await harness._button(false)
	await harness._drag_to(Vector3(200, 250, 0), 9); await harness._button(true); await harness._button(false)
	await harness._wait_confirm()
	var orig: Dictionary = m.ops.back().duplicate(true)
	var rid: String = orig["id"]
	harness._ok("placed click-click rectangle in -X/+Y quadrant before amend",
		m.ops.size() == 1 and orig["size"] == [100.0, 150.0] and orig["corner"] == [-100.0, 0.0], orig)

	await harness._type("200, 120\n")
	await harness._wait_confirm()
	var amended: Dictionary = m.ops.back()
	var pts: PackedVector3Array = m.rects.get(rid, {}).get("pts", PackedVector3Array())
	var lo := Vector3(INF, INF, INF)
	var hi := -lo
	for p in pts:
		lo = lo.min(p); hi = hi.max(p)
	var draft_span := hi - lo
	harness._ok("after-the-fact 200, 120 keeps ID/origin/plane/quadrant and updates draft and FreeCAD",
		m.ops.size() == 1 and amended["id"] == rid and amended["plane"] == orig["plane"]
		and amended["size"] == [200.0, 120.0] and amended["corner"] == [-200.0, 0.0]
		and is_equal_approx(draft_span.x, 200.0) and is_equal_approx(draft_span.y, 120.0)
		and m.doc.confirmed_ids.has(rid) and m.reject_note == "",
		[amended, draft_span, m.doc.confirmed_ids.has(rid), m.reject_note])

	await harness._type("80, 90\n")
	await harness._wait_confirm()
	var amended2: Dictionary = m.ops.back()
	harness._ok("retyping 80, 90 a second time updates the same rectangle cleanly",
		m.ops.size() == 1 and amended2["id"] == rid and amended2["plane"] == orig["plane"]
		and amended2["size"] == [80.0, 90.0] and amended2["corner"] == [-80.0, 0.0]
		and m.doc.confirmed_ids.has(rid) and m.reject_note == "",
		[amended2, m.doc.confirmed_ids.has(rid), m.reject_note])

	# Switching tools with P is not eaten by the measurements box; returning to Rectangle does not amend old rect.
	await harness._key(KEY_P)
	var switched_to_push: bool = m.tool == "push" and m.vcb == ""
	await harness._key(KEY_R)
	await harness._type("300, 300\n")
	await harness._wait_confirm()
	harness._ok("pressing P switches to Push/Pull and returning to Rectangle does not amend old rect",
		switched_to_push and m.ops.size() == 1 and m.ops.back()["size"] == [80.0, 90.0],
		[switched_to_push, m.tool, m.ops.back()])

	# Undo after amending reverts in one step, and typing after undo does not resurrect or alter an earlier op.
	await harness._drag_to(Vector3(0, 0, 0), 4); await harness._button(true); await harness._button(false)
	await harness._drag_to(Vector3(60, 40, 0), 9); await harness._button(true); await harness._button(false)
	await harness._type("70, 50\n")
	await harness._wait_confirm()
	var count_before_undo := m.ops.size()
	await harness._key_cmd(KEY_Z)
	await harness._wait_confirm()
	var count_after_undo := m.ops.size()
	await harness._type("100, 100\n")
	await harness._wait_confirm()
	harness._ok("undo after amend reverts in one step and typing afterwards does not resurrect or alter earlier op",
		count_before_undo == 2 and count_after_undo == 1 and m.ops.size() == 1
		and m.ops.back()["id"] == rid and m.ops.back()["size"] == [80.0, 90.0],
		[count_before_undo, count_after_undo, m.ops])

	# 3. Rotated Rectangle (H129, T84): R toggle, tool switch reset, 3-click rotated rect, typed length/width, amend.
	await harness._fresh("rect_rotated")
	await harness._view(Vector3(300, 200, 0), -30, -50, 1.4)
	m.set_tool("rect")
	await harness._key(KEY_R)
	var toggled_on: bool = m.tools["rect"].rotated and m.tools["rect"].tip() == "Rotated Rectangle" and "Rotated Rectangle:" in m.tools["rect"].hint()
	await harness._key(KEY_P)
	await harness._key(KEY_R)
	var reset_on_switch: bool = not m.tools["rect"].rotated and m.tools["rect"].tip() == "Rectangle"
	harness._ok("R toggles Rotated Rectangle and switching tools resets to Rectangle",
		toggled_on and reset_on_switch, [toggled_on, reset_on_switch, m.tools["rect"].tip(), m.tools["rect"].hint()])

	await harness._key(KEY_R)
	await harness._drag_to(Vector3(0, 0, 0), 4); await harness._button(true); await harness._button(false)
	await harness._drag_to(Vector3(80, 60, 0), 6)
	var label_edge: String = m.tools["rect"].vcb_label()
	await harness._button(true); await harness._button(false)
	await harness._drag_to(Vector3(-30, 40, 0), 6)
	var label_width: String = m.tools["rect"].vcb_label()
	await harness._button(true); await harness._button(false)
	await harness._wait_confirm()
	var rot_op: Dictionary = m.ops.back().duplicate(true)
	var rot_pts: PackedVector3Array = m.rects.get(rot_op.get("id", ""), {}).get("pts", PackedVector3Array())
	var expected_pts := [Vector3(0, 0, 0), Vector3(80, 60, 0), Vector3(50, 100, 0), Vector3(-30, 40, 0)]
	var pts_ok := rot_pts.size() == 4
	if pts_ok:
		for i in 4:
			if rot_pts[i].distance_to(expected_pts[i]) > 0.01:
				pts_ok = false
	harness._ok("3-click rotated rectangle draws rotated draft, emits x, and confirms in FreeCAD",
		m.ops.size() == 1 and label_edge == "Length" and label_width == "Width"
		and rot_op.has("x") and Vector3(rot_op["x"][0], rot_op["x"][1], rot_op["x"][2]).distance_to(Vector3(0.8, 0.6, 0)) < 0.01
		and is_equal_approx(float(rot_op["size"][0]), 100.0) and is_equal_approx(float(rot_op["size"][1]), 50.0)
		and pts_ok and m.doc.confirmed_ids.has(rot_op["id"]) and m.reject_note == "",
		[label_edge, label_width, rot_op, rot_pts, m.doc.confirmed_ids.has(rot_op.get("id", "")), m.reject_note])
	var drawn_x: Vector3 = m.tools["rect"].last_meta.get("x", Vector3.ZERO)
	harness._ok("rotated rectangle sends its direction unrounded (T145 finding 7)",
		rot_op.has("x") and Vector3(rot_op["x"][0], rot_op["x"][1], rot_op["x"][2]).is_equal_approx(drawn_x),
		[rot_op.get("x"), drawn_x])

	# Typed first-edge length and perpendicular width, then after-the-fact length, width amend.
	await harness._drag_to(Vector3(200, 0, 0), 4); await harness._button(true); await harness._button(false)
	await harness._drag_to(Vector3(260, 80, 0), 6)
	await harness._type("150\n")
	await harness._drag_to(Vector3(120, 60, 0), 6)
	await harness._type("40\n")
	await harness._wait_confirm()
	var typed_op: Dictionary = m.ops.back().duplicate(true)
	harness._ok("typing first-edge length and width commits rotated rectangle",
		m.ops.size() == 2 and typed_op.has("x")
		and Vector3(typed_op["x"][0], typed_op["x"][1], typed_op["x"][2]).distance_to(Vector3(0.6, 0.8, 0)) < 0.01
		and is_equal_approx(float(typed_op["size"][0]), 150.0) and is_equal_approx(float(typed_op["size"][1]), 40.0)
		and m.doc.confirmed_ids.has(typed_op["id"]) and m.reject_note == "",
		[m.ops.size(), typed_op, m.reject_note])

	await harness._type("200, 60\n")
	await harness._wait_confirm()
	var amended_rot: Dictionary = m.ops.back()
	harness._ok("after-the-fact length, width amend preserves rotated axes",
		m.ops.size() == 2 and amended_rot["id"] == typed_op["id"]
		and amended_rot.get("x") == typed_op.get("x")
		and is_equal_approx(float(amended_rot["size"][0]), 200.0) and is_equal_approx(float(amended_rot["size"][1]), 60.0)
		and m.doc.confirmed_ids.has(typed_op["id"]) and m.reject_note == "",
		[amended_rot, m.reject_note])
