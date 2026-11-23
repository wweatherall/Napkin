extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const CameraRig := preload("res://camera_rig.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	var rig: CameraRig = m.camera_rig
	# T7: trackpad gestures move the camera like the mouse does
	await harness._view(Vector3(0, 0, 0), -30, -30, 2.0)
	var y0 := rig.yaw; var p0 := rig.pitch
	var pan := InputEventPanGesture.new(); pan.delta = Vector2(100.0 / CameraRig.TRACKPAD_PX, 0.0)
	await harness._gesture(pan)
	var orbit_ok := is_equal_approx(rig.yaw, y0 - 100 * 0.008) and is_equal_approx(rig.pitch, p0)
	var mouse := InputEventMouseMotion.new(); mouse.relative = Vector2(100, 0); mouse.position = m.cursor2d.position
	rig.orbiting = true; m._unhandled_input(mouse); rig.orbiting = false            # the same 100 px with the middle button
	var same_as_mouse := is_equal_approx(rig.yaw, y0 - 2 * 100 * 0.008)
	var t0 := rig.target
	var span := InputEventPanGesture.new(); span.delta = Vector2(0.0, 50.0 / CameraRig.TRACKPAD_PX); span.shift_pressed = true
	await harness._gesture(span)
	var pan_ok := rig.target.distance_to(t0) > 0.01 and is_equal_approx(rig.yaw, y0 - 2 * 100 * 0.008)
	var d0 := rig.dist
	var pinch := InputEventMagnifyGesture.new(); pinch.factor = 1.25
	await harness._gesture(pinch)
	var zoom_in := rig.dist < d0
	var d1 := rig.dist
	var spread := InputEventMagnifyGesture.new(); spread.factor = 0.8
	await harness._gesture(spread)
	# T23: a wheel zooms by the amount scrolled (a smooth-scrolling mouse sends many small amounts)
	var dz := rig.dist
	var notch := InputEventMouseButton.new(); notch.button_index = MOUSE_BUTTON_WHEEL_UP; notch.pressed = true; notch.factor = 1.0
	notch.position = m.cursor2d.position; m._unhandled_input(notch)
	var after_notch := rig.dist
	rig.dist = dz; rig.update_camera()
	for i in 10:
		var tiny := InputEventMouseButton.new(); tiny.button_index = MOUSE_BUTTON_WHEEL_UP; tiny.pressed = true; tiny.factor = 0.1
		tiny.position = m.cursor2d.position; m._unhandled_input(tiny)
	var after_tiny := rig.dist
	print("GESTURETEST wheel: one notch %.3f -> %.3f | ten 0.1 steps -> %.3f (same as one notch: %s)" % [dz, after_notch, after_tiny,
		is_equal_approx(after_notch, after_tiny)])
	print("GESTURETEST two-finger orbit %s | same as a mouse drag %s | Shift+two-finger pan %s | pinch out zooms in %s (%.2f -> %.2f) | pinch in zooms out %s" % [
		orbit_ok, same_as_mouse, pan_ok, zoom_in, d0, d1, rig.dist > d1])
	print("GESTURETEST done")
	harness.get_tree().quit()
