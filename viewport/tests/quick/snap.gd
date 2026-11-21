extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 4. Snapping (I03b, I23): midpoint, on edge on the grid, push to a point, the back face
	await harness._fresh("snap", harness._plank(1, Vector3.ZERO, Vector3(300, 200, 18)) + harness._plank(2, Vector3(400, 0, 0), Vector3(100, 100, 50)))
	await harness._view(Vector3(250, 100, 20), -30, -35, 1.1)
	m.set_tool("rect")
	var mid := m.snap(m.pick(harness._screen_of(Vector3(150, 0, 18))), harness._screen_of(Vector3(150, 0, 18)))
	harness._ok("a rectangle corner snaps to an edge's midpoint", mid.get("snap", "") == "midpoint" and mid["point"].is_equal_approx(Vector3(150, 0, 18)), mid)
	var oe := m.snap(m.pick(harness._screen_of(Vector3(64, 0, 18), Vector2(0, 2))), harness._screen_of(Vector3(64, 0, 18), Vector2(0, 2)))
	harness._ok("on an edge, it lands on the grid", oe.get("snap", "") == "on edge" and oe["point"].is_equal_approx(Vector3(60, 0, 18)), oe)
	m.set_tool("push")
	var push = m.tools["push"]
	push.click(harness._screen_of(Vector3(150, 100, 18), Vector2.ZERO))
	push.mouse_moved(harness._screen_of(Vector3(400, 0, 50)))
	harness._ok("a push snaps to another board's corner height", push.state.get("dist", 0) == 32.0 and push.state.get("snap", "") == "endpoint", push.state.get("dist"))
	m.set_tool("push")
	push.click(harness._screen_of(Vector3(450, 50, 50), Vector2.ZERO))
	push.mouse_moved(harness._screen_of(Vector3(450, 50, 3), Vector2.ZERO))
	harness._ok("pushing in snaps to the hidden back face", push.state.get("dist", 0) == -50.0 and push.state.get("snap", "") == "back face", push.state.get("dist"))
	m.set_tool("rect")
