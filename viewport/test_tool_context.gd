extends SceneTree
## The tools' interface (tool_context.gd, T88 step 0) on its own, with no window and no worker: real document,
## selection, presenter and inference objects with stand-in contents. Checks that each capability offers exactly
## its allowlisted public members (no owner, node or map escapes), that answers are snapshots a tool may change,
## the id sequences, appending without syncing, remove's signals, the camera ray and projection against the
## camera's own answers on a tilted view, and that the context, geometry and inference scripts never reach main.gd.
## Run: Godot --headless --path viewport --script res://test_tool_context.gd
const ToolContext = preload("res://tool_context.gd")
const Geo = preload("res://tool_geometry.gd")
const Inference = preload("res://inference.gd")
const Document = preload("res://document.gd")
const Selection = preload("res://selection.gd")
const Presenter = preload("res://presenter.gd")
const Appearance = preload("res://appearance.gd")
const Main = preload("res://main.gd")
var passed := 0
var failed := 0
var made: Array = []


class LinePresenter:
	var received := {}
	func register_line(o: Dictionary) -> void:
		received = o.duplicate(true)
		o.end[0] = 999


class FakeAppearance:
	var calls: Array
	func _init(log: Array) -> void: calls = log
	func current_name() -> String: return "White oak"
	func apply(targets: Array) -> void:
		calls.append(["paint", targets.duplicate()])
		targets.append("x")


class PaintInference:
	var hit := {}
	func pick(_screen: Vector2) -> Dictionary: return hit.duplicate(true)


class FakeClient:
	var sent: Array = []
	func send(d: Dictionary) -> void: sent.append(d)


func check(label: String, condition: bool, detail = "") -> void:
	if condition:
		passed += 1
		print("PASS ", label)
	else:
		failed += 1
		print("FAIL ", label, "  ", detail)


# The spec's surface (docs/specs/T88-tool-interface.md, "Proposed surface"). `selection.set` is `set_ids`
# (Object.set can't be overridden). DEFERRED arrive with the step that first uses them; each step moves its
# names from DEFERRED to ALLOW.
const ALLOW := {
	"pick": ["hit", "snap", "on_grid", "point", "axis", "axis_dest", "plane_dest", "ray", "project", "cursor",
			 "grid_enabled", "grid_step", "snap_radius"],
	"model": ["body_ids", "has_body", "triangles", "profile", "stock_frame", "unit_triangles", "cut_at",
			  "cut_triangles", "circle_geometry", "lines_on"],
	"selection": ["ids", "context", "assembly_of", "members_of", "unit_of", "in_context", "is_hidden",
				  "context_assembly", "edit_blocked", "set_ids", "enter"],
	"document": ["next_id", "op", "append", "remove", "sync"],
	"view": ["preview", "clear_preview", "marker", "hide_marker", "guides", "clear_guides", "selection_box",
			 "clear_selection_box", "face_highlight", "clear_face_highlight", "register_profile", "register_line"],
	"ui": ["typed_text", "refresh_measurements", "refresh_tip", "clear_rejection", "new_board"],
	"paint": ["current_name", "apply"],
}
const DEFERRED := {"view": ["present_draft", "mirror_preview"]}   # step 5 (Push/Pull), step 6 (Move)


static func public_members(o: Object) -> Dictionary:
	"""A script object's public methods and variables (not starting with _), own and inherited from scripts."""
	var methods := {}
	var props := {}
	for md in o.get_script().get_script_method_list():
		if not String(md["name"]).begins_with("_"): methods[String(md["name"])] = true
	for pd in o.get_script().get_script_property_list():
		if pd["usage"] & PROPERTY_USAGE_SCRIPT_VARIABLE and not String(pd["name"]).begins_with("_"):
			props[String(pd["name"])] = true
	return {"methods": methods.keys(), "props": props.keys()}


static func code_only(text: String) -> String:
	"""Source without comments and docstrings, so prose that names main.gd doesn't count as use."""
	var out := PackedStringArray()
	var in_doc := false
	for line in text.split("\n"):
		var t := line.strip_edges()
		if t.begins_with('"""'):
			if not (t.length() > 3 and t.ends_with('"""')): in_doc = not in_doc
			continue
		if in_doc:
			if t.ends_with('"""'): in_doc = false
			continue
		var hash := line.find("#")
		out.append(line if hash < 0 else line.substr(0, hash))
	return "\n".join(out)


