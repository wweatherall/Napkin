extends "res://tools/tool.gd"
## Rectangle (R): click a face or the ground, then click or type  width, height  + Return.
## Started with a click, it ends with a click; started with a press-and-drag (or a press held down), it ends
## when you let go (tool.gd, I43).

const TOOL := {"id": "rect", "label": "Rectangle", "tip": "Rectangle (R)", "key": KEY_R, "order": 30, "show_links": true}   # the toolbar, the Tools menu and the key (tool_registry.gd)

var state := {}


func reset() -> void:
	state = {}
	press_reset()


func hint() -> String:
	return "Rectangle: click a face or the ground, then click or type  width, height  + Enter"


func busy() -> bool:
	return state.get("active", false)


func mouse_moved(screen: Vector2) -> void:
	press_moved(screen)
	if state.get("active", false):
		_rect_drag(screen)
	else:
		m._show_marker(m.snap(m.pick(screen), screen))


func click(screen: Vector2) -> void:
	if not state.get("active", false):
		var p := m.snap(m.pick(screen), screen)
		if not p.get("hit", false): return
		if m.edit_blocked(p["body"]): return
		var n: Vector3 = p["normal"]
		var b := Main.plane_basis(n)
		var on: String = p["body"]
		if p["rect"] != "": on = m.rects[p["rect"]]["on"]
		state = {"active": true, "origin": p["point"], "n": n, "x": b[0], "y": b[1], "on": on, "du": 0.0, "dv": 0.0}
		press_started(screen)
	else:
		_finish_rect()


func release(screen: Vector2) -> void:
	if not press_released().get("drag", false): return   # a click: the rectangle ends with the next click
	if not state.get("active", false): return
	_rect_drag(screen)
	_finish_rect()     # a drag: it ends here


func typed(txt: String) -> void:
	if not state.get("active", false): return
	var parts := txt.split(",")
	if parts.size() != 2: return
	var w := absf(float(parts[0])); var h := absf(float(parts[1]))
	var su := -1.0 if state["du"] < 0 else 1.0
	var sv := -1.0 if state["dv"] < 0 else 1.0
	commit_rect(w * su, h * sv)


func vcb_label() -> String:
	return "Dimensions"


func vcb_value() -> String:
	return DIMENSIONS_DISPLAY_FORMAT % [absf(state["du"]), absf(state["dv"])] if state.get("active", false) else ""


func _rect_drag(screen: Vector2) -> void:
	var o := Main.g2m(m.cam.project_ray_origin(screen))
	var d := Main.n_g2m(m.cam.project_ray_normal(screen))
	var n: Vector3 = state["n"]
	var den := d.dot(n)
	if absf(den) < 1e-6: return
	var t: float = (state["origin"] - o).dot(n) / den
	var q: Vector3 = o + d * t
	var p := m.snap({"hit": true, "point": q, "normal": n, "body": state["on"], "rect": ""}, screen)
	var v: Vector3 = p["point"] - state["origin"]
	if p.get("snap", "grid") != "grid" and (absf(v.dot(state["x"])) < GEOMETRY_TOLERANCE_MM or absf(v.dot(state["y"])) < GEOMETRY_TOLERANCE_MM):
		# a point snap that leaves a side at zero (the start corner, the edge you started on) can't make a
		# rectangle: ignore it and follow the cursor (I44)
		p = infer.on_grid({"hit": true, "point": q, "normal": n, "body": state["on"], "rect": ""})
		v = p["point"] - state["origin"]
	m._show_marker(p)
	state["point_snap"] = p.get("snap", "") in ["endpoint", "midpoint", "on edge"]
	state["du"] = v.dot(state["x"])
	state["dv"] = v.dot(state["y"])
	_preview_rect(state["du"], state["dv"])
	m._update_vcb()


func _preview_rect(du: float, dv: float) -> void:
	var pts := Main._rect_pts(state["origin"], state["x"], state["y"], du, dv)
	var tris := PackedVector3Array([pts[0], pts[1], pts[2], pts[0], pts[2], pts[3]])
	m.overlay.mesh = m._tri_mesh(tris, m.mat_rect)
	m.overlay_lines.mesh = m._lines(PackedVector3Array([pts[0], pts[1], pts[1], pts[2], pts[2], pts[3], pts[3], pts[0]]), Color(0.1, 0.2, 0.6)).mesh


func _finish_rect() -> void:
	if not pointer_distance_ok(minf(absf(state["du"]), absf(state["dv"])), state.get("point_snap", false)): return
	commit_rect(state["du"], state["dv"])


func commit_rect(du: float, dv: float) -> void:
	if absf(du) < GEOMETRY_TOLERANCE_MM or absf(dv) < GEOMETRY_TOLERANCE_MM: return
	m.counters["r"] += 1
	var rid := "r%d" % m.counters["r"]
	var n: Vector3 = state["n"]
	var plane := {}
	if state["on"] != "":
		plane = {"on": {"body": state["on"], "normal": Main.arr3(n), "point": Main.arr3(state["origin"])}}
	else:
		plane = {"origin": Main.arr3(state["origin"]), "normal": Main.arr3(n)}
	var op := {"id": rid, "type": "rect", "plane": plane,
			   "corner": [minf(0, du), minf(0, dv)], "size": [absf(du), absf(dv)]}
	m.ops.append(op)
	m._register_rect(op)
	state = {}
	m.overlay.mesh = null; m.overlay_lines.mesh = null
	m.sync()
