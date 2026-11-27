extends RefCounted
## Orbit, pan and zoom for mouse and trackpad (T113).
##
## Owns orbit target, angles, distance, drag state and live tunables (`trackpad_px`, `zoom_step`); zooms toward cursor
## via `m.pick`; `handle_input` returns false for non-camera events (left button, plain motion).
## Entry points: handle_input, update_camera.

const Geo := preload("res://tool_geometry.gd")

var m
var camera: Camera3D
var target := Vector3(0.25, 0.2, -0.15)
var yaw := deg_to_rad(-38.0)
var pitch := deg_to_rad(-26.0)
var dist := 2.0
var orbiting := false
var panning := false

const TRACKPAD_PX := 33.0     # Godot scales a trackpad's scroll by 0.03: this makes one finger-pixel = one mouse-pixel
var trackpad_px := TRACKPAD_PX

const ZOOM_STEP := 0.88       # zoom per notch of a plain wheel (scroll amount 1)
const ZOOM_MAX_STEPS := 3.0   # one scroll event never zooms more than this many notches
var zoom_step := ZOOM_STEP


func _init(main) -> void:
	m = main


func handle_input(e: InputEvent) -> bool:
	if e is InputEventMouseButton:
		if e.button_index in [MOUSE_BUTTON_MIDDLE, MOUSE_BUTTON_RIGHT]:
			orbiting = e.pressed and not e.shift_pressed
			panning = e.pressed and e.shift_pressed
		elif e.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN] and e.pressed:
			# zoom by how much was scrolled: a smooth-scrolling mouse (MX Master) sends many small steps per notch
			var amount := clampf(e.factor if e.factor > 0.0 else 1.0, 0.0, ZOOM_MAX_STEPS)
			var step := pow(zoom_step, amount)
			_zoom(step if e.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0 / step, e.position)
		else:
			return false
	elif e is InputEventPanGesture:
		# trackpad (and Magic Mouse) two-finger drag: orbit; with Shift, pan. A wheel mouse sends wheel buttons instead.
		if e.shift_pressed:
			var k := dist * 0.0012 * trackpad_px
			target += (-camera.global_transform.basis.x * e.delta.x + camera.global_transform.basis.y * e.delta.y) * k
		else:
			yaw -= e.delta.x * 0.008 * trackpad_px
			pitch = clampf(pitch - e.delta.y * 0.008 * trackpad_px, -1.5, 1.5)
		update_camera()
	elif e is InputEventMagnifyGesture:
		_zoom(1.0 / maxf(e.factor, 0.01), e.position)      # pinch out = closer, toward the cursor
	elif e is InputEventMouseMotion:
		if orbiting:
			yaw -= e.relative.x * 0.008
			pitch = clampf(pitch - e.relative.y * 0.008, -1.5, 1.5)
			update_camera()
		elif panning:
			var k := dist * 0.0012
			target += (-camera.global_transform.basis.x * e.relative.x + camera.global_transform.basis.y * e.relative.y) * k
			update_camera()
		else:
			return false
	else:
		return false
	return true


func _zoom(f: float, screen: Vector2) -> void:
	var p: Dictionary = m.pick(screen)
	if p.get("hit", false) and f < 1.0:
		target = target.lerp(Geo.m2g(p["point"]), 1.0 - pow(0.88, log(f) / log(zoom_step)))   # toward the cursor, as much as zoomed
	dist = clampf(dist * f, 0.05, 50.0)
	update_camera()


func update_camera() -> void:
	var off := Vector3(0, 0, dist).rotated(Vector3.RIGHT, pitch).rotated(Vector3.UP, yaw)
	camera.position = target + off
	camera.look_at(target, Vector3.UP)
	if m.grid_mat != null:       # the grid fades out past a few orbit distances (no shimmer toward the horizon)
		m.grid_mat.set_shader_parameter("fade_start", dist * 1.5 + 0.5)
		m.grid_mat.set_shader_parameter("fade_end", dist * 3.5 + 1.5)
