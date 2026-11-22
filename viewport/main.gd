extends Node3D
## Shop Sketch: tool-first viewport. Records an op log; FreeCAD (worker) catches up.
## Model space = Z-up millimetres (what the op log uses). Godot space = Y-up metres.

const WorkerClient := preload("res://worker_client.gd")
const Units := preload("res://units.gd")
const LINE_SHADER := preload("res://line.gdshader")
const Geo := preload("res://tool_geometry.gd")
const Inference := preload("res://inference.gd")
const Presenter := preload("res://presenter.gd")
const GRID := Inference.GRID          # the grid and snap settings are inference's (T88); old names for consumers
const SNAP_PX := Inference.SNAP_PX

# ---------------- state ----------------
# The model's actions and their sync with FreeCAD live in the document controller (document.gd, A31, T39). These
# names forward to it, so tools and tests can keep writing m.ops, m.counters, m.seq.
const Document := preload("res://document.gd")
var doc: Document = Document.new()
var ops: Array:
	get: return doc.ops
	set(v): doc.ops = v
var counters: Dictionary:
	get: return doc.counters
var seq: int:
	get: return doc.seq
var in_flight: bool:
	get: return doc.in_flight
var dirty: bool:
	get: return doc.dirty
var last_sync_ms: int:
	get: return doc.last_sync_ms
var model_path: String:       # the FreeCAD file: the model itself (A21)
	get: return doc.model_path
	set(v): doc.model_path = v
var out_dir: String:
	get: return doc.out_dir
	set(v): doc.out_dir = v
var undo_floor: int:
	get: return doc.undo_floor
var confirmed_ids: Dictionary:  # op ids FreeCAD has already confirmed
	get: return doc.confirmed_ids
var opened: bool:             # the worker has answered our "open"
	get: return doc.opened
var pending_rev: int:
	get: return doc.pending_rev
var saved_rev: int:
	get: return doc.saved_rev
var redo_stack: Array:
	get: return doc.redo_stack
var test_delay_ms: int:       # test hook: ask the worker to sit on its answer
	get: return doc.test_delay_ms
	set(v): doc.test_delay_ms = v
var tool := "rect"
var grid_snap := true
var new_board := false       # a rectangle on a face joins that board when pushed out (I04b); B for a separate board
# The measurements box (typed values, `typing`, lengths FreeCAD is working out) lives in measure_box.gd (T75);
# these names forward to it, so tools and tests keep writing m.vcb, m.apply_vcb().
var measure = load("res://measure_box.gd").new()
var vcb: String:
	get: return measure.vcb
	set(v): measure.vcb = v
var typing: bool:                   # the measurements box has Delete/Backspace (I48)
	get: return measure.typing
	set(v): measure.typing = v
var length_id: int:
	get: return measure.length_id
var length_pending: Dictionary:     # a length FreeCAD is working out
	get: return measure.length_pending
	set(v): measure.length_pending = v
var ui_vcb: Label:
	get: return measure.ui_value
var ui_vcb_label: Label:
	get: return measure.ui_label
var ui_vcb_box: PanelContainer:
	get: return measure.ui_box
func _update_vcb() -> void: measure.update()
func apply_vcb() -> void: measure.apply()
func _on_length(resp: Dictionary) -> void: measure.on_length(resp)

var oplog_path := ""
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

# What's on screen (boards' triangles, corners, edges and cuts; drafts; confirmed boards; remembered states; waves)
# lives in the presenter (presenter.gd, A33b, T41). These names forward to it, so tools and tests keep m.body_tris.
var pres = Presenter.new()
var body_tris: Dictionary:          # body id -> PackedVector3Array (model mm, 3 per tri)
	get: return pres.body_tris
var body_verts: Dictionary:         # body id -> PackedVector3Array (unique corners)
	get: return pres.body_verts
var body_edges: Dictionary:         # body id -> feature edge segments (model mm)
	get: return pres.body_edges
var body_cuts: Dictionary:          # body id -> [{op, kind, lo, hi}] from FreeCAD: holes and added pieces
	get: return pres.body_cuts
var rects: Dictionary:              # rect id -> {"tris","n","on","pts"}
	get: return pres.rects
var drafts: Dictionary:             # op id -> Node3D
	get: return pres.drafts
var stock_frames: Dictionary:       # body id -> rectangular stock frame (plane fits, I40)
	get: return pres.stock_frames
var op_waves: Dictionary:           # op id -> wave state
	get: return pres.op_waves
var shown_key: String:              # the confirmed state on screen
	get: return pres.shown_key
var predicted_undo: bool:           # the model on screen is a remembered state; FreeCAD is still catching up
	get: return pres.predicted_undo
	set(v): pres.predicted_undo = v
var trace_wave: String:             # test hook: record this op's front over time
	get: return pres.trace_wave
	set(v): pres.trace_wave = v
var trace_rows: Array[String]:
	get: return pres.trace_rows
func _register_rect(op: Dictionary) -> void: pres.register_rect(op)
func _begin_wave(oid: String, origin_m: Vector3, tris: PackedVector3Array, is_new: bool, body) -> void:
	pres.begin_wave(oid, origin_m, tris, is_new, body)
func _attach_wave(oid: String, mi: MeshInstance3D, edges: MeshInstance3D, base: Color) -> void:
	pres.attach_wave(oid, mi, edges, base)
func _end_wave(oid: String) -> void: pres.end_wave(oid)
func _show_state(key: String) -> bool: return pres.show_state(key)
func _cut_at(bid: String, pt: Vector3) -> Dictionary: return pres.cut_at(bid, pt)
func _cut_tris(bid: String, op_id: String) -> PackedVector3Array: return pres.cut_tris(bid, op_id)
func _base_of(mi: MeshInstance3D) -> Color: return pres.base_of(mi)


func _make_presenter() -> void:
	pres.name = "Presenter"
	pres.m = self
	pres.sel = sel
	add_child(pres)
	pres.boards_read.connect(_on_boards_read)
	pres.wave_rejected_done.connect(_on_wave_rejected_done)


var fx_points := {}           # op id -> model point where the operation ended (wave origin)
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
var snap_test := false
var rect_test := false
var perf_test := false
var shell_test := false
var join_test := false
var reject_test := false
var quick_test := false
var fast_test := false    # --fast: any suite at the quick test's pace (T48; not for recordings)
const OVERLAY_BIAS := 0.001   # overlays sit 0.1% of the camera distance nearer the eye (invisible, beats z-fighting)
var overlay_bias := OVERLAY_BIAS
var grid_mat: ShaderMaterial
var caption: Label
var draft_bboxes := {}     # test: new body id -> [min, max] of its draft prism (model mm)
var preload_path := ""
var cursor2d: Node2D

var client: Node
var properties_panel: PanelContainer
var properties_request := 0
var properties_seq := -1

var ui_hint: Label
var ui_sync: Label
var ui_tip: Label

signal confirmed(seq_no: int)

var mat_draft: StandardMaterial3D
var mat_cut: StandardMaterial3D
var mat_rect: ShaderMaterial
var mat_hover: ShaderMaterial
var mat_cut_hl: ShaderMaterial    # hole highlight in Move
var mat_sibling: ShaderMaterial   # linked copies of the board you're editing
var mat_selected: ShaderMaterial  # selected boards
var mat_plane: StandardMaterial3D  # mirror-plane visuals
var mat_edge: StandardMaterial3D
var mat_draft_edge: StandardMaterial3D


# ---------------- coordinates ----------------
# The pure functions live in tool_geometry.gd (T88 step 0); these wrappers keep the old names for main.gd, the
# presenter, panels and tests until each moves to Geo itself.
static func m2g(p: Vector3) -> Vector3: return Geo.m2g(p)
static func g2m(p: Vector3) -> Vector3: return Geo.g2m(p)
static func n_g2m(n: Vector3) -> Vector3: return Geo.n_g2m(n)
static func r3(x: float) -> float: return Geo.r3(x)
static func arr3(v: Vector3) -> Array: return Geo.arr3(v)
static func clean_normal(n: Vector3) -> Vector3: return Geo.clean_normal(n)
static func plane_basis(n: Vector3) -> Array: return Geo.plane_basis(n)

