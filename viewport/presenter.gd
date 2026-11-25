extends Node
## Geometry presentation (A33b, T41), `m.pres`: what the model looks like on screen.
## It owns each board's triangles, corners, edges and cuts (what picking and snapping read), the drafts and the
## rectangles drawn on faces, the confirmed board nodes built from FreeCAD's mesh files, the remembered confirmed
## states (undo shows at once), the confirmation waves, and the highlights that show selection and context (the
## selection, ghosting outside an entered assembly, hidden boards, the mirror plane, linked copies), drawn from
## what selection.gd says. main.gd routes the document's signals here and keeps the rejection bookkeeping; this
## builds the meshes, line strips and pick collisions, using the window's materials.

signal boards_read(data: Array, dir: String)   # bodies.json read, before building: main updates selection and wood
signal wave_rejected_done(oid: String)        # a red wave has played out: main removes the op (and its dependents)

const Regions := preload("res://regions.gd")
const Geo := preload("res://tool_geometry.gd")
const LINE_SHADER := preload("res://line.gdshader")
const LINE_PX := 1.5
const WAVE := preload("res://confirm_wave.gdshader")
const WAVE_LINES := preload("res://confirm_wave_lines.gdshader")
const WOOD := preload("res://wood.gdshader")
# Rendering constants (T88: moved from main.gd, which keeps the old names)
const DEFAULT_BASE := Color(0.82, 0.80, 0.76)   # a board's colour before FreeCAD says (tools start waves with it)
const SNAP_COLORS := {"endpoint": Color(0.1, 0.65, 0.1), "midpoint": Color(0.1, 0.7, 0.8), "on edge": Color(0.85, 0.15, 0.15),
					  "on face": Color(0.2, 0.35, 0.95), "back face": Color(0.2, 0.35, 0.95), "face behind": Color(0.2, 0.35, 0.95)}
const AXIS_COLORS := [Color(0.85, 0.15, 0.15, 0.16), Color(0.15, 0.65, 0.2, 0.16), Color(0.2, 0.35, 0.95, 0.16)]

var m                               # main.gd
var sel                             # selection.gd: what to highlight, ghost and hide

var body_tris := {}                 # body id -> PackedVector3Array (model mm, 3 per tri)
var body_verts := {}                # body id -> PackedVector3Array (unique corners)
var body_edges := {}                # body id -> feature edge segments (model mm)
var body_cuts := {}                 # body id -> [{op, kind, lo, hi}] from FreeCAD: holes and added pieces
var rects := {}                     # profile id (rectangle or circle) -> {"tris","n","on","pts"}
var loose_lines := {}             # line id -> {a, b, n, on}; rebuilt from journal
var drafts := {}                    # op id -> Node3D
var stock_frames := {}              # body id -> rectangular stock frame from bodies.json (plane fits, I40)


var _selection_box: Panel
var _face: MeshInstance3D
var draft_tests := DraftTestRecorder.new()


class DraftTestRecorder:
	var reject_next := false
	var bounds := {}

	func filter(op: Dictionary) -> void:
		if reject_next and op.target.has("rect"):
			op.target = {"rect": "r_missing"}
			reject_next = false

	func record(id: String, tris: PackedVector3Array) -> void:
		var lo := Vector3(INF, INF, INF)
		var hi := -lo
		for point in tris:
			lo = lo.min(point)
			hi = hi.max(point)
		bounds[id] = [Geo.arr3(lo), Geo.arr3(hi)]


var guides: MeshInstance3D


func draw_guides(ref: Vector3, axis: int, plane_axis: int) -> void:
	if guides == null:
		guides = MeshInstance3D.new(); add_child(guides)
	guides.mesh = null
	var segs := PackedVector3Array()
	var col := Color(0.4, 0.4, 0.4)
	if axis >= 0:
		var v := Geo.axis_vector(axis)
		var k := -3000.0
		while k < 3000.0:                                # dotted line along the axis through the grab point
			segs.append_array([ref + v * k, ref + v * (k + 14.0)])
			k += 30.0
		col = [Color(0.85, 0.1, 0.1), Color(0.1, 0.6, 0.1), Color(0.1, 0.25, 0.9)][axis]
	if plane_axis >= 0:
		var u := Geo.axis_vector((plane_axis + 1) % 3) * 600.0
		var w := Geo.axis_vector((plane_axis + 2) % 3) * 600.0
		for k in range(-6, 7):
			segs.append_array([ref + u * (k / 6.0) - w, ref + u * (k / 6.0) + w, ref + w * (k / 6.0) - u, ref + w * (k / 6.0) + u])
		col = [Color(0.85, 0.1, 0.1, 0.5), Color(0.1, 0.6, 0.1, 0.5), Color(0.1, 0.25, 0.9, 0.5)][plane_axis]
	if not segs.is_empty():
		guides.mesh = line_mesh(segs, col)


func clear_guides() -> void:
	if guides: guides.mesh = null


