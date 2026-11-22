extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 5f. Hide and unhide, SketchUp style (T28, I37): H hides the selection, Cmd+Z brings it back at once, View >
	# Hidden geometry ghosts hidden boards so one can be picked and unhidden, Shift+H unhides all
	await harness._fresh("hide", harness._plank(1, Vector3.ZERO, Vector3(100, 50, 18)) + harness._plank(2, Vector3(300, 0, 0), Vector3(100, 50, 18)))
	await harness._view(Vector3(200, 25, 0), -25, -50, 1.2)
	var node := func(bid: String) -> MeshInstance3D: return m.bodies_root.get_node_or_null(bid)
	var hidden_json := func() -> Array:
		return harness._bodies().values().filter(func(b): return b.get("hidden", false)).map(func(b): return b["id"])
	await harness._key(KEY_SPACE)
	await harness._click_at(Vector3(50, 25, 18))
	await harness._key(KEY_H)
	harness._ok("H hides the selected board at once", m.is_hidden("b1") and not node.call("b1").visible and node.call("b2").visible
		and m.selection.is_empty(), [m.body_hidden, m.selection])
	await harness._wait_wave()
	harness._ok("FreeCAD has it hidden too (bodies.json)", hidden_json.call() == ["b1"], hidden_json.call())
	await harness._drag_to(Vector3(50, 25, 18), 4)
	harness._ok("a hidden board can't be picked", m.pick(m.cursor2d.position).get("body", "") == "", m.pick(m.cursor2d.position))
	var snapped: Dictionary = m.infer.point(m.cam.unproject_position(Main.m2g(Vector3(100, 50, 18))), "")
	harness._ok("nor snapped to", snapped.get("body", "") != "b1", snapped)
	await harness._key_cmd(KEY_Z)
	harness._ok("Cmd+Z shows it again at once", not m.is_hidden("b1") and node.call("b1").visible, m.body_hidden)
	await harness._wait_wave()
	harness._ok("and FreeCAD agrees", hidden_json.call().is_empty(), hidden_json.call())
	await harness._click_at(Vector3(50, 25, 18))
	await harness._key(KEY_H)
	await harness._wait_wave()
	await harness._menu("hiddengeom")
	harness._ok("View > Hidden geometry shows it ghosted", node.call("b1").visible and node.call("b1").material_override == m.mat_hidden_ghost,
		node.call("b1").material_override)
	await harness._click_at(Vector3(50, 25, 18))
	harness._ok("a ghosted board can be selected", m.selection == ["b1"], m.selection)
	await harness._menu("unhide_selected")
	await harness._wait_wave()
	harness._ok("Edit > Unhide selected", not m.is_hidden("b1") and hidden_json.call().is_empty(), hidden_json.call())
	await harness._menu("hiddengeom")
	m.set_selection(["b1", "b2"])
	await harness._menu("hide")
	await harness._wait_wave()
	m.set_selection([])
	await harness._key_shift(KEY_H)
	await harness._wait_wave()
	harness._ok("Shift+H unhides all", m.body_hidden.is_empty() and hidden_json.call().is_empty() and node.call("b2").visible, hidden_json.call())
	m.set_selection(["b1"]); m.hide_selected()        # (straight calls: _menu drops a repeat within 150 ms)
	m.set_selection(["b2"]); m.hide_selected()
	m.unhide("last")
	await harness._wait_wave()
	harness._ok("Edit > Unhide last brings back only the last one hidden", hidden_json.call() == ["b1"], hidden_json.call())