# ---------------- setup ----------------
func _ready() -> void:
	_make_presenter()
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
		elif a == "--fast": fast_test = true
		elif a == "--zfighttest": test_mode = true; fx_test = true; zfight_test = true
		elif a == "--holetest": test_mode = true; fx_test = true; hole_test = true
		elif a == "--linetest": test_mode = true; fx_test = true; line_test = true
		elif a == "--undotest": test_mode = true; fx_test = true; undo_test = true
		elif a == "--gesturetest": test_mode = true; fx_test = true; gesture_test = true
		elif a == "--snaptest": test_mode = true; fx_test = true; snap_test = true
		elif a == "--recttest": test_mode = true; fx_test = true; rect_test = true
		elif a == "--perftest": test_mode = true; fx_test = true; perf_test = true
		elif a == "--shelltest": test_mode = true; fx_test = true; shell_test = true
		elif a == "--jointest": test_mode = true; fx_test = true; join_test = true
		elif a == "--rejecttest": test_mode = true; fx_test = true; reject_test = true
		elif a == "--quicktest": test_mode = true; fx_test = true; quick_test = true
		elif a == "--lifecycletest": test_mode = true; fx_test = true; lifecycle_test = true
		elif a == "--nobias": overlay_bias = 0.0
		elif a.begins_with("--preload="): preload_path = a.substr(10)
	if oplog_path == "": oplog_path = ProjectSettings.globalize_path("user://ops.json")
	out_root = out_dir if out_dir != "" else ProjectSettings.globalize_path("user://out")
	if model_path == "":
		model_path = (out_root + "/model.FCStd") if test_mode else _last_model()
	out_dir = out_root if test_mode else _out_for(model_path)
	DirAccess.make_dir_recursive_absolute(out_dir)
	if drawing_script == "" and not test_mode:
		drawing_script = _beside_project("worker/drawing.py")
	var port := -1                 # --port=N: use a worker that's already running there (tests); else start our own
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--port="): port = int(a.substr(7))
		elif a.begins_with("--freecad="): freecad_path = a.substr(10)
		elif a.begins_with("--worker="): worker_script = a.substr(9)
		elif a.begins_with("--worker-log="): worker_log = a.substr(13)
		elif a.begins_with("--shared-port="): SHARED_PORT = int(a.substr(14))
	if port < 0:
		port = _pick_worker()

	line_scale = maxf(1.0, DisplayServer.screen_get_scale())
	get_window().content_scale_factor = line_scale        # the interface at its proper size on a Retina screen
	_make_materials()
	_make_world()
	_make_tools()                 # after the world: inference and the tool context take the camera and overlays
	_make_keys()
	_make_ui()
	_make_menus()
	_set_title()
	if not test_mode: _remember_model(model_path)
	client = WorkerClient.new()
	add_child(client)
	doc.name = "Document"
	doc.client = client
	doc.start_fresh = test_mode and not heavy_test
	add_child(doc)
	doc.sync_started.connect(_on_sync_started)
	doc.sent.connect(func(n: int): sent_clock[n] = movie_clock)
	doc.synced.connect(_on_synced)
	doc.sync_failed.connect(_on_sync_failed)
	doc.save_changed.connect(_update_saved)
	doc.close_ready.connect(_close_now)
	doc.close_blocked.connect(_ask_close)
	get_tree().set_auto_accept_quit(false)       # closing waits for the latest save first (I55, _request_close)
	doc.op_removed.connect(_on_op_removed)
	doc.removed.connect(_on_removed)
	doc.idle.connect(_request_properties)
	_make_selection()
	client.replied.connect(_on_worker)
	client.link_up.connect(_on_link_up)
	client.link_down.connect(_on_link_down)
	if port == 0 and _port_file != "":
		port = _await_port_file()                   # the worker has been starting while the window was built
		worker_port = port
	client.start(port)
	_update_camera()
	_warm_up_previews()
	set_tool("rect")
	# open the model file; the worker answers with its history, which we adopt (tests start clean)
	_send_open()
	if test_mode:                     # scripted tests live in tests.gd (T4)
		var t: Node = load("res://tests.gd").new()
		t.name = "Tests"
		t.m = self
		add_child(t)
		t.run.call_deferred()


func _warm_up_previews() -> void:
	"""Draw every preview material once, too small to see, so the first drag with each tool doesn't stall
	~100 ms while the renderer prepares it (measured on the first Rectangle and Push/Pull drags)."""
	var tri := PackedVector3Array([Vector3(0, 0, 0), Vector3(0.001, 0, 0), Vector3(0, 0.001, 0)])
	var holder := Node3D.new()
	holder.position = Vector3(0, 0, -0.5)          # in front of the camera, a speck far below a pixel
	cam.add_child(holder)
	var mats: Array = [mat_draft, mat_cut, mat_plane, mat_rect, mat_hover, mat_cut_hl, mat_sibling, mat_selected]
	for mat in mats:
		var mi := MeshInstance3D.new()
		var am := ArrayMesh.new()
		var arr := []; arr.resize(Mesh.ARRAY_MAX); arr[Mesh.ARRAY_VERTEX] = tri
		arr[Mesh.ARRAY_NORMAL] = PackedVector3Array([Vector3.BACK, Vector3.BACK, Vector3.BACK])
		am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
		am.surface_set_material(0, mat)
		mi.mesh = am
		holder.add_child(mi)
	var ahead := g2m(cam.global_position - cam.global_transform.basis.z * 0.5)
	var lines := _lines(PackedVector3Array([ahead, ahead + Vector3(0.001, 0, 0)]), Color(0.6, 0.35, 0.0))
	add_child(lines)
	for i in 3: await get_tree().process_frame
	holder.queue_free(); lines.queue_free()


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
	mat_sibling = _overlay_mat(Color(0.25, 0.55, 1.0, 0.22))      # linked copies, while you edit one
	mat_selected = _overlay_mat(Color(0.1, 0.45, 1.0, 0.35))      # what the Select tool picked
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
	if RenderingServer.get_current_rendering_method() != "gl_compatibility":
		# Forward+ (Metal) tone-maps the background: this renders the same colour as before
		env.background_color = Color(0.835, 0.88, 0.94)
		env.background_energy_multiplier = 0.9
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


# ---------------- interface (T24: Mac-like) ----------------
# System font, macOS colours (light or dark, your accent colour), a segmented control for the tools,
# push buttons, a quiet status bar and a measurements field that lights up while you type.
var dark := false
var accent := Color(0.0, 0.48, 1.0)
var _tool_buttons := {}
var _toggle_buttons := {}
var ui_saved: Label                 # quiet 'Saving…' / 'Saved' (Q22): the wave means accepted, this means on disk


var saved_shown: Array = []         # tests: what the indicator has said, in order (T45: fast saves can't be missed)


func _update_saved() -> void:
	if ui_saved == null: return
	if doc.save_error != "":            # stays until a save lands (I54); the worker retries on the next change
		ui_saved.text = "Couldn't save: %s" % doc.save_error
		ui_saved.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))
	else:
		ui_saved.text = "Saving…" if pending_rev > saved_rev else "Saved"
		ui_saved.remove_theme_color_override("font_color")
	if test_mode and (saved_shown.is_empty() or saved_shown.back() != ui_saved.text): saved_shown.append(ui_saved.text)


func _c(light: Color, dark_c: Color) -> Color:
	return dark_c if dark else light


func _box(bg: Color, radius := 6, border := Color(0, 0, 0, 0), bw := 0, pad := Vector2(10, 4)) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.set_corner_radius_all(radius)
	if bw > 0:
		s.border_color = border
		s.set_border_width_all(bw)
	s.content_margin_left = pad.x; s.content_margin_right = pad.x
	s.content_margin_top = pad.y; s.content_margin_bottom = pad.y
	s.anti_aliasing = true
	return s


func _make_theme() -> Theme:
	var t := Theme.new()
	var f := SystemFont.new()
	f.font_names = PackedStringArray([".AppleSystemUIFont", "SF Pro Text", "Helvetica Neue", "Arial"])
	t.default_font = f
	t.default_font_size = 13
	var text := _c(Color(0.11, 0.11, 0.12), Color(0.92, 0.92, 0.93))
	t.set_color("font_color", "Label", text)
	for st in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_focus_color"]:
		t.set_color(st, "Button", text)
	# push buttons
	var edge := _c(Color(0.77, 0.77, 0.79), Color(0.36, 0.36, 0.38))
	t.set_stylebox("normal", "Button", _box(_c(Color(1, 1, 1), Color(0.36, 0.36, 0.38)), 6, edge, 1, Vector2(12, 3)))
	t.set_stylebox("hover", "Button", _box(_c(Color(0.97, 0.97, 0.98), Color(0.4, 0.4, 0.42)), 6, edge, 1, Vector2(12, 3)))
	t.set_stylebox("pressed", "Button", _box(_c(Color(0.86, 0.86, 0.88), Color(0.46, 0.46, 0.48)), 6, edge, 1, Vector2(12, 3)))
	t.set_stylebox("hover_pressed", "Button", t.get_stylebox("pressed", "Button"))
	t.set_stylebox("focus", "Button", StyleBoxEmpty.new())
	# segments: flat inside a grey track; the selected one is a raised white tile
	t.set_type_variation("Segment", "Button")
	var flat := _box(Color(0, 0, 0, 0), 5, Color(0, 0, 0, 0), 0, Vector2(11, 3))
	var hov := _box(_c(Color(0, 0, 0, 0.05), Color(1, 1, 1, 0.06)), 5, Color(0, 0, 0, 0), 0, Vector2(11, 3))
	var sel := _box(_c(Color(1, 1, 1), Color(0.43, 0.43, 0.46)), 5, Color(0, 0, 0, 0), 0, Vector2(11, 3))
	sel.shadow_color = Color(0, 0, 0, 0.18); sel.shadow_size = 2; sel.shadow_offset = Vector2(0, 1)
	t.set_stylebox("normal", "Segment", flat)
	t.set_stylebox("hover", "Segment", hov)
	t.set_stylebox("pressed", "Segment", sel)
	t.set_stylebox("hover_pressed", "Segment", sel)
	t.set_stylebox("focus", "Segment", StyleBoxEmpty.new())
	t.set_type_variation("Quiet", "Label")
	t.set_color("font_color", "Quiet", _c(Color(0.43, 0.43, 0.45), Color(0.62, 0.62, 0.65)))
	t.set_font_size("font_size", "Quiet", 11)
	return t


func _segments(items: Array, toggles: bool) -> PanelContainer:
	var track := PanelContainer.new()
	track.add_theme_stylebox_override("panel", _box(_c(Color(0.86, 0.86, 0.88), Color(0.24, 0.24, 0.26)), 7, Color(0, 0, 0, 0), 0, Vector2(2, 2)))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 2)
	track.add_child(row)
	var group := ButtonGroup.new()
	for it in items:
		var b := Button.new()
		b.text = it[0]; b.tooltip_text = it[2]
		b.theme_type_variation = "Segment"
		b.toggle_mode = true
		b.focus_mode = Control.FOCUS_NONE
		if not toggles: b.button_group = group
		b.pressed.connect(_menu.bind(it[1]))
		row.add_child(b)
		(_toggle_buttons if toggles else _tool_buttons)[it[1]] = b
	return track


