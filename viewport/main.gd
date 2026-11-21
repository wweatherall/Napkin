extends Node3D
## Shop Sketch: tool-first viewport. Records an op log; FreeCAD (worker) catches up.
## Model space = Z-up millimetres (what the op log uses). Godot space = Y-up metres.

const WorkerClient := preload("res://worker_client.gd")
const WAVE := preload("res://confirm_wave.gdshader")
const WAVE_LINES := preload("res://confirm_wave_lines.gdshader")
const LINE_SHADER := preload("res://line.gdshader")
const GRID := 10.0            # mm, grid snap step
const SNAP_PX := 14.0         # endpoint snap radius on screen

# ---------------- state ----------------
var ops: Array = []
var counters := {"r": 0, "b": 0, "pp": 0, "m": 0, "mv": 0}
var mirror_state := {}
var seq := 0
var in_flight := false
var dirty := false
var sent_at := {}             # seq -> msec
var last_sync_ms := 0
var tool := "rect"
var grid_snap := true
var new_board := true
var vcb := ""

var oplog_path := ""
var model_path := ""      # the FreeCAD file: the model itself (A21)
var undo_floor := 0       # ops before this came from a file FreeCAD has since edited
var out_dir := ""
var drawing_script := ""
var test_mode := false
var shots_dir := ""

var cam: Camera3D
var target := Vector3(0.25, 0.2, -0.15)
var yaw := deg_to_rad(-38.0)
var pitch := deg_to_rad(-26.0)
var dist := 2.0
var orbiting := false
var panning := false

var bodies_root: Node3D
var drafts_root: Node3D
var overlay: MeshInstance3D
var overlay_lines: MeshInstance3D
var marker: MeshInstance3D

var body_tris := {}           # body id -> PackedVector3Array (model mm, 3 per tri)
var body_verts := {}          # body id -> PackedVector3Array (unique corners)
var rects := {}               # rect id -> {"tris","n","on","pts"}
var drafts := {}              # op id -> Node3D
var rect_state := {}
var push_state := {}
var hover := {}
var body_cuts := {}      # body id -> [{op, kind, lo, hi}] from FreeCAD: holes and added pieces
var fx_points := {}           # op id -> model point where the operation ended (wave origin)
var confirmed_ids := {}       # op ids FreeCAD has already confirmed
var fx_test := false
var breath_test := false
var face_test := false
var orbit_test := false
var mirror_test := false
var move_test := false
var infer_test := false
var true_latency := false   # recording: hold each FreeCAD reply until the video clock has run FreeCAD's real time
var movie_clock := 0.0
var sent_clock := {}
var held_resp: Dictionary = {}
var heavy_test := false
var zfight_test := false
var hole_test := false
var line_test := false
var undo_test := false
var gesture_test := false
const OVERLAY_BIAS := 0.001   # overlays sit 0.1% of the camera distance nearer the eye (invisible, beats z-fighting)
var overlay_bias := OVERLAY_BIAS
var grid_mat: ShaderMaterial
var caption: Label
var draft_bboxes := {}     # test: new body id -> [min, max] of its draft prism (model mm)
var preload_path := ""
var cursor2d: Node2D

var client: Node
var ui_hint: Label
var ui_sync: Label
var ui_vcb: Label
var ui_toggles: Label
var ui_tip: Label

signal confirmed(seq_no: int)

var mat_draft: StandardMaterial3D
var mat_cut: StandardMaterial3D
var mat_rect: ShaderMaterial
var mat_hover: ShaderMaterial
var mat_cut_hl: ShaderMaterial    # hole highlight in Move
var mat_plane: StandardMaterial3D  # mirror-plane visuals
var mat_edge: StandardMaterial3D
var mat_draft_edge: StandardMaterial3D


# ---------------- coordinates ----------------
static func m2g(p: Vector3) -> Vector3:
	return Vector3(p.x, p.z, -p.y) * 0.001

static func g2m(p: Vector3) -> Vector3:
	return Vector3(p.x, -p.z, p.y) * 1000.0

static func n_g2m(n: Vector3) -> Vector3:
	return Vector3(n.x, -n.z, n.y)

static func r3(x: float) -> float:
	return snappedf(x, 0.001)

static func arr3(v: Vector3) -> Array:
	return [r3(v.x), r3(v.y), r3(v.z)]

static func clean_normal(n: Vector3) -> Vector3:
	var c := [n.x, n.y, n.z]
	for i in 3:
		if absf(c[i]) < 1e-3:
			c[i] = 0.0
		elif absf(absf(c[i]) - 1.0) < 1e-3:
			c[i] = signf(c[i])
	var v := Vector3(c[0], c[1], c[2]).normalized()
	return Vector3(snappedf(v.x, 1e-6), snappedf(v.y, 1e-6), snappedf(v.z, 1e-6))

static func plane_basis(n: Vector3) -> Array:
	# must match worker/replay.py plane_from()
	var x: Vector3
	if absf(n.z) > 0.9:
		x = Vector3(1, 0, 0)
	else:
		x = Vector3(0, 0, 1).cross(n).normalized()
	x = (x - n * x.dot(n)).normalized()
	return [x, n.cross(x)]


# ---------------- setup ----------------
func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--oplog="): oplog_path = a.substr(8)
		elif a.begins_with("--model="): model_path = a.substr(8)
		elif a.begins_with("--out="): out_dir = a.substr(6)
		elif a.begins_with("--drawing="): drawing_script = a.substr(10)
		elif a.begins_with("--shots="): shots_dir = a.substr(8)
		elif a == "--test": test_mode = true
		elif a == "--fxtest": test_mode = true; fx_test = true
		elif a == "--breathtest": test_mode = true; fx_test = true; breath_test = true
		elif a == "--facetest": test_mode = true; fx_test = true; face_test = true
		elif a == "--orbittest": test_mode = true; fx_test = true; orbit_test = true
		elif a == "--mirrortest": test_mode = true; fx_test = true; mirror_test = true
		elif a == "--movetest": test_mode = true; fx_test = true; move_test = true
		elif a == "--infertest": test_mode = true; fx_test = true; infer_test = true
		elif a == "--heavytest": test_mode = true; fx_test = true; heavy_test = true
		elif a == "--true-latency": true_latency = true
		elif a == "--zfighttest": test_mode = true; fx_test = true; zfight_test = true
		elif a == "--holetest": test_mode = true; fx_test = true; hole_test = true
		elif a == "--linetest": test_mode = true; fx_test = true; line_test = true
		elif a == "--undotest": test_mode = true; fx_test = true; undo_test = true
		elif a == "--gesturetest": test_mode = true; fx_test = true; gesture_test = true
		elif a == "--lifecycletest": test_mode = true; fx_test = true; lifecycle_test = true
		elif a == "--nobias": overlay_bias = 0.0
		elif a.begins_with("--preload="): preload_path = a.substr(10)
	if oplog_path == "": oplog_path = ProjectSettings.globalize_path("user://ops.json")
	if out_dir == "": out_dir = ProjectSettings.globalize_path("user://out")
	DirAccess.make_dir_recursive_absolute(out_dir)
	if model_path == "":
		model_path = (out_dir + "/model.FCStd") if test_mode else ProjectSettings.globalize_path("user://model.FCStd")
	var port := -1                 # --port=N: use a worker that's already running there (tests); else start our own
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--port="): port = int(a.substr(7))
		elif a.begins_with("--freecad="): freecad_path = a.substr(10)
		elif a.begins_with("--worker="): worker_script = a.substr(9)
		elif a.begins_with("--worker-log="): worker_log = a.substr(13)
	if port < 0:
		port = _free_port(7878)
		worker_port = port
		_start_worker()

	line_scale = maxf(1.0, DisplayServer.screen_get_scale())
	_make_materials()
	_make_world()
	_make_ui()
	client = WorkerClient.new()
	add_child(client)
	client.replied.connect(_on_worker)
	client.link_up.connect(_on_link_up)
	client.link_down.connect(_on_link_down)
	client.start(port)
	_update_camera()
	set_tool("rect")
	# open the model file; the worker answers with its history, which we adopt (tests start clean)
	_send_open()
	if test_mode:                     # scripted tests live in tests.gd (T4)
		var t: Node = load("res://tests.gd").new()
		t.name = "Tests"
		t.m = self
		add_child(t)
		t.run.call_deferred()


func _overlay_mat(col: Color) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = preload("res://overlay.gdshader")
	m.set_shader_parameter("color", col)
	m.set_shader_parameter("bias", overlay_bias)
	return m


func _make_materials() -> void:
	mat_draft = StandardMaterial3D.new()
	mat_draft.albedo_color = Color(0.95, 0.72, 0.3, 0.55)
	mat_draft.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat_draft.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat_cut = mat_draft.duplicate()
	mat_cut.albedo_color = Color(0.5, 0.3, 0.85, 0.45)    # violet: red is kept for rejections
	mat_plane = mat_draft.duplicate()
	mat_plane.albedo_color = Color(0.35, 0.55, 0.95, 0.35)
	mat_plane.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat_rect = _overlay_mat(Color(0.35, 0.55, 0.95, 0.35))
	mat_hover = _overlay_mat(Color(0.2, 0.45, 1.0, 0.45))
	mat_hover.render_priority = 2
	mat_cut_hl = _overlay_mat(Color(0.5, 0.3, 0.85, 0.5))
	mat_cut_hl.render_priority = 2
	mat_edge = StandardMaterial3D.new()
	mat_edge.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat_edge.albedo_color = Color(0.08, 0.08, 0.08)
	mat_edge.render_priority = 1
	mat_draft_edge = mat_edge.duplicate()
	mat_draft_edge.albedo_color = Color(0.6, 0.35, 0.0)


func _make_world() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.background_color = Color(0.86, 0.89, 0.92)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(1, 1, 1)
	env.ambient_light_energy = 0.42
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-55, -35, 0)
	sun.light_energy = 0.62
	add_child(sun)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-20, 140, 0)
	fill.light_energy = 0.3
	add_child(fill)
	cam = Camera3D.new()
	cam.fov = 45
	cam.near = 0.005
	add_child(cam)
	bodies_root = Node3D.new(); bodies_root.name = "Confirmed"; add_child(bodies_root)
	drafts_root = Node3D.new(); drafts_root.name = "Drafts"; add_child(drafts_root)
	overlay = MeshInstance3D.new(); add_child(overlay)
	overlay_lines = MeshInstance3D.new(); add_child(overlay_lines)
	marker = MeshInstance3D.new()
	var sm := SphereMesh.new(); sm.radius = 0.006; sm.height = 0.012
	var mm := StandardMaterial3D.new(); mm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mm.no_depth_test = true; mm.albedo_color = Color(0.1, 0.6, 0.1)
	sm.material = mm
	marker.mesh = sm
	marker.visible = false
	add_child(marker)
	# ground grid + axes (model X red, Y green, Z blue, like SketchUp)
	var segs := PackedVector3Array()
	for i in range(-20, 21):
		var s := float(i) * 100.0
		var end := 0.0 if i == 0 else 2000.0           # the positive axes draw over that half themselves
		segs.append_array([Vector3(s, -2000, 0), Vector3(s, end, 0), Vector3(-2000, s, 0), Vector3(end, s, 0)])
	var grid := _lines(segs, Color(0.62, 0.66, 0.7), GRID_LINE_PX, 0.0)
	grid_mat = grid.mesh.surface_get_material(0).duplicate()      # its own copy: the fade follows the camera
	grid_mat.render_priority = -10      # drawn first, so axes and edges are never painted over where grid lines cross
	grid.mesh.surface_set_material(0, grid_mat)
	add_child(grid)
	add_child(_lines(PackedVector3Array([Vector3.ZERO, Vector3(2000, 0, 0)]), Color(0.85, 0.1, 0.1), AXIS_LINE_PX))
	add_child(_lines(PackedVector3Array([Vector3.ZERO, Vector3(0, 2000, 0)]), Color(0.1, 0.65, 0.1), AXIS_LINE_PX))
	add_child(_lines(PackedVector3Array([Vector3.ZERO, Vector3(0, 0, 2000)]), Color(0.1, 0.25, 0.9), AXIS_LINE_PX))


