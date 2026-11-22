extends RefCounted
## Planar arrangements in model mm (I51). Pure functions; no scene or model state.
## Split intersections, weld within native tolerance, prune dangling branches, walk bounded faces.
const Geo := preload("res://tool_geometry.gd")
const EPS := 0.001

static func _area(p: PackedVector2Array) -> float:
	var a := 0.0
	for i in p.size(): a += p[i].cross(p[(i + 1) % p.size()])
	return a * 0.5

static func _near_segment(p: Vector2, a: Vector2, b: Vector2) -> bool:
	return Geometry2D.get_closest_point_to_segment(p, a, b).distance_to(p) <= EPS

static func _in_tri(p: Vector2, a: Vector2, b: Vector2, c: Vector2) -> bool:
	var ab := (b - a).cross(p - a); var bc := (c - b).cross(p - b); var ca := (a - c).cross(p - c)
	var ta := EPS * (b - a).length(); var tb := EPS * (c - b).length(); var tc := EPS * (a - c).length()
	return (ab >= -ta and bc >= -tb and ca >= -tc) or (ab <= ta and bc <= tb and ca <= tc)

static func _inside_source(p: Vector2, tris: PackedVector2Array) -> bool:
	if tris.is_empty(): return true
	for i in range(0, tris.size(), 3):
		if _in_tri(p, tris[i], tris[i + 1], tris[i + 2]): return true
	return false

static func _edge(a: int, b: int) -> String:
	return "%d:%d" % [mini(a, b), maxi(a, b)]

static func _vertex(p: Vector2, verts: Array, buckets: Dictionary) -> int:
	var cell := Vector2i(floori(p.x / EPS), floori(p.y / EPS))
	var first := -1
	for x in range(-1, 2):
		for y in range(-1, 2):
			for i in buckets.get(cell + Vector2i(x,y), []):
				if p.distance_to(verts[i]) <= EPS and (first < 0 or i < first): first = i
	if first >= 0: return first
	var id := verts.size()
	verts.append(p)
	if not buckets.has(cell): buckets[cell] = []
	buckets[cell].append(id)
	return id

static func _simple_cycles(walk: Array, verts: Array, cycles: Array) -> void:
	# A bridge between loops walks out and back. Split at repeated vertices before classifying cycles.
	var seen := {}
	for i in walk.size():
		var id: int = walk[i]
		if seen.has(id):
			var at: int = seen[id]
			_simple_cycles(walk.slice(at, i), verts, cycles)
			_simple_cycles(walk.slice(0, at) + walk.slice(i), verts, cycles)
			return
		seen[id] = i
	if walk.size() < 3: return
	var polygon := PackedVector2Array()
	for id in walk: polygon.append(verts[id])
	if _area(polygon) > EPS * EPS: cycles.append(polygon)

static func _cycles(segments: Array, source: PackedVector2Array, boundary_count: int) -> Array:
	var cuts := []
	for s in segments: cuts.append([s[0], s[1]])
	for i in segments.size():
		var a: Vector2 = segments[i][0]; var b: Vector2 = segments[i][1]
		var ab := b - a
		for j in range(i + 1, segments.size()):
			var c: Vector2 = segments[j][0]; var d: Vector2 = segments[j][1]
			var cd := d - c
			var den := ab.cross(cd)
			if absf(den) > 1e-10 * ab.length() * cd.length():
				var t := (c - a).cross(cd) / den
				var u := (c - a).cross(ab) / den
				if t >= 0 and t <= 1 and u >= 0 and u <= 1:
					var q := a + ab * t
					cuts[i].append(q); cuts[j].append(q)
			# Endpoint-on-segment also handles collinear partial overlaps and tiny endpoint gaps.
			for p in [a, b]:
				if _near_segment(p, c, d): cuts[j].append(p)
			for p in [c, d]:
				if _near_segment(p, a, b): cuts[i].append(p)
	var verts := []
	var buckets := {}
	var edges := {}
	for i in segments.size():
		var a: Vector2 = segments[i][0]; var delta: Vector2 = segments[i][1] - a
		cuts[i].sort_custom(func(p, q): return (p - a).dot(delta) < (q - a).dot(delta))
		for k in range(cuts[i].size() - 1):
			var v := _vertex(cuts[i][k], verts, buckets); var w := _vertex(cuts[i][k + 1], verts, buckets)
			if v != w and _inside_source((verts[v] + verts[w]) * 0.5, source):
				var key := _edge(v, w)
				if not edges.has(key): edges[key] = {"pair": [v, w], "count": 0, "line": false}
				if i < boundary_count: edges[key].count += 1
				else: edges[key].line = true
	var neighbors := []
	for v in verts: neighbors.append([])
	for edge in edges.values():
		if not edge.line and edge.count % 2 == 0: continue
		var e: Array = edge.pair
		neighbors[e[0]].append(e[1]); neighbors[e[1]].append(e[0])
	var queue := []
	for i in verts.size():
		if neighbors[i].size() == 1: queue.append(i)
	while not queue.is_empty():
		var v: int = queue.pop_back()
		if neighbors[v].size() != 1: continue
		var w: int = neighbors[v][0]
		neighbors[v].clear(); neighbors[w].erase(v)
		if neighbors[w].size() == 1: queue.append(w)
	for i in verts.size():
		var center: Vector2 = verts[i]
		neighbors[i].sort_custom(func(a, b): return (verts[a] - center).angle() < (verts[b] - center).angle())
	var seen := {}
	var cycles := []
	for i in verts.size():
		for j in neighbors[i]:
			if seen.has("%d>%d" % [i, j]): continue
			var walk := []
			var a := i; var b: int = j
			while not seen.has("%d>%d" % [a, b]):
				seen["%d>%d" % [a, b]] = true
				walk.append(a)
				var around: Array = neighbors[b]
				var c: int = around[(around.find(a) - 1 + around.size()) % around.size()]
				a = b; b = c
			_simple_cycles(walk, verts, cycles)
	# A bridge may expose the same simple ring on two walks. Keep each oriented ring once.
	var unique := []
	var rings := {}
	for cycle in cycles:
		var keys := PackedStringArray()
		for p in cycle: keys.append("%.6f,%.6f" % [p.x,p.y])
		keys.sort()
		var key := ";".join(keys)
		if not rings.has(key): rings[key] = true; unique.append(cycle)
	return unique

