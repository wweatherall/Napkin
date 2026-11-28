extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	await harness._fresh("selection", harness._plank(1, Vector3.ZERO, Vector3(100, 50, 18)) + harness._plank(2, Vector3(200, 0, 0), Vector3(100, 50, 18)) + harness._plank(3, Vector3(400, 0, 0), Vector3(100, 50, 18)))
	await harness._view(Vector3(250, 25, 0), -15, -55, 1.8)
	m.set_tool("select")
	var select = m.tools["select"]
	var lo := Vector2(INF, INF); var hi := -lo
	for b in [harness.id("b1"), harness.id("b2"), harness.id("b3")]:
		for v in m.body_verts[b]:
			var point: Vector2 = m.cam.unproject_position(Main.m2g(v))
			lo = lo.min(point); hi = hi.max(point)
	lo -= Vector2(8, 8); hi += Vector2(8, 8)
	select.click(lo); select.mouse_moved(hi); select.release(hi)
	harness._ok("window drag selects three enclosed boards", m.selection.size() == 3, m.selection)
	var center: Vector2 = m.cam.unproject_position(Main.m2g(Vector3(250, 25, 18)))
	harness._ok("tiny enclosing window misses partial board", select.box_ids(center - Vector2(2, 2), center + Vector2(2, 2)).is_empty())
	harness._ok("crossing drag selects triangle interior without an enclosed vertex", select.box_ids(center + Vector2(2, -2), center + Vector2(-2, 2)) == [harness.id("b2")])
	select.click(lo); select.mouse_moved(hi); select.reset()
	harness._ok("Esc cancels drag and restores selection", m.selection.size() == 3 and not select.in_gesture())
	m.sel.set_selection([])
	await harness._click_at(Vector3(50, 25, 18))
	harness._ok("Select click picks a board", m.selection == [harness.id("b1")], m.selection)
	await harness._key_state(KEY_SHIFT, true); await harness._click_at(Vector3(250, 25, 18)); await harness._key_state(KEY_SHIFT, false)
	harness._ok("Shift-click adds to the reusable selection", m.selection.size() == 2 and m.selection.has(harness.id("b2")), m.selection)
	await harness._key_state(KEY_SHIFT, true); await harness._click_at(Vector3(250, 25, 18)); await harness._key_state(KEY_SHIFT, false)
	harness._ok("Shift-click toggles a selected board off", m.selection == [harness.id("b1")], m.selection)
	select.click(lo); select.mouse_moved(hi); select.release(hi)
	var before := m.ops.size()
	await harness._grab(Vector3(50, 25, 18)); await harness._key(KEY_RIGHT); await harness._drag_to(Vector3(100, 25, 18), 6); await harness._type("40\n"); await harness._wait_wave()
	harness._ok("select first: one move moves all three boards", m.ops.size() == before + 1 and harness._bbox(harness.id("b1"))[0] == 40.0 and harness._bbox(harness.id("b2"))[0] == 240.0 and harness._bbox(harness.id("b3"))[0] == 440.0, m.ops.back())
	m.undo(); await harness._wait_wave()
	harness._ok("multi-move undoes as one action", harness._bbox(harness.id("b1"))[0] == 0.0 and harness._bbox(harness.id("b3"))[0] == 400.0)
	m.redo(); await harness._wait_wave()
	harness._ok("multi-move redoes as one action", harness._bbox(harness.id("b1"))[0] == 40.0 and harness._bbox(harness.id("b3"))[0] == 440.0)
	m.sel.set_selection([harness.id("b1"), harness.id("b2"), harness.id("b3")])
	await harness._grab(Vector3(90, 25, 18)); await harness._key(KEY_ALT); await harness._key(KEY_LEFT); await harness._drag_to(Vector3(90, 80, 18), 6); await harness._type("100\n"); await harness._wait_wave()
	harness._ok("three selected boards copy in one action", m.ops.back().get("new_ids", []).size() == 3 and harness._shown_ids().size() == 6, m.ops.back())
	await harness._type("2x\n"); await harness._wait_wave()
	harness._ok("multi-copy count amendment retains every target", harness._shown_ids().size() == 9 and m.ops.back()["targets"].size() == 3 and m.ops.back()["new_ids"].size() == 6, m.ops.back())
	await harness._type("/2\n"); await harness._wait_wave()
	harness._ok("multi-copy distribution amendment retains every target", harness._shown_ids().size() == 9 and m.ops.back()["divide"] and m.ops.back()["targets"].size() == 3, m.ops.back())
	await harness._type("1x\n"); await harness._wait_wave()
	m.undo(); await harness._wait_wave()
	harness._ok("multi-copy undo removes all copies", harness._shown_ids().size() == 3, harness._shown_ids())
	m.redo(); await harness._wait_wave()
	harness._ok("multi-copy redo restores all copies", harness._shown_ids().size() == 6)
	m.sel.set_selection([harness.id("b1"), harness.id("b2"), harness.id("b3")])
	m.set_tool("move")
	await harness._key(KEY_DELETE)                # in Move, nothing typed: Delete removes the selection (I48)
	harness._ok("Delete predicts removal immediately", m.selection.is_empty() and not m.bodies_root.get_node(harness.id("b1")).visible)
	await harness._wait_wave()
	harness._ok("Delete preserves unselected linked copies", harness._shown_ids().size() == 3 and not harness._shown_ids().has(harness.id("b1")), harness._shown_ids())
	m.undo(); await harness._wait_wave()
	harness._ok("multi-delete undoes as one action", harness._shown_ids().size() == 6)
	m.redo(); await harness._wait_wave()
	harness._ok("multi-delete redoes as one action", harness._shown_ids().size() == 3)
	m.undo(); await harness._wait_wave()
	m.sel.set_selection([harness.id("b1"), harness.id("b2"), harness.id("b3")])
	await harness._grab(Vector3(90, 25, 18)); await harness._key(KEY_ALT); await harness._key(KEY_SHIFT); await harness._key(KEY_RIGHT); await harness._type("300\n"); await harness._wait_wave()
	harness._ok("three selected boards mirror in one action", m.ops.back()["type"] == "mirror" and m.ops.back()["targets"].size() == 3 and harness._shown_ids().size() == 9, m.ops.back())
	m.undo(); await harness._wait_wave()
	harness._ok("multi-mirror undoes as one action", harness._shown_ids().size() == 6)
	# Tool first, with no prior selection, still picks just the pointed board.
	m.sel.set_selection([])
	await harness._grab(Vector3(90, 25, 18))
	harness._ok("tool-first grab after undo uses restored relationships", m.tools["move"].state.get("active", false) and m.body_assembly.get(harness.id("b1"), "") == "", [m.tools["move"].state, m.body_assembly])
	await harness._key(KEY_RIGHT); await harness._drag_to(Vector3(130, 25, 18), 6); await harness._type("20\n"); await harness._wait_wave()
	harness._ok("tool first moves only the pointed board", m.ops.back()["targets"] == [harness.id("b1")] and harness._bbox(harness.id("b2"))[0] == 240.0, m.ops.back())
	await harness._grab(Vector3(240 + 50, 25, 18)); await harness._drag_to(Vector3(330, 25, 18), 6)
	await harness._key(KEY_BACKSPACE); await harness._wait_wave()
	harness._ok("mid-move, nothing typed: Backspace deletes the board being moved, and only it (I48)",
		m.ops.back()["type"] == "delete" and m.ops.back()["targets"] == [harness.id("b2")] and not m.tools["move"].in_gesture()
		and not harness._shown_ids().has(harness.id("b2")) and harness._shown_ids().has(harness.id("b1")), [m.ops.back(), harness._shown_ids()])
	m.sel.set_selection([harness.id("b1")]); m.set_tool("move")
	var n_ops := m.ops.size()
	var x1: float = harness._bbox(harness.id("b1"))[0] + 50
	await harness._grab(Vector3(x1, 25, 18)); await harness._drag_to(Vector3(x1 + 40, 25, 18), 6); await harness._type("12"); await harness._key(KEY_BACKSPACE)
	harness._ok("with text typed, Backspace only edits the text (I48)", m.ops.size() == n_ops and m.vcb == "1" and m.tools["move"].in_gesture(), [m.ops.back(), m.vcb])
	await harness._key(KEY_BACKSPACE); await harness._key(KEY_BACKSPACE)
	harness._ok("once typing, emptying the box doesn't make the next Backspace delete (I48)", m.ops.size() == n_ops and m.tools["move"].in_gesture(), m.ops.back())
	await harness._key(KEY_ESCAPE)
	m.set_tool("select")
	await harness._click_at(Vector3(x1, 25, 18))
	var click := InputEventMouseButton.new(); click.button_index = MOUSE_BUTTON_LEFT; click.pressed = true
	m.ui_vcb_box.gui_input.emit(click)
	await harness._key(KEY_BACKSPACE)
	harness._ok("a click on the measurements box gives it Backspace too (I48)", m.typing and m.ops.size() == n_ops and m.selection == [harness.id("b1")], [m.ops.back(), m.selection])
	await harness._click_at(Vector3(x1, 25, 18))
	m.set_tool("push")
	await harness._key(KEY_BACKSPACE); await harness._wait_wave()
	harness._ok("after picking the board again, Backspace deletes it, in any tool (Push/Pull here) (I48)",
		m.ops.size() == n_ops + 1 and m.ops.back()["targets"] == [harness.id("b1")] and not harness._shown_ids().has(harness.id("b1")), m.ops.back())

	# Enter a real row and delete its original: context, identity and linked survivors follow promotion.
	await harness._fresh("selection_row", harness._plank(1, Vector3.ZERO, Vector3(100, 50, 18)) + [{"id": "mv1", "type": "move", "targets": ["b1"], "vector": [150, 0, 0], "copy": true, "count": 5, "new_ids": ["b2", "b3", "b4", "b5", "b6"]}])
	await harness._view(Vector3(350, 25, 0), 0, -80, 1.8)
	m.set_tool("select")
	await harness._double_click_at(Vector3(200, 25, 18))
	var member := harness.id("b2")
	var original := harness.id("b1")
	harness._ok("double-click on one of five linked copies isolates that instance and tints its siblings",
		m.context == "component:" + member and m.sel.in_context(member) and not m.sel.in_context(original)
		and m.bodies_root.get_node(original).material_override == m.mat_sibling, m.context)
	await harness._key(KEY_ESCAPE)
	m.sel.context = "row:" + original
	m._apply_context()
	m.sel.set_selection([original])
	await harness._key(KEY_BACKSPACE); await harness._wait_wave()
	harness._ok("entered row Delete preserves siblings and promotes a new original", harness._shown_ids().size() == 5 and m.context == "row:b2" and m.body_row.get(harness.id("b3"), "") == harness.id("b2") and m.body_array.get(harness.id("b2"), "") == "", [m.context, m.body_row, m.body_array])
	harness._ok("window selection excludes out-of-context and deleted boards", not m.tools["select"].box_ids(Vector2.ZERO, harness.get_viewport().get_visible_rect().size).has(harness.id("b1")))
	m.undo(); await harness._wait_wave()
	harness._ok("undo restores the row's original and entered context", harness._shown_ids().size() == 6 and m.context == "row:b1", m.context)
	m.sel.set_selection([harness.id("b2")]); m.sel.hide_selected(); await harness._wait_wave()
	var window: Array = m.tools["select"].box_ids(Vector2.ZERO, harness.get_viewport().get_visible_rect().size)
	harness._ok("window selection leaves hidden boards out", not window.has(harness.id("b2")) and window.has(harness.id("b3")), window)
	m.sel.leave_context(); m.sel.set_selection([])

	await _select_drawings()


