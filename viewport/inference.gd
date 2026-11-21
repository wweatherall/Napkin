extends RefCounted
## The one snapping and inference engine every tool uses (T4, Q16): what's under the cursor (pick), point snaps
## in SketchUp's order (endpoint > midpoint > on edge), axis inference with hysteresis, and moves along an axis
## or across a plane. Model space (Z-up mm) in and out.

const Main := preload("res://main.gd")
const EDGE_PX := 8.0            # on-edge snap radius, pixels
const INFER_DEG := 8.0          # drag within this angle of an axis's on-screen direction -> sticks to it
const RELEASE_DEG := 12.0       # ...and lets go beyond this (hysteresis)
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
	if not p.get("hit", false):
		return p
	var n: Vector3 = p["normal"]
	var best = null
	var bestd := Main.SNAP_PX
	var pools := []
	if p["body"] != "": pools.append(m.body_verts.get(p["body"], PackedVector3Array()))
	else: for k in m.body_verts: pools.append(m.body_verts[k])
	for k in m.rects: pools.append(PackedVector3Array(m.rects[k]["pts"]))
	for pool in pools:
		for v in pool:
			if absf((v - p["point"]).dot(n)) > 0.5: continue   # stay on the plane
			var gv := Main.m2g(v)
			if m.cam.is_position_behind(gv): continue
			var dd := m.cam.unproject_position(gv).distance_to(screen)
			if dd < bestd:
				bestd = dd; best = v
	if best != null:
		p["point"] = best; p["snap"] = "endpoint"
	elif m.grid_snap:
		var pt: Vector3 = p["point"]
		for i in 3:
			if absf(n[i]) < 0.5:
				pt[i] = snappedf(pt[i], Main.GRID)
		p["point"] = pt; p["snap"] = "grid"
	return p


func point(screen: Vector2, exclude: String) -> Dictionary:
	"""Point snaps on other boards, in SketchUp's priority: endpoint > midpoint > on edge. Empty if none."""
	var best := {}
	var bestd := Main.SNAP_PX
	for bid in m.body_verts:
		if bid == exclude: continue
		for v in m.body_verts[bid]:
			var gv := Main.m2g(v)
			if m.cam.is_position_behind(gv): continue
			var dd := m.cam.unproject_position(gv).distance_to(screen)
			if dd < bestd: bestd = dd; best = {"point": v, "kind": "endpoint", "body": bid}
	if not best.is_empty(): return best
	bestd = Main.SNAP_PX
	for bid in m.body_edges:
		if bid == exclude: continue
		var segs: PackedVector3Array = m.body_edges[bid]
		for i in range(0, segs.size(), 2):
			var mid := (segs[i] + segs[i + 1]) * 0.5
			var gm := Main.m2g(mid)
			if m.cam.is_position_behind(gm): continue
			var dd := m.cam.unproject_position(gm).distance_to(screen)
			if dd < bestd: bestd = dd; best = {"point": mid, "kind": "midpoint", "body": bid}
	if not best.is_empty(): return best
	bestd = EDGE_PX
	var o := Main.g2m(m.cam.project_ray_origin(screen)); var d := Main.n_g2m(m.cam.project_ray_normal(screen))
	for bid in m.body_edges:
		if bid == exclude: continue
		var segs: PackedVector3Array = m.body_edges[bid]
		for i in range(0, segs.size(), 2):
			var q := closest_on_segment_to_ray(segs[i], segs[i + 1], o, d)
			var gq := Main.m2g(q)
			if m.cam.is_position_behind(gq): continue
			var dd := m.cam.unproject_position(gq).distance_to(screen)
			if dd < bestd: bestd = dd; best = {"point": q, "kind": "on edge", "body": bid}
	return best


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