static func _contains(outer: PackedVector2Array, inner: PackedVector2Array) -> bool:
	if _area(outer) <= _area(inner) + EPS * EPS: return false
	# An interior triangle point avoids a shared vertex or edge between neighboring cells.
	var indices := Geometry2D.triangulate_polygon(inner)
	if indices.size() < 3: return false
	var p := (inner[indices[0]] + inner[indices[1]] + inner[indices[2]]) / 3.0
	return Geometry2D.is_point_in_polygon(p, outer)

static func _bridge(outer: PackedVector2Array, holes: Array) -> PackedVector2Array:
	var result := outer
	var ordered := holes.duplicate()
	ordered.sort_custom(func(a, b):
		var ax := -INF; var bx := -INF
		for p in a: ax = maxf(ax, p.x)
		for p in b: bx = maxf(bx, p.x)
		return ax > bx)
	for hole in ordered:
		# Connect a hole's rightmost point to the first outer edge on a horizontal ray.
		var hi := 0
		for i in hole.size():
			if hole[i].x > hole[hi].x: hi = i
		var h: Vector2 = hole[hi]
		var best := INF; var edge := -1; var q := Vector2.ZERO
		for i in result.size():
			var a := result[i]; var b := result[(i + 1) % result.size()]
			if (a.y > h.y) == (b.y > h.y): continue
			var x := a.x + (h.y - a.y) * (b.x - a.x) / (b.y - a.y)
			if x >= h.x and x < best: best = x; edge = i; q = Vector2(x, h.y)
		if edge < 0: return PackedVector2Array()
		var joined := PackedVector2Array()
		for i in range(edge + 1): joined.append(result[i])
		joined.append(q)
		for i in range(hole.size() + 1): joined.append(hole[(hi - i + hole.size()) % hole.size()])
		joined.append(q)
		for i in range(edge + 1, result.size()): joined.append(result[i])
		result = joined
	return result

static func _triangulate(polygon: PackedVector2Array) -> PackedVector2Array:
	# Ear clipping a weakly simple polygon (hole bridges have repeated endpoints).
	var ids := []
	for i in polygon.size():
		if i == 0 or polygon[i].distance_to(polygon[i - 1]) > EPS * 0.01: ids.append(i)
	if ids.size() > 1 and polygon[ids[0]].distance_to(polygon[ids.back()]) < EPS * 0.01: ids.pop_back()
	var out := PackedVector2Array()
	while ids.size() > 2:
		var found := false
		for k in ids.size():
			var a := polygon[ids[(k - 1 + ids.size()) % ids.size()]]
			var b := polygon[ids[k]]; var c := polygon[ids[(k + 1) % ids.size()]]
			if (b - a).cross(c - b) <= 1e-9: continue
			var blocked := false
			for id in ids:
				var p := polygon[id]
				if p.distance_to(a) < 1e-6 or p.distance_to(b) < 1e-6 or p.distance_to(c) < 1e-6: continue
				if _in_tri(p, a, b, c): blocked = true; break
			if blocked: continue
			out.append_array([a, b, c]); ids.remove_at(k); found = true; break
		if not found:
			# Collinear subdivisions carry no area. Remove them only after ordinary ears are exhausted.
			for k in ids.size():
				var a := polygon[ids[(k - 1 + ids.size()) % ids.size()]]
				var b := polygon[ids[k]]; var c := polygon[ids[(k + 1) % ids.size()]]
				if absf((b - a).cross(c - b)) < 1e-9:
					ids.remove_at(k); found = true; break
			if not found: return PackedVector2Array()
	return out