func _make_ui() -> void:
	dark = DisplayServer.is_dark_mode_supported() and DisplayServer.is_dark_mode()
	for a in OS.get_cmdline_user_args():
		if a == "--appearance=light": dark = false
		elif a == "--appearance=dark": dark = true
	var ac := DisplayServer.get_accent_color()
	if ac.a > 0.0: accent = ac
	var layer := CanvasLayer.new()
	add_child(layer)
	var root := Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = _make_theme()
	layer.add_child(root)
	# toolbar
	var bar := PanelContainer.new()
	bar.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	var bar_style := _box(_c(Color(0.93, 0.93, 0.94), Color(0.17, 0.17, 0.18)), 0, Color(0, 0, 0, 0), 0, Vector2(10, 7))
	bar_style.border_width_bottom = 1; bar_style.border_color = _c(Color(0.8, 0.8, 0.82), Color(0.07, 0.07, 0.08))
	bar.add_theme_stylebox_override("panel", bar_style)
	root.add_child(bar)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	bar.add_child(row)
	row.add_child(_segments(tool_list.map(func(t): return [t["label"], t["id"], t["tip"]]), false))   # tool_registry.gd
	for spec in [["Undo", "undo", "Undo (⌘Z)"], ["Redo", "redo", "Redo (⇧⌘Z)"], ["Drawing", "drawing", "Drawing and cut list (D)"]]:
		var b := Button.new(); b.text = spec[0]; b.tooltip_text = spec[2]; b.focus_mode = Control.FOCUS_NONE
		b.pressed.connect(_menu.bind(spec[1]))
		row.add_child(b)
	var gap := Control.new(); gap.size_flags_horizontal = Control.SIZE_EXPAND_FILL; gap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(gap)
	row.add_child(_segments([["Grid snap", "grid", "Snap to a 10 mm grid (G)"], ["New board", "newboard", "Pushing a profile drawn on a face makes a separate board (B)"]], true))
	var properties_button := Button.new()
	properties_button.text = "Properties"
	properties_button.focus_mode = Control.FOCUS_NONE
	properties_button.pressed.connect(func():
		properties_panel.visible = not properties_panel.visible
		if properties_panel.visible: _request_properties())
	row.add_child(properties_button)
	properties_panel = load("res://property_panel.gd").new()
	root.add_child(properties_panel)
	properties_panel.set_anchors_and_offsets_preset(Control.PRESET_RIGHT_WIDE)
	properties_panel.offset_left = -360
	properties_panel.offset_right = -10
	properties_panel.offset_top = 60
	properties_panel.offset_bottom = -45
	properties_panel.add_theme_stylebox_override("panel", _box(_c(Color(0.96, 0.96, 0.97), Color(0.17, 0.17, 0.18)), 8, _c(Color(0.7, 0.7, 0.72), Color(0.3, 0.3, 0.32)), 1, Vector2(12, 10)))
	properties_panel.hide()
	properties_panel.refresh_requested.connect(_request_properties)
	properties_panel.edit_requested.connect(_edit_property)
	var fit_outline := MeshInstance3D.new()          # the plane-fit preview (I40)
	add_child(fit_outline)
	properties_panel.preview_changed.connect(func(lines: PackedVector3Array):
		fit_outline.mesh = null
		if not lines.is_empty():
			var outline := _lines(lines, Color(0.9, 0.4, 0.05))
			fit_outline.mesh = outline.mesh
			outline.free())
	# status bar with the measurements field
	var status := PanelContainer.new()
	status.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	status.grow_vertical = Control.GROW_DIRECTION_BEGIN          # grow up from the bottom edge
	var st_style := _box(_c(Color(0.95, 0.95, 0.96), Color(0.15, 0.15, 0.16)), 0, Color(0, 0, 0, 0), 0, Vector2(12, 4))
	st_style.border_width_top = 1; st_style.border_color = _c(Color(0.82, 0.82, 0.84), Color(0.07, 0.07, 0.08))
	status.add_theme_stylebox_override("panel", st_style)
	root.add_child(status)
	var srow := HBoxContainer.new()
	srow.add_theme_constant_override("separation", 14)
	status.add_child(srow)
	ui_hint = Label.new(); ui_hint.theme_type_variation = "Quiet"; ui_hint.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	ui_hint.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS; ui_hint.clip_text = true
	ui_sync = Label.new(); ui_sync.theme_type_variation = "Quiet"; ui_sync.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	ui_sync.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS; ui_sync.clip_text = true
	ui_saved = Label.new(); ui_saved.theme_type_variation = "Quiet"
	srow.add_child(ui_hint); srow.add_child(ui_sync); srow.add_child(ui_saved)
	measure.name = "MeasureBox"
	measure.m = self
	add_child(measure)
	measure.build(srow)
	# tooltip by the cursor
	ui_tip = Label.new()
	ui_tip.add_theme_font_size_override("font_size", 11)
	var tip := _box(_c(Color(1, 1, 1, 0.97), Color(0.2, 0.2, 0.22, 0.97)), 6, _c(Color(0.78, 0.78, 0.8), Color(0.33, 0.33, 0.35)), 1, Vector2(8, 4))
	tip.shadow_color = Color(0, 0, 0, 0.18); tip.shadow_size = 4; tip.shadow_offset = Vector2(0, 2)
	ui_tip.add_theme_stylebox_override("normal", tip)
	ui_tip.visible = false
	root.add_child(ui_tip)
	_update_toggles()


func _update_toggles() -> void:
	_update_menu_checks()
	if _toggle_buttons.has("grid"): _toggle_buttons["grid"].set_pressed_no_signal(grid_snap)
	if _toggle_buttons.has("newboard"): _toggle_buttons["newboard"].set_pressed_no_signal(new_board)


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


static func _ekey(p: Vector3, q: Vector3) -> String: return Geo.edge_key(p, q)
static func feature_edges(tris: PackedVector3Array) -> PackedVector3Array: return Geo.feature_edges(tris)
static func unique_verts(tris: PackedVector3Array) -> PackedVector3Array: return Geo.unique_verts(tris)
static func prism(tris: PackedVector3Array, n: Vector3, d: float) -> PackedVector3Array: return Geo.prism(tris, n, d)
static func prism_by(tris: PackedVector3Array, offset: Callable) -> PackedVector3Array: return Geo.prism_by(tris, offset)

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
func _show_marker(p: Dictionary) -> void:
	marker.visible = p.get("hit", false)
	if marker.visible:
		marker.position = m2g(p["point"])
		var col: Color = SNAP_COLORS.get(p.get("snap", ""), Color(0.35, 0.35, 0.4))
		(marker.mesh.material as StandardMaterial3D).albedo_color = col


# ---------------- tools ----------------
# Each tool is its own object in tools/ (T4); they all snap through inference.gd. This section only hands
# them the cursor, clicks and typed values.
var tools := {}                     # "rect" / "push" / "move" -> tool object
var tool_list: Array = []           # each tool's TOOL dictionary, in toolbar order (tool_registry.gd)
var tool_info := {}                 # tool id -> its TOOL dictionary
var tool_keys := {}                 # keycode -> tool id (keys.gd)
var infer                           # inference.gd: the one snapping engine
var tool_ctx                        # tool_context.gd: what every tool may use (T88)


func _make_tools() -> void:
	"""Every tool in tools/ that declares a TOOL (tool_registry.gd): adding a tool needs no edit here."""
	infer = Inference.new()
	infer.cam = cam
	infer.world = get_world_3d()
	infer.pres = pres
	infer.sel = sel
	infer.grid_enabled = func() -> bool: return grid_snap
	tool_ctx = _make_tool_context()
	var registry = load("res://tool_registry.gd")
	tool_list = registry.found()
	for p in registry.problems(tool_list): push_error("tools: " + p)
	for t in tool_list:
		tools[t["id"]] = t["script"].new()
		tools[t["id"]].setup_context(tool_ctx)
		if tools[t["id"]].uses_main(): tools[t["id"]].setup(self)   # T88: not yet moved to the context
		tool_info[t["id"]] = t
		if t["key"] != KEY_NONE: tool_keys[t["key"]] = t["id"]


func _make_tool_context():
	"""The owners each capability wraps, and the few main.gd helpers still bound in (T88 step 0: each moves to
	its owner when its first tool migrates). Nothing here hands a tool main.gd itself."""
	return load("res://tool_context.gd").new({
		"infer": infer, "pres": pres, "sel": sel, "doc": doc, "measure": measure,
		"cursor": _cursor_pos,
		"tri_mesh": _tri_mesh, "lines": _lines, "overlay": overlay, "overlay_lines": overlay_lines,
		"materials": {"hover": mat_hover, "profile": mat_rect, "draft": mat_draft, "cut": mat_cut, "cut_highlight": mat_cut_hl},
		"show_marker": _show_marker, "hide_marker": func(): marker.visible = false,
		"guides": _draw_guides, "clear_guides": func(): if guides: guides.mesh = null,
		"add_node": add_child,
		"refresh_tip": _update_tip, "clear_rejection": func(): reject_note = "",
		"new_board": func() -> bool: return new_board,
		"paint_name": func() -> String: return String(wood_library.get(paint_material, {}).get("name", "")),
		"paint_apply": paint,
	})


# the tests reach these two by their old names
var move_state: Dictionary:
	get: return tools["move"].state
	set(v): tools["move"].state = v
var hover: Dictionary:
	get: return tools["push"].hover
	set(v): tools["push"].hover = v


func pick(screen: Vector2) -> Dictionary:
	return infer.pick(screen)


func snap(p: Dictionary, screen: Vector2) -> Dictionary:
	return infer.snap(p, screen)


func set_tool(t: String) -> void:
	length_pending = {}
	tool = t
	for k in tools: tools[k].reset()
	vcb = ""
	if guides: guides.mesh = null
	if ui_tip: ui_tip.visible = false
	overlay.mesh = null; overlay_lines.mesh = null
	ui_hint.text = tools[t].hint()
	if _tool_buttons.has(t): _tool_buttons[t].set_pressed_no_signal(true)
	_update_vcb()


func tool_move(screen: Vector2) -> void:
	if not length_pending.is_empty(): return
	tools[tool].mouse_moved(screen)
	_show_siblings(pick(screen).get("body", ""))
	_update_tip(screen)


func tool_click(screen: Vector2) -> void:
	if tool != "move": tools["move"].last_oid = ""
	tools[tool].click(screen)
	_update_vcb()


