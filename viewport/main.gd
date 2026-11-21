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
var snap_test := false
var rect_test := false
var perf_test := false
var shell_test := false
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
		elif a == "--snaptest": test_mode = true; fx_test = true; snap_test = true
		elif a == "--recttest": test_mode = true; fx_test = true; rect_test = true
		elif a == "--perftest": test_mode = true; fx_test = true; perf_test = true
		elif a == "--shelltest": test_mode = true; fx_test = true; shell_test = true
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
	if port < 0:
		port = _free_port(7878)
		worker_port = port
		_start_worker()

	line_scale = maxf(1.0, DisplayServer.screen_get_scale())
	get_window().content_scale_factor = line_scale        # the interface at its proper size on a Retina screen
	_make_materials()
	_make_tools()
	_make_world()
	_make_ui()
	_make_menus()
	_set_title()
	if not test_mode: _remember_model(model_path)
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
var ui_vcb_label: Label
var ui_vcb_box: PanelContainer
var _vcb_style: StyleBoxFlat
var _vcb_style_typing: StyleBoxFlat


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
	row.add_child(_segments([["Rectangle", "rect", "Rectangle (R)"], ["Push/Pull", "push", "Push/Pull (P)"], ["Move", "move", "Move (M)"]], false))
	for spec in [["Undo", "undo", "Undo (⌘Z)"], ["Drawing", "drawing", "Drawing and cut list (D)"]]:
		var b := Button.new(); b.text = spec[0]; b.tooltip_text = spec[2]; b.focus_mode = Control.FOCUS_NONE
		b.pressed.connect(_menu.bind(spec[1]))
		row.add_child(b)
	var gap := Control.new(); gap.size_flags_horizontal = Control.SIZE_EXPAND_FILL; gap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(gap)
	row.add_child(_segments([["Grid snap", "grid", "Snap to a 10 mm grid (G)"], ["New board", "newboard", "Pushing a rectangle drawn on a face makes a separate board (B)"]], true))
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
	ui_vcb_label = Label.new(); ui_vcb_label.theme_type_variation = "Quiet"
	ui_vcb_box = PanelContainer.new()
	ui_vcb_box.custom_minimum_size = Vector2(150, 0)
	_vcb_style = _box(_c(Color(1, 1, 1), Color(0.11, 0.11, 0.12)), 5, _c(Color(0.75, 0.75, 0.77), Color(0.33, 0.33, 0.35)), 1, Vector2(8, 2))
	_vcb_style_typing = _vcb_style.duplicate()
	_vcb_style_typing.border_color = accent; _vcb_style_typing.set_border_width_all(2)
	ui_vcb_box.add_theme_stylebox_override("panel", _vcb_style)
	ui_vcb = Label.new()
	ui_vcb.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	ui_vcb_box.add_child(ui_vcb)
	srow.add_child(ui_hint); srow.add_child(ui_sync); srow.add_child(ui_vcb_label); srow.add_child(ui_vcb_box)
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
var infer                           # inference.gd: the one snapping engine


func _make_tools() -> void:
	infer = load("res://inference.gd").new()
	infer.m = self
	for k in ["rect", "push", "move"]:
		tools[k] = load("res://tools/%s_tool.gd" % k).new()
		tools[k].setup(self)


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
	tool = t
	for k in tools: tools[k].reset()
	vcb = ""
	if guides: guides.mesh = null
	if ui_tip: ui_tip.visible = false
	overlay.mesh = null; overlay_lines.mesh = null
	ui_hint.text = tools[t].hint()
	if _tool_buttons.has(t): _tool_buttons[t].set_pressed_no_signal(true)
	_update_vcb()


func _update_vcb() -> void:
	var t = tools[tool]
	var val: String = vcb if vcb != "" else t.vcb_value()
	ui_vcb_label.text = t.vcb_label()
	ui_vcb.text = (val + " mm") if val != "" else ""
	ui_vcb_box.add_theme_stylebox_override("panel", _vcb_style_typing if vcb != "" else _vcb_style)   # typing: accent ring