func mirror_preview(tris: PackedVector3Array, corners: PackedVector3Array, axis := -1) -> void:
	var plane := m.mat_plane.duplicate() as StandardMaterial3D
	var edge_color := Color(0.6, 0.2, 0.45)
	plane.albedo_color = Color(0.85, 0.35, 0.6, 0.3)
	if axis >= 0:
		plane.albedo_color = AXIS_COLORS[axis]
		edge_color = AXIS_COLORS[axis]
		edge_color.a = 1.0
		edge_color = edge_color.darkened(0.2)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in [0, 1, 2, 0, 2, 3]: st.add_vertex(Geo.m2g(corners[i]))
	var mesh := tri_mesh(tris, m.mat_draft)
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, st.commit_to_arrays())
	mesh.surface_set_material(1, plane)
	m.overlay.mesh = mesh
	var segments := Geo.feature_edges(tris)
	for i in 4:
		segments.append(corners[i])
		segments.append(corners[(i + 1) % 4])
	m.overlay_lines.mesh = line_mesh(segments, edge_color)


func face_highlight(tris: PackedVector3Array) -> void:
	if not is_instance_valid(_face):
		_face = MeshInstance3D.new()
		add_child(_face)
	_face.mesh = null if tris.is_empty() else tri_mesh(tris, m.mat_hover)


func clear_face_highlight() -> void:
	if is_instance_valid(_face): _face.mesh = null


func present_draft(op: Dictionary, pieces: Array, wave: Dictionary) -> void:
	var root := Node3D.new()
	m.drafts_root.add_child(root)
	drafts[op.id] = root
	for piece in pieces:
		var tris: PackedVector3Array = piece.tris
		var surface := MeshInstance3D.new()
		surface.mesh = tri_mesh(tris, m.mat_cut if piece.style == "cut" else m.mat_draft)
		var segments := Geo.feature_edges(tris)
		surface.add_child(lines(segments, piece.line_color))
		root.add_child(surface)
		var id: String = piece.body_id
		if id.is_empty(): continue
		add_collision(surface, "body_id", id)
		body_tris[id] = tris
		body_verts[id] = Geo.unique_verts(tris)
		body_edges[id] = segments
		if m.test_mode: draft_tests.record(id, tris)
		if piece.replace:
			for old in m.bodies_root.find_children(id, "MeshInstance3D", true, false):
				old.visible = false

	if op.type == "push_pull" and not op.target.has("region"): drop_draft(op.target.get("rect", ""))
	var bodies: Array = wave.bodies
	begin_wave(op.id, wave.origin, wave.tris, wave.is_new, bodies[0] if op.type == "push_pull" or op.has("cut") else bodies)
	if wave.attach == "drafts":
		for surface in root.get_children():
			attach_wave(op.id, surface, surface.get_child(0), DEFAULT_BASE)
	else:
		for id in wave.bodies:
			for surface in m.bodies_root.find_children(id, "MeshInstance3D", true, false):
				attach_wave(op.id, surface, surface.get_meta("edges"), base_of(surface))


var _line_mats := {}          # [color, width, bias] -> ShaderMaterial, shared


func _line_mat(color: Color, width_pt: float, bias: float) -> ShaderMaterial:
	var key := [color, width_pt, bias]
	if not _line_mats.has(key):
		var material := ShaderMaterial.new()
		material.shader = LINE_SHADER
		material.set_shader_parameter("color", color)
		material.set_shader_parameter("width_px", width_pt * m.line_scale)
		material.set_shader_parameter("bias", bias)
		_line_mats[key] = material
	return _line_mats[key]


## Line segments (pairs of model-space points) as anti-aliased strips a fixed width on screen (line.gdshader).
func lines(segs_m: PackedVector3Array, color: Color, width_pt := LINE_PX, bias := -1.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	if segs_m.size() < 2:
		return mi
	mi.mesh = line_mesh(segs_m, color, width_pt, bias)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.extra_cull_margin = 0.05      # the strip is a little wider than its segment on screen
	return mi

func line_mesh(segs_m: PackedVector3Array, color: Color, width_pt := LINE_PX, bias := -1.0) -> ArrayMesh:
	var n := segs_m.size() / 2
	var verts := PackedVector3Array(); verts.resize(n * 4)
	var other := PackedFloat32Array(); other.resize(n * 16)
	var uvs := PackedVector2Array(); uvs.resize(n * 4)
	var idx := PackedInt32Array(); idx.resize(n * 6)
	for i in n:
		var a := Geo.m2g(segs_m[2 * i]); var b := Geo.m2g(segs_m[2 * i + 1])
		var v := 4 * i
		verts[v] = a; verts[v + 1] = a; verts[v + 2] = b; verts[v + 3] = b
		for k in 4:
			var o: Vector3 = b if k < 2 else a
			other[(v + k) * 4] = o.x; other[(v + k) * 4 + 1] = o.y; other[(v + k) * 4 + 2] = o.z; other[(v + k) * 4 + 3] = 0.0
		uvs[v] = Vector2(0, -1); uvs[v + 1] = Vector2(0, 1); uvs[v + 2] = Vector2(1, -1); uvs[v + 3] = Vector2(1, 1)
		var t := 6 * i
		idx[t] = v; idx[t + 1] = v + 1; idx[t + 2] = v + 2; idx[t + 3] = v + 1; idx[t + 4] = v + 3; idx[t + 5] = v + 2
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = verts
	arr[Mesh.ARRAY_CUSTOM0] = other
	arr[Mesh.ARRAY_TEX_UV] = uvs
	arr[Mesh.ARRAY_INDEX] = idx
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr, [], {},
		Mesh.ARRAY_CUSTOM_RGBA_FLOAT << Mesh.ARRAY_FORMAT_CUSTOM0_SHIFT)
	mesh.surface_set_material(0, _line_mat(color, width_pt, m.overlay_bias if bias < 0.0 else bias))
	return mesh