func _make_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var bar := HBoxContainer.new()
	bar.position = Vector2(10, 8)
	bar.add_theme_constant_override("separation", 6)
	layer.add_child(bar)
	for spec in [["Rectangle  R", "rect"], ["Push/Pull  P", "push"], ["Move  M", "move"]]:
		var b := Button.new(); b.text = spec[0]; b.focus_mode = Control.FOCUS_NONE
		b.pressed.connect(set_tool.bind(spec[1]))
		bar.add_child(b)
	var u := Button.new(); u.text = "Undo  Ctrl+Z"; u.focus_mode = Control.FOCUS_NONE
	u.pressed.connect(undo); bar.add_child(u)
	var dbtn := Button.new(); dbtn.text = "Drawing  D"; dbtn.focus_mode = Control.FOCUS_NONE
	dbtn.pressed.connect(export_drawing); bar.add_child(dbtn)
	ui_toggles = Label.new()
	ui_toggles.position = Vector2(12, 44)
	ui_toggles.add_theme_color_override("font_color", Color(0.2, 0.2, 0.25))
	layer.add_child(ui_toggles)
	var panel := PanelContainer.new()
	panel.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	panel.offset_top = -34
	layer.add_child(panel)
	var row := HBoxContainer.new()
	panel.add_child(row)
	ui_hint = Label.new(); ui_hint.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	ui_sync = Label.new(); ui_sync.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	ui_vcb = Label.new(); ui_vcb.custom_minimum_size = Vector2(300, 0)
	ui_tip = Label.new()
	ui_tip.add_theme_color_override("font_color", Color(0.1, 0.1, 0.12))
	var tip_bg := StyleBoxFlat.new(); tip_bg.bg_color = Color(1, 1, 0.92, 0.92)
	tip_bg.set_content_margin_all(5); tip_bg.corner_radius_top_left = 4; tip_bg.corner_radius_bottom_right = 4
	ui_tip.add_theme_stylebox_override("normal", tip_bg)
	ui_tip.visible = false
	layer.add_child(ui_tip)
	row.add_child(ui_hint); row.add_child(ui_sync); row.add_child(ui_vcb)
	_update_toggles()


func _update_toggles() -> void:
	ui_toggles.text = "Grid snap %s (G)    New board on faces %s (B)    Orbit: middle/right drag or two fingers   Pan: Shift+drag   Zoom: wheel or pinch" % [
		"on" if grid_snap else "off", "on" if new_board else "off"]


# ---------------- mesh helpers ----------------
const LINE_PX := 1.5          # width of edges and outlines, in points (doubled on a Retina screen)
const GRID_LINE_PX := 1.0
const AXIS_LINE_PX := 1.75
var line_scale := 1.0         # physical pixels per point
var _line_mats := {}          # [color, width, bias] -> ShaderMaterial, shared


func _line_mat(color: Color, width_pt: float, bias: float) -> ShaderMaterial:
	var key := [color, width_pt, bias]
	if not _line_mats.has(key):
		var m := ShaderMaterial.new()
		m.shader = LINE_SHADER
		m.set_shader_parameter("color", color)
		m.set_shader_parameter("width_px", width_pt * line_scale)
		m.set_shader_parameter("bias", bias)
		_line_mats[key] = m
	return _line_mats[key]


## Line segments (pairs of model-space points) as anti-aliased strips a fixed width on screen (line.gdshader).
func _lines(segs_m: PackedVector3Array, color: Color, width_pt := LINE_PX, bias := -1.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	if segs_m.size() < 2:
		return mi
	var n := segs_m.size() / 2
	var verts := PackedVector3Array(); verts.resize(n * 4)
	var other := PackedFloat32Array(); other.resize(n * 16)
	var uvs := PackedVector2Array(); uvs.resize(n * 4)
	var idx := PackedInt32Array(); idx.resize(n * 6)
	for i in n:
		var a := m2g(segs_m[2 * i]); var b := m2g(segs_m[2 * i + 1])
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
	var m := ArrayMesh.new()
	m.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr, [], {},
		Mesh.ARRAY_CUSTOM_RGBA_FLOAT << Mesh.ARRAY_FORMAT_CUSTOM0_SHIFT)
	m.surface_set_material(0, _line_mat(color, width_pt, overlay_bias if bias < 0.0 else bias))
	mi.mesh = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.extra_cull_margin = 0.05      # the strip is a little wider than its segment on screen
	return mi


func _tri_mesh(tris_m: PackedVector3Array, mat: Material) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var c := Vector3.ZERO
	for p in tris_m:
		c += p
	c /= maxf(1.0, tris_m.size())
	for i in range(0, tris_m.size(), 3):
		var a := m2g(tris_m[i]); var b := m2g(tris_m[i + 1]); var d := m2g(tris_m[i + 2])
		var n := (b - a).cross(d - a).normalized()
		var mid := (a + b + d) / 3.0
		if n.dot(mid - m2g(c)) < 0: n = -n
		if (b - a).cross(d - a).dot(n) > 0:   # Godot front faces are clockwise
			var t := b; b = d; d = t
		for p in [a, b, d]:
			st.set_normal(n); st.add_vertex(p)
	var m := st.commit()
	m.surface_set_material(0, mat)
	return m


static func _ekey(p: Vector3, q: Vector3) -> String:
	var a := "%.2f,%.2f,%.2f" % [p.x, p.y, p.z]
	var b := "%.2f,%.2f,%.2f" % [q.x, q.y, q.z]
	return a + "|" + b if a < b else b + "|" + a


static func feature_edges(tris: PackedVector3Array) -> PackedVector3Array:
	var edges := {}
	for i in range(0, tris.size(), 3):
		var a := tris[i]; var b := tris[i + 1]; var c := tris[i + 2]
		var n := (b - a).cross(c - a).normalized()
		for e in [[a, b], [b, c], [c, a]]:
			var k := _ekey(e[0], e[1])
			if not edges.has(k):
				edges[k] = [e[0], e[1], []]
			edges[k][2].append(n)
	var out := PackedVector3Array()
	for k in edges:
		var ns: Array = edges[k][2]
		var feat := ns.size() == 1
		if not feat:
			for j in range(1, ns.size()):
				if absf(ns[0].dot(ns[j])) < 0.9998:
					feat = true
		if feat:
			out.append_array([edges[k][0], edges[k][1]])
	return out


static func unique_verts(tris: PackedVector3Array) -> PackedVector3Array:
	var seen := {}
	var out := PackedVector3Array()
	for p in tris:
		var k := "%.1f,%.1f,%.1f" % [p.x, p.y, p.z]
		if not seen.has(k):
			seen[k] = true
			out.append(p)
	return out


static func prism(tris: PackedVector3Array, n: Vector3, d: float) -> PackedVector3Array:
	var o := n * d
	var out := PackedVector3Array()
	var edges := {}
	for i in range(0, tris.size(), 3):
		var a := tris[i]; var b := tris[i + 1]; var c := tris[i + 2]
		out.append_array([a, b, c, a + o, b + o, c + o])
		for e in [[a, b], [b, c], [c, a]]:
			var k := _ekey(e[0], e[1])
			edges[k] = [e[0], e[1], edges.get(k, [0, 0, 0])[2] + 1]
	for k in edges:
		if edges[k][2] == 1:
			var p: Vector3 = edges[k][0]; var q: Vector3 = edges[k][1]
			out.append_array([p, q, q + o, p, q + o, p + o])
	return out


func _add_collision(mi: MeshInstance3D, meta_key: String, meta_val: String) -> void:
	mi.create_trimesh_collision()
	for c in mi.get_children():
		if c is StaticBody3D:
			c.set_meta(meta_key, meta_val)
			c.collision_layer = 2 if meta_key == "rect_id" else 1
			for s in c.get_children():
				if s is CollisionShape3D and s.shape is ConcavePolygonShape3D:
					s.shape.backface_collision = true


# ---------------- picking & snapping ----------------
func pick(screen: Vector2) -> Dictionary:
	var o := cam.project_ray_origin(screen)
	var d := cam.project_ray_normal(screen)
	var space := get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(o, o + d * 100.0, 1)
	q.hit_back_faces = true
	var r := space.intersect_ray(q)
	var q2 := PhysicsRayQueryParameters3D.create(o, o + d * 100.0, 2)
	q2.hit_back_faces = true
	var r2 := space.intersect_ray(q2)
	if not r2.is_empty() and (r.is_empty() or o.distance_to(r2["position"]) <= o.distance_to(r["position"]) + 0.002):
		r = r2   # a rectangle drawn on a face wins over the face itself
	if not r.is_empty():
		var n: Vector3 = r["normal"]
		if n.dot(d) > 0: n = -n                      # face toward the camera = outward
		var col: Object = r["collider"]
		var res := {"hit": true, "point": g2m(r["position"]), "normal": clean_normal(n_g2m(n)),
					"body": String(col.get_meta("body_id", "")), "rect": String(col.get_meta("rect_id", ""))}
		if res["rect"] != "":
			res["normal"] = rects[res["rect"]]["n"]
		return res
	if absf(d.y) > 1e-6:
		var t := -o.y / d.y
		if t > 0:
			return {"hit": true, "point": g2m(o + d * t), "normal": Vector3(0, 0, 1), "body": "", "rect": "", "ground": true}
	return {"hit": false}


func snap(p: Dictionary, screen: Vector2) -> Dictionary:
	if not p.get("hit", false):
		return p
	var n: Vector3 = p["normal"]
	var best = null
	var bestd := SNAP_PX
	var pools := []
	if p["body"] != "": pools.append(body_verts.get(p["body"], PackedVector3Array()))
	else: for k in body_verts: pools.append(body_verts[k])
	for k in rects: pools.append(PackedVector3Array(rects[k]["pts"]))
	for pool in pools:
		for v in pool:
			if absf((v - p["point"]).dot(n)) > 0.5: continue   # stay on the plane
			var gv := m2g(v)
			if cam.is_position_behind(gv): continue
			var dd := cam.unproject_position(gv).distance_to(screen)
			if dd < bestd:
				bestd = dd; best = v
	if best != null:
		p["point"] = best; p["snap"] = "endpoint"
	elif grid_snap:
		var pt: Vector3 = p["point"]
		for i in 3:
			if absf(n[i]) < 0.5:
				pt[i] = snappedf(pt[i], GRID)
		p["point"] = pt; p["snap"] = "grid"
	return p


func _show_marker(p: Dictionary) -> void:
	marker.visible = p.get("hit", false)
	if marker.visible:
		marker.position = m2g(p["point"])
		var col := Color(0.1, 0.6, 0.1) if p.get("snap", "") == "endpoint" else Color(0.35, 0.35, 0.4)
		(marker.mesh.material as StandardMaterial3D).albedo_color = col


# ---------------- tools ----------------
func set_tool(t: String) -> void:
	tool = t
	rect_state = {}; push_state = {}; mirror_state = {}; move_state = {}; vcb = ""
	if guides: guides.mesh = null
	move_copy = false
	move_mirror = false
	if ui_tip: ui_tip.visible = false
	overlay.mesh = null; overlay_lines.mesh = null
	ui_hint.text = {"rect": "Rectangle: click a face or the ground, then click or type  width, height  + Enter",
					"push": "Push/Pull: click a face or rectangle, move, then click or type a distance + Enter (minus = cut)",
					"move": "Move: grab a point on a board, click or type a distance. Ctrl/Option = copy, Shift = mirror, arrows lock axis. After a copy: 5x or /5",
					"mirror": "Mirror: click a board, move the plane (arrows: Right=red Left=green Up=blue), click or type distance past the board + Enter"}[t]
	_update_vcb()