static func _rect_pts(origin: Vector3, x: Vector3, y: Vector3, du: float, dv: float) -> PackedVector3Array:
	return Geo.rect_points(origin, x, y, du, dv)


func _update_tip(screen: Vector2) -> void:
	if ui_tip == null: return
	var txt: String = tools[tool].tip()
	var n := _siblings_of(hover_body).size()
	if n > 0:
		txt = ((txt + "\n") if txt != "" else "") + "changes %d linked board%s" % [n + 1, "" if n == 0 else "s"]
	ui_tip.visible = txt != ""
	ui_tip.text = txt
	ui_tip.position = screen + Vector2(22, 20)


# ---------------- selection and context (selection.gd, A33b, T41) ----------------
# What a click stands for, the entered assembly or array, hidden boards and the board under the cursor live in
# selection.gd (`m.sel`); it adds hide / assembly / unlink ops through the document. These names forward to it, so
# tools and tests keep writing m.selection, m.unit_of(...). main draws what its signals say.
const Selection := preload("res://selection.gd")
var sel: Selection = Selection.new()
var selection: Array:
	get: return sel.selection
var context: String:                # "" outside; "assembly:<id>" or "row:<original>" inside
	get: return sel.context
var body_assembly: Dictionary:      # board id -> assembly id, "" if none
	get: return sel.body_assembly
var body_row: Dictionary:           # board id -> the original its array row was copied from, "" if none
	get: return sel.body_row
var body_mirror_plane: Dictionary:  # mirrored board id -> [point, normal] of its plane (model mm)
	get: return sel.body_mirror_plane
var body_family: Dictionary:        # board id -> its family (shared definition), "" if it isn't linked
	get: return sel.body_family
var body_array: Dictionary:         # board id -> the array it's a copy in, "" if none
	get: return sel.body_array
var body_hidden: Dictionary:        # board id -> true while it's hidden
	get: return sel.body_hidden
var show_hidden: bool:              # View > Hidden geometry: hidden boards ghosted and pickable
	get: return sel.show_hidden
var hover_body: String:             # the board under the cursor (Make unique / Detach / Hide act on it)
	get: return sel.hover_body
	set(v): sel.hover_body = v
var _plane_node: MeshInstance3D:    # the mirror plane, shown inside an entered mirror group (A11b; the presenter's)
	get: return pres.plane_node
var mat_hidden_ghost: StandardMaterial3D:
	get: return pres.mat_hidden_ghost


func _make_selection() -> void:
	sel.name = "Selection"
	sel.doc = doc
	sel.has_board = func(b): return body_tris.has(b)
	add_child(sel)
	sel.selection_changed.connect(_on_selection_changed)
	sel.context_changed.connect(_on_context_changed)
	sel.hidden_changed.connect(_on_hidden_changed)
	sel.links_changed.connect(pres.forget_siblings)
	sel.say.connect(_say_status)


func unit_of(bid: String) -> Dictionary: return sel.unit_of(bid)
func in_context(bid: String) -> bool: return sel.in_context(bid)
func edit_blocked(bid: String) -> bool: return sel.edit_blocked(bid)
func context_assembly() -> String: return sel.context_assembly()
func enter_context_of(bid: String) -> void: sel.enter_context_of(bid)
func leave_context() -> void: sel.leave_context()
func set_selection(ids: Array) -> void: sel.set_selection(ids)
func hidden_boards() -> Dictionary: return sel.hidden_boards()
func is_hidden(bid: String) -> bool: return sel.is_hidden(bid)
func hide_selected() -> void: sel.hide_selected()
func unhide(which: String) -> void: sel.unhide(which)
func toggle_hidden_geometry() -> void: sel.toggle_hidden_geometry()
func make_assembly() -> void: sel.make_assembly()
func _siblings_of(bid: String) -> Array: return sel.siblings_of(bid)
func _linked_op(kind: String) -> void: sel.linked_op(kind)


func unit_tris(unit: Dictionary) -> PackedVector3Array:
	var t := PackedVector3Array()
	for b in unit.get("bodies", []): t.append_array(body_tris.get(b, PackedVector3Array()))
	return t


func _on_context_changed() -> void:
	_apply_context()
	if context == "": ui_hint.text = tools[tool].hint()
	else: ui_hint.text = "Inside %s. Esc to leave" % ("the assembly" if context.begins_with("assembly:") else "the array")


func _on_hidden_changed(by_op: bool) -> void:
	_apply_context()
	if by_op:
		if overlay != null: overlay.mesh = null
		pres.forget_siblings()
	else:
		_update_menu_checks()


func _apply_context() -> void: pres.apply_context()


func _on_selection_changed() -> void:
	if properties_panel != null and properties_panel.visible: _request_properties()
	pres.show_selection()
	if not sel.selection.is_empty(): measure.stop_typing()   # selecting boards again gives Delete back to them (I48)


func _request_properties() -> void:
	if properties_panel == null or not properties_panel.visible: return
	properties_request += 1
	properties_seq = -1
	if selection.size() != 1:
		properties_panel.message("Select one piece to inspect its properties.")
		return
	if in_flight or dirty or not opened:
		properties_panel.message("Waiting for FreeCAD…")
		return
	properties_panel.message("Reading properties…")
	client.send({"cmd": "inspect_properties", "model": model_path, "body": selection[0],
		"seq": seq, "request_id": properties_request})

func _on_properties(resp: Dictionary) -> void:
	if properties_panel == null or not properties_panel.visible: return
	if int(resp.get("seq", -1)) != seq or in_flight or dirty: return
	if int(resp.get("request_id", -1)) != properties_request: return
	if not resp.get("ok", false):
		properties_panel.message(str(resp.get("error", "Could not read properties")))
		return
	if resp.get("model") != model_path: return
	if selection.size() != 1 or resp.properties.body != selection[0]: return
	properties_seq = seq
	properties_panel.display(resp.properties)

func _edit_property(change: Dictionary) -> void:
	if properties_seq != seq or dirty or in_flight:
		_request_properties()
		return
	if selection.size() != 1 or change.body != selection[0]: return
	counters["pr"] += 1
	var op := change.duplicate(true)
	op["id"] = "pr%d" % counters["pr"]
	op["type"] = "property_edit"
	ops.append(op)
	properties_panel.message("Applying property…")
	sync()

# ---------------- wood (T15, M03) ----------------
# The worker writes materials.json (the library) beside bodies.json; each board's material, grain and across
# directions come in bodies.json. Textures live in materials/textures beside the project (or in the app bundle).
const WOOD := preload("res://wood.gdshader")
var wood_library := {}              # key -> library entry
var wood_keys: Array = []           # in library order, for the menu
var body_material := {}             # board id -> material key
var paint_material := "white-oak"   # what the Paint tool puts on
var _wood_tex := {}                 # texture file -> ImageTexture


func _load_wood_library(dir: String) -> void:
	var data = JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("materials.json")))
	if typeof(data) != TYPE_ARRAY: return
	wood_keys = []
	for e in data:
		wood_library[e["key"]] = e; wood_keys.append(e["key"])
	_build_materials_menu()


func _wood_texture(file: String) -> Texture2D:
	if not _wood_tex.has(file):
		var img := Image.load_from_file(_beside_project("materials/textures/" + file))
		if img == null or img.is_empty():
			_wood_tex[file] = null
		else:
			img.generate_mipmaps()
			_wood_tex[file] = ImageTexture.create_from_image(img)
	return _wood_tex[file]


func _wood_material(bid: String, b: Dictionary, base: Color) -> ShaderMaterial:
	var e: Dictionary = wood_library.get(b.get("material", ""), {})
	if e.is_empty(): return null
	var side := _wood_texture(e["texture"]); var end := _wood_texture(e["end_texture"])
	if side == null or end == null: return null
	var sm := ShaderMaterial.new(); sm.shader = WOOD
	sm.set_shader_parameter("side_tex", side); sm.set_shader_parameter("end_tex", end)
	var g: Array = b.get("grain", [1, 0, 0]); var a: Array = b.get("across", [0, 1, 0])
	sm.set_shader_parameter("grain", m2g(Vector3(g[0], g[1], g[2])))
	sm.set_shader_parameter("across", m2g(Vector3(a[0], a[1], a[2])))
	sm.set_shader_parameter("side_size", float(e["size_mm"]) / 1000.0)
	sm.set_shader_parameter("side_grain_v", e["grain"] == "v")
	sm.set_shader_parameter("end_size", float(e["end_size_mm"]) / 1000.0)
	var et := end.get_size()
	sm.set_shader_parameter("end_aspect", et.y / maxf(et.x, 1.0))
	var h := hash(bid)
	sm.set_shader_parameter("offset", Vector2(float(h & 1023) / 1024.0, float((h >> 10) & 1023) / 1024.0))
	sm.set_shader_parameter("base_color", base)
	return sm


func _build_materials_menu() -> void:
	"""The Wood menu: pick what Paint puts on (picking one switches to Paint)."""
	if not NativeMenu.has_feature(NativeMenu.FEATURE_GLOBAL_MENU) or _wood_menu_rid.is_valid(): return
	var bar := NativeMenu.get_system_menu(NativeMenu.MAIN_MENU_ID)
	_wood_menu_rid = NativeMenu.create_menu()
	for k in wood_keys:
		var i := NativeMenu.add_radio_check_item(_wood_menu_rid, wood_library[k]["name"], _on_wood_menu, Callable(), k)
		NativeMenu.set_item_checked(_wood_menu_rid, i, k == paint_material)
	NativeMenu.add_separator(_wood_menu_rid)
	NativeMenu.add_item(_wood_menu_rid, "Turn grain 90° (T)", _on_wood_menu, Callable(), "turn")
	NativeMenu.add_submenu_item(bar, "Wood", _wood_menu_rid)


var _wood_menu_rid := RID()


func _on_wood_menu(tag) -> void:
	if tag == "turn":
		_turn_grain(); return
	set_paint_material(String(tag))


