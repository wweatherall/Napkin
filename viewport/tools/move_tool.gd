extends "res://tools/tool.gd"
## Move (M), SketchUp style: grab a point on a board (or a hole's wall: the hole), move, click or type a distance.
## Ctrl/Option toggles copy, Shift toggles mirror (the board flips across the plane halfway to the cursor).
## Arrows cycle axis lock -> plane lock -> free. After a copy: 5x / *5 for an array, /5 to spread copies;
## a plain number right after a move changes its distance.

var state := {}
var copy := false
var mirror := false
var last_oid := ""      # the move/copy you can still adjust by typing (distance, Nx, *N, /N)
var memo := {}          # move op id -> {"tris": geometry before the move, "ref": pick-up point}


func reset() -> void:
	state = {}
	copy = false
	mirror = false


func hint() -> String:
	return "Move: grab a point on a board, click or type a distance. Ctrl/Option = copy, Shift = mirror, arrows lock axis. After a copy: 5x or /5"


func busy() -> bool:
	return state.get("active", false) or last_oid != ""


func in_gesture() -> bool:
	return state.get("active", false)        # (after a move, typing amends it; that isn't a gesture)


func accepts(ch: String) -> bool:
	return super.accepts(ch) or ch.to_lower() == "x"


func mouse_moved(screen: Vector2) -> void:
	_move_move(screen)


func click(screen: Vector2) -> void:
	_move_click(screen)


func key(e: InputEventKey) -> bool:
	if e.keycode in [KEY_CTRL, KEY_ALT, KEY_SHIFT]:
		if e.keycode == KEY_SHIFT:
			mirror = not mirror            # Shift: mirror across the plane halfway to the cursor
		else:
			copy = not copy                # SketchUp: tap Ctrl (Option on a Mac) to toggle copy
		if state.get("active", false): _move_move(m._cursor_pos())
		m._update_vcb(); m._update_tip(m._cursor_pos())
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
			_move_move(m._cursor_pos())
			m._update_tip(m._cursor_pos())
			return true
	return false


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
			var side: float = signf(state["vec"][ax]) if absf(state["vec"][ax]) > 0.5 else state["face_sign"]
			var c: float
			if ax == state["face_ax"]:
				c = state["face_c"] + side * d
			else:
				c = state["hi"][ax] + d if side >= 0 else state["lo"][ax] - d
			commit_mirror_move(ax, c)
		return
	var tl := txt.to_lower()
	if tl.is_valid_float() and state["vec"].length() > 0.5:
		commit_move(state["vec"].normalized() * absf(float(tl)))


func vcb_label() -> String:
	return "Face to plane" if mirror else ("Copy distance" if copy else "Distance")


func vcb_value() -> String:
	if not state.get("active", false): return ""
	if mirror and state.get("mir_face", "") != "":
		return "%d" % absf((state["ref"] - state["mir_p"]).dot(state["mir_n"]))
	if mirror and state.has("mir_c"):
		return "%d" % _mirror_face_gap(state["mir_ax"], state["mir_c"])
	return "%d" % state["vec"].length()


func tip() -> String:
	if state.get("active", false) and mirror and state.get("mir_face", "") != "":
		return "Mirror%s across %s's face\ntype a distance to stand the plane off it" % [" + copy" if copy else "", state["mir_face"]]
	if state.get("active", false) and mirror and state.has("mir_c"):
		var g := _mirror_face_gap(state["mir_ax"], state["mir_c"])
		var col: String = ["red", "green", "blue"][state["mir_ax"]]
		return "Mirror%s (%s plane)\nface → plane  %d mm\nface → mirrored face  %d mm" % [" + copy" if copy else "", col, g, 2.0 * g]
	if state.get("active", false):
		var k: String = state.get("kind", "")
		return "%s  %d mm%s" % ["Copy +" if copy else "Move", state["vec"].length(), ("\n" + k) if k != "" else ""]
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
	var p := m.pick(m._cursor_pos())
	var b: String = p.get("body", "")
	if not p.get("hit", false) or b == "" or b == state["body"] or state.get("unit", {}).get("bodies", []).has(b): return {}
	return {"p": p["point"], "n": Main.clean_normal(p["normal"]), "body": b}


