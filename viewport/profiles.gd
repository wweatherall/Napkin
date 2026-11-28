extends RefCounted
## Drawn profiles (rectangles, circles, polygons, lines and arcs), `pres.profiles`: owns `rects` and `loose_lines`, their drafts, loop fills, and op cleanup.
##
## Owned and instantiated by presenter.gd, which keeps forwarders for main.gd, history.gd, inference.gd,
## tool_context.gd, arc_tool.gd and tests (`rects`, `loose_lines`, `CIRCLE_SEGMENTS`, `arc_points`,
## `polyline_segments`, `register_line`, `lines_on`, `drawn_region`, `register_rect`, `circle_geometry`,
## `polygon_geometry`, `rebuild_rect_drafts`, `forget_op`, `drop_confirmed_drafts`).
## Entry points: register_line, lines_on, drawn_region, register_rect, circle_geometry, polygon_geometry,
## rebuild_rect_drafts, forget_op, drop_confirmed_drafts.

const Regions := preload("res://regions.gd")
const Geo := preload("res://tool_geometry.gd")
# A viewport approximation only. The op contains the radius; FreeCAD keeps an exact sketch circle.
const CIRCLE_SEGMENTS := 64

var pres                            # presenter.gd
var rects := {}                     # profile id (rectangle, circle or polygon) -> {"tris","n","on","pts"}
var loose_lines := {}               # line id -> {a, b, n, on}; rebuilt from journal


func _init(p) -> void:
	pres = p


static func arc_points(a: Vector3, mid: Vector3, b: Vector3) -> PackedVector3Array:
	"""Tessellate an exact arc whose mid point is halfway along the sweep."""
	var half := a.distance_to(b) * 0.5
	if half <= 0.0: return PackedVector3Array()
	var along := (b - a).normalized()
	var chord_mid := a + (b - a) * 0.5
	var sag := mid - chord_mid
	sag -= along * sag.dot(along)
	var height := sag.length()
	if height <= 0.0: return PackedVector3Array()
	var side := sag / height
	var half_sweep := 2.0 * atan2(height, half)
	var radius := (half * half + height * height) / (2.0 * height)
	var count := maxi(2, ceili(CIRCLE_SEGMENTS * half_sweep / PI))
	var points := PackedVector3Array([a])
	for i in range(1, count):
		var angle := (2.0 * float(i) / count - 1.0) * half_sweep
		# cos(angle) - cos(half_sweep), factored to retain precision on shallow arcs.
		var rise := 2.0 * radius * sin((half_sweep + angle) * 0.5) * sin((half_sweep - angle) * 0.5)
		points.append(chord_mid + along * (radius * sin(angle)) + side * rise)
	points.append(b)
	return points


static func polyline_segments(points: PackedVector3Array) -> PackedVector3Array:
	var segments := PackedVector3Array()
	for i in range(1, points.size()):
		segments.append(points[i - 1])
		segments.append(points[i])
	return segments


func register_line(op: Dictionary) -> void:
	var src: Dictionary = op.plane.get("on", op.plane)
	var start: Array = src.get("point", src.get("origin", [0, 0, 0]))
	var a := Vector3(start[0], start[1], start[2])
	var b := Vector3(op.end[0], op.end[1], op.end[2])
	var n := Vector3(src.normal[0], src.normal[1], src.normal[2])
	loose_lines[op.id] = {"a": a, "b": b, "n": n, "on": src.get("body", ""), "snap_start": op.get("snap_start", false), "snap_end": op.get("snap_end", false)}
	drop_draft("line:" + op.id)
	var segments := PackedVector3Array([a, b])
	if op.type == "arc":
		var mid := Vector3(op.mid[0], op.mid[1], op.mid[2])
		var points := arc_points(a, mid, b)
		loose_lines[op.id]["pts"] = points
		loose_lines[op.id]["mid"] = mid
		segments = polyline_segments(points)
	var node: MeshInstance3D = pres.lines(segments, Color(0.1, 0.2, 0.6))
	pres.m.drafts_root.add_child(node)
	pres.drafts["line:" + op.id] = node
	if op.has("outline"): register_rect(op)
	if loose_lines[op.id].on == "": _refresh_loop_drafts()


func _canonical_normal(n: Vector3) -> Vector3:
	var u := n.normalized()
	if absf(u.x) > 1e-5: return -u if u.x < 0.0 else u
	if absf(u.y) > 1e-5: return -u if u.y < 0.0 else u
	return -u if u.z < 0.0 else u


func _point_in_ground_line_draft(pt: Vector3, normal: Vector3) -> bool:
	var basis := Geo.plane_basis(normal)
	for rid in rects:
		if not pres.drafts.has(rid): continue
		var r: Dictionary = rects[rid]
		if r.get("kind", "") != "line" or r.get("on", "") != "": continue
		if absf(r.n.normalized().dot(normal)) < 0.9999: continue
		var tris: PackedVector3Array = r.tris
		if tris.size() < 3 or absf((pt - tris[0]).dot(normal)) > Regions.EPS: continue
		var origin := tris[0]
		var p2 := Vector2((pt - origin).dot(basis[0]), (pt - origin).dot(basis[1]))
		for i in range(0, tris.size(), 3):
			var a2 := Vector2((tris[i] - origin).dot(basis[0]), (tris[i] - origin).dot(basis[1]))
			var b2 := Vector2((tris[i + 1] - origin).dot(basis[0]), (tris[i + 1] - origin).dot(basis[1]))
			var c2 := Vector2((tris[i + 2] - origin).dot(basis[0]), (tris[i + 2] - origin).dot(basis[1]))
			if Regions._in_tri(p2, a2, b2, c2): return true
	return false