func _update_vcb() -> void:
	var label := "Dimensions" if tool == "rect" else ("Face to plane" if tool == "mirror" or (tool == "move" and move_mirror) else ("Copy distance" if tool == "move" and move_copy else "Distance"))
	var val := vcb
	if val == "":
		if tool == "rect" and rect_state.get("active", false):
			val = "%d, %d" % [absf(rect_state["du"]), absf(rect_state["dv"])]
		elif tool == "push" and push_state.get("active", false):
			val = "%d" % push_state["dist"]
		elif tool == "mirror" and mirror_state.get("stage", "") == "place":
			val = "%d" % _mirror_gap()
		elif tool == "move" and move_state.get("active", false) and move_mirror and move_state.has("mir_c"):
			val = "%d" % _mirror_face_gap(move_state["mir_ax"], move_state["mir_c"])
		elif tool == "move" and move_state.get("active", false):
			val = "%d" % move_state["vec"].length()
	ui_vcb.text = "%s   [ %s ] mm" % [label, val]


func tool_move(screen: Vector2) -> void:
	if tool == "rect":
		if rect_state.get("active", false):
			_rect_drag(screen)
		else:
			_show_marker(snap(pick(screen), screen))
	elif tool == "push":
		if push_state.get("active", false):
			_push_drag(screen)
		else:
			_push_hover(screen)
	elif tool == "mirror":
		_mirror_move(screen)
	elif tool == "move":
		_move_move(screen)
	_update_tip(screen)


func tool_click(screen: Vector2) -> void:
	if tool != "move": last_move_oid = ""
	if tool == "rect":
		if not rect_state.get("active", false):
			var p := snap(pick(screen), screen)
			if not p.get("hit", false): return
			var n: Vector3 = p["normal"]
			var b := plane_basis(n)
			var on: String = p["body"]
			if p["rect"] != "": on = rects[p["rect"]]["on"]
			rect_state = {"active": true, "origin": p["point"], "n": n, "x": b[0], "y": b[1], "on": on, "du": 0.0, "dv": 0.0}
		else:
			commit_rect(rect_state["du"], rect_state["dv"])
	elif tool == "push":
		if not push_state.get("active", false):
			_push_hover(screen)
			if hover.is_empty(): return
			push_state = hover.duplicate()
			push_state["active"] = true
			push_state["dist"] = 0.0
		else:
			commit_push(push_state["dist"])
	elif tool == "mirror":
		_mirror_click(screen)
	elif tool == "move":
		_move_click(screen)
	_update_vcb()


func _rect_drag(screen: Vector2) -> void:
	var o := g2m(cam.project_ray_origin(screen))
	var d := n_g2m(cam.project_ray_normal(screen))
	var n: Vector3 = rect_state["n"]
	var den := d.dot(n)
	if absf(den) < 1e-6: return
	var t: float = (rect_state["origin"] - o).dot(n) / den
	var q: Vector3 = o + d * t
	var p := snap({"hit": true, "point": q, "normal": n, "body": rect_state["on"], "rect": ""}, screen)
	_show_marker(p)
	var v: Vector3 = p["point"] - rect_state["origin"]
	rect_state["du"] = r3(v.dot(rect_state["x"]))
	rect_state["dv"] = r3(v.dot(rect_state["y"]))
	_preview_rect(rect_state["du"], rect_state["dv"])
	_update_vcb()


func _rect_pts(origin: Vector3, x: Vector3, y: Vector3, du: float, dv: float) -> PackedVector3Array:
	return PackedVector3Array([origin, origin + x * du, origin + x * du + y * dv, origin + y * dv])


func _preview_rect(du: float, dv: float) -> void:
	var pts := _rect_pts(rect_state["origin"], rect_state["x"], rect_state["y"], du, dv)
	var tris := PackedVector3Array([pts[0], pts[1], pts[2], pts[0], pts[2], pts[3]])
	overlay.mesh = _tri_mesh(tris, mat_rect)
	overlay_lines.mesh = _lines(PackedVector3Array([pts[0], pts[1], pts[1], pts[2], pts[2], pts[3], pts[3], pts[0]]), Color(0.1, 0.2, 0.6)).mesh


func commit_rect(du: float, dv: float) -> void:
	if absf(du) < 0.5 or absf(dv) < 0.5: return
	counters["r"] += 1
	var rid := "r%d" % counters["r"]
	var n: Vector3 = rect_state["n"]
	var plane := {}
	if rect_state["on"] != "":
		plane = {"on": {"body": rect_state["on"], "normal": arr3(n), "point": arr3(rect_state["origin"])}}
	else:
		plane = {"origin": arr3(rect_state["origin"]), "normal": arr3(n)}
	var op := {"id": rid, "type": "rect", "plane": plane,
			   "corner": [r3(minf(0, du)), r3(minf(0, dv))], "size": [r3(absf(du)), r3(absf(dv))]}
	ops.append(op)
	_register_rect(op)
	rect_state = {}
	overlay.mesh = null; overlay_lines.mesh = null
	sync()


func _register_rect(op: Dictionary) -> void:
	var pl: Dictionary = op["plane"]
	var src: Dictionary = pl["on"] if pl.has("on") else pl
	var origin := Vector3(src["point"][0], src["point"][1], src["point"][2]) if pl.has("on") else Vector3(src["origin"][0], src["origin"][1], src["origin"][2])
	var n := Vector3(src["normal"][0], src["normal"][1], src["normal"][2])
	var b := plane_basis(n)
	var corner: Array = op.get("corner", [0, 0])     # optional, as in the worker
	var o2: Vector3 = origin + b[0] * float(corner[0]) + b[1] * float(corner[1])
	var pts := _rect_pts(o2, b[0], b[1], op["size"][0], op["size"][1])
	var tris := PackedVector3Array([pts[0], pts[1], pts[2], pts[0], pts[2], pts[3]])
	rects[op["id"]] = {"tris": tris, "n": n, "on": src.get("body", "") if pl.has("on") else "", "pts": pts}
	var mi := MeshInstance3D.new()
	mi.mesh = _tri_mesh(tris, mat_rect)
	mi.add_child(_lines(PackedVector3Array([pts[0], pts[1], pts[1], pts[2], pts[2], pts[3], pts[3], pts[0]]), Color(0.1, 0.2, 0.6)))
	drafts_root.add_child(mi)
	_add_collision(mi, "rect_id", op["id"])
	drafts[op["id"]] = mi


func _push_hover(screen: Vector2) -> void:
	hover = {}
	overlay.mesh = null
	var p := pick(screen)
	marker.visible = false
	if not p.get("hit", false) or p.get("ground", false): return
	var tris := PackedVector3Array()
	if p["rect"] != "":
		tris = rects[p["rect"]]["tris"]
	elif p["body"] != "":
		tris = coplanar_region(p["body"], p["normal"], p["point"])
	if tris.is_empty(): return
	hover = {"rect": p["rect"], "body": p["body"], "n": p["normal"], "anchor": p["point"], "tris": tris}
	overlay.mesh = _tri_mesh(tris, mat_hover)


func coplanar_region(bid: String, n: Vector3, p: Vector3) -> PackedVector3Array:
	var all: PackedVector3Array = body_tris.get(bid, PackedVector3Array())
	var cand := []
	for i in range(0, all.size(), 3):
		var a := all[i]; var b := all[i + 1]; var c := all[i + 2]
		var tn := (b - a).cross(c - a).normalized()
		if absf(tn.dot(n)) > 0.999 and absf((a - p).dot(n)) < 0.5:
			cand.append([a, b, c])
	if cand.is_empty(): return PackedVector3Array()
	# flood fill from the triangle under the point, across shared edges
	var start := 0
	for i in cand.size():
		if _in_tri(p, cand[i][0], cand[i][1], cand[i][2]): start = i; break
	var by_edge := {}
	for i in cand.size():
		for e in [[0, 1], [1, 2], [2, 0]]:
			var k := _ekey(cand[i][e[0]], cand[i][e[1]])
			if not by_edge.has(k): by_edge[k] = []
			by_edge[k].append(i)
	var seen := {start: true}
	var stack := [start]
	while not stack.is_empty():
		var i: int = stack.pop_back()
		for e in [[0, 1], [1, 2], [2, 0]]:
			for j in by_edge[_ekey(cand[i][e[0]], cand[i][e[1]])]:
				if not seen.has(j): seen[j] = true; stack.append(j)
	var out := PackedVector3Array()
	for i in seen: out.append_array(PackedVector3Array(cand[i]))
	return out


static func _in_tri(p: Vector3, a: Vector3, b: Vector3, c: Vector3) -> bool:
	var v0 := c - a; var v1 := b - a; var v2 := p - a
	var d00 := v0.dot(v0); var d01 := v0.dot(v1); var d11 := v1.dot(v1)
	var d20 := v2.dot(v0); var d21 := v2.dot(v1)
	var den := d00 * d11 - d01 * d01
	if absf(den) < 1e-12: return false
	var v := (d11 * d20 - d01 * d21) / den
	var w := (d00 * d21 - d01 * d20) / den
	return v >= -1e-4 and w >= -1e-4 and v + w <= 1.0001


func _push_drag(screen: Vector2) -> void:
	var a := m2g(push_state["anchor"])
	var n := Vector3(push_state["n"].x, push_state["n"].z, -push_state["n"].y)
	var o := cam.project_ray_origin(screen); var d := cam.project_ray_normal(screen)
	var w0 := a - o
	var bb := n.dot(d); var cc := d.dot(d); var dd := n.dot(w0); var ee := d.dot(w0)
	var den := n.dot(n) * cc - bb * bb
	if absf(den) < 1e-9: return
	var s := (bb * ee - cc * dd) / den
	push_state["dist"] = roundf(s * 1000.0)
	_preview_push(push_state["dist"])
	_update_vcb()


func _preview_push(d: float) -> void:
	if absf(d) < 0.5:
		overlay.mesh = _tri_mesh(push_state["tris"], mat_hover); overlay_lines.mesh = null; return
	var pr := prism(push_state["tris"], push_state["n"], d)
	overlay.mesh = _tri_mesh(pr, mat_cut if d < 0 else mat_draft)
	overlay_lines.mesh = _lines(feature_edges(pr), Color(0.6, 0.35, 0.0)).mesh


func commit_push(d: float) -> void:
	if absf(d) < 0.5: return
	reject_note = ""
	counters["pp"] += 1
	var oid := "pp%d" % counters["pp"]
	var op := {"id": oid, "type": "push_pull", "distance": r3(d)}
	var on := ""
	if push_state["rect"] != "":
		op["target"] = {"rect": push_state["rect"]}
		on = rects[push_state["rect"]]["on"]
	else:
		op["target"] = {"face": {"body": push_state["body"], "normal": arr3(push_state["n"]), "point": arr3(push_state["anchor"])}}
		on = push_state["body"]
	var new_id := ""
	# a rectangle becomes its own board (free, or on a face with "new board" on);
	# pushing a body's own face always edits that body, like SketchUp
	if push_state["rect"] != "" and (on == "" or (d > 0 and new_board)):
		counters["b"] += 1
		new_id = "b%d" % counters["b"]
		op["body"] = new_id
	if force_reject_next and op["target"].has("rect"):
		op["target"] = {"rect": "r_missing"}      # test hook only: guarantees FreeCAD rejects it
		force_reject_next = false
	ops.append(op)
	var end_point: Vector3 = push_state["anchor"] + push_state["n"] * d   # on the moved face, under the cursor's axis
	var pr := prism(push_state["tris"], push_state["n"], d)
	var nodes := _add_push_draft(op, pr, d, new_id)
	if test_mode and new_id != "":
		var lo := Vector3(INF, INF, INF); var hi := -lo
		for q in pr: lo = lo.min(q); hi = hi.max(q)
		draft_bboxes[new_id] = [arr3(lo), arr3(hi)]
	# the wave starts now, before FreeCAD has answered
	if new_id != "":
		_begin_wave(oid, end_point, pr, true, new_id)
		_attach_wave(oid, nodes[0], nodes[1], DEFAULT_BASE)
	else:
		_begin_wave(oid, end_point, body_tris.get(on, pr), false, on)
		for mi in bodies_root.find_children(on, "MeshInstance3D", true, false):
			_attach_wave(oid, mi, mi.get_child(mi.get_child_count() - 1), _base_of(mi))
	if push_state["rect"] != "" and drafts.has(push_state["rect"]):
		drafts[push_state["rect"]].queue_free(); drafts.erase(push_state["rect"])
	push_state = {}
	overlay.mesh = null; overlay_lines.mesh = null
	sync()


