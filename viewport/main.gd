extends Node3D
## Shop Sketch: tool-first viewport. Records an op log; FreeCAD (worker) catches up.
## Model space = Z-up millimetres (what the op log uses). Godot space = Y-up metres.

const WorkerClient := preload("res://worker_client.gd")
const Geo := preload("res://tool_geometry.gd")
const Inference := preload("res://inference.gd")
const Presenter := preload("res://presenter.gd")
const Preferences := preload("res://preferences.gd")
const Tool := preload("res://tools/tool.gd")
const GRID := Inference.GRID          # the grid and snap settings are inference's (T88); old names for consumers
const SNAP_PX := Inference.SNAP_PX

# ---------------- state ----------------
# The model's actions and their sync with FreeCAD live in the document controller (document.gd, A31, T39). These
# names forward to it, so tools and tests can keep writing m.ops, m.counters, m.seq.
const Document := preload("res://document.gd")
var doc: Document = Document.new()
var appearance = load("res://appearance.gd").new(doc, _beside_project)
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
var menus = load("res://menus.gd").new(self)
var ui = load("res://ui.gd").new(self)
# The model quick test and shell suite still read the menu names here.
var _menus: Dictionary:
	get: return menus.menus

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


func set_units(spec: String) -> bool:
	return measure.set_units(spec, true)

var oplog_path := ""
var drawing_script := ""
var test_mode := false
var shots_dir := ""

var cam: Camera3D
var camera_rig = load("res://camera_rig.gd").new(self)
# The preferences quick test still reads these names from main.
const TRACKPAD_PX := preload("res://camera_rig.gd").TRACKPAD_PX
const ZOOM_STEP := preload("res://camera_rig.gd").ZOOM_STEP
var yaw: float:
	get: return camera_rig.yaw
var dist: float:
	get: return camera_rig.dist
var trackpad_px: float:
	get: return camera_rig.trackpad_px
	set(v): camera_rig.trackpad_px = v
var zoom_step: float:
	get: return camera_rig.zoom_step
	set(v): camera_rig.zoom_step = v

var bodies_root: Node3D
var drafts_root: Node3D
var overlay: MeshInstance3D
var overlay_lines: MeshInstance3D
var marker: MeshInstance3D

# What's on screen (boards' triangles, corners, edges and cuts; drafts; confirmed boards; remembered states; waves)
# lives in the presenter (presenter.gd, A33b, T41). These names forward to it, for the window and its test suites.
var pres = Presenter.new()
var body_tris: Dictionary:          # body id -> PackedVector3Array (model mm, 3 per tri)
	get: return pres.body_tris
var body_verts: Dictionary:         # body id -> PackedVector3Array (unique corners)
	get: return pres.body_verts
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
func _show_state(key: String) -> bool: return pres.show_state(key)


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
var draft_bboxes: Dictionary:   # predicted bounds read by the recorded suites
	get: return pres.draft_tests.bounds
var preload_path := ""
var cursor2d: Node2D

var client: Node
var properties_panel: PanelContainer
var properties_request := 0
var properties_seq := -1

var ui_hint: Label
var ui_sync: Label
var ui_tip: Label
var ui_saved: Label                 # quiet 'Saving…' / 'Saved' (Q22): the wave means accepted, this means on disk
var saved_shown: Array = []         # tests: what the indicator has said, in order (T45: fast saves can't be missed)

# The registry quick test still reads the toolbar buttons here.
var _tool_buttons: Dictionary:
	get: return ui.tool_buttons

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
static func arr3(v: Vector3) -> Array: return Geo.arr3(v)
static func plane_basis(n: Vector3) -> Array: return Geo.plane_basis(n)

