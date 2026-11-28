extends "res://tools/tool.gd"
## Move (M), SketchUp style: grab a point on a board (or a hole's wall: the hole), move, click or type a distance.
## Ctrl/Option toggles copy, Shift toggles mirror (the board flips across the plane halfway to the cursor).
## Arrows cycle axis lock -> plane lock -> free. After a copy: 5x, x5, *5 or 5* for an array, /5 to spread copies.
##
## Context-only: uses only `ctx` and `Geo` (never Main or inference). Consumes selection when grab point belongs to it.
## Entry points: commit_move, commit_mirror_move.
## a plain number right after a move changes its distance.

const TOOL := {"id": "move", "label": "Move", "tip": "Move (M)", "key": KEY_M, "order": 50, "show_links": true}   # the toolbar, the Tools menu and the key (tool_registry.gd)

var state := {}
var copy := false
var mirror := false
var _shift_tap := false
var last_oid := ""      # the move/copy you can still adjust by typing
var memo := {}          # move op id -> {"tris": geometry before the move, "ref": pick-up point}


func reset() -> void:
	state = {}
	press_reset()
	copy = false
	mirror = false
	_shift_tap = false


func hint() -> String:
	return "Move: grab a point on a board, click or type a distance. Ctrl/Option = copy, Shift = mirror, arrows lock axis. After a copy: 5x or /5"


func busy() -> bool:
	return state.get("active", false) or last_oid != ""


func in_gesture() -> bool:
	return state.get("active", false)        # (after a move, typing amends it; that isn't a gesture)


func accepts(ch: String) -> bool:
	return super.accepts(ch) or ch.to_lower() == "x"


func mouse_moved(screen: Vector2) -> void:
	press_moved(screen)
	_move_move(screen)


func click(screen: Vector2) -> void:
	_move_click(screen)


func release(screen: Vector2) -> void:
	# a press-and-drag ends here; a click goes on until the next click (I43). A mirror only if the cursor moved:
	# a long press in place would otherwise mirror the board where it stands.
	var r := press_released()
	if not r.get("drag", false) or not state.get("active", false): return
	if mirror and state.get("cut", {}).is_empty() and not r["moved"]: return
	_move_move(screen)
	_finish()


func observe_shift(e: InputEventKey) -> void:
	# Wait for the release to distinguish a mirror tap from a chord like Shift+8.
	if e.pressed:
		_shift_tap = e.keycode == KEY_SHIFT and ctx.ui.typed_text().is_empty()
	elif e.keycode == KEY_SHIFT and _shift_tap:
		_shift_tap = false
		if _moving_drawings():
			ctx.ui.show_status("Drawings can be moved. Copy and mirror require boards.")
			return
		mirror = not mirror
		_refresh_mode()


func _moving_drawings() -> bool:
	return state.get("active", false) and not state.get("drawing_ids", []).is_empty()


func _refresh_mode() -> void:
	var cursor := ctx.pick.cursor()
	if in_gesture(): _move_move(cursor)
	ctx.ui.refresh_measurements()
	ctx.ui.refresh_tip(cursor)


func key(e: InputEventKey) -> bool:
	if e.keycode in [KEY_CTRL, KEY_ALT]:
		if _moving_drawings():
			ctx.ui.show_status("Drawings can be moved. Copy and mirror require boards.")
			return true
		copy = not copy                # SketchUp: tap Ctrl (Option on a Mac) to toggle copy
		_refresh_mode()
		return true
	if state.get("active", false):
		var lock: int = {KEY_RIGHT: 0, KEY_LEFT: 1, KEY_UP: 2}.get(e.keycode, -2)
		if lock > -2:
			var mode: String = state.get("lock_mode", "free")
			if state["lock"] != lock or mode == "free":
				state["lock"] = lock; state["lock_mode"] = "axis"
			elif mode == "axis":
				state["lock_mode"] = "plane"          # tap again: the plane perpendicular to that axis
			else:
				state["lock"] = -1; state["lock_mode"] = "free"
			_move_move(ctx.pick.cursor())
			ctx.ui.refresh_tip(ctx.pick.cursor())
			return true
	return false


