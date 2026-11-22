extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 5. Move: along an axis, copy into an array, endpoint inference, a hole moved and copied (I14, I18, I21)
	await harness._fresh("move", harness._plank(1, Vector3.ZERO, Vector3(100, 50, 18)) + harness._plank(2, Vector3(300, 200, 0), Vector3(100, 50, 18)))
	await harness._view(Vector3(200, 100, 0), -30, -45, 1.6)
	await harness._grab(Vector3(0, 25, 18))
	await harness._drag_to(Vector3(80, 25, 18), 6)
	var asked := m.length_id
	await harness._type("5in + 23mm\n")
	await harness._wait_wave()
	harness._ok("moved 150 along red", harness._bbox(harness.id("b1")).slice(0, 2) == [150.0, 0.0], harness._bbox(harness.id("b1")))
	harness._ok("arithmetic in a typed length is worked out at once, the way FreeCAD would", m.length_id == asked, [asked, m.length_id])
	await harness._grab(Vector3(150, 25, 18))
	await harness._key(KEY_ALT)
	await harness._key(KEY_LEFT)                          # lock green
	await harness._drag_to(Vector3(150, 80, 18), 6)
	asked = m.length_id
	await harness._type("60mm^1\n")                      # a unit power: the local evaluator declines, FreeCAD answers 60
	harness._ok("what the local evaluator declines is worked out by FreeCAD", m.length_id == asked + 1, [asked, m.length_id])
	await harness._frames(4)
	await harness._type("3x\n")
	await harness._wait_wave()
	var last: String = harness._shown_ids().back()
	harness._ok("copied into a row of 3 at 60 mm", harness._shown_ids().size() == 5 and harness._bbox(last).slice(0, 2) == [150.0, 180.0], [harness._shown_ids(), harness._bbox(last)])
	m.set_tool("move"); m.tools["move"].reset()
	await harness._grab(Vector3(300, 200, 18))
	await harness._drag_to(Vector3(250, 50, 18), 8)
	var kind: String = m.move_state.get("kind", "")
	await harness._press()
	await harness._wait_wave()
	harness._ok("a corner dragged onto another board's corner snaps to it", kind == "endpoint" and harness._bbox(harness.id("b2")).slice(0, 2) == [250.0, 50.0], [kind, harness._bbox(harness.id("b2"))])