func tri_mesh(tris_m: PackedVector3Array, mat: Material) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var c := Vector3.ZERO
	for p in tris_m:
		c += p
	c /= maxf(1.0, tris_m.size())
	for i in range(0, tris_m.size(), 3):
		var a := Geo.m2g(tris_m[i]); var b := Geo.m2g(tris_m[i + 1]); var d := Geo.m2g(tris_m[i + 2])
		var n := (b - a).cross(d - a).normalized()
		var mid := (a + b + d) / 3.0
		if n.dot(mid - Geo.m2g(c)) < 0: n = -n
		if (b - a).cross(d - a).dot(n) > 0:   # Godot front faces are clockwise
			var t := b; b = d; d = t
		for p in [a, b, d]:
			st.set_normal(n); st.add_vertex(p)
	var mesh := st.commit()
	mesh.surface_set_material(0, mat)
	return mesh


func add_collision(mi: MeshInstance3D, meta_key: String, meta_val: String) -> void:
	mi.create_trimesh_collision()
	for c in mi.get_children():
		if c is StaticBody3D:
			c.set_meta(meta_key, meta_val)
			c.collision_layer = 2 if meta_key == "rect_id" else 1
			for s in c.get_children():
				if s is CollisionShape3D and s.shape is ConcavePolygonShape3D:
					s.shape.backface_collision = true


func show_marker(p: Dictionary) -> void:
	m.marker.visible = p.get("hit", false)
	if m.marker.visible:
		m.marker.position = Geo.m2g(p["point"])
		var col: Color = SNAP_COLORS.get(p.get("snap", ""), Color(0.35, 0.35, 0.4))
		(m.marker.mesh.material as StandardMaterial3D).albedo_color = col


func unit_tris(unit: Dictionary) -> PackedVector3Array:
	var t := PackedVector3Array()
	for b in unit.get("bodies", []): t.append_array(body_tris.get(b, PackedVector3Array()))
	return t


func selection_box(start: Vector2, finish: Vector2) -> void:
	if not is_instance_valid(_selection_box):
		_selection_box = Panel.new()
		_selection_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(_selection_box)
	var style := StyleBoxFlat.new()
	var color := Color(0.2, 0.45, 0.95) if finish.x >= start.x else Color(0.1, 0.65, 0.4)
	style.bg_color = Color(color, 0.12)
	style.border_color = color
	style.set_border_width_all(1)
	_selection_box.add_theme_stylebox_override("panel", style)
	var rect := Rect2(start, finish - start).abs()
	_selection_box.position = rect.position; _selection_box.size = rect.size


func clear_selection_box() -> void:
	if is_instance_valid(_selection_box): _selection_box.queue_free()
	_selection_box = null


func reset() -> void:
	"""Another model: nothing of the old one stays on screen or in the caches."""
	clear_face_highlight()
	for oid in op_waves.keys(): end_wave(oid)
	for k in drafts: drafts[k].queue_free()
	drafts.clear(); rects.clear(); loose_lines.clear()
	for c in m.bodies_root.get_children(): m.bodies_root.remove_child(c)
	for f in _boards: _boards[f]["node"].queue_free()
	_boards.clear(); _states.clear(); _state_lru.clear(); shown_key = ""
	body_tris = {}; body_verts = {}; body_edges = {}; body_cuts = {}; stock_frames = {}


# ---------------- rectangles drawn on faces and in space ----------------

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
	var node := lines(segments, Color(0.1, 0.2, 0.6))
	m.drafts_root.add_child(node)
	drafts["line:" + op.id] = node
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
		if not drafts.has(rid): continue
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
	mi.mesh = tri_mesh(all_tris, m.mat_rect)
	m.drafts_root.add_child(mi)
	drafts["line:loops"] = mi


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
	else:
		var corner: Array = op.get("corner", [0, 0])
		var o2: Vector3 = origin + b[0] * float(corner[0]) + b[1] * float(corner[1])
		pts = Geo.rect_points(o2, b[0], b[1], op["size"][0], op["size"][1])
		tris = PackedVector3Array([pts[0], pts[1], pts[2], pts[0], pts[2], pts[3]])
		lines = PackedVector3Array([pts[0], pts[1], pts[1], pts[2], pts[2], pts[3], pts[3], pts[0]])
	rects[op["id"]] = {"tris": tris, "n": n, "on": src.get("body", "") if pl.has("on") else "", "pts": pts, "kind": op["type"]}
	var mi := MeshInstance3D.new()
	mi.mesh = tri_mesh(tris, m.mat_rect)
	mi.add_child(self.lines(lines, Color(0.1, 0.2, 0.6)))
	m.drafts_root.add_child(mi)
	add_collision(mi, "rect_id", op["id"])
	drafts[op["id"]] = mi