func tool_move(screen: Vector2) -> void:
	tools[tool].mouse_moved(screen)
	_update_tip(screen)


func tool_click(screen: Vector2) -> void:
	if tool != "move": tools["move"].last_oid = ""
	tools[tool].click(screen)
	_update_vcb()


static func _rect_pts(origin: Vector3, x: Vector3, y: Vector3, du: float, dv: float) -> PackedVector3Array:
	return PackedVector3Array([origin, origin + x * du, origin + x * du + y * dv, origin + y * dv])


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


func _update_tip(screen: Vector2) -> void:
	if ui_tip == null: return
	var txt: String = tools[tool].tip()
	ui_tip.visible = txt != ""
	ui_tip.text = txt
	ui_tip.position = screen + Vector2(22, 20)


# ---------------- snapping visuals (the engine is inference.gd) ----------------
const SNAP_COLORS := {"endpoint": Color(0.1, 0.65, 0.1), "midpoint": Color(0.1, 0.7, 0.8), "on edge": Color(0.85, 0.15, 0.15),
					  "on face": Color(0.2, 0.35, 0.95), "back face": Color(0.2, 0.35, 0.95), "face behind": Color(0.2, 0.35, 0.95)}
var body_edges := {}            # body id -> feature edge segments (model mm)
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
const AXIS_COLORS := [Color(0.85, 0.15, 0.15, 0.16), Color(0.15, 0.65, 0.2, 0.16), Color(0.2, 0.35, 0.95, 0.16)]

static func _axis_vec(ax: int) -> Vector3:
	return [Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)][ax]


static func _mirror_tris(tris: PackedVector3Array, ax: int, c: float) -> PackedVector3Array:
	var out := PackedVector3Array()
	for q in tris:
		var m := q
		m[ax] = 2.0 * c - q[ax]
		out.append(m)
	return out


# ---------------- typed input, undo ----------------
func apply_vcb() -> void:
	var txt := vcb.strip_edges()
	vcb = ""
	if txt != "":
		tools[tool].typed(txt)
	_update_vcb()


func _on_open(resp: Dictionary) -> void:
	if not resp.get("ok", false):
		ui_sync.text = "✗ couldn't open %s: %s" % [model_path, resp.get("error", "?")]
		ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))
		return
	opened = true
	if test_mode and not heavy_test and _first_open:
		_first_open = false
		return                      # tests start clean; a model opened later (switch_model) adopts its history
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
			_apply_confirmed(resp["outdir"], key)
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


# ---------------- confirmed boards (T3) ----------------
# Each board FreeCAD confirmed is a node built from its own file (worker: meshes/<board>-<key>.bin: triangles,
# normals, and FreeCAD's exact edges and corners). A reply builds only the files it hasn't seen; every other
# board stays on screen untouched. Nodes are shared by the remembered states below.
const M2G_BASIS := Basis(Vector3(1, 0, 0), Vector3(0, 0, -1), Vector3(0, 1, 0))     # model Z-up -> Godot Y-up
var _boards := {}             # mesh file -> {"node", "bid", "tris", "verts", "edges"}


func _apply_confirmed(dir: String, key: String) -> void:
	var data = JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("bodies.json")))
	if typeof(data) != TYPE_ARRAY: return
	var files := {}
	for b in data:
		files[b["id"]] = b["mesh"]
		if not _boards.has(b["mesh"]):
			_boards[b["mesh"]] = _build_board(dir, b)
	_load_cuts(dir)
	_show_boards(files)
	_remember_state(key, files)


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
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(b["color"][0], b["color"][1], b["color"][2]).linear_to_srgb()   # as glTF import did
		mat.roughness = 0.85
		mesh.surface_set_material(0, mat)
		mi.mesh = mesh
		_add_collision(mi, "body_id", bid)
	var edges := _lines(parts[2], Color(0.08, 0.08, 0.08))
	mi.add_child(edges)
	mi.set_meta("body_mesh", true); mi.set_meta("edges", edges)
	return {"node": mi, "bid": bid, "tris": tris, "verts": parts[3], "edges": parts[2]}