func _add_push_draft(op: Dictionary, pr: PackedVector3Array, d: float, new_id: String) -> Array:
	var mi := MeshInstance3D.new()
	mi.mesh = _tri_mesh(pr, mat_cut if d < 0 else mat_draft)
	var edges := _lines(feature_edges(pr), Color(0.6, 0.35, 0.0))
	mi.add_child(edges)
	drafts_root.add_child(mi)
	drafts[op["id"]] = mi
	if new_id != "":
		_add_collision(mi, "body_id", new_id)
		body_tris[new_id] = pr                     # lets you keep working on a draft board
		body_verts[new_id] = unique_verts(pr)
		body_edges[new_id] = feature_edges(pr)
	return [mi, edges]


func _update_tip(screen: Vector2) -> void:
	if ui_tip == null: return
	var txt := ""
	if tool == "mirror" and mirror_state.get("stage", "") == "place":
		var g := _mirror_gap()
		var what := "face → plane" if mirror_state["axis"] == mirror_state["face_ax"] else "board → plane"
		txt = "%s  %d mm\n%s  %d mm" % [what, g, "face → mirrored face" if what == "face → plane" else "board → copy", 2.0 * g]
	elif tool == "move" and move_state.get("active", false) and move_mirror and move_state.has("mir_c"):
		var g := _mirror_face_gap(move_state["mir_ax"], move_state["mir_c"])
		var col: String = ["red", "green", "blue"][move_state["mir_ax"]]
		txt = "Mirror%s (%s plane)\nface → plane  %d mm\nface → mirrored face  %d mm" % [" + copy" if move_copy else "", col, g, 2.0 * g]
	elif tool == "move" and move_state.get("active", false):
		var k: String = move_state.get("kind", "")
		txt = "%s  %d mm%s" % ["Copy +" if move_copy else "Move", move_state["vec"].length(), ("\n" + k) if k != "" else ""]
	elif tool == "move" and last_move_oid != "" and move_copy:
		txt = "type 5x or /5 for more copies"
	elif tool == "move" and (move_copy or move_mirror):
		txt = ("+ copy " if move_copy else "") + ("+ mirror" if move_mirror else "")
	ui_tip.visible = txt != ""
	ui_tip.text = txt
	ui_tip.position = screen + Vector2(22, 20)


# ---------------- mirror as a Move modifier (Shift) ----------------
var move_mirror := false


func _mirror_axis_and_plane() -> Array:
	var vec: Vector3 = move_state["vec"]
	var ax: int = move_state["lock"] if move_state.get("lock_mode", "free") == "axis" else -1
	if ax < 0:
		ax = move_state["face_ax"]           # parallel to the face you grabbed, unless an arrow key says otherwise
	var ref: Vector3 = move_state["ref"]
	return [ax, ref[ax] + vec[ax] * 0.5]        # perpendicular bisector: the grabbed point lands under the cursor


func _mirror_face_gap(ax: int, c: float) -> float:
	if ax == move_state["face_ax"]:
		return absf(c - move_state["face_c"])
	return c - move_state["hi"][ax] if c >= (move_state["lo"][ax] + move_state["hi"][ax]) * 0.5 else move_state["lo"][ax] - c


func _preview_mirror_move() -> void:
	var r := _mirror_axis_and_plane()
	var ax: int = r[0]; var c: float = r[1]
	move_state["mir_ax"] = ax; move_state["mir_c"] = c
	var ghost := _mirror_tris(move_state["tris"], ax, c)
	var lo: Vector3 = move_state["lo"]; var hi: Vector3 = move_state["hi"]
	for q in ghost: lo = lo.min(q); hi = hi.max(q)
	var u := (ax + 1) % 3; var v := (ax + 2) % 3
	var corners := PackedVector3Array()
	for uv in [[lo[u] - 60, lo[v] - 60], [hi[u] + 60, lo[v] - 60], [hi[u] + 60, hi[v] + 60], [lo[u] - 60, hi[v] + 60]]:
		var pt := Vector3.ZERO
		pt[ax] = c; pt[u] = uv[0]; pt[v] = uv[1]
		corners.append(pt)
	var pm := mat_plane.duplicate() as StandardMaterial3D
	pm.albedo_color = AXIS_COLORS[ax]
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for q in [corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]]: st.add_vertex(m2g(q))
	var mesh := _tri_mesh(ghost, mat_draft)
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, st.commit_to_arrays())
	mesh.surface_set_material(1, pm)
	overlay.mesh = mesh
	var edge_col: Color = AXIS_COLORS[ax]
	edge_col.a = 1.0
	var segs := feature_edges(ghost)
	segs.append_array(PackedVector3Array([corners[0], corners[1], corners[1], corners[2], corners[2], corners[3], corners[3], corners[0]]))
	overlay_lines.mesh = _lines(segs, edge_col.darkened(0.2)).mesh
	var landed: Vector3 = move_state["ref"]
	landed[ax] = 2.0 * c - landed[ax]
	_show_marker({"hit": true, "point": landed})
	_update_vcb()


func commit_mirror_move(ax: int, c: float) -> void:
	reject_note = ""
	var body: String = move_state["body"]
	counters["m"] += 1
	var oid := "m%d" % counters["m"]
	var pt := Vector3.ZERO
	pt[ax] = c
	var op := {"id": oid, "type": "mirror", "targets": [body], "plane": {"point": arr3(pt), "normal": arr3(_axis_vec(ax))}}
	var bid := body
	if move_copy:
		counters["b"] += 1
		bid = "b%d" % counters["b"]
		op["new_ids"] = [bid]
	else:
		op["replace"] = true                 # flip the board itself
	ops.append(op)
	var ghost := _mirror_tris(move_state["tris"], ax, c)
	var mi := MeshInstance3D.new()
	mi.mesh = _tri_mesh(ghost, mat_draft)
	var edges := _lines(feature_edges(ghost), Color(0.6, 0.35, 0.0))
	mi.add_child(edges)
	drafts_root.add_child(mi)
	drafts[oid] = mi
	_add_collision(mi, "body_id", bid)
	body_tris[bid] = ghost
	body_verts[bid] = unique_verts(ghost)
	body_edges[bid] = feature_edges(ghost)
	if not move_copy:
		for n in bodies_root.find_children(body, "MeshInstance3D", true, false):
			n.visible = false
	if test_mode:
		var blo := Vector3(INF, INF, INF); var bhi := -blo
		for q in ghost: blo = blo.min(q); bhi = bhi.max(q)
		draft_bboxes[bid] = [arr3(blo), arr3(bhi)]
	var landed: Vector3 = move_state["ref"]
	landed[ax] = 2.0 * c - landed[ax]
	_begin_wave(oid, landed, ghost, move_copy, bid)
	_attach_wave(oid, mi, edges, DEFAULT_BASE)
	last_move_oid = ""
	move_state["active"] = false
	if guides: guides.mesh = null
	overlay.mesh = null; overlay_lines.mesh = null
	marker.visible = false
	_update_tip(_cursor_pos())
	sync()


# ---------------- inference (SketchUp-style snapping for Move) ----------------
const EDGE_PX := 8.0
const INFER_DEG := 8.0          # drag within this angle of an axis's on-screen direction -> sticks to it
const RELEASE_DEG := 12.0       # ...and lets go beyond this (hysteresis)
const SNAP_COLORS := {"endpoint": Color(0.1, 0.65, 0.1), "midpoint": Color(0.1, 0.7, 0.8), "on edge": Color(0.85, 0.15, 0.15),
					  "on face": Color(0.2, 0.35, 0.95)}
var body_edges := {}            # body id -> feature edge segments (model mm)
var guides: MeshInstance3D


func _infer_point(screen: Vector2, exclude: String) -> Dictionary:
	"""Point snaps on other boards, in SketchUp's priority: endpoint > midpoint > on edge. Empty if none."""
	var best := {}
	var bestd := SNAP_PX
	for bid in body_verts:
		if bid == exclude: continue
		for v in body_verts[bid]:
			var gv := m2g(v)
			if cam.is_position_behind(gv): continue
			var dd := cam.unproject_position(gv).distance_to(screen)
			if dd < bestd: bestd = dd; best = {"point": v, "kind": "endpoint", "body": bid}
	if not best.is_empty(): return best
	bestd = SNAP_PX
	for bid in body_edges:
		if bid == exclude: continue
		var segs: PackedVector3Array = body_edges[bid]
		for i in range(0, segs.size(), 2):
			var mid := (segs[i] + segs[i + 1]) * 0.5
			var gm := m2g(mid)
			if cam.is_position_behind(gm): continue
			var dd := cam.unproject_position(gm).distance_to(screen)
			if dd < bestd: bestd = dd; best = {"point": mid, "kind": "midpoint", "body": bid}
	if not best.is_empty(): return best
	bestd = EDGE_PX
	var o := g2m(cam.project_ray_origin(screen)); var d := n_g2m(cam.project_ray_normal(screen))
	for bid in body_edges:
		if bid == exclude: continue
		var segs: PackedVector3Array = body_edges[bid]
		for i in range(0, segs.size(), 2):
			var q := _closest_on_segment_to_ray(segs[i], segs[i + 1], o, d)
			var gq := m2g(q)
			if cam.is_position_behind(gq): continue
			var dd := cam.unproject_position(gq).distance_to(screen)
			if dd < bestd: bestd = dd; best = {"point": q, "kind": "on edge", "body": bid}
	return best


static func _closest_on_segment_to_ray(p0: Vector3, p1: Vector3, o: Vector3, d: Vector3) -> Vector3:
	var u := p1 - p0
	var w0 := p0 - o
	var a := u.dot(u); var b := u.dot(d); var c := d.dot(d); var dd := u.dot(w0); var e := d.dot(w0)
	var den := a * c - b * b
	var s := 0.0 if absf(den) < 1e-9 else clampf((b * e - c * dd) / den, 0.0, 1.0)
	return p0 + u * s


func _infer_axis(screen: Vector2, anchor: Vector3, axes: Array, current: int) -> int:
	var a2 := cam.unproject_position(m2g(anchor))
	var dv := screen - a2
	if dv.length() < 15.0: return -1
	var best := -1
	var best_ang := INF
	for ax in axes:
		var b2 := cam.unproject_position(m2g(anchor + _axis_vec(ax) * 100.0))
		var dir := b2 - a2
		if dir.length() < 3.0: continue                 # axis points at the camera: nothing to follow on screen
		var ang := rad_to_deg(dv.angle_to(dir))
		ang = minf(absf(ang), 180.0 - absf(ang))        # either direction along the axis
		var limit := RELEASE_DEG if ax == current else INFER_DEG
		if ang < limit and ang < best_ang:
			best_ang = ang; best = ax
	return best


func _axis_dest(screen: Vector2, ref: Vector3, ax: int) -> Variant:
	var ax_v := _axis_vec(ax)
	var a := m2g(ref); var n := (m2g(ref + ax_v) - a).normalized()
	var o := cam.project_ray_origin(screen); var d := cam.project_ray_normal(screen)
	var bb := n.dot(d); var den := 1.0 - bb * bb
	var t := 0.0
	if den > 0.06:
		var w0 := a - o
		t = (bb * d.dot(w0) - n.dot(w0)) / den * 1000.0
	else:
		# looking almost straight down the axis: use the point under the cursor, projected onto it
		var under := pick(screen)
		if not under.get("hit", false) or under["body"] == move_state.get("body", ""): return null
		t = (under["point"] - ref).dot(ax_v)
	return ref + ax_v * (snappedf(t, GRID) if grid_snap else roundf(t))


