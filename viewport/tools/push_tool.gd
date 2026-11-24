extends "res://tools/tool.gd"
## Push/Pull (P): click a face, rectangle or circle, move, then click or type a distance + Return (minus = cut).

const TOOL := {"id": "push", "label": "Push/Pull", "tip": "Push/Pull (P)", "key": KEY_P, "order": 40, "show_links": true}   # the toolbar, the Tools menu and the key (tool_registry.gd)

var state := {}
const FIT_MODES := ["Butt to plane", "Slice at plane", "Fully reach plane"]   # I41: ⌥ Option cycles them
var hover := {}          # the face, rectangle or circle under the cursor


func reset() -> void:
	state = {}
	press_reset()
	ctx.view.clear_face_highlight()


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
		if ctx.selection.edit_blocked(hover.get("body", "") if hover.get("rect", "") == "" else ctx.model.profile(hover["rect"]).on): return
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
	return ctx.ui.format_length(state["dist"]) if state.get("active", false) else ""


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
	var bid: String = state["body"] if state.get("rect", "") == "" else ctx.model.profile(state["rect"]).on
	var tris: PackedVector3Array = ctx.model.triangles(bid)
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
	var screen_at := func(d: float) -> Vector2: return ctx.pick.project(state["anchor"] + state["n"] * d).screen
	var here: Vector2 = screen_at.call(state["dist"])
	var stops := [0.0] + depths                  # the start, then the faces behind, nearest first
	for k in depths.size():
		var c: float = depths[k]
		var at: Vector3 = state["anchor"] + state["n"] * c
		var p: Vector2 = screen_at.call(c)
		var radius := ctx.pick.snap_radius()
		radius = minf(radius, 0.5 * p.distance_to(screen_at.call(stops[k])))
		if k + 1 < depths.size(): radius = minf(radius, 0.5 * p.distance_to(screen_at.call(depths[k + 1])))
		if p.distance_to(here) < radius:
			state["dist"] = c
			state["snap"] = "back face" if k == depths.size() - 1 else "face behind"
			ctx.view.marker({"hit": true, "point": at, "snap": state["snap"]})
			return


func _push_hover(screen: Vector2) -> void:
	hover = {}
	ctx.view.clear_preview()
	var p := ctx.pick.hit(screen)
	ctx.view.hide_marker()
	if not p.get("hit", false): return
	var tris := PackedVector3Array()
	var on: String = p.body
	if p["rect"] != "":
		var profile := ctx.model.profile(p.rect)
		tris = profile.tris
		on = profile.on
	elif p["body"] != "":
		tris = coplanar_region(p["body"], p["normal"], p["point"])
	var region: Dictionary = ctx.model.drawn_region(tris, on, p.normal, p.point)
	if not region.is_empty(): tris = region.tris
	if tris.is_empty(): return
	hover = {"rect": p["rect"], "body": p["body"], "n": p["normal"], "anchor": p["point"], "tris": tris}
	if not region.is_empty(): hover["region"] = region
	ctx.view.preview(tris, "hover")


func coplanar_region(bid: String, n: Vector3, p: Vector3) -> PackedVector3Array:
	var all: PackedVector3Array = ctx.model.triangles(bid)
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
			var k := Geo.edge_key(cand[i][e[0]], cand[i][e[1]])
			if not by_edge.has(k): by_edge[k] = []
			by_edge[k].append(i)
	var seen := {start: true}
	var stack := [start]
	while not stack.is_empty():
		var i: int = stack.pop_back()
		for e in [[0, 1], [1, 2], [2, 0]]:
			for j in by_edge[Geo.edge_key(cand[i][e[0]], cand[i][e[1]])]:
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
	var ray := ctx.pick.ray(screen)
	var n: Vector3 = state.n
	var d: Vector3 = ray.direction
	var w0: Vector3 = state.anchor - ray.origin
	var bb := n.dot(d); var cc := d.dot(d); var dd := n.dot(w0); var ee := d.dot(w0)
	var den := n.dot(n) * cc - bb * bb
	if absf(den) < 1e-9: return
	var s := (bb * ee - cc * dd) / den
	state["dist"] = roundf(s)
	state["snap"] = ""
	# push to a point (Q16): over a corner, midpoint or edge of any board, the face goes to that point's level
	var pt := ctx.pick.point(screen, "", {}, false, {"n": state["n"], "p": state["anchor"]})
	ctx.view.hide_marker()
	if not pt.is_empty():
		state["dist"] = clean_pointer_distance((pt["point"] - state["anchor"]).dot(state["n"]))
		state["snap"] = pt["kind"]
		ctx.view.marker({"hit": true, "point": pt["point"], "snap": pt["kind"]})
	else:
		_snap_to_face_behind(screen)
	_edge_inference(pt, screen)
	_preview_push(state["dist"])
	ctx.ui.refresh_measurements()


