extends "res://tools/tool.gd"
## I60: both gestures save the start, halfway point and end of one circular arc.

const Presenter := preload("res://presenter.gd")
const TOOL := {"id": "arc", "label": "Arc", "tip": "Arc (A)", "key": KEY_A, "order": 38, "show_links": true}
const LINE_COLOR := Color(0.1, 0.2, 0.6)
const TANGENT_COLOR := Color.MAGENTA
const POINT_SNAPS := ["endpoint", "midpoint", "on edge"]

enum Stage { FIRST_POINT, SECOND_POINT, SHAPE }

var state := {}
var centre := false
var stage := Stage.FIRST_POINT


func reset() -> void:
	_clear_gesture()
	if ctx != null and not ctx.ui.tool_active("arc"): centre = false


func _clear_gesture() -> void:
	state = {}
	stage = Stage.FIRST_POINT
	press_reset()
	if ctx != null: ctx.view.clear_preview()


func busy() -> bool:
	return stage != Stage.FIRST_POINT


func tip() -> String:
	if state.get("tangent", false): return "Tangent at corner"
	return "Centre Arc" if centre else "2-Point Arc"


func hint() -> String:
	if centre: return "Centre Arc: click the centre, then the start, then sweep to the end; A for 2-Point Arc"
	return "2-Point Arc: click the start, then the end, then the bulge; A for Centre Arc"


func key(event: InputEventKey) -> bool:
	if event.keycode != KEY_A or event.ctrl_pressed or event.meta_pressed or event.alt_pressed:
		return false
	# Once typing a length, letters can belong to its unit.
	if not ctx.ui.typed_text().is_empty(): return false
	_clear_gesture()
	centre = not centre
	ctx.view.hide_marker()
	ctx.ui.refresh_hint()
	ctx.ui.refresh_measurements()
	ctx.ui.refresh_tip(ctx.pick.cursor())
	return true


func vcb_label() -> String:
	if centre: return "Angle" if typed_raw() else "Radius"
	return "Bulge" if radius_input() else "Length"


func vcb_value() -> String:
	if not busy(): return ""
	if stage == Stage.SECOND_POINT: return ctx.ui.format_length(state.first.distance_to(state.second))
	if centre: return "%s°" % str(snappedf(rad_to_deg(state.sweep), 0.1))
	return ctx.ui.format_length(absf(state.height))


func typed_raw() -> bool:
	return centre and stage == Stage.SHAPE


func radius_input() -> bool:
	return not centre and stage == Stage.SHAPE


func mouse_moved(screen: Vector2) -> void:
	press_moved(screen)
	if busy(): _follow(screen)
	else: ctx.view.marker(ctx.pick.snap(ctx.pick.hit(screen), screen))


func click(screen: Vector2) -> void:
	if not busy():
		_start(screen)
		return
	_follow(screen)
	if stage == Stage.SECOND_POINT:
		_place_second()
	elif centre:
		_commit_sweep(state.sweep, state.get("end_snap", false))
	elif state.tangent:
		_commit_fillet(state.fillet)
	elif pointer_distance_ok(state.height, false):
		_commit_bulge(state.height)


func release(screen: Vector2) -> void:
	if stage == Stage.SECOND_POINT and not centre and press_released().get("drag", false):
		_follow(screen)
		_place_second()


func _start(screen: Vector2) -> void:
	var p := ctx.pick.snap(ctx.pick.hit(screen), screen)
	if not p.get("hit", false): return
	var profile := ctx.model.profile(p.rect) if p.rect != "" else {}
	var on: String = profile.get("on", p.body)
	if ctx.selection.edit_blocked(on): return
	var source: PackedVector3Array = profile.tris if not profile.is_empty() else ctx.model.triangles(on)
	var normal: Vector3 = p.normal
	# Reuse Line's plane correction for Float32 physics hits on exact faces and profiles.
	for i in range(0, source.size(), 3):
		var n := (source[i + 1] - source[i]).cross(source[i + 2] - source[i]).normalized()
		var gap: float = (p.point - source[i]).dot(normal)
		if absf(n.dot(normal)) > 0.999 and absf(gap) < GEOMETRY_TOLERANCE_MM:
			p.point -= normal * gap
			break
	state = {"first": p.point, "second": p.point, "n": normal, "on": on, "first_snap": _point_snapped(p)}
	if not centre and state.first_snap and profile.get("kind", "") != "circle":
		state.corners = _corners(source, not profile.is_empty())
	stage = Stage.SECOND_POINT
	if not centre: press_started(screen)
	ctx.ui.refresh_measurements()