func _preview_mirror_move() -> void:
	var fp := _face_plane_under_cursor()
	state["mir_face"] = fp.get("body", "")
	if not fp.is_empty():
		_preview_mirror_plane(fp["p"], fp["n"])
		return
	var r := _mirror_axis_and_plane()
	var ax: int = r[0]; var c: float = r[1]
	state["mir_ax"] = ax; state["mir_c"] = c
	var ghost := Main._mirror_tris(state["tris"], ax, c)
	var lo: Vector3 = state["lo"]; var hi: Vector3 = state["hi"]
	for q in ghost: lo = lo.min(q); hi = hi.max(q)
	var u := (ax + 1) % 3; var v := (ax + 2) % 3
	var corners := PackedVector3Array()
	for uv in [[lo[u] - 60, lo[v] - 60], [hi[u] + 60, lo[v] - 60], [hi[u] + 60, hi[v] + 60], [lo[u] - 60, hi[v] + 60]]:
		var pt := Vector3.ZERO
		pt[ax] = c; pt[u] = uv[0]; pt[v] = uv[1]
		corners.append(pt)
	var pm := m.mat_plane.duplicate() as StandardMaterial3D
	pm.albedo_color = Main.AXIS_COLORS[ax]
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for q in [corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]]: st.add_vertex(Main.m2g(q))
	var mesh := m._tri_mesh(ghost, m.mat_draft)
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, st.commit_to_arrays())
	mesh.surface_set_material(1, pm)
	m.overlay.mesh = mesh
	var edge_col: Color = Main.AXIS_COLORS[ax]
	edge_col.a = 1.0
	var segs := Main.feature_edges(ghost)
	segs.append_array(PackedVector3Array([corners[0], corners[1], corners[1], corners[2], corners[2], corners[3], corners[3], corners[0]]))
	m.overlay_lines.mesh = m._lines(segs, edge_col.darkened(0.2)).mesh
	var landed: Vector3 = state["ref"]
	landed[ax] = 2.0 * c - landed[ax]
	m._show_marker({"hit": true, "point": landed})
	m._update_vcb()


func _preview_mirror_plane(pp: Vector3, n: Vector3) -> void:
	"""The ghost and plane for a plane at any angle (a snapped face)."""
	state["mir_p"] = pp; state["mir_n"] = n
	var ghost := Main.reflect_tris(state["tris"], pp, n)
	var lo: Vector3 = state["lo"]; var hi: Vector3 = state["hi"]
	for q in ghost: lo = lo.min(q); hi = hi.max(q)
	var bs := Main.plane_basis(n)
	var c := (lo + hi) * 0.5
	c -= n * (c - pp).dot(n)
	var r := (hi - lo).length() * 0.5 + 60.0
	var u: Vector3 = bs[0] * r; var v: Vector3 = bs[1] * r
	var corners := PackedVector3Array([c - u - v, c + u - v, c + u + v, c - u + v])
	var pm := m.mat_plane.duplicate() as StandardMaterial3D
	pm.albedo_color = Color(0.85, 0.35, 0.6, 0.3)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for q in [corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]]: st.add_vertex(Main.m2g(q))
	var mesh := m._tri_mesh(ghost, m.mat_draft)
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, st.commit_to_arrays())
	mesh.surface_set_material(1, pm)
	m.overlay.mesh = mesh
	var segs := Main.feature_edges(ghost)
	segs.append_array(PackedVector3Array([corners[0], corners[1], corners[1], corners[2], corners[2], corners[3], corners[3], corners[0]]))
	m.overlay_lines.mesh = m._lines(segs, Color(0.6, 0.2, 0.45)).mesh
	m._show_marker({"hit": true, "point": Main.reflect_point(state["ref"], pp, n)})
	m._update_vcb()


func commit_mirror_move(ax: int, c: float) -> void:
	var pt := Vector3.ZERO
	pt[ax] = c
	commit_mirror(pt, Main._axis_vec(ax))


