extends Node
## Geometry presentation (A33b, T41), `m.pres`: what the model looks like on screen.
## It owns each board's triangles, corners, edges and cuts (what picking and snapping read), the drafts, the
## confirmed board nodes built from FreeCAD's mesh files, the remembered confirmed states (undo shows at once), and
## holds `profiles` (profiles.gd, drawn rectangles, circles, polygons, lines and arcs), `waves` (waves.gd,
## confirmation waves) and `selection_view` (selection_view.gd, selection/context/sibling highlights drawn from what
## selection.gd says). main.gd routes the document's signals here and keeps the rejection bookkeeping; this builds the
## meshes, line strips and pick collisions, using the window's materials.
##
## Also owns DEFAULT_BASE/SNAP_COLORS/AXIS_COLORS, unit_tris, selection_box / clear_selection_box,
## tri_mesh/line_mesh/lines/add_collision/show_marker, face_highlight, draw_guides/clear_guides, mirror_preview,
## present_draft, draft_tests (DraftTestRecorder, test mode only), and stock_frames. Reuses board nodes by mesh
## filename + material/grain key and caches up to 40 confirmed states (eviction must never become history deletion).
## `_build_board` reads meshes/<board>-<key>.bin (change together with worker/export.py:board_mesh_file).
## Entry points: apply_confirmed, show_confirmed, show_state, forget_op, register_rect, register_line, lines_on,
## drawn_region, circle_geometry, present_draft, tri_mesh, line_mesh, lines, add_collision, face_highlight, begin_wave,
## step_waves, apply_context, show_selection, show_siblings, forget_siblings, reset.

signal boards_read(data: Array, dir: String)   # bodies.json read, before building: main updates selection and wood
signal wave_rejected_done(oid: String)        # a red wave has played out: main removes the op (and its dependents)

const Geo := preload("res://tool_geometry.gd")
const Profiles := preload("res://profiles.gd")
const Waves := preload("res://waves.gd")
const SelectionView := preload("res://selection_view.gd")
const LINE_SHADER := preload("res://line.gdshader")
const LINE_PX := 1.5
const CIRCLE_SEGMENTS := Profiles.CIRCLE_SEGMENTS
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

	if op.type in ["push_pull", "new_board"] and not op.target.has("region"): profiles.drop_draft(op.target.get("rect", ""))
	var bodies: Array = wave.bodies
	waves.begin_wave(op.id, wave.origin, wave.tris, wave.is_new, bodies[0] if op.type in ["push_pull", "new_board"] or op.has("cut") else bodies)
	if wave.attach == "drafts":
		for surface in root.get_children():
			waves.attach_wave(op.id, surface, surface.get_child(0), DEFAULT_BASE)
	else:
		for id in wave.bodies:
			for surface in m.bodies_root.find_children(id, "MeshInstance3D", true, false):
				waves.attach_wave(op.id, surface, surface.get_meta("edges"), base_of(surface))


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
	for oid in waves.op_waves.keys(): waves.end_wave(oid)
	for k in drafts: drafts[k].queue_free()
	drafts.clear(); rects.clear(); loose_lines.clear()
	for c in m.bodies_root.get_children(): m.bodies_root.remove_child(c)
	for f in _boards: _boards[f]["node"].queue_free()
	_boards.clear(); _states.clear(); _state_lru.clear(); shown_key = ""
	body_tris = {}; body_verts = {}; body_edges = {}; body_cuts = {}; stock_frames = {}


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
		for oid in waves.op_waves:                    # a wave running for this board carries onto it
			if bid in waves.op_waves[oid]["bodies"]:
				waves.attach_wave(oid, node, edges, base_of(node))
	selection_view.show_selection()                  # the selected board may have a new shape
	var t = m.tools.get(m.tool)
	if t != null and not t.busy():                   # an idle tool's hover highlight is of the old shape
		m.overlay.mesh = null; m.overlay_lines.mesh = null
	selection_view.apply_context()


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


# ---------------- drawn profiles (profiles.gd), operation wave (waves.gd) & selection/context (selection_view.gd) ----------------
var profiles: Profiles = Profiles.new(self)
var rects: Dictionary:
	get: return profiles.rects
var loose_lines: Dictionary:
	get: return profiles.loose_lines


static func arc_points(a: Vector3, mid: Vector3, b: Vector3) -> PackedVector3Array:
	return Profiles.arc_points(a, mid, b)


static func polyline_segments(points: PackedVector3Array) -> PackedVector3Array:
	return Profiles.polyline_segments(points)


func register_line(op: Dictionary) -> void:
	profiles.register_line(op)


func lines_on(body: String, normal: Vector3, point: Vector3) -> Array:
	return profiles.lines_on(body, normal, point)


func drawn_region(source: PackedVector3Array, body: String, normal: Vector3, point: Vector3) -> Dictionary:
	return profiles.drawn_region(source, body, normal, point)


func register_rect(op: Dictionary) -> void:
	profiles.register_rect(op)


func circle_geometry(center: Vector3, normal: Vector3, radius: float) -> Dictionary:
	return profiles.circle_geometry(center, normal, radius)


func polygon_geometry(center: Vector3, normal: Vector3, radius: float, sides: int, toward := Vector3.ZERO) -> Dictionary:
	return profiles.polygon_geometry(center, normal, radius, sides, toward)


func rebuild_rect_drafts(ops: Array, used: Dictionary) -> void:
	profiles.rebuild_rect_drafts(ops, used)


func forget_op(op: Dictionary, ops: Array, used: Dictionary) -> void:
	profiles.forget_op(op, ops, used)


func drop_confirmed_drafts(used: Dictionary) -> void:
	profiles.drop_confirmed_drafts(used)


var waves: Waves = Waves.new(self)
var op_waves: Dictionary:
	get: return waves.op_waves
var trace_wave: String:
	get: return waves.trace_wave
	set(v): waves.trace_wave = v
var trace_rows: Array[String]:
	get: return waves.trace_rows


func begin_wave(oid: String, origin_m: Vector3, tris: PackedVector3Array, is_new: bool, body) -> void:
	waves.begin_wave(oid, origin_m, tris, is_new, body)


func step_waves(delta: float) -> void:
	waves.step_waves(delta)


var selection_view: SelectionView = SelectionView.new(self)
var plane_node: MeshInstance3D:
	get: return selection_view.plane_node
var _sel_overlay: MeshInstance3D:
	get: return selection_view._sel_overlay
var mat_ghost: StandardMaterial3D:
	get: return selection_view.mat_ghost
var mat_hidden_ghost: StandardMaterial3D:
	get: return selection_view.mat_hidden_ghost


func apply_context() -> void:
	selection_view.apply_context()


func show_selection() -> void:
	selection_view.show_selection()


func show_siblings(sib: Array) -> void:
	selection_view.show_siblings(sib)


func forget_siblings() -> void:
	selection_view.forget_siblings()