# ---------------- setup ----------------
func _ready() -> void:
	appearance.status.connect(_say_status)
	appearance.wood_selected.connect(menus.update_wood_checks)
	appearance.wood_selected.connect(func(_key: String): set_tool("paint"))
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
		elif a == "--lifecycletest": test_mode = true; fx_test = true; worker.lifecycle_test = true
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
		elif a.begins_with("--freecad="): worker.freecad_path = a.substr(10)
		elif a.begins_with("--worker="): worker.worker_script = a.substr(9)
		elif a.begins_with("--worker-log="): worker.worker_log = a.substr(13)
		elif a.begins_with("--shared-port="): worker.SHARED_PORT = int(a.substr(14))
	if port < 0:
		port = worker.pick_worker()

	line_scale = maxf(1.0, DisplayServer.screen_get_scale())
	get_window().content_scale_factor = line_scale        # the interface at its proper size on a Retina screen
	_make_materials()
	_make_world()
	_make_tools()                 # after the world: inference and the tool context take the camera and overlays
	_make_keys()
	ui.make_ui()
	_init_preferences()
	menus.make_menus()
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
	doc.save_changed.connect(ui.update_saved)
	doc.close_ready.connect(_close_now)
	doc.close_blocked.connect(_ask_close)
	get_tree().set_auto_accept_quit(false)       # closing waits for the latest save first (I55, _request_close)
	doc.op_removed.connect(_on_op_removed)
	doc.removed.connect(_on_removed)
	doc.idle.connect(_request_properties)
	doc.outside_waiting.connect(_on_outside_waiting)
	doc.outside_failed.connect(_on_outside_failed)
	doc.outside_keep_failed.connect(_on_outside_keep_failed)
	doc.outside_actions_landed.connect(_on_outside_actions_landed)
	doc.reloaded.connect(_on_reloaded)
	doc.kept_mine.connect(_on_kept_mine)
	_make_selection()
	client.replied.connect(_on_worker)
	client.link_up.connect(_on_link_up)
	client.link_down.connect(_on_link_down)
	client.start(worker.resolve_port(port))
	camera_rig.camera = cam
	camera_rig.update_camera()
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


# The native Grid snap and New board menu commands still call this.
func _update_toggles() -> void:
	ui.update_toggles()


# ---------------- mesh helpers ----------------
const LINE_PX := Presenter.LINE_PX          # width of edges and outlines, in points (doubled on a Retina screen)
const GRID_LINE_PX := 1.0
const AXIS_LINE_PX := 1.75
var line_scale := 1.0         # physical pixels per point


func _lines(segs_m: PackedVector3Array, color: Color, width_pt := LINE_PX, bias := -1.0) -> MeshInstance3D:
	return pres.lines(segs_m, color, width_pt, bias)


static func _ekey(p: Vector3, q: Vector3) -> String: return Geo.edge_key(p, q)
static func feature_edges(tris: PackedVector3Array) -> PackedVector3Array: return Geo.feature_edges(tris)
static func unique_verts(tris: PackedVector3Array) -> PackedVector3Array: return Geo.unique_verts(tris)


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
		tool_info[t["id"]] = t
		if t["key"] != KEY_NONE: tool_keys[t["key"]] = t["id"]