# A viewport approximation only. The op contains the radius; FreeCAD keeps an exact sketch circle.
const CIRCLE_SEGMENTS := 64

func circle_geometry(center: Vector3, normal: Vector3, radius: float) -> Dictionary:
	var basis: Array = Geo.plane_basis(normal)   # pure: works with no Main (T88 step 3)
	var pts := PackedVector3Array()
	var tris := PackedVector3Array()
	var lines := PackedVector3Array()
	for i in CIRCLE_SEGMENTS:
		var angle := 2.0 * PI * i / CIRCLE_SEGMENTS
		pts.append(center + radius * (basis[0] * cos(angle) + basis[1] * sin(angle)))
	for i in CIRCLE_SEGMENTS:
		var a := pts[i]; var b := pts[(i + 1) % CIRCLE_SEGMENTS]
		lines.append_array(PackedVector3Array([a, b]))
	for i in range(1, CIRCLE_SEGMENTS - 1):
		tris.append_array(PackedVector3Array([pts[0], pts[i], pts[i + 1]]))
	return {"pts": pts, "tris": tris, "lines": lines}


func drop_draft(oid: String) -> void:
	if drafts.has(oid):
		drafts[oid].queue_free(); drafts.erase(oid)


func rebuild_rect_drafts(ops: Array, used: Dictionary) -> void:
	"""After an open: every rectangle's data, and a draft for those not yet pushed out."""
	for op in ops:
		if op.type in ["line", "arc"]:
			if not loose_lines.has(op.id): register_line(op)
			if used.has(op.id): drop_draft(op.id)
			continue
		if op["type"] in ["rect", "circle"]:
			if used.has(op["id"]):
				register_rect(op); drop_draft(op["id"])
			elif not drafts.has(op["id"]):
				register_rect(op)
	_refresh_loop_drafts()


func forget_op(op: Dictionary, ops: Array, used: Dictionary) -> void:
	"""The document dropped an op (undo, rejection): take away what it drew. `used`: rectangles still pushed out."""
	var oid: String = op["id"]
	end_wave(oid)
	drop_draft(oid)
	if op.type in ["line", "arc"]:
		loose_lines.erase(oid); rects.erase(oid); drop_draft("line:" + oid)
		_refresh_loop_drafts()
	elif op["type"] in ["rect", "circle"]:
		rects.erase(oid)
	elif op["type"] in ["mirror", "move"]:
		for nid in op.get("new_ids", []):
			body_tris.erase(nid); body_verts.erase(nid); body_edges.erase(nid)
	elif op["type"] == "push_pull":
		if op.has("body"):
			body_tris.erase(op["body"]); body_verts.erase(op["body"]); body_edges.erase(op["body"])
		var rid: String = op["target"].get("rect", "")
		if rid != "" and not op["target"].has("region"):
			for r in ops:
				if r["id"] == rid and not used.has(rid):
					rects.erase(rid); register_rect(r)
					_refresh_loop_drafts()


func drop_confirmed_drafts(used: Dictionary) -> void:
	"""FreeCAD answered: drafts give way to its boards (a rejected one stays until its red wave is done)."""
	for k in drafts.keys():
		var w = op_waves.get(k)
		if w != null and w["state"] == "rejected": continue
		if k.begins_with("line:"): continue
		if not rects.has(k) or used.has(k):
			drafts[k].queue_free(); drafts.erase(k)


# ---------------- confirmed boards (T3) ----------------
# Each board FreeCAD confirmed is a node built from its own file (worker: meshes/<board>-<key>.bin: triangles,
# normals, and FreeCAD's exact edges and corners). A reply builds only the files it hasn't seen; every other
# board stays on screen untouched. Nodes are shared by the remembered states below.
const M2G_BASIS := Basis(Vector3(1, 0, 0), Vector3(0, 0, -1), Vector3(0, 1, 0))     # model Z-up -> Godot Y-up
var _boards := {}             # mesh file -> {"node", "bid", "tris", "verts", "edges"}


func show_confirmed(dir: String, key: String) -> void:
	"""FreeCAD's state for these ops (key): on screen, unless it already is (an undo shown from the cache)."""
	if key != shown_key or not _states.has(key):
		apply_confirmed(dir, key)