func parse_array_count(txt: String) -> Dictionary:
	"""The whole-number forms that Measurements passes through before evaluating a length."""
	var t := txt.strip_edges().to_lower()
	var divide := t.begins_with("/")
	var digits := ""
	if divide or t.begins_with("x") or t.begins_with("*"):
		digits = t.substr(1)
	elif t.ends_with("x") or t.ends_with("*"):
		digits = t.left(-1)
	if not digits.is_valid_int() or digits[0] not in "0123456789":
		return {}
	return {"count": maxi(1, int(digits)), "divide": divide}


func typed(txt: String) -> void:
	if not state.get("active", false):
		_amend_last_move(txt)
		return
	if mirror:
		if txt.is_valid_float() and state.get("mir_face", "") != "":
			var fn: Vector3 = state["mir_n"]          # off the snapped face, on its outside (T27)
			commit_mirror(state["mir_p"] + fn * float(txt), fn)
			return
		if txt.is_valid_float():
			var ax: int = state.get("mir_ax", state["face_ax"])
			var d := absf(float(txt))
			var side: float = signf(state["vec"][ax]) if absf(state["vec"][ax]) >= GEOMETRY_TOLERANCE_MM else state["face_sign"]
			var c: float
			if ax == state["face_ax"]:
				c = state["face_c"] + side * d
			else:
				c = state["hi"][ax] + d if side >= 0 else state["lo"][ax] - d
			commit_mirror_move(ax, c)
		return
	var parsed := parse_array_count(txt)
	if not parsed.is_empty():
		if not state.get("drawing_ids", []).is_empty():
			ctx.ui.show_status("Copy counts require boards.")
			return
		copy = true
		state["count"] = parsed["count"]
		state["divide"] = parsed["divide"]
		_preview_move()
		ctx.ui.refresh_tip(ctx.pick.cursor())
		return
	var tl := txt.to_lower()
	if tl.is_valid_float() and state["vec"].length() >= GEOMETRY_TOLERANCE_MM:
		commit_move(state["vec"].normalized() * absf(float(tl)), state.get("count", 1), state.get("divide", false))


func vcb_label() -> String:
	if mirror: return "Face to plane"
	if copy and state.get("active", false) and state.get("count", 1) > 1:
		return ("Divide /%d" if state.get("divide", false) else "Copy ×%d") % state["count"]
	return "Copy distance" if copy else "Distance"


func vcb_value() -> String:
	if not state.get("active", false): return ""
	if mirror and state.get("mir_face", "") != "":
		return ctx.ui.format_length(absf((state["ref"] - state["mir_p"]).dot(state["mir_n"])))
	if mirror and state.has("mir_c"):
		return ctx.ui.format_length(_mirror_face_gap(state["mir_ax"], state["mir_c"]))
	return ctx.ui.format_length(state["vec"].length())


func tip() -> String:
	if state.get("active", false) and mirror and state.get("mir_face", "") != "":
		return "Mirror%s across %s's face\ntype a distance to stand the plane off it" % [" + copy" if copy else "", state["mir_face"]]
	if state.get("active", false) and mirror and state.has("mir_c"):
		var g := _mirror_face_gap(state["mir_ax"], state["mir_c"])
		var col: String = ["red", "green", "blue"][state["mir_ax"]]
		return "Mirror%s (%s plane)\nface → plane  %s\nface → mirrored face  %s" % [" + copy" if copy else "", col,
			ctx.ui.format_length(g), ctx.ui.format_length(2.0 * g)]
	if state.get("active", false):
		var k: String = state.get("kind", "")
		var prefix := "Move"
		if copy:
			var cnt: int = state.get("count", 1)
			if cnt > 1:
				prefix = ("Divide /%d" if state.get("divide", false) else "Copy ×%d") % cnt
			else:
				prefix = "Copy +"
		return "%s  %s%s" % [prefix, ctx.ui.format_length(state["vec"].length()), ("\n" + k) if k != "" else ""]
	if last_oid != "" and copy:
		return "type 5x or /5 for more copies"
	if copy or mirror:
		return ("+ copy " if copy else "") + ("+ mirror" if mirror else "")
	return ""