func _make_tool_context():
	"""Wire the capability owners and window callbacks shared by every tool."""
	return load("res://tool_context.gd").new({
		"infer": infer, "pres": pres, "sel": sel, "doc": doc, "measure": measure,
		"cursor": _cursor_pos,
		"tri_mesh": pres.tri_mesh, "line_mesh": pres.line_mesh, "overlay": overlay, "overlay_lines": overlay_lines,
		"materials": {"hover": mat_hover, "profile": mat_rect, "draft": mat_draft, "cut": mat_cut, "cut_highlight": mat_cut_hl},
		"show_marker": pres.show_marker, "hide_marker": func(): marker.visible = false,
		"push_filter": pres.draft_tests.filter if test_mode else Callable(),
		"refresh_tip": _update_tip, "clear_rejection": func(): reject_note = "",
		"refresh_hint": func(): ui_hint.text = tools[tool].hint(),
		"show_status": _say_status, "tool_active": func(id: String) -> bool: return tool == id,
		"new_board": func() -> bool: return new_board,
		"appearance": appearance,
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
	pres.clear_guides()
	if ui_tip: ui_tip.visible = false
	overlay.mesh = null; overlay_lines.mesh = null
	ui_hint.text = tools[t].hint()
	if ui.tool_buttons.has(t): ui.tool_buttons[t].set_pressed_no_signal(true)
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
	var n := sel.siblings_of(hover_body).size()
	if n > 0:
		txt = ((txt + "\n") if txt != "" else "") + "changes %d linked board%s" % [n + 1, "" if n == 0 else "s"]
	ui_tip.visible = txt != ""
	ui_tip.text = doc.readable_ids(txt)
	ui_tip.position = screen + Vector2(22, 20)


# ---------------- selection and context (selection.gd, A33b, T41) ----------------
# What a click stands for, the entered assembly or array, hidden boards and the board under the cursor live in
# selection.gd (`m.sel`); it adds hide / assembly / unlink ops through the document. These properties forward to it,
# while callers use m.sel.* directly for its methods. main draws what its signals say.
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
		menus.update_menu_checks()


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
	var op := change.duplicate(true)
	op["id"] = doc.next_id("pr")
	op["type"] = "property_edit"
	ops.append(op)
	properties_panel.message("Applying property…")
	sync()

# The Wood menu in menus.gd still uses these names.
var wood_library: Dictionary:
	get: return appearance.wood_library
var wood_keys: Array:
	get: return appearance.wood_keys
var paint_material: String:
	get: return appearance.paint_material


func set_paint_material(k: String) -> void:
	appearance.set_paint_material(k)


func _turn_grain() -> void:
	appearance.turn_grain(hover_body)


# ---------------- linked boards (T12: A22c, I28, Q28, Q29) ----------------
# Copies share one definition: editing one edits all. While a tool is over a linked board its copies get a soft
# tint and the tooltip counts them; U (Edit > Make unique) frees the board under the cursor, Edit > Detach from
# array frees its position.


func _show_siblings(bid: String) -> void:
	hover_body = bid
	pres.show_siblings(sel.siblings_of(bid) if tool_info.get(tool, {}).get("show_links", false) else [])


func _say_status(txt: String) -> void:
	ui_sync.text = doc.readable_ids(txt)
	ui_sync.remove_theme_color_override("font_color")


# ---------------- snapping visuals (the engine is inference.gd) ----------------
const SNAP_COLORS := Presenter.SNAP_COLORS   # the rendering constants are the presenter's (T88)


func _cursor_pos() -> Vector2:
	return cursor2d.position if test_mode and cursor2d != null else get_viewport().get_mouse_position()


# ---------------- axes ----------------
const AXIS_COLORS := Presenter.AXIS_COLORS

static func _axis_vec(ax: int) -> Vector3: return Geo.axis_vector(ax)
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
			worker.say_worker("%s is open in another window" % name)
		return
	_model_before = ""
	if not resp.get("ok", false):
		ui_sync.text = "✗ couldn't open %s: %s" % [model_path, resp.get("error", "?")]
		ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))
		return
	var adopt := not (test_mode and not heavy_test and _first_open)   # tests start clean; a model opened later (switch_model) adopts its history
	_first_open = false
	doc.on_opened(resp, adopt)
	measure.on_opened(resp, adopt)
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
	if op.type in ["line", "arc"]:
		pres.register_line(op)
	elif op["type"] in ["rect", "circle"]:
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
	if resp.get("cmd", "") == "outside_save":        # FreeCAD saved this model (A36, T64)
		doc.on_outside_save(resp)
		return
	if resp.get("cmd", "") == "reload":
		doc.on_reload_reply(resp)
		return
	if resp.get("cmd", "") == "keep_mine":
		doc.on_keep_mine_reply(resp)
		return
	if resp.get("cmd", "") == "set_units":
		measure.on_set_units_reply(resp)
		return
	if not resp.get("cmd", "") in ["sync", "replay"]:   # flush, hello, bye, quit, or an error for some other request:
		if not resp.get("ok", false):                    # never sync state (T70)
			worker.say_worker("✗ worker error: %s" % resp.get("error", "?"))
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
		ui_sync.text = "✗ rejected " + doc.readable_ids(reject_note)
		ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))
	elif _startup_prefs_problem != "":
		_say_status(_startup_prefs_problem)
		_startup_prefs_problem = ""
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
	if appearance.wood_library.is_empty() and appearance.load_library(dir): menus.build_materials_menu()
	appearance.set_boards(data)
	pres.forget_siblings()


