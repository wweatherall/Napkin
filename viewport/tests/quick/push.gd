extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 2. Push/Pull: a new board, join by default (I04b), B for a separate board, the saved indicator (Q22)
	await harness._fresh("push", harness._plank(1, Vector3.ZERO, Vector3(300, 200, 18)))
	await harness._view(Vector3(150, 100, 20), -30, -40, 1.0)
	await harness._rect(Vector3(100, 50, 18), Vector3(150, 100, 18), "50,50")
	m.saved_shown.clear()
	await harness._push(Vector3(125, 75, 18), Vector3(125, 75, 30), "20")
	await harness._wait_wave()
	harness._ok("pushed out from a face, it joins that board", harness._shown_ids() == [harness.id("b1")] and not m.ops.back().has("body"), [harness._shown_ids(), m.ops.back()])
	harness._ok("the joined bump adds 50 x 50 x 20", is_equal_approx(harness._bodies()[harness.id("b1")]["volume_mm3"], 300.0 * 200 * 18 + 50 * 50 * 20), harness._bodies()[harness.id("b1")]["volume_mm3"])
	var t0 := Time.get_ticks_msec()
	while m.ui_saved.text != "Saved" and Time.get_ticks_msec() - t0 < 3000: await harness._frames(1)
	harness._ok("the save indicator says Saving..., then Saved (T45: however quickly the save lands)",
		m.ui_saved.text == "Saved" and m.saved_shown.slice(-2) == ["Saving…", "Saved"], [m.ui_saved.text, m.saved_shown])
	await harness._key(KEY_B)
	await harness._rect(Vector3(200, 50, 18), Vector3(250, 100, 18), "40,40")
	await harness._push(Vector3(220, 70, 18), Vector3(220, 70, 30), "10")
	await harness._wait_wave()
	harness._ok("with B, a separate board", harness._shown_ids() == [harness.id("b1"), harness.id("b2")], harness._shown_ids())

	await _pocket_floor_tie()
	await _hover_and_drag_cache()


func _hover_and_drag_cache() -> void:
	await harness._fresh("push_cache", harness._plank(1, Vector3.ZERO, Vector3(300, 200, 18)))
	await harness._view(Vector3(150, 100, 18), -30, -40, 0.7)
	m.set_tool("push")
	var push = m.tools["push"]
	push.reset()
	var before_recomputes: int = push._hover_recomputes
	var p1 := harness._screen_of(Vector3(100, 100, 18), Vector2.ZERO)
	var p2 := harness._screen_of(Vector3(180, 120, 18), Vector2.ZERO)
	push.mouse_moved(p1)
	var after_first: int = push._hover_recomputes
	var initial_tris: PackedVector3Array = push.hover.get("tris", PackedVector3Array()).duplicate()
	push.mouse_moved(p2)
	var after_same_face: int = push._hover_recomputes
	harness._ok("hovering across the same face reuses the cached region without recomputing",
		after_first == before_recomputes + 1 and after_same_face == after_first
		and not initial_tris.is_empty(), [before_recomputes, after_first, after_same_face, initial_tris.size()])

	# Drag across same distance (cached) then distinct distances (rebuilt)
	push.click(p1)
	var before_previews: int = push._preview_rebuilds
	var d1 := harness._screen_of(Vector3(100, 100, 38), Vector2.ZERO)
	var d2 := harness._screen_of(Vector3(100, 100, 58), Vector2.ZERO)
	push.mouse_moved(d1)
	var dist1: float = push.state.get("dist", 0.0)
	var after_d1: int = push._preview_rebuilds
	push.mouse_moved(d1)
	var after_d1_repeat: int = push._preview_rebuilds
	push.mouse_moved(d2)
	var dist2: float = push.state.get("dist", 0.0)
	var after_d2: int = push._preview_rebuilds
	harness._ok("push drag skips redundant preview rebuilds at the same distance and updates across distinct distances",
		after_d1 == before_previews + 1 and after_d1_repeat == after_d1
		and after_d2 == after_d1 + 1 and not is_equal_approx(dist1, dist2),
		[before_previews, after_d1, after_d1_repeat, after_d2, dist1, dist2])
	push.reset()

	# Push a pocket, then hover the modified top face: cache must invalidate and recompute the updated region
	await harness._rect(Vector3(50, 50, 18), Vector3(110, 110, 18), "60,60")
	await harness._push(Vector3(80, 80, 18), Vector3(80, 80, 12), "-6")
	await harness._wait_wave()
	m.set_tool("push")
	var pre_mod: int = push._hover_recomputes
	push.mouse_moved(p2)
	var mod_tris: PackedVector3Array = push.hover.get("tris", PackedVector3Array()).duplicate()
	var after_mod: int = push._hover_recomputes
	harness._ok("hovering after a push modifies the face recomputes the updated region",
		after_mod == pre_mod + 1 and mod_tris != initial_tris, [pre_mod, after_mod, initial_tris.size(), mod_tris.size()])

	# Undo the push (and rect) and hover again without calling reset(): cache must invalidate and restore original region
	m.undo()
	await harness._wait_confirm()
	m.undo()
	await harness._wait_confirm()
	var pre_undo: int = push._hover_recomputes
	push.mouse_moved(p2)
	var undo_tris: PackedVector3Array = push.hover.get("tris", PackedVector3Array()).duplicate()
	var after_undo: int = push._hover_recomputes
	harness._ok("hovering after undo invalidates the cache and recomputes the restored face",
		after_undo == pre_undo + 1 and undo_tris != mod_tris and undo_tris.size() == initial_tris.size(),
		[pre_undo, after_undo, mod_tris.size(), undo_tris.size(), initial_tris.size()])