func _mirror_axis_and_plane() -> Array:
	var vec: Vector3 = state["vec"]
	var ax: int = state["lock"] if state.get("lock_mode", "free") == "axis" else -1
	if ax < 0:
		ax = state["face_ax"]           # parallel to the face you grabbed, unless an arrow key says otherwise
	var ref: Vector3 = state["ref"]
	return [ax, ref[ax] + vec[ax] * 0.5]        # perpendicular bisector: the grabbed point lands under the cursor


func _mirror_face_gap(ax: int, c: float) -> float:
	if ax == state["face_ax"]:
		return absf(c - state["face_c"])
	return c - state["hi"][ax] if c >= (state["lo"][ax] + state["hi"][ax]) * 0.5 else state["lo"][ax] - c


func _face_plane_under_cursor() -> Dictionary:
	"""While mirroring with no arrow-key lock: a face of another board under the cursor (T27, Q12)."""
	if state.get("lock_mode", "free") != "free": return {}
	var p := ctx.pick.hit(ctx.pick.cursor())
	var b: String = p.get("body", "")
	if not p.get("hit", false) or b == "" or b == state["body"] or state.get("unit", {}).get("bodies", []).has(b): return {}
	return {"p": p["point"], "n": Geo.clean_normal(p["normal"]), "body": b}


func _preview_mirror_move() -> void:
	var fp := _face_plane_under_cursor()
	state["mir_face"] = fp.get("body", "")
	if not fp.is_empty():
		_preview_mirror_plane(fp["p"], fp["n"])
		return
	var r := _mirror_axis_and_plane()
	var ax: int = r[0]; var c: float = r[1]
	state["mir_ax"] = ax; state["mir_c"] = c
	var ghost := Geo.mirror_triangles(state["tris"], ax, c)
	var lo: Vector3 = state["lo"]; var hi: Vector3 = state["hi"]
	for q in ghost: lo = lo.min(q); hi = hi.max(q)
	var u := (ax + 1) % 3; var v := (ax + 2) % 3
	var corners := PackedVector3Array()
	for uv in [[lo[u] - 60, lo[v] - 60], [hi[u] + 60, lo[v] - 60], [hi[u] + 60, hi[v] + 60], [lo[u] - 60, hi[v] + 60]]:
		var pt := Vector3.ZERO
		pt[ax] = c; pt[u] = uv[0]; pt[v] = uv[1]
		corners.append(pt)
	ctx.view.mirror_preview(ghost, corners, ax)
	var landed: Vector3 = state["ref"]
	landed[ax] = 2.0 * c - landed[ax]
	ctx.view.marker({"hit": true, "point": landed})
	ctx.ui.refresh_measurements()


func _preview_mirror_plane(pp: Vector3, n: Vector3) -> void:
	"""The ghost and plane for a plane at any angle (a snapped face)."""
	state["mir_p"] = pp; state["mir_n"] = n
	var ghost := Geo.reflect_tris(state["tris"], pp, n)
	var lo: Vector3 = state["lo"]; var hi: Vector3 = state["hi"]
	for q in ghost: lo = lo.min(q); hi = hi.max(q)
	var bs := Geo.plane_basis(n)
	var c := (lo + hi) * 0.5
	c -= n * (c - pp).dot(n)
	var r := (hi - lo).length() * 0.5 + 60.0
	var u: Vector3 = bs[0] * r; var v: Vector3 = bs[1] * r
	var corners := PackedVector3Array([c - u - v, c + u - v, c + u + v, c - u + v])
	ctx.view.mirror_preview(ghost, corners)
	ctx.view.marker({"hit": true, "point": Geo.reflect_point(state["ref"], pp, n)})
	ctx.ui.refresh_measurements()


func commit_mirror_move(ax: int, c: float) -> void:
	var pt := Vector3.ZERO
	pt[ax] = c
	commit_mirror(pt, Geo.axis_vector(ax))


