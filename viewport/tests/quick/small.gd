extends RefCounted
## T33: pointer filtering must not discard typed or snapped sub-millimetre geometry.
const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	await harness._fresh("small", harness._plank(1, Vector3.ZERO, Vector3(50, 30, 10)))
	await harness._view(Vector3(25, 15, 10), -30, -45, 0.5)
	m.grid_snap = false
	var initial: int = m.ops.size()
	await harness._push(Vector3(25, 15, 10), Vector3(25, 15, 30), "0.2mm")
	await harness._wait_wave()
	harness._ok("typed 0.2 mm push reaches FreeCAD", m.ops.size() == initial + 1
		and absf(float(harness._bodies()["b1"]["world_bbox"][5]) - 10.2) < 0.00001, m.ops.back())
	m.undo(); await harness._wait_wave()
	harness._ok("small push undoes in one step", m.ops.size() == initial
		and absf(float(harness._bodies()["b1"]["world_bbox"][5]) - 10) < 0.00001)

	await harness._grab(Vector3(0, 15, 10))
	await harness._key(KEY_RIGHT)
	await harness._drag_to(Vector3(20, 15, 10), 4)
	await harness._type("0.2mm\n")
	await harness._wait_wave()
	harness._ok("typed 0.2 mm move reaches FreeCAD", m.ops.size() == initial + 1
		and absf(float(harness._bodies()["b1"]["world_bbox"][0]) - 0.2) < 0.00001, m.ops.back())
	await harness._type("1/64\"\n")
	await harness._wait_wave()
	var fraction := 25.4 / 64.0
	harness._ok("typed fractional amendment retains full distance", m.ops.size() == initial + 1
		and absf(float(m.ops.back()["vector"][0]) - fraction) < 0.000001
		and absf(float(harness._bodies()["b1"]["world_bbox"][0]) - fraction) < 0.000001, m.ops.back())
	m.undo(); await harness._wait_wave()
	harness._ok("small amended move undoes in one step", m.ops.size() == initial
		and absf(float(harness._bodies()["b1"]["world_bbox"][0])) < 0.00001)

	# Start with a real picked face; inject the final distance to test the exact threshold,
	# independently of pixel size, camera angle and the inference engine's existing snap radii.
	await harness._grab(Vector3(0, 15, 10))
	var move = m.tools["move"]
	move.state["vec"] = Vector3(0.3, 0, 0); move.state["point_snap"] = false
	move._finish()
	harness._ok("unsnapped 0.3 mm move is ignored", m.ops.size() == initial)
	# Typing is allowed even when the preview vector itself is less than 0.5 mm.
	move.state["vec"] = Vector3(0.2, 0, 0)
	await harness._type("0.2mm\n"); await harness._wait_wave()
	harness._ok("typed small move accepts a small preview direction", m.ops.size() == initial + 1)
	m.undo(); await harness._wait_wave()
	await harness._grab(Vector3(0, 15, 10))
	move.state["vec"] = Vector3(0.2, 0, 0); move.state["point_snap"] = true
	move._finish(); await harness._wait_wave()
	harness._ok("point snap commits a 0.2 mm move", m.ops.size() == initial + 1
		and absf(float(harness._bodies()["b1"]["world_bbox"][0]) - 0.2) < 0.00001)
	m.undo(); await harness._wait_wave()

	m.set_tool("push")
	await harness._drag_to(Vector3(25, 15, 10), 4); await harness._press()
	var push = m.tools["push"]
	push.state["dist"] = 0.3; push.state["snap"] = ""
	push._finish_push()
	harness._ok("unsnapped 0.3 mm push is ignored", m.ops.size() == initial)
	push.state["dist"] = 0.2; push.state["snap"] = "endpoint"
	push._finish_push(); await harness._wait_wave()
	harness._ok("point snap commits a 0.2 mm push", m.ops.size() == initial + 1
		and absf(float(harness._bodies()["b1"]["world_bbox"][5]) - 10.2) < 0.00001)
	m.undo(); await harness._wait_wave()
	await harness._push(Vector3(25, 15, 10), Vector3(25, 15, 30), "1/64\"")
	await harness._wait_wave()
	harness._ok("typed fractional push retains full distance", absf(float(m.ops.back()["distance"]) - fraction) < 0.000001
		and absf(float(harness._bodies()["b1"]["world_bbox"][5]) - 10 - fraction) < 0.000001, m.ops.back())
	m.undo(); await harness._wait_wave()

	await harness._rect(Vector3(100, 0, 0), Vector3(120, 20, 0), "0.2mm,20mm")
	harness._ok("typed 0.2 mm rectangle is recorded", m.ops.size() == initial + 1
		and absf(float(m.ops.back().get("size", [0,0])[0]) - 0.2) < 0.000001, m.ops.back())
	m.undo(); await harness._wait_wave()
	m.set_tool("rect")
	await harness._drag_to(Vector3(100, 0, 0), 4); await harness._press()
	var rect = m.tools["rect"]
	rect.state["du"] = 0.3; rect.state["dv"] = 20; rect.state["point_snap"] = false
	rect._finish_rect()
	harness._ok("unsnapped 0.3 mm rectangle side is ignored", m.ops.size() == initial)
	rect.state["du"] = 0.2; rect.state["point_snap"] = true
	rect._finish_rect(); await harness._wait_confirm()
	harness._ok("point snap commits a 0.2 mm rectangle side", m.ops.size() == initial + 1
		and absf(float(m.ops.back().get("size", [0,0])[0]) - 0.2) < 0.000001, m.ops.back())
	m.grid_snap = true