func apply_confirmed(dir: String, key: String) -> void:
	var data = JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("bodies.json")))
	if typeof(data) != TYPE_ARRAY: return
	boards_read.emit(data, dir)
	var files := {}
	stock_frames = {}
	for b in data:
		if b.get("stock_frame") is Dictionary: stock_frames[b["id"]] = b["stock_frame"]
		var vkey := "%s|%s|%s|%s" % [b["mesh"], b.get("material", ""), b.get("grain", []), b.get("across", [])]
		files[b["id"]] = vkey                        # a repaint or a turned grain is a new look for the same mesh
		if not _boards.has(vkey):
			_boards[vkey] = _build_board(dir, b)
	_load_cuts(dir)
	_show_boards(files)
	_remember_state(key, files, data, dir)


func _build_board(dir: String, b: Dictionary) -> Dictionary:
	var bid: String = b["id"]
	var bytes := FileAccess.get_file_as_bytes(dir.path_join("meshes").path_join(b["mesh"]))
	var parts := []
	var off := 0
	for i in 4:                                      # tris, normals, edges, corners: Godot's own array format
		var size := 8 + int(bytes.decode_u32(off + 4)) * 12
		parts.append(bytes_to_var(bytes.slice(off, off + size)))
		off += size
	var tris: PackedVector3Array = parts[0]
	var mi := MeshInstance3D.new()
	mi.name = bid
	if not tris.is_empty():
		var arr := []
		arr.resize(Mesh.ARRAY_MAX)
		arr[Mesh.ARRAY_VERTEX] = Transform3D(M2G_BASIS * 0.001, Vector3.ZERO) * tris
		arr[Mesh.ARRAY_NORMAL] = Transform3D(M2G_BASIS, Vector3.ZERO) * (parts[1] as PackedVector3Array)
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
		var base := Color(b["color"][0], b["color"][1], b["color"][2]).linear_to_srgb()   # as glTF import did
		var wood: ShaderMaterial = m.appearance.wood_material(bid, b, base)
		if wood != null:
			mesh.surface_set_material(0, wood)
		else:
			var mat := StandardMaterial3D.new()
			mat.albedo_color = base
			mat.roughness = 0.85
			mesh.surface_set_material(0, mat)
		mi.mesh = mesh
		add_collision(mi, "body_id", bid)
	var edges: MeshInstance3D = lines(parts[2], Color(0.08, 0.08, 0.08))
	mi.add_child(edges)
	mi.set_meta("body_mesh", true); mi.set_meta("edges", edges)
	return {"node": mi, "bid": bid, "tris": tris, "verts": parts[3], "edges": parts[2]}


func _show_boards(files: Dictionary) -> void:
	"""Put exactly these boards (board id -> mesh file) on screen, keeping the ones already there."""
	var root: Node3D = m.bodies_root
	var want := {}
	for bid in files: want[_boards[files[bid]]["node"]] = files[bid]
	for c in root.get_children():
		if not want.has(c): root.remove_child(c)
	body_tris = {}; body_verts = {}; body_edges = {}
	for node in want:
		var e: Dictionary = _boards[want[node]]
		var bid: String = e["bid"]
		body_tris[bid] = e["tris"]; body_verts[bid] = e["verts"]; body_edges[bid] = e["edges"]
		if node.get_parent() == root: continue
		root.add_child(node)
		node.visible = true                          # a move hides the board's old spot until FreeCAD answers
		node.material_override = null                # a wave that ran on it earlier is over
		var edges: MeshInstance3D = node.get_meta("edges")
		edges.material_override = null
		for oid in op_waves:                         # a wave running for this board carries onto it
			if bid in op_waves[oid]["bodies"]:
				attach_wave(oid, node, edges, base_of(node))
	show_selection()                                 # the selected board may have a new shape
	var t = m.tools.get(m.tool)
	if t != null and not t.busy():                   # an idle tool's hover highlight is of the old shape
		m.overlay.mesh = null; m.overlay_lines.mesh = null
	apply_context()


# ---------------- confirmed states (T10) ----------------
# The last few model states FreeCAD confirmed (which board files they had). Undo shows the previous one at once,
# so you can keep undoing while FreeCAD catches up, even when it has to rebuild the whole model (its
# command-line program keeps only 20 undo steps). FreeCAD's answer then matches what's on screen: no reload.
const STATE_CACHE_MAX := 40
var _states := {}             # ops key -> {"files": board id -> mesh file, "cuts"}
var _state_lru: Array = []    # keys, oldest first
var shown_key := ""           # the confirmed state on screen
var predicted_undo := false   # the model on screen is a remembered state; FreeCAD is still catching up


func _remember_state(key: String, files: Dictionary, data: Array, dir: String) -> void:
	_states[key] = {"files": files, "cuts": body_cuts.duplicate(), "stock_frames": stock_frames.duplicate(), "boards": data.duplicate(true), "dir": dir}
	_state_lru.erase(key); _state_lru.append(key)
	shown_key = key
	var evicted := false
	while _state_lru.size() > STATE_CACHE_MAX:
		var old: String = _state_lru.pop_front()
		if old != shown_key: _states.erase(old); evicted = true
	if evicted: _free_unused_boards()


func _free_unused_boards() -> void:
	var used := {}
	for k in _states:
		for bid in _states[k]["files"]: used[_states[k]["files"][bid]] = true
	for f in _boards.keys():
		if not used.has(f) and _boards[f]["node"].get_parent() != m.bodies_root:
			_boards[f]["node"].queue_free()
			_boards.erase(f)