func _show_boards(files: Dictionary) -> void:
	"""Put exactly these boards (board id -> mesh file) on screen, keeping the ones already there."""
	var want := {}
	for bid in files: want[_boards[files[bid]]["node"]] = files[bid]
	for c in bodies_root.get_children():
		if not want.has(c): bodies_root.remove_child(c)
	body_tris = {}; body_verts = {}; body_edges = {}
	for node in want:
		var e: Dictionary = _boards[want[node]]
		var bid: String = e["bid"]
		body_tris[bid] = e["tris"]; body_verts[bid] = e["verts"]; body_edges[bid] = e["edges"]
		if node.get_parent() == bodies_root: continue
		bodies_root.add_child(node)
		node.visible = true                          # a move hides the board's old spot until FreeCAD answers
		node.material_override = null                # a wave that ran on it earlier is over
		var edges: MeshInstance3D = node.get_meta("edges")
		edges.material_override = null
		for oid in op_waves:                         # a wave running for this board carries onto it
			if bid in op_waves[oid]["bodies"]:
				_attach_wave(oid, node, edges, _base_of(node))


# ---------------- confirmed states (T10) ----------------
# The last few model states FreeCAD confirmed (which board files they had). Undo shows the previous one at once,
# so you can keep undoing while FreeCAD catches up, even when it has to rebuild the whole model (its
# command-line program keeps only 20 undo steps). FreeCAD's answer then matches what's on screen: no reload.
const STATE_CACHE_MAX := 40
var _states := {}             # ops key -> {"files": board id -> mesh file, "cuts"}
var _state_lru: Array = []    # keys, oldest first
var shown_key := ""           # the confirmed state on screen
var predicted_undo := false   # the model on screen is a remembered state; FreeCAD is still catching up


static func _ops_key(list: Array) -> String:
	return JSON.stringify(list).sha256_text()


func _remember_state(key: String, files: Dictionary) -> void:
	_states[key] = {"files": files, "cuts": body_cuts.duplicate()}
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
		if not used.has(f) and _boards[f]["node"].get_parent() != bodies_root:
			_boards[f]["node"].queue_free()
			_boards.erase(f)


func _show_state(key: String) -> bool:
	"""Put a remembered confirmed state back on screen (undo). False if it isn't remembered."""
	if not _states.has(key): return false
	if key == shown_key: return true
	var st: Dictionary = _states[key]
	body_cuts = st["cuts"].duplicate()
	_show_boards(st["files"])
	shown_key = key
	_state_lru.erase(key); _state_lru.append(key)
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
	if OS.get_name() == "Windows":
		OS.set_environment("SERVE_PORT", str(worker_port))
		worker_pid = OS.create_process(freecad_path, [worker_script])
	else:
		worker_pid = OS.create_process("/bin/sh", ["-c", "SERVE_PORT=%d exec %s %s >> %s 2>&1" % [
			worker_port, _sh(freecad_path), _sh(worker_script), _sh(worker_log)]])
	print("SHOPSKETCH worker pid %d on port %d: %s (log %s)" % [worker_pid, worker_port, worker_script, worker_log])


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


func switch_model(path: String, fresh := false) -> void:
	"""Close the current model (the worker keeps it saved) and open another; fresh = start it empty."""
	if path.get_extension().to_lower() != "fcstd": path += ".FCStd"
	if path == model_path and not fresh: return
	_reset_model_state()
	model_path = path
	if not test_mode:
		out_dir = _out_for(path)
		_remember_model(path)
	DirAccess.make_dir_recursive_absolute(out_dir)
	opened = false
	_set_title()
	client.send({"cmd": "open", "model": model_path, "fresh": fresh})
	ui_sync.text = "opening %s" % path.get_file()


