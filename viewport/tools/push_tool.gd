extends "res://tools/tool.gd"
## Push/Pull (P): click a face or rectangle, move, then click or type a distance + Return (minus = cut).

var state := {}
var hover := {}          # the face or rectangle under the cursor


func reset() -> void:
	state = {}


func hint() -> String:
	return "Push/Pull: click a face or rectangle, move, then click or type a distance + Enter (minus = cut)"


func busy() -> bool:
	return state.get("active", false)


func mouse_moved(screen: Vector2) -> void:
	if state.get("active", false):
		_push_drag(screen)
	else:
		_push_hover(screen)


func click(screen: Vector2) -> void:
	if not state.get("active", false):
		_push_hover(screen)
		if hover.is_empty(): return
		state = hover.duplicate()
		state["active"] = true
		state["dist"] = 0.0
	else:
		commit_push(state["dist"])


func typed(txt: String) -> void:
	if state.get("active", false):
		commit_push(float(txt))


func vcb_value() -> String:
	return "%d" % state["dist"] if state.get("active", false) else ""


func tip() -> String:
	return "to " + state["snap"] if state.get("active", false) and state.get("snap", "") != "" else ""


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
		if absf(tn.dot(n)) > 0.999 and absf((a - p).dot(n)) < 0.5:
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
		state["dist"] = Main.r3((pt["point"] - state["anchor"]).dot(state["n"]))
		state["snap"] = pt["kind"]
		m._show_marker({"hit": true, "point": pt["point"], "snap": pt["kind"]})
	_preview_push(state["dist"])
	m._update_vcb()


func _preview_push(d: float) -> void:
	if absf(d) < 0.5:
		m.overlay.mesh = m._tri_mesh(state["tris"], m.mat_hover); m.overlay_lines.mesh = null; return
	var pr := Main.prism(state["tris"], state["n"], d)
	m.overlay.mesh = m._tri_mesh(pr, m.mat_cut if d < 0 else m.mat_draft)
	m.overlay_lines.mesh = m._lines(Main.feature_edges(pr), Color(0.6, 0.35, 0.0)).mesh


func commit_push(d: float) -> void:
	if absf(d) < 0.5: return
	m.reject_note = ""
	m.counters["pp"] += 1
	var oid := "pp%d" % m.counters["pp"]
	var op := {"id": oid, "type": "push_pull", "distance": Main.r3(d)}
	var on := ""
	if state["rect"] != "":
		op["target"] = {"rect": state["rect"]}
		on = m.rects[state["rect"]]["on"]
	else:
		op["target"] = {"face": {"body": state["body"], "normal": Main.arr3(state["n"]), "point": Main.arr3(state["anchor"])}}
		on = state["body"]
	var new_id := ""
	# a rectangle becomes its own board (free, or on a face with "new board" on);
	# pushing a body's own face always edits that body, like SketchUp
	if state["rect"] != "" and (on == "" or (d > 0 and m.new_board)):
		m.counters["b"] += 1
		new_id = "b%d" % m.counters["b"]
		op["body"] = new_id
	if m.force_reject_next and op["target"].has("rect"):
		op["target"] = {"rect": "r_missing"}      # test hook only: guarantees FreeCAD rejects it
		m.force_reject_next = false
	m.ops.append(op)
	var end_point: Vector3 = state["anchor"] + state["n"] * d   # on the moved face, under the cursor's axis
	var pr := Main.prism(state["tris"], state["n"], d)
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
	state = {}
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