func _refresh_loop_drafts() -> void:
	"""Translucent fill for closed ground loops of loose_lines not already shown by a line-profile rect draft."""
	drop_draft("line:loops")
	var groups := []
	for id in loose_lines:
		var line: Dictionary = loose_lines[id]
		if line.on != "": continue
		var n := _canonical_normal(line.n)
		var d: float = line.a.dot(n)
		var placed := false
		for g in groups:
			if absf(g.n.dot(n)) > 0.9999 and absf(g.d - d) <= Regions.EPS:
				g.lines.append(line)
				placed = true
				break
		if not placed:
			groups.append({"n": n, "d": d, "lines": [line]})
	var all_tris := PackedVector3Array()
	for g in groups:
		if g.lines.size() < 2: continue
		for face in Regions.all_faces(g.lines, g.n):
			var tris: PackedVector3Array = face.tris
			if tris.size() < 3: continue
			var sample: Vector3 = (tris[0] + tris[1] + tris[2]) / 3.0
			if _point_in_ground_line_draft(sample, g.n): continue
			all_tris.append_array(tris)
	if all_tris.is_empty(): return
	var mi := MeshInstance3D.new()
	mi.mesh = pres.tri_mesh(all_tris, pres.m.mat_rect)
	pres.m.drafts_root.add_child(mi)
	pres.drafts["line:loops"] = mi


func lines_on(body: String, normal: Vector3, point: Vector3) -> Array:
	"""Snapshot of drawings belonging to this body and plane; no cache escapes."""
	var result := []
	for id in loose_lines:
		var line: Dictionary = loose_lines[id]
		if line.on != body: continue
		var points: PackedVector3Array = line.get("pts", PackedVector3Array([line.a, line.b]))
		var coplanar := not points.is_empty()
		for p in points:
			if absf((p - point).dot(normal)) > Regions.EPS:
				coplanar = false
				break
		if not coplanar: continue
		var copy := line.duplicate(true); copy["id"] = id
		result.append(copy)
	return result


func drawn_region(source: PackedVector3Array, body: String, normal: Vector3, point: Vector3) -> Dictionary:
	var lines := lines_on(body, normal, point)
	if lines.is_empty(): return {}
	var result := Regions.find(source, lines, normal, point)
	if not result.is_empty() and not source.is_empty():
		var area := 0.0
		for i in range(0, source.size(), 3): area += (source[i + 1] - source[i]).cross(source[i + 2] - source[i]).length() * 0.5
		# An unrelated/dangling line does not replace an exact circle or a stock resize with mesh facets.
		if absf(result.area - area) <= maxf(0.001, area * 1e-6): return {}
	if not result.is_empty(): result["lines"] = lines.map(func(line): return line.id)
	return result


func register_rect(op: Dictionary) -> void:
	var pl: Dictionary = op["plane"]
	var src: Dictionary = pl["on"] if pl.has("on") else pl
	var origin := Vector3(src["point"][0], src["point"][1], src["point"][2]) if pl.has("on") else Vector3(src["origin"][0], src["origin"][1], src["origin"][2])
	var n := Vector3(src["normal"][0], src["normal"][1], src["normal"][2])
	var b: Array = Geo.plane_basis(n)
	if op["type"] == "rect" and op.get("x") != null:
		var bx := Vector3(op["x"][0], op["x"][1], op["x"][2])
		bx = (bx - n * bx.dot(n)).normalized()
		if bx.length() > 0.5:
			b = [bx, n.cross(bx).normalized()]
	var pts: PackedVector3Array
	var tris: PackedVector3Array
	var lines := PackedVector3Array()
	if op["type"] == "line":
		for p in op.outline: pts.append(Vector3(p[0], p[1], p[2]))
		var poly := PackedVector2Array()
		for p in pts: poly.append(Vector2(p.dot(b[0]), p.dot(b[1])))
		var indices := Geometry2D.triangulate_polygon(poly)
		if indices.is_empty(): return
		for i in indices: tris.append(pts[i])
		for i in pts.size(): lines.append_array([pts[i], pts[(i + 1) % pts.size()]])
	elif op["type"] == "circle":
		var center: Array = op.get("center", [0, 0])
		var shape := circle_geometry(origin + b[0] * float(center[0]) + b[1] * float(center[1]), n, op["radius"])
		pts = shape.pts; tris = shape.tris; lines = shape.lines
	elif op["type"] == "polygon":
		var center: Array = op.get("center", [0, 0])
		var toward: Array = op.get("x", [0, 0, 0])
		var shape := polygon_geometry(origin + b[0] * float(center[0]) + b[1] * float(center[1]), n, op["radius"],
				int(op["sides"]), Vector3(toward[0], toward[1], toward[2]))
		pts = shape.pts; tris = shape.tris; lines = shape.lines
	else:
		var corner: Array = op.get("corner", [0, 0])
		var o2: Vector3 = origin + b[0] * float(corner[0]) + b[1] * float(corner[1])
		pts = Geo.rect_points(o2, b[0], b[1], op["size"][0], op["size"][1])
		tris = PackedVector3Array([pts[0], pts[1], pts[2], pts[0], pts[2], pts[3]])
		lines = PackedVector3Array([pts[0], pts[1], pts[1], pts[2], pts[2], pts[3], pts[3], pts[0]])
	rects[op["id"]] = {"tris": tris, "n": n, "on": src.get("body", "") if pl.has("on") else "", "pts": pts, "kind": op["type"]}
	var mi := MeshInstance3D.new()
	mi.mesh = pres.tri_mesh(tris, pres.m.mat_rect)
	mi.add_child(pres.lines(lines, Color(0.1, 0.2, 0.6)))
	pres.m.drafts_root.add_child(mi)
	pres.add_collision(mi, "rect_id", op["id"])
	pres.drafts[op["id"]] = mi