func commit_mirror(pp: Vector3, n: Vector3) -> void:
	"""Mirror the grabbed board across the plane through pp with normal n (any angle)."""
	m.reject_note = ""
	var body: String = state["body"]
	m.counters["m"] += 1
	var oid := "m%d" % m.counters["m"]
	var targets: Array = state["unit"]["bodies"].duplicate() if state.get("unit", {}).get("kind", "") == "selection" else [body]
	var op := {"id": oid, "type": "mirror", "targets": targets, "plane": {"point": Main.arr3(pp), "normal": Main.arr3(n)}}
	var made: Array = []
	if copy:
		for b in targets:
			m.counters["b"] += 1
			made.append("b%d" % m.counters["b"])
		op["new_ids"] = made
		if m.context == "" and targets.all(func(b): return m.body_assembly.get(b, "") == ""):
			m.counters["a"] += 1
			op["group"] = "a%d" % m.counters["a"]
	else:
		op["replace"] = true
		made = targets.duplicate()
	m.ops.append(op)
	var root := Node3D.new()
	m.drafts_root.add_child(root); m.drafts[oid] = root
	var all := PackedVector3Array()
	for i in targets.size():
		var ghost := Main.reflect_tris(m.body_tris[targets[i]], pp, n)
		all.append_array(ghost)
		var mi := MeshInstance3D.new()
		mi.mesh = m._tri_mesh(ghost, m.mat_draft)
		mi.add_child(m._lines(Main.feature_edges(ghost), Color(0.6, 0.35, 0.0)))
		root.add_child(mi)
		var bid: String = made[i]
		m._add_collision(mi, "body_id", bid)
		m.body_tris[bid] = ghost
		m.body_verts[bid] = Main.unique_verts(ghost)
		m.body_edges[bid] = Main.feature_edges(ghost)
		if not copy:
			for node in m.bodies_root.find_children(targets[i], "MeshInstance3D", true, false): node.visible = false
		if m.test_mode:
			var blo := Vector3(INF, INF, INF); var bhi := -blo
			for q in ghost: blo = blo.min(q); bhi = bhi.max(q)
			m.draft_bboxes[bid] = [Main.arr3(blo), Main.arr3(bhi)]
	var landed := Main.reflect_point(state["ref"], pp, n)
	m._begin_wave(oid, landed, all, copy, made)
	for mi in root.get_children(): m._attach_wave(oid, mi, mi.get_child(0), Main.DEFAULT_BASE)
	last_oid = ""
	state["active"] = false
	if m.guides: m.guides.mesh = null
	m.overlay.mesh = null; m.overlay_lines.mesh = null
	m.marker.visible = false
	m._update_tip(m._cursor_pos())
	m.sync()


func _move_click(screen: Vector2) -> void:
	if not state.get("active", false):
		var p := m.snap(m.pick(screen), screen)
		if not p.get("hit", false) or p["body"] == "" or not m.body_tris.has(p["body"]): return
		last_oid = ""
		var tris: PackedVector3Array = m.body_tris[p["body"]]
		var unit := m.unit_of(p["body"])             # from outside: the whole assembly, or the array's row (I32)
		if m.selection.has(p["body"]) and m.selection.size() > 1:
			unit = {"id": p["body"], "kind": "selection", "bodies": m.selection.duplicate()}
		var cut := m._cut_at(p["body"], p["point"]) if unit["kind"] == "board" and not m.selection.has(p["body"]) else {}
		var cut_ref := {}
		if unit["kind"] != "board":
			tris = m.unit_tris(unit)
		if not cut.is_empty():                       # clicked a hole: move / copy the hole, not the board
			cut_ref = {"body": p["body"], "op": cut["op"], "kind": cut["kind"]}
			tris = m._cut_tris(p["body"], cut["op"])
		var lo := Vector3(INF, INF, INF); var hi := -lo
		for q in tris: lo = lo.min(q); hi = hi.max(q)
		var n: Vector3 = p["normal"]
		var fax := 0
		for i in 3:
			if absf(n[i]) > absf(n[fax]): fax = i
		state = {"active": true, "body": p["body"], "tris": tris, "ref": p["point"],
					  "vec": Vector3.ZERO, "lock": -1, "lock_mode": "free", "inferred": -1, "kind": "",
					  "count": 1, "divide": false, "lo": lo, "hi": hi,
					  "face_ax": fax, "face_c": snappedf(p["point"][fax], 0.01), "face_sign": signf(n[fax]),
					  "cut": cut_ref, "unit": unit}
	elif mirror and state.get("cut", {}).is_empty():
		if state.get("mir_face", "") != "": commit_mirror(state["mir_p"], state["mir_n"])
		else: commit_mirror_move(state["mir_ax"], state["mir_c"])
	else:
		commit_move(state["vec"])