func _plane_dest(screen: Vector2, ref: Vector3, n: Vector3) -> Variant:
	var o := g2m(cam.project_ray_origin(screen)); var d := n_g2m(cam.project_ray_normal(screen))
	var den := d.dot(n)
	if absf(den) < 1e-4: return null
	var t := (ref - o).dot(n) / den
	if t <= 0: return null
	var vec := o + d * t - ref
	if grid_snap:                                    # snap the distance travelled, not the position
		for i in 3:
			if absf(n[i]) < 0.5: vec[i] = snappedf(vec[i], GRID)
	return ref + vec


func _draw_guides(ref: Vector3, axis: int, plane_axis: int) -> void:
	if guides == null:
		guides = MeshInstance3D.new(); add_child(guides)
	guides.mesh = null
	var segs := PackedVector3Array()
	var col := Color(0.4, 0.4, 0.4)
	if axis >= 0:
		var v := _axis_vec(axis)
		var k := -3000.0
		while k < 3000.0:                                # dotted line along the axis through the grab point
			segs.append_array([ref + v * k, ref + v * (k + 14.0)])
			k += 30.0
		col = [Color(0.85, 0.1, 0.1), Color(0.1, 0.6, 0.1), Color(0.1, 0.25, 0.9)][axis]
	if plane_axis >= 0:
		var u := _axis_vec((plane_axis + 1) % 3) * 600.0
		var w := _axis_vec((plane_axis + 2) % 3) * 600.0
		for k in range(-6, 7):
			segs.append_array([ref + u * (k / 6.0) - w, ref + u * (k / 6.0) + w, ref + w * (k / 6.0) - u, ref + w * (k / 6.0) + u])
		col = [Color(0.85, 0.1, 0.1, 0.5), Color(0.1, 0.6, 0.1, 0.5), Color(0.1, 0.25, 0.9, 0.5)][plane_axis]
	if not segs.is_empty():
		guides.mesh = _lines(segs, col).mesh


# ---------------- move tool (SketchUp-style) ----------------
var move_state := {}
var move_copy := false
var last_move_oid := ""        # the move/copy you can still adjust by typing (distance, Nx, *N, /N)
var move_memo := {}            # move op id -> {"tris": geometry before the move, "ref": pick-up point}


func _cursor_pos() -> Vector2:
	return cursor2d.position if test_mode and cursor2d != null else get_viewport().get_mouse_position()


func _move_click(screen: Vector2) -> void:
	if not move_state.get("active", false):
		var p := snap(pick(screen), screen)
		if not p.get("hit", false) or p["body"] == "" or not body_tris.has(p["body"]): return
		last_move_oid = ""
		var tris: PackedVector3Array = body_tris[p["body"]]
		var cut := _cut_at(p["body"], p["point"])
		var cut_ref := {}
		if not cut.is_empty():                       # clicked a hole: move / copy the hole, not the board
			cut_ref = {"body": p["body"], "op": cut["op"], "kind": cut["kind"]}
			tris = _cut_tris(p["body"], cut["op"])
		var lo := Vector3(INF, INF, INF); var hi := -lo
		for q in tris: lo = lo.min(q); hi = hi.max(q)
		var n: Vector3 = p["normal"]
		var fax := 0
		for i in 3:
			if absf(n[i]) > absf(n[fax]): fax = i
		move_state = {"active": true, "body": p["body"], "tris": tris, "ref": p["point"],
					  "vec": Vector3.ZERO, "lock": -1, "lock_mode": "free", "inferred": -1, "kind": "",
					  "count": 1, "divide": false, "lo": lo, "hi": hi,
					  "face_ax": fax, "face_c": snappedf(p["point"][fax], 0.01), "face_sign": signf(n[fax]),
					  "cut": cut_ref}
	elif move_mirror and move_state.get("cut", {}).is_empty():
		commit_mirror_move(move_state["mir_ax"], move_state["mir_c"])
	else:
		commit_move(move_state["vec"])


func _move_move(screen: Vector2) -> void:
	if not move_state.get("active", false):
		var hp := pick(screen)
		overlay_lines.mesh = null
		overlay.mesh = null
		if hp.get("hit", false) and body_tris.has(hp["body"]):
			var hc := _cut_at(hp["body"], hp["point"])
			if hc.is_empty():
				overlay.mesh = _tri_mesh(body_tris[hp["body"]], mat_hover)
			else:
				var ht := _cut_tris(hp["body"], hc["op"])
				overlay.mesh = _tri_mesh(ht, mat_cut_hl)
				overlay_lines.mesh = _lines(feature_edges(ht), Color(0.35, 0.15, 0.6)).mesh
		return
	var ref: Vector3 = move_state["ref"]
	var body: String = move_state["body"]
	var moving_cut: bool = not move_state.get("cut", {}).is_empty()
	var mode: String = move_state.get("lock_mode", "free")
	var lax: int = move_state["lock"]
	var dest = null
	var kind := ""
	var guide_axis := -1
	var guide_plane := -1
	if mode == "axis":
		dest = _axis_dest(screen, ref, lax)
		kind = ["red", "green", "blue"][lax] + " axis (locked)"
		guide_axis = lax
	else:
		var plane_n := _axis_vec(lax) if mode == "plane" else Vector3(0, 0, 1)
		if mode == "plane": guide_plane = lax
		var pt := _infer_point(screen, "" if moving_cut else body)   # a hole can snap to its own board
		if not pt.is_empty():
			dest = pt["point"]
			if mode == "plane":                       # stay on the locked plane
				dest = dest - plane_n * (dest - ref).dot(plane_n)
			kind = pt["kind"]
		else:
			var axes := [0, 1, 2] if mode == "free" else [(lax + 1) % 3, (lax + 2) % 3]
			var inf := _infer_axis(screen, ref, axes, move_state.get("inferred", -1))
			move_state["inferred"] = inf
			if inf >= 0:
				dest = _axis_dest(screen, ref, inf)
				kind = "on " + ["red", "green", "blue"][inf] + " axis"
				guide_axis = inf
			else:
				var hit := pick(screen)
				if hit.get("hit", false) and hit["body"] != "" and hit["body"] != body and mode == "free":
					dest = hit["point"]                   # on another board's face
					var fn: Vector3 = hit["normal"]
					if grid_snap:
						var vec: Vector3 = dest - ref
						for i in 3:
							if absf(fn[i]) < 0.5: vec[i] = snappedf(vec[i], GRID)
						dest = ref + vec
					kind = "on face"
				else:
					dest = _plane_dest(screen, ref, plane_n)
					kind = "free" if mode == "free" else ["green/blue", "red/blue", "red/green"][lax] + " plane (locked)"
	if dest == null: return
	move_state["vec"] = dest - ref
	move_state["kind"] = kind
	_draw_guides(ref, guide_axis, guide_plane)
	if move_mirror and not moving_cut:
		_preview_mirror_move()
		return
	var mcol: Color = SNAP_COLORS.get(kind, Color(0.35, 0.35, 0.4))
	marker.visible = true
	marker.position = m2g(dest)
	(marker.mesh.material as StandardMaterial3D).albedo_color = mcol
	_preview_move()


func _move_offsets(vec: Vector3, count: int, divide: bool, copy: bool) -> Array:
	var out := []
	if not copy:
		out.append(vec)
		return out
	for i in range(1, count + 1):
		out.append(vec * (float(i) / count) if divide else vec * i)
	return out


func _preview_move() -> void:
	var all := PackedVector3Array()
	for off in _move_offsets(move_state["vec"], move_state["count"], move_state["divide"], move_copy):
		for q in move_state["tris"]: all.append(q + off)
	overlay.mesh = _tri_mesh(all, mat_draft if move_state.get("cut", {}).is_empty() else mat_cut)
	overlay_lines.mesh = _lines(feature_edges(all), Color(0.6, 0.35, 0.0)).mesh
	_update_vcb()


func commit_move(vec: Vector3, count := 1, divide := false, reuse_oid := "") -> void:
	if vec.length() < 0.5: return
	reject_note = ""
	if not move_state.get("cut", {}).is_empty():
		_commit_cut_move(vec, count, divide, reuse_oid)
		return
	var body: String = move_state.get("body", "")
	var oid := reuse_oid
	if oid == "":
		counters["mv"] += 1
		oid = "mv%d" % counters["mv"]
	var op := {"id": oid, "type": "move", "targets": [body], "vector": arr3(vec), "copy": move_copy}
	var offsets := _move_offsets(vec, count, divide, move_copy)
	var made := []
	if move_copy:
		op["count"] = count
		op["divide"] = divide
		for i in offsets.size():
			counters["b"] += 1
			made.append("b%d" % counters["b"])
		op["new_ids"] = made
	ops.append(op)
	var root := Node3D.new()
	drafts_root.add_child(root)
	drafts[oid] = root
	var all := PackedVector3Array()
	var src: PackedVector3Array = move_state["tris"]
	move_memo[oid] = {"tris": src, "ref": move_state["ref"]}
	var wave_bodies := made if move_copy else [body]
	for i in offsets.size():
		var moved := PackedVector3Array()
		for q in src: moved.append(q + offsets[i])
		all.append_array(moved)
		var mi := MeshInstance3D.new()
		mi.mesh = _tri_mesh(moved, mat_draft)
		var edges := _lines(feature_edges(moved), Color(0.6, 0.35, 0.0))
		mi.add_child(edges)
		root.add_child(mi)
		var bid: String = wave_bodies[i]
		_add_collision(mi, "body_id", bid)
		body_tris[bid] = moved
		body_verts[bid] = unique_verts(moved)
		body_edges[bid] = feature_edges(moved)
		if test_mode:
			var lo := Vector3(INF, INF, INF); var hi := -lo
			for q in moved: lo = lo.min(q); hi = hi.max(q)
			draft_bboxes[bid] = [arr3(lo), arr3(hi)]
	if not move_copy:
		for n in bodies_root.find_children(body, "MeshInstance3D", true, false):
			n.visible = false            # it has left: hide the old spot until FreeCAD's mesh arrives
	var dest: Vector3 = move_state["ref"] + offsets[offsets.size() - 1]
	_begin_wave(oid, dest, all, move_copy, wave_bodies)
	for i in root.get_child_count():
		var mi: MeshInstance3D = root.get_child(i)
		_attach_wave(oid, mi, mi.get_child(0), DEFAULT_BASE)
	last_move_oid = oid
	move_state["last_vec"] = vec
	if guides: guides.mesh = null
	move_state["active"] = false
	overlay.mesh = null; overlay_lines.mesh = null
	marker.visible = false
	_update_tip(_cursor_pos())
	sync()


func _commit_cut_move(vec: Vector3, count: int, divide: bool, reuse_oid: String) -> void:
	"""Move a hole, or copy it (FreeCAD makes the copies a Draft array of the cutter)."""
	var cut: Dictionary = move_state["cut"]
	var body: String = cut["body"]
	var oid := reuse_oid
	if oid == "":
		counters["mv"] += 1
		oid = "mv%d" % counters["mv"]
	var op := {"id": oid, "type": "move", "targets": [], "cut": {"body": body, "op": cut["op"]},
		"vector": arr3(vec), "copy": move_copy}
	if move_copy:
		op["count"] = count
		op["divide"] = divide
	ops.append(op)
	var root := Node3D.new()
	drafts_root.add_child(root)
	drafts[oid] = root
	var src: PackedVector3Array = move_state["tris"]
	move_memo[oid] = {"tris": src, "ref": move_state["ref"], "cut": cut}
	var offsets := _move_offsets(vec, count, divide, move_copy)
	for off in offsets:
		var moved := PackedVector3Array()
		for q in src: moved.append(q + off)
		var mi := MeshInstance3D.new()
		mi.mesh = _tri_mesh(moved, mat_cut if cut["kind"] == "cut" else mat_draft)
		mi.add_child(_lines(feature_edges(moved), Color(0.35, 0.15, 0.6)))
		root.add_child(mi)
	var dest: Vector3 = move_state["ref"] + offsets[offsets.size() - 1]
	_begin_wave(oid, dest, body_tris.get(body, src), false, body)
	for mi in bodies_root.find_children(body, "MeshInstance3D", true, false):
		_attach_wave(oid, mi, mi.get_child(mi.get_child_count() - 1), _base_of(mi))
	last_move_oid = oid
	move_state["last_vec"] = vec
	if guides: guides.mesh = null
	move_state["active"] = false
	overlay.mesh = null
	overlay_lines.mesh = null
	marker.visible = false
	_update_tip(_cursor_pos())
	sync()