func circle_geometry(center: Vector3, normal: Vector3, radius: float) -> Dictionary:
	return polygon_geometry(center, normal, radius, CIRCLE_SEGMENTS)


# A regular polygon, its first corner `radius` toward `toward` (zero: the plane's own x), as worker/polygon.py.
func polygon_geometry(center: Vector3, normal: Vector3, radius: float, sides: int, toward := Vector3.ZERO) -> Dictionary:
	var basis: Array = Geo.plane_basis(normal)   # pure: works with no Main (T88 step 3)
	var x: Vector3 = toward - normal * (toward.dot(normal) / normal.length_squared())
	if x.length() > 1e-6: basis = [x.normalized(), normal.cross(x).normalized()]
	var pts := PackedVector3Array()
	var tris := PackedVector3Array()
	var lines := PackedVector3Array()
	for i in sides:
		var angle := 2.0 * PI * i / sides
		pts.append(center + radius * (basis[0] * cos(angle) + basis[1] * sin(angle)))
	for i in sides:
		var a := pts[i]; var b := pts[(i + 1) % sides]
		lines.append_array(PackedVector3Array([a, b]))
	for i in range(1, sides - 1):
		tris.append_array(PackedVector3Array([pts[0], pts[i], pts[i + 1]]))
	return {"pts": pts, "tris": tris, "lines": lines}


func drop_draft(oid: String) -> void:
	if pres.drafts.has(oid):
		pres.drafts[oid].queue_free(); pres.drafts.erase(oid)


func rebuild_rect_drafts(ops: Array, used: Dictionary) -> void:
	"""After an open: every rectangle's data, and a draft for those not yet pushed out."""
	for op in ops:
		if op.type in ["line", "arc"]:
			if not loose_lines.has(op.id): register_line(op)
			if used.has(op.id): drop_draft(op.id)
			continue
		if op["type"] in ["rect", "circle", "polygon"]:
			if used.has(op["id"]):
				register_rect(op); drop_draft(op["id"])
			elif not pres.drafts.has(op["id"]):
				register_rect(op)
	_refresh_loop_drafts()


func forget_op(op: Dictionary, ops: Array, used: Dictionary) -> void:
	"""The document dropped an op (undo, rejection): take away what it drew. `used`: rectangles still pushed out."""
	var oid: String = op["id"]
	pres.waves.end_wave(oid)
	drop_draft(oid)
	if op.type in ["line", "arc"]:
		loose_lines.erase(oid); rects.erase(oid); drop_draft("line:" + oid)
		_refresh_loop_drafts()
	elif op["type"] in ["rect", "circle", "polygon"]:
		rects.erase(oid)
	elif op["type"] in ["mirror", "move"]:
		for nid in op.get("new_ids", []):
			pres.body_tris.erase(nid); pres.body_verts.erase(nid); pres.body_edges.erase(nid)
	elif op["type"] in ["push_pull", "new_board"]:
		if op["type"] == "new_board" and op.has("body"):
			pres.body_tris.erase(op["body"]); pres.body_verts.erase(op["body"]); pres.body_edges.erase(op["body"])
		var rid: String = op["target"].get("rect", "")
		if rid != "" and not op["target"].has("region"):
			for r in ops:
				if r["id"] == rid and not used.has(rid):
					rects.erase(rid); register_rect(r)
					_refresh_loop_drafts()


func drop_confirmed_drafts(used: Dictionary) -> void:
	"""FreeCAD answered: drafts give way to its boards (a rejected one stays until its red wave is done)."""
	for k in pres.drafts.keys():
		var w = pres.waves.op_waves.get(k)
		if w != null and w["state"] == "rejected": continue
		if k.begins_with("line:"): continue
		if not rects.has(k) or used.has(k):
			pres.drafts[k].queue_free(); pres.drafts.erase(k)
