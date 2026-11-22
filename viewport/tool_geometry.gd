extends RefCounted
## Pure geometry shared by tools, inference and main.gd (T88 step 0): units, rounding for ops, plane bases,
## prisms, feature edges, reflections. No state and no scene: every function is static. main.gd keeps wrappers
## under the old names (`Main.m2g`, `Main._rect_pts`, ...) while its other consumers move here.
## Model space is Z-up millimetres; Godot is Y-up metres.


static func m2g(p: Vector3) -> Vector3:
	return Vector3(p.x, p.z, -p.y) * 0.001


static func g2m(p: Vector3) -> Vector3:
	return Vector3(p.x, -p.z, p.y) * 1000.0


static func n_g2m(n: Vector3) -> Vector3:
	return Vector3(n.x, -n.z, n.y)


static func r3(x: float) -> float:
	return snappedf(x, 0.001)


static func arr3(v: Vector3) -> Array:
	return [r3(v.x), r3(v.y), r3(v.z)]


static func clean_normal(n: Vector3) -> Vector3:
	var c := [n.x, n.y, n.z]
	for i in 3:
		if absf(c[i]) < 1e-3:
			c[i] = 0.0
		elif absf(absf(c[i]) - 1.0) < 1e-3:
			c[i] = signf(c[i])
	var v := Vector3(c[0], c[1], c[2]).normalized()
	return Vector3(snappedf(v.x, 1e-6), snappedf(v.y, 1e-6), snappedf(v.z, 1e-6))


static func plane_basis(n: Vector3) -> Array:
	# must match worker/replay.py plane_from()
	var x: Vector3
	if absf(n.z) > 0.9:
		x = Vector3(1, 0, 0)
	else:
		x = Vector3(0, 0, 1).cross(n).normalized()
	x = (x - n * x.dot(n)).normalized()
	return [x, n.cross(x)]


static func rect_points(origin: Vector3, x: Vector3, y: Vector3, du: float, dv: float) -> PackedVector3Array:
	return PackedVector3Array([origin, origin + x * du, origin + x * du + y * dv, origin + y * dv])


static func edge_key(p: Vector3, q: Vector3) -> String:
	var a := "%.2f,%.2f,%.2f" % [p.x, p.y, p.z]
	var b := "%.2f,%.2f,%.2f" % [q.x, q.y, q.z]
	return a + "|" + b if a < b else b + "|" + a


static func feature_edges(tris: PackedVector3Array) -> PackedVector3Array:
	var edges := {}
	for i in range(0, tris.size(), 3):
		var a := tris[i]; var b := tris[i + 1]; var c := tris[i + 2]
		var n := (b - a).cross(c - a).normalized()
		for e in [[a, b], [b, c], [c, a]]:
			var k := edge_key(e[0], e[1])
			if not edges.has(k):
				edges[k] = [e[0], e[1], []]
			edges[k][2].append(n)
	var out := PackedVector3Array()
	for k in edges:
		var ns: Array = edges[k][2]
		var feat := ns.size() == 1
		if not feat:
			for j in range(1, ns.size()):
				if absf(ns[0].dot(ns[j])) < 0.9998:
					feat = true
		if feat:
			out.append_array([edges[k][0], edges[k][1]])
	return out


static func unique_verts(tris: PackedVector3Array) -> PackedVector3Array:
	var seen := {}
	var out := PackedVector3Array()
	for p in tris:
		var k := "%.1f,%.1f,%.1f" % [p.x, p.y, p.z]
		if not seen.has(k):
			seen[k] = true
			out.append(p)
	return out


static func prism(tris: PackedVector3Array, n: Vector3, d: float) -> PackedVector3Array:
	var o := n * d
	return prism_by(tris, func(_p: Vector3) -> Vector3: return o)


static func prism_by(tris: PackedVector3Array, offset: Callable) -> PackedVector3Array:
	"""A face swept out: each corner moves by offset(corner) (the same for a square end, its own for a sloped one)."""
	var out := PackedVector3Array()
	var edges := {}
	for i in range(0, tris.size(), 3):
		var a := tris[i]; var b := tris[i + 1]; var c := tris[i + 2]
		out.append_array([a, b, c, a + offset.call(a), b + offset.call(b), c + offset.call(c)])
		for e in [[a, b], [b, c], [c, a]]:
			var k := edge_key(e[0], e[1])
			edges[k] = [e[0], e[1], edges.get(k, [0, 0, 0])[2] + 1]
	for k in edges:
		if edges[k][2] == 1:
			var p: Vector3 = edges[k][0]; var q: Vector3 = edges[k][1]
			var po: Vector3 = p + offset.call(p); var qo: Vector3 = q + offset.call(q)
			out.append_array([p, q, qo, p, qo, po])
	return out


static func axis_vector(ax: int) -> Vector3:
	return [Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)][ax]


static func reflect_point(q: Vector3, p: Vector3, n: Vector3) -> Vector3:
	return q - n * (2.0 * (q - p).dot(n))


static func reflect_tris(tris: PackedVector3Array, p: Vector3, n: Vector3) -> PackedVector3Array:
	"""Mirror across any plane (T27). Each triangle's winding flips, so normals stay pointing out."""
	var out := PackedVector3Array()
	for i in range(0, tris.size(), 3):
		out.append(reflect_point(tris[i], p, n)); out.append(reflect_point(tris[i + 2], p, n)); out.append(reflect_point(tris[i + 1], p, n))
	return out


static func mirror_triangles(tris: PackedVector3Array, ax: int, c: float) -> PackedVector3Array:
	var out := PackedVector3Array()
	for q in tris:
		var m := q
		m[ax] = 2.0 * c - q[ax]
		out.append(m)
	return out
