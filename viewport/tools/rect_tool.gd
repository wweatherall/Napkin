extends "res://tools/tool.gd"
## Rectangle (R): click a face or the ground, then click or type  width, height  + Return.
## Started with a click, it ends with a click; started with a press-and-drag (or a press held down), it ends
## when you let go (tool.gd, I43).

const TOOL := {"id": "rect", "label": "Rectangle", "tip": "Rectangle (R)", "key": KEY_R, "order": 30, "show_links": true}   # the toolbar, the Tools menu and the key (tool_registry.gd)

var state := {}
var last_oid := ""
var last_meta := {}


func reset() -> void:
	state = {}
	press_reset()
	last_oid = ""
	last_meta = {}


func hint() -> String:
	return "Rectangle: click a face or the ground, then click or type  width, height  + Enter"


func busy() -> bool:
	if state.get("active", false): return true
	if last_oid != "" and not ctx.document.is_last(last_oid):
		last_oid = ""
		last_meta = {}
	return last_oid != ""


func in_gesture() -> bool:
	return state.get("active", false)        # (after a rectangle, typing amends it; that isn't a gesture)


func mouse_moved(screen: Vector2) -> void:
	press_moved(screen)
	if state.get("active", false):
		_rect_drag(screen)
	else:
		ctx.view.marker(ctx.pick.snap(ctx.pick.hit(screen), screen))


func click(screen: Vector2) -> void:
	if not state.get("active", false):
		last_oid = ""
		last_meta = {}
		var p := ctx.pick.snap(ctx.pick.hit(screen), screen)
		if not p.get("hit", false): return
		if ctx.selection.edit_blocked(p["body"]): return
		var n: Vector3 = p["normal"]
		var b := Geo.plane_basis(n)
		var on: String = p["body"]
		if p["rect"] != "": on = ctx.model.profile(p["rect"]).get("on", "")
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
	if not state.get("active", false):
		_amend_last_rect(txt)
		return
	var parts := txt.split(",")
	if parts.size() != 2: return
	var w := absf(float(parts[0])); var h := absf(float(parts[1]))
	var su := -1.0 if state["du"] < 0 else 1.0
	var sv := -1.0 if state["dv"] < 0 else 1.0
	commit_rect(w * su, h * sv)


func _amend_last_rect(txt: String) -> void:
	"""SketchUp's after-the-fact typing (I65): retype width, height right after placing a rectangle."""
	if last_oid == "": return
	if not ctx.document.is_last(last_oid) or ctx.document.op(last_oid).is_empty():
		last_oid = ""
		last_meta = {}
		ctx.ui.refresh_measurements()
		return
	var parts := txt.split(",")
	if parts.size() != 2: return
	var a := parts[0].strip_edges()
	var b := parts[1].strip_edges()
	if not a.is_valid_float() or not b.is_valid_float(): return
	var w := float(a); var h := float(b)
	if w < GEOMETRY_TOLERANCE_MM or h < GEOMETRY_TOLERANCE_MM: return
	var oid := last_oid
	var meta := last_meta.duplicate()
	ctx.document.remove(oid, false)
	state = {"active": false, "origin": meta["origin"], "n": meta["n"], "x": meta["x"], "y": meta["y"],
			 "on": meta["on"], "du": meta["du"], "dv": meta["dv"]}
	commit_rect(w * float(meta["su"]), h * float(meta["sv"]), oid)


func vcb_label() -> String:
	return "Dimensions"


func vcb_value() -> String:
	if state.get("active", false):
		return "%s, %s" % [ctx.ui.format_length(absf(state["du"])), ctx.ui.format_length(absf(state["dv"]))]
	if last_oid != "":
		if ctx.document.is_last(last_oid) and not ctx.document.op(last_oid).is_empty():
			return "%s, %s" % [ctx.ui.format_length(absf(last_meta["du"])), ctx.ui.format_length(absf(last_meta["dv"]))]
		last_oid = ""
		last_meta = {}
	return ""


func _rect_drag(screen: Vector2) -> void:
	var ray := ctx.pick.ray(screen)
	var o: Vector3 = ray["origin"]
	var d: Vector3 = ray["direction"]
	var n: Vector3 = state["n"]
	var den := d.dot(n)
	if absf(den) < 1e-6: return
	var t: float = (state["origin"] - o).dot(n) / den
	var q: Vector3 = o + d * t
	var p := ctx.pick.snap({"hit": true, "point": q, "normal": n, "body": state["on"], "rect": ""}, screen)
	var v: Vector3 = p["point"] - state["origin"]
	if p.get("snap", "grid") != "grid" and (absf(v.dot(state["x"])) < GEOMETRY_TOLERANCE_MM or absf(v.dot(state["y"])) < GEOMETRY_TOLERANCE_MM):
		# a point snap that leaves a side at zero (the start corner, the edge you started on) can't make a
		# rectangle: ignore it and follow the cursor (I44)
		p = ctx.pick.on_grid({"hit": true, "point": q, "normal": n, "body": state["on"], "rect": ""})
		v = p["point"] - state["origin"]
	ctx.view.marker(p)
	state["point_snap"] = p.get("snap", "") in ["endpoint", "midpoint", "on edge"]
	state["du"] = v.dot(state["x"])
	state["dv"] = v.dot(state["y"])
	_preview_rect(state["du"], state["dv"])
	ctx.ui.refresh_measurements()


func _preview_rect(du: float, dv: float) -> void:
	var pts := Geo.rect_points(state["origin"], state["x"], state["y"], du, dv)
	var tris := PackedVector3Array([pts[0], pts[1], pts[2], pts[0], pts[2], pts[3]])
	ctx.view.preview(tris, "profile", PackedVector3Array([pts[0], pts[1], pts[1], pts[2], pts[2], pts[3], pts[3], pts[0]]), Color(0.1, 0.2, 0.6))


func _finish_rect() -> void:
	if not pointer_distance_ok(minf(absf(state["du"]), absf(state["dv"])), state.get("point_snap", false)): return
	commit_rect(state["du"], state["dv"])


func commit_rect(du: float, dv: float, reuse_oid := "") -> void:
	if absf(du) < GEOMETRY_TOLERANCE_MM or absf(dv) < GEOMETRY_TOLERANCE_MM: return
	var rid := reuse_oid if reuse_oid != "" else ctx.document.next_id("r")
	var n: Vector3 = state["n"]
	var plane := {}
	if state["on"] != "":
		plane = {"on": {"body": state["on"], "normal": Geo.arr3(n), "point": Geo.arr3(state["origin"])}}
	else:
		plane = {"origin": Geo.arr3(state["origin"]), "normal": Geo.arr3(n)}
	var op := {"id": rid, "type": "rect", "plane": plane,
			   "corner": [minf(0, du), minf(0, dv)], "size": [absf(du), absf(dv)]}
	ctx.document.append(op)
	ctx.view.register_profile(op)
	last_oid = rid
	last_meta = {
		"origin": state["origin"], "n": n, "x": state["x"], "y": state["y"], "on": state["on"],
		"su": -1.0 if du < 0 else 1.0, "sv": -1.0 if dv < 0 else 1.0, "du": du, "dv": dv,
	}
	state = {}
	ctx.view.clear_preview()
	ctx.document.sync()
	ctx.ui.refresh_measurements()
