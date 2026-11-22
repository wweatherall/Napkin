extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	await harness._fresh("hole", [{"id": "r1", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, 0, 0]}, "size": [600, 300]},
		{"id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": 18, "body": "b1"},
		{"id": "r2", "type": "rect", "plane": {"on": {"body": "b1", "normal": [0, 0, 1], "point": [30, 30, 18]}}, "size": [20, 20]},
		{"id": "pp2", "type": "push_pull", "target": {"rect": "r2"}, "distance": -18}])
	await harness._view(Vector3(300, 150, 0), -20, -50, 1.3)
	await harness._grab(Vector3(40, 50, 9))
	harness._ok("grabbing a hole's wall picks the hole", m.move_state.get("cut", {}).get("op", "") == harness.id("pp2"), m.move_state.get("cut"))
	await harness._key(KEY_ALT)
	await harness._key(KEY_RIGHT)
	await harness._drag_to(Vector3(100, 30, 9), 6)
	await harness._type("60\n")
	await harness._frames(4)
	await harness._type("5x\n")
	await harness._wait_wave()
	var holes: Array = harness._bodies()[harness.id("b1")]["cuts"].filter(func(c): return c["op"] == harness.id("pp2"))
	harness._ok("the hole copied into a row of 6", holes.size() == 6 and is_equal_approx(harness._bodies()[harness.id("b1")]["volume_mm3"], 600.0 * 300 * 18 - 6 * 20 * 20 * 18), [holes.size(), harness._bodies()[harness.id("b1")]["volume_mm3"]])