func show_state(key: String) -> bool:
	"""Put a remembered confirmed state back on screen (undo). False if it isn't remembered."""
	if not _states.has(key): return false
	if key == shown_key: return true
	var st: Dictionary = _states[key]
	boards_read.emit(st["boards"], st["dir"])
	body_cuts = st["cuts"].duplicate()
	stock_frames = st["stock_frames"].duplicate()
	_show_boards(st["files"])
	shown_key = key
	_state_lru.erase(key); _state_lru.append(key)
	return true


# ---------------- cuts: holes and added pieces, as FreeCAD reports them ----------------

func _load_cuts(dir: String) -> void:
	body_cuts = {}
	var path := dir.path_join("bodies.json")
	if not FileAccess.file_exists(path): return
	var data = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(data) != TYPE_ARRAY: return
	for b in data:
		var lst := []
		for c in b.get("cuts", []):
			lst.append({"op": c["op"], "kind": c["kind"],
				"lo": Vector3(c["lo"][0], c["lo"][1], c["lo"][2]), "hi": Vector3(c["hi"][0], c["hi"][1], c["hi"][2])})
		body_cuts[b["id"]] = lst


func cut_at(bid: String, pt: Vector3) -> Dictionary:
	"""The hole (or added piece) of a board under this point: its walls, floor or top."""
	var best := {}
	var best_vol := INF
	for c in body_cuts.get(bid, []):
		var lo: Vector3 = c["lo"] - Vector3.ONE * 0.3
		var hi: Vector3 = c["hi"] + Vector3.ONE * 0.3
		if pt.x >= lo.x and pt.y >= lo.y and pt.z >= lo.z and pt.x <= hi.x and pt.y <= hi.y and pt.z <= hi.z:
			var sz: Vector3 = c["hi"] - c["lo"]
			if sz.x * sz.y * sz.z < best_vol:                # the smallest one wins (a pin hole inside a dado)
				best = c
				best_vol = sz.x * sz.y * sz.z
	return best


static func _box_tris(lo: Vector3, hi: Vector3) -> PackedVector3Array:
	var c := [Vector3(lo.x, lo.y, lo.z), Vector3(hi.x, lo.y, lo.z), Vector3(hi.x, hi.y, lo.z), Vector3(lo.x, hi.y, lo.z),
		Vector3(lo.x, lo.y, hi.z), Vector3(hi.x, lo.y, hi.z), Vector3(hi.x, hi.y, hi.z), Vector3(lo.x, hi.y, hi.z)]
	var out := PackedVector3Array()
	for f in [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]:
		out.append_array([c[f[0]], c[f[1]], c[f[2]], c[f[0]], c[f[2]], c[f[3]]])
	return out


func cut_tris(bid: String, op_id: String) -> PackedVector3Array:
	var out := PackedVector3Array()
	for c in body_cuts.get(bid, []):
		if c["op"] == op_id: out.append_array(_box_tris(c["lo"], c["hi"]))
	return out


func base_of(mi: MeshInstance3D) -> Color:
	var mat = mi.mesh.surface_get_material(0)
	if mat is ShaderMaterial and mat.shader == WOOD: return mat.get_shader_parameter("base_color")
	return mat.albedo_color if mat is StandardMaterial3D else DEFAULT_BASE


# ---------------- operation wave (W01–W09) ----------------
const HOLD := 0.6          # fraction of the forward wave that runs before FreeCAD must have answered
const REJECT_DUR := 0.6

var op_waves := {}         # op id -> wave state
var trace_wave := ""       # test hook: record this op's front over time
var trace_rows: Array[String] = []


func begin_wave(oid: String, origin_m: Vector3, tris: PackedVector3Array, is_new: bool, body) -> void:
	var og := Geo.m2g(origin_m)
	var reach := 0.0
	for p in tris:
		reach = maxf(reach, Geo.m2g(p).distance_to(og))
	var dur := clampf(reach / 0.7, 0.5, 1.0)
	op_waves[oid] = {"og": og, "reach": reach, "dur": dur, "tn": 0.0,
					 "p": 0.0, "v": 1.0 / dur, "v1": 1.0 / dur,   # progress (0..1), velocity, and the first smoothing stage
					 "hraw": 0.0, "held": 0.0, "t0": 0.0, "bphase": 0.0,
					 "rt": -1.0, "state": "pending", "new": is_new, "body": body if body is String else "",
					 "bodies": [body] if body is String else body, "links": []}


