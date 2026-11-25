extends "res://tools/tool.gd"
## Rectangle (R): click a face or the ground, then click or type  width, height  + Return.
## Pressing R again toggles Rotated Rectangle (3-point: start, first edge, width; I64).
## Started with a click, it ends with a click; started with a press-and-drag (or a press held down), it ends
## when you let go (tool.gd, I43).

const TOOL := {"id": "rect", "label": "Rectangle", "tip": "Rectangle (R)", "key": KEY_R, "order": 30, "show_links": true}   # the toolbar, the Tools menu and the key (tool_registry.gd)
const LINE_COLOR := Color(0.1, 0.2, 0.6)

enum Stage { IDLE, EDGE, WIDTH }

var state := {}
var stage := Stage.IDLE
var rotated := false
var last_oid := ""
var last_meta := {}


func reset() -> void:
	_clear_gesture()
	if ctx != null and not ctx.ui.tool_active("rect"): rotated = false


func _clear_gesture() -> void:
	state = {}
	stage = Stage.IDLE
	press_reset()
	last_oid = ""
	last_meta = {}
	if ctx != null: ctx.view.clear_preview()


func tip() -> String:
	return "Rotated Rectangle" if rotated else "Rectangle"


func hint() -> String:
	if rotated:
		return "Rotated Rectangle: click start, click end of first edge, then click width; R for Rectangle"
	return "Rectangle: click a face or the ground, then click or type  width, height  + Enter; R for Rotated Rectangle"


func key(event: InputEventKey) -> bool:
	if event.keycode != KEY_R or event.ctrl_pressed or event.meta_pressed or event.alt_pressed:
		return false
	# Once typing a length, letters can belong to its unit.
	if not ctx.ui.typed_text().is_empty(): return false
	_clear_gesture()
	rotated = not rotated
	ctx.view.hide_marker()
	ctx.ui.refresh_hint()
	ctx.ui.refresh_measurements()
	ctx.ui.refresh_tip(ctx.pick.cursor())
	return true


func busy() -> bool:
	if stage != Stage.IDLE: return true
	if last_oid != "" and not ctx.document.is_last(last_oid):
		last_oid = ""
		last_meta = {}
	return last_oid != ""


func in_gesture() -> bool:
	return stage != Stage.IDLE        # (after a rectangle, typing amends it; that isn't a gesture)


func expects_pair() -> bool:
	return not rotated or stage == Stage.IDLE


func accepts_pair() -> bool:
	return stage != Stage.EDGE


func mouse_moved(screen: Vector2) -> void:
	press_moved(screen)
	if stage == Stage.EDGE:
		_edge_drag(screen)
	elif stage == Stage.WIDTH:
		_rect_drag(screen)
	else:
		ctx.view.marker(ctx.pick.snap(ctx.pick.hit(screen), screen))


func click(screen: Vector2) -> void:
	if stage == Stage.IDLE:
		last_oid = ""
		last_meta = {}
		var p := ctx.pick.snap(ctx.pick.hit(screen), screen)
		if not p.get("hit", false): return
		var on: String = p["body"]
		if p["rect"] != "": on = ctx.model.profile(p["rect"]).get("on", "")
		if ctx.selection.edit_blocked(on): return
		var n: Vector3 = p["normal"]
		if rotated:
			state = {"origin": p["point"], "end": p["point"], "n": n, "x": Vector3.ZERO, "y": Vector3.ZERO,
				"on": on, "du": 0.0, "dv": 0.0, "rotated": true, "point_snap": false}
			stage = Stage.EDGE
			ctx.ui.refresh_measurements()
		else:
			var b := Geo.plane_basis(n)
			state = {"origin": p["point"], "n": n, "x": b[0], "y": b[1], "on": on,
				"du": 0.0, "dv": 0.0, "rotated": false, "point_snap": false}
			stage = Stage.WIDTH
			press_started(screen)
	elif stage == Stage.EDGE:
		var v := _plane_vec(state["end"] - state["origin"])
		if v.length() < GEOMETRY_TOLERANCE_MM or not pointer_distance_ok(v.length(), state.get("point_snap", false)):
			return
		_lock_edge(v.normalized(), v.length())
	else:
		_finish_rect()


