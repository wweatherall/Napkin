extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 3. Faces: a pocket, a through-hole in a side face, a bump on another side face
	await harness._fresh("faces", harness._plank(1, Vector3.ZERO, Vector3(300, 200, 18)))
	await harness._view(Vector3(150, 100, 9), -35, -30, 1.0)
	await harness._rect(Vector3(50, 50, 18), Vector3(150, 130, 18), "100,80")
	await harness._push(Vector3(100, 90, 18), Vector3(100, 90, 8), "-10")
	await harness._wait_wave()
	await harness._rect(Vector3(200, 0, 4), Vector3(220, 0, 14), "20,10")
	await harness._push(Vector3(210, 0, 9), Vector3(210, 30, 9), "-200")
	await harness._wait_wave()
	var thru: Dictionary = m.ops.back()
	harness._ok("a cut typed to the far face is a through-cut (I24)", thru.get("through", false), thru)
	await harness._view(Vector3(300, 100, 9), 40, -25, 0.8)
	await harness._rect(Vector3(300, 50, 2), Vector3(300, 100, 12), "50,10")
	await harness._push(Vector3(300, 75, 7), Vector3(330, 75, 7), "30")
	await harness._wait_wave()
	var v: float = harness._bodies().get("b1", {}).get("volume_mm3", -1)
	harness._ok("pocket, through-hole and bump add up", is_equal_approx(v, 300.0 * 200 * 18 - 100 * 80 * 10 - 20 * 10 * 200 + 50 * 10 * 30), v)
	harness._ok("still one board", harness._shown_ids() == ["b1"], harness._shown_ids())