func attach_wave(oid: String, mi: MeshInstance3D, edges: MeshInstance3D, base: Color) -> void:
	var w: Dictionary = op_waves[oid]
	var draft: StandardMaterial3D = m.mat_draft
	var sm := ShaderMaterial.new(); sm.shader = WAVE
	sm.set_shader_parameter("base_color", Color(base.r, base.g, base.b))
	sm.set_shader_parameter("draft_color", Color(draft.albedo_color.r, draft.albedo_color.g, draft.albedo_color.b))
	sm.set_shader_parameter("draft_alpha", draft.albedo_color.a)
	var lm := ShaderMaterial.new(); lm.shader = WAVE_LINES
	lm.set_shader_parameter("width_px", LINE_PX * m.line_scale)
	lm.set_shader_parameter("bias", m.overlay_bias)
	for mat in [sm, lm]:
		mat.set_shader_parameter("origin", w["og"])
		mat.set_shader_parameter("reach", w["reach"])
		mat.set_shader_parameter("duration", w["dur"])
		mat.set_shader_parameter("reject_dur", REJECT_DUR)
		mat.set_shader_parameter("from_draft", 1.0 if w["new"] else 0.0)
	mi.material_override = sm
	if edges != null: edges.material_override = lm
	w["links"].append([mi, edges, sm, lm])
	_push_params(w)


func _push_params(w: Dictionary) -> void:
	var keep := []
	for l in w["links"]:
		if not is_instance_valid(l[0]): continue
		keep.append(l)
		for mat in [l[2], l[3]]:
			mat.set_shader_parameter("t", w["p"] * w["dur"])
			mat.set_shader_parameter("tn", w["tn"])
			mat.set_shader_parameter("reject_t", -1.0 if w["rt"] < 0.0 else smoothstep(0.0, 1.0, w["rt"] / REJECT_DUR) * REJECT_DUR)
			mat.set_shader_parameter("held", w["held"])
			mat.set_shader_parameter("bphase", w["bphase"])
	w["links"] = keep


func end_wave(oid: String) -> void:
	if not op_waves.has(oid): return
	for l in op_waves[oid]["links"]:
		if is_instance_valid(l[0]): l[0].material_override = null
		if is_instance_valid(l[1]): l[1].material_override = null
	op_waves.erase(oid)


const SLOW := 0.35         # progress distance over which the front slows into the hold (longer = gentler)
const TAU := 0.12          # seconds, per smoothing stage
const TAU_UP := 0.20       # seconds, per stage, when speeding back up after FreeCAD accepts
const LEAD := 0.10         # seconds of look-ahead in the controller (cancels overshoot from smoothing)
const AMP_COMP := 1.11     # smoothing shrinks the swing about 10%; aim wider so the front really spans BREATH_LO..HOLD
const BREATH_W := 2.4      # rad/s of the breathing (one glide back and forth = 2.6 s)
const BREATH_LO := 0.3     # breathing glides between BREATH_LO and HOLD of the full travel


func step_waves(delta: float) -> void:
	"""One frame of every wave: run, ease into the hold, breathe while FreeCAD works, finish or go red."""
	for oid in op_waves.keys():
		if not op_waves.has(oid): continue          # removed this frame along with a rejection it built on
		var w: Dictionary = op_waves[oid]
		var v0: float = 1.0 / w["dur"]
		w["tn"] += delta
		var parking: bool = w["state"] == "pending" or (w["state"] == "rejected" and w["rt"] < 0.0)
		var breathing: bool = w["bphase"] > 0.0
		# where the front wants to be: run free, ease to HOLD, then glide between BREATH_LO and HOLD
		var vdes := v0
		if parking:
			var goal: float = HOLD
			if w["state"] == "pending" and breathing:
				var mid := (HOLD + BREATH_LO) * 0.5
				goal = mid + (HOLD - mid) * AMP_COMP * cos(w["bphase"])   # zero slope at the start

			elif w["state"] == "rejected" and breathing:
				goal = w["p"]                                       # rejected mid-breath: settle where it is
			# aim from slightly ahead (LEAD) so the smoothing delay doesn't make it overshoot
			vdes = v0 * clampf((goal - (w["p"] + LEAD * w["v"])) / SLOW, -1.0, 1.0)
		var tau := TAU_UP if w["state"] == "ok" else TAU
		# two smoothing stages: v1 follows the command, v follows v1.
		# speed AND acceleration stay continuous, so there's no corner (no thud) anywhere.
		var k := 1.0 - exp(-delta / tau)
		w["v1"] += (vdes - w["v1"]) * k
		w["v"] += (w["v1"] - w["v"]) * k
		w["p"] += w["v"] * delta
		var stopped: bool = parking and absf(w["v"]) < 0.15 * v0
		if w["state"] == "pending" and (breathing or stopped):
			w["bphase"] += BREATH_W * delta                         # phase clock starts once the front has settled
		if w["state"] == "rejected":
			if w["rt"] >= 0.0 or stopped:
				w["rt"] = maxf(w["rt"], 0.0) + delta     # red wave eases in/out (smoothstep in _push_params)
		_push_params(w)
		if trace_wave != "" and oid == trace_wave:
			trace_rows.append("%.4f,%.6f,%.6f,%.4f,%s" % [w["tn"], w["p"], w["v"], w["reach"], w["state"]])
		if w["state"] == "ok" and w["p"] > 1.25:
			end_wave(oid)
		elif w["state"] == "rejected" and w["rt"] > REJECT_DUR + 0.1:
			wave_rejected_done.emit(oid)            # main removes it, with what built on it