static func _ops_key(list: Array) -> String:
	return Document.ops_key(list)


# ---------------- the frame ----------------
const DEFAULT_BASE := Presenter.DEFAULT_BASE   # a board's colour before FreeCAD says (tools start waves with it)
var reject_note := ""
var force_reject_next: bool:
	get: return pres.draft_tests.reject_next
	set(v): pres.draft_tests.reject_next = v


func _process(delta: float) -> void:
	movie_clock += delta
	worker.watch_worker(delta)
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
	if tg.has("region"): out.append_array(tg.region.get("lines", []))
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
var worker = load("res://worker_process.gd").new(self)
# The lifecycle suite and test dispatcher still read these names here.
var worker_port: int:
	get: return worker.worker_port
var worker_pid: int:
	get: return worker.worker_pid
var _first_open := true
var lifecycle_test: bool:
	get: return worker.lifecycle_test

# The window <-> worker protocol's version (docs/protocol.md): bump it when a message or shared-file field changes.
# The worker reports its own (worker/serve.py PROTOCOL_VERSION) in hello; a worker speaking another isn't shared.
const PROTOCOL_VERSION := 11


func _send_open() -> void:
	doc.send_open()


func _on_link_down() -> void:
	if worker.worker_pid > 0 or opened:
		worker.say_worker("● lost the FreeCAD worker - reconnecting")


func _on_link_up(first: bool) -> void:
	if first: return
	doc.on_link_up()
	measure.on_link_up()


func _exit_tree() -> void:
	worker.shutdown_worker()


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
	worker.say_worker("saving %s before closing…" % model_path.get_file())
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
			ui.update_saved()
			ui_sync.text = ""


func _close_now() -> void:
	close_done = true
	if test_mode: return                # tests check close_done; the run goes on
	worker.shutdown_worker()
	get_tree().quit()


# ---------------- outside saves (A36, T64) ----------------
# FreeCAD saved the open model. The document reloads it once nothing is on its way; if actions haven't landed in
# OUTSIDE_SAVE_WAIT, a dialog asks: Use FreeCAD's version (reload; the unfinished actions stay in the journal) or
# Keep Shop Sketch's (FreeCAD's file copied aside first). The worker writes nothing over FreeCAD's save meanwhile.
const OUTSIDE_SAVE_WAIT := 10.0     # seconds actions pending at an outside save get to land before asking (tunable)
var _outside_try := 0               # numbers each wait, so an old wait's timer can't ask
var _outside_dialog: ConfirmationDialog
var _outside_question_model := ""  # the open Godot dialog, or the question simulated in test mode
var _outside_closed_model := ""    # report an automatically closed question when its reload lands
var _outside_question_text := ""
var _outside_question_reason := ""
var outside_asked: Array = []       # tests: the reasons the dialog would have given (it isn't shown in test mode)
var outside_closed := 0            # tests: questions that automatically closed when the actions landed
var reload_waves: Array = []        # tests: the boards the last reload's wave ran on


func _on_outside_waiting() -> void:
	worker.say_worker("FreeCAD saved %s - waiting for Shop Sketch's last actions to land" % model_path.get_file())
	_outside_try += 1
	var try_then := _outside_try
	get_tree().create_timer(OUTSIDE_SAVE_WAIT).timeout.connect(func() -> void:
		if _outside_try == try_then and not doc.outside.is_empty() and doc.outside_seq < 0:
			_ask_outside())


