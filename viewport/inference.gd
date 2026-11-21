extends RefCounted
## The one snapping and inference engine every tool uses (T4, Q16): what's under the cursor (pick), point snaps
## in SketchUp's order (endpoint > midpoint > on edge), axis inference with hysteresis, and moves along an axis
## or across a plane. Model space (Z-up mm) in and out.

const Main := preload("res://main.gd")
const EDGE_PX := 8.0            # on-edge snap radius, pixels
const INFER_DEG := 8.0          # drag within this angle of an axis's on-screen direction -> sticks to it
const RELEASE_DEG := 12.0       # ...and lets go beyond this (hysteresis)
const PLANE_TOL := 0.5          # mm: how far off a plane a point may sit and still count as on it
var m: Main


func pick(screen: Vector2) -> Dictionary:
	var o := m.cam.project_ray_origin(screen)
	var d := m.cam.project_ray_normal(screen)
	var space := m.get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(o, o + d * 100.0, 1)
	q.hit_back_faces = true
	var r := space.intersect_ray(q)
	var q2 := PhysicsRayQueryParameters3D.create(o, o + d * 100.0, 2)
	q2.hit_back_faces = true
	var r2 := space.intersect_ray(q2)
	if not r2.is_empty() and (r.is_empty() or o.distance_to(r2["position"]) <= o.distance_to(r["position"]) + 0.002):
		r = r2   # a rectangle drawn on a face wins over the face itself
	if not r.is_empty():
		var n: Vector3 = r["normal"]
		if n.dot(d) > 0: n = -n                      # face toward the camera = outward
		var col: Object = r["collider"]
		var res := {"hit": true, "point": Main.g2m(r["position"]), "normal": Main.clean_normal(Main.n_g2m(n)),
					"body": String(col.get_meta("body_id", "")), "rect": String(col.get_meta("rect_id", ""))}
		if res["rect"] != "":
			res["normal"] = m.rects[res["rect"]]["n"]
		return res
	if absf(d.y) > 1e-6:
		var t := -o.y / d.y
		if t > 0:
			return {"hit": true, "point": Main.g2m(o + d * t), "normal": Vector3(0, 0, 1), "body": "", "rect": "", "ground": true}
	return {"hit": false}


func snap(p: Dictionary, screen: Vector2) -> Dictionary:
	"""A point picked on a plane (a face or the ground), snapped like Move snaps (Q16): endpoint > midpoint >
	on edge, on any board or rectangle but staying on that plane; else the grid."""
	if not p.get("hit", false):
		return p
	var n: Vector3 = p["normal"]
	var hit := point(screen, "", {"n": n, "p": p["point"]}, true)
	if not hit.is_empty():
		p["point"] = hit["point"]; p["snap"] = hit["kind"]
	elif m.grid_snap:
		var pt: Vector3 = p["point"]
		for i in 3:
			if absf(n[i]) < 0.5:
				pt[i] = snappedf(pt[i], Main.GRID)
		p["point"] = pt; p["snap"] = "grid"
	return p


static func _on_plane(v: Vector3, plane: Dictionary) -> bool:
	return plane.is_empty() or absf((v - plane["p"]).dot(plane["n"])) <= PLANE_TOL


static func _on_other(v: Vector3, plane: Dictionary) -> bool:
	return not plane.is_empty() and absf((v - plane["p"]).dot(plane["n"])) <= PLANE_TOL


func _screen_d(v: Vector3, screen: Vector2) -> float:
	var gv := Main.m2g(v)
	if m.cam.is_position_behind(gv): return INF
	return m.cam.unproject_position(gv).distance_to(screen)


func point(screen: Vector2, exclude: String, plane := {}, with_rects := false, not_on := {}) -> Dictionary:
	"""Point snaps in SketchUp's priority: endpoint > midpoint > on edge, nearest first, and only points you can
	see (one hidden behind a board doesn't count). Empty if none.
	exclude: a board to ignore (the one being moved). plane: {"n", "p"}: only points on that plane.
	with_rects: rectangles' corners and sides count too (drawing on a face).
	not_on: {"n", "p"}: ignore points on this plane (Push/Pull: the face being pushed)."""
	var verts := {}
	var edges := {}
	for bid in m.body_verts:
		if bid != exclude and not m.is_hidden(bid): verts[bid] = m.body_verts[bid]
	for bid in m.body_edges:
		if bid != exclude and not m.is_hidden(bid): edges[bid] = m.body_edges[bid]
	if with_rects:
		for rid in m.rects:
			var pts: PackedVector3Array = PackedVector3Array(m.rects[rid]["pts"])
			verts["rect " + rid] = pts
			edges["rect " + rid] = PackedVector3Array([pts[0], pts[1], pts[1], pts[2], pts[2], pts[3], pts[3], pts[0]])
	var keep := func(v: Vector3) -> bool: return _on_plane(v, plane) and not _on_other(v, not_on)
	# endpoints
	var cands := []
	for bid in verts:
		for v in verts[bid]:
			if keep.call(v): cands.append([v, bid])
	var best := _nearest_visible(cands, screen, Main.SNAP_PX, "endpoint")
	if not best.is_empty(): return best
	# midpoints
	cands = []
	for bid in edges:
		var segs: PackedVector3Array = edges[bid]
		for i in range(0, segs.size(), 2):
			var mid := (segs[i] + segs[i + 1]) * 0.5
			if keep.call(mid): cands.append([mid, bid])
	best = _nearest_visible(cands, screen, Main.SNAP_PX, "midpoint")
	if not best.is_empty(): return best
	# on an edge
	cands = []
	var o := Main.g2m(m.cam.project_ray_origin(screen)); var d := Main.n_g2m(m.cam.project_ray_normal(screen))
	for bid in edges:
		var segs: PackedVector3Array = edges[bid]
		for i in range(0, segs.size(), 2):
			if not (_on_plane(segs[i], plane) and _on_plane(segs[i + 1], plane)): continue
			var q := closest_on_segment_to_ray(segs[i], segs[i + 1], o, d)
			var g := _grid_along(q, segs[i], segs[i + 1])
			if _on_other(q, not_on) or _on_other(g, not_on): continue
			cands.append([g, bid, q])
	return _nearest_visible(cands, screen, EDGE_PX, "on edge")