static func _vec(a: Array) -> Vector3:
	return Vector3(a[0],a[1],a[2])


static func _target_face_plane(target: Dictionary, face: int) -> Dictionary:
	var fe = target.get("fitted_end", null)
	if fe is Dictionary and int(fe.get("face", -1)) == face:
		return {"point": _vec(fe.point), "normal": _vec(fe.normal)}
	var i := floori(face / 2.0)
	var axis_n := _vec(target.axes[i])
	var side := face % 2
	return {"point": _vec(target.origin) + axis_n * float(target.sizes[i]) * side, "normal": axis_n if side else -axis_n}


func _edge_inference(pt: Dictionary, screen: Vector2) -> void:
	if state.has("region"): return     # a region push must not resize an entire stock face
	var previous: Dictionary = state.get("edge_fit", {})
	state.erase("edge_fit")
	ctx.view.clear_face_highlight()
	var body: String = pt.get("body","")
	if pt.get("kind","") not in ["on edge","midpoint","endpoint"]:
		var hit := ctx.pick.hit(screen)
		if hit.get("body","") != "": state["last_hover"] = hit
		if not pt.is_empty() or hit.get("body","") == "": return
		body = hit.body
		pt = hit
	var target := ctx.model.stock_frame(body)
	if body == state.body or target.is_empty(): return
	var source_size := 0.0
	if state.rect != "":
		# Plane-fit stock dimensions describe rectangles. Circle pushes still use point/back-face inference.
		var profile := ctx.model.profile(state.rect)
		if profile.get("kind", "rect") != "rect": return
		if profile.on != "" and not (ctx.ui.new_board() and state.dist > 0): return
	else:
		var src := ctx.model.stock_frame(state.body)
		if src.is_empty() or src.fitted: return
		for i in 3:
			if absf(_vec(src.axes[i]).dot(state.n)) > 0.9999: source_size = src.sizes[i]
		if source_size <= 0: return
	var edge_point: Vector3 = pt.get("edge_point",pt.point)
	var push: Vector3 = state.n
	if state.rect != "" and state.dist < 0: push = -push
	var options := []
	for face in 6:
		var plane := _target_face_plane(target, face)
		var outward: Vector3 = plane.normal
		var plane_point: Vector3 = plane.point
		var denom := outward.dot(push)
		if absf(denom) < 0.00001: continue
		if pt.has("normal"):
			if outward.dot(pt.normal) < 0.999: continue
		elif absf(outward.dot(edge_point - plane_point)) > 0.002: continue
		var depth := INF
		var far := -INF
		for corner in state.tris:
			depth = minf(depth, outward.dot(plane_point - corner) / denom)
			far = maxf(far, outward.dot(plane_point - corner) / denom)
		if depth + source_size <= 0.001 or absf(depth) < GEOMETRY_TOLERANCE_MM: continue
		var last: Dictionary = state.get("last_hover",{})
		var hovered: bool = last.get("body","") == body and outward.dot(last.normal) > 0.999
		options.append({"face":face,"distance":depth*push.dot(state.n),"far":far*push.dot(state.n),"normal":outward,
				"plane_point":plane_point,"plane_normal":outward,"push":push,"score":snappedf(absf(denom),0.001),"hovered":hovered})
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
	var triangles := coplanar_region(state.edge_body,option.normal,state.edge_point)
	ctx.view.face_highlight(triangles)


func key(e: InputEventKey) -> bool:
	"""Pushing into a face (I40, I41): Tab switches the face, ⌥ Option the end condition (it holds for this push)."""
	if e.keycode not in [KEY_TAB, KEY_ALT] or not state.has("edge_fit"): return false
	if e.keycode == KEY_ALT:
		state["fit_mode"] = (state.get("fit_mode", 0) + 1) % FIT_MODES.size()
		_choose_face(state.choice)
	else:
		_choose_face((state.choice+1)%state.options.size())
	_preview_push(state.dist)
	ctx.ui.refresh_measurements()
	ctx.ui.refresh_tip(state.edge_screen)
	return true