func _ask_outside() -> void:
	if _outside_question_model == model_path: return
	var reason := "they hadn't landed after %d s" % int(OUTSIDE_SAVE_WAIT)
	if not client.connected or (worker.worker_pid > 0 and not OS.is_process_running(worker.worker_pid)):
		reason = "the FreeCAD worker stopped"
	elif doc.in_flight:
		reason = "the FreeCAD worker hasn't answered for %d s (it may be stuck)" % int(OUTSIDE_SAVE_WAIT)
	worker.log_worker("outside save of %s with actions pending: %s; asking" % [model_path, reason])
	var text := ("%s was saved in FreeCAD while Shop Sketch still had actions on their way: %s.\n\n"
		+ "Use FreeCAD's version: its file becomes the model; Shop Sketch's unfinished actions stay in the journal.\n"
		+ "Keep Shop Sketch's: FreeCAD's file is first copied aside as %s.freecad-<time>.FCStd.") % [
		model_path.get_file(), reason, model_path.get_file().get_basename()]
	_show_outside_question(text, reason)


func _on_outside_failed(error: String) -> void:
	_outside_try += 1
	_outside_closed_model = ""
	var reason := "couldn't open FreeCAD's save: " + error
	worker.log_worker("outside save of %s: %s; asking" % [model_path, reason])
	var text := ("%s was saved in FreeCAD, but Shop Sketch couldn't open FreeCAD's save: %s.\n\n"
		+ "Use FreeCAD's version: try opening it again.\n"
		+ "Keep Shop Sketch's: FreeCAD's file is first copied aside as %s.freecad-<time>.FCStd.") % [
		model_path.get_file(), error, model_path.get_file().get_basename()]
	_show_outside_question(text, reason)


func _on_outside_keep_failed(error: String) -> void:
	_on_sync_failed(error)
	worker.log_worker("outside save of %s: %s" % [model_path, error])
	_outside_try += 1
	var try_then := _outside_try
	# The macOS alert handles its choice on the same call stack. Reopen on the next turn.
	var ask_again := func() -> void:
		if _outside_try != try_then or doc.outside.is_empty() or doc.outside_seq >= 0:
			return
		if _outside_question_text.is_empty():
			_ask_outside()
		else:
			_show_outside_question(_outside_question_text, _outside_question_reason)
	ask_again.call_deferred()


func _show_outside_question(text: String, reason: String) -> void:
	_dismiss_outside_question()
	_outside_question_text = text
	_outside_question_reason = reason
	if test_mode:
		_outside_question_model = model_path
		outside_asked.append(reason)
		return
	var title := "FreeCAD saved this model while Shop Sketch was busy"
	if DisplayServer.has_feature(DisplayServer.FEATURE_NATIVE_DIALOG):
		DisplayServer.dialog_show(title, text, PackedStringArray(["Use FreeCAD's version", "Keep Shop Sketch's"]),
			func(i: int) -> void: _outside_choice("mine" if i == 1 else "freecad"))
		return
	var dlg := ConfirmationDialog.new()
	_outside_dialog = dlg
	_outside_question_model = model_path
	dlg.title = title
	dlg.dialog_text = text
	dlg.ok_button_text = "Use FreeCAD's version"
	dlg.cancel_button_text = "Keep Shop Sketch's"
	dlg.confirmed.connect(func() -> void: _outside_choice("freecad"))
	dlg.canceled.connect(func() -> void: _outside_choice("mine"))
	add_child(dlg)
	dlg.popup_centered()


func _dismiss_outside_question() -> void:
	_outside_question_model = ""
	if is_instance_valid(_outside_dialog):
		_outside_dialog.hide()
		_outside_dialog.queue_free()
		_outside_dialog = null


func _on_outside_actions_landed() -> void:
	if _outside_question_model != model_path: return
	_dismiss_outside_question()
	_outside_closed_model = model_path
	if test_mode: outside_closed += 1


func _outside_choice(choice: String) -> void:
	if doc.outside.is_empty() or doc.outside_seq >= 0: return
	_dismiss_outside_question()
	if choice == "mine":
		measure.flush_units_if_dirty()
		doc.send_keep_mine()
	else: doc.send_reload()