func release(screen: Vector2) -> void:
	if rotated or stage != Stage.WIDTH: return
	if not press_released().get("drag", false): return   # a click: the rectangle ends with the next click
	_rect_drag(screen)
	_finish_rect()     # a drag: it ends here


func typed(txt: String) -> void:
	if stage == Stage.IDLE:
		_amend_last_rect(txt)
		return
	if rotated and stage == Stage.EDGE:
		var length := float(txt)
		var v := _plane_vec(state["end"] - state["origin"])
		if not is_finite(length) or length < GEOMETRY_TOLERANCE_MM or v.length() < GEOMETRY_TOLERANCE_MM: return
		_lock_edge(v.normalized(), length)
		return
	var parts := txt.split(",")
	if rotated and stage == Stage.WIDTH and parts.size() == 1:
		var width := absf(float(parts[0]))
		if not is_finite(width) or width < GEOMETRY_TOLERANCE_MM: return
		var sv := -1.0 if state["dv"] < 0 else 1.0
		commit_rect(state["du"], width * sv)
		return
	if parts.size() != 2: return
	var w := absf(float(parts[0])); var h := absf(float(parts[1]))
	var su := 1.0 if rotated else (-1.0 if state["du"] < 0 else 1.0)
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
	state = {"origin": meta["origin"], "n": meta["n"], "x": meta["x"], "y": meta["y"],
		"on": meta["on"], "du": meta["du"], "dv": meta["dv"], "rotated": meta.get("rotated", false)}
	commit_rect(w * float(meta["su"]), h * float(meta["sv"]), oid)


func vcb_label() -> String:
	if rotated:
		if stage == Stage.EDGE: return "Length"
		if stage == Stage.WIDTH: return "Width"
	return "Dimensions"


func vcb_value() -> String:
	if stage == Stage.EDGE:
		return ctx.ui.format_length(state["du"])
	if stage == Stage.WIDTH:
		if rotated: return ctx.ui.format_length(absf(state["dv"]))
		return "%s, %s" % [ctx.ui.format_length(absf(state["du"])), ctx.ui.format_length(absf(state["dv"]))]
	if last_oid != "":
		if ctx.document.is_last(last_oid) and not ctx.document.op(last_oid).is_empty():
			return "%s, %s" % [ctx.ui.format_length(absf(last_meta["du"])), ctx.ui.format_length(absf(last_meta["dv"]))]
		last_oid = ""
		last_meta = {}
	return ""


func _plane_hit(screen: Vector2) -> Dictionary:
	var ray := ctx.pick.ray(screen)
	var o: Vector3 = ray["origin"]
	var d: Vector3 = ray["direction"]
	var n: Vector3 = state["n"]
	var den := d.dot(n)
	if absf(den) < 1e-6: return {}
	var t: float = (state["origin"] - o).dot(n) / den
	var q: Vector3 = o + d * t
	var p := ctx.pick.snap({"hit": true, "point": q, "normal": n, "body": state["on"], "rect": ""}, screen)
	return {"q": q, "p": p}


func _plane_vec(v: Vector3) -> Vector3:
	var n: Vector3 = state["n"]
	return v - n * v.dot(n)


func _edge_drag(screen: Vector2) -> void:
	var hit := _plane_hit(screen)
	if hit.is_empty(): return
	var p: Dictionary = hit["p"]
	var v := _plane_vec(p["point"] - state["origin"])
	if p.get("snap", "grid") != "grid" and v.length() < GEOMETRY_TOLERANCE_MM:
		p = ctx.pick.on_grid({"hit": true, "point": hit["q"], "normal": state["n"], "body": state["on"], "rect": ""})
		v = _plane_vec(p["point"] - state["origin"])
	ctx.view.marker(p)
	state["point_snap"] = p.get("snap", "") in ["endpoint", "midpoint", "on edge"]
	state["end"] = state["origin"] + v
	state["du"] = v.length()
	ctx.view.preview(PackedVector3Array(), "profile", PackedVector3Array([state["origin"], state["end"]]), LINE_COLOR)
	ctx.ui.refresh_measurements()