func set_paint_material(k: String) -> void:
	if not wood_library.has(k): return
	paint_material = k
	if _wood_menu_rid.is_valid():
		for i in NativeMenu.get_item_count(_wood_menu_rid):
			NativeMenu.set_item_checked(_wood_menu_rid, i, NativeMenu.get_item_tag(_wood_menu_rid, i) == k)
	set_tool("paint")


func paint(bodies: Array) -> void:
	if bodies.is_empty() or not wood_library.has(paint_material): return
	counters["sm"] += 1
	ops.append({"id": "sm%d" % counters["sm"], "type": "set_material", "targets": bodies, "material": paint_material})
	sync()
	_say_status("%s: %s" % [", ".join(bodies), wood_library[paint_material]["name"]])


func _turn_grain() -> void:
	var bid := hover_body
	if bid == "" or body_material.get(bid, "") == "":
		_say_status("Point at a painted board to turn its grain"); return
	counters["tg"] += 1
	ops.append({"id": "tg%d" % counters["tg"], "type": "turn_grain", "targets": [bid]})
	sync()
	_say_status("%s: grain turned 90°" % bid)


# ---------------- linked boards (T12: A22c, I28, Q28, Q29) ----------------
# Copies share one definition: editing one edits all. While a tool is over a linked board its copies get a soft
# tint and the tooltip counts them; U (Edit > Make unique) frees the board under the cursor, Edit > Detach from
# array frees its position.


func _show_siblings(bid: String) -> void:
	hover_body = bid
	pres.show_siblings(_siblings_of(bid) if tool_info.get(tool, {}).get("show_links", false) else [])


func _say_status(txt: String) -> void:
	ui_sync.text = txt
	ui_sync.remove_theme_color_override("font_color")


# ---------------- snapping visuals (the engine is inference.gd) ----------------
const SNAP_COLORS := Presenter.SNAP_COLORS   # the rendering constants are the presenter's (T88)
var guides: MeshInstance3D


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


func _cursor_pos() -> Vector2:
	return cursor2d.position if test_mode and cursor2d != null else get_viewport().get_mouse_position()


# ---------------- axes ----------------
const AXIS_COLORS := Presenter.AXIS_COLORS

static func _axis_vec(ax: int) -> Vector3: return Geo.axis_vector(ax)
static func reflect_point(q: Vector3, p: Vector3, n: Vector3) -> Vector3: return Geo.reflect_point(q, p, n)
static func reflect_tris(tris: PackedVector3Array, p: Vector3, n: Vector3) -> PackedVector3Array: return Geo.reflect_tris(tris, p, n)
static func _mirror_tris(tris: PackedVector3Array, ax: int, c: float) -> PackedVector3Array: return Geo.mirror_triangles(tris, ax, c)

# ---------------- open, undo ----------------
func _on_open(resp: Dictionary) -> void:
	if not doc.is_current_open(resp):           # an answer to an older open (a model since left): ignored (T70)
		print("SHOPSKETCH ignored a late open reply for %s" % resp.get("model", "?"))
		return
	if resp.get("error", "") == "already_open":
		if _model_before == "":
			# launched on a model another window has: that window came forward, this one isn't needed (W13)
			print("SHOPSKETCH %s is open in another window: closing this one" % model_path)
			get_tree().quit()
		else:
			var name := model_path.get_file()
			switch_model(_model_before)
			_say_worker("%s is open in another window" % name)
		return
	_model_before = ""
	if not resp.get("ok", false):
		ui_sync.text = "✗ couldn't open %s: %s" % [model_path, resp.get("error", "?")]
		ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))
		return
	var adopt := not (test_mode and not heavy_test and _first_open)   # tests start clean; a model opened later (switch_model) adopts its history
	_first_open = false
	doc.on_opened(resp, adopt)
	if not adopt: return
	_rebuild_rect_drafts()
	sync()
	if resp.get("external", false):
		reject_note = ""
		ui_sync.text = "opened %s - changed in FreeCAD since Shop Sketch last saved it" % model_path.get_file()


func undo() -> void:
	if doc.at_undo_floor():
		ui_sync.text = "✗ can't undo past changes made in FreeCAD (yet)"
		ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))
		return
	doc.undo()


# ---------------- redo (T31) ----------------
# Linear redo (the document controller keeps the stack and says when it's over); here it's drawn again.
func can_redo() -> bool:
	return doc.can_redo()


func redo() -> void:
	var op: Dictionary = doc.take_redo()
	if op.is_empty():
		_say_status("Nothing to redo")
		return
	if op["type"] in ["rect", "circle"]:
		if not rects.has(op["id"]): _register_rect(op)
	elif op["type"] == "push_pull":
		var rid: String = op["target"].get("rect", "")
		if drafts.has(rid): drafts[rid].queue_free(); drafts.erase(rid)
	_show_state(_ops_key(ops))                 # the state it led to, if remembered: on screen at once
	_apply_context()
	sync()
	ui_sync.text = "↷ redone - FreeCAD catching up (%d ops)" % ops.size()


func remove_ops(ids: Array) -> void:
	doc.remove_ops(ids)


func remove_op(oid: String, resync := true) -> void:
	doc.remove_op(oid, resync)


func _on_op_removed(op: Dictionary) -> void:
	"""The document dropped an op (undo, rejection): take away what it drew."""
	pres.forget_op(op, ops, _consumed_rects())


func _on_removed() -> void:
	var k := _ops_key(ops)
	if k != shown_key and _show_state(k):      # undo: the state before this op, remembered, on screen at once
		predicted_undo = true
	_apply_context()                           # an undone hide shows its boards again at once (T28)


func _restore_counters() -> void:
	doc.restore_counters()


func _consumed_rects() -> Dictionary:
	return doc.consumed_rects()


func _rebuild_rect_drafts() -> void:
	pres.rebuild_rect_drafts(ops, _consumed_rects())


# ---------------- worker sync ----------------
func oplog() -> Dictionary:
	return doc.oplog()


func sync() -> void:
	doc.sync()


func _on_sync_started() -> void:
	properties_seq = -1
	if properties_panel != null and properties_panel.visible: properties_panel.message("Waiting for FreeCAD…")
	ui_sync.text = "● draft - FreeCAD catching up (%d ops)" % ops.size()
	if predicted_undo:
		ui_sync.text = "↶ undone - FreeCAD catching up (%d ops)" % ops.size()
		predicted_undo = false
	ui_sync.add_theme_color_override("font_color", Color(0.75, 0.45, 0.0))


func _on_worker(resp: Dictionary) -> void:
	if resp.get("cmd", "") == "inspect_properties":
		_on_properties(resp)
		return
	if resp.get("cmd", "") == "length":
		_on_length(resp)
		return
	if resp.get("cmd", "") == "focus":               # someone tried to open this window's model: come forward
		DisplayServer.window_move_to_foreground()
		return
	if resp.get("cmd", "") == "open":
		_on_open(resp)
		return
	if resp.get("cmd", "") == "saved":
		doc.on_saved(resp)
		return
	if resp.get("cmd", "") == "save_failed":         # T79: the indicator says why (I54)
		doc.on_save_failed(resp)
		return
	if resp.get("cmd", "") == "flush":               # what it saved and couldn't (T79); closing waits on it
		doc.on_flush_reply(resp)
		return
	if not resp.get("cmd", "") in ["sync", "replay"]:   # flush, hello, bye, quit, or an error for some other request:
		if not resp.get("ok", false):                    # never sync state (T70)
			_say_worker("✗ worker error: %s" % resp.get("error", "?"))
		return
	if true_latency and resp.get("ok", false) and resp.has("wall_ms") and not resp.get("_released", false):
		held_resp = resp
		return
	doc.on_sync_reply(resp)


func _on_sync_failed(error: String) -> void:
	ui_sync.text = "✗ worker error: %s" % error
	ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))


func _on_synced(resp: Dictionary) -> void:
	"""FreeCAD's answer for what's on screen: confirmed boards replace drafts, waves finish or go red."""
	var res: Dictionary = resp["result"]
	var drop_now := []
	for o in res["ops"]:
		var w = op_waves.get(o["id"])
		if o["status"] == "ok":
			if w != null and w["state"] == "pending": w["state"] = "ok"
		else:
			_on_rejected(o, w, drop_now)
	var ok_ids := {}
	for o in res["ops"]:
		if o["status"] == "ok": ok_ids[o["id"]] = true
	var key := _ops_key(ops.filter(func(op): return ok_ids.has(op["id"])))
	pres.show_confirmed(resp["outdir"], key)          # unless already on screen (an undo shown from the cache)
	pres.drop_confirmed_drafts(_consumed_rects())     # a rejected draft stays until its red wave is done
	if true_latency: doc.last_sync_ms = int((movie_clock - float(sent_clock.get(seq, movie_clock))) * 1000.0)
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


# ---------------- confirmed boards (presenter.gd) ----------------
func _apply_confirmed(dir: String, key: String) -> void:
	pres.apply_confirmed(dir, key)


func _on_boards_read(data: Array, dir: String) -> void:
	"""bodies.json, before the presenter builds from it: what each board belongs to, and its wood."""
	sel.set_boards(data)
	if wood_library.is_empty(): _load_wood_library(dir)
	for b in data: body_material[b["id"]] = b.get("material", "")
	pres.forget_siblings()


static func _ops_key(list: Array) -> String:
	return Document.ops_key(list)


# ---------------- the frame ----------------
const DEFAULT_BASE := Presenter.DEFAULT_BASE   # a board's colour before FreeCAD says (tools start waves with it)
var reject_note := ""
var force_reject_next := false


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
	pres.step_waves(delta)


func _on_wave_rejected_done(oid: String) -> void:
	if _rejected.has(oid):                              # a rejection: it goes with the actions that built on it
		remove_ops([oid] + _rejected[oid]["deps"])
	else:
		var w: Dictionary = op_waves[oid]
		if not w.get("dependent", false) or not op_waves.has(w["root"]):
			remove_op(oid)                              # ends the wave, frees the draft, resyncs