func _amend_last_move(txt: String) -> bool:
	"""SketchUp's after-the-fact typing: a distance, Nx / xN / *N (array), or /N (divide)."""
	if last_move_oid == "": return false
	var op: Dictionary = {}
	for o in ops:
		if o["id"] == last_move_oid: op = o
	if op.is_empty(): return false
	var vec := Vector3(op["vector"][0], op["vector"][1], op["vector"][2])
	var count: int = op.get("count", 1)
	var divide: bool = op.get("divide", false)
	var t := txt.strip_edges().to_lower()
	if t.begins_with("/") and t.substr(1).is_valid_int():
		if not op["copy"]: return false
		count = maxi(1, int(t.substr(1))); divide = true
	elif (t.ends_with("x") and t.left(-1).is_valid_int()) or ((t.begins_with("x") or t.begins_with("*")) and t.substr(1).is_valid_int()):
		if not op["copy"]: return false
		count = maxi(1, int(t.trim_suffix("x").trim_prefix("x").trim_prefix("*"))); divide = false
	elif t.is_valid_float():
		# a new distance along the same direction (for an array this sets the spacing; for divide, the total)
		vec = vec.normalized() * absf(float(t))
	else:
		return false
	var body: String = op["cut"]["body"] if op.has("cut") else op["targets"][0]
	var was_copy: bool = op["copy"]
	remove_op(last_move_oid)
	move_copy = was_copy
	var memo: Dictionary = move_memo.get(op["id"], {})
	if memo.is_empty(): return true
	move_state = {"active": false, "body": body, "tris": memo["tris"], "ref": memo["ref"], "cut": memo.get("cut", {})}
	commit_move(vec, count, divide, op["id"])
	return true


# ---------------- mirror tool ----------------
const AXIS_COLORS := [Color(0.85, 0.15, 0.15, 0.16), Color(0.15, 0.65, 0.2, 0.16), Color(0.2, 0.35, 0.95, 0.16)]

static func _axis_vec(ax: int) -> Vector3:
	return [Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)][ax]


func _mirror_click(screen: Vector2) -> void:
	if mirror_state.get("stage", "") != "place":
		var p := pick(screen)
		if not p.get("hit", false) or p["body"] == "": return
		var tris: PackedVector3Array = body_tris.get(p["body"], PackedVector3Array())
		if tris.is_empty(): return
		var lo := Vector3(INF, INF, INF); var hi := -lo
		for q in tris: lo = lo.min(q); hi = hi.max(q)
		var n: Vector3 = p["normal"]
		var ax := 0
		for i in 3:
			if absf(n[i]) > absf(n[ax]): ax = i       # start parallel to the face you clicked
		mirror_state = {"stage": "place", "body": p["body"], "tris": tris, "lo": lo, "hi": hi,
						"axis": ax, "c": hi[ax], "side": 1, "cursor": p["point"],
						"face_ax": ax, "face_c": snappedf(p["point"][ax], 0.01), "face_sign": signf(n[ax])}
		_mirror_move(screen)
	else:
		commit_mirror()


func _mirror_move(screen: Vector2) -> void:
	if mirror_state.get("stage", "") != "place":
		# pick stage: light up the whole board under the cursor
		var hp := pick(screen)
		overlay_lines.mesh = null
		overlay.mesh = _tri_mesh(body_tris[hp["body"]], mat_hover) if hp.get("hit", false) and body_tris.has(hp["body"]) else null
		return
	var p := snap(pick(screen), screen)
	if not p.get("hit", false): return
	_show_marker(p)
	mirror_state["cursor"] = p["point"]
	_mirror_set_plane(p["point"][mirror_state["axis"]])
	_update_vcb()


func _mirror_set_plane(c: float) -> void:
	var ax: int = mirror_state["axis"]
	var mid: float = (mirror_state["lo"][ax] + mirror_state["hi"][ax]) * 0.5
	mirror_state["c"] = c
	mirror_state["side"] = 1 if c >= mid else -1
	var ghost := _mirror_tris(mirror_state["tris"], ax, c)
	var lo: Vector3 = mirror_state["lo"]; var hi: Vector3 = mirror_state["hi"]
	for q in ghost: lo = lo.min(q); hi = hi.max(q)
	var u := (ax + 1) % 3; var v := (ax + 2) % 3
	var corners := PackedVector3Array()
	for uv in [[lo[u] - 60, lo[v] - 60], [hi[u] + 60, lo[v] - 60], [hi[u] + 60, hi[v] + 60], [lo[u] - 60, hi[v] + 60]]:
		var pt := Vector3.ZERO
		pt[ax] = c; pt[u] = uv[0]; pt[v] = uv[1]
		corners.append(pt)
	var pm := mat_plane.duplicate() as StandardMaterial3D
	pm.albedo_color = AXIS_COLORS[ax]
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for q in [corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]]: st.add_vertex(m2g(q))
	var plane_arrays := st.commit_to_arrays()
	var ghost_mesh := _tri_mesh(ghost, mat_draft)
	ghost_mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, plane_arrays)
	ghost_mesh.surface_set_material(1, pm)
	overlay.mesh = ghost_mesh
	var edge_col: Color = AXIS_COLORS[ax]
	edge_col.a = 1.0
	var segs := feature_edges(ghost)
	segs.append_array(PackedVector3Array([corners[0], corners[1], corners[1], corners[2], corners[2], corners[3], corners[3], corners[0]]))
	overlay_lines.mesh = _lines(segs, edge_col.darkened(0.2)).mesh


static func _mirror_tris(tris: PackedVector3Array, ax: int, c: float) -> PackedVector3Array:
	var out := PackedVector3Array()
	for q in tris:
		var m := q
		m[ax] = 2.0 * c - q[ax]
		out.append(m)
	return out


func _mirror_gap() -> float:
	var ax: int = mirror_state["axis"]
	if ax == mirror_state["face_ax"]:
		return (mirror_state["c"] - mirror_state["face_c"]) * mirror_state["face_sign"]   # clicked face -> plane
	return mirror_state["c"] - mirror_state["hi"][ax] if mirror_state["side"] >= 0 else mirror_state["lo"][ax] - mirror_state["c"]


func commit_mirror() -> void:
	if mirror_state.get("stage", "") != "place": return
	reject_note = ""
	var ax: int = mirror_state["axis"]
	var c: float = mirror_state["c"]
	counters["m"] += 1; counters["b"] += 1
	var oid := "m%d" % counters["m"]
	var new_id := "b%d" % counters["b"]
	var pt := Vector3.ZERO
	pt[ax] = c
	var op := {"id": oid, "type": "mirror", "targets": [mirror_state["body"]],
			   "plane": {"point": arr3(pt), "normal": arr3(_axis_vec(ax))}, "new_ids": [new_id]}
	ops.append(op)
	var ghost := _mirror_tris(mirror_state["tris"], ax, c)
	var mi := MeshInstance3D.new()
	mi.mesh = _tri_mesh(ghost, mat_draft)
	var edges := _lines(feature_edges(ghost), Color(0.6, 0.35, 0.0))
	mi.add_child(edges)
	drafts_root.add_child(mi)
	drafts[oid] = mi
	_add_collision(mi, "body_id", new_id)
	body_tris[new_id] = ghost
	body_verts[new_id] = unique_verts(ghost)
	body_edges[new_id] = feature_edges(ghost)
	if test_mode:
		var blo := Vector3(INF, INF, INF); var bhi := -blo
		for q in ghost: blo = blo.min(q); bhi = bhi.max(q)
		draft_bboxes[new_id] = [arr3(blo), arr3(bhi)]
	# the wave starts where the cursor met the plane
	var origin: Vector3 = mirror_state["cursor"]
	origin[ax] = c
	_begin_wave(oid, origin, ghost, true, new_id)
	_attach_wave(oid, mi, edges, DEFAULT_BASE)
	mirror_state = {}
	overlay.mesh = null; overlay_lines.mesh = null
	marker.visible = false
	_update_tip(_cursor_pos())
	sync()


# ---------------- typed input, undo ----------------
func apply_vcb() -> void:
	var txt := vcb.strip_edges()
	vcb = ""
	if txt == "": return
	if tool == "move" and not move_state.get("active", false):
		_amend_last_move(txt)
		_update_vcb()
		return
	if tool == "move" and move_state.get("active", false) and move_mirror:
		if txt.is_valid_float():
			var ax: int = move_state.get("mir_ax", move_state["face_ax"])
			var d := absf(float(txt))
			var side: float = signf(move_state["vec"][ax]) if absf(move_state["vec"][ax]) > 0.5 else move_state["face_sign"]
			var c: float
			if ax == move_state["face_ax"]:
				c = move_state["face_c"] + side * d
			else:
				c = move_state["hi"][ax] + d if side >= 0 else move_state["lo"][ax] - d
			commit_mirror_move(ax, c)
		_update_vcb()
		return
	if tool == "move" and move_state.get("active", false):
		var tl := txt.to_lower()
		if tl.is_valid_float() and move_state["vec"].length() > 0.5:
			commit_move(move_state["vec"].normalized() * absf(float(tl)))
		_update_vcb()
		return
	if tool == "rect" and rect_state.get("active", false):
		var parts := txt.split(",")
		if parts.size() != 2: return
		var w := absf(float(parts[0])); var h := absf(float(parts[1]))
		var su := -1.0 if rect_state["du"] < 0 else 1.0
		var sv := -1.0 if rect_state["dv"] < 0 else 1.0
		commit_rect(w * su, h * sv)
	elif tool == "push" and push_state.get("active", false):
		commit_push(float(txt))
	elif tool == "mirror" and mirror_state.get("stage", "") == "place":
		var d := absf(float(txt))
		var ax: int = mirror_state["axis"]
		var c: float = mirror_state["hi"][ax] + d if mirror_state["side"] >= 0 else mirror_state["lo"][ax] - d
		if ax == mirror_state["face_ax"]:
			c = mirror_state["face_c"] + mirror_state["face_sign"] * d     # measured from the face you clicked
		_mirror_set_plane(c)
		commit_mirror()
	_update_vcb()


func _on_open(resp: Dictionary) -> void:
	if not resp.get("ok", false):
		ui_sync.text = "✗ couldn't open %s: %s" % [model_path, resp.get("error", "?")]
		ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))
		return
	opened = true
	if test_mode and not heavy_test: return
	ops = resp.get("ops", [])
	undo_floor = int(resp.get("undo_floor", 0))
	_restore_counters()
	_rebuild_rect_drafts()
	for op in ops: confirmed_ids[op["id"]] = true     # already in the file: no wave
	sync()
	if resp.get("external", false):
		reject_note = ""
		ui_sync.text = "opened %s - changed in FreeCAD since Shop Sketch last saved it" % model_path.get_file()


func undo() -> void:
	if ops.is_empty(): return
	if ops.size() <= undo_floor:
		ui_sync.text = "✗ can't undo past changes made in FreeCAD (yet)"
		ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))
		return
	remove_op(ops.back()["id"])


func remove_op(oid: String) -> void:
	"""Remove one op (undo, or FreeCAD rejected it) and resync."""
	var idx := -1
	for i in ops.size():
		if ops[i]["id"] == oid: idx = i
	if idx < 0: return
	var op: Dictionary = ops[idx]
	ops.remove_at(idx)
	confirmed_ids.erase(oid)
	_end_wave(oid)
	if drafts.has(oid):
		drafts[oid].queue_free(); drafts.erase(oid)
	if op["type"] == "rect":
		rects.erase(oid)
	elif op["type"] in ["mirror", "move"]:
		for nid in op.get("new_ids", []):
			body_tris.erase(nid); body_verts.erase(nid); body_edges.erase(nid)
	elif op["type"] == "push_pull":
		if op.has("body"):
			body_tris.erase(op["body"]); body_verts.erase(op["body"]); body_edges.erase(op["body"])
		var rid: String = op["target"].get("rect", "")
		if rid != "":
			for r in ops:
				if r["id"] == rid and not _consumed_rects().has(rid):
					rects.erase(rid); _register_rect(r)
	var k := _ops_key(ops)
	if k != shown_key and _show_state(k):      # undo: the state before this op, remembered, on screen at once
		predicted_undo = true
	sync()


