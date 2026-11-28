extends RefCounted
## T81: real Circle gestures, length syntax, exact Push/Pull, and profile undo/redo.
const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func _circle(at: Vector3, toward: Vector3, radius: String) -> void:
	await harness._key(KEY_C)
	await harness._click_at(at)
	await harness._drag_to(toward, 4)
	await harness._type(radius + "\n")
	await harness.get_tree().physics_frame


func run() -> void:
	await harness._fresh("circle")
	await harness._view(Vector3(200, 100, 0), -30, -50, 1.2)
	await harness._key(KEY_C)
	harness._ok("C selects Circle and labels the measurement Radius", m.tool == "circle" and m.tools.circle.vcb_label() == "Radius", m.tool)
	await harness._drag_to(Vector3.ZERO, 4)
	await harness._button(true)
	await harness._drag_to(Vector3(40, 0, 0), 6)
	await harness._button(false)
	harness._ok("press-drag-release makes a circle of radius 40", m.ops.size() == 1 and m.ops.back().type == "circle" and is_equal_approx(m.ops.back().radius, 40.0), m.ops)
	m.undo()
	await harness._wait_confirm()
	harness._ok("undo removes the loose circle", m.rects.is_empty(), m.rects.keys())
	m.redo()
	await harness._wait_confirm()
	harness._ok("redo restores the loose circle and its picking draft", m.rects.has(harness.id("r1")) and m.drafts.has(harness.id("r1")), m.rects.keys())
	await harness.get_tree().physics_frame
	var center_pick := m.pick(m.cam.unproject_position(Main.m2g(Vector3.ZERO)))
	harness._ok("the loose circle is pickable at its centre", center_pick.get("rect", "") == harness.id("r1"), center_pick)
	await harness._push(Vector3(0, 0, 0), Vector3(0, 0, 60), "100")
	await harness._wait_wave()
	var bodies := harness._bodies()
	harness._ok("Push/Pull makes an exact dowel", bodies.has(harness.id("b1")) and absf(bodies.get(harness.id("b1"), {}).get("volume_mm3", 0.0) - PI * 1600 * 100) < 0.1, bodies)
	await harness._shot("circle_dowel")
	m.undo()
	await harness._wait_wave()
	harness._ok("undo push restores the loose circle", m.drafts.has(harness.id("r1")) and not m.body_tris.has(harness.id("b1")), m.drafts.keys())
	m.redo()
	await harness._wait_wave()
	harness._ok("redo push consumes the loose circle again", not m.drafts.has(harness.id("r1")) and m.body_tris.has(harness.id("b1")), m.drafts.keys())
	await _circle(Vector3(180, 0, 0), Vector3(210, 0, 0), "3/4\"")
	harness._ok("typed fractional inches become an unrounded radius", m.ops.back().type == "circle" and absf(m.ops.back().get("radius", 0.0) - 19.05) < 1e-9, m.ops.back())
	# A completed click starts the circle; only the second click ends it.
	await harness._click_at(Vector3(320, 0, 0))
	await harness._drag_to(Vector3(350, 0, 0), 4)
	var count := m.ops.size()
	harness._ok("click and move leaves the circle active", m.tools.circle.busy(), m.tools.circle.state)
	await harness._press()
	harness._ok("second click finishes a radius 30 circle", m.ops.size() == count + 1 and is_equal_approx(m.ops.back().get("radius", 0.0), 30.0), m.ops.back())
	await _circle(Vector3(450, 0, 0), Vector3(470, 0, 0), "0.2")
	harness._ok("a typed sub-millimetre radius bypasses the accidental-drag filter", is_equal_approx(m.ops.back().get("radius", 0.0), 0.2), m.ops.back())
	await harness._key(KEY_C)
	await harness._click_at(Vector3(450, 100, 0))
	await harness._key(KEY_ESCAPE)
	harness._ok("Escape cancels the circle gesture", not m.tools.circle.busy(), m.tools.circle.state)
	# On-face profiles use the same join/cut/New board rules as rectangles.
	await harness._fresh("circle_face", harness._plank(1, Vector3.ZERO, Vector3(300, 200, 18)))
	await harness._view(Vector3(150, 100, 18), -30, -50, 1.0)
	await _circle(Vector3(60, 60, 18), Vector3(80, 60, 18), "20")
	await harness._push(Vector3(60, 60, 18), Vector3(60, 60, 0), "-18")
	await harness._wait_wave()
	bodies = harness._bodies()
	harness._ok("a circle on a face cuts an exact round through hole", bodies.has(harness.id("b1")) and absf(bodies.b1.volume_mm3 - (300.0 * 200 * 18 - PI * 400 * 18)) < 0.1 and m.ops.back().get("through", false), bodies)
	await _circle(Vector3(150, 60, 18), Vector3(170, 60, 18), "20")
	await harness._push(Vector3(150, 60, 18), Vector3(150, 60, 38), "20")
	await harness._wait_wave()
	bodies = harness._bodies()
	harness._ok("a positive circle push joins as a boss", not m.ops.back().has("body") and absf(bodies.b1.volume_mm3 - (300.0 * 200 * 18 + PI * 400 * 2)) < 0.1, bodies)
	await harness._key(KEY_B)
	await _circle(Vector3(240, 60, 18), Vector3(255, 60, 18), "15")
	await harness._push(Vector3(240, 60, 18), Vector3(240, 60, 48), "30")
	await harness._wait_wave()
	bodies = harness._bodies()
	harness._ok("B makes a separate exact round board", bodies.has(harness.id("b2")) and absf(bodies.get(harness.id("b2"), {}).get("volume_mm3", 0.0) - PI * 225 * 30) < 0.1, bodies)
	await harness._shot("circle_hole_boss_board")
	await _check_predictions()