# ---------------- rejections take what built on them (T16, Q7) ----------------
# FreeCAD rejects an action a moment after you did it; meanwhile you may have drawn on the board it made or the
# face it changed. Those later actions fail too (what they refer to is gone): they join the first rejection,
# go red with it and are removed together, with one message. Independent work stays.
const REJECT_WINDOW_MS := 15000     # a rejection collects its dependents for this long
var _rejected := {}                 # root op id -> {"ids", "bodies", "deps", "at", "note"}
var last_reject_note := ""          # the latest rejection message (kept for tests; the status bar clears on your next action)


func _op_of(oid: String) -> Dictionary:
	return doc.op_of(oid)


static func _op_refs(op: Dictionary) -> Array:
	"""Ids an op refers to: the board or rectangle it acts on."""
	var out := []
	var pl: Dictionary = op.get("plane", {})
	if pl.has("on"): out.append(pl["on"]["body"])
	var tg: Dictionary = op.get("target", {})
	if op.has("edge_fit"): out.append(op["edge_fit"]["target_body"])
	if tg.has("rect"): out.append(tg["rect"])
	if tg.has("face"): out.append(tg["face"]["body"])
	out.append_array(op.get("targets", []))
	if op.has("cut"): out.append_array([op["cut"]["body"], op["cut"]["op"]])
	if op["type"] in ["make_component", "property_edit"]: out.append(op["body"])
	return out


func _op_makes(op: Dictionary) -> Array:
	var out: Array = [op["id"]]
	if op["type"] == "push_pull" and op.has("body"): out.append(op["body"])
	out.append_array(op.get("new_ids", []))
	return out


func _op_touches(op: Dictionary) -> Array:
	"""Boards an op changes in place (a face on them may exist only because of it)."""
	var tg: Dictionary = op.get("target", {})
	if op["type"] == "push_pull" and not op.has("body"):
		if tg.has("rect"):
			var r := _op_of(tg["rect"])
			if not r.is_empty() and r["plane"].has("on"): return [r["plane"]["on"]["body"]]
		if tg.has("face"): return [tg["face"]["body"]]
	if op["type"] == "move": return op.get("targets", []) + ([op["cut"]["body"]] if op.has("cut") else [])
	return []


func _on_rejected(o: Dictionary, w, drop_now: Array) -> void:
	var now := Time.get_ticks_msec()
	for r in _rejected.keys():
		if now - int(_rejected[r]["at"]) > REJECT_WINDOW_MS and not op_waves.has(r): _rejected.erase(r)
	var op := _op_of(o["id"])
	if op.is_empty(): return
	var msg: String = o.get("message", "")
	var root := ""
	for r in _rejected:
		var e: Dictionary = _rejected[r]
		for ref in _op_refs(op):
			if e["ids"].has(ref): root = r
		for b in e["bodies"]:
			if msg.contains("'%s'" % b): root = r
		if root != "": break
	if root == "":                                   # a rejection of its own
		root = o["id"]
		var e := {"ids": {}, "bodies": {}, "deps": [], "at": now, "note": "%s: %s" % [o["id"], msg]}
		for x in _op_makes(op): e["ids"][x] = true
		for b in _op_touches(op): e["bodies"][b] = true
		_rejected[root] = e
		reject_note = e["note"]
		if w != null: w["state"] = "rejected"        # red wave plays, then it goes with its dependents
		else: drop_now.append(o["id"])
		return
	var e: Dictionary = _rejected[root]              # built on an earlier rejection: goes with it
	if not e["deps"].has(o["id"]): e["deps"].append(o["id"])
	for x in _op_makes(op): e["ids"][x] = true
	for b in _op_touches(op): e["bodies"][b] = true
	var n: int = e["deps"].size()
	reject_note = "%s (and %d action%s that built on it)" % [e["note"], n, "" if n == 1 else "s"]
	last_reject_note = reject_note
	if w != null:
		w["state"] = "rejected"; w["dependent"] = true; w["root"] = root
	if not op_waves.has(root):                       # its rejection has already played: remove it now
		drop_now.append(o["id"])


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
var _port_file := ""                # tests: where our worker reports the port it bound (T47)
var _worker_restarts: Array = []
var _worker_check := 0.0
var _first_open := true
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


# One FreeCAD worker serves every window (W13): each window has its own document, and a model is open in one
# window at a time. A window uses the worker on SHARED_PORT if it runs the same worker script; else it starts it
# there; a different version (say the repo and the built app at once) gets a worker of its own. Tests never share.
var SHARED_PORT := 7878             # --shared-port=N: another one (to try windows sharing next to a running app)
const SHARED_IDLE_EXIT := 10        # seconds the shared worker waits after the last window leaves
var shared_worker := false
var _down_since := -1.0
var _gave_up := false


func _worker_files() -> void:
	if freecad_path == "":
		for c in FREECAD_CANDIDATES:
			if FileAccess.file_exists(c): freecad_path = c; break
	if worker_script == "":
		worker_script = _beside_project("worker/replay.py")


func _worker_identity() -> String:
	"""The same hash the worker reports in hello (serve.py worker_identity): MD5 of every worker .py except the
	tests, one after another in name order. A change to any worker module means a different worker."""
	var folder := worker_script.get_base_dir()
	var names: Array = Array(DirAccess.get_files_at(folder)).filter(
		func(n: String) -> bool: return n.ends_with(".py") and not n.begins_with("test_"))
	if names.is_empty(): return ""
	names.sort()
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_MD5)
	for n in names:
		ctx.update(FileAccess.get_file_as_bytes(folder.path_join(n)))
	return ctx.finish().hex_encode()


func _port_free(p: int) -> bool:
	var srv := TCPServer.new()
	if srv.listen(p, "127.0.0.1") != OK: return false
	srv.stop()
	return true


# The window <-> worker protocol's version (docs/protocol.md): bump it when a message or shared-file field changes.
# The worker reports its own (worker/serve.py PROTOCOL_VERSION) in hello; a worker speaking another isn't shared.
const PROTOCOL_VERSION := 3


func _probe_worker(p: int) -> String:
	"""Ask whatever listens on port p who it is: the worker's script hash, or "" if it isn't a Shop Sketch worker
	this window can use (_worker_of)."""
	return _worker_of(_hello(p), p)


func _worker_of(r, p: int) -> String:
	"""A hello reply's worker hash, or "": not a Shop Sketch worker, or one speaking another protocol version
	(then it's treated like a different worker: this window starts its own, and says why)."""
	if typeof(r) != TYPE_DICTIONARY or r.get("app", "") != "shopsketch": return ""
	if int(r.get("protocol", 0)) != PROTOCOL_VERSION:
		print("SHOPSKETCH the worker on port %d speaks protocol %s, this window %d: not sharing it" % [p, str(r.get("protocol", "none")), PROTOCOL_VERSION])
		return ""
	return String(r.get("worker", ""))


func _hello(p: int):
	"""The hello reply from whatever listens on port p (a separate short-lived connection), or null."""
	var peer := StreamPeerTCP.new()
	if peer.connect_to_host("127.0.0.1", p) != OK: return null
	var t0 := Time.get_ticks_msec()
	var buf := ""
	var sent := false
	while Time.get_ticks_msec() - t0 < 3000:
		peer.poll()
		var st := peer.get_status()
		if st == StreamPeerTCP.STATUS_ERROR or st == StreamPeerTCP.STATUS_NONE: return null
		if st == StreamPeerTCP.STATUS_CONNECTED:
			if not sent:
				peer.put_data((JSON.stringify({"cmd": "hello"}) + "\n").to_utf8_buffer()); sent = true
			var n := peer.get_available_bytes()
			if n > 0:
				buf += peer.get_utf8_string(n)
				if buf.contains("\n"):
					var r = JSON.parse_string(buf.get_slice("\n", 0))
					peer.disconnect_from_host()
					return r
		OS.delay_msec(10)
	peer.disconnect_from_host()
	return null


func _pick_worker() -> int:
	_worker_files()
	if test_mode:                                   # tests: a worker of their own, on a port it picks itself (T47)
		_start_worker()
		return worker_port
	var mine := _worker_identity()
	if _port_free(SHARED_PORT):
		shared_worker = true
		worker_port = SHARED_PORT
		_start_worker()
	elif _probe_worker(SHARED_PORT) == mine and mine != "":
		shared_worker = true                       # another window's worker: use it
		worker_port = SHARED_PORT
		print("SHOPSKETCH sharing the worker on port %d" % SHARED_PORT)
	else:
		worker_port = _free_port(SHARED_PORT + 1)   # something else (or another version) has the port
		_start_worker()
	return worker_port


func _start_worker() -> void:
	if freecad_path == "":
		for c in FREECAD_CANDIDATES:
			if FileAccess.file_exists(c): freecad_path = c; break
	if worker_script == "":
		worker_script = _beside_project("worker/replay.py")
	if worker_log == "":
		worker_log = ProjectSettings.globalize_path("user://worker.log")
	if freecad_path == "" or not FileAccess.file_exists(worker_script):
		_say_worker("✗ couldn't find FreeCAD's command-line program (freecadcmd) or worker/replay.py")
		worker_pid = -1
		return
	# a test's worker binds port 0 and writes the port the system gave it to a file: two test runs at once can't
	# pick the same port before either binds it (T47). The app's workers keep their known ports (W13).
	var port_file := ""
	if test_mode:
		port_file = OS.get_temp_dir().path_join("shopsketch-worker-%d.port" % OS.get_process_id())
		DirAccess.remove_absolute(port_file)
		worker_port = 0
	if OS.get_name() == "Windows":
		OS.set_environment("SERVE_PORT", str(worker_port))
		OS.set_environment("SERVE_PORT_FILE", port_file)
		worker_pid = OS.create_process(freecad_path, [worker_script])
	else:
		worker_pid = OS.create_process("/bin/sh", ["-c", "SERVE_PORT=%d SERVE_PORT_FILE=%s SERVE_IDLE_EXIT=%d exec %s %s >> %s 2>&1" % [
			worker_port, _sh(port_file), SHARED_IDLE_EXIT, _sh(freecad_path), _sh(worker_script), _sh(worker_log)]])   # never outlives its windows
	_port_file = port_file
	if port_file != "" and client != null:           # a restarted worker: wait for its new port
		worker_port = _await_port_file()
		client.port = worker_port
	print("SHOPSKETCH worker pid %d %s: %s (log %s)" % [worker_pid, "port pending" if worker_port == 0 else
		"on port %d" % worker_port, worker_script, worker_log])