# ---------------- selection and context, drawn (what selection.gd says) ----------------
var plane_node: MeshInstance3D      # the mirror plane, shown inside an entered mirror group (A11b)
var _sel_overlay: MeshInstance3D
var _sibling_overlay: MeshInstance3D
var _sibling_key := ""              # the siblings now tinted ("-": out of date, draw again)
var mat_ghost: StandardMaterial3D
var mat_hidden_ghost: StandardMaterial3D


func _overlay_node() -> MeshInstance3D:
	var mi := MeshInstance3D.new(); m.add_child(mi)
	return mi


func apply_context() -> void:
	"""Grey out, and make unpickable, every board outside the one you're in. Hidden boards (T28) are left out
	altogether, or shown ghosted (and pickable, to unhide them) with View > Hidden geometry."""
	if mat_ghost == null:
		mat_ghost = StandardMaterial3D.new()
		mat_ghost.albedo_color = Color(0.75, 0.75, 0.78, 0.35)
		mat_ghost.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	if mat_hidden_ghost == null:
		mat_hidden_ghost = StandardMaterial3D.new()
		mat_hidden_ghost.albedo_color = Color(0.55, 0.6, 0.7, 0.25)
		mat_hidden_ghost.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	sel.refresh_hidden()
	for node in m.bodies_root.get_children():
		if not node.has_meta("body_mesh"): continue
		var bid := String(node.name)
		var hidden: bool = sel.body_hidden.has(bid)
		if sel.body_deleted.has(bid) or (hidden and not sel.show_hidden):
			node.visible = false; node.set_meta("ss_hidden", true)
		elif node.get_meta("ss_hidden", false):
			node.visible = true; node.set_meta("ss_hidden", false)
		var inside: bool = not sel.body_deleted.has(bid) and sel.in_context(bid) and (not hidden or sel.show_hidden)
		var comp_sib: bool = not sel.body_deleted.has(bid) and sel.is_context_sibling(bid) and (not hidden or sel.show_hidden)
		if inside:
			node.material_override = mat_hidden_ghost if hidden else null
		elif comp_sib:
			node.material_override = m.mat_sibling
		else:
			node.material_override = mat_ghost
		var edges: MeshInstance3D = node.get_meta("edges")
		edges.visible = inside or comp_sib
		for c in node.get_children():
			if c is StaticBody3D: c.collision_layer = 1 if inside else 0
	for collider in m.drafts_root.find_children("*", "StaticBody3D", true, false):
		var bid := String(collider.get_meta("body_id", ""))
		if sel.body_deleted.has(bid):
			collider.set_meta("ss_deleted", true)
			collider.collision_layer = 0
			collider.get_parent().visible = false
		elif collider.get_meta("ss_deleted", false):
			collider.remove_meta("ss_deleted")
			collider.collision_layer = 1
			collider.get_parent().visible = true
	show_mirror_plane()


func show_mirror_plane() -> void:
	"""Inside a mirror group: its plane, as a soft sheet a little bigger than the pair."""
	if plane_node == null: plane_node = _overlay_node()
	plane_node.mesh = null
	var plane: Array = sel.mirror_plane_of_context()
	if plane.is_empty(): return
	var lo := Vector3(INF, INF, INF); var hi := -lo
	for b in sel.members_of(sel.context_assembly()):
		for q in body_tris.get(b, PackedVector3Array()):
			lo = lo.min(q); hi = hi.max(q)
	var p0: Vector3 = plane[0]; var n: Vector3 = plane[1]
	var basis: Array = Geo.plane_basis(n)
	var c := (lo + hi) * 0.5
	c -= n * (c - p0).dot(n)                       # the middle of the pair, on the plane
	var r := maxf((hi - lo).length() * 0.6, 50.0)
	var u: Vector3 = basis[0] * r; var v: Vector3 = basis[1] * r
	var quad := PackedVector3Array()
	for q in [c - u - v, c + u - v, c + u + v, c - u - v, c + u + v, c - u + v]: quad.append(q)
	plane_node.mesh = tri_mesh(quad, m.mat_plane)


func show_selection() -> void:
	if _sel_overlay == null: _sel_overlay = _overlay_node()
	var t := PackedVector3Array()
	for b in sel.selection: t.append_array(body_tris.get(b, PackedVector3Array()))
	_sel_overlay.mesh = tri_mesh(t, m.mat_selected) if not t.is_empty() else null


func show_siblings(sib: Array) -> void:
	"""Linked copies of the board you're pointing at, tinted (T12)."""
	var key := ",".join(sib)
	if key == _sibling_key: return
	_sibling_key = key
	if _sibling_overlay == null: _sibling_overlay = _overlay_node()
	_sibling_overlay.mesh = null
	var tris := PackedVector3Array()
	for b in sib: tris.append_array(body_tris.get(b, PackedVector3Array()))
	if not tris.is_empty():
		_sibling_overlay.mesh = tri_mesh(tris, m.mat_sibling)


func forget_siblings() -> void:
	_sibling_key = "-"