func _on_reloaded(resp: Dictionary) -> void:
	"""FreeCAD's save is on screen, with the wave over the boards it changed."""
	measure.on_reloaded(resp)
	pres._states.clear(); pres._state_lru.clear()     # remembered states are of the file before FreeCAD's save
	var data = JSON.parse_string(FileAccess.get_file_as_string(String(resp.get("outdir", out_dir)).path_join("bodies.json")))
	reload_waves = []
	if typeof(data) == TYPE_ARRAY:
		for b in data:
			if not b["id"] in resp.get("changed", []): continue
			var bb: Array = b["world_bbox"]
			var lo := Vector3(bb[0], bb[1], bb[2]); var hi := Vector3(bb[3], bb[4], bb[5])
			_begin_wave("reload:" + b["id"], (lo + hi) * 0.5, PackedVector3Array([lo, hi]), false, b["id"])
			pres.op_waves["reload:" + b["id"]]["state"] = "ok"
			reload_waves.append(b["id"])
	pres.apply_confirmed(String(resp.get("outdir", out_dir)), _ops_key(resp.get("ops", [])))
	_rebuild_rect_drafts()
	_apply_context()
	var n: int = resp.get("changed", []).size()
	var dropped: int = resp.get("dropped", []).size()
	ui_sync.text = "↻ took FreeCAD's save of %s: %d board%s changed%s" % [model_path.get_file(), n, "" if n == 1 else "s",
		"" if dropped == 0 else "; %d Shop Sketch action%s it didn't have kept in the journal" % [dropped, "" if dropped == 1 else "s"]]
	if _outside_closed_model == model_path:
		ui_sync.text += " (Shop Sketch's actions landed while you were deciding, so the question closed)"
	_outside_closed_model = ""
	ui_sync.add_theme_color_override("font_color", Color(0.1, 0.5, 0.15))


func _on_kept_mine(resp: Dictionary) -> void:
	var aside = resp.get("aside")
	ui_sync.text = "kept Shop Sketch's %s" % model_path.get_file()
	if aside is String and aside != "":
		ui_sync.text += "; FreeCAD's save is beside it as %s" % aside.get_file()
	ui_sync.add_theme_color_override("font_color", Color(0.1, 0.5, 0.15))


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
	_outside_try += 1
	_dismiss_outside_question()
	_outside_closed_model = ""
	_outside_question_text = ""
	_outside_question_reason = ""
	properties_seq = -1
	properties_request += 1
	sel.set_selection([])
	doc.reset()                     # a reply still on its way belongs to the old model: it's ignored
	measure.reset_for_model()
	pres.reset()
	reject_note = ""
	tools["move"].last_oid = ""; tools["move"].memo.clear()
	set_tool(tool)
	marker.visible = false


# ---------------- preferences (I63, T111) ----------------
const PREFERENCES_PATH := "user://preferences.json"
const PREFERENCES_KEY := KEY_MASK_META | KEY_COMMA
var preferences_path := PREFERENCES_PATH
var prefs := Preferences.new()
var _prefs_timer: Timer
var _startup_prefs_problem := ""


func _init_preferences() -> void:
	if test_mode: return
	_start_preferences()


func _start_preferences() -> void:
	"""Load preferences_path and start the 0.5 s poll timer (skipped at startup in test_mode, I63)."""
	_load_preferences(true)
	if not doc.opened and not measure.units_user_set:
		measure.units = measure.default_units()
		measure.update()
	if _prefs_timer == null:
		_prefs_timer = Timer.new()
		_prefs_timer.name = "PreferencesTimer"
		_prefs_timer.wait_time = 0.5
		_prefs_timer.one_shot = false
		_prefs_timer.timeout.connect(_poll_preferences)
		add_child(_prefs_timer)
	_prefs_timer.start()


func _poll_preferences() -> void:
	if prefs.changed_on_disk(preferences_path):
		_load_preferences(false)


