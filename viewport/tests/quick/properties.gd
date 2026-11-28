extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# Native property panel: inspect -> expression edit -> updated geometry -> undo.
	await harness._fresh("properties", harness._plank(1, Vector3.ZERO, Vector3(100, 50, 20)))
	m.properties_panel.show()
	m.sel.set_selection([harness.id("b1")])
	await harness._wait_properties()
	await harness._shot("properties_board")
	var snapshot: Dictionary = m.properties_panel.data
	harness._ok("native features appear in the Properties panel", snapshot.get("objects", []).size() >= 3, snapshot.keys())
	var plane: Dictionary = {}
	var width: Dictionary = {}
	for feature in snapshot.get("objects", []):
		if feature.type == "Part::Plane":
			plane = feature
			for entry in feature.fields:
				if entry.path == "Length": width = entry
	harness._ok("the native rectangle length is editable", width.get("editable", false))
	if not width.is_empty():
		m.properties_panel.native_toggle.button_pressed = true
		m.properties_panel.object_picker.select(snapshot.objects.find(plane))
		m.properties_panel._show_feature()
		await harness._shot("properties_dimensions")
		for field_box in m.properties_panel.fields.get_children():
			if field_box is VBoxContainer and field_box.get_child_count() >= 3 and field_box.get_child(0) is Label and field_box.get_child(0).text == "Length":
				field_box.get_child(1).text = "150 mm"
				field_box.get_child(2).get_child(0).select(1)
				field_box.get_child(2).get_child(2).pressed.emit()
				break
		await harness._wait_confirm()
		await harness._wait_properties()
		harness._ok("property edit changes confirmed geometry", is_equal_approx(float(harness._bodies().b1.volume_mm3), 150000.0))
		harness._ok("property edits are journal actions", m.ops.back().type == "property_edit")
		m.undo()
		await harness._wait_confirm()
		await harness._wait_properties()
		harness._ok("undo restores native property geometry", is_equal_approx(float(harness._bodies().b1.volume_mm3), 100000.0))
	var fit_scene := harness._plank(1, Vector3.ZERO, Vector3(100,50,20))
	var target_board := harness._plank(2, Vector3(-20,-10,100), Vector3(150,80,10))
	var tilt := Vector3(0.32,0,0.9474).normalized()
	target_board[0].plane.normal = [tilt.x,tilt.y,tilt.z]
	target_board[0].plane.xdir = [tilt.z,0,-tilt.x]
	fit_scene.append_array(target_board)
	await harness._fresh("plane_fit",fit_scene)
	m.set_tool("select")
	m.sel.set_selection([harness.id("b1")])
	await harness._wait_properties()
	await harness._view(Vector3(55,30,65), -32,-25,0.45)
	var panel = m.properties_panel
	panel.summary.get_child(3).get_child(-1).pressed.emit()
	await harness._click_at(Vector3(-20,-10,100)+Vector3(tilt.z,0,-tilt.x)*65+Vector3.UP*40+tilt*10)
	harness._ok("viewport face click fills the dimension",not panel.pending.is_empty(),panel.result.text)
	if not panel.pending.is_empty():
		for option in [0,2,1]:
			panel.mode_picker.select(option)
			panel.mode_picker.item_selected.emit(option)
			await harness._shot(["fit_butt","fit_slice","fit_fully_reach"][option])
		await harness._shot("plane_fit_preview")
		panel.apply_fit.pressed.emit()
		await harness._wait_confirm()
		await harness._wait_properties()
		harness._ok("slice applied to the selected board",panel.data.boards.b1.fitted,panel.result.text)
		await harness._shot("plane_fit_applied")
		m.undo()
		await harness._wait_confirm()
		await harness._wait_properties()
		var dimension_field: LineEdit = panel.summary.get_child(3).get_child(1)
		m.cursor2d.position = dimension_field.get_global_rect().get_center()
		await harness._press()
		harness._ok("clicking the Z dimension arms face linking",panel.direct_link and panel.picking_axis == 2)
		var mid_edge := Vector3(-20,30,100) + tilt*10
		await harness._click_at(mid_edge)
		await harness._wait_confirm()
		await harness._wait_properties()
		harness._ok("dimension click links an edge midpoint without Apply",m.ops.back().get("type","") == "fit" and m.ops.back().get("id","").begins_with("ft") and m.ops.back().get("face") is Dictionary and panel.data.boards.b1.fitted,m.ops.back())
		var visible_box: AABB = m.pres._sel_overlay.mesh.get_aabb()
		var actual := AABB(Main.m2g(m.body_tris.b1[0]),Vector3.ZERO)
		for vertex in m.body_tris.b1: actual = actual.expand(Main.m2g(vertex))
		harness._ok("selection tint follows resized stock",visible_box.is_equal_approx(actual),[visible_box,actual])
		m.undo()
		await harness._wait_confirm()
		await harness._wait_properties()
		dimension_field = panel.summary.get_child(3).get_child(1)
		m.cursor2d.position = dimension_field.get_global_rect().get_center()
		await harness._press()
		await harness._click_at(Vector3(-20,-10,100) + tilt*10)
		await harness._wait_confirm()
		await harness._wait_properties()
		harness._ok("dimension corner click commits the inferred face",m.ops.back().get("type","") == "fit" and m.ops.back().get("id","").begins_with("ft") and m.ops.back().get("face") is Dictionary and panel.data.boards.b1.fitted,m.ops.back())
	m.properties_panel.hide()
	await harness._fresh("edge_fit",fit_scene)
	await harness._view(Vector3(55,30,65), -32,-25,0.45)
	m.set_tool("push")
	await harness._click_at(Vector3(45,18,20))
	var face_interior := Vector3(-20,-10,100) + Vector3(tilt.z,0,-tilt.x)*60 + Vector3.UP*32 + tilt*10
	await harness._drag_to(face_interior,12)
	harness._ok("drag onto target face offers live fit",m.tools.push.state.get("edge_face_idx",-1)==5,[m.tools.push.tip(),m.pick(m.cursor2d.position),m.tools.push.state.get("body")])
	if m.tools.push.state.has("edge_fit"):        # I41: Option cycles Butt -> Slice -> Fully reach -> Butt
		var near: float = m.tools.push.state.dist
		await harness._key(KEY_ALT)
		var sliced: bool = m.tools.push.state.edge_fit.fit_mode == 1 and "Slice at plane" in m.tools.push.tip()
		await harness._key(KEY_ALT)
		var far: float = m.tools.push.state.dist
		await harness._key(KEY_ALT)
		harness._ok("Option cycles the end condition", sliced and far > near + 1.0 and m.tools.push.state.edge_fit.fit_mode == 0
				and absf(m.tools.push.state.dist - near) < 0.01, [near, far, m.tools.push.tip()])
	var rail_midpoint := Vector3(-20,30,100) + tilt*10
	await harness._drag_to(rail_midpoint,12)
	harness._ok("push midpoint infers adjacent rail face",m.tools.push.state.get("snap","") == "midpoint" and m.tools.push.state.get("edge_face_idx",-1) == 5,m.tools.push.tip())
	var edge := Vector3(-20,10,100) + tilt*10
	await harness._drag_to(edge,12)
	var edge_tool = m.tools.push
	harness._ok("edge infers the rail top",edge_tool.state.get("edge_face_idx",-1)==5,[edge_tool.tip(),edge_tool.state.get("body"),edge_tool.state.get("n"),m.stock_frames.keys(),m.infer.point(m.cursor2d.position,"")])
	if edge_tool.state.has("edge_fit"):
		var initial: int = edge_tool.state.edge_face_idx
		var initial_face: Dictionary = edge_tool.state.edge_fit.face.duplicate(true)
		await harness._key(KEY_TAB)
		harness._ok("Tab previews the adjacent face",edge_tool.state.edge_face_idx != initial,edge_tool.tip())
		await harness._key(KEY_TAB)
		await harness._key(KEY_ALT)                       # Slice at plane: the draft's end lies on the tilted rail
		await harness._shot("push_edge_inferred_face")
		await harness._press()
		var fit_id: String = m.ops.back().get("id", "")
		harness._ok("face fit creates one draft and one wave",
				m.drafts_root.get_child_count() == 1 and m.pres.op_waves.has(fit_id),
				[m.drafts_root.get_child_count(), m.pres.op_waves.keys()])
		await harness._wait_confirm()
		harness._ok("edge fit saved in a single push",m.ops.back().get("type","")=="fit"
				and m.ops.back().get("face")==initial_face and m.stock_frames.b1.fitted
				and m.ops.back().get("fit_mode",-1) == 1 and "Slice at plane" in str(m.stock_frames.b1.result),m.ops.back())
		m.undo()
		await harness._wait_confirm()
		harness._ok("one Undo undoes face fit", not m.stock_frames.b1.fitted, m.stock_frames.b1)
	# All three incident planes are reachable for this small piece under a doubly tilted rail.
	var corner_scene := harness._plank(1,Vector3(-18,-18,0),Vector3(8,8,15))
	var corner_target := harness._plank(2,Vector3(0,0,150),Vector3(70,60,12))
	var corner_normal := Vector3(0.3,0.4,0.866).normalized()
	corner_target[0].plane.normal = Main.arr3(corner_normal)
	corner_target[0].plane.xdir = [1,0,0]
	corner_scene.append_array(corner_target)
	await harness._fresh("corner_fit",corner_scene)
	await harness._view(Vector3(5,5,75),-32,-25,0.42)
	m.set_tool("push")
	await harness._click_at(Vector3(-14,-14,15))
	await harness._drag_to(Vector3(0,0,150) + corner_normal*12,12)
	harness._ok("corner offers its three reachable faces",edge_tool.state.get("snap","") == "endpoint" and edge_tool.state.get("options",[]).size() == 3,[edge_tool.state.get("body"),edge_tool.state.get("n"),edge_tool.state.get("snap"),edge_tool.tip(),m.infer.point(m.cursor2d.position,""),m.stock_frames.keys()])
	if edge_tool.state.get("options",[]).size() == 3:
		var chosen := []
		var chosen_faces := []
		for j in 3:
			chosen.append(edge_tool.state.edge_face_idx)
			chosen_faces.append(edge_tool.state.edge_fit.face.duplicate(true))
			await harness._key(KEY_TAB)
		var distinct := chosen.duplicate()
		distinct.sort()
		harness._ok("Tab cycles each incident face once",distinct == [0,2,5] and edge_tool.state.edge_face_idx == chosen[0],chosen)
		await harness._press()
		await harness._wait_confirm()
		harness._ok("corner click commits its previewed face",m.stock_frames.b1.fitted and m.ops.back().get("type","") == "fit" and m.ops.back().get("face") == chosen_faces[0])
	# T60: Push/Pull edge-inference onto a fitted board B's fitted end creates A <- B <- C, and moving A updates both.
	var chain_scene := harness._plank(1, Vector3(-100, 0, 200), Vector3(120, 60, 20))
	chain_scene.append_array(harness._plank(2, Vector3(0, 0, 80), Vector3(80, 40, 20)))
	chain_scene.append_array(harness._plank(3, Vector3(100, 0, 0), Vector3(40, 40, 20)))
	chain_scene.append({"id": "fit_b2", "type": "fit", "body": "b2",
			"target_body": "b1", "axis": 2, "face": {"normal": [0, 0, -1], "point": [-100, 0, 200]}, "fit_mode": 0})
	await harness._fresh("chain_fit", chain_scene)
	await harness._view(Vector3(60, 20, 120), -35, -28, 0.65)
	m.set_tool("push")
	await harness._click_at(Vector3(120, 20, 20))
	await harness._drag_to(Vector3(55, 20, 200), 12)
	harness._ok("push onto fitted board end infers its fitted face",
			m.tools.push.state.get("edge_fit", {}).get("target_body", "") == "b2"
			and m.tools.push.state.get("edge_face_idx", -1) == 5,
			[m.tools.push.tip(), m.tools.push.state.get("edge_fit", {}), m.stock_frames.get("b2", {})])
	if m.tools.push.state.has("edge_fit"):
		await harness._press()
		await harness._wait_confirm()
		harness._ok("chain push commits C tied to B",
				m.stock_frames.b2.fitted and m.stock_frames.b3.fitted
				and is_equal_approx(float(harness._bodies().b3.volume_mm3), 320000.0),
				[m.ops.back(), harness._bodies().b3.volume_mm3])
		m.ops.append({"id": "mv_chain_a", "type": "move", "targets": ["b1"], "vector": [0, 0, 40]})
		m.doc.sync()
		await harness._wait_confirm()
		harness._ok("moving A updates both B and C on screen",
				is_equal_approx(float(harness._bodies().b2.volume_mm3), 512000.0)
				and is_equal_approx(float(harness._bodies().b3.volume_mm3), 384000.0),
				[harness._bodies().b2.volume_mm3, harness._bodies().b3.volume_mm3])
	# T61: Option-copy a board to make a linked pair, link one copy to a target face via Push/Pull, move target -> both update.
	var linked_scene := harness._plank(1, Vector3.ZERO, Vector3(40, 40, 40))
	linked_scene.append_array(harness._plank(2, Vector3(-20, -20, 140), Vector3(220, 80, 20)))
	linked_scene.append({"id": "cp_linked", "type": "move", "targets": ["b1"], "vector": [100, 0, 0], "copy": true, "new_ids": ["b3"]})
	await harness._fresh("linked_fit", linked_scene)
	await harness._view(Vector3(70, 20, 80), -35, -25, 0.55)
	m.set_tool("push")
	await harness._click_at(Vector3(20, 20, 40))
	await harness._drag_to(Vector3(20, 20, 160), 12)
	harness._ok("push from linked copy infers target face",
			m.tools.push.state.get("edge_fit", {}).get("target_body", "") == "b2"
			and m.tools.push.state.get("edge_face_idx", -1) == 5,
			[m.tools.push.tip(), m.tools.push.state.get("edge_fit", {}), m.stock_frames.get("b1", {})])
	if m.tools.push.state.has("edge_fit"):
		await harness._press()
		await harness._wait_confirm()
		harness._ok("linked copy fit updates both siblings on screen",
				m.stock_frames.b1.fitted and m.stock_frames.b3.fitted
				and is_equal_approx(float(harness._bodies().b1.volume_mm3), 256000.0)
				and is_equal_approx(float(harness._bodies().b3.volume_mm3), 256000.0),
				[harness._bodies().b1.volume_mm3, harness._bodies().b3.volume_mm3])
		m.ops.append({"id": "mv_linked_target", "type": "move", "targets": ["b2"], "vector": [0, 0, 30]})
		m.doc.sync()
		await harness._wait_confirm()
		harness._ok("moving target updates both linked copies on screen",
				is_equal_approx(float(harness._bodies().b1.volume_mm3), 304000.0)
				and is_equal_approx(float(harness._bodies().b3.volume_mm3), 304000.0),
				[harness._bodies().b1.volume_mm3, harness._bodies().b3.volume_mm3])

		# T127: Upgraded Component Properties window + component context isolation.
		m.properties_panel.show()
		m.properties_panel.native_toggle.button_pressed = false
		m.sel.set_selection([harness.id("b1")])
		await harness._wait_properties()
		var p = m.properties_panel
		harness._ok("properties header shows label, linked subtitle, and Parametric badge",
				p.piece_title.text != "" and "Linked component (2 instances)" in p.piece_subtitle.text
				and p.parametric_badge.visible and not p.native_section.visible,
				[p.piece_title.text, p.piece_subtitle.text, p.parametric_badge.visible, p.native_section.visible])

		p.display({
			"body": "b_cut", "boards": {},
			"summary": {"label": "Cut board", "context": "Board", "parametric": false,
				"dimensions": [{"axis": 0, "label": "Length", "value_mm": 120.0, "editable": false, "linked": false, "target_label": "", "target_face": "", "offset_mm": 0.0}]},
			"objects": [{"name": "Cut", "label": "Cut board", "type": "Part::Cut", "fields": []}],
			"references": [],
		})
		harness._ok("cut board summary stays visible with read-only dimensions", p.summary.visible and p.summary.get_child_count() >= 2)

		m.sel.enter_context_of("b1")
		m._apply_context()
		var n_b1 = m.bodies_root.get_node_or_null("b1")
		var n_b3 = m.bodies_root.get_node_or_null("b3")
		var n_b2 = m.bodies_root.get_node_or_null("b2")
		harness._ok("component context isolates entered board, tints siblings, ghosts others",
				m.sel.context == "component:b1"
				and n_b1 != null and n_b1.material_override == null
				and n_b3 != null and n_b3.material_override == m.mat_sibling
				and n_b2 != null and n_b2.material_override == m.pres.mat_ghost,
				[m.sel.context])
		m.sel.leave_context()
		m._apply_context()
	m.properties_panel.hide()

	# T62: Properties "Pick face…" can tie a board to a circular board's planar face and updates when target moves.
	var cyl_scene := harness._plank(1, Vector3.ZERO, Vector3(40, 40, 20))
	cyl_scene.append({"id": "c1", "type": "circle", "plane": {"origin": [20, 20, 120], "normal": [0, 0, 1]}, "radius": 30.0})
	cyl_scene.append({"id": "cp1", "type": "new_board", "target": {"rect": "c1"}, "distance": 20.0, "body": "b2"})
	await harness._fresh("t62_cyl_fit", cyl_scene)
	m.set_tool("select")
	m.properties_panel.show()
	m.sel.set_selection([harness.id("b1")])
	await harness._wait_properties()
	await harness._view(Vector3(20, 20, 70), -32, -25, 0.5)
	var p62 = m.properties_panel
	p62.summary.get_child(3).get_child(-1).pressed.emit()
	await harness._click_at(Vector3(20, 20, 140))
	harness._ok("T62 Properties Pick face targets circular board planar face", not p62.pending.is_empty(), p62.result.text)
	if not p62.pending.is_empty():
		p62.apply_fit.pressed.emit()
		await harness._wait_confirm()
		await harness._wait_properties()
		harness._ok("T62 circular target fit applied", p62.data.boards.b1.fitted and is_equal_approx(float(harness._bodies().b1.volume_mm3), 224000.0), harness._bodies().b1.volume_mm3)
		m.ops.append({"id": "mv_t62_cyl", "type": "move", "targets": ["b2"], "vector": [0, 0, 30]})
		m.doc.sync()
		await harness._wait_confirm()
		harness._ok("T62 moving circular target updates tied board on screen", is_equal_approx(float(harness._bodies().b1.volume_mm3), 272000.0), harness._bodies().b1.volume_mm3)
	m.properties_panel.hide()

	# T147: Picking a non-rectangular target's fitted end in Properties names the same face FreeCAD reports.
	var nonrect_fit_scene := harness._plank(1, Vector3.ZERO, Vector3(40, 40, 20))
	nonrect_fit_scene.append({"id": "c2", "type": "circle", "plane": {"origin": [20, 20, 120], "normal": [0, 0, 1]}, "radius": 30.0})
	nonrect_fit_scene.append({"id": "cp2", "type": "new_board", "target": {"rect": "c2"}, "distance": 20.0, "body": "b2"})
	nonrect_fit_scene.append_array(harness._plank(3, Vector3(120, 0, 200), Vector3(40, 40, 20)))
	nonrect_fit_scene.append({"id": "fit_b2", "type": "fit", "body": "b2",
			"target_body": "b3", "axis": 2, "face": {"normal": [0, 0, -1], "point": [120, 0, 200]}, "fit_mode": 0})
	await harness._fresh("t147_nonrect_fitted_end", nonrect_fit_scene)
	m.set_tool("select")
	m.properties_panel.show()
	m.sel.set_selection([harness.id("b1")])
	await harness._wait_properties()
	await harness._view(Vector3(20, 20, 100), -32, -25, 0.5)
	var p147 = m.properties_panel
	p147.summary.get_child(3).get_child(-1).pressed.emit()
	await harness._click_at(Vector3(20, 20, 200))
	var preview_text: String = p147.result.text
	harness._ok("T147 preview names non-rectangular target's fitted end as Face 2",
			not p147.pending.is_empty() and "Face 2 face" in preview_text, preview_text)
	if not p147.pending.is_empty():
		p147.apply_fit.pressed.emit()
		await harness._wait_confirm()
		await harness._wait_properties()
		harness._ok("T147 applied fit result names the same face FreeCAD reports",
				p147.data.boards.b1.fitted and "Face 2 face" in p147.data.boards.b1.result,
				[preview_text, p147.data.boards.b1.result])
	m.properties_panel.hide()

	# H199: commit_push shows normal rejections for missing stock frame and unmatched axis
	m.set_tool("push")
	var pt = m.tools.push
	var ops_before: int = m.ops.size()
	pt.state = {"rect": "", "body": "no_such_board", "n": Vector3(0, 0, 1), "anchor": Vector3.ZERO}
	pt.commit_push(10.0, {"target_body": harness.id("b3"), "face": 4})
	harness._ok("H199 commit_push rejects missing stock frame with reason",
			m.ops.size() == ops_before and m.reject_note == "Source has no extrudable stock"
			and m.ui_sync.text == "✗ rejected Source has no extrudable stock" and not pt.busy(),
			[m.reject_note, m.ui_sync.text])
	pt.state = {"rect": "", "body": harness.id("b1"), "n": Vector3(1, 1, 0).normalized(), "anchor": Vector3.ZERO}
	pt.commit_push(10.0, {"target_body": harness.id("b3"), "face": 4})
	harness._ok("H199 commit_push rejects unmatched axis with reason",
			m.ops.size() == ops_before and m.reject_note == "Source face no longer matches the chosen dimension"
			and m.ui_sync.text == "✗ rejected Source face no longer matches the chosen dimension" and not pt.busy(),
			[m.reject_note, m.ui_sync.text])