func commit_mirror(pp: Vector3, n: Vector3) -> void:
	"""Mirror the grabbed board across the plane through pp with normal n (any angle)."""
	ctx.ui.clear_rejection()
	var body: String = state["body"]
	var oid := ctx.document.next_id("m")
	var targets: Array = state["unit"]["bodies"].duplicate() if state.get("unit", {}).get("kind", "") == "selection" else [body]
	var op := {"id": oid, "type": "mirror", "targets": targets, "plane": {"point": Geo.arr3(pp), "normal": Geo.arr3(n)}}
	var made: Array = []
	if copy:
		for b in targets:
			made.append(ctx.document.next_id("b"))
		op["new_ids"] = made
		if ctx.selection.context() == "" and targets.all(func(b): return ctx.selection.assembly_of(b) == ""):
			op["group"] = ctx.document.next_id("a")
	else:
		op["replace"] = true
		made = targets.duplicate()
	ctx.document.append(op)
	var pieces := []
	var all := PackedVector3Array()
	for i in targets.size():
		var ghost := Geo.reflect_tris(ctx.model.triangles(targets[i]), pp, n)
		all.append_array(ghost)
		pieces.append(_board_piece(ghost, made[i]))
	var landed := Geo.reflect_point(state["ref"], pp, n)
	ctx.view.present_draft(op, pieces, {"origin": landed, "tris": all, "is_new": copy, "bodies": made, "attach": "drafts"})
	last_oid = ""
	_end_commit()


func _board_piece(tris: PackedVector3Array, id: String) -> Dictionary:
	return {"tris": tris, "style": "draft", "line_color": Color(0.6, 0.35, 0), "body_id": id, "replace": not copy}


func _end_commit() -> void:
	state["active"] = false
	ctx.view.clear_guides()
	ctx.view.clear_preview()
	ctx.view.hide_marker()
	ctx.ui.refresh_tip(ctx.pick.cursor())
	ctx.document.sync()


func _move_click(screen: Vector2) -> void:
	if not state.get("active", false):
		var hit := ctx.pick.hit(screen)
		var drawing_hit := ctx.pick.drawing_hit(screen, hit)
		var p := ctx.pick.snap(hit, screen) if drawing_hit.is_empty() else drawing_hit
		if not p.get("hit", false) or p["body"] == "": return
		var drawing := ctx.model.drawing(p["body"])
		if drawing.is_empty() and not ctx.model.has_body(p["body"]): return
		last_oid = ""
		var tris: PackedVector3Array = ctx.model.triangles(p["body"])
		var unit := ctx.selection.unit_of(p["body"])             # from outside: the whole assembly, or the array's row (I32)
		var selected := ctx.selection.ids()
		if selected.has(p["body"]) and selected.size() > 1:
			unit = {"id": p["body"], "kind": "selection", "bodies": selected}
		var segments := PackedVector3Array()
		var drawing_ids: Array = unit.bodies.filter(func(id): return not ctx.model.drawing(id).is_empty())
		var cut := ctx.model.cut_at(p["body"], p["point"]) if unit["kind"] == "board" and not selected.has(p["body"]) else {}
		var cut_ref := {}
		if unit["kind"] != "board":
			tris = ctx.model.unit_triangles(unit)
		for id in drawing_ids:
			var profile := ctx.model.drawing(id)
			tris.append_array(profile.tris)
			segments.append_array(profile.segments)
		if not drawing_ids.is_empty():
			copy = false
			mirror = false
		if not cut.is_empty():                       # clicked a hole: move / copy the hole, not the board
			cut_ref = {"body": p["body"], "op": cut["op"], "kind": cut["kind"]}
			tris = ctx.model.cut_triangles(p["body"], cut["op"])
		var lo := Vector3(INF, INF, INF); var hi := -lo
		for q in tris + segments: lo = lo.min(q); hi = hi.max(q)
		var n: Vector3 = p["normal"]
		var fax := 0
		for i in 3:
			if absf(n[i]) > absf(n[fax]): fax = i
		state = {"active": true, "body": p["body"], "tris": tris, "ref": p["point"],
					  "vec": Vector3.ZERO, "lock": -1, "lock_mode": "free", "inferred": -1, "kind": "",
					  "count": 1, "divide": false, "lo": lo, "hi": hi,
					  "face_ax": fax, "face_c": snappedf(p["point"][fax], 0.01), "face_sign": signf(n[fax]),
					  "cut": cut_ref, "unit": unit, "drawing_ids": drawing_ids, "segments": segments}
		press_started(screen)
	else:
		_finish()