func _check_predictions() -> void:
	# P21: feed the same circle/height to the actual viewport predictor and FreeCAD.
	# The native boundary is exact; the preview's extrema may fall short by one facet's sagitta.
	var cases := [
		[Vector3.ZERO, Vector3(0, 0, 1), 40.0],
		[Vector3(120, 80, 50), Vector3(1, 0, 0), 19.05],
		[Vector3(75, -25, 10), Vector3(1, 2, 3).normalized(), 35.5],
		[Vector3(-80, 20, 5), Vector3(0, 0, -1), 0.2],
		[Vector3(1000, -900, 250), Vector3(0, -1, 0), 300.0],
	]
	var height := 37.0
	for i in cases.size():
		var center: Vector3 = cases[i][0]
		var normal: Vector3 = cases[i][1]
		var radius: float = cases[i][2]
		await harness._fresh("circle_prediction_%d" % i, [
			{"id": "r1", "type": "circle", "plane": {"origin": Main.arr3(center), "normal": Main.arr3(normal)}, "radius": radius},
			{"id": "pp1", "type": "new_board", "target": {"rect": "r1"}, "distance": height, "body": "b1"},
		])
		var shape: Dictionary = m.pres.circle_geometry(center, normal, radius)
		var predicted_radius: float = (shape.pts[0] - center).length()
		var predicted_volume := PI * predicted_radius * predicted_radius * height
		var native: Dictionary = harness._bodies().get(harness.id("b1"), {})
		harness._ok("circle prediction %d: preview radius agrees with native cylinder volume" % i,
			not native.is_empty() and absf(native.get("volume_mm3", -1.0) - predicted_volume) < maxf(0.051, predicted_volume * 0.000002), native)
		var lo := Vector3(INF, INF, INF)
		var hi := -lo
		for p in shape.pts:
			lo = lo.min(p).min(p + normal * height)
			hi = hi.max(p).max(p + normal * height)
		var bounds: Array = native.get("world_bbox", [])
		var matches := bounds.size() == 6
		var tolerance := radius * (1.0 - cos(PI / m.pres.CIRCLE_SEGMENTS)) + 0.001
		for axis in 3:
			if matches:
				matches = absf(bounds[axis] - lo[axis]) <= tolerance and absf(bounds[axis + 3] - hi[axis]) <= tolerance
		harness._ok("circle prediction %d: faceted preview bounds agree with native geometry" % i, matches, [bounds, lo, hi, tolerance])
