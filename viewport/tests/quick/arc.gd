extends RefCounted
## I60: Arc modes, lengths, radius and sweep, plus a face-to-face Push/Pull.
const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	await harness._fresh("arc")
	await harness._view(Vector3(130, 45, 0), -30, -50, 1.0)
	await harness._key(KEY_A)
	_check_mode("2-Point Arc")
	await harness._click_at(Vector3.ZERO)
	await harness._key(KEY_A)
	_check_mode("Centre Arc")
	harness._ok("changing arc mode cancels the gesture", not m.tools.arc.busy() and m.ops.is_empty())
	await harness._key(KEY_A)
	_check_mode("2-Point Arc")
	await harness._click_at(Vector3.ZERO)
	await harness._drag_to(Vector3(105, 0, 0), 6)
	await harness._type("100\n")
	harness._ok("typed chord length sets the second point", m.ui_vcb_label.text == "Bulge"
		and absf(m.tools.arc.state.first.distance_to(m.tools.arc.state.second) - 100.0) < 0.001, m.tools.arc.state)
	await harness._drag_to(Vector3(50, 24, 0), 6)
	await harness._type("20\n")
	var arc: Dictionary = m.ops.back()
	harness._ok("typed 20 mm bulge saves its exact halfway point and ends the gesture",
		arc.type == "arc" and absf((_xyz(arc.mid) - _chord_mid(arc)).length() - 20.0) < 0.001
		and not m.tools.arc.busy(), arc)
	await harness._wait_confirm()
	m.undo()
	await harness._wait_confirm()
	harness._ok("arc undo removes draft and snap geometry", not m.pres.loose_lines.has(arc.id) and not m.drafts.has("line:" + arc.id))
	m.redo()
	await harness._wait_confirm()
	harness._ok("arc redo restores the faceted drawing", m.pres.loose_lines.get(arc.id, {}).get("pts", []).size() > 2)
	var midpoint := _xyz(arc.mid)
	await harness._drag_to(midpoint, 4)
	var snap: Dictionary = m.infer.point(m.cursor2d.position, "")
	harness._ok("the arc snaps to its true midpoint", snap.get("kind", "") == "midpoint"
		and snap.get("point", Vector3.ZERO).distance_to(midpoint) < 0.001, snap)

	await harness._drag_to(Vector3(150, 0, 0), 4)
	await harness._button(true)
	await harness._drag_to(Vector3(230, 0, 0), 6)
	await harness._button(false)
	harness._ok("dragging an Arc chord advances to the bulge", m.ui_vcb_label.text == "Bulge")
	await harness._drag_to(Vector3(190, 30, 0), 4)
	await harness._type("25r\n")
	harness._ok("radius shorter than half the chord is refused with a status note",
		m.ops.size() == 1 and m.ui_sync.text == "Radius must be at least half the chord", m.ui_sync.text)
	await harness._type("50 R\n")
	arc = m.ops.back()
	var half := _xyz(arc.end).distance_to(_xyz(arc.plane.origin)) * 0.5
	var sag := 50.0 - sqrt(2500.0 - half * half)
	harness._ok("typed radius gives the minor arc on the cursor side", m.ops.size() == 2
		and absf(_xyz(arc.mid).y - _chord_mid(arc).y - sag) < 0.001, arc)
	await harness._wait_confirm()

	await harness._key(KEY_A)
	await harness._click_at(Vector3(280, 0, 0))
	await harness._drag_to(Vector3(315, 0, 0), 4)
	await harness._type("30\n")
	harness._ok("typed centre radius advances to Angle", m.ui_vcb_label.text == "Angle")
	await harness._type("360\n")
	harness._ok("a full sweep is refused", m.ops.size() == 2 and m.tools.arc.busy())
	await harness._type("90\n")
	arc = m.ops.back()
	var centre := Vector3(280, 0, 0)
	var radial := _xyz(arc.plane.origin) - centre
	harness._ok("Centre Arc saves a typed positive 90-degree sweep and radius",
		m.ops.size() == 3 and absf(radial.length() - 30.0) < 0.01
		and _xyz(arc.mid).distance_to(centre + radial.rotated(Vector3.BACK, PI / 4)) < 0.02
		and _xyz(arc.end).distance_to(centre + radial.rotated(Vector3.BACK, PI / 2)) < 0.02, arc)
	await harness._view(Vector3(180, 120, 0), -30, -50, 1.0)
	await harness._click_at(Vector3(180, 125, 0))
	await harness._click_at(Vector3(220, 125, 0))
	await harness._drag_to(Vector3(180, 165, 0), 4)
	await harness._drag_to(Vector3(140, 125, 0), 4)
	await harness._click_at(Vector3(180, 85, 0))
	arc = m.ops.back()
	harness._ok("a mouse sweep crosses 180 degrees continuously", m.ops.size() == 4
		and _xyz(arc.mid).x < 180 and _xyz(arc.mid).y > 125, arc)
	await harness._click_at(Vector3(280, 100, 0))
	await harness._key(KEY_ESCAPE)
	harness._ok("Escape ends the gesture and retains Centre Arc", m.ops.size() == 4
		and not m.tools.arc.busy() and m.tools.arc.tip() == "Centre Arc")

	await harness._fresh("arc_face", harness._plank(1, Vector3.ZERO, Vector3(100, 100, 20)))
	await harness._view(Vector3(50, 50, 20), -30, -50, 0.72)
	await harness._key(KEY_A)
	_check_mode("2-Point Arc")
	await harness._click_at(Vector3(50, 0.25, 20))
	await harness._click_at(Vector3(50, 100, 20))
	await harness._drag_to(Vector3(70, 50, 20), 4)
	await harness._type("20\n")
	await harness._wait_confirm()
	await harness._key(KEY_P)
	await harness._drag_to(Vector3(30, 45, 20), 6)
	var hover: Dictionary = m.tools.push.hover
	var area := 5000.0 + 72.5 ** 2 * (4.0 * atan2(20.0, 50.0) - sin(4.0 * atan2(20.0, 50.0))) * 0.5
	harness._ok("the Push/Pull draft traces just the selected arc-bounded side", hover.has("region")
		and absf(hover.get("region", {}).get("area", 0.0) - area) < 10.0, hover.get("region", {}))
	await harness._push(Vector3(30, 45, 20), Vector3(30, 45, 35), "10")
	await harness._wait_wave()
	var body: Dictionary = harness._bodies().get(harness.id("b1"), {})
	harness._ok("FreeCAD joins just the exact curved region", m.ops.back().target.has("region")
		and absf(body.get("volume_mm3", 0.0) - (200000.0 + area * 10.0)) < 0.2, body)


func _check_mode(kind: String) -> void:
	harness._ok("A shows the " + kind + " mode and hint",
		m.tool == "arc" and m.ui_hint.text.begins_with(kind + ":") and m.tools.arc.tip() == kind, m.ui_hint.text)


func _xyz(p: Array) -> Vector3:
	return Vector3(p[0], p[1], p[2])


func _chord_mid(arc: Dictionary) -> Vector3:
	return (_xyz(arc.end) + _xyz(arc.plane.origin)) * 0.5