static func _snap_boundary(p: Vector2, segments: Array, limit: float) -> Vector2:
	var best := limit; var result := p
	for pair in segments:
		var q := Geometry2D.get_closest_point_to_segment(p, pair[0], pair[1])
		var d := q.distance_to(p)
		if d < best: best = d; result = q
	return result

static func find(source: PackedVector3Array, lines: Array, normal: Vector3, point: Vector3) -> Dictionary:
	var basis := Geo.plane_basis(normal)
	# Physics hits have float noise. Reconstruct on the source geometry's plane, never the ray hit's plane.
	var plane_point: Vector3 = source[0] if not source.is_empty() else (lines[0].a if not lines.is_empty() else point)
	var origin := point - normal * (point - plane_point).dot(normal)
	var flat := func(p: Vector3) -> Vector2: return Vector2((p - origin).dot(basis[0]), (p - origin).dot(basis[1]))
	var world := func(p: Vector2) -> Vector3: return origin + basis[0] * p.x + basis[1] * p.y
	var source2 := PackedVector2Array()
	for p in source: source2.append(flat.call(p))
	if not _inside_source(Vector2.ZERO, source2): return {}
	var boundary := {}
	for i in range(0, source.size(), 3):
		for pair in [[i, i + 1], [i + 1, i + 2], [i + 2, i]]:
			var a: Vector3 = source[pair[0]]; var b: Vector3 = source[pair[1]]
			var key_a := "%.6f,%.6f,%.6f" % [a.x, a.y, a.z]
			var key_b := "%.6f,%.6f,%.6f" % [b.x, b.y, b.z]
			var key: String = key_a + "/" + key_b if key_a < key_b else key_b + "/" + key_a
			if boundary.has(key): boundary.erase(key)
			else: boundary[key] = [flat.call(a), flat.call(b)]
	var segments: Array = boundary.values()
	var boundary_count := segments.size()
	for line in lines:
		var a: Vector3 = line.a; var b: Vector3 = line.b
		if absf((a - point).dot(normal)) > EPS or absf((b - point).dot(normal)) > EPS: continue
		var a2: Vector2 = flat.call(a); var b2: Vector2 = flat.call(b)
		# Explicit geometry snaps may land on a different tessellation of the same native curved edge.
		# Only these endpoints bridge the export's existing 0.1 mm display deflection; free endpoints keep EPS.
		if line.get("snap_start", false): a2 = _snap_boundary(a2, boundary.values(), 0.101)
		if line.get("snap_end", false): b2 = _snap_boundary(b2, boundary.values(), 0.101)
		if a2.distance_to(b2) >= EPS: segments.append([a2, b2])
	var cycles := _cycles(segments, source2, boundary_count)
	var chosen := PackedVector2Array()
	for cycle in cycles:
		if Geometry2D.is_point_in_polygon(Vector2.ZERO, cycle) and (chosen.is_empty() or _area(cycle) < _area(chosen)):
			chosen = cycle
	if chosen.is_empty(): return {}
	var holes := []
	for cycle in cycles:
		if not _contains(chosen, cycle): continue
		var nested := false
		for other in cycles:
			if _contains(chosen, other) and _contains(other, cycle): nested = true; break
		if not nested: holes.append(cycle)
	var flat_tris := _triangulate(_bridge(chosen, holes))
	if flat_tris.is_empty(): return {}
	var tris := PackedVector3Array(); var outline := PackedVector3Array(); var world_holes := []
	var area := 0.0
	for i in range(0, flat_tris.size(), 3): area += absf((flat_tris[i + 1] - flat_tris[i]).cross(flat_tris[i + 2] - flat_tris[i])) * 0.5
	var wanted := _area(chosen)
	for hole in holes: wanted -= _area(hole)
	if absf(area - wanted) > maxf(0.001, wanted * 1e-5): return {}
	for p in flat_tris: tris.append(world.call(p))
	for p in chosen: outline.append(world.call(p))
	for hole in holes:
		var points := PackedVector3Array()
		for p in hole: points.append(world.call(p))
		world_holes.append(points)
	return {"outline": outline, "holes": world_holes, "tris": tris, "area": area}
