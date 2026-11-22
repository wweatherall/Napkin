extends "res://tools/tool.gd"
## Push/Pull (P): click a face, rectangle or circle, move, then click or type a distance + Return (minus = cut).

const TOOL := {"id": "push", "label": "Push/Pull", "tip": "Push/Pull (P)", "key": KEY_P, "order": 40, "show_links": true}   # the toolbar, the Tools menu and the key (tool_registry.gd)

var state := {}
var face_highlight: MeshInstance3D
const FIT_MODES := ["Butt to plane", "Slice at plane", "Fully reach plane"]   # I41: ⌥ Option cycles them
var hover := {}          # the face, rectangle or circle under the cursor


func reset() -> void:
	state = {}
	press_reset()
	if is_instance_valid(face_highlight): face_highlight.mesh = null


func hint() -> String:
	return "Push/Pull: click a face, rectangle or circle, move, then click or type a distance + Enter (minus = cut)"


func busy() -> bool:
	return state.get("active", false)


func mouse_moved(screen: Vector2) -> void:
	press_moved(screen)
	if state.get("active", false):
		_push_drag(screen)
	else:
		_push_hover(screen)


func click(screen: Vector2) -> void:
	if not state.get("active", false):
		_push_hover(screen)
		if hover.is_empty(): return
		if m.edit_blocked(hover.get("body", "") if hover.get("rect", "") == "" else m.rects[hover["rect"]]["on"]): return
		state = hover.duplicate()
		state["active"] = true
		state["dist"] = 0.0
		state["depths"] = _depths_behind()
		press_started(screen)
	else:
		_finish_push()


func release(screen: Vector2) -> void:
	# a press-and-drag ends here; a click goes on until the next click (I43)
	if press_released().get("drag", false) and state.get("active", false):
		_push_drag(screen)
		_finish_push()


func typed(txt: String) -> void:
	if state.get("active", false):
		commit_push(float(txt))


func vcb_value() -> String:
	return DISTANCE_DISPLAY_FORMAT % state["dist"] if state.get("active", false) else ""


func tip() -> String:
	if state.has("edge_fit"):
		var fit: Dictionary = state.edge_fit
		var face: String = ["Left","Right","Front","Back","Bottom","Top"][fit.face]
		return "%s → %s face · %s · ⌥ end%s" % [state.edge_label, face, FIT_MODES[state.get("fit_mode", 0)],
				" · Tab face" if state.options.size() > 1 else ""]
	return "to " + state["snap"] if state.get("active", false) and state.get("snap", "") != "" else ""


func _depths_behind() -> Array:
	"""How far behind the pushed face each face of the same board lies (the back face, a pocket's floor), as
	negative push distances, deepest last. Measured straight through the board, so hidden faces count here."""
	var bid: String = state["body"] if state.get("rect", "") == "" else m.rects[state["rect"]]["on"]
	var tris: PackedVector3Array = m.body_tris.get(bid, PackedVector3Array())
	var n: Vector3 = state["n"]
	var from: Vector3 = state["anchor"] - n * 0.01
	var found := {}
	for i in range(0, tris.size(), 3):
		var hit = Geometry3D.ray_intersects_triangle(from, -n, tris[i], tris[i + 1], tris[i + 2])
		if hit == null: continue
		var t: float = clean_pointer_distance((hit - state["anchor"]).dot(-n))
		if t >= GEOMETRY_TOLERANCE_MM: found[-t] = true
	var out := found.keys()
	out.sort()
	out.reverse()            # nearest first: -6 (a pocket floor), then -18 (the back face)
	return out


func _snap_to_face_behind(screen: Vector2) -> void:
	"""Pushing in: within a few pixels of a face behind (the back face for a through-hole), go exactly there.
	Only nearer to it than to the start or the next face along (I45): on a thin board the snap doesn't swallow
	the whole thickness, so the first part of a push in follows the cursor."""
	var depths: Array = state.get("depths", [])
	if depths.is_empty() or state["dist"] >= 0.0: return
	var screen_at := func(d: float) -> Vector2: return m.cam.unproject_position(Main.m2g(state["anchor"] + state["n"] * d))
	var here: Vector2 = screen_at.call(state["dist"])
	var stops := [0.0] + depths                  # the start, then the faces behind, nearest first
	for k in depths.size():
		var c: float = depths[k]
		var at: Vector3 = state["anchor"] + state["n"] * c
		var p: Vector2 = screen_at.call(c)
		var radius := Main.SNAP_PX
		radius = minf(radius, 0.5 * p.distance_to(screen_at.call(stops[k])))
		if k + 1 < depths.size(): radius = minf(radius, 0.5 * p.distance_to(screen_at.call(depths[k + 1])))
		if p.distance_to(here) < radius:
			state["dist"] = c
			state["snap"] = "back face" if k == depths.size() - 1 else "face behind"
			m._show_marker({"hit": true, "point": at, "snap": state["snap"]})
			return