func _finish() -> void:
	"""The second click, or the release of a drag: the move (or mirror) is made."""
	if mirror and state.get("cut", {}).is_empty():
		if state.get("mir_face", "") != "": commit_mirror(state["mir_p"], state["mir_n"])
		else: commit_mirror_move(state["mir_ax"], state["mir_c"])
	else:
		if not pointer_distance_ok(state["vec"].length(), state.get("point_snap", false)): return
		commit_move(state["vec"], state.get("count", 1), state.get("divide", false))


func _move_move(screen: Vector2) -> void:
	if not state.get("active", false):
		var hp := ctx.pick.hit(screen)
		if hp.get("hit", false) and ctx.model.has_body(hp["body"]):
			var hc := ctx.model.cut_at(hp["body"], hp["point"])
			if hc.is_empty():
				ctx.view.preview(ctx.model.triangles(hp["body"]), "hover")
			else:
				var ht := ctx.model.cut_triangles(hp["body"], hc["op"])
				ctx.view.preview(ht, "cut_highlight", Geo.feature_edges(ht), Color(0.35, 0.15, 0.6))
		else:
			ctx.view.clear_preview()
		return
	var ref: Vector3 = state["ref"]
	var body: String = state["body"]
	var moving_cut: bool = not state.get("cut", {}).is_empty()
	var mode: String = state.get("lock_mode", "free")
	var lax: int = state["lock"]
	var dest = null
	var kind := ""
	var point_snap := false
	var guide_axis := -1
	var guide_plane := -1
	if mode == "axis":
		dest = ctx.pick.axis_dest(screen, ref, lax, body)
		kind = ["red", "green", "blue"][lax] + " axis (locked)"
		guide_axis = lax
	else:
		var plane_n := Geo.axis_vector(lax) if mode == "plane" else Vector3(0, 0, 1)
		if mode == "plane": guide_plane = lax
		var pt := ctx.pick.point(screen, "" if moving_cut else body)   # a hole can snap to its own board
		if not pt.is_empty():
			dest = pt["point"]
			if mode == "plane":                       # stay on the locked plane
				dest = dest - plane_n * (dest - ref).dot(plane_n)
			kind = pt["kind"]
			point_snap = true
		else:
			var axes := [0, 1, 2] if mode == "free" else [(lax + 1) % 3, (lax + 2) % 3]
			var inf := ctx.pick.axis(screen, ref, axes, state.get("inferred", -1))
			state["inferred"] = inf
			if inf >= 0:
				dest = ctx.pick.axis_dest(screen, ref, inf, body)
				kind = "on " + ["red", "green", "blue"][inf] + " axis"
				guide_axis = inf
			else:
				var hit := ctx.pick.hit(screen)
				if hit.get("hit", false) and hit["body"] != "" and hit["body"] != body and mode == "free":
					dest = hit["point"]                   # on another board's face
					var fn: Vector3 = hit["normal"]
					if ctx.pick.grid_enabled():
						var vec: Vector3 = dest - ref
						for i in 3:
							if absf(fn[i]) < 0.5: vec[i] = snappedf(vec[i], ctx.pick.grid_step())
						dest = ref + vec
					kind = "on face"
				else:
					dest = ctx.pick.plane_dest(screen, ref, plane_n)
					kind = "free" if mode == "free" else ["green/blue", "red/blue", "red/green"][lax] + " plane (locked)"
	if dest == null: return
	state["vec"] = dest - ref
	state["kind"] = kind
	state["point_snap"] = point_snap
	ctx.view.guides(ref, guide_axis, guide_plane)
	if mirror and not moving_cut:
		_preview_mirror_move()
		return
	ctx.view.marker({"hit": true, "point": dest, "snap": kind})
	_preview_move()


