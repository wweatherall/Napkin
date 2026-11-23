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
		harness._ok("dimension click links an edge midpoint without Apply",m.ops.back().get("mode","") == "plane_fit" and m.ops.back().get("face",-1) == 5 and panel.data.boards.b1.fitted,m.ops.back())
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
		harness._ok("dimension corner click commits the inferred face",m.ops.back().get("mode","") == "plane_fit" and m.ops.back().get("face",-1) == 5 and panel.data.boards.b1.fitted,m.ops.back())
	m.properties_panel.hide()
	await harness._fresh("edge_fit",fit_scene)
	await harness._view(Vector3(55,30,65), -32,-25,0.45)
	m.set_tool("push")
	await harness._click_at(Vector3(45,18,20))
	var face_interior := Vector3(-20,-10,100) + Vector3(tilt.z,0,-tilt.x)*60 + Vector3.UP*32 + tilt*10
	await harness._drag_to(face_interior,12)
	harness._ok("drag onto target face offers live fit",m.tools.push.state.get("edge_fit",{}).get("face",-1)==5,[m.tools.push.tip(),m.pick(m.cursor2d.position),m.tools.push.state.get("body")])
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
	harness._ok("push midpoint infers adjacent rail face",m.tools.push.state.get("snap","") == "midpoint" and m.tools.push.state.get("edge_fit",{}).get("face",-1) == 5,m.tools.push.tip())
	var edge := Vector3(-20,10,100) + tilt*10
	await harness._drag_to(edge,12)
	var edge_tool = m.tools.push
	harness._ok("edge infers the rail top",edge_tool.state.get("edge_fit",{}).get("face",-1)==5,[edge_tool.tip(),edge_tool.state.get("body"),edge_tool.state.get("n"),m.stock_frames.keys(),m.infer.point(m.cursor2d.position,"")])
	if edge_tool.state.has("edge_fit"):
		var initial: int = edge_tool.state.edge_fit.face
		await harness._key(KEY_TAB)
		harness._ok("Tab previews the adjacent face",edge_tool.state.edge_fit.face != initial,edge_tool.tip())
		await harness._key(KEY_TAB)
		await harness._key(KEY_ALT)                       # Slice at plane: the draft's end lies on the tilted rail
		await harness._shot("push_edge_inferred_face")
		await harness._press()
		await harness._wait_confirm()
		harness._ok("edge fit saved in a single push",m.ops.back().get("edge_fit",{}).get("face",-1)==initial and m.stock_frames.b1.fitted
				and m.ops.back().edge_fit.get("fit_mode",-1) == 1 and "Slice at plane" in str(m.stock_frames.b1.result),m.ops.back())
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
		for j in 3:
			chosen.append(edge_tool.state.edge_fit.face)
			await harness._key(KEY_TAB)
		var distinct := chosen.duplicate()
		distinct.sort()
		harness._ok("Tab cycles each incident face once",distinct == [0,2,5] and edge_tool.state.edge_fit.face == chosen[0],chosen)
		await harness._press()
		await harness._wait_confirm()
		harness._ok("corner click commits its previewed face",m.stock_frames.b1.fitted and m.ops.back().edge_fit.face == chosen[0])
	m.properties_panel.hide()