func _restore_counters() -> void:
	for op in ops:
		var id: String = op["id"]
		for k in ["pp", "mv", "r", "m"]:
			if id.begins_with(k) and id.substr(k.length()).is_valid_int():
				counters[k] = maxi(counters[k], int(id.substr(k.length())))
				break
		var made: Array = op.get("new_ids", [])
		if op.has("body"): made = [op["body"]]
		for bid in made:
			if String(bid).begins_with("b") and String(bid).substr(1).is_valid_int():
				counters["b"] = maxi(counters["b"], int(String(bid).substr(1)))


func _consumed_rects() -> Dictionary:
	var c := {}
	for op in ops:
		if op["type"] == "push_pull" and op["target"].has("rect"):
			c[op["target"]["rect"]] = true
	return c


func _rebuild_rect_drafts() -> void:
	var used := _consumed_rects()
	for op in ops:
		if op["type"] == "rect":
			if used.has(op["id"]):
				_register_rect_data_only(op)
			elif not drafts.has(op["id"]):
				_register_rect(op)


func _register_rect_data_only(op: Dictionary) -> void:
	_register_rect(op)
	drafts[op["id"]].queue_free(); drafts.erase(op["id"])


# ---------------- worker sync ----------------
func oplog() -> Dictionary:
	return {"format": "oplog/0.1", "units": "mm", "name": "Shop Sketch session", "ops": ops}


func sync() -> void:
	seq += 1
	dirty = true
	ui_sync.text = "● draft - FreeCAD catching up (%d ops)" % ops.size()
	if predicted_undo:
		ui_sync.text = "↶ undone - FreeCAD catching up (%d ops)" % ops.size()
		predicted_undo = false
	ui_sync.add_theme_color_override("font_color", Color(0.75, 0.45, 0.0))
	if not in_flight:
		_send()


func _send(drawing := false) -> void:
	in_flight = true
	dirty = false
	sent_at[seq] = Time.get_ticks_msec()
	sent_clock[seq] = movie_clock
	client.send({"cmd": "sync", "model": model_path, "oplog": oplog(), "outdir": out_dir, "seq": seq,
		"drawing": drawing, "delay_ms": test_delay_ms})
	test_delay_ms = 0


func _on_worker(resp: Dictionary) -> void:
	if resp.get("cmd", "") == "open":
		_on_open(resp)
		return
	if true_latency and resp.get("ok", false) and resp.has("wall_ms") and not resp.get("_released", false):
		held_resp = resp
		return
	in_flight = false
	if not resp.get("ok", false):
		ui_sync.text = "✗ worker error: %s" % resp.get("error", "?")
		ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))
	elif int(resp["seq"]) == seq and not dirty:
		var res: Dictionary = resp["result"]
		var drop_now := []
		for o in res["ops"]:
			var w = op_waves.get(o["id"])
			if o["status"] == "ok":
				confirmed_ids[o["id"]] = true
				if w != null and w["state"] == "pending": w["state"] = "ok"
			else:
				reject_note = "%s: %s" % [o["id"], o["message"]]
				if w != null: w["state"] = "rejected"     # red wave plays, then the op is removed
				else: drop_now.append(o["id"])
		var ok_ids := {}
		for o in res["ops"]:
			if o["status"] == "ok": ok_ids[o["id"]] = true
		var key := _ops_key(ops.filter(func(op): return ok_ids.has(op["id"])))
		if key != shown_key or not _states.has(key):        # already on screen (an undo shown from the cache): no reload
			_load_confirmed(resp["glb"], key)
		for k in drafts.keys():
			var w = op_waves.get(k)
			if w != null and w["state"] == "rejected": continue   # keep it until the red wave is done
			if not rects.has(k) or _consumed_rects().has(k):
				drafts[k].queue_free(); drafts.erase(k)
		last_sync_ms = Time.get_ticks_msec() - int(sent_at.get(seq, Time.get_ticks_msec()))
		if true_latency: last_sync_ms = int((movie_clock - float(sent_clock.get(seq, movie_clock))) * 1000.0)
		ui_sync.text = "✓ FreeCAD confirmed  (round trip %d ms)" % last_sync_ms
		if res.get("how", "") == "rebuilt":
			ui_sync.text = "✓ FreeCAD rebuilt the model (undo past its 20-step history, %d ms)" % last_sync_ms
		ui_sync.add_theme_color_override("font_color", Color(0.1, 0.5, 0.15))
		if reject_note != "":
			ui_sync.text = "✗ rejected " + reject_note
			ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))
		confirmed.emit(seq)
		if resp["result"].has("export_ms") and drawing_pending:
			drawing_pending = false
			_run_drawing_script()
		for oid in drop_now:
			remove_op(oid)
	if dirty and not in_flight:
		_send()


func _load_confirmed(path: String, key: String) -> void:
	_stash_shown()
	body_tris = {}
	body_verts = {}
	body_edges = {}
	var scene: Node3D = Node3D.new()        # empty model (only rectangles so far)
	if FileAccess.get_file_as_bytes(path).size() >= 200:
		var doc := GLTFDocument.new()
		var st := GLTFState.new()
		if doc.append_from_file(path, st) == OK:
			scene = doc.generate_scene(st)
	bodies_root.add_child(scene)
	_load_cuts(path.get_base_dir())
	for mi in scene.find_children("*", "MeshInstance3D", true, false):
		var bid := String(mi.name)
		var arr: Array = mi.mesh.surface_get_arrays(0)
		var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var idx = arr[Mesh.ARRAY_INDEX]
		var xf: Transform3D = mi.transform
		var tris := PackedVector3Array()
		if idx != null and idx.size() > 0:
			for i in idx: tris.append(g2m(xf * v[i]))
		else:
			for p in v: tris.append(g2m(xf * p))
		body_tris[bid] = tris
		body_verts[bid] = unique_verts(tris)
		body_edges[bid] = feature_edges(tris)
		_add_collision(mi, "body_id", bid)
		var edges := _lines(body_edges[bid], Color(0.08, 0.08, 0.08))
		edges.transform = xf.affine_inverse()
		mi.add_child(edges)
		mi.set_meta("body_mesh", true); mi.set_meta("edges", edges)
		var m = mi.mesh.surface_get_material(0)
		if m is StandardMaterial3D:
			m.roughness = 0.85
		# a wave already running for this board carries straight over onto the real mesh
		for oid in op_waves:
			if bid in op_waves[oid]["bodies"]:
				_attach_wave(oid, mi, edges, _base_of(mi))
	_remember_state(key, scene)


# ---------------- confirmed states (T10) ----------------
# The last few model states FreeCAD confirmed, kept as ready scenes. Undo shows the previous one at once, so
# you can keep undoing while FreeCAD catches up, even when it has to rebuild the whole model (its command-line
# program keeps only 20 undo steps). FreeCAD's answer then replaces it; it's the same state, so nothing reloads.
const STATE_CACHE_MAX := 40
var _states := {}             # ops key -> {"scene", "tris", "verts", "edges", "cuts"} (own copies)
var _state_lru: Array = []    # keys, oldest first
var shown_key := ""           # the confirmed state on screen
var predicted_undo := false   # the model on screen is a remembered state; FreeCAD is still catching up


static func _ops_key(list: Array) -> String:
	return JSON.stringify(list).sha256_text()


func _remember_state(key: String, scene: Node3D) -> void:
	if _states.has(key) and _states[key]["scene"] != scene:
		_free_state(key)
	_states[key] = {"scene": scene, "tris": body_tris.duplicate(), "verts": body_verts.duplicate(),
					"edges": body_edges.duplicate(), "cuts": body_cuts.duplicate()}
	_state_lru.erase(key); _state_lru.append(key)
	shown_key = key
	while _state_lru.size() > STATE_CACHE_MAX:
		var old: String = _state_lru.pop_front()
		if old != shown_key: _free_state(old)


func _free_state(key: String) -> void:
	var sc: Node3D = _states[key]["scene"]
	if is_instance_valid(sc) and not sc.is_inside_tree(): sc.queue_free()
	_states.erase(key)
	_state_lru.erase(key)


func _stash_shown() -> void:
	"""Take the confirmed scene off screen; it stays in the cache (or is freed if it isn't cached)."""
	for c in bodies_root.get_children():
		bodies_root.remove_child(c)
		if not (_states.has(shown_key) and _states[shown_key]["scene"] == c):
			c.queue_free()
	shown_key = ""


func _show_state(key: String) -> bool:
	"""Put a cached confirmed state back on screen (undo). False if it isn't cached."""
	if not _states.has(key): return false
	if key == shown_key: return true
	_stash_shown()
	var st: Dictionary = _states[key]
	var scene: Node3D = st["scene"]
	bodies_root.add_child(scene)
	body_tris = st["tris"].duplicate(); body_verts = st["verts"].duplicate()
	body_edges = st["edges"].duplicate(); body_cuts = st["cuts"].duplicate()
	shown_key = key
	_state_lru.erase(key); _state_lru.append(key)
	for mi in scene.find_children("*", "MeshInstance3D", true, false):
		if not mi.has_meta("body_mesh"): continue
		mi.material_override = null                  # a wave that was running when it was stashed is over
		var edges: MeshInstance3D = mi.get_meta("edges")
		if is_instance_valid(edges): edges.material_override = null
		var bid := String(mi.name)
		for oid in op_waves:
			if bid in op_waves[oid]["bodies"]:
				_attach_wave(oid, mi, edges, _base_of(mi))
	return true


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


func _cut_at(bid: String, pt: Vector3) -> Dictionary:
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


func _cut_tris(bid: String, op_id: String) -> PackedVector3Array:
	var out := PackedVector3Array()
	for c in body_cuts.get(bid, []):
		if c["op"] == op_id: out.append_array(_box_tris(c["lo"], c["hi"]))
	return out


func _base_of(mi: MeshInstance3D) -> Color:
	var m = mi.mesh.surface_get_material(0)
	return m.albedo_color if m is StandardMaterial3D else DEFAULT_BASE


# ---------------- operation wave ----------------
const DEFAULT_BASE := Color(0.82, 0.80, 0.76)
const HOLD := 0.6          # fraction of the forward wave that runs before FreeCAD must have answered
const REJECT_DUR := 0.6

var op_waves := {}         # op id -> wave state
var reject_note := ""
var force_reject_next := false
var test_delay_ms := 0     # test hook: ask the worker to sit on its answer
var trace_wave := ""       # test hook: record this op's front over time
var trace_rows: Array[String] = []


func _begin_wave(oid: String, origin_m: Vector3, tris: PackedVector3Array, is_new: bool, body) -> void:
	var og := m2g(origin_m)
	var reach := 0.0
	for p in tris:
		reach = maxf(reach, m2g(p).distance_to(og))
	var dur := clampf(reach / 0.7, 0.5, 1.0)
	op_waves[oid] = {"og": og, "reach": reach, "dur": dur, "tn": 0.0,
					 "p": 0.0, "v": 1.0 / dur, "v1": 1.0 / dur,   # progress (0..1), velocity, and the first smoothing stage
					 "hraw": 0.0, "held": 0.0, "t0": 0.0, "bphase": 0.0,
					 "rt": -1.0, "state": "pending", "new": is_new, "body": body if body is String else "",
					 "bodies": [body] if body is String else body, "links": []}


func _attach_wave(oid: String, mi: MeshInstance3D, edges: MeshInstance3D, base: Color) -> void:
	var w: Dictionary = op_waves[oid]
	var sm := ShaderMaterial.new(); sm.shader = WAVE
	sm.set_shader_parameter("base_color", Color(base.r, base.g, base.b))
	sm.set_shader_parameter("draft_color", Color(mat_draft.albedo_color.r, mat_draft.albedo_color.g, mat_draft.albedo_color.b))
	sm.set_shader_parameter("draft_alpha", mat_draft.albedo_color.a)
	var lm := ShaderMaterial.new(); lm.shader = WAVE_LINES
	lm.set_shader_parameter("width_px", LINE_PX * line_scale)
	lm.set_shader_parameter("bias", overlay_bias)
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