func _follow(screen: Vector2) -> void:
	var ray := ctx.pick.ray(screen)
	var normal: Vector3 = state.n
	var den: float = ray.direction.dot(normal)
	if absf(den) < 1e-8: return
	var q: Vector3 = ray.origin + ray.direction * ((state.first - ray.origin).dot(normal) / den)
	if stage == Stage.SECOND_POINT:
		var p := _snap(q, screen)
		if not centre:
			p = _snap_corner(p, screen)
		state.second = p.point
		state.second_snap = _point_snapped(p)
		ctx.view.marker(p)
		_preview_segment()
	elif centre:
		_follow_sweep(q, screen)
	else:
		state.height = (q - _chord_mid()).dot(_bulge_axis())
		var fillet: PackedVector3Array = state.fillet
		state.tangent = not fillet.is_empty() and _screen_distance(fillet[1], screen) < ctx.pick.snap_radius()
		if state.tangent:
			state.height = (fillet[1] - _chord_mid()).dot(_bulge_axis())
			_preview(fillet[0], fillet[1], fillet[2], TANGENT_COLOR)
		else:
			_preview(state.first, _chord_mid() + _bulge_axis() * state.height, state.second)
	ctx.ui.refresh_measurements()


func _snap(q: Vector3, screen: Vector2) -> Dictionary:
	var n: Vector3 = state.n
	var p := ctx.pick.snap({"hit": true, "point": q, "normal": n, "body": state.on, "rect": ""}, screen)
	p.point -= n * (p.point - state.first).dot(n)
	return p


func _point_snapped(p: Dictionary) -> bool:
	return p.get("snap", "") in POINT_SNAPS


func _corners(source: PackedVector3Array, is_profile: bool) -> Array:
	var first: Vector3 = state.first
	var outline := _plane_outline(source, first, state.n)
	var corners := []
	for edge in outline:
		if not _on_segment(first, edge[0], edge[1]): continue
		for i in 2:
			var vertex: Vector3 = edge[i]
			if first.distance_to(vertex) < GEOMETRY_TOLERANCE_MM: continue
			if not is_profile and not _is_board_vertex(vertex): continue
			var from: Vector3 = edge[1 - i] - vertex
			for adjacent in outline:
				if adjacent == edge: continue
				var to: Vector3
				if vertex.distance_to(adjacent[0]) < GEOMETRY_TOLERANCE_MM:
					to = adjacent[1] - vertex
				elif vertex.distance_to(adjacent[1]) < GEOMETRY_TOLERANCE_MM:
					to = adjacent[0] - vertex
				else:
					continue
				var cosine := from.normalized().dot(to.normalized())
				if absf(cosine) >= 1.0 - 1e-6: continue
				corners.append({"vertex": vertex, "from": from, "to": to,
					"half_angle": acos(cosine) * 0.5})
	return corners


static func _plane_outline(source: PackedVector3Array, point: Vector3, normal: Vector3) -> Array:
	# Keep the boundary of the coplanar triangles, omitting internal triangulation edges.
	var boundary := {}
	for i in range(0, source.size(), 3):
		var a := source[i]
		var b := source[i + 1]
		var c := source[i + 2]
		if maxf(absf((a - point).dot(normal)), maxf(absf((b - point).dot(normal)),
			absf((c - point).dot(normal)))) >= GEOMETRY_TOLERANCE_MM: continue
		for edge in [[a, b], [b, c], [c, a]]:
			var key: Array = edge if edge[0] < edge[1] else [edge[1], edge[0]]
			if boundary.has(key): boundary.erase(key)
			else: boundary[key] = edge
	return boundary.values()


func _is_board_vertex(vertex: Vector3) -> bool:
	# A curved boundary also has display facets. Only native endpoints can be corners.
	var projection := ctx.pick.project(vertex)
	if projection.behind: return false
	var hit := ctx.pick.point(projection.screen, "", {"n": state.n, "p": vertex})
	return hit.get("kind", "") == "endpoint" and hit.body == state.on \
		and vertex.distance_to(hit.point) < GEOMETRY_TOLERANCE_MM