func _reset_model_state() -> void:
	seq += 1                        # a reply still on its way belongs to the old model: it's ignored
	dirty = false
	for oid in op_waves.keys(): _end_wave(oid)
	for k in drafts: drafts[k].queue_free()
	drafts.clear(); rects.clear(); confirmed_ids.clear()
	ops.clear()
	for k in counters: counters[k] = 0
	undo_floor = 0
	reject_note = ""
	for c in bodies_root.get_children(): bodies_root.remove_child(c)
	for f in _boards: _boards[f]["node"].queue_free()
	_boards.clear(); _states.clear(); _state_lru.clear(); shown_key = ""
	body_tris = {}; body_verts = {}; body_edges = {}; body_cuts = {}
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
		["File", [["New…", "new", KEY_MASK_META | KEY_N], ["Open…", "open", KEY_MASK_META | KEY_O], [],
				  ["Show in Finder", "reveal", 0], [], ["Drawing and cut list (D)", "drawing", 0]]],
		["Edit", [["Undo", "undo", KEY_MASK_META | KEY_Z]]],
		["Tools", [["Rectangle (R)", "rect", 0], ["Push/Pull (P)", "push", 0], ["Move (M)", "move", 0]]],
		["View", [["Grid snap (G)", "grid", -1], ["New board on faces (B)", "newboard", -1]]],
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


func _menu(tag) -> void:
	var now := Time.get_ticks_msec()
	if now - int(_menu_last.get(tag, -1000)) < 150: return        # the menu and the key both fired
	_menu_last[tag] = now
	match tag:
		"new": _file_dialog(true)
		"open": _file_dialog(false)
		"reveal": OS.shell_show_in_file_manager(model_path)
		"drawing": export_drawing()
		"undo": undo()
		"rect", "push", "move": set_tool(tag)
		"grid": grid_snap = not grid_snap; _update_toggles()
		"newboard": new_board = not new_board; _update_toggles()


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
	if fx_test and cursor2d != null and (e is InputEventMouseMotion or e is InputEventMouseButton) \
			and e.position.distance_to(cursor2d.position) > 0.5:
		return       # tests: the real pointer over the window isn't the test's cursor; ignore it
	if e is InputEventMouseButton:
		if e.button_index in [MOUSE_BUTTON_MIDDLE, MOUSE_BUTTON_RIGHT]:
			orbiting = e.pressed and not e.shift_pressed
			panning = e.pressed and e.shift_pressed
		elif e.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN] and e.pressed:
			# zoom by how much was scrolled: a smooth-scrolling mouse (MX Master) sends many small steps per notch
			var amount := clampf(e.factor if e.factor > 0.0 else 1.0, 0.0, ZOOM_MAX_STEPS)
			var step := pow(ZOOM_STEP, amount)
			_zoom(step if e.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0 / step, e.position)
		elif e.button_index == MOUSE_BUTTON_LEFT and e.pressed:
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
		if (e.ctrl_pressed or e.meta_pressed) and e.keycode == KEY_Z: _menu("undo"); return    # Cmd+Z on a Mac
		if (e.ctrl_pressed or e.meta_pressed) and e.keycode == KEY_N: _menu("new"); return
		if (e.ctrl_pressed or e.meta_pressed) and e.keycode == KEY_O: _menu("open"); return
		match e.keycode:
			KEY_ESCAPE: set_tool(tool); return
			KEY_ENTER, KEY_KP_ENTER: apply_vcb(); return
			KEY_BACKSPACE: vcb = vcb.left(-1); _update_vcb(); return
		var ch := char(e.unicode) if e.unicode > 0 else ""
		var t = tools[tool]
		if t.key(e): return                              # the tool's own keys (Move: modifiers, axis locks)
		if t.busy() and ch != "" and t.accepts(ch):
			vcb += ch; _update_vcb(); return
		match e.keycode:
			KEY_R: set_tool("rect")
			KEY_P: set_tool("push")
			KEY_M: set_tool("move")
			KEY_G: _menu("grid")
			KEY_B: _menu("newboard")
			KEY_D: export_drawing()


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