func _load_preferences(at_start: bool) -> void:
	var res := prefs.load_from(preferences_path)
	_apply_preferences(res["values"])
	var msg := _preferences_status(res, at_start)
	if msg != "":
		_say_status(msg)
		if at_start and not doc.opened and not res["problems"].is_empty():
			_startup_prefs_problem = msg
	elif res["problems"].is_empty():
		_startup_prefs_problem = ""


func _apply_preferences(values: Dictionary) -> void:
	"""Apply preferences values ({units, tuning}, or a tuning dictionary) to live tunables and default units."""
	var t: Dictionary = values["tuning"] if typeof(values.get("tuning")) == TYPE_DICTIONARY else values
	if t.has("GRID"): Inference.grid = float(t["GRID"])
	if t.has("SNAP_PX"): Inference.snap_px = float(t["SNAP_PX"])
	if t.has("EDGE_PX"): Inference.edge_px = float(t["EDGE_PX"])
	if t.has("INFER_DEG"): Inference.infer_deg = float(t["INFER_DEG"])
	if t.has("RELEASE_DEG"): Inference.release_deg = float(t["RELEASE_DEG"])
	if t.has("DRAG_PX"): Tool.drag_px = float(t["DRAG_PX"])
	if t.has("HOLD_MS"): Tool.hold_ms = int(t["HOLD_MS"])
	if t.has("TRACKPAD_PX"): trackpad_px = float(t["TRACKPAD_PX"])
	if t.has("ZOOM_STEP"): zoom_step = float(t["ZOOM_STEP"])
	if typeof(values.get("units")) == TYPE_DICTIONARY:
		var def_u = values["units"].get("default")
		measure.pref_default_units = String(def_u) if typeof(def_u) == TYPE_STRING else ""


func _preferences_status(res: Dictionary, at_start: bool) -> String:
	var problems: Array = res.get("problems", [])
	if not problems.is_empty():
		var first: String = problems[0]
		if problems.size() > 1:
			return "%s (and %d more)" % [first, problems.size() - 1]
		return first
	if at_start:
		return ""
	var changed: Array = res.get("changed", [])
	if changed.is_empty():
		return ""
	var parts: Array[String] = []
	for k in changed:
		if k == "units.default":
			parts.append("default units %s" % (measure.pref_default_units if measure.pref_default_units != "" else "none"))
		else:
			parts.append("%s %s" % [k, Preferences.format_num(_live_tuning(k))])
	return "Preferences: " + ", ".join(parts)


func _live_tuning(key: String) -> float:
	match key:
		"GRID": return Inference.grid
		"SNAP_PX": return Inference.snap_px
		"EDGE_PX": return Inference.edge_px
		"INFER_DEG": return Inference.infer_deg
		"RELEASE_DEG": return Inference.release_deg
		"DRAG_PX": return Tool.drag_px
		"HOLD_MS": return float(Tool.hold_ms)
		"TRACKPAD_PX": return trackpad_px
		"ZOOM_STEP": return zoom_step
	return 0.0


func _open_preferences() -> void:
	var err := prefs.write_defaults(preferences_path)
	if err != OK and err != ERR_ALREADY_EXISTS:
		_say_status("Couldn't write preferences.json: %s" % error_string(err))
		return
	OS.shell_open(ProjectSettings.globalize_path(preferences_path))


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
# Keys go to keys.gd (T75), camera input to camera_rig.gd (T113).
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
	if (e is InputEventPanGesture or e is InputEventMagnifyGesture) and _repeat_gesture(e):
		return       # Godot 4.6 hands an injected gesture over twice in the same frame (seen in tests); act once
	if camera_rig.handle_input(e):
		return
	if e is InputEventMouseButton:
		if e.button_index == MOUSE_BUTTON_LEFT and e.pressed and e.double_click:
			tools[tool].double_click(e.position)
		elif e.button_index == MOUSE_BUTTON_LEFT and e.pressed:
			measure.stop_typing()      # picking in the view again gives Delete back to the model (I48)
			tool_click(e.position)
		elif e.button_index == MOUSE_BUTTON_LEFT:
			tools[tool].release(e.position)
			_update_vcb()
	elif e is InputEventMouseMotion:
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
