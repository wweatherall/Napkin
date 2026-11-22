extends SceneTree
## I51/P21: pure planar arrangement cases; optionally export predictions for the FreeCAD scenario.
const Regions := preload("res://regions.gd")
const Geo := preload("res://tool_geometry.gd")
var passed := 0
var failed := 0
var predictions := []

func check(label: String, condition: bool, detail = "") -> void:
	if condition: passed += 1; print("PASS ", label)
	else: failed += 1; print("FAIL ", label, " ", detail)

static func points(values: Array, n := Vector3(0, 0, 1), offset := Vector3.ZERO) -> PackedVector3Array:
	var basis := Geo.plane_basis(n)
	var result := PackedVector3Array()
	for p in values: result.append(offset + basis[0] * p[0] + basis[1] * p[1])
	return result

static func tris(polygon: PackedVector3Array, n: Vector3) -> PackedVector3Array:
	var basis := Geo.plane_basis(n); var flat := PackedVector2Array()
	for p in polygon: flat.append(Vector2(p.dot(basis[0]), p.dot(basis[1])))
	var out := PackedVector3Array()
	for i in Geometry2D.triangulate_polygon(flat): out.append(polygon[i])
	return out

static func arr(p: Vector3) -> Array: return [p.x, p.y, p.z]
static func arrays(p: PackedVector3Array) -> Array:
	var out := []
	for v in p: out.append(arr(v))
	return out

func example(label: String, segments: Array, at: Array, area: float, polygon := [[0, 0], [100, 0], [100, 100], [0, 100]], n := Vector3(0, 0, 1), offset := Vector3.ZERO, source_hole := false) -> void:
	var outline := points(polygon, n, offset)
	var source := tris(outline, n)
	if source_hole:
		# A 20x20 hole at 40..60, with four surrounding rectangular strips.
		source = PackedVector3Array()
		for box in [[[0,0],[100,0],[100,40],[0,40]], [[0,60],[100,60],[100,100],[0,100]], [[0,40],[40,40],[40,60],[0,60]], [[60,40],[100,40],[100,60],[60,60]]]:
			source.append_array(tris(points(box, n, offset), n))
	var lines := []
	for pair in segments:
		var ps := points(pair, n, offset)
		lines.append({"a": ps[0], "b": ps[1]})
	var p := points([at], n, offset)[0]
	var result := Regions.find(source, lines, n, p)
	check(label + ": area", not result.is_empty() and absf(result.get("area", 0.0) - area) < 0.15, result.get("area", "empty"))
	if result.is_empty(): return
	var lo := Vector3(INF, INF, INF); var hi := -lo
	var measured := 0.0
	for i in range(0, result.tris.size(), 3):
		measured += (result.tris[i + 1] - result.tris[i]).cross(result.tris[i + 2] - result.tris[i]).length() * 0.5
	for v in result.tris: lo = lo.min(v); hi = hi.max(v)
	check(label + ": preview stays on plane and has the same area", absf(measured - area) < 0.15 and Array(result.tris).all(func(v): return absf((v - p).dot(n)) < 0.001))
	predictions.append({"name": label, "source": arrays(outline), "source_hole": source_hole, "normal": arr(n), "point": arr(p),
		"outline": arrays(result.outline), "holes": result.holes.map(func(h): return arrays(h)), "area": result.area, "lo": arr(lo), "hi": arr(hi)})