func make() -> Dictionary:
	var doc := Document.new(); made.append(doc)
	var client := FakeClient.new()
	doc.client = client
	var sel := Selection.new(); made.append(sel)
	sel.doc = doc
	var pres := Presenter.new(); made.append(pres)
	pres.sel = sel
	var infer := Inference.new()
	var parts := {"doc": doc, "sel": sel, "pres": pres, "infer": infer}
	return {"doc": doc, "client": client, "sel": sel, "pres": pres, "infer": infer, "parts": parts,
			"ctx": ToolContext.new(parts)}


func _initialize() -> void:
	var t := make()
	var ctx = t["ctx"]

	# --- the allowlist: each capability offers exactly the spec's surface, nothing raw ---
	var top := public_members(ctx)
	var caps := ["pick", "model", "selection", "document", "view", "ui", "paint"]
	check("ToolContext's public members are the seven capabilities and nothing else",
		top["methods"].is_empty() and _same(top["props"], caps), top)
	for cap in caps:
		var pm := public_members(ctx.get(cap))
		check("%s: public methods are the allowlist" % cap, _same(pm["methods"], ALLOW[cap]),
			{"extra": _minus(pm["methods"], ALLOW[cap]), "missing": _minus(ALLOW[cap], pm["methods"])})
		check("%s: no public variables (owners stay private)" % cap, pm["props"].is_empty(), pm["props"])
		for name in DEFERRED.get(cap, []):
			check("%s.%s is not there yet (its step adds it)" % [cap, name], not pm["methods"].has(name))
	var raw := ["main", "m", "doc", "pres", "sel", "measure", "cam", "client", "infer", "get_owner", "ops",
				"counters", "body_tris", "rects", "overlay"]
	var leaks := []
	for cap in caps:
		var pm := public_members(ctx.get(cap))
		for r in raw:
			if pm["methods"].has(r) or pm["props"].has(r): leaks.append("%s.%s" % [cap, r])
	check("no capability exposes Main, a controller, the camera, a node or a cache by name", leaks.is_empty(), leaks)

	var line_pres := LinePresenter.new()
	var line_ctx := ToolContext.new({"pres": line_pres})
	var line_op := {"id": "rline", "type": "line", "end": [10, 20, 0]}
	line_ctx.view.register_line(line_op)
	check("view.register_line passes a deep copy to the presenter", line_pres.received == line_op and line_op.end[0] == 10)

	# --- snapshots: what a tool gets back is its own copy ---
	var pres = t["pres"]; var sel = t["sel"]; var doc = t["doc"]
	var tri := PackedVector3Array([Vector3(0, 0, 0), Vector3(10, 0, 0), Vector3(0, 10, 0)])
	pres.body_tris["b1"] = tri
	pres.rects["r1"] = {"tris": tri, "n": Vector3(0, 0, 1), "on": "", "pts": PackedVector3Array([Vector3.ZERO]), "kind": "rect",
						"nested": {"a": [1, 2]}}
	pres.stock_frames["b1"] = {"fitted": false, "axes": [[1, 0, 0]]}
	var got: PackedVector3Array = ctx.model.triangles("b1")
	got[0] = Vector3(99, 99, 99)
	check("model.triangles is a copy", pres.body_tris["b1"][0] == Vector3.ZERO)
	var prof: Dictionary = ctx.model.profile("r1")
	prof["n"] = Vector3(1, 0, 0); prof["nested"]["a"].append(3); prof["pts"][0] = Vector3.ONE
	check("model.profile is a deep copy", pres.rects["r1"]["n"] == Vector3(0, 0, 1) and pres.rects["r1"]["nested"]["a"].size() == 2
		and pres.rects["r1"]["pts"][0] == Vector3.ZERO)
	check("model.profile keeps kind, and {} for a missing profile", ctx.model.profile("r1")["kind"] == "rect" and ctx.model.profile("r9").is_empty())
	pres.loose_lines["rline"] = {"a": Vector3.ZERO, "b": Vector3(10,0,0), "n": Vector3(0,0,1), "on": "b1"}
	var saved: Array = ctx.model.lines_on("b1", Vector3(0,0,1), Vector3.ZERO)
	saved[0].a = Vector3.ONE
	check("model.lines_on returns a snapshot with ids", saved[0].id == "rline" and pres.loose_lines.rline.a == Vector3.ZERO)
	check("model.lines_on filters body and plane", ctx.model.lines_on("b2", Vector3(0,0,1), Vector3.ZERO).is_empty() and ctx.model.lines_on("b1", Vector3(0,0,1), Vector3(0,0,1)).is_empty())
	var sf: Dictionary = ctx.model.stock_frame("b1")
	sf["axes"][0].append(5)
	check("model.stock_frame is a deep copy; {} for none", pres.stock_frames["b1"]["axes"][0].size() == 3 and ctx.model.stock_frame("b2").is_empty())
	check("model.body_ids / has_body", ctx.model.body_ids() == ["b1"] and ctx.model.has_body("b1") and not ctx.model.has_body("b2"))
	var ids: Array = ctx.model.body_ids(); ids.append("bx")
	check("model.body_ids is a copy", pres.body_tris.size() == 1)
	check("model.triangles of a missing board is empty", ctx.model.triangles("b9").is_empty())
	check("model.unit_triangles joins the unit's boards", ctx.model.unit_triangles({"bodies": ["b1", "b9", "b1"]}).size() == 6)
	sel.set_boards([{"id": "b1", "assembly": "a1"}, {"id": "b2", "assembly": "a1"}, {"id": "b3"}])
	sel.selection = ["b3"]
	var sids: Array = ctx.selection.ids(); sids.append("b1")
	check("selection.ids is a copy", sel.selection == ["b3"])
	var unit: Dictionary = ctx.selection.unit_of("b1")
	check("selection.unit_of from outside: the assembly", unit.get("kind") == "assembly" and unit["bodies"].size() == 2, unit)
	unit["bodies"].clear()
	check("selection.unit_of is a deep copy", ctx.selection.unit_of("b1")["bodies"].size() == 2)
	check("selection.assembly_of reads the map; '' for none", ctx.selection.assembly_of("b2") == "a1" and ctx.selection.assembly_of("b3") == "")
	var mem: Array = ctx.selection.members_of("a1"); mem.clear()
	check("selection.members_of is a copy", sel.members_of("a1").size() == 2)
	var chosen := ["b2"]
	ctx.selection.set_ids(chosen)
	chosen.append("b3")
	check("selection.set_ids sets the selection, from a copy", sel.selection == ["b2"], sel.selection)

	# --- the document: ids, append, snapshots, sync, remove ---
	var client = t["client"]
	check("document.next_id counts up per prefix", ctx.document.next_id("r").begins_with("r1_") and ctx.document.next_id("r").begins_with("r2_")
		and ctx.document.next_id("b").begins_with("b1_") and ctx.document.next_id("pp").begins_with("pp1_"))
	doc.ops = [{"id": "pp7", "type": "push_pull", "target": {"rect": "r1"}}]
	doc.restore_counters()
	check("document.next_id continues after restored counters", ctx.document.next_id("pp").begins_with("pp8_"))
	print("  (an unknown prefix: one ERROR line is expected next)")
	check("document.next_id: an unknown prefix gives \"\"", ctx.document.next_id("zz") == "")
	doc.ops = []
	var seq0: int = doc.seq
	var o := {"id": "r3", "type": "rect", "plane": {"origin": [0, 0, 0], "normal": [0, 0, 1]}, "corner": [0, 0], "size": [10, 20]}
	ctx.document.append(o)
	o["size"][0] = 999; o["id"] = "changed"
	check("document.append adds a copy", doc.ops.size() == 1 and doc.ops[0]["id"] == "r3" and doc.ops[0]["size"][0] == 10)
	check("document.append doesn't sync", doc.seq == seq0 and client.sent.is_empty())
	var snap: Dictionary = ctx.document.op("r3")
	snap["plane"]["normal"][2] = -1
	check("document.op is a deep copy; {} for none", doc.ops[0]["plane"]["normal"][2] == 1 and ctx.document.op("r9").is_empty())
	ctx.document.sync()
	check("document.sync sends once", doc.seq == seq0 + 1 and client.sent.filter(func(d): return d["cmd"] == "sync").size() == 1)
	var seen := {"ops": [], "removed": 0}
	doc.op_removed.connect(func(op): seen["ops"].append(op["id"]))
	doc.removed.connect(func(): seen["removed"] += 1)
	ctx.document.append({"id": "r4", "type": "rect"}); ctx.document.append({"id": "r5", "type": "rect"})
	var seq1: int = doc.seq
	ctx.document.remove("r4", false)
	check("document.remove without resync: op_removed only, no sync", seen["ops"] == ["r4"] and seen["removed"] == 0 and doc.seq == seq1)
	ctx.document.remove("r5")
	check("document.remove: op_removed, removed, then a sync", seen["ops"] == ["r4", "r5"] and seen["removed"] == 1 and doc.seq == seq1 + 1)
	ctx.document.remove("r9")
	check("document.remove of a missing op does nothing", seen["ops"].size() == 2 and seen["removed"] == 1)

	# --- picking: the grid, and snap / on_grid leave the tool's dictionary alone ---
	var infer = t["infer"]
	var grid := {"on": true}        # lambdas copy locals: a dictionary they share
	infer.grid_enabled = func() -> bool: return grid["on"]
	var p := {"hit": true, "point": Vector3(13, 27, 5), "normal": Vector3(0, 0, 1), "body": "", "rect": ""}
	var g: Dictionary = ctx.pick.on_grid(p)
	check("pick.on_grid snaps along the plane (not across it)", g["point"] == Vector3(10, 30, 5) and g["snap"] == "grid", g)
	check("pick.on_grid leaves the dictionary passed in as it was", p["point"] == Vector3(13, 27, 5) and not p.has("snap"))
	grid["on"] = false
	check("pick.on_grid with the grid off: unchanged", ctx.pick.on_grid(p)["point"] == Vector3(13, 27, 5) and not ctx.pick.grid_enabled())
	check("pick.grid_step / snap_radius are inference's", ctx.pick.grid_step() == Inference.GRID and ctx.pick.snap_radius() == Inference.SNAP_PX
		and Main.GRID == Inference.GRID and Main.SNAP_PX == Inference.SNAP_PX)
	check("pick.cursor with no cursor bound: zero", ctx.pick.cursor() == Vector2.ZERO)

	# --- ray and project on a tilted camera: the camera's own answers, in model units ---
	var cam := Camera3D.new()
	root.add_child.call_deferred(cam)
	await process_frame                 # the camera projects only once it's in the scene
	cam.fov = 45; cam.near = 0.005
	cam.look_at_from_position(Vector3(0.7, 0.55, 0.9), Vector3(0.1, 0.0, -0.05), Vector3.UP)
	cam.current = true
	infer.cam = cam
	var worst := 0.0
	var worst_dir := 0.0
	var round_trip := 0.0
	for s in [Vector2(100, 80), Vector2(576, 324), Vector2(1000, 600), Vector2(3, 640)]:
		var r: Dictionary = ctx.pick.ray(s)
		worst = maxf(worst, r["origin"].distance_to(Main.g2m(cam.project_ray_origin(s))))
		worst_dir = maxf(worst_dir, r["direction"].distance_to(Main.n_g2m(cam.project_ray_normal(s))))
		var q: Vector3 = r["origin"] + r["direction"] * 750.0           # 750 mm along the ray
		var back: Dictionary = ctx.pick.project(q)
		round_trip = maxf(round_trip, back["screen"].distance_to(s))
	check("pick.ray = the camera's ray converted to model mm", worst < 1e-6 and worst_dir < 1e-6, [worst, worst_dir])
	check("pick.project brings a point on the ray back to its pixel", round_trip < 0.01, round_trip)
	var front: Dictionary = ctx.pick.project(Vector3(100, 50, 0))
	var g_front := Main.m2g(Vector3(100, 50, 0))
	check("pick.project = the camera's unproject_position", front["screen"].distance_to(cam.unproject_position(g_front)) < 1e-4 and not front["behind"])
	var behind_pt: Vector3 = Main.g2m(cam.global_position + cam.global_transform.basis.z * 0.5)   # half a metre behind the eye
	check("pick.project says behind for a point behind the camera", ctx.pick.project(behind_pt)["behind"])

	# --- view, ui and paint with bound stand-ins ---
	var calls := []
	var overlay := MeshInstance3D.new(); var overlay_lines := MeshInstance3D.new(); made.append(overlay); made.append(overlay_lines)
	var added := []
	var mats := {"hover": StandardMaterial3D.new(), "profile": StandardMaterial3D.new()}
	var vparts: Dictionary = t["parts"].duplicate()
	vparts.merge({"overlay": overlay, "overlay_lines": overlay_lines, "materials": mats,
		"tri_mesh": func(tris, mat): calls.append(["tri", tris.size(), mat]); return ArrayMesh.new(),
		"lines": func(segs, col): calls.append(["lines", segs.size(), col]); var mi := MeshInstance3D.new(); mi.mesh = ArrayMesh.new(); made.append(mi); return mi,
		"show_marker": func(h): calls.append(["marker", h]); h["point"] = Vector3.ONE,
		"add_node": func(n): added.append(n),
		"refresh_tip": func(s): calls.append(["tip", s]),
		"new_board": func() -> bool: return true,
		"appearance": FakeAppearance.new(calls)})
	var v = ToolContext.new(vparts)
	v.view.preview(tri, "profile", PackedVector3Array([Vector3.ZERO, Vector3.ONE]), Color(0.1, 0.2, 0.6))
	check("view.preview draws tris in the style's material and the outline", overlay.mesh != null and overlay_lines.mesh != null
		and calls[0] == ["tri", 3, mats["profile"]] and calls[1] == ["lines", 2, Color(0.1, 0.2, 0.6)], calls)
	v.view.preview(tri, "hover")
	check("view.preview with no lines clears the outline", overlay.mesh != null and overlay_lines.mesh == null)
	v.view.clear_preview()
	check("view.clear_preview clears both", overlay.mesh == null and overlay_lines.mesh == null)
	var hit := {"hit": true, "point": Vector3(5, 5, 0), "snap": "endpoint"}
	v.view.marker(hit)
	check("view.marker passes a copy of the hit", hit["point"] == Vector3(5, 5, 0) and calls.back()[0] == "marker")
	v.view.selection_box(Vector2(10, 10), Vector2(50, 40)); v.view.selection_box(Vector2(10, 10), Vector2(60, 70))
	check("view.selection_box makes one box and follows the drag", added.size() == 1 and added[0] is Panel
		and added[0].size == Vector2(50, 60) and added[0].mouse_filter == Control.MOUSE_FILTER_IGNORE)
	v.view.clear_selection_box()
	v.view.face_highlight(tri)
	check("view.face_highlight makes its own node in the hover style", added.size() == 2 and added[1] is MeshInstance3D
		and added[1].mesh != null and calls.back() == ["tri", 3, mats["hover"]])
	v.view.clear_face_highlight()
	check("view.clear_face_highlight clears it", added[1].mesh == null)
	made.append(added[1])
	check("ui.new_board / paint.current_name read the bound options", v.ui.new_board() and v.paint.current_name() == "White oak")
	var targets := ["b1"]
	v.paint.apply(targets)
	check("paint.apply hands over a copy of the targets", targets == ["b1"] and calls.back()[0] == "paint")
	v.ui.refresh_tip(Vector2(3, 4))
	check("ui.refresh_tip calls the bound tooltip", calls.back() == ["tip", Vector2(3, 4)])
	check("a context with nothing bound answers quietly", ctx.paint.current_name() == "" and not ctx.ui.new_board())

	# The real paint owner, through the same capability used by Paint.
	var appearance := Appearance.new(doc)
	appearance.wood_library = {"white-oak": {"name": "White oak"}, "black-walnut": {"name": "Black walnut"}}
	appearance.wood_keys = ["white-oak", "black-walnut"]
	var paint_ctx := ToolContext.new({"appearance": appearance})
	var statuses := []
	appearance.status.connect(func(text): statuses.append([text, doc.seq, client.sent.size()]))
	check("paint defaults to white oak and rejects an unknown wood without changing it",
		paint_ctx.paint.current_name() == "White oak" and not appearance.select_wood("missing")
		and paint_ctx.paint.current_name() == "White oak")
	check("selecting wood changes the capability's name", appearance.select_wood("black-walnut")
		and paint_ctx.paint.current_name() == "Black walnut")
	var count: int = doc.ops.size()
	var before_seq: int = doc.seq
	var before_sent: int = client.sent.size()
	paint_ctx.paint.apply([])
	appearance.paint_material = "missing"
	paint_ctx.paint.apply(["b1"])
	check("empty targets and an invalid wood append nothing, send nothing and say nothing",
		doc.ops.size() == count and doc.seq == before_seq and client.sent.size() == before_sent and statuses.is_empty())
	appearance.select_wood("black-walnut")
	doc.in_flight = false
	var boards := ["b1", "b2"]
	paint_ctx.paint.apply(boards)
	boards.append("b3")
	var painted: Dictionary = doc.ops.back()
	check("paint appends one set_material op with copied targets and a document ID",
		doc.ops.size() == count + 1 and painted.type == "set_material" and painted.id.begins_with("sm1_")
		and painted.targets == ["b1", "b2"] and painted.material == "black-walnut", painted)
	check("paint syncs before emitting the unchanged readable status",
		doc.seq == before_seq + 1 and client.sent.size() > before_sent
		and statuses == [["Board 1, Board 2: Black walnut", doc.seq, client.sent.size()]], statuses)
	appearance.wood_library.clear()
	check("paint exposes an empty name when its library has no selection", paint_ctx.paint.current_name() == "")

	# Paint's real tool never receives Main, including assembly hover/click and empty space.
	appearance.wood_library = {"black-walnut": {"name": "Black walnut"}}
	var paint_infer := PaintInference.new()
	var paint_parts := vparts.duplicate()
	paint_parts["infer"] = paint_infer
	paint_parts["appearance"] = appearance
	var paint_tool = load("res://tools/paint_tool.gd").new()
	paint_tool.setup_context(ToolContext.new(paint_parts))
	paint_infer.hit = {"hit": true, "body": "b1"}
	paint_tool.mouse_moved(Vector2.ZERO)
	check("context-only Paint previews the hovered assembly and names the chosen wood",
		paint_tool.m == null and not paint_tool.uses_main() and overlay.mesh != null
		and calls.back() == ["tri", 3, mats["hover"]] and paint_tool.hint().begins_with("Paint with Black walnut:"))
	paint_tool.click(Vector2.ZERO)
	check("Paint click targets the whole assembly through the context",
		doc.ops.back().targets == ["b1", "b2"], doc.ops.back())
	count = doc.ops.size()
	paint_infer.hit = {"hit": false}
	paint_tool.mouse_moved(Vector2.ZERO)
	paint_tool.click(Vector2.ZERO)
	check("Paint clears hover and ignores a click off the model", overlay.mesh == null and doc.ops.size() == count)

	# --- geometry: the moved functions, and Main's wrappers give the same answers ---
	var v3 := Vector3(1.23456, -7.0004, 2.5)
	check("arr3 keeps its 0.001 rounding", Geo.arr3(v3) == [1.235, -7.0, 2.5] and Main.arr3(v3) == Geo.arr3(v3))
	var box_tris := Geo.prism(tri, Vector3(0, 0, 1), 5.0)
	check("Main's wrappers forward to tool_geometry.gd", Main.m2g(v3) == Geo.m2g(v3) and Main.g2m(v3) == Geo.g2m(v3)
		and Main._rect_pts(v3, Vector3.RIGHT, Vector3.UP, 2, 3) == Geo.rect_points(v3, Vector3.RIGHT, Vector3.UP, 2, 3)
		and Main._ekey(v3, Vector3.ZERO) == Geo.edge_key(v3, Vector3.ZERO) and Main._axis_vec(2) == Geo.axis_vector(2)
		and Main.feature_edges(box_tris) == Geo.feature_edges(box_tris) and Main.unique_verts(box_tris).size() == 6
		and Main._mirror_tris(tri, 0, 5.0) == Geo.mirror_triangles(tri, 0, 5.0)
		and Main.reflect_tris(tri, Vector3.ZERO, Vector3(1, 0, 0)) == Geo.reflect_tris(tri, Vector3.ZERO, Vector3(1, 0, 0))
		and Main.plane_basis(Vector3(0, 1, 0)) == Geo.plane_basis(Vector3(0, 1, 0)))
	check("rendering constants are the presenter's", Main.DEFAULT_BASE == Presenter.DEFAULT_BASE and Main.SNAP_COLORS == Presenter.SNAP_COLORS
		and Main.AXIS_COLORS == Presenter.AXIS_COLORS)

	# --- source: the context, geometry and inference never reach main.gd ---
	for path in ["res://tool_context.gd", "res://tool_geometry.gd", "res://inference.gd", "res://appearance.gd", "res://tools/paint_tool.gd"]:
		var code := code_only(FileAccess.get_file_as_string(path))
		var bad := []
		for needle in ['preload("res://main.gd")', 'load("res://main.gd")', "Main.", "Main)", ": Main", "infer.m", "\tm.", " m.", "(m."]:
			if code.contains(needle): bad.append(needle)
		check("%s has no main.gd reference in its code" % path.get_file(), bad.is_empty(), bad)

	cam.queue_free()
	for n in made: if is_instance_valid(n): n.free()
	print("TOOL CONTEXT TESTS: %d passed, %d failed" % [passed, failed])
	quit(1 if failed > 0 else 0)


static func _same(a: Array, b: Array) -> bool:
	var x := a.duplicate(); var y := b.duplicate()
	x.sort(); y.sort()
	return x == y


static func _minus(a: Array, b: Array) -> Array:
	return a.filter(func(e): return not b.has(e))