func _move_move(screen: Vector2) -> void:
	if not state.get("active", false):
		var hp := m.pick(screen)
		m.overlay_lines.mesh = null
		m.overlay.mesh = null
		if hp.get("hit", false) and m.body_tris.has(hp["body"]):
			var hc := m._cut_at(hp["body"], hp["point"])
			if hc.is_empty():
				m.overlay.mesh = m._tri_mesh(m.body_tris[hp["body"]], m.mat_hover)
			else:
				var ht := m._cut_tris(hp["body"], hc["op"])
				m.overlay.mesh = m._tri_mesh(ht, m.mat_cut_hl)
				m.overlay_lines.mesh = m._lines(Main.feature_edges(ht), Color(0.35, 0.15, 0.6)).mesh
		return
	var ref: Vector3 = state["ref"]
	var body: String = state["body"]
	var moving_cut: bool = not state.get("cut", {}).is_empty()
	var mode: String = state.get("lock_mode", "free")
	var lax: int = state["lock"]
	var dest = null
	var kind := ""
	var guide_axis := -1
	var guide_plane := -1
	if mode == "axis":
		dest = infer.axis_dest(screen, ref, lax, body)
		kind = ["red", "green", "blue"][lax] + " axis (locked)"
		guide_axis = lax
	else:
		var plane_n := Main._axis_vec(lax) if mode == "plane" else Vector3(0, 0, 1)
		if mode == "plane": guide_plane = lax
		var pt := infer.point(screen, "" if moving_cut else body)   # a hole can snap to its own board
		if not pt.is_empty():
			dest = pt["point"]
			if mode == "plane":                       # stay on the locked plane
				dest = dest - plane_n * (dest - ref).dot(plane_n)
			kind = pt["kind"]
		else:
			var axes := [0, 1, 2] if mode == "free" else [(lax + 1) % 3, (lax + 2) % 3]
			var inf := infer.axis(screen, ref, axes, state.get("inferred", -1))
			state["inferred"] = inf
			if inf >= 0:
				dest = infer.axis_dest(screen, ref, inf, body)
				kind = "on " + ["red", "green", "blue"][inf] + " axis"
				guide_axis = inf
			else:
				var hit := m.pick(screen)
				if hit.get("hit", false) and hit["body"] != "" and hit["body"] != body and mode == "free":
					dest = hit["point"]                   # on another board's face
					var fn: Vector3 = hit["normal"]
					if m.grid_snap:
						var vec: Vector3 = dest - ref
						for i in 3:
							if absf(fn[i]) < 0.5: vec[i] = snappedf(vec[i], Main.GRID)
						dest = ref + vec
					kind = "on face"
				else:
					dest = infer.plane_dest(screen, ref, plane_n)
					kind = "free" if mode == "free" else ["green/blue", "red/blue", "red/green"][lax] + " plane (locked)"
	if dest == null: return
	state["vec"] = dest - ref
	state["kind"] = kind
	m._draw_guides(ref, guide_axis, guide_plane)
	if mirror and not moving_cut:
		_preview_mirror_move()
		return
	var mcol: Color = Main.SNAP_COLORS.get(kind, Color(0.35, 0.35, 0.4))
	m.marker.visible = true
	m.marker.position = Main.m2g(dest)
	(m.marker.mesh.material as StandardMaterial3D).albedo_color = mcol
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
		src = m.body_tris[state["body"]]              # copying from a row copies just that board
	for off in _move_offsets(state["vec"], state["count"], state["divide"], copy):
		for q in src: all.append(q + off)
	m.overlay.mesh = m._tri_mesh(all, m.mat_draft if state.get("cut", {}).is_empty() else m.mat_cut)
	m.overlay_lines.mesh = m._lines(Main.feature_edges(all), Color(0.6, 0.35, 0.0)).mesh
	m._update_vcb()


