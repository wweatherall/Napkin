extends Control
## H202 fit detachment design demo. Two isolated views use Napkin's confirmed board and line styles.

const Geo := preload("res://tool_geometry.gd")
const Presenter := preload("res://presenter.gd")
const NapkinUI := preload("res://ui.gd")

const EDGE := Color(0.08, 0.08, 0.08)
const INK := Color(0.24, 0.28, 0.32)
const END_X := 0.06
const FIT_LENGTH := 0.60
const CONNECTOR_Y := 0.27
const CONNECTOR_Z := 0.265
const LEAD_IN := 0.24
const EFFECT_TIME := 1.08
const LINK_COUNT := 4

# The presenter's line helper only reads these two settings from its host.
var line_scale := 1.0
var overlay_bias := 0.001
var _presenter := Presenter.new()
var _stock := StandardMaterial3D.new()
var _target_before: MeshInstance3D
var _target_after: MeshInstance3D
var _links: Array[MeshInstance3D] = []
var _threads: Array[MeshInstance3D] = []
var _link_badge: MeshInstance3D
var _thread_badge: MeshInstance3D
var _paused_links := Node3D.new()
var _paused_thread := Node3D.new()
var _using_links := true
var _timeline: Tween


func _ready() -> void:
	var ui := NapkinUI.new(self)
	theme = ui._make_theme()
	# The demo shares line meshes and materials without creating a Napkin window or document.
	add_child(_presenter)
	_presenter.m = self
	_stock.albedo_color = Presenter.DEFAULT_BASE.linear_to_srgb()
	_stock.roughness = 0.85
	_build_stage(%DetachView)
	_build_stage(%PauseView)
	_target_before = _board(%DetachView, Vector3(0.36, 0.46, 0.44), Vector3(0.24, 0.23, 0))
	_target_after = _board(%DetachView, Vector3(0.12, 0.46, 0.44), Vector3(0.36, 0.23, 0))
	var turned := _board(%PauseView, Vector3(0.36, 0.46, 0.44), Vector3(0.40, 0.23, 0))
	turned.rotation.y = PI / 2.0

	%PauseView.add_child(_paused_links)
	%PauseView.add_child(_paused_thread)
	for i in LINK_COUNT:
		var radius := 0.034
		var height := 0.018 if i % 2 == 0 else 0.010
		var outline := _loop(radius, height)
		_links.append(_line(%DetachView, outline, INK, 2.4, true))
		var paused := _line(_paused_links, outline, INK, 2.4)
		paused.position = _link_origin(i) - Vector3(0, 0.033 * sin(PI * i / (LINK_COUNT - 1)), 0)
	for side in [0, 1]:
		var thread := _line(%DetachView, _cord(0.105, 0.015), INK, 2.4, true)
		thread.scale.x = 1.0 if side == 0 else -1.0
		_threads.append(thread)
		var paused := _line(_paused_thread, _cord(0.105, 0.058), INK, 2.4)
		paused.position = _thread_origin(side)
		paused.scale.x = thread.scale.x

	var open_link := _loop(0.026, 0.017, 0.8)
	var broken_link := Transform3D(Basis.IDENTITY, Vector3(-0.030, 0, 0)) * open_link
	broken_link.append_array(Transform3D(Basis(Vector3.FORWARD, PI), Vector3(0.030, 0, 0)) * open_link)
	_link_badge = _badge(broken_link)
	var broken_thread := PackedVector3Array([
		Vector3(-0.051, 0.012, 0), Vector3(-0.026, 0.009, 0),
		Vector3(-0.026, 0.009, 0), Vector3(-0.013, -0.006, 0),
		Vector3(0.012, 0.009, 0), Vector3(0.026, -0.006, 0),
		Vector3(0.026, -0.006, 0), Vector3(0.051, -0.014, 0),
	])
	_thread_badge = _badge(broken_thread)

	%Links.pressed.connect(_play.bind(true))
	%Thread.pressed.connect(_play.bind(false))
	%Replay.pressed.connect(func(): _play(_using_links))
	_reset()


func _build_stage(view: SubViewport) -> void:
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color(0.86, 0.89, 0.92)
	environment.environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color.WHITE
	environment.environment.ambient_light_energy = 0.42
	view.add_child(environment)
	_light(view, Vector3(-55, -35, 0), 0.62)
	_light(view, Vector3(-20, 140, 0), 0.30)
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.keep_aspect = Camera3D.KEEP_WIDTH
	camera.size = 1.34
	camera.near = 0.005
	view.add_child(camera)
	camera.position = Vector3(1.04, 0.88, 1.62)
	camera.look_at(Vector3(-0.015, 0.21, 0.0))
	camera.current = true
	_board(view, Vector3(FIT_LENGTH, 0.12, 0.24), Vector3(END_X - FIT_LENGTH / 2.0, 0.16, 0))
	var grid := PackedVector3Array()
	for i in range(-10, 11):
		var p := i * 0.10
		grid.append_array([Vector3(p, 0, -1), Vector3(p, 0, 1), Vector3(-1, 0, p), Vector3(1, 0, p)])
	_line(view, grid, Color(0.62, 0.66, 0.70, 0.42), 1.0)


