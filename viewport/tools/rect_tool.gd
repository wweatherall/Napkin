extends "res://tools/tool.gd"
## Rectangle (R): click a face or the ground, then click or type  width, height  + Return.
## Started with a click, it ends with a click; started with a press-and-drag (or a press held down), it ends
## when you let go.

const DRAG_PX := 6.0          # the cursor moved this far with the button down: it's a drag
const HOLD_MS := 300          # ...or the button stayed down this long
var state := {}


func reset() -> void:
	state = {}


func hint() -> String:
	return "Rectangle: click a face or the ground, then click or type  width, height  + Enter"


func busy() -> bool:
	return state.get("active", false)


func mouse_moved(screen: Vector2) -> void:
	if state.get("held", false) and screen.distance_to(state["press"]) > DRAG_PX:
		state["drag"] = true
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
		state = {"active": true, "origin": p["point"], "n": n, "x": b[0], "y": b[1], "on": on, "du": 0.0, "dv": 0.0,
				 "press": screen, "held": true, "t0": Time.get_ticks_msec(), "drag": false}
	else:
		commit_rect(state["du"], state["dv"])


func release(screen: Vector2) -> void:
	if not state.get("held", false): return
	state["held"] = false
	if not state["drag"] and Time.get_ticks_msec() - int(state["t0"]) < HOLD_MS:
		return                                   # a click: the rectangle ends with the next click
	_rect_drag(screen)
	if absf(state["du"]) >= 0.5 and absf(state["dv"]) >= 0.5:
		commit_rect(state["du"], state["dv"])     # a drag: it ends here


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
	return "%d, %d" % [absf(state["du"]), absf(state["dv"])] if state.get("active", false) else ""


func _rect_drag(screen: Vector2) -> void:
	var o := Main.g2m(m.cam.project_ray_origin(screen))
	var d := Main.n_g2m(m.cam.project_ray_normal(screen))
	var n: Vector3 = state["n"]
	var den := d.dot(n)
	if absf(den) < 1e-6: return
	var t: float = (state["origin"] - o).dot(n) / den
	var q: Vector3 = o + d * t
	var p := m.snap({"hit": true, "point": q, "normal": n, "body": state["on"], "rect": ""}, screen)
	m._show_marker(p)
	var v: Vector3 = p["point"] - state["origin"]
	state["du"] = Main.r3(v.dot(state["x"]))
	state["dv"] = Main.r3(v.dot(state["y"]))
	_preview_rect(state["du"], state["dv"])
	m._update_vcb()


func _preview_rect(du: float, dv: float) -> void:
	var pts := Main._rect_pts(state["origin"], state["x"], state["y"], du, dv)
	var tris := PackedVector3Array([pts[0], pts[1], pts[2], pts[0], pts[2], pts[3]])
	m.overlay.mesh = m._tri_mesh(tris, m.mat_rect)
	m.overlay_lines.mesh = m._lines(PackedVector3Array([pts[0], pts[1], pts[1], pts[2], pts[2], pts[3], pts[3], pts[0]]), Color(0.1, 0.2, 0.6)).mesh


func commit_rect(du: float, dv: float) -> void:
	if absf(du) < 0.5 or absf(dv) < 0.5: return
	m.counters["r"] += 1
	var rid := "r%d" % m.counters["r"]
	var n: Vector3 = state["n"]
	var plane := {}
	if state["on"] != "":
		plane = {"on": {"body": state["on"], "normal": Main.arr3(n), "point": Main.arr3(state["origin"])}}
	else:
		plane = {"origin": Main.arr3(state["origin"]), "normal": Main.arr3(n)}
	var op := {"id": rid, "type": "rect", "plane": plane,
			   "corner": [Main.r3(minf(0, du)), Main.r3(minf(0, dv))], "size": [Main.r3(absf(du)), Main.r3(absf(dv))]}
	m.ops.append(op)
	m._register_rect(op)
	state = {}
	m.overlay.mesh = null; m.overlay_lines.mesh = null
	m.sync()