func commit_move(vec: Vector3, count := 1, divide := false, reuse_oid := "") -> void:
	if vec.length() < 0.5: return
	m.reject_note = ""
	if not state.get("cut", {}).is_empty():
		_commit_cut_move(vec, count, divide, reuse_oid)
		return
	var body: String = state.get("body", "")
	var unit: Dictionary = state.get("unit", {"kind": "board", "bodies": [body]})
	var targets: Array = unit["bodies"].duplicate() if unit["kind"] in ["selection", "assembly"] else [body]
	var whole := _whole_assemblies(targets) if copy else []
	if not whole.is_empty() and (count > 1 or divide):
		m._say_status(ASSEMBLY_ROW); return
	var oid := reuse_oid
	if oid == "":
		m.counters["mv"] += 1
		oid = "mv%d" % m.counters["mv"]
	var op := {"id": oid, "type": "move", "targets": targets, "selection": unit["kind"] in ["selection", "assembly"],
			   "vector": Main.arr3(vec), "copy": copy}
	if not whole.is_empty():                     # each wholly copied assembly comes out as a new one (I44)
		var groups := {}
		for aid in whole:
			m.counters["a"] += 1
			groups[aid] = "a%d" % m.counters["a"]
		op["groups"] = groups
	if not copy and m.context.begins_with("row:"):
		op["detach"] = true                          # inside an entered array a copy moves alone (I32)
	var offsets := _move_offsets(vec, count, divide, copy)
	var made := []
	if copy:
		op["count"] = count
		op["divide"] = divide
		for b in targets:
			for i in offsets.size():
				m.counters["b"] += 1
				made.append("b%d" % m.counters["b"])
		op["new_ids"] = made
	m.ops.append(op)
	var root := Node3D.new()
	m.drafts_root.add_child(root)
	m.drafts[oid] = root
	var all := PackedVector3Array()
	var src: PackedVector3Array = state["tris"]
	memo[oid] = {"tris": src, "ref": state["ref"], "unit": unit.duplicate(true)}
	var wave_bodies := made if copy else [body]
	var srcs := []
	for i in offsets.size(): srcs.append(m.body_tris[body] if copy and unit["kind"] != "board" else src)
	if copy and targets.size() > 1:
		var steps := offsets.duplicate()
		srcs = []; offsets = []
		for b in targets:
			for step in steps:
				srcs.append(m.body_tris[b]); offsets.append(step)
	if not copy and unit["kind"] != "board":       # the whole assembly / row moves: one draft per board
		wave_bodies = unit["bodies"]
		srcs = []; offsets = []
		for b in wave_bodies:
			srcs.append(m.body_tris.get(b, PackedVector3Array())); offsets.append(vec)
	for i in offsets.size():
		var moved := PackedVector3Array()
		for q in srcs[i]: moved.append(q + offsets[i])
		all.append_array(moved)
		var mi := MeshInstance3D.new()
		mi.mesh = m._tri_mesh(moved, m.mat_draft)
		var edges := m._lines(Main.feature_edges(moved), Color(0.6, 0.35, 0.0))
		mi.add_child(edges)
		root.add_child(mi)
		var bid: String = wave_bodies[i]
		m._add_collision(mi, "body_id", bid)
		m.body_tris[bid] = moved
		m.body_verts[bid] = Main.unique_verts(moved)
		m.body_edges[bid] = Main.feature_edges(moved)
		if m.test_mode:
			var lo := Vector3(INF, INF, INF); var hi := -lo
			for q in moved: lo = lo.min(q); hi = hi.max(q)
			m.draft_bboxes[bid] = [Main.arr3(lo), Main.arr3(hi)]
	if not copy:
		for b in wave_bodies:
			for n in m.bodies_root.find_children(b, "MeshInstance3D", true, false):
				n.visible = false        # it has left: hide the old spot until FreeCAD's mesh arrives
	var dest: Vector3 = state["ref"] + offsets[offsets.size() - 1]
	m._begin_wave(oid, dest, all, copy, wave_bodies)
	for i in root.get_child_count():
		var mi: MeshInstance3D = root.get_child(i)
		m._attach_wave(oid, mi, mi.get_child(0), Main.DEFAULT_BASE)
	last_oid = oid
	state["last_vec"] = vec
	if m.guides: m.guides.mesh = null
	state["active"] = false
	m.overlay.mesh = null; m.overlay_lines.mesh = null
	m.marker.visible = false
	m._update_tip(m._cursor_pos())
	m.sync()


