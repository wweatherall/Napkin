extends "res://tools/tool.gd"
## Polygon (T84, I64): centre, then circumradius; Circle's click/drag gesture (I43). A corner follows the cursor.
## Before a gesture the box is the side count: type 8 (Return optional; the centre click takes it) or 8s. During one,
## `8s` + Return sets the sides and a plain number is the radius (I-new-1). No key yet (Q33).

const TOOL := {"id": "polygon", "label": "Polygon", "tip": "Polygon", "key": KEY_NONE, "order": 36, "show_links": true}
const DEFAULT_SIDES := 6
const MIN_SIDES := 3
const MAX_SIDES := 64      # worker/polygon.py has the same range

var sides := DEFAULT_SIDES      # kept when the gesture or the tool is left
var state := {}


func reset() -> void:
	state = {}
	press_reset()


func hint() -> String:
	return "Polygon (%d sides): type the sides, then click a face or the ground for the centre, then click or type a radius + Enter" % sides


func busy() -> bool:
	return state.get("active", false)


func accepts_idle(ch: String, typed_so_far: String) -> bool:
	"""Characters taken before a gesture (keys.gd): a side count, `8s`. Letters stay tool keys until a digit."""
	return ch in "0123456789" or (ch.to_lower() == "s" and typed_so_far.is_valid_int())


func mouse_moved(screen: Vector2) -> void:
	press_moved(screen)
	if busy():
		_radius_drag(screen)
	else:
		ctx.view.marker(ctx.pick.snap(ctx.pick.hit(screen), screen))


func click(screen: Vector2) -> void:
	if busy():
		_finish()
		return
	var p := ctx.pick.snap(ctx.pick.hit(screen), screen)
	if not p.get("hit", false): return
	if ctx.selection.edit_blocked(p["body"]): return
	var on: String = p["body"]
	if p["rect"] != "": on = ctx.model.profile(p["rect"]).get("on", "")
	# A side count typed before the centre click and not entered yet still counts: the box said Sides (I-new-1).
	var pending := ctx.ui.typed_text().strip_edges().to_lower().trim_suffix("s").strip_edges()
	if pending.is_valid_int(): set_sides(pending)
	state = {"active": true, "origin": p["point"], "n": p["normal"], "on": on, "radius": 0.0, "x": Vector3.ZERO}
	ctx.ui.clear_typed()   # the radius starts from an empty box (I72's purpose, kept by I-new-1)
	press_started(screen)


func release(screen: Vector2) -> void:
	if not press_released().get("drag", false) or not busy(): return
	_radius_drag(screen)
	_finish()


func typed(txt: String) -> void:
	var t := txt.strip_edges().to_lower()
	if t.ends_with("s"):
		set_sides(t.left(-1).strip_edges())
	elif busy():
		commit_polygon(absf(float(t)))
	else:
		set_sides(t)   # before a gesture the box is the side count (I-new-1)


func set_sides(txt: String) -> void:
	if not txt.is_valid_int(): return
	var n := int(txt)
	if n < MIN_SIDES or n > MAX_SIDES: return
	sides = n
	if busy() and state["radius"] > 0.0: _preview()
	ctx.ui.refresh_hint()
	ctx.ui.refresh_measurements()


func vcb_label() -> String:
	return "Radius" if busy() else "Sides"


func vcb_value() -> String:
	return ctx.ui.format_length(state["radius"]) if busy() else str(sides)


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
	# A snap to the centre cannot make a polygon; follow the grid/cursor, as Circle does.
	if p.get("snap", "grid") != "grid" and v.length() < GEOMETRY_TOLERANCE_MM:
		p = ctx.pick.on_grid({"hit": true, "point": q, "normal": n, "body": state["on"], "rect": ""})
		v = p["point"] - state["origin"]
		v -= n * v.dot(n)
	ctx.view.marker(p)
	state["point_snap"] = p.get("snap", "") in ["endpoint", "midpoint", "on edge"]
	state["radius"] = v.length()
	if v.length() >= GEOMETRY_TOLERANCE_MM: state["x"] = v.normalized()
	_preview()
	ctx.ui.refresh_measurements()


func _preview() -> void:
	var shape := ctx.model.polygon_geometry(state["origin"], state["n"], state["radius"], sides, state["x"])
	ctx.view.preview(shape.tris, "profile", shape.lines, Color(0.1, 0.2, 0.6))


func _finish() -> void:
	if not pointer_distance_ok(state["radius"], state.get("point_snap", false)): return
	commit_polygon(state["radius"])


func commit_polygon(radius: float) -> void:
	if not is_finite(radius) or radius < GEOMETRY_TOLERANCE_MM: return
	var rid := ctx.document.next_id("r")
	var plane := {}
	if state["on"] != "":
		plane = {"on": {"body": state["on"], "normal": Geo.arr3(state["n"]), "point": Geo.arr3(state["origin"])}}
	else:
		plane = {"origin": Geo.arr3(state["origin"]), "normal": Geo.arr3(state["n"])}
	var op := {"id": rid, "type": "polygon", "plane": plane, "radius": radius, "sides": sides}
	# Toward the first corner, unrounded: three decimals would move a snapped corner of a large polygon.
	var x: Vector3 = state["x"]
	if x != Vector3.ZERO: op["x"] = [x.x, x.y, x.z]
	ctx.document.append(op)
	ctx.view.register_profile(op)
	reset()
	ctx.view.clear_preview()
	ctx.document.sync()