func _pocket_floor_tie() -> void:
	await harness._fresh("pocket_floor", harness._plank(1, Vector3.ZERO, Vector3(300, 200, 18)))
	await harness._view(Vector3(150, 100, 18), -30, -40, 0.6)
	await harness._rect(Vector3(40, 40, 18), Vector3(140, 100, 18), "100,60")
	await harness._push(Vector3(90, 70, 18), Vector3(90, 70, 12), "-6")
	await harness._wait_wave()
	var pocket_a: String = m.ops.back().id
	# Start B on the remaining top so its plane is the top even where it overlaps A.
	await harness._rect(Vector3(200, 90, 18), Vector3(100, 50, 18), "100,40")
	await harness._wait_confirm()
	var profile_b: Dictionary = m.ops.back()

	var over_a := Vector3(120, 70, 18)
	var away_from_a := Vector3(170, 70, 18)
	var push = m.tools["push"]
	_aim_pocket(over_a, -6)
	var snapped: bool = push.state.get("snap", "") == "face behind"
	await harness._type("-6\n")
	await harness._wait_wave()
	var cut: Dictionary = m.ops.back()
	harness._ok("typing -6 after a floor snap makes a measured cut", snapped and cut.type == "push_pull"
		and is_equal_approx(cut.distance, -6.0) and not cut.has("to_face"), cut)
	m.undo()
	await harness._wait_confirm()

	var finish := _aim_pocket(over_a, -18)
	snapped = push.state.get("snap", "") == "back face"
	push.click(finish)
	await harness._wait_wave()
	cut = m.ops.back()
	harness._ok("a back face snap sends through without a floor tie", snapped and cut.get("through", false)
		and not cut.has("to_face"), cut)
	m.undo()
	await harness._wait_confirm()

	push.click(_aim_pocket(away_from_a, 8))
	await harness._wait_wave()
	cut = m.ops.back()
	harness._ok("pushing out sends no floor tie", cut.get("distance", 0) > 0 and not cut.has("to_face"), cut)
	m.undo()
	await harness._wait_confirm()

	finish = _aim_pocket(away_from_a, -6)
	var free: bool = push.state.get("snap", "") == ""
	push.click(finish)
	await harness._wait_wave()
	cut = m.ops.back()
	harness._ok("an unsnapped pointer cut sends no floor tie", free and cut.get("distance", 0) < 0
		and not cut.get("through", false) and not cut.has("to_face"), cut)
	m.undo()
	await harness._wait_confirm()

	push.click(_aim_pocket(over_a, -6))
	await harness._wait_wave()
	var tied_cut: Dictionary = m.ops.back()
	var to_face: Dictionary = tied_cut.get("to_face", {})
	var point: Array = to_face.get("point", [0, 0, 0])
	harness._ok("a pointer cut ties profile B to the floor directly behind the grab",
		tied_cut.get("target", {}).get("rect", "") == profile_b.id and tied_cut.get("distance") == -6.0
		and not tied_cut.has("through") and to_face.get("normal") == [0.0, 0.0, 1.0]
		and Vector3(point[0], point[1], point[2]).distance_to(Vector3(120, 70, 12)) < 0.01, tied_cut)

	var body := harness.id("b1")
	# Get A's native cutter name from the same inspection used by the Properties panel.
	m.properties_panel.show()
	m.sel.set_selection([body])
	await harness._wait_properties()
	var cutter_name := ""
	for feature in m.properties_panel.data.get("objects", []):
		if feature.type == "Part::Extrusion" and feature.label == pocket_a + " push":
			cutter_name = feature.name
			break
	var pocket_area := 100.0 * 60 + 100.0 * 40 - 40.0 * 40
	var shallow_volume := 300.0 * 200 * 18 - pocket_area * 6
	var deep_volume := 300.0 * 200 * 18 - pocket_area * 10
	m._edit_property({"body": body, "object": cutter_name, "property": "LengthFwd", "value": "10mm", "mode": "value"})
	await harness._wait_confirm()
	m.properties_panel.hide()
	var volume: float = harness._bodies().get(body, {}).get("volume_mm3", 0)
	var edit: Dictionary = m.ops.back()
	harness._ok("deepening A to 10 mm deepens snapped B as well", edit.type == "property_edit"
		and absf(volume - deep_volume) < 0.1, [edit, volume])

	m.undo()
	await harness._wait_confirm()
	m.undo()
	await harness._wait_confirm()
	volume = harness._bodies().get(body, {}).get("volume_mm3", 0)
	harness._ok("undo removes the snapped pocket B", m.ops.back().id == profile_b.id
		and absf(volume - (300.0 * 200 * 18 - 100.0 * 60 * 6)) < 0.1, [m.ops.back(), volume])
	m.redo()
	await harness._wait_confirm()
	volume = harness._bodies().get(body, {}).get("volume_mm3", 0)
	harness._ok("redo restores B and its floor reference", not to_face.is_empty() and m.ops.back() == tied_cut
		and absf(volume - shallow_volume) < 0.1, [m.ops.back(), volume])
	m.redo()
	await harness._wait_confirm()
	volume = harness._bodies().get(body, {}).get("volume_mm3", 0)
	harness._ok("after redo, pocket B follows A's depth again", m.ops.back() == edit
		and absf(volume - deep_volume) < 0.1, [m.ops.back(), volume])


func _aim_pocket(anchor: Vector3, distance: float) -> Vector2:
	m.set_tool("push")
	var push = m.tools["push"]
	push.click(harness._screen_of(anchor, Vector2.ZERO))
	var finish := harness._screen_of(anchor + Vector3(0, 0, distance), Vector2.ZERO)
	push.mouse_moved(finish)
	return finish