func _await_port_file() -> int:
	"""Tests only: wait for the worker to report the port it bound (it starts in about a second)."""
	var path := _port_file
	var t0 := Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 60000:
		if FileAccess.file_exists(path):
			var p := int(FileAccess.get_file_as_string(path).strip_edges())
			DirAccess.remove_absolute(path)
			if p > 0:
				print("SHOPSKETCH worker on port %d" % p)
				return p
		if worker_pid > 0 and not OS.is_process_running(worker_pid): break
		OS.delay_msec(20)
	push_error("SHOPSKETCH the worker didn't report its port: see %s" % worker_log)
	return -1


func _watch_worker(delta: float) -> void:
	_worker_check -= delta
	if _worker_check > 0.0: return
	_worker_check = 1.0
	if shared_worker:
		# whoever started it, it's everyone's: when it's gone and its port is free, this window starts it again
		if client.connected:
			_down_since = -1.0; return
		var now_s := Time.get_ticks_msec() / 1000.0
		if _down_since < 0.0: _down_since = now_s
		if now_s - _down_since < 1.5 or not _port_free(worker_port) or _gave_up: return
		_down_since = -1.0
	elif worker_pid <= 0 or OS.is_process_running(worker_pid):
		return
	var now := Time.get_ticks_msec()
	_worker_restarts = _worker_restarts.filter(func(t): return now - t < 60000)
	_worker_restarts.append(now)
	if _worker_restarts.size() > WORKER_MAX_RESTARTS:
		_say_worker("✗ the FreeCAD worker keeps stopping - see %s" % worker_log)
		worker_pid = -1
		_gave_up = true
		return
	_say_worker("✗ the FreeCAD worker stopped - starting it again")
	_start_worker()


func _say_worker(txt: String) -> void:
	ui_sync.text = txt
	ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))


func _send_open() -> void:
	doc.send_open()


func _on_link_down() -> void:
	if worker_pid > 0 or opened:
		_say_worker("● lost the FreeCAD worker - reconnecting")


func _on_link_up(first: bool) -> void:
	if first: return
	doc.on_link_up()


var _worker_shut := false


func _shutdown_worker() -> void:
	if _worker_shut: return
	_worker_shut = true
	if shared_worker:
		# other windows may be using it: hand back this window's model (saved first) and leave it running;
		# it stops by itself a few seconds after the last window has gone
		if client.connected:
			client.send({"cmd": "bye"})
			var t0 := Time.get_ticks_msec()
			while client.connected and Time.get_ticks_msec() - t0 < 4000:
				client.peer.poll()
				if client.peer.get_status() != StreamPeerTCP.STATUS_CONNECTED: break
				if client.peer.get_available_bytes() > 0 and client.peer.get_utf8_string(client.peer.get_available_bytes()).contains("bye"): break
				OS.delay_msec(20)
		return
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


# ---------------- closing the window (I55, T79) ----------------
# Closing (the window's close button, Cmd+Q) waits until the latest revision is on disk. If it can't be saved, a
# dialog says why: Retry, Close without saving (the journal still has the actions), or Cancel.
const CLOSE_WAIT_S := 10.0          # FreeCAD hasn't answered closing's save in this long: ask (tunable)
var _close_asking := false          # the dialog is up
var _close_try := 0                 # numbers each try, so an old try's timer can't ask during a newer one
var close_asked: Array = []         # tests: the reasons the dialog would have given (it isn't shown in test mode)
var close_done := false             # tests: _close_now ran (the window would have gone)


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		_request_close()


func _request_close() -> void:
	if _close_asking or doc.closing: return      # already waiting, or asking
	if doc.begin_close():
		_close_now()
		return
	_say_worker("saving %s before closing…" % model_path.get_file())
	_close_try += 1
	var try_then := _close_try
	get_tree().create_timer(CLOSE_WAIT_S).timeout.connect(func() -> void:
		if doc.closing and not _close_asking and _close_try == try_then:
			doc.cancel_close()
			_ask_close("FreeCAD hasn't answered"))


func _ask_close(reason: String) -> void:
	_close_asking = true
	var text := "%s couldn't be saved: %s.\nIts actions are kept in its journal beside the file." % [model_path.get_file(), reason]
	if test_mode:
		close_asked.append(reason)
		return
	if DisplayServer.has_feature(DisplayServer.FEATURE_NATIVE_DIALOG):
		DisplayServer.dialog_show("Couldn't save", text, PackedStringArray(["Retry", "Close without saving", "Cancel"]),
			func(i: int) -> void: _close_choice(["retry", "discard", "cancel"][clampi(i, 0, 2)]))
		return
	var dlg := ConfirmationDialog.new()
	dlg.title = "Couldn't save"
	dlg.dialog_text = text
	dlg.ok_button_text = "Retry"
	dlg.add_button("Close without saving", true, "discard")
	dlg.confirmed.connect(func() -> void: dlg.queue_free(); _close_choice("retry"))
	dlg.canceled.connect(func() -> void: dlg.queue_free(); _close_choice("cancel"))
	dlg.custom_action.connect(func(_a: StringName) -> void: dlg.queue_free(); _close_choice("discard"))
	add_child(dlg)
	dlg.popup_centered()


func _close_choice(choice: String) -> void:
	_close_asking = false
	match choice:
		"retry": _request_close()
		"discard":
			print("SHOPSKETCH closing without saving %s (rev %d not saved: %s)" % [model_path, pending_rev, doc.save_error])
			_close_now()
		_:
			doc.cancel_close()
			_update_saved()
			ui_sync.text = ""


func _close_now() -> void:
	close_done = true
	if test_mode: return                # tests check close_done; the run goes on
	_shutdown_worker()
	get_tree().quit()


# ---------------- documents, menus, dialogs (T8) ----------------
# Shop Sketch works on one FreeCAD file at a time. File > New / Open switch files without restarting; the last
# file reopens next time. Native macOS menus and file dialogs where the system has them.
const SETTINGS := "user://settings.cfg"
var out_root := ""                  # each model's outputs go in a folder of their own under here


func _beside_project(rel: String) -> String:
	"""A file shipped next to the viewport: the repo when run from source, the app bundle's Resources otherwise."""
	var src := ProjectSettings.globalize_path("res://")
	if src != "" and FileAccess.file_exists(src.path_join("..").path_join(rel).simplify_path()):
		return src.path_join("..").path_join(rel).simplify_path()
	return OS.get_executable_path().get_base_dir().path_join("../Resources").path_join(rel).simplify_path()


func _last_model() -> String:
	var cfg := ConfigFile.new()
	if cfg.load(SETTINGS) == OK:
		var p: String = cfg.get_value("files", "last_model", "")
		if p != "" and (FileAccess.file_exists(p) or DirAccess.dir_exists_absolute(p.get_base_dir())):
			return p
	var docs := OS.get_system_dir(OS.SYSTEM_DIR_DOCUMENTS).path_join("Shop Sketch")
	DirAccess.make_dir_recursive_absolute(docs)
	return docs.path_join("Untitled.FCStd")


func _remember_model(path: String) -> void:
	var cfg := ConfigFile.new()
	cfg.load(SETTINGS)
	cfg.set_value("files", "last_model", path)
	cfg.save(SETTINGS)


func _out_for(path: String) -> String:
	return out_root.path_join("%s-%s" % [path.get_file().get_basename(), path.md5_text().left(8)])


func _set_title() -> void:
	if test_mode: return
	DisplayServer.window_set_title("%s — Shop Sketch" % model_path.get_file().get_basename())


var _model_before := ""                # the model this window had before an Open (to go back if it's taken)


func switch_model(path: String, fresh := false) -> void:
	"""Close the current model (the worker keeps it saved) and open another; fresh = start it empty."""
	if path.get_extension().to_lower() != "fcstd": path += ".FCStd"
	if path == model_path and not fresh: return
	if opened: _model_before = model_path
	_reset_model_state()
	model_path = path
	if not test_mode:
		out_dir = _out_for(path)
		_remember_model(path)
	DirAccess.make_dir_recursive_absolute(out_dir)
	_set_title()
	doc.open(path, fresh)
	ui_sync.text = "opening %s" % path.get_file()


func _reset_model_state() -> void:
	properties_seq = -1
	properties_request += 1
	set_selection([])
	doc.reset()                     # a reply still on its way belongs to the old model: it's ignored
	pres.reset()
	reject_note = ""
	tools["move"].last_oid = ""; tools["move"].memo.clear()
	set_tool(tool)
	marker.visible = false


# menus: tag -> action. Menu shortcuts and the same keys in the window may both arrive: act once.
var _menu_last := {}
var _menus := {}                    # name -> menu RID (for check marks)