func _lock_edge(dir: Vector3, length: float) -> void:
	press_reset()
	state["x"] = dir
	state["y"] = state["n"].cross(dir).normalized()
	state["du"] = length
	state["dv"] = 0.0
	state["point_snap"] = false
	stage = Stage.WIDTH
	ctx.view.hide_marker()
	_preview_rect(length, 0.0)
	ctx.ui.refresh_measurements()


func _rect_drag(screen: Vector2) -> void:
	var hit := _plane_hit(screen)
	if hit.is_empty(): return
	var p: Dictionary = hit["p"]
	var v: Vector3 = p["point"] - state["origin"]
	var bad_snap: bool = absf(v.dot(state["y"])) < GEOMETRY_TOLERANCE_MM if state.get("rotated", false) \
		else (absf(v.dot(state["x"])) < GEOMETRY_TOLERANCE_MM or absf(v.dot(state["y"])) < GEOMETRY_TOLERANCE_MM)
	if p.get("snap", "grid") != "grid" and bad_snap:
		# a point snap that leaves a side at zero (the start corner, the edge you started on) can't make a
		# rectangle: ignore it and follow the cursor (I44)
		p = ctx.pick.on_grid({"hit": true, "point": hit["q"], "normal": state["n"], "body": state["on"], "rect": ""})
		v = p["point"] - state["origin"]
	ctx.view.marker(p)
	state["point_snap"] = p.get("snap", "") in ["endpoint", "midpoint", "on edge"]
	if not state.get("rotated", false):
		state["du"] = v.dot(state["x"])
	state["dv"] = v.dot(state["y"])
	_preview_rect(state["du"], state["dv"])
	ctx.ui.refresh_measurements()


func _preview_rect(du: float, dv: float) -> void:
	var pts := Geo.rect_points(state["origin"], state["x"], state["y"], du, dv)
	var tris := PackedVector3Array([pts[0], pts[1], pts[2], pts[0], pts[2], pts[3]])
	ctx.view.preview(tris, "profile", PackedVector3Array([pts[0], pts[1], pts[1], pts[2], pts[2], pts[3], pts[3], pts[0]]), LINE_COLOR)


func _finish_rect() -> void:
	var d: float = absf(state["dv"]) if state.get("rotated", false) else minf(absf(state["du"]), absf(state["dv"]))
	if not pointer_distance_ok(d, state.get("point_snap", false)): return
	commit_rect(state["du"], state["dv"])


func commit_rect(du: float, dv: float, reuse_oid := "") -> void:
	if absf(du) < GEOMETRY_TOLERANCE_MM or absf(dv) < GEOMETRY_TOLERANCE_MM: return
	var rid := reuse_oid if reuse_oid != "" else ctx.document.next_id("r")
	var n: Vector3 = state["n"]
	var is_rotated: bool = state.get("rotated", rotated)
	var plane := {}
	if state["on"] != "":
		plane = {"on": {"body": state["on"], "normal": Geo.arr3(n), "point": Geo.arr3(state["origin"])}}
	else:
		plane = {"origin": Geo.arr3(state["origin"]), "normal": Geo.arr3(n)}
	var op := {"id": rid, "type": "rect", "plane": plane,
			   "corner": [minf(0, du), minf(0, dv)], "size": [absf(du), absf(dv)]}
	if is_rotated:
		op["x"] = Geo.arr3(state["x"])
	ctx.document.append(op)
	ctx.view.register_profile(op)
	last_oid = rid
	last_meta = {
		"origin": state["origin"], "n": n, "x": state["x"], "y": state["y"], "on": state["on"],
		"su": -1.0 if du < 0 else 1.0, "sv": -1.0 if dv < 0 else 1.0, "du": du, "dv": dv,
		"rotated": is_rotated,
	}
	state = {}
	stage = Stage.IDLE
	ctx.view.clear_preview()
	ctx.document.sync()
	ctx.ui.refresh_measurements()
