extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 5b. Linked copies (T12): a row of linked copies, the tint while editing, a hole on one shows on all, U, Detach
	await harness._fresh("linked", harness._plank(1, Vector3.ZERO, Vector3(100, 50, 18)))
	await harness._view(Vector3(250, 25, 0), -25, -50, 1.6)
	await harness._grab(Vector3(0, 25, 18))
	await harness._key(KEY_ALT)
	await harness._key(KEY_RIGHT)                         # lock red
	await harness._drag_to(Vector3(80, 25, 18), 6)
	await harness._type("150\n")
	await harness._frames(4)
	await harness._type("3x\n")
	await harness._wait_wave()
	var row: Array = harness._shown_ids()
	var fams := {}
	for b in row: fams[m.body_family.get(b, "")] = true
	harness._ok("a 3x copy makes 4 linked boards", row.size() == 4 and fams.size() == 1 and not fams.has(""), [row, m.body_family])
	var copy_b: String = row[2]
	m.set_tool("push")
	await harness._drag_to(Vector3(325, 25, 18), 4)
	harness._ok("hovering a copy tints its 3 siblings and the tooltip counts 4", m.sel.siblings_of(copy_b).size() == 3 and m.ui_tip.text.contains("changes 4 linked boards"),
		[m.hover_body, m.sel.siblings_of(copy_b), m.ui_tip.text])
	await harness._view(Vector3(350, 25, 18), -25, -50, 0.8)          # close enough that the start isn't within snapping range
	await harness._rect(Vector3(338, 18, 18), Vector3(358, 38, 18), "20,20")
	await harness._push(Vector3(348, 28, 18), Vector3(348, 28, 8), "-18")
	await harness._view(Vector3(250, 25, 0), -25, -50, 1.6)
	await harness._wait_wave()
	var vols := {}
	for b in row: vols[snappedf(harness._bodies()[b]["volume_mm3"], 0.1)] = true
	harness._ok("a hole cut in one copy is in all four", vols.keys() == [100.0 * 50 * 18 - 20 * 20 * 18], vols.keys())
	m.set_tool("push")
	await harness._drag_to(Vector3(475, 25, 18), 4)
	await harness._key(KEY_U)
	await harness._wait_wave()
	var uniq: String = m.hover_body
	harness._ok("U makes the board under the cursor its own", uniq != "" and m.body_family.get(uniq, "x") == "", [uniq, m.body_family])
	await harness._drag_to(Vector3(175, 25, 18), 4)
	var det: String = m.hover_body
	await harness._menu("detach")
	await harness._wait_wave()
	harness._ok("Edit > Detach from array takes it out of the row", m.body_array.get(det, "x") == "" and m.body_family.get(det, "") != "", [det, m.body_array, m.body_family])