static func _on_segment(point: Vector3, a: Vector3, b: Vector3) -> bool:
	return point.distance_to(Geometry3D.get_closest_point_to_segment(point, a, b)) < GEOMETRY_TOLERANCE_MM


func _screen_distance(point: Vector3, screen: Vector2) -> float:
	var projection := ctx.pick.project(point)
	return INF if projection.behind else screen.distance_to(projection.screen)


func _snap_corner(p: Dictionary, screen: Vector2) -> Dictionary:
	state.corner = {}
	state.fillet = PackedVector3Array()
	if not _point_snapped(p): return p
	var nearest := ctx.pick.snap_radius()
	for corner in state.get("corners", []):
		var vertex: Vector3 = corner.vertex
		if vertex.distance_to(p.point) < GEOMETRY_TOLERANCE_MM \
			or not _on_segment(p.point, vertex, vertex + corner.to): continue
		state.corner = corner
		var fillet := _fillet(corner, vertex.distance_to(state.first))
		if fillet.is_empty(): continue
		var distance := _screen_distance(fillet[2], screen)
		if distance >= nearest: continue
		nearest = distance
		state.fillet = fillet
	if not state.fillet.is_empty():
		p.point = state.fillet[2]
		p.snap = "on edge"
	return p


static func _fillet(corner: Dictionary, setback: float) -> PackedVector3Array:
	var vertex: Vector3 = corner.vertex
	var from: Vector3 = corner.from
	var to: Vector3 = corner.to
	if not is_finite(setback) or setback < GEOMETRY_TOLERANCE_MM or setback > minf(from.length(), to.length()):
		return PackedVector3Array()
	var a := from.normalized()
	var b := to.normalized()
	var angle: float = corner.half_angle
	# Along the bisector, the arc midpoint is the circle centre minus its radius.
	var middle := setback * cos(angle) / (1.0 + sin(angle))
	return PackedVector3Array([vertex + a * setback, vertex + (a + b).normalized() * middle, vertex + b * setback])


func _place_second(typed_length := false) -> void:
	var delta: Vector3 = state.second - state.first
	if not delta.is_finite() or delta.length() < GEOMETRY_TOLERANCE_MM: return
	if not typed_length and not pointer_distance_ok(delta.length(), state.get("second_snap", false)): return
	press_reset()
	stage = Stage.SHAPE
	state.height = 0.0
	state.tangent = false
	state.sweep = 0.0
	state.last_direction = delta.normalized()
	_preview_segment()
	ctx.view.hide_marker()
	ctx.ui.refresh_measurements()


func _follow_sweep(q: Vector3, screen: Vector2) -> void:
	var radial: Vector3 = state.second - state.first
	var cursor: Vector3 = q - state.first
	if cursor.length() < GEOMETRY_TOLERANCE_MM: return
	var p := _snap(q, screen)
	var snapped: Vector3 = p.point - state.first
	state.end_snap = _point_snapped(p) and absf(snapped.length() - radial.length()) < GEOMETRY_TOLERANCE_MM
	var direction := (snapped if state.end_snap else cursor).normalized()
	if state.end_snap: ctx.view.marker(p)
	else: ctx.view.hide_marker()
	var n: Vector3 = state.n
	var last: Vector3 = state.last_direction
	state.sweep += atan2(n.dot(last.cross(direction)), last.dot(direction))
	state.last_direction = direction
	if absf(state.sweep) < TAU:
		_preview(state.second, state.first + radial.rotated(n, state.sweep * 0.5), state.first + radial.rotated(n, state.sweep))
	else:
		ctx.view.clear_preview()