func _light(view: SubViewport, rotation: Vector3, energy: float) -> void:
	var light := DirectionalLight3D.new()
	light.rotation_degrees = rotation
	light.light_energy = energy
	view.add_child(light)


func _board(parent: Node, size: Vector3, center: Vector3) -> MeshInstance3D:
	var board := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	mesh.material = _stock
	board.mesh = mesh
	board.position = center
	parent.add_child(board)
	var model_triangles := PackedVector3Array()
	for point in mesh.get_faces():
		model_triangles.append(Geo.g2m(point))
	board.add_child(_presenter.lines(Geo.feature_edges(model_triangles), EDGE))
	return board


func _line(parent: Node, points: PackedVector3Array, color: Color, width: float, fade := false) -> MeshInstance3D:
	var model_points := PackedVector3Array()
	for point in points:
		model_points.append(Geo.g2m(point))
	var node := _presenter.lines(model_points, color, width)
	if fade:
		node.material_override = node.mesh.surface_get_material(0).duplicate()
	parent.add_child(node)
	return node


func _badge(points: PackedVector3Array) -> MeshInstance3D:
	var node := _line(%DetachView, points, INK, 2.5)
	node.position = Vector3(END_X + 0.002, 0.16, 0)
	node.rotation.y = PI / 2.0
	return node


func _loop(width: float, height: float, gap := 0.0) -> PackedVector3Array:
	var points := PackedVector3Array()
	var previous := Vector3(width * cos(gap), height * sin(gap), 0)
	for i in range(1, 17):
		var angle := lerpf(gap, TAU - gap, i / 16.0)
		var point := Vector3(width * cos(angle), height * sin(angle), 0)
		points.append_array([previous, point])
		previous = point
	return points


func _cord(length_m: float, drop: float) -> PackedVector3Array:
	var points := PackedVector3Array()
	var previous := Vector3.ZERO
	for i in range(1, 11):
		var fraction := i / 10.0
		var point := Vector3(length_m * fraction, -drop * (1.0 - cos(PI * fraction)) / 2.0, 0)
		points.append_array([previous, point])
		previous = point
	return points


func _link_origin(i: int) -> Vector3:
	return Vector3(0.075 + i * 0.052, CONNECTOR_Y, CONNECTOR_Z)


func _thread_origin(side: int) -> Vector3:
	return Vector3(0.065 + side * 0.210, CONNECTOR_Y, CONNECTOR_Z)


func _reset() -> void:
	_target_before.show()
	_target_after.hide()
	_paused_links.visible = _using_links
	_paused_thread.visible = not _using_links
	%DetachedState.text = "Live fit"
	%DetachedCaption.text = "Fitted board: 600 mm · Target face present"
	_pose(0.0)


func _play(use_links: bool) -> void:
	if _timeline:
		_timeline.kill()
	_using_links = use_links
	_reset()
	_timeline = create_tween()
	_timeline.tween_interval(LEAD_IN)
	_timeline.tween_callback(_detach)
	_timeline.tween_method(_pose, 0.0, EFFECT_TIME, EFFECT_TIME)


func _detach() -> void:
	_target_before.hide()
	_target_after.show()
	%DetachedState.text = "Detached fit"
	%DetachedCaption.text = "Fitted board: 600 mm · Target face cut away"


func _pose(elapsed: float) -> void:
	for i in _links.size():
		var link := _links[i]
		var fall := clampf((elapsed - (LINK_COUNT - 1 - i) * 0.055) / 0.75, 0.0, 1.0)
		link.position = _link_origin(i) + Vector3((i - 1.5) * 0.016 * fall, -0.25 * fall * fall, 0)
		link.rotation.z = (i - 1.5) * fall * 1.8
		_pose_ink(link, _using_links, 1.0 - smoothstep(0.38, 1.0, fall))
	for i in _threads.size():
		var thread := _threads[i]
		var sag := smoothstep(0.0, 0.38, elapsed)
		var direction := -1.0 if i == 0 else 1.0
		thread.position = _thread_origin(i) + Vector3(i * 0.043 * sag, -i * 0.056 * sag, 0)
		thread.rotation.z = direction * sag * 0.93
		_pose_ink(thread, not _using_links, 1.0 - smoothstep(0.32 + 0.16 * (1 - i), EFFECT_TIME, elapsed))
	_link_badge.visible = _using_links and elapsed >= 0.76
	_thread_badge.visible = not _using_links and elapsed >= 0.70


func _pose_ink(node: MeshInstance3D, active: bool, opacity: float) -> void:
	node.visible = active and opacity > 0.0
	var color := INK
	color.a = opacity
	(node.material_override as ShaderMaterial).set_shader_parameter("color", color)
