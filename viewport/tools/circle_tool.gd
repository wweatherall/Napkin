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
		ctx.view.marker(ctx.pick.snap(ctx.pick.hit(screen), screen))


func click(screen: Vector2) -> void:
	if busy():
		_finish_circle()
		return
	var p := ctx.pick.snap(ctx.pick.hit(screen), screen)
	if not p.get("hit", false): return
	if ctx.selection.edit_blocked(p["body"]): return
	var on: String = p["body"]
	if p["rect"] != "": on = ctx.model.profile(p["rect"]).get("on", "")
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
	return ctx.ui.format_length(state["radius"]) if busy() else ""


func _radius_drag(screen: Vector2) -> void:
	var ray := ctx.pick.ray(screen)
	var o: Vector3 = ray["origin"]
	var d: Vector3 = ray["direction"]
	var n: Vector3 = state["n"]
	var den := d.dot(n)
	if absf(den) < 1e-6: return
	var t: float = (state["origin"] - o).dot(n) / den
	var q := o + d * t
	var p := ctx.pick.snap({"hit": true, "point": q, "normal": n, "body": state["on"], "rect": ""}, screen)
	var v: Vector3 = p["point"] - state["origin"]
	v -= n * v.dot(n)
	# A snap to the centre cannot make a circle; follow the grid/cursor, as Rectangle does for zero sides.
	if p.get("snap", "grid") != "grid" and v.length() < GEOMETRY_TOLERANCE_MM:
		p = ctx.pick.on_grid({"hit": true, "point": q, "normal": n, "body": state["on"], "rect": ""})
		v = p["point"] - state["origin"]
	ctx.view.marker(p)
	state["point_snap"] = p.get("snap", "") in ["endpoint", "midpoint", "on edge"]
	state["radius"] = v.length()
	var shape := ctx.model.circle_geometry(state["origin"], n, state["radius"])
	ctx.view.preview(shape.tris, "profile", shape.lines, Color(0.1, 0.2, 0.6))
	ctx.ui.refresh_measurements()


func _finish_circle() -> void:
	if not pointer_distance_ok(state["radius"], state.get("point_snap", false)): return
	commit_circle(state["radius"])


func commit_circle(radius: float) -> void:
	if not is_finite(radius) or radius < GEOMETRY_TOLERANCE_MM: return
	var rid := ctx.document.next_id("r")
	var plane := {}
	if state["on"] != "":
		plane = {"on": {"body": state["on"], "normal": Geo.arr3(state["n"]), "point": Geo.arr3(state["origin"])}}
	else:
		plane = {"origin": Geo.arr3(state["origin"]), "normal": Geo.arr3(state["n"])}
	var op := {"id": rid, "type": "circle", "plane": plane, "radius": radius}
	ctx.document.append(op)
	ctx.view.register_profile(op)      # shared loose-profile presentation and picking
	reset()
	ctx.view.clear_preview()
	ctx.document.sync()