func _select_drawings() -> void:
	var plane := {"origin": [0, 0, 0], "normal": [0, 0, 1]}
	var drawing_ops := [
		{"id": "r1", "type": "rect", "plane": plane, "size": [100, 50]},
		{"id": "r2", "type": "circle", "plane": {"origin": [170, 25, 0], "normal": [0, 0, 1]}, "radius": 24},
		{"id": "r3", "type": "polygon", "plane": {"origin": [270, 25, 0], "normal": [0, 0, 1]}, "radius": 24, "sides": 5},
		{"id": "r4", "type": "line", "plane": {"origin": [30, 120, 0], "normal": [0, 0, 1]}, "end": [110, 120, 0]},
		{"id": "r5", "type": "arc", "plane": {"origin": [190, 120, 0], "normal": [0, 0, 1]}, "mid": [220, 145, 0], "end": [250, 120, 0]},
	]
	await harness._fresh("profile_selection", drawing_ops)
	m._rebuild_rect_drafts()
	await harness._view(Vector3(165, 75, 0), 0, -82, 0.9)
	m.set_tool("select")
	for example in [
		["r1", "rectangle", Vector3(50, 25, 0)],
		["r2", "circle", Vector3(170, 25, 0)],
		["r3", "polygon", Vector3(270, 25, 0)],
		["r4", "line", Vector3(70, 120, 0)],
		["r5", "arc", Vector3(220, 145, 0)],
	]:
		await harness._click_at(example[2])
		var overlay: MeshInstance3D = m.pres.selection_view._sel_edges if example[0] in ["r4", "r5"] else m.pres._sel_overlay
		harness._ok("click-select highlights a drawn %s" % example[1],
			m.selection == [harness.id(example[0])] and overlay.mesh != null, m.selection)

	var select = m.tools["select"]
	var lo := Vector2(INF, INF)
	var hi := -lo
	for point in [Vector3(-10, -15, 0), Vector3(70, 15, 0), Vector3(85, 132, 0), Vector3(161, 167, 0)]:
		var screen := harness._screen_of(point, Vector2.ZERO)
		lo = lo.min(screen)
		hi = hi.max(screen)
	harness._ok("crossing box includes an intersected drawing segment",
		select.box_ids(Vector2(hi.x, lo.y), Vector2(lo.x, hi.y)).has(harness.id("r4")))
	var corners := [Vector3(-20, -20, 0), Vector3(320, -20, 0), Vector3(-20, 170, 0), Vector3(320, 170, 0)]
	lo = Vector2(INF, INF); hi = -lo
	for corner in corners:
		var point := harness._screen_of(corner, Vector2.ZERO)
		lo = lo.min(point)
		hi = hi.max(point)
	select.click(lo)
	select.mouse_moved(hi)
	select.release(hi)
	harness._ok("box-select includes drawn profiles and loose edges", m.selection.size() == 5, m.selection)

	var rectangle := harness.id("r1")
	await harness._click_at(Vector3(50, 25, 0))
	await harness._key(KEY_DELETE)
	harness._ok("Delete immediately removes a selected drawing", not m.drafts.has(rectangle), m.drafts.keys())
	await harness._wait_wave()
	m.undo()
	await harness._wait_wave()
	harness._ok("Undo restores the deleted drawing", m.drafts.has(rectangle), m.drafts.keys())
	await harness._click_at(Vector3(50, 25, 0))
	m.set_tool("move")
	await harness._grab(Vector3(50, 25, 0))
	await harness._key(KEY_RIGHT)
	await harness._drag_to(Vector3(100, 25, 0), 6)
	await harness._type("35mm\n")
	await harness._wait_wave()
	harness._ok("Move translates the selected drawing by the typed distance",
		m.ops.back().type == "move" and m.ops.back().targets == [rectangle]
		and is_equal_approx(m.rects[rectangle].pts[0].x, 35.0), [m.ops.back(), m.rects[rectangle].pts])
	m.undo()
	await harness._wait_wave()
	harness._ok("Undo restores the drawing placement", is_zero_approx(m.rects[rectangle].pts[0].x))