func _move_offsets(vec: Vector3, count: int, divide: bool, copy: bool) -> Array:
	var out := []
	if not copy:
		out.append(vec)
		return out
	for i in range(1, count + 1):
		out.append(vec * (float(i) / count) if divide else vec * i)
	return out


func _preview_move() -> void:
	var all := PackedVector3Array()
	var src: PackedVector3Array = state["tris"]
	if copy and state.get("unit", {}).get("kind", "") == "row":
		var body: String = state["body"]
		var aid: String = ctx.selection.assembly_of(body)
		src = ctx.model.unit_triangles({"bodies": ctx.selection.members_of(aid)}) if aid != "" else ctx.model.triangles(body)
	for off in _move_offsets(state["vec"], state["count"], state["divide"], copy):
		for q in src: all.append(q + off)
	var edges := Geo.feature_edges(all)
	for p in state.get("segments", PackedVector3Array()): edges.append(p + state["vec"])
	ctx.view.preview(all, "draft" if state.get("cut", {}).is_empty() else "cut", edges)
	ctx.ui.refresh_measurements()


func commit_move(vec: Vector3, count := 1, divide := false, reuse_oid := "") -> void:
	if vec.length() < GEOMETRY_TOLERANCE_MM: return
	ctx.ui.clear_rejection()
	if not state.get("cut", {}).is_empty():
		_commit_cut_move(vec, count, divide, reuse_oid)
		return
	var body: String = state.get("body", "")
	var unit: Dictionary = state.get("unit", {"kind": "board", "bodies": [body]})
	# Copying from an assembly row copies the pointed-at assembly, just as copying
	# from a board row copies its pointed-at board.
	var assembly := ctx.selection.assembly_of(body)
	if copy and unit["kind"] == "row" and assembly != "":
		unit = {"id": assembly, "kind": "assembly", "bodies": ctx.selection.members_of(assembly)}
	var assembly_row: bool = unit["kind"] == "row" and assembly != ""
	var targets: Array = unit["bodies"].duplicate() if unit["kind"] in ["selection", "assembly"] or assembly_row else [body]
	var whole := _whole_assemblies(targets) if copy else []
	var oid := reuse_oid
	if oid == "":
		oid = ctx.document.next_id("mv")
	var op := {"id": oid, "type": "move", "targets": targets, "selection": unit["kind"] in ["selection", "assembly"] or assembly_row,
			   "vector": [vec.x, vec.y, vec.z], "copy": copy}
	if not whole.is_empty():                     # each wholly copied assembly comes out as a new one (I47)
		var groups := {}
		for aid in whole:
			var ids := []
			for i in count:
				ids.append(ctx.document.next_id("a"))
			groups[aid] = ids if count > 1 else ids[0]
		op["groups"] = groups
	if not copy and (ctx.selection.context().begins_with("row:") or ctx.selection.context().begins_with("component:")):
		op["detach"] = true                          # inside an entered array a copy moves alone (I32)
	var offsets := _move_offsets(vec, count, divide, copy)
	var made := []
	if copy:
		op["count"] = count
		op["divide"] = divide
		for b in targets:
			for i in offsets.size():
				made.append(ctx.document.next_id("b"))
		op["new_ids"] = made
	ctx.document.append(op)
	var pieces := []
	var all := PackedVector3Array()
	var src: PackedVector3Array = state["tris"]
	memo[oid] = {"tris": src, "ref": state["ref"], "unit": unit.duplicate(true)}
	# A row move has one op target but previews every member. Copies follow the
	# same target-then-offset order used above to allocate their new body IDs.
	var sources: Array = unit["bodies"] if not copy and unit["kind"] != "board" else targets
	sources = sources.filter(func(id): return ctx.model.has_body(id))
	var wave_bodies: Array = made if copy else sources
	for source_id in sources:
		var source := src if unit["kind"] == "board" else ctx.model.triangles(source_id)
		for offset in offsets:
			var moved := PackedVector3Array()
			for point in source:
				moved.append(point + offset)
			all.append_array(moved)
			pieces.append(_board_piece(moved, wave_bodies[pieces.size()]))
	var dest: Vector3 = state["ref"] + offsets.back()
	if not pieces.is_empty():
		ctx.view.present_draft(op, pieces, {"origin": dest, "tris": all, "is_new": copy, "bodies": wave_bodies, "attach": "drafts"})
	last_oid = oid
	state["last_vec"] = vec
	_end_commit()