func _make_menus() -> void:
	if not NativeMenu.has_feature(NativeMenu.FEATURE_GLOBAL_MENU): return
	var main_menu := NativeMenu.get_system_menu(NativeMenu.MAIN_MENU_ID)
	var spec := [
		["File", [["New Window", "newwindow", KEY_MASK_META | KEY_MASK_SHIFT | KEY_N], ["New…", "new", KEY_MASK_META | KEY_N],
				  ["Open…", "open", KEY_MASK_META | KEY_O], [],
				  ["Show in Finder", "reveal", 0], [], ["Drawing and cut list (D)", "drawing", 0]]],
		["Edit", [["Undo", "undo", KEY_MASK_META | KEY_Z], ["Redo", "redo", KEY_MASK_META | KEY_MASK_SHIFT | KEY_Z], [], ["Make assembly", "assemble", KEY_MASK_META | KEY_G],
				  ["Delete (⌫)", "delete", 0], ["Make unique (U)", "unique", 0], ["Detach from array", "detach", 0], [],
				  ["Hide (H)", "hide", 0], ["Unhide selected", "unhide_selected", 0], ["Unhide last", "unhide_last", 0],
				  ["Unhide all (Shift+H)", "unhide_all", 0]]],
		["Tools", tool_list.map(func(t): return [load("res://tool_registry.gd").menu_label(t), t["id"], 0])],
		["View", [["Grid snap (G)", "grid", -1], ["New board on faces (B)", "newboard", -1], ["Hidden geometry", "hiddengeom", -1]]],
	]
	for m in spec:
		var rid := NativeMenu.create_menu()
		_menus[m[0]] = rid
		for it in m[1]:
			if it.is_empty():
				NativeMenu.add_separator(rid)
			elif it[2] == -1:
				NativeMenu.add_check_item(rid, it[0], _menu, Callable(), it[1])
			else:
				NativeMenu.add_item(rid, it[0], _menu, Callable(), it[1], it[2])
		NativeMenu.add_submenu_item(main_menu, m[0], rid)
	_update_menu_checks()


func _update_menu_checks() -> void:
	if not _menus.has("View"): return
	NativeMenu.set_item_checked(_menus["View"], 0, grid_snap)
	NativeMenu.set_item_checked(_menus["View"], 1, new_board)
	NativeMenu.set_item_checked(_menus["View"], 2, show_hidden)


func _menu(tag) -> void:
	var now := Time.get_ticks_msec()
	if now - int(_menu_last.get(tag, -1000)) < 150: return        # the menu and the key both fired
	_menu_last[tag] = now
	if tools.has(tag): set_tool(tag); return      # a tool's id (tool_registry.gd)
	match tag:
		"newwindow": new_window()
		"new": _file_dialog(true)
		"open": _file_dialog(false)
		"reveal": OS.shell_show_in_file_manager(model_path)
		"drawing": export_drawing()
		"undo": undo()
		"redo": redo()
		"assemble": make_assembly()
		"unique": _linked_op("make_unique")
		"detach": _linked_op("detach")
		"delete": tools[tool].reset(); sel.delete_selected()
		"hide": hide_selected()
		"unhide_selected": unhide("selected")
		"unhide_last": unhide("last")
		"unhide_all": unhide("all")
		"hiddengeom": toggle_hidden_geometry()
		"grid": grid_snap = not grid_snap; _update_toggles()
		"newboard": new_board = not new_board; _update_toggles()


func new_window() -> void:
	"""Another window on a new Untitled model, sharing this window's FreeCAD worker (W13)."""
	var docs := OS.get_system_dir(OS.SYSTEM_DIR_DOCUMENTS).path_join("Shop Sketch")
	DirAccess.make_dir_recursive_absolute(docs)
	var path := ""
	for i in range(2, 1000):
		path = docs.path_join("Untitled %d.FCStd" % i)
		if not FileAccess.file_exists(path) and not FileAccess.file_exists(path.get_basename() + ".shopsketch.json"): break
	var args := OS.get_cmdline_args()             # the engine's own arguments (--path when run from source)
	args.append("--")
	for a in OS.get_cmdline_user_args():
		if not (a.begins_with("--model=") or a.begins_with("--out=")): args.append(a)
	args.append("--model=" + path)
	var pid := OS.create_process(OS.get_executable_path(), args)
	print("SHOPSKETCH new window pid %d on %s" % [pid, path])


func _file_dialog(new: bool) -> void:
	var start := model_path.get_base_dir()
	var name := "Untitled.FCStd" if new else ""
	var filters := PackedStringArray(["*.FCStd ; FreeCAD model"])
	var mode := DisplayServer.FILE_DIALOG_MODE_SAVE_FILE if new else DisplayServer.FILE_DIALOG_MODE_OPEN_FILE
	var done := func(ok: bool, paths: PackedStringArray, _filter: int) -> void:
		if ok and not paths.is_empty(): switch_model(paths[0], new)
	if DisplayServer.has_feature(DisplayServer.FEATURE_NATIVE_DIALOG_FILE):
		DisplayServer.file_dialog_show("New model" if new else "Open a model", start, name, false, mode, filters, done)
	else:
		var fd := FileDialog.new()
		fd.access = FileDialog.ACCESS_FILESYSTEM
		fd.file_mode = FileDialog.FILE_MODE_SAVE_FILE if new else FileDialog.FILE_MODE_OPEN_FILE
		fd.filters = filters
		fd.current_dir = start
		fd.file_selected.connect(func(p: String) -> void: switch_model(p, new); fd.queue_free())
		add_child(fd)
		fd.popup_centered_ratio(0.6)


# ---------------- drawing export ----------------
var drawing_pending := false

func export_drawing() -> void:
	drawing_pending = true
	doc.request_drawing()


func _run_drawing_script() -> void:
	if drawing_script == "":
		ui_sync.text = "drawing page saved in model.FCStd (no --drawing script given for PDF)"
		return
	var out := []
	var code := OS.execute("python3", [drawing_script, out_dir, model_path.get_basename() + ".shopsketch.json"], out, true)
	ui_sync.text = ("✓ drawing written to %s/drawing.pdf" % out_dir) if code == 0 else ("✗ drawing failed: %s" % str(out))


# ---------------- input ----------------
# Keys go to keys.gd (`m.keys`, T75); the mouse, trackpad and camera stay here.
var keys = load("res://keys.gd").new()


func _make_keys() -> void:
	keys.name = "Keys"
	keys.m = self
	add_child(keys)


func _input(e: InputEvent) -> void:
	if keys.before_gui(e): get_viewport().set_input_as_handled()     # Tab / Option in Push/Pull (I40)


var finish_reference_click := false  # the release of the click that picked a Properties reference is eaten too

func _unhandled_input(e: InputEvent) -> void:
	if (e is InputEventKey and e.pressed) or (e is InputEventMouseButton and e.pressed): length_pending = {}
	if fx_test and cursor2d != null and (e is InputEventMouseMotion or e is InputEventMouseButton) \
			and e.position.distance_to(cursor2d.position) > 0.5:
		return       # tests: the real pointer over the window isn't the test's cursor; ignore it
	if finish_reference_click and e is InputEventMouseButton and e.button_index == MOUSE_BUTTON_LEFT:
		finish_reference_click = false
		if not e.pressed: return
	if properties_panel.visible and properties_panel.picking_axis >= 0:   # Properties: pick a face to fit to
		if e is InputEventKey and e.pressed and e.keycode == KEY_ESCAPE:
			properties_panel.cancel_pick()
			_request_properties()
			return
		if e is InputEventMouseButton and e.button_index == MOUSE_BUTTON_LEFT:
			if e.pressed:
				finish_reference_click = true
				var hit := pick(e.position)
				var near: Dictionary = infer.point(e.position, str(properties_panel.data.body))
				if near.get("kind", "") in ["midpoint", "on edge", "endpoint"] and properties_panel.data.boards.has(near.body):
					hit = near
				properties_panel.pick_reference(hit)
			return
	if e is InputEventMouseButton:
		if e.button_index in [MOUSE_BUTTON_MIDDLE, MOUSE_BUTTON_RIGHT]:
			orbiting = e.pressed and not e.shift_pressed
			panning = e.pressed and e.shift_pressed
		elif e.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN] and e.pressed:
			# zoom by how much was scrolled: a smooth-scrolling mouse (MX Master) sends many small steps per notch
			var amount := clampf(e.factor if e.factor > 0.0 else 1.0, 0.0, ZOOM_MAX_STEPS)
			var step := pow(ZOOM_STEP, amount)
			_zoom(step if e.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0 / step, e.position)
		elif e.button_index == MOUSE_BUTTON_LEFT and e.pressed and e.double_click:
			tools[tool].double_click(e.position)
		elif e.button_index == MOUSE_BUTTON_LEFT and e.pressed:
			measure.stop_typing()      # picking in the view again gives Delete back to the model (I48)
			tool_click(e.position)
		elif e.button_index == MOUSE_BUTTON_LEFT:
			tools[tool].release(e.position)
			_update_vcb()
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
		keys.press(e)


var _last_gesture := ""


func _repeat_gesture(e: InputEventGesture) -> bool:
	var amount: Variant = e.delta if e is InputEventPanGesture else e.factor
	var sig := "%d|%s|%s|%s|%s" % [Engine.get_process_frames(), e.get_class(), amount, e.position, e.shift_pressed]
	if sig == _last_gesture: return true
	_last_gesture = sig
	return false


const TRACKPAD_PX := 33.0     # Godot scales a trackpad's scroll by 0.03: this makes one finger-pixel = one mouse-pixel


const ZOOM_STEP := 0.88       # zoom per notch of a plain wheel (scroll amount 1)
const ZOOM_MAX_STEPS := 3.0   # one scroll event never zooms more than this many notches


func _zoom(f: float, screen: Vector2) -> void:
	var p := pick(screen)
	if p.get("hit", false) and f < 1.0:
		target = target.lerp(m2g(p["point"]), 1.0 - pow(0.88, log(f) / log(ZOOM_STEP)))   # toward the cursor, as much as zoomed
	dist = clampf(dist * f, 0.05, 50.0)
	_update_camera()


func _update_camera() -> void:
	var off := Vector3(0, 0, dist).rotated(Vector3.RIGHT, pitch).rotated(Vector3.UP, yaw)
	cam.position = target + off
	cam.look_at(target, Vector3.UP)
	if grid_mat != null:       # the grid fades out past a few orbit distances (no shimmer toward the horizon)
		grid_mat.set_shader_parameter("fade_start", dist * 1.5 + 0.5)
		grid_mat.set_shader_parameter("fade_end", dist * 3.5 + 1.5)