func _push_hover(screen: Vector2) -> void:
	hover = {}
	m.overlay.mesh = null
	var p := m.pick(screen)
	m.marker.visible = false
	if not p.get("hit", false) or p.get("ground", false): return
	var tris := PackedVector3Array()
	if p["rect"] != "":
		tris = m.rects[p["rect"]]["tris"]
	elif p["body"] != "":
		tris = coplanar_region(p["body"], p["normal"], p["point"])
	if tris.is_empty(): return
	hover = {"rect": p["rect"], "body": p["body"], "n": p["normal"], "anchor": p["point"], "tris": tris}
	m.overlay.mesh = m._tri_mesh(tris, m.mat_hover)


func coplanar_region(bid: String, n: Vector3, p: Vector3) -> PackedVector3Array:
	var all: PackedVector3Array = m.body_tris.get(bid, PackedVector3Array())
	var cand := []
	for i in range(0, all.size(), 3):
		var a := all[i]; var b := all[i + 1]; var c := all[i + 2]
		var tn := (b - a).cross(c - a).normalized()
		if absf(tn.dot(n)) > 0.999 and absf((a - p).dot(n)) < GEOMETRY_TOLERANCE_MM:
			cand.append([a, b, c])
	if cand.is_empty(): return PackedVector3Array()
	# flood fill from the triangle under the point, across shared edges
	var start := 0
	for i in cand.size():
		if _in_tri(p, cand[i][0], cand[i][1], cand[i][2]): start = i; break
	var by_edge := {}
	for i in cand.size():
		for e in [[0, 1], [1, 2], [2, 0]]:
			var k := Main._ekey(cand[i][e[0]], cand[i][e[1]])
			if not by_edge.has(k): by_edge[k] = []
			by_edge[k].append(i)
	var seen := {start: true}
	var stack := [start]
	while not stack.is_empty():
		var i: int = stack.pop_back()
		for e in [[0, 1], [1, 2], [2, 0]]:
			for j in by_edge[Main._ekey(cand[i][e[0]], cand[i][e[1]])]:
				if not seen.has(j): seen[j] = true; stack.append(j)
	var out := PackedVector3Array()
	for i in seen: out.append_array(PackedVector3Array(cand[i]))
	return out


static func _in_tri(p: Vector3, a: Vector3, b: Vector3, c: Vector3) -> bool:
	var v0 := c - a; var v1 := b - a; var v2 := p - a
	var d00 := v0.dot(v0); var d01 := v0.dot(v1); var d11 := v1.dot(v1)
	var d20 := v2.dot(v0); var d21 := v2.dot(v1)
	var den := d00 * d11 - d01 * d01
	if absf(den) < 1e-12: return false
	var v := (d11 * d20 - d01 * d21) / den
	var w := (d00 * d21 - d01 * d20) / den
	return v >= -1e-4 and w >= -1e-4 and v + w <= 1.0001


func _push_drag(screen: Vector2) -> void:
	var a := Main.m2g(state["anchor"])
	var n := Vector3(state["n"].x, state["n"].z, -state["n"].y)
	var o := m.cam.project_ray_origin(screen); var d := m.cam.project_ray_normal(screen)
	var w0 := a - o
	var bb := n.dot(d); var cc := d.dot(d); var dd := n.dot(w0); var ee := d.dot(w0)
	var den := n.dot(n) * cc - bb * bb
	if absf(den) < 1e-9: return
	var s := (bb * ee - cc * dd) / den
	state["dist"] = roundf(s * 1000.0)
	state["snap"] = ""
	# push to a point (Q16): over a corner, midpoint or edge of any board, the face goes to that point's level
	var pt := infer.point(screen, "", {}, false, {"n": state["n"], "p": state["anchor"]})
	m.marker.visible = false
	if not pt.is_empty():
		state["dist"] = clean_pointer_distance((pt["point"] - state["anchor"]).dot(state["n"]))
		state["snap"] = pt["kind"]
		m._show_marker({"hit": true, "point": pt["point"], "snap": pt["kind"]})
	else:
		_snap_to_face_behind(screen)
	_edge_inference(pt, screen)
	_preview_push(state["dist"])
	m._update_vcb()


static func _vec(a: Array) -> Vector3:
	return Vector3(a[0],a[1],a[2])


