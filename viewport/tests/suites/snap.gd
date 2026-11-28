extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# Q16: Rectangle and Push/Pull snap like Move (endpoint > midpoint > on edge > grid; push to a point)
	m.cursor2d.visible = false
	m.ops.append({"id": "r1", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, 0, 0]}, "size": [300, 200]})
	m.ops.append({"id": "pp1", "type": "new_board", "target": {"rect": "r1"}, "distance": 18, "body": "b1"})
	m.ops.append({"id": "r2", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [400, 0, 0]}, "size": [100, 100]})
	m.ops.append({"id": "pp2", "type": "new_board", "target": {"rect": "r2"}, "distance": 50, "body": "b2"})
	m.counters["r"] = 2; m.counters["pp"] = 2; m.counters["b"] = 2
	m.sync(); await harness._wait_confirm()
	await harness._view(Vector3(250, 100, 20), -30, -35, 1.1)
	m.set_tool("rect")
	var mid := m.snap(m.pick(harness._screen_of(Vector3(150, 0, 18))), harness._screen_of(Vector3(150, 0, 18)))
	var mid_ok: bool = mid.get("snap", "") == "midpoint" and mid["point"].is_equal_approx(Vector3(150, 0, 18))
	var on_edge := m.snap(m.pick(harness._screen_of(Vector3(64, 0, 18), Vector2(0, 2))), harness._screen_of(Vector3(64, 0, 18), Vector2(0, 2)))
	var edge_ok: bool = on_edge.get("snap", "") == "on edge" and on_edge["point"].is_equal_approx(Vector3(60, 0, 18))
	var near_corner := harness._screen_of(Vector3(296, 196, 18), Vector2.ZERO)      # on the face, a few pixels from its corner
	var corner := m.snap(m.pick(near_corner), near_corner)
	var corner_ok: bool = corner.get("snap", "") == "endpoint" and corner["point"].is_equal_approx(Vector3(300, 200, 18))
	var inside := m.snap(m.pick(harness._screen_of(Vector3(121, 93, 18), Vector2.ZERO)), harness._screen_of(Vector3(121, 93, 18), Vector2.ZERO))
	var grid_ok: bool = inside.get("snap", "") == "grid" and inside["point"].is_equal_approx(Vector3(120, 90, 18))
	print("SNAPTEST rectangle: midpoint %s %s | on edge, on the grid %s %s | endpoint %s | grid inside a face %s %s" % [
		mid_ok, mid.get("snap"), edge_ok, on_edge.get("point"), corner_ok, grid_ok, inside.get("point")])
	# push b1's top up to the level of b2's top corner
	m.set_tool("push")
	var push = m.tools["push"]
	push.click(harness._screen_of(Vector3(150, 100, 18), Vector2.ZERO))
	push.mouse_moved(harness._screen_of(Vector3(150, 200, 18), Vector2(0, 2)))     # over the pushed face's own far edge
	var own_edge_ignored: bool = push.state.get("snap", "") == ""
	if not own_edge_ignored: print("SNAPTEST own-edge hover snapped: %s, distance %s" % [push.state.get("snap"), push.state.get("dist")])
	push.mouse_moved(harness._screen_of(Vector3(400, 0, 50)))
	var dist: float = push.state.get("dist", -1)
	var kind: String = push.state.get("snap", "")
	push.click(harness._screen_of(Vector3(400, 0, 50)))
	await harness._wait_wave()
	var top := -1.0
	for b in JSON.parse_string(FileAccess.get_file_as_string(m.out_dir.path_join("bodies.json"))):
		if b["id"] == harness.id("b1"): top = b["world_bbox"][5]
	print("SNAPTEST push to a point: distance %s (want 32) by %s | b1's top now at %s mm (want 50) | own face's edges ignored %s" % [
		dist, kind, top, own_edge_ignored])
	# pushing in: the back face snaps (a through-hole) even though you can't see it; elsewhere, no snap
	m.set_tool("push")
	push.click(harness._screen_of(Vector3(450, 50, 50), Vector2.ZERO))
	push.mouse_moved(harness._screen_of(Vector3(450, 50, 3), Vector2.ZERO))
	var through: float = push.state.get("dist", 0); var through_kind: String = push.state.get("snap", "")
	push.mouse_moved(harness._screen_of(Vector3(450, 50, 22), Vector2.ZERO))
	var free: float = push.state.get("dist", 0); var free_kind: String = push.state.get("snap", "")
	m.set_tool("push")
	print("SNAPTEST push in near the back: %s by %s (want -50 by back face) | at -28: %s, snap '%s' (want about -28, none)" % [
		through, through_kind, free, free_kind])
	# a real hole: rectangle on b2's top, pushed in to the back face -> a through cut FreeCAD keeps through (I24)
	var rop := {"id": "r3", "type": "rect", "plane": {"on": {"body": "b2", "normal": [0, 0, 1], "point": [440, 40, 50]}}, "size": [20, 20]}
	m.ops.append(rop); m._register_rect(rop); m.counters["r"] = 3
	m.sync(); await harness._wait_confirm()
	m.set_tool("push")
	push.click(harness._screen_of(Vector3(450, 50, 50), Vector2.ZERO))
	push.mouse_moved(harness._screen_of(Vector3(450, 50, 2), Vector2.ZERO))
	push.click(harness._screen_of(Vector3(450, 50, 2), Vector2.ZERO))
	var hole_op: Dictionary = m.ops.back()
	await harness._wait_wave()
	var b2_vol := -1.0
	for b in JSON.parse_string(FileAccess.get_file_as_string(m.out_dir.path_join("bodies.json"))):
		if b["id"] == harness.id("b2"): b2_vol = b["volume_mm3"]
	print("SNAPTEST through-hole: op %s through=%s distance %s | b2 volume %s (want %s)" % [
		hole_op["id"], hole_op.get("through", false), hole_op.get("distance"), b2_vol, 100 * 100 * 50 - 20 * 20 * 50])
	print("SNAPTEST done")
	harness.get_tree().quit()
