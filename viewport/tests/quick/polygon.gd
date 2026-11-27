extends RefCounted
## T84: the Polygon button, its side count, real gestures, exact Push/Pull, and who gets keys before a gesture.
const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


static func _area(sides: int, radius: float) -> float:
	return 0.5 * sides * radius * radius * sin(TAU / sides)


func _volume(alias: String) -> float:
	return harness._bodies().get(harness.id(alias), {}).get("volume_mm3", -1.0)


func run() -> void:
	await harness._fresh("polygon")
	await harness._view(Vector3(200, 100, 0), -30, -50, 1.2)
	m.ui.tool_buttons["polygon"].pressed.emit()
	var tool = m.tools["polygon"]
	harness._ok("the toolbar button picks Polygon, which has no key and starts at 6 sides", m.tool == "polygon"
		and tool.TOOL.key == KEY_NONE and tool.sides == 6 and tool.vcb_label() == "Sides" and m.ui_vcb.text == "6", [m.tool, tool.sides, m.ui_vcb.text])
	await harness._drag_to(Vector3.ZERO, 4)
	await harness._button(true)
	await harness._drag_to(Vector3(40, 0, 0), 6)
	await harness._button(false)
	var op: Dictionary = m.ops.back() if not m.ops.is_empty() else {}
	harness._ok("press-drag-release makes a 6-sided polygon of radius 40 with a corner toward the cursor", op.get("type") == "polygon"
		and op.get("sides") == 6 and is_equal_approx(op.get("radius", 0.0), 40.0) and Vector3(op.x[0], op.x[1], op.x[2]).is_equal_approx(Vector3(1, 0, 0)), op)
	harness._ok("its draft has six corners", m.rects.get(harness.id("r1"), {}).get("pts", []).size() == 6, m.rects.keys())
	await harness._wait_confirm()
	m.undo()
	await harness._wait_confirm()
	harness._ok("undo removes the loose polygon", m.rects.is_empty(), m.rects.keys())
	m.redo()
	await harness._wait_confirm()
	harness._ok("redo restores the loose polygon and its picking draft", m.rects.has(harness.id("r1")) and m.drafts.has(harness.id("r1")), m.rects.keys())
	await harness._push(Vector3.ZERO, Vector3(0, 0, 60), "100")
	await harness._wait_wave()
	harness._ok("FreeCAD makes the exact hexagonal prism", absf(_volume("b1") - _area(6, 40) * 100) < 0.1, harness._bodies())

	m.ui.tool_buttons["polygon"].pressed.emit()
	await harness._type("8s\n")
	harness._ok("8s + Return before a gesture sets 8 sides, shown in the box and the hint", tool.sides == 8 and not tool.busy()
		and m.ui_vcb.text == "8" and tool.hint().contains("8 sides"), [tool.sides, m.ui_vcb.text])
	await harness._type("2s\n")
	await harness._type("100s\n")
	harness._ok("side counts outside 3-64 are ignored", tool.sides == 8, tool.sides)
	var count := m.ops.size()
	var units_were: bool = m.measure.units_explicit
	await harness._type("150\n")
	harness._ok("a length before a gesture does nothing", m.ops.size() == count and m.measure.units_explicit == units_were and m.measure.vcb == "", m.measure.vcb)
	await harness._click_at(Vector3(200, 0, 0))
	await harness._drag_to(Vector3(230, 0, 0), 4)
	await harness._press()
	harness._ok("click, move, click makes an 8-sided polygon", m.ops.size() == count + 1 and m.ops.back().get("sides") == 8
		and is_equal_approx(m.ops.back().get("radius", 0.0), 30.0), m.ops.back())
	await harness._push(Vector3(200, 0, 0), Vector3(200, 0, 60), "20")
	await harness._wait_wave()
	harness._ok("Push/Pull makes the octagonal board", absf(_volume("b2") - _area(8, 30) * 20) < 0.1, harness._bodies())

	m.ui.tool_buttons["polygon"].pressed.emit()
	await harness._click_at(Vector3(320, 0, 0))
	await harness._drag_to(Vector3(350, 0, 0), 4)
	await harness._type("12s\n")
	harness._ok("12s during a gesture changes the preview's sides and keeps the gesture", tool.busy() and tool.sides == 12 and m.overlay.mesh != null, tool.state)
	await harness._type("3/4\"\n")
	harness._ok("then a typed length commits that unrounded radius", not tool.busy() and m.ops.back().get("sides") == 12
		and absf(m.ops.back().get("radius", 0.0) - 19.05) < 1e-9, m.ops.back())
	# a direction three decimals can't hold: the op's corner is still where the cursor snapped
	await harness._click_at(Vector3(300, 200, 0))
	await harness._drag_to(Vector3(430, 270, 0), 4)
	await harness._press()
	var turned: Dictionary = m.ops.back()
	var corner := Vector3(300, 200, 0) + Vector3(turned.x[0], turned.x[1], turned.x[2]) * float(turned.radius)
	harness._ok("the op's first corner is the point the radius was set at", corner.distance_to(Vector3(430, 270, 0)) < 0.001, [turned, corner])
	await harness._click_at(Vector3(450, 100, 0))
	await harness._key(KEY_ESCAPE)
	harness._ok("Escape cancels the polygon gesture", not tool.busy(), tool.state)

	count = m.ops.size()
	await harness._type("5")
	await harness._click_at(Vector3(200, 150, 0))
	await harness._type("20\n")
	harness._ok("digits typed before the centre click, not entered, set the sides; the radius starts empty (William's steps)",
		m.ops.size() == count + 1 and is_equal_approx(m.ops.back().get("radius", 0.0), 20.0) and m.ops.back().get("sides") == 5
		and tool.sides == 5, [m.ops.back(), tool.sides, m.measure.vcb])
	await harness._type("7\n")
	harness._ok("a plain number + Return before a gesture sets the sides", tool.sides == 7 and not tool.busy() and m.ui_vcb.text == "7",
		[tool.sides, m.ui_vcb.text])
	var sides_were: int = tool.sides
	count = m.ops.size()
	await harness._type("2")
	await harness._click_at(Vector3(200, 150, 0))
	await harness._type("20\n")
	harness._ok("a side count outside 3-64 typed before the click is dropped, and the radius still starts empty",
		m.ops.size() == count + 1 and is_equal_approx(m.ops.back().get("radius", 0.0), 20.0) and m.ops.back().get("sides") == sides_were,
		[m.ops.back(), tool.sides, m.measure.vcb])

	# keys.gd: only a tool with accepts_idle gets characters before a gesture; hotkeys behave as before
	var taken := {}
	for id in ["rect", "circle", "line", "arc", "push", "move", "select", "paint"]:
		m.set_tool(id)
		await harness._type("8")
		if m.measure.vcb != "" or m.tools[id].has_method("accepts_idle"): taken[id] = m.measure.vcb
	harness._ok("no other tool takes typed characters before a gesture", taken.is_empty(), taken)
	m.set_tool("polygon")
	await harness._key(KEY_C)
	harness._ok("a tool key still switches away from an idle Polygon", m.tool == "circle", m.tool)
	m.set_tool("polygon")
	await harness._type("5")
	await harness._key(KEY_R)
	harness._ok("a tool key after typed digits switches tools and empties the box", m.tool == "rect" and m.measure.vcb == "", [m.tool, m.measure.vcb])

	# On a face: the same cut rules as a circle.
	await harness._fresh("polygon_face", harness._plank(1, Vector3.ZERO, Vector3(300, 200, 18)))
	await harness._view(Vector3(150, 100, 18), -30, -50, 1.0)
	m.set_tool("polygon")
	await harness._type("6s\n")
	await harness._click_at(Vector3(60, 60, 18))
	await harness._drag_to(Vector3(80, 60, 18), 4)
	await harness._type("20\n")
	await harness.get_tree().physics_frame
	await harness._push(Vector3(60, 60, 18), Vector3(60, 60, 0), "-18")
	await harness._wait_wave()
	harness._ok("a polygon on a face cuts an exact through hole", absf(_volume("b1") - (300.0 * 200 * 18 - _area(6, 20) * 18)) < 0.1
		and m.ops.back().get("through", false), harness._bodies())
	await _check_predictions()