func _edge_inference(pt: Dictionary, screen: Vector2) -> void:
	var previous: Dictionary = state.get("edge_fit", {})
	state.erase("edge_fit")
	if is_instance_valid(face_highlight): face_highlight.mesh = null
	var body: String = pt.get("body","")
	if pt.get("kind","") not in ["on edge","midpoint","endpoint"]:
		var hit := m.pick(screen)
		if hit.get("body","") != "": state["last_hover"] = hit
		if not pt.is_empty() or hit.get("body","") == "": return
		body = hit.body
		pt = hit
	if body == state.body or not m.stock_frames.has(body) or m.stock_frames[body].fitted: return
	var source_size := 0.0
	if state.rect != "":
		# Plane-fit stock dimensions describe rectangles. Circle pushes still use point/back-face inference.
		if m.rects[state.rect].get("kind", "rect") == "circle": return
		if m.rects[state.rect].on != "" and not (m.new_board and state.dist > 0): return
	else:
		if not m.stock_frames.has(state.body) or m.stock_frames[state.body].fitted: return
		var src: Dictionary = m.stock_frames[state.body]
		for i in 3:
			if absf(_vec(src.axes[i]).dot(state.n)) > 0.9999: source_size = src.sizes[i]
		if source_size <= 0: return
	var target: Dictionary = m.stock_frames[body]
	var origin := _vec(target.origin)
	var edge_point: Vector3 = pt.get("edge_point",pt.point)
	var push: Vector3 = state.n
	if state.rect != "" and state.dist < 0: push = -push
	var options := []
	for i in 3:
		var normal := _vec(target.axes[i])
		var denom := normal.dot(push)
		if absf(denom) < 0.00001: continue
		for side in 2:
			var plane_point := origin + normal * float(target.sizes[i]) * side
			if pt.has("normal"):
				var face_normal := normal if side else -normal
				if face_normal.dot(pt.normal) < 0.999: continue
			elif absf(normal.dot(edge_point-plane_point)) > 0.002: continue
			var depth := INF
			var far := -INF
			for corner in state.tris:
				depth = minf(depth,normal.dot(plane_point-corner)/denom)
				far = maxf(far,normal.dot(plane_point-corner)/denom)
			if depth + source_size <= 0.001 or absf(depth) < GEOMETRY_TOLERANCE_MM: continue
			var outward := normal if side else -normal
			var last: Dictionary = state.get("last_hover",{})
			var hovered: bool = last.get("body","") == body and outward.dot(last.normal) > 0.999
			options.append({"face":2*i+side,"distance":depth*push.dot(state.n),"far":far*push.dot(state.n),"normal":outward,
					"plane_point":plane_point,"plane_normal":normal,"push":push,"score":snappedf(absf(denom),0.001),"hovered":hovered})
	if options.is_empty(): return
	options.sort_custom(func(a,b):
		if a.score != b.score: return a.score > b.score
		if a.hovered != b.hovered: return a.hovered
		return a.face < b.face)
	var choice := 0
	var faces := options.map(func(option): return option.face)
	faces.sort()
	if previous.get("target_body","") == body and state.get("edge_faces",[]) == faces:
		for i in options.size():
			if options[i].face == previous.face: choice = i
	state["edge_faces"] = faces
	state["options"] = options
	state["edge_body"] = body
	state["edge_label"] = target.label
	state["edge_point"] = edge_point
	state["edge_screen"] = screen
	_choose_face(choice)


func _choose_face(index: int) -> void:
	var option: Dictionary = state.options[index]
	state["choice"] = index
	var mode: int = state.get("fit_mode", 0)
	state["dist"] = option.far if mode == 2 else option.distance      # Fully reach: square at the last contact
	state["edge_fit"] = {"target_body":state.edge_body,"face":option.face,"fit_mode":mode}
	if not is_instance_valid(face_highlight):
		face_highlight = MeshInstance3D.new()
		m.add_child(face_highlight)
	var triangles := coplanar_region(state.edge_body,option.normal,state.edge_point)
	face_highlight.mesh = m._tri_mesh(triangles,m.mat_hover)


func key(e: InputEventKey) -> bool:
	"""Pushing into a face (I40, I41): Tab switches the face, ⌥ Option the end condition (it holds for this push)."""
	if e.keycode not in [KEY_TAB, KEY_ALT] or not state.has("edge_fit"): return false
	if e.keycode == KEY_ALT:
		state["fit_mode"] = (state.get("fit_mode", 0) + 1) % FIT_MODES.size()
		_choose_face(state.choice)
	else:
		_choose_face((state.choice+1)%state.options.size())
	_preview_push(state.dist)
	m._update_vcb()
	m._update_tip(state.edge_screen)
	return true


func _push_shape(d: float) -> PackedVector3Array:
	"""What the push makes: a prism of d, or, sliced at a face's plane (I41), each corner run to that plane."""
	if state.get("edge_fit", {}).get("fit_mode", 0) == 1 and state.has("options"):
		var o: Dictionary = state.options[state.choice]
		var pp: Vector3 = o.plane_point; var pn: Vector3 = o.plane_normal; var push: Vector3 = o.push
		var denom := pn.dot(push)
		return Main.prism_by(state["tris"], func(p: Vector3) -> Vector3: return push * (pn.dot(pp - p) / denom))
	return Main.prism(state["tris"], state["n"], d)


