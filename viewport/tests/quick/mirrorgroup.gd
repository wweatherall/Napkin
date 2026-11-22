extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 5d. Mirror groups (T26, A11b): a mirrored copy makes a group; inside, the plane shows and moving the copy
	# moves its original the mirrored way
	await harness._fresh("mirrorgroup", harness._plank(1, Vector3.ZERO, Vector3(100, 50, 18)))
	await harness._view(Vector3(150, 25, 0), -25, -50, 1.2)
	await harness._grab(Vector3(50, 25, 18))
	await harness._key(KEY_ALT)                            # copy
	await harness._key(KEY_SHIFT)                          # mirror
	await harness._key(KEY_RIGHT)                          # across a red-axis plane (else it's parallel to the grabbed top)
	await harness._drag_to(Vector3(250, 25, 18), 6)
	await harness._press()
	await harness._wait_wave()
	var pair: Array = harness._shown_ids()
	var grp: String = m.body_assembly.get(harness.id("b1"), "")
	harness._ok("a mirrored copy makes a mirror group with its original", pair.size() == 2 and grp != "" and m.body_assembly.get(pair[1], "") == grp,
		[pair, m.body_assembly])
	var mir_b: String = pair[1]
	m.set_tool("select")
	await harness._double_click_at(Vector3(50, 25, 18))
	harness._ok("inside the mirror group its plane shows", m.context == "assembly:" + grp and m._plane_node.mesh != null, m.context)
	var x0: float = harness._bbox(harness.id("b1"))[0]
	var mx: float = (harness._bbox(mir_b)[0] + harness._bbox(mir_b)[3]) * 0.5
	await harness._grab(Vector3(mx, 25, 18))
	await harness._key(KEY_RIGHT)
	await harness._drag_to(Vector3(mx + 40, 25, 18), 6)
	await harness._type("50\n")
	await harness._wait_wave()
	harness._ok("moving the copy 50 out moves the original 50 the other way", absf(harness._bbox(harness.id("b1"))[0] - (x0 - 50)) < 0.01, [x0, harness._bbox(harness.id("b1")), harness._bbox(mir_b)])
	await harness._key(KEY_ESCAPE); await harness._key(KEY_ESCAPE)
