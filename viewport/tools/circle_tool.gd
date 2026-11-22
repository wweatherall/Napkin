extends "res://tools/tool.gd"
## Circle (C): centre, then radius; the same click/drag gesture as Rectangle (I43).

const TOOL := {"id": "circle", "label": "Circle", "tip": "Circle (C)", "key": KEY_C, "order": 35, "show_links": true}

var state := {}


func reset() -> void:
	state = {}
	press_reset()


func hint() -> String:
	return "Circle: click a face or the ground for the centre, then click or type a radius + Enter"


func busy() -> bool:
	return state.get("active", false)


func mouse_moved(screen: Vector2) -> void:
	press_moved(screen)
	if busy():
		_radius_drag(screen)
	else:
		m._show_marker(m.snap(m.pick(screen), screen))


func click(screen: Vector2) -> void:
	if busy():
		_finish_circle()
		return
	var p := m.snap(m.pick(screen), screen)
	if not p.get("hit", false): return
	if m.edit_blocked(p["body"]): return
	var on: String = p["body"]
	if p["rect"] != "": on = m.rects[p["rect"]]["on"]
	state = {"active": true, "origin": p["point"], "n": p["normal"], "on": on, "radius": 0.0}
	press_started(screen)


func release(screen: Vector2) -> void:
	if not press_released().get("drag", false) or not busy(): return
	_radius_drag(screen)
	_finish_circle()


func typed(txt: String) -> void:
	if busy(): commit_circle(absf(float(txt)))


func vcb_label() -> String:
	return "Radius"


func vcb_value() -> String:
	return DISTANCE_DISPLAY_FORMAT % state["radius"] if busy() else ""


func _radius_drag(screen: Vector2) -> void:
	var o := Main.g2m(m.cam.project_ray_origin(screen))
	var d := Main.n_g2m(m.cam.project_ray_normal(screen))
	var n: Vector3 = state["n"]
	var den := d.dot(n)
	if absf(den) < 1e-6: return
	var t: float = (state["origin"] - o).dot(n) / den
	var q := o + d * t
	var p := m.snap({"hit": true, "point": q, "normal": n, "body": state["on"], "rect": ""}, screen)
	var v: Vector3 = p["point"] - state["origin"]
	v -= n * v.dot(n)
	# A snap to the centre cannot make a circle; follow the grid/cursor, as Rectangle does for zero sides.
	if p.get("snap", "grid") != "grid" and v.length() < GEOMETRY_TOLERANCE_MM:
		p = infer.on_grid({"hit": true, "point": q, "normal": n, "body": state["on"], "rect": ""})
		v = p["point"] - state["origin"]
	m._show_marker(p)
	state["point_snap"] = p.get("snap", "") in ["endpoint", "midpoint", "on edge"]
	state["radius"] = v.length()
	var shape: Dictionary = m.pres.circle_geometry(state["origin"], n, state["radius"])
	m.overlay.mesh = m._tri_mesh(shape.tris, m.mat_rect)
	m.overlay_lines.mesh = m._lines(shape.lines, Color(0.1, 0.2, 0.6)).mesh
	m._update_vcb()


func _finish_circle() -> void:
	if not pointer_distance_ok(state["radius"], state.get("point_snap", false)): return
	commit_circle(state["radius"])


func commit_circle(radius: float) -> void:
	if not is_finite(radius) or radius < GEOMETRY_TOLERANCE_MM: return
	m.counters["r"] += 1
	var rid := "r%d" % m.counters["r"]
	var plane := {}
	if state["on"] != "":
		plane = {"on": {"body": state["on"], "normal": Main.arr3(state["n"]), "point": Main.arr3(state["origin"])}}
	else:
		plane = {"origin": Main.arr3(state["origin"]), "normal": Main.arr3(state["n"])}
	var op := {"id": rid, "type": "circle", "plane": plane, "radius": radius}
	m.ops.append(op)
	m._register_rect(op)      # shared loose-profile presentation and picking
	reset()
	m.overlay.mesh = null; m.overlay_lines.mesh = null
	m.sync()