func _commit_cut_move(vec: Vector3, count: int, divide: bool, reuse_oid: String) -> void:
	"""Move a hole, or copy it (FreeCAD makes the copies a Draft array of the cutter)."""
	var cut: Dictionary = state["cut"]
	var body: String = cut["body"]
	var oid := reuse_oid
	if oid == "":
		m.counters["mv"] += 1
		oid = "mv%d" % m.counters["mv"]
	var op := {"id": oid, "type": "move", "targets": [], "cut": {"body": body, "op": cut["op"]},
		"vector": Main.arr3(vec), "copy": copy}
	if copy:
		op["count"] = count
		op["divide"] = divide
	m.ops.append(op)
	var root := Node3D.new()
	m.drafts_root.add_child(root)
	m.drafts[oid] = root
	var src: PackedVector3Array = state["tris"]
	memo[oid] = {"tris": src, "ref": state["ref"], "cut": cut}
	var offsets := _move_offsets(vec, count, divide, copy)
	for off in offsets:
		var moved := PackedVector3Array()
		for q in src: moved.append(q + off)
		var mi := MeshInstance3D.new()
		mi.mesh = m._tri_mesh(moved, m.mat_cut if cut["kind"] == "cut" else m.mat_draft)
		mi.add_child(m._lines(Main.feature_edges(moved), Color(0.35, 0.15, 0.6)))
		root.add_child(mi)
	var dest: Vector3 = state["ref"] + offsets[offsets.size() - 1]
	m._begin_wave(oid, dest, m.body_tris.get(body, src), false, body)
	for mi in m.bodies_root.find_children(body, "MeshInstance3D", true, false):
		m._attach_wave(oid, mi, mi.get_child(mi.get_child_count() - 1), m._base_of(mi))
	last_oid = oid
	state["last_vec"] = vec
	if m.guides: m.guides.mesh = null
	state["active"] = false
	m.overlay.mesh = null
	m.overlay_lines.mesh = null
	m.marker.visible = false
	m._update_tip(m._cursor_pos())
	m.sync()


const ASSEMBLY_ROW := "Copying an assembly into a row isn't built yet: copy it once"


func _whole_assemblies(targets: Array) -> Array:
	"""The assemblies every member of which is being copied, from outside (I44)."""
	var out := []
	if m.context != "": return out
	for b in targets:
		var aid: String = m.body_assembly.get(b, "")
		if aid == "" or out.has(aid): continue
		var all_in := true
		for other in m.body_assembly:
			if m.body_assembly[other] == aid and not targets.has(other): all_in = false
		if all_in: out.append(aid)
	return out


func _amend_last_move(txt: String) -> bool:
	"""SketchUp's after-the-fact typing: a distance, Nx / xN / *N (array), or /N (divide)."""
	if last_oid == "": return false
	var op: Dictionary = {}
	for o in m.ops:
		if o["id"] == last_oid: op = o
	if op.is_empty(): return false
	var vec := Vector3(op["vector"][0], op["vector"][1], op["vector"][2])
	var count: int = op.get("count", 1)
	var divide: bool = op.get("divide", false)
	var t := txt.strip_edges().to_lower()
	if t.begins_with("/") and t.substr(1).is_valid_int():
		if not op["copy"]: return false
		count = maxi(1, int(t.substr(1))); divide = true
	elif (t.ends_with("x") and t.left(-1).is_valid_int()) or ((t.begins_with("x") or t.begins_with("*")) and t.substr(1).is_valid_int()):
		if not op["copy"]: return false
		count = maxi(1, int(t.trim_suffix("x").trim_prefix("x").trim_prefix("*"))); divide = false
	elif t.is_valid_float():
		# a new distance along the same direction (for an array this sets the spacing; for divide, the total)
		vec = vec.normalized() * absf(float(t))
	else:
		return false
	if op.has("groups") and (count > 1 or divide):
		m._say_status(ASSEMBLY_ROW); return true   # the single copy stays as it is
	var body: String = op["cut"]["body"] if op.has("cut") else op["targets"][0]
	var was_copy: bool = op["copy"]
	m.remove_op(last_oid)
	copy = was_copy
	var memo: Dictionary = memo.get(op["id"], {})
	if memo.is_empty(): return true
	state = {"active": false, "body": body, "tris": memo["tris"], "ref": memo["ref"], "cut": memo.get("cut", {}), "unit": memo.get("unit", {"id": body, "kind": "board", "bodies": [body]})}
	commit_move(vec, count, divide, op["id"])
	return true