func _nearest_visible(cands: Array, screen: Vector2, radius: float, kind: String) -> Dictionary:
	"""The candidate nearest the cursor on screen (within radius pixels) that isn't hidden behind a board."""
	var near := []
	for c in cands:
		var dd := _screen_d(c[2] if c.size() > 2 else c[0], screen)
		if dd < radius: near.append([dd, c])
	near.sort_custom(func(x, y): return x[0] < y[0])
	for n in near:
		var c: Array = n[1]
		if _visible(c[2] if c.size() > 2 else c[0]):
			var point_hit := {"point": c[0], "kind": kind, "body": c[1]}
			if c.size() > 2: point_hit["edge_point"] = c[2]
			return point_hit
	return {}


func _visible(v: Vector3) -> bool:
	"""Nothing solid between the camera and this point (a point on a board's surface sees itself)."""
	var o := m.cam.global_position
	var g := Main.m2g(v)
	var dist := o.distance_to(g)
	var q := PhysicsRayQueryParameters3D.create(o, g, 1)       # boards only, not rectangles
	q.hit_back_faces = true
	var r := m.get_world_3d().direct_space_state.intersect_ray(q)
	return r.is_empty() or o.distance_to(r["position"]) >= dist - (0.001 + dist * 0.003)


func _grid_along(q: Vector3, a: Vector3, b: Vector3) -> Vector3:
	"""With grid snap on, a point on a straight (axis-aligned) edge lands on the grid along it."""
	if not m.grid_snap: return q
	var u := (b - a).normalized()
	for i in 3:
		if absf(absf(u[i]) - 1.0) < 1e-6:
			var lo := minf(a[i], b[i]); var hi := maxf(a[i], b[i])
			q[i] = clampf(snappedf(q[i], Main.GRID), lo, hi)
	return q


static func closest_on_segment_to_ray(p0: Vector3, p1: Vector3, o: Vector3, d: Vector3) -> Vector3:
	var u := p1 - p0
	var w0 := p0 - o
	var a := u.dot(u); var b := u.dot(d); var c := d.dot(d); var dd := u.dot(w0); var e := d.dot(w0)
	var den := a * c - b * b
	var s := 0.0 if absf(den) < 1e-9 else clampf((b * e - c * dd) / den, 0.0, 1.0)
	return p0 + u * s


func axis(screen: Vector2, anchor: Vector3, axes: Array, current: int) -> int:
	var a2 := m.cam.unproject_position(Main.m2g(anchor))
	var dv := screen - a2
	if dv.length() < 15.0: return -1
	var best := -1
	var best_ang := INF
	for ax in axes:
		var b2 := m.cam.unproject_position(Main.m2g(anchor + Main._axis_vec(ax) * 100.0))
		var dir := b2 - a2
		if dir.length() < 3.0: continue                 # axis points at the camera: nothing to follow on screen
		var ang := rad_to_deg(dv.angle_to(dir))
		ang = minf(absf(ang), 180.0 - absf(ang))        # either direction along the axis
		var limit := RELEASE_DEG if ax == current else INFER_DEG
		if ang < limit and ang < best_ang:
			best_ang = ang; best = ax
	return best


func axis_dest(screen: Vector2, ref: Vector3, ax: int, exclude := "") -> Variant:
	var ax_v := Main._axis_vec(ax)
	var a := Main.m2g(ref); var n := (Main.m2g(ref + ax_v) - a).normalized()
	var o := m.cam.project_ray_origin(screen); var d := m.cam.project_ray_normal(screen)
	var bb := n.dot(d); var den := 1.0 - bb * bb
	var t := 0.0
	if den > 0.06:
		var w0 := a - o
		t = (bb * d.dot(w0) - n.dot(w0)) / den * 1000.0
	else:
		# looking almost straight down the axis: use the point under the cursor, projected onto it
		var under := pick(screen)
		if not under.get("hit", false) or under["body"] == exclude: return null
		t = (under["point"] - ref).dot(ax_v)
	return ref + ax_v * (snappedf(t, Main.GRID) if m.grid_snap else roundf(t))


func plane_dest(screen: Vector2, ref: Vector3, n: Vector3) -> Variant:
	var o := Main.g2m(m.cam.project_ray_origin(screen)); var d := Main.n_g2m(m.cam.project_ray_normal(screen))
	var den := d.dot(n)
	if absf(den) < 1e-4: return null
	var t := (ref - o).dot(n) / den
	if t <= 0: return null
	var vec := o + d * t - ref
	if m.grid_snap:                                    # snap the distance travelled, not the position
		for i in 3:
			if absf(n[i]) < 0.5: vec[i] = snappedf(vec[i], Main.GRID)
	return ref + vec