func _init() -> void:
	example("unsplit face", [], [20, 20], 10000)
	example("one crossing line left", [[[50, 0], [50, 100]]], [20, 20], 5000)
	example("one crossing line right", [[[50, 0], [50, 100]]], [80, 20], 5000)
	example("crossing lines", [[[50, 0], [50, 100]], [[0, 50], [100, 50]]], [20, 20], 2500)
	example("diagonal through corners", [[[0, 0], [100, 100]]], [80, 20], 5000)
	example("line stops partway", [[[50, 0], [50, 60]]], [20, 20], 10000)
	example("floating segment", [[[30, 30], [70, 70]]], [20, 20], 10000)
	example("two lines meeting at edge", [[[0, 0], [50, 100]], [[100, 0], [50, 100]]], [50, 40], 5000)
	example("two lines meeting inside", [[[0, 50], [50, 50]], [[50, 50], [100, 50]]], [20, 20], 5000)
	example("T junction", [[[50, 0], [50, 100]], [[0, 50], [50, 50]]], [20, 20], 2500)
	example("overlapping duplicate line", [[[50, 0], [50, 100]], [[50, 20], [50, 80]]], [20, 20], 5000)
	example("reversed duplicate", [[[50, 0], [50, 100]], [[50, 100], [50, 0]]], [20, 20], 5000)
	example("near overlapping within tolerance", [[[50, 0], [50, 100]], [[50.0004, 20], [50.0004, 80]]], [20, 20], 5000)
	example("endpoint within tolerance", [[[50, 0.0004], [50, 99.9996]]], [20, 20], 5000)
	example("endpoint outside tolerance stays dangling", [[[50, 0.01], [50, 99.99]]], [20, 20], 10000)
	example("line extends beyond face", [[[50, -50], [50, 150]]], [20, 20], 5000)
	var loop := [[[30, 30], [70, 30]], [[70, 30], [70, 70]], [[70, 70], [30, 70]], [[30, 70], [30, 30]]]
	example("closed island inside", loop, [50, 50], 1600)
	example("closed island outside has hole", loop, [20, 20], 8400)
	example("island with dangling bridge", loop + [[[0, 30], [30, 30]]], [20, 20], 8400)
	var small_loops := []
	for x in [15, 55]:
		var ps := [[x,30], [x+20,30], [x+20,50], [x,50]]
		for i in 4: small_loops.append([ps[i], ps[(i+1)%4]])
	example("two holes sharing a bridge ray", small_loops, [5,5], 9200)
	example("narrow distinct parallel lines", [[[50,0],[50,100]], [[50.01,0],[50.01,100]]], [50.005,50], 1.0)
	example("self crossing closed chain", [[[20,20],[80,80]], [[80,80],[20,80]], [[20,80],[80,20]], [[80,20],[20,20]]], [50,30], 900)
	example("face with existing hole", [], [20, 20], 9600, [[0,0],[100,0],[100,100],[0,100]], Vector3(0,0,1), Vector3.ZERO, true)
	example("concave outline", [[[40, 0], [40, 40]]], [20, 20], 4000, [[0,0],[100,0],[100,40],[40,40],[40,100],[0,100]])
	example("tilted normal", [[[50, 0], [50, 100]]], [20, 20], 5000, [[0,0],[100,0],[100,100],[0,100]], Vector3(1,2,3).normalized(), Vector3(700,300,200))
	example("reversed normal", [[[50, 0], [50, 100]]], [20, 20], 5000, [[0,0],[100,0],[100,100],[0,100]], Vector3(0,0,-1))
	var circle := []
	for i in 64: circle.append([50*cos(TAU*i/64), 50*sin(TAU*i/64)])
	example("circular boundary split", [[[0,-50],[0,50]]], [-20,0], 64*2500*sin(TAU/64)/4, circle, Vector3(0,0,1), Vector3(800,0,20))
	if not predictions.is_empty(): predictions.back()["circle_radius"] = 50
	var sq := tris(points([[0,0],[100,0],[100,100],[0,100]]), Vector3(0,0,1))
	var noisy: Dictionary = Regions.find(sq, [{"a":Vector3(50,0,0), "b":Vector3(50,100,0)}], Vector3(0,0,1), Vector3(20,20,0.0001))
	var snapped_edge: Dictionary = Regions.find(sq, [{"a":Vector3(50,0.02,0), "b":Vector3(50,99.98,0), "snap_start":true, "snap_end":true}], Vector3(0,0,1), Vector3(20,20,0))
	check("explicit curved-edge snaps bridge display tessellation only", absf(snapped_edge.get("area",0) - 5000) < 0.01)
	check("physics hit noise never moves the actual region plane", not noisy.is_empty() and Array(noisy.outline).all(func(p): return p.z == 0))
	check("outside face has no region", Regions.find(sq, [], Vector3(0,0,1), Vector3(200,200,0)).is_empty())
	check("off-plane lines do not divide face", absf(Regions.find(sq, [{"a":Vector3(50,0,1), "b":Vector3(50,100,1)}], Vector3(0,0,1), Vector3(20,20,0)).get("area",0) - 10000) < 0.01)
	var free := []
	for pair in loop:
		var ps := points(pair); free.append({"a":ps[0], "b":ps[1]})
	check("independent loose segments close into a free region", absf(Regions.find(PackedVector3Array(), free, Vector3(0,0,1), Vector3(50,50,0)).get("area",0) - 1600) < 0.01)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--regions-output="):
			var f := FileAccess.open(arg.trim_prefix("--regions-output="), FileAccess.WRITE)
			f.store_string(JSON.stringify(predictions))
	print("REGION TESTS: %d passed, %d failed" % [passed, failed])
	quit(1 if failed else 0)