func typed(txt: String) -> void:
	if not busy(): return
	if typed_raw():
		if txt.is_valid_float(): _commit_sweep(deg_to_rad(float(txt)))
		return
	if stage == Stage.SECOND_POINT:
		var delta: Vector3 = state.second - state.first
		var length := float(txt)
		if not is_finite(length) or length < GEOMETRY_TOLERANCE_MM or delta.length() < GEOMETRY_TOLERANCE_MM: return
		state.second = state.first + delta.normalized() * length
		state.second_snap = false
		state.corner = {}
		state.fillet = PackedVector3Array()
		_place_second(true)
		return
	var magnitude := absf(float(txt.trim_suffix("r")))
	if txt.ends_with("r"):
		var corner: Dictionary = state.get("corner", {})
		if not corner.is_empty():
			var setback: float = magnitude / tan(corner.half_angle)
			var longest: float = minf(corner.from.length(), corner.to.length())
			if is_finite(setback) and setback > longest + GEOMETRY_TOLERANCE_MM:
				ctx.ui.show_status("Radius must be at most %s for this corner"
					% ctx.ui.format_length(longest * tan(corner.half_angle), true))
				return
			# Float noise can put the largest radius itself a hair past the edge's end.
			_commit_fillet(_fillet(corner, minf(setback, longest)))
			return
		var half: float = state.first.distance_to(state.second) * 0.5
		if magnitude < half:
			ctx.ui.show_status("Radius must be at least half the chord")
			return
		# The rationalized sagitta avoids subtracting two nearly equal distances.
		magnitude = half * (half / magnitude) / (1.0 + sqrt(1.0 - (half / magnitude) ** 2))
	_commit_bulge(-magnitude if state.height < 0.0 else magnitude)


func _chord_mid() -> Vector3:
	return state.first + (state.second - state.first) * 0.5


func _bulge_axis() -> Vector3:
	return state.n.cross(state.second - state.first).normalized()


func _preview_segment() -> void:
	ctx.view.preview(PackedVector3Array(), "profile", PackedVector3Array([state.first, state.second]), LINE_COLOR)


func _preview(a: Vector3, mid: Vector3, b: Vector3, color := LINE_COLOR) -> void:
	var points := Presenter.arc_points(a, mid, b)
	ctx.view.preview(PackedVector3Array(), "profile", Presenter.polyline_segments(points), color)


func _commit_fillet(points: PackedVector3Array) -> void:
	if points.is_empty(): return
	_commit(points[0], points[1], points[2], true, true, true)


func _commit_bulge(height: float) -> void:
	if not is_finite(height) or absf(height) < GEOMETRY_TOLERANCE_MM: return
	_commit(state.first, _chord_mid() + _bulge_axis() * height, state.second, state.first_snap, state.get("second_snap", false))


func _commit_sweep(sweep: float, end_snap := false) -> void:
	if not is_finite(sweep) or absf(sweep) >= TAU: return
	var radial: Vector3 = state.second - state.first
	var centre_point: Vector3 = state.first
	var n: Vector3 = state.n
	_commit(state.second, centre_point + radial.rotated(n, sweep * 0.5),
		centre_point + radial.rotated(n, sweep), state.get("second_snap", false), end_snap)


func _commit(a: Vector3, mid: Vector3, b: Vector3, snap_start: bool, snap_end: bool, tangent := false) -> void:
	var chord := b - a
	if not (a.is_finite() and mid.is_finite() and b.is_finite()): return
	var minimum := minf(chord.length(), minf(a.distance_to(mid), b.distance_to(mid)))
	if minimum < GEOMETRY_TOLERANCE_MM: return
	if absf((mid - a).cross(chord.normalized()).dot(state.n)) < GEOMETRY_TOLERANCE_MM: return
	# Rounding the midpoint to 0.001 mm changes the radius and the tangent directions.
	var coordinates := func(p: Vector3) -> Array: return [p.x, p.y, p.z] if tangent else Geo.arr3(p)
	var plane := {"origin": coordinates.call(a), "normal": Geo.arr3(state.n)}
	if state.on != "": plane = {"on": {"body": state.on, "point": plane.origin, "normal": plane.normal}}
	var op := {"id": ctx.document.next_id("r"), "type": "arc", "plane": plane, "mid": coordinates.call(mid),
		"end": coordinates.call(b), "snap_start": snap_start, "snap_end": snap_end}
	ctx.ui.clear_rejection()
	ctx.document.append(op)
	ctx.view.register_line(op)
	_clear_gesture()
	ctx.view.hide_marker()
	ctx.ui.refresh_tip(ctx.pick.cursor())
	ctx.ui.refresh_measurements()
	ctx.document.sync()