func _end_wave(oid: String) -> void:
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


func _process(delta: float) -> void:
	movie_clock += delta
	_watch_worker(delta)
	if not held_resp.is_empty():
		var waited: float = movie_clock - float(sent_clock.get(int(held_resp["seq"]), movie_clock))
		if waited * 1000.0 >= float(held_resp["wall_ms"]):
			var r := held_resp
			held_resp = {}
			r["_released"] = true
			_on_worker(r)
	for oid in op_waves.keys():
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
			_end_wave(oid)
		elif w["state"] == "rejected" and w["rt"] > REJECT_DUR + 0.1:
			remove_op(oid)                                  # ends the wave, frees the draft, resyncs


# ---------------- the FreeCAD worker (T6) ----------------
# Shop Sketch starts its own worker (freecadcmd worker/replay.py) on a free port, watches it, and starts it
# again if it stops; the request that was lost with it is sent again. On quit the worker saves and stops.
const FREECAD_CANDIDATES := ["/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd",
	"/Applications/FreeCAD.app/Contents/Resources/bin/FreeCADCmd", "/Applications/FreeCAD.app/Contents/MacOS/freecadcmd",
	"/Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd", "/usr/bin/freecadcmd", "/usr/local/bin/freecadcmd"]
const WORKER_MAX_RESTARTS := 5      # in a minute; after that, say so and stop trying
var freecad_path := ""
var worker_script := ""
var worker_log := ""
var worker_port := -1
var worker_pid := -1                # -1: not ours (tests pass --port), or given up
var _worker_restarts: Array = []
var _worker_check := 0.0
var opened := false                 # the worker has answered our "open"
var lifecycle_test := false


func _free_port(from: int) -> int:
	for p in range(from, from + 100):
		var srv := TCPServer.new()
		if srv.listen(p, "127.0.0.1") == OK:
			srv.stop()
			return p
	return from


static func _sh(s: String) -> String:
	return "'" + s.replace("'", "'\\''") + "'"


func _start_worker() -> void:
	if freecad_path == "":
		for c in FREECAD_CANDIDATES:
			if FileAccess.file_exists(c): freecad_path = c; break
	if worker_script == "":
		worker_script = ProjectSettings.globalize_path("res://").path_join("../worker/replay.py").simplify_path()
	if worker_log == "":
		worker_log = ProjectSettings.globalize_path("user://worker.log")
	if freecad_path == "" or not FileAccess.file_exists(worker_script):
		_say_worker("✗ couldn't find FreeCAD's command-line program (freecadcmd) or worker/replay.py")
		worker_pid = -1
		return
	if OS.get_name() == "Windows":
		OS.set_environment("SERVE_PORT", str(worker_port))
		worker_pid = OS.create_process(freecad_path, [worker_script])
	else:
		worker_pid = OS.create_process("/bin/sh", ["-c", "SERVE_PORT=%d exec %s %s >> %s 2>&1" % [
			worker_port, _sh(freecad_path), _sh(worker_script), _sh(worker_log)]])
	print("SHOPSKETCH worker pid %d on port %d (log %s)" % [worker_pid, worker_port, worker_log])


func _watch_worker(delta: float) -> void:
	if worker_pid <= 0: return
	_worker_check -= delta
	if _worker_check > 0.0: return
	_worker_check = 1.0
	if OS.is_process_running(worker_pid): return
	var now := Time.get_ticks_msec()
	_worker_restarts = _worker_restarts.filter(func(t): return now - t < 60000)
	_worker_restarts.append(now)
	if _worker_restarts.size() > WORKER_MAX_RESTARTS:
		_say_worker("✗ the FreeCAD worker keeps stopping - see %s" % worker_log)
		worker_pid = -1
		return
	_say_worker("✗ the FreeCAD worker stopped - starting it again")
	_start_worker()


func _say_worker(txt: String) -> void:
	ui_sync.text = txt
	ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))


func _send_open() -> void:
	client.send({"cmd": "open", "model": model_path, "fresh": test_mode and not heavy_test and not opened})


func _on_link_down() -> void:
	if worker_pid > 0 or opened:
		_say_worker("● lost the FreeCAD worker - reconnecting")


func _on_link_up(first: bool) -> void:
	if first: return
	# a new worker (or the same one back): whatever was in flight is gone, so send the model again
	in_flight = false
	if not opened:
		_send_open()
	else:
		sync()


func _shutdown_worker() -> void:
	if worker_pid <= 0 or not OS.is_process_running(worker_pid): return
	client.send({"cmd": "quit"})            # it saves anything pending, then stops
	var t0 := Time.get_ticks_msec()
	while OS.is_process_running(worker_pid) and Time.get_ticks_msec() - t0 < 4000:
		client.peer.poll()
		OS.delay_msec(50)
	if OS.is_process_running(worker_pid):
		OS.kill(worker_pid)
	worker_pid = -1


func _exit_tree() -> void:
	_shutdown_worker()


# ---------------- drawing export ----------------
var drawing_pending := false

func export_drawing() -> void:
	drawing_pending = true
	seq += 1
	if not in_flight:
		_send(true)
	else:
		dirty = true


func _run_drawing_script() -> void:
	if drawing_script == "":
		ui_sync.text = "drawing page saved in model.FCStd (no --drawing script given for PDF)"
		return
	var out := []
	var code := OS.execute("python3", [drawing_script, out_dir, model_path.get_basename() + ".shopsketch.json"], out, true)
	ui_sync.text = ("✓ drawing written to %s/drawing.pdf" % out_dir) if code == 0 else ("✗ drawing failed: %s" % str(out))


# ---------------- input ----------------
func _unhandled_input(e: InputEvent) -> void:
	if e is InputEventMouseButton:
		if e.button_index in [MOUSE_BUTTON_MIDDLE, MOUSE_BUTTON_RIGHT]:
			orbiting = e.pressed and not e.shift_pressed
			panning = e.pressed and e.shift_pressed
		elif e.button_index == MOUSE_BUTTON_WHEEL_UP and e.pressed:
			_zoom(0.88, e.position)
		elif e.button_index == MOUSE_BUTTON_WHEEL_DOWN and e.pressed:
			_zoom(1.0 / 0.88, e.position)
		elif e.button_index == MOUSE_BUTTON_LEFT and e.pressed:
			tool_click(e.position)
	elif (e is InputEventPanGesture or e is InputEventMagnifyGesture) and _repeat_gesture(e):
		return       # Godot 4.6 hands an injected gesture over twice in the same frame (seen in tests); act once
	elif e is InputEventPanGesture:
		# trackpad (and Magic Mouse) two-finger drag: orbit; with Shift, pan. A wheel mouse sends wheel buttons instead.
		if e.shift_pressed:
			var k := dist * 0.0012 * TRACKPAD_PX
			target += (-cam.global_transform.basis.x * e.delta.x + cam.global_transform.basis.y * e.delta.y) * k
		else:
			yaw -= e.delta.x * 0.008 * TRACKPAD_PX
			pitch = clampf(pitch - e.delta.y * 0.008 * TRACKPAD_PX, -1.5, 1.5)
		_update_camera()
	elif e is InputEventMagnifyGesture:
		_zoom(1.0 / maxf(e.factor, 0.01), e.position)      # pinch out = closer, toward the cursor
	elif e is InputEventMouseMotion:
		if orbiting:
			yaw -= e.relative.x * 0.008
			pitch = clampf(pitch - e.relative.y * 0.008, -1.5, 1.5)
			_update_camera()
		elif panning:
			var k := dist * 0.0012
			target += (-cam.global_transform.basis.x * e.relative.x + cam.global_transform.basis.y * e.relative.y) * k
			_update_camera()
		else:
			tool_move(e.position)
	elif e is InputEventKey and e.pressed and not e.echo:
		if (e.ctrl_pressed or e.meta_pressed) and e.keycode == KEY_Z: undo(); return    # Cmd+Z on a Mac
		match e.keycode:
			KEY_ESCAPE: set_tool(tool); return
			KEY_ENTER, KEY_KP_ENTER: apply_vcb(); return
			KEY_BACKSPACE: vcb = vcb.left(-1); _update_vcb(); return
		var ch := char(e.unicode) if e.unicode > 0 else ""
		var busy: bool = rect_state.get("active", false) or push_state.get("active", false) or mirror_state.get("stage", "") == "place" \
			or (tool == "move" and (move_state.get("active", false) or last_move_oid != ""))
		if tool == "move" and e.keycode in [KEY_CTRL, KEY_ALT, KEY_SHIFT]:
			if e.keycode == KEY_SHIFT:
				move_mirror = not move_mirror            # Shift: mirror across the plane halfway to the cursor
			else:
				move_copy = not move_copy                # SketchUp: tap Ctrl (Option on a Mac) to toggle copy
			if move_state.get("active", false): _move_move(_cursor_pos())
			_update_vcb(); _update_tip(_cursor_pos())
			return
		if tool == "move" and move_state.get("active", false):
			var lock: int = {KEY_RIGHT: 0, KEY_LEFT: 1, KEY_UP: 2}.get(e.keycode, -2)
			if lock > -2:
				var mode: String = move_state.get("lock_mode", "free")
				if move_state["lock"] != lock or mode == "free":
					move_state["lock"] = lock; move_state["lock_mode"] = "axis"
				elif mode == "axis":
					move_state["lock_mode"] = "plane"          # tap again: the plane perpendicular to that axis
				else:
					move_state["lock"] = -1; move_state["lock_mode"] = "free"
				_move_move(_cursor_pos())
				_update_tip(_cursor_pos())
				return
		if tool == "mirror" and mirror_state.get("stage", "") == "place":
			var new_axis: int = {KEY_RIGHT: 0, KEY_LEFT: 1, KEY_UP: 2}.get(e.keycode, -1)
			if new_axis >= 0:
				mirror_state["axis"] = new_axis
				_mirror_move(cursor2d.position if test_mode and cursor2d != null else get_viewport().get_mouse_position())
				return
		if busy and ch != "" and (ch in "0123456789.,-" or (tool == "move" and ch.to_lower() in "x*/")):
			vcb += ch; _update_vcb(); return
		match e.keycode:
			KEY_R: set_tool("rect")
			KEY_P: set_tool("push")
			KEY_M: set_tool("move")
			KEY_G: grid_snap = not grid_snap; _update_toggles()
			KEY_B: new_board = not new_board; _update_toggles()
			KEY_D: export_drawing()


var _last_gesture := ""


func _repeat_gesture(e: InputEventGesture) -> bool:
	var amount: Variant = e.delta if e is InputEventPanGesture else e.factor
	var sig := "%d|%s|%s|%s|%s" % [Engine.get_process_frames(), e.get_class(), amount, e.position, e.shift_pressed]
	if sig == _last_gesture: return true
	_last_gesture = sig
	return false


const TRACKPAD_PX := 33.0     # Godot scales a trackpad's scroll by 0.03: this makes one finger-pixel = one mouse-pixel


func _zoom(f: float, screen: Vector2) -> void:
	var p := pick(screen)
	if p.get("hit", false) and f < 1.0:
		target = target.lerp(m2g(p["point"]), 0.12)
	dist = clampf(dist * f, 0.05, 50.0)
	_update_camera()


func _update_camera() -> void:
	var off := Vector3(0, 0, dist).rotated(Vector3.RIGHT, pitch).rotated(Vector3.UP, yaw)
	cam.position = target + off
	cam.look_at(target, Vector3.UP)
	if grid_mat != null:       # the grid fades out past a few orbit distances (no shimmer toward the horizon)
		grid_mat.set_shader_parameter("fade_start", dist * 1.5 + 0.5)
		grid_mat.set_shader_parameter("fade_end", dist * 3.5 + 1.5)