func _push_shape(d: float) -> PackedVector3Array:
	"""What the push makes: a prism of d, or, sliced at a face's plane (I41), each corner run to that plane."""
	if state.get("edge_fit", {}).get("fit_mode", 0) == 1 and state.has("options"):
		var o: Dictionary = state.options[state.choice]
		var pp: Vector3 = o.plane_point; var pn: Vector3 = o.plane_normal; var push: Vector3 = o.push
		var denom := pn.dot(push)
		return Geo.prism_by(state["tris"], func(p: Vector3) -> Vector3: return push * (pn.dot(pp - p) / denom))
	return Geo.prism(state["tris"], state["n"], d)


func _preview_push(d: float) -> void:
	if absf(d) < GEOMETRY_TOLERANCE_MM:
		ctx.view.preview(state.tris, "hover")
		return
	var pr := _push_shape(d)
	ctx.view.preview(pr, "cut" if d < 0 else "draft", Geo.feature_edges(pr))


func _finish_push() -> void:
	var snap: String = state.get("snap", "")
	if not pointer_distance_ok(state["dist"], snap != "" or state.has("edge_fit")): return
	commit_push(state["dist"], state.get("edge_fit", {}), snap == "face behind")


func commit_push(d: float, edge_fit := {}, snapped_to_floor := false) -> void:
	if absf(d) < GEOMETRY_TOLERANCE_MM: return
	ctx.ui.clear_rejection()
	var oid := ctx.document.next_id("pp")
	var op := {"id": oid, "type": "push_pull", "distance": d}
	var on := ""
	if state["rect"] != "":
		op["target"] = {"rect": state["rect"]}
		on = ctx.model.profile(state["rect"]).on
	else:
		op["target"] = {"face": {"body": state["body"], "normal": Geo.arr3(state["n"]), "point": Geo.arr3(state["anchor"])}}
		on = state["body"]
	if state.has("region"):
		var r: Dictionary = state.region
		var array3 := func(v: Vector3) -> Array: return [v.x, v.y, v.z]
		op.target["region"] = {"outline": Array(r.outline).map(array3),
			"holes": r.holes.map(func(h): return Array(h).map(array3)), "lines": r.lines,
			"normal": array3.call(state.n)}
		if on == "": op.target.erase("face")
	var depths: Array = state.get("depths", [])
	if d < 0 and not depths.is_empty() and absf(d - float(depths.back())) < 0.01:
		op["through"] = true        # to the opposite face: FreeCAD keeps it through if the board changes (I24)
	var new_id := ""
	# a rectangle becomes its own board (free, or on a face with "new board" on);
	# pushing a body's own face always edits that body, like SketchUp
	if (state["rect"] != "" or state.has("region")) and (on == "" or (d > 0 and ctx.ui.new_board())):
		new_id = ctx.document.next_id("b")
		op["body"] = new_id
		if ctx.selection.context_assembly() != "": op["assembly"] = ctx.selection.context_assembly()   # drawn inside: it joins (T20)
	if not edge_fit.is_empty():
		op["edge_fit"] = edge_fit.duplicate()
	elif not state.has("region") and state.rect == "" and not ctx.model.stock_frame(on).get("fitted", true):
		op["resize_stock"] = true
	if snapped_to_floor and d < 0 and on != "" and (state.rect != "" or state.has("region")) \
			and not (op.has("through") or op.has("body") or op.has("edge_fit") or op.has("resize_stock")):
		op["to_face"] = {"normal": Geo.arr3(state.n), "point": Geo.arr3(state.anchor + state.n * d)}
	ctx.document.append(op)
	var pr := _push_shape(d)
	var piece := {"tris": pr, "style": "cut" if d < 0 else "draft", "line_color": Color(0.6, 0.35, 0),
		"body_id": new_id, "replace": false}
	var is_new := new_id != ""
	var wave := {"origin": state.anchor + state.n * d, "tris": pr if is_new or not ctx.model.has_body(on) else ctx.model.triangles(on),
		"is_new": is_new, "bodies": [new_id if is_new else on], "attach": "drafts" if is_new else "confirmed"}
	ctx.view.present_draft(op, [piece], wave)
	reset()
	ctx.view.clear_preview()
	ctx.view.hide_marker()
	ctx.document.sync()
