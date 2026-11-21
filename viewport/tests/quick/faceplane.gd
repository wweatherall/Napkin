extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 5e. Mirror across another board's face (T27, Q12): point at the face while mirroring
	await harness._fresh("faceplane", harness._plank(1, Vector3.ZERO, Vector3(100, 50, 18)) + harness._plank(2, Vector3(300, 0, 0), Vector3(18, 50, 60)))
	await harness._view(Vector3(150, 25, 30), -25, -50, 1.2)
	await harness._grab(Vector3(50, 25, 18))
	await harness._key(KEY_ALT)
	await harness._key(KEY_SHIFT)
	await harness._drag_to(Vector3(309, 25, 60), 6)
	harness._ok("pointing at b2's top while mirroring snaps the plane to it", m.tools["move"].state.get("mir_face", "") == "b2" and m.ui_tip.text.contains("b2's face"),
		[m.tools["move"].state.get("mir_face", ""), m.ui_tip.text])
	await harness._press()
	await harness._wait_wave()
	var fp_ids: Array = harness._shown_ids()
	var fp_new: String = fp_ids.back() if fp_ids.size() == 3 else ""
	harness._ok("the copy lands mirrored across b2's top: z 102..120", fp_new != "" and harness._bbox(fp_new)[2] == 102.0 and harness._bbox(fp_new)[5] == 120.0,
		[fp_ids, harness._bbox(fp_new) if fp_new != "" else []])
	await harness._grab(Vector3(50, 25, 18))
	await harness._key(KEY_ALT)
	await harness._key(KEY_SHIFT)
	await harness._drag_to(Vector3(309, 10, 60), 6)
	await harness._type("20\n")
	await harness._wait_wave()
	fp_ids = harness._shown_ids()
	fp_new = fp_ids.back() if fp_ids.size() == 4 else ""
	harness._ok("typing 20 stands the plane 20 off the face: z 142..160", fp_new != "" and harness._bbox(fp_new)[2] == 142.0, [fp_ids, harness._bbox(fp_new) if fp_new != "" else []])