func _commit_cut_move(vec: Vector3, count: int, divide: bool, reuse_oid: String) -> void:
	"""Move a hole, or copy it (FreeCAD makes the copies a Draft array of the cutter)."""
	var cut: Dictionary = state["cut"]
	var body: String = cut["body"]
	var oid := reuse_oid
	if oid == "":
		oid = ctx.document.next_id("mv")
	var op := {"id": oid, "type": "move", "targets": [], "cut": {"body": body, "op": cut["op"]},
		"vector": [vec.x, vec.y, vec.z], "copy": copy}
	if copy:
		op["count"] = count
		op["divide"] = divide
	ctx.document.append(op)
	var pieces := []
	var src: PackedVector3Array = state["tris"]
	memo[oid] = {"tris": src, "ref": state["ref"], "cut": cut}
	var offsets := _move_offsets(vec, count, divide, copy)
	for off in offsets:
		var moved := PackedVector3Array()
		for q in src: moved.append(q + off)
		pieces.append({"tris": moved, "style": "cut" if cut["kind"] == "cut" else "draft",
			"line_color": Color(0.35, 0.15, 0.6), "body_id": "", "replace": false})
	var dest: Vector3 = state["ref"] + offsets.back()
	var wave_tris := ctx.model.triangles(body) if ctx.model.has_body(body) else src
	ctx.view.present_draft(op, pieces, {"origin": dest, "tris": wave_tris, "is_new": false, "bodies": [body], "attach": "confirmed"})
	last_oid = oid
	state["last_vec"] = vec
	_end_commit()


func _whole_assemblies(targets: Array) -> Array:
	"""The assemblies every member of which is being copied, from outside (I47)."""
	var out := []
	if ctx.selection.context().begins_with("assembly:"): return out
	for b in targets:
		var aid: String = ctx.selection.assembly_of(b)
		if aid == "" or out.has(aid): continue
		if ctx.selection.members_of(aid).all(func(member): return targets.has(member)):
			out.append(aid)
	return out


func _amend_last_move(txt: String) -> bool:
	"""SketchUp's after-the-fact typing: a distance, an array count or a divide count."""
	if last_oid == "": return false
	var op := ctx.document.op(last_oid)
	if op.is_empty(): return false
	var vec := Vector3(op["vector"][0], op["vector"][1], op["vector"][2])
	var count: int = op.get("count", 1)
	var divide: bool = op.get("divide", false)
	var t := txt.strip_edges().to_lower()
	var parsed := parse_array_count(txt)
	if not parsed.is_empty():
		if not op["copy"]: return false
		count = parsed["count"]; divide = parsed["divide"]
	elif t.is_valid_float():
		# a new distance along the same direction (for an array this sets the spacing; for divide, the total)
		vec = vec.normalized() * absf(float(t))
	else:
		return false
	var body: String = op["cut"]["body"] if op.has("cut") else op["targets"][0]
	var was_copy: bool = op["copy"]
	ctx.document.remove(last_oid)
	copy = was_copy
	var memo: Dictionary = memo.get(op["id"], {})
	if memo.is_empty(): return true
	state = {"active": false, "body": body, "tris": memo["tris"], "ref": memo["ref"], "cut": memo.get("cut", {}), "unit": memo.get("unit", {"id": body, "kind": "board", "bodies": [body]})}
	commit_move(vec, count, divide, op["id"])
	return true