func _check_predictions() -> void:
	# P21: the viewport's corners against FreeCAD's prism, on several planes, side counts and corner directions.
	var cases := [
		[Vector3.ZERO, Vector3(0, 0, 1), 40.0, 3, Vector3.ZERO],
		[Vector3(120, 80, 50), Vector3(1, 0, 0), 19.05, 5, Vector3(0, 1, 1).normalized()],
		[Vector3(75, -25, 10), Vector3(1, 2, 3).normalized(), 35.5, 7, Vector3.ZERO],
		[Vector3(-80, 20, 5), Vector3(0, 0, -1), 300.0, 64, Vector3(1, 1, 0).normalized()],
	]
	var height := 37.0
	for i in cases.size():
		var center: Vector3 = cases[i][0]
		var normal: Vector3 = cases[i][1]
		var radius: float = cases[i][2]
		var sides: int = cases[i][3]
		var toward: Vector3 = cases[i][4]
		var op := {"id": "r1", "type": "polygon", "plane": {"origin": Main.arr3(center), "normal": Main.arr3(normal)}, "radius": radius, "sides": sides}
		if toward != Vector3.ZERO: op["x"] = [toward.x, toward.y, toward.z]
		# both sides get what the op carries (Geo.arr3 rounds the plane's normal, as every tool's op does)
		center = Vector3(op.plane.origin[0], op.plane.origin[1], op.plane.origin[2])
		normal = Vector3(op.plane.normal[0], op.plane.normal[1], op.plane.normal[2]).normalized()
		await harness._fresh("polygon_prediction_%d" % i, [op, {"id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": height, "body": "b1"}])
		var shape: Dictionary = m.pres.polygon_geometry(center, normal, radius, sides, toward)
		var lo := Vector3(INF, INF, INF)
		var hi := -lo
		for p in shape.pts:
			lo = lo.min(p).min(p + normal * height)
			hi = hi.max(p).max(p + normal * height)
		var native: Dictionary = harness._bodies().get(harness.id("b1"), {})
		var bounds: Array = native.get("world_bbox", [])
		var matches := bounds.size() == 6
		for axis in 3:
			if matches: matches = absf(bounds[axis] - lo[axis]) <= 0.01 and absf(bounds[axis + 3] - hi[axis]) <= 0.01
		harness._ok("polygon prediction %d: the preview's corners are FreeCAD's" % i,
			matches and absf(native.get("volume_mm3", -1.0) - _area(sides, radius) * height) < maxf(0.1, _area(sides, radius) * height * 0.000002), [native, lo, hi])
