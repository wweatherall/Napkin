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
	# 8. Trackpad and wheel (I22, I30)
	harness._q_lap("trackpad")
	await harness._view(Vector3.ZERO, -30, -30, 2.0)
	var y0 := rig.yaw
	var pan := InputEventPanGesture.new(); pan.delta = Vector2(100.0 / CameraRig.TRACKPAD_PX, 0.0)
	await harness._gesture(pan)
	harness._ok("two fingers orbit like a 100 px drag", is_equal_approx(rig.yaw, y0 - 0.8), rig.yaw - y0)
	var d0 := rig.dist
	for i in 10:
		var tiny := InputEventMouseButton.new(); tiny.button_index = MOUSE_BUTTON_WHEEL_UP; tiny.pressed = true; tiny.factor = 0.1
		tiny.position = m.cursor2d.position; m._unhandled_input(tiny)
	harness._ok("ten small wheel steps zoom like one notch", is_equal_approx(rig.dist, d0 * CameraRig.ZOOM_STEP), rig.dist / d0)
