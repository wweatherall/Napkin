extends RefCounted
## T82: real chain/drag/typed gestures, undo/redo, snapping and exact polygon Push/Pull.
const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m

func run() -> void:
	await harness._fresh("line")
	await harness._view(Vector3(120, 60, 0), -30, -50, 1.2)
	await harness._key(KEY_L)
	harness._ok("L selects the context-only Line tool", m.tool == "line" and not m.tools.line.uses_main() and m.tools.line.m == null)
	await harness._drag_to(Vector3.ZERO, 4)
	await harness._button(true)
	await harness._drag_to(Vector3(100, 0, 0), 6)
	await harness._button(false)
	harness._ok("Line drag releases one saved segment", m.ops.size() == 1 and m.ops.back().type == "line" and not m.tools.line.busy(), m.ops)
	m.undo()
	await harness._wait_confirm()
	harness._ok("line undo removes drawing and snap data", m.pres.loose_lines.is_empty(), m.pres.loose_lines)
	m.redo()
	await harness._wait_confirm()
	harness._ok("line redo restores the drawing", m.pres.loose_lines.size() == 1 and m.drafts.has(("line:" + harness.id("r1"))), m.pres.loose_lines)
	# A chain starts at the end of the earlier single line and closes a triangle.
	await harness._click_at(Vector3(100, 0, 0))
	await harness._click_at(Vector3(100, 60, 0))
	harness._ok("each chain click ends a segment and keeps drawing", m.ops.size() == 2 and m.tools.line.busy(), m.ops)
	await harness._click_at(Vector3(200, 0, 0))
	await harness._click_at(Vector3(100, 0, 0))
	harness._ok("clicking chain start creates a closed profile and ends chain", m.ops.size() == 4 and m.ops.back().has("outline") and not m.tools.line.busy() and m.rects.has(harness.id("r4")), m.ops)
	await harness.get_tree().physics_frame
	await harness._push(Vector3(125, 20, 0), Vector3(125, 20, 40), "20")
	await harness._wait_wave()
	var bodies := harness._bodies()
	harness._ok("closed lines push an exact triangular board", bodies.has(harness.id("b1")) and absf(bodies.get(harness.id("b1"), {}).get("volume_mm3", 0.0) - 60000) < 0.1, bodies)
	m.undo()
	await harness._wait_wave()
	harness._ok("undo polygon push restores pickable outline", m.drafts.has(harness.id("r4")) and not m.body_tris.has(harness.id("b1")), m.drafts.keys())
	m.redo()
	await harness._wait_wave()
	harness._ok("redo polygon push consumes profile again", not m.drafts.has(harness.id("r4")) and m.body_tris.has(harness.id("b1")), m.drafts.keys())
	await harness._key(KEY_L)
	await harness._click_at(Vector3(300, 0, 0))
	await harness._drag_to(Vector3(330, 0, 0), 4)
	await harness._type("3/4\"\n")
	var last: Dictionary = m.ops.back()
	var start: Array = last.plane.get("origin", [])
	harness._ok("typed fractional inch line keeps exact length and chain", last.type == "line" and start.size() == 3 and absf(Vector3(last.end[0], last.end[1], last.end[2]).distance_to(Vector3(start[0], start[1], start[2])) - 19.05) < 0.001 and m.tools.line.busy(), last)
	await harness._key(KEY_ESCAPE)
	harness._ok("Escape ends chain without removing committed lines", not m.tools.line.busy() and m.ops.back().id == last.id, m.tools.line.state)

	# Stage 2: two crossing saved lines divide a face into four immediately previewed cells.
	await harness._fresh("line_regions", harness._plank(1, Vector3.ZERO, Vector3(200, 200, 20)))
	await harness._view(Vector3(100,100,20), -30, -50, 1.0)
	await _segment(Vector3(100,0,20), Vector3(100,200,20))
	await _segment(Vector3(0,100,20), Vector3(200,100,20))
	await harness._wait_confirm()
	var before: Dictionary = harness._bodies().get(harness.id("b1"), {})
	harness._ok("crossing lines preserve the original solid", before.get("volume_mm3", 0.0) == 800000, before)
	await harness._key(KEY_P)
	await harness._drag_to(Vector3(50,50,20), 4)
	var hover: Dictionary = m.tools.push.hover
	harness._ok("Push/Pull previews only the quadrant under cursor", hover.has("region") and absf(hover.get("region", {}).get("area", 0.0) - 10000) < 0.1, hover)
	await harness._push(Vector3(50,50,20), Vector3(50,50,40), "10")
	await harness._wait_wave()
	bodies = harness._bodies()
	harness._ok("one region op joins only the chosen quadrant", m.ops.back().target.has("region") and not m.ops.back().has("resize_stock") and absf(bodies.get(harness.id("b1"), {}).get("volume_mm3", 0.0) - 900000) < 0.1, bodies)
	await harness._push(Vector3(150,50,20), Vector3(150,50,0), "-5")
	await harness._wait_wave()
	bodies = harness._bodies()
	harness._ok("neighboring quadrant remains independently pushable", absf(bodies.get(harness.id("b1"), {}).get("volume_mm3", 0.0) - 850000) < 0.1, bodies)
	m.undo()
	await harness._wait_wave()
	harness._ok("region undo restores the preceding solid", absf(harness._bodies().get(harness.id("b1"), {}).get("volume_mm3", 0.0) - 900000) < 0.1)
	m.redo()
	await harness._wait_wave()
	harness._ok("region redo restores exact cut", absf(harness._bodies().get(harness.id("b1"), {}).get("volume_mm3", 0.0) - 850000) < 0.1)
	await harness._shot("line_regions")
	await harness._fresh("line_dangling", harness._plank(1, Vector3.ZERO, Vector3(200,200,20)))
	await _segment(Vector3(100,0,20), Vector3(100,60,20))
	await harness._key(KEY_P)
	await harness._drag_to(Vector3(50,50,20), 4)
	harness._ok("a dangling line leaves one whole face", not m.tools.push.hover.is_empty() and not m.tools.push.hover.has("region") and m.tools.push.hover.tris.size() == 6, m.tools.push.hover)

	await harness._fresh("line_loop_face", harness._plank(1, Vector3.ZERO, Vector3(200,200,20)))
	await harness._key(KEY_L)
	for point in [Vector3(60,60,20), Vector3(100,60,20), Vector3(100,100,20), Vector3(60,100,20), Vector3(60,60,20)]:
		await harness._click_at(point)
	await harness._wait_confirm()
	harness._ok("closed line loop on face preserves source volume", absf(harness._bodies().get(harness.id("b1"), {}).get("volume_mm3", 0.0) - 800000) < 0.1)
	await harness._push(Vector3(80,80,20), Vector3(80,80,0), "-5")
	await harness._wait_wave()
	harness._ok("closed line loop cuts a pocket on its own face", absf(harness._bodies().get(harness.id("b1"), {}).get("volume_mm3", 0.0) - 792000) < 0.1, harness._bodies())
	await harness._drag_to(Vector3(30,30,20), 4)
	harness._ok("outside loop previews a region with its hole", not m.tools.push.hover.is_empty() and absf(_area(m.tools.push.hover.tris) - 38400) < 0.1, m.tools.push.hover)
	await harness._push(Vector3(30,30,20), Vector3(30,30,40), "10")
	await harness._wait_wave()
	harness._ok("outer region push leaves the pocket alone", absf(harness._bodies().get(harness.id("b1"), {}).get("volume_mm3", 0.0) - 1176000) < 0.1, harness._bodies())

	await harness._fresh("line_exact_circle")
	await harness._view(Vector3(100,0,20), -30, -50, 1.0)
	await _segment(Vector3(250,0,0), Vector3(350,0,0))
	await harness._key(KEY_C)
	await harness._click_at(Vector3.ZERO)
	await harness._drag_to(Vector3(40,0,0), 4)
	await harness._type("40\n")
	await harness.get_tree().physics_frame
	await harness._push(Vector3.ZERO, Vector3(0,0,40), "20")
	await harness._wait_wave()
	harness._ok("unrelated lines preserve exact Circle Push/Pull", not m.ops.back().target.has("region") and absf(harness._bodies().get(harness.id("b1"), {}).get("volume_mm3",0.0) - PI*1600*20) < 0.1, harness._bodies())
	await _segment(Vector3(0,-39.8,20), Vector3(0,40,20))
	await harness._push(Vector3(-20,0,20), Vector3(-20,0,40), "10")
	await harness._wait_wave()
	var divider: Dictionary = m.pres.lines_on(harness.id("b1"), Vector3(0,0,1), Vector3(0,0,20))[0]
	var ab: Vector3 = divider.b - divider.a
	var offset := absf(ab.cross(-divider.a + Vector3(0,0,20)).z) / ab.length()
	var small := 1600*acos(offset/40) - offset*sqrt(1600-offset*offset)
	var same_side := ab.cross(Vector3(-20,0,20)-divider.a).z * ab.cross(Vector3(0,0,20)-divider.a).z >= 0
	var exact_area := PI*1600-small if same_side else small
	harness._ok("a split circular face keeps its exact native arc", m.ops.back().target.has("region") and absf(harness._bodies().get(harness.id("b1"), {}).get("volume_mm3",0.0) - (PI*1600*20+exact_area*10)) < 0.1, harness._bodies())

func _segment(a: Vector3, b: Vector3) -> void:
	await harness._key(KEY_L)
	# Pick the top side of the boundary, then snap to the exact edge; the edge has two visible normals.
	var inside := a
	if is_zero_approx(inside.y): inside.y = 0.25
	if is_zero_approx(inside.x): inside.x = 0.25
	await harness._click_at(inside)
	await harness._click_at(b)
	await harness._key(KEY_ESCAPE)

func _area(triangles: PackedVector3Array) -> float:
	var result := 0.0
	for i in range(0, triangles.size(), 3): result += (triangles[i+1] - triangles[i]).cross(triangles[i+2] - triangles[i]).length() * 0.5
	return result
