extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 5f. Wood (T15): pick a wood, paint a board, the board shows it; T turns its grain
	await harness._fresh("wood", harness._plank(1, Vector3.ZERO, Vector3(600, 90, 19)))
	await harness._view(Vector3(560, 45, 10), -50, -25, 0.5)
	m.set_paint_material("black-walnut")
	harness._ok("picking a wood switches to Paint", m.tool == "paint", m.tool)
	await harness._click_at(Vector3(300, 45, 19))
	await harness._wait_wave()
	await harness._frames(30)
	var wb: Dictionary = harness._bodies().get("b1", {})
	var node: MeshInstance3D = m.bodies_root.get_node_or_null("b1")
	var smat = node.mesh.surface_get_material(0) if node != null else null
	harness._ok("painted walnut: FreeCAD has it, the board shows the wood shader", wb.get("material", "") == "black-walnut"
		and smat is ShaderMaterial and smat.shader == m.WOOD, [wb.get("material", ""), smat])
	await harness._drag_to(Vector3(700, 300, 0), 3)       # off the board: no hover highlight
	await harness._shot("wood_walnut")
	await harness._view(Vector3(600, 45, 10), 60, -12, 0.13)
	await harness._drag_to(Vector3(700, 300, 0), 2)
	await harness._shot("wood_walnut_end")
	await harness._view(Vector3(560, 45, 10), -50, -25, 0.5)
	await harness._drag_to(Vector3(500, 45, 19), 3)
	await harness._key(KEY_T)
	await harness._wait_wave()
	harness._ok("T turns the grain across the board", harness._bodies()["b1"].get("grain", []) == [0.0, 1.0, 0.0], harness._bodies()["b1"].get("grain", []))
	await harness._drag_to(Vector3(700, 300, 0), 2)
	await harness._frames(20)
	await harness._shot("wood_walnut_turned")