func _preview_push(d: float) -> void:
	if absf(d) < GEOMETRY_TOLERANCE_MM:
		m.overlay.mesh = m._tri_mesh(state["tris"], m.mat_hover); m.overlay_lines.mesh = null; return
	var pr := _push_shape(d)
	m.overlay.mesh = m._tri_mesh(pr, m.mat_cut if d < 0 else m.mat_draft)
	m.overlay_lines.mesh = m._lines(Main.feature_edges(pr), Color(0.6, 0.35, 0.0)).mesh


func _finish_push() -> void:
	if not pointer_distance_ok(state["dist"], state.get("snap", "") != "" or state.has("edge_fit")): return
	commit_push(state["dist"], state.get("edge_fit", {}))


func commit_push(d: float, edge_fit := {}) -> void:
	if absf(d) < GEOMETRY_TOLERANCE_MM: return
	m.reject_note = ""
	m.counters["pp"] += 1
	var oid := "pp%d" % m.counters["pp"]
	var op := {"id": oid, "type": "push_pull", "distance": d}
	var on := ""
	if state["rect"] != "":
		op["target"] = {"rect": state["rect"]}
		on = m.rects[state["rect"]]["on"]
	else:
		op["target"] = {"face": {"body": state["body"], "normal": Main.arr3(state["n"]), "point": Main.arr3(state["anchor"])}}
		on = state["body"]
	var depths: Array = state.get("depths", [])
	if d < 0 and not depths.is_empty() and absf(d - float(depths.back())) < 0.01:
		op["through"] = true        # to the opposite face: FreeCAD keeps it through if the board changes (I24)
	var new_id := ""
	# a rectangle becomes its own board (free, or on a face with "new board" on);
	# pushing a body's own face always edits that body, like SketchUp
	if state["rect"] != "" and (on == "" or (d > 0 and m.new_board)):
		m.counters["b"] += 1
		new_id = "b%d" % m.counters["b"]
		op["body"] = new_id
		if m.context_assembly() != "": op["assembly"] = m.context_assembly()   # drawn inside: it joins (T20)
	if m.force_reject_next and op["target"].has("rect"):
		op["target"] = {"rect": "r_missing"}      # test hook only: guarantees FreeCAD rejects it
		m.force_reject_next = false
	if not edge_fit.is_empty():
		op["edge_fit"] = edge_fit.duplicate()
	elif state.rect == "" and m.stock_frames.has(on) and not m.stock_frames[on].fitted:
		op["resize_stock"] = true
	m.ops.append(op)
	var end_point: Vector3 = state["anchor"] + state["n"] * d   # on the moved face, under the cursor's axis
	var pr := _push_shape(d)
	var nodes := _add_push_draft(op, pr, d, new_id)
	if m.test_mode and new_id != "":
		var lo := Vector3(INF, INF, INF); var hi := -lo
		for q in pr: lo = lo.min(q); hi = hi.max(q)
		m.draft_bboxes[new_id] = [Main.arr3(lo), Main.arr3(hi)]
	# the wave starts now, before FreeCAD has answered
	if new_id != "":
		m._begin_wave(oid, end_point, pr, true, new_id)
		m._attach_wave(oid, nodes[0], nodes[1], Main.DEFAULT_BASE)
	else:
		m._begin_wave(oid, end_point, m.body_tris.get(on, pr), false, on)
		for mi in m.bodies_root.find_children(on, "MeshInstance3D", true, false):
			m._attach_wave(oid, mi, mi.get_child(mi.get_child_count() - 1), m._base_of(mi))
	if state["rect"] != "" and m.drafts.has(state["rect"]):
		m.drafts[state["rect"]].queue_free(); m.drafts.erase(state["rect"])
	reset()
	m.overlay.mesh = null; m.overlay_lines.mesh = null
	m.marker.visible = false
	m.sync()


func _add_push_draft(op: Dictionary, pr: PackedVector3Array, d: float, new_id: String) -> Array:
	var mi := MeshInstance3D.new()
	mi.mesh = m._tri_mesh(pr, m.mat_cut if d < 0 else m.mat_draft)
	var edges := m._lines(Main.feature_edges(pr), Color(0.6, 0.35, 0.0))
	mi.add_child(edges)
	m.drafts_root.add_child(mi)
	m.drafts[op["id"]] = mi
	if new_id != "":
		m._add_collision(mi, "body_id", new_id)
		m.body_tris[new_id] = pr                     # lets you keep working on a draft board
		m.body_verts[new_id] = Main.unique_verts(pr)
		m.body_edges[new_id] = Main.feature_edges(pr)
	return [mi, edges]
