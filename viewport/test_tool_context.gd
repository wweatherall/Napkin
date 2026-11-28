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
	var region := {"outline": [Vector3.ZERO], "holes": [[Vector3.ONE]], "lines": ["rline"]}
	func drawn_region(_source: PackedVector3Array, _body: String, _normal: Vector3, _point: Vector3) -> Dictionary:
		return region
	func register_line(o: Dictionary) -> void:
		received = o.duplicate(true)
		o.end[0] = 999


class DraftScene:
	var drafts_root := Node3D.new()
	var bodies_root := Node3D.new()
	var mat_hover := StandardMaterial3D.new()
	var mat_draft := StandardMaterial3D.new()
	var mat_cut := StandardMaterial3D.new()
	var mat_rect := StandardMaterial3D.new()
	var mat_plane := StandardMaterial3D.new()
	var overlay: MeshInstance3D
	var overlay_lines: MeshInstance3D
	var overlay_bias := 0.0
	var line_scale := 1.0
	var test_mode := true


class FakeAppearance:
	var calls: Array
	func _init(log: Array) -> void: calls = log
	func current_name() -> String: return "White oak"
	func apply(targets: Array) -> void:
		calls.append(["paint", targets.duplicate()])
		targets.append("x")


class PaintInference:
	var hit := {}
	var projection
	func project(p: Vector3) -> Dictionary: return projection.project(p)
	func pick(_screen: Vector2) -> Dictionary: return hit.duplicate(true)


class CircleInference:
	## Circle's stand-in: a fixed hit, snap/on_grid hand back the point (grid snap), a straight-down ray.
	var hit := {}
	var ray_at := Vector3.ZERO
	var snap_kind := "grid"
	var snap_at: Variant = null
	var calls: Array = []
	func pick(_screen: Vector2) -> Dictionary: return hit.duplicate(true)
	func snap(p: Dictionary, _screen: Vector2) -> Dictionary:
		calls.append("snap"); p["snap"] = snap_kind
		if snap_at != null: p["point"] = snap_at
		return p
	func on_grid(p: Dictionary) -> Dictionary:
		calls.append("on_grid"); p["snap"] = "grid"; return p
	func ray(_screen: Vector2) -> Dictionary: return {"origin": ray_at + Vector3(0, 0, 500), "direction": Vector3(0, 0, -1)}
	func snap_radius() -> float: return 10.0
	func cursor() -> Vector2: return Vector2.ZERO


class ProfilePresenter:
	## Circle's presenter stand-in: the real circle_geometry, register_rect recorded (no Main to draw with).
	var real
	var rects := {}
	var registered: Array = []
	func circle_geometry(c: Vector3, n: Vector3, r: float) -> Dictionary: return real.circle_geometry(c, n, r)
	func register_rect(o: Dictionary) -> void:
		registered.append(o.duplicate(true))
		rects[o["id"]] = {"tris": PackedVector3Array(), "n": Vector3(0, 0, 1), "on": "board-under", "pts": PackedVector3Array(), "kind": o["type"]}
		o["radius"] = -1.0


class FakeMeasure:
	var updates := 0
	var vcb := ""
	var unit_spec := "mm:1"
	func update() -> void: updates += 1
	func format_length(mm: float, down := false) -> String: return load("res://units.gd").format_length(mm, unit_spec, 0, down)


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
# (Object.set can't be overridden).
const ALLOW := {
	"pick": ["hit", "hit_board", "drawing_hit", "snap", "on_grid", "point", "axis", "axis_dest", "plane_dest", "ray", "project", "cursor",
			 "grid_enabled", "grid_step", "snap_radius"],
	"model": ["body_ids", "drawing_ids", "drawing", "has_body", "triangles", "profile", "stock_frame", "unit_triangles", "cut_at",
			  "cut_triangles", "circle_geometry", "polygon_geometry", "lines_on", "drawn_region"],
	"selection": ["ids", "context", "assembly_of", "members_of", "unit_of", "in_context", "is_hidden",
				  "context_assembly", "edit_blocked", "set_ids", "enter"],
	"document": ["next_id", "op", "is_last", "append", "remove", "sync"],
	"view": ["preview", "mirror_preview", "clear_preview", "marker", "hide_marker", "guides", "clear_guides", "selection_box",
			 "clear_selection_box", "face_highlight", "clear_face_highlight", "register_profile", "register_line", "present_draft"],
	"ui": ["typed_text", "clear_typed", "format_length", "refresh_measurements", "refresh_tip", "clear_rejection", "show_rejection", "refresh_hint", "show_status", "tool_active", "new_board"],
	"paint": ["current_name", "apply"],
}


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

	var region := line_ctx.model.drawn_region(PackedVector3Array(), "b1", Vector3.UP, Vector3.ZERO)
	region.outline.clear(); region.holes[0].clear(); region.lines.clear()
	check("model.drawn_region returns independent outlines, holes and line IDs",
		line_pres.region == {"outline": [Vector3.ZERO], "holes": [[Vector3.ONE]], "lines": ["rline"]})

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
	var joined: PackedVector3Array = ctx.model.unit_triangles({"bodies": ["b1", "b9", "b1"]})
	check("model.unit_triangles joins the unit's boards", joined.size() == 6)
	joined[0] = Vector3.ONE
	check("model.unit_triangles is a snapshot from its presenter owner", pres.body_tris.b1[0] == Vector3.ZERO
		and pres.unit_tris({"bodies": ["b1"]}) == tri)
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
	check("document.is_last matches only the latest op", ctx.document.is_last("r3") and not ctx.document.is_last("r9") and not ctx.document.is_last(""))
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
	Inference.grid = 25.0; Inference.snap_px = 20.0
	check("pick.grid_step / snap_radius follow live inference values", ctx.pick.grid_step() == 25.0 and ctx.pick.snap_radius() == 20.0)
	Inference.grid = Inference.GRID; Inference.snap_px = Inference.SNAP_PX
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
	var scene := DraftScene.new()
	made.append(scene.drafts_root); made.append(scene.bodies_root)
	pres.m = scene
	var mats := {"hover": StandardMaterial3D.new(), "profile": StandardMaterial3D.new()}
	var vparts: Dictionary = t["parts"].duplicate()
	vparts.merge({"overlay": overlay, "overlay_lines": overlay_lines, "materials": mats,
		"tri_mesh": func(tris, mat): calls.append(["tri", tris.size(), mat]); return ArrayMesh.new(),
		"line_mesh": func(segs, col): calls.append(["lines", segs.size(), col]); return ArrayMesh.new(),
		"show_marker": func(h): calls.append(["marker", h]); h["point"] = Vector3.ONE,
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
	var panels: Array = pres.get_children().filter(func(n): return n is Panel)
	check("view.selection_box reuses a presenter-owned box and follows the drag", panels.size() == 1
		and panels[0].size == Vector2(50, 60) and panels[0].mouse_filter == Control.MOUSE_FILTER_IGNORE)
	var panel: Panel = panels[0]
	var style: StyleBoxFlat = panel.get_theme_stylebox("panel")
	check("window box keeps blue fill and one-pixel border", style.border_color == Color(0.2, 0.45, 0.95)
		and style.bg_color == Color(Color(0.2, 0.45, 0.95), 0.12) and style.border_width_left == 1)
	v.view.selection_box(Vector2(60, 70), Vector2(10, 10))
	check("crossing box keeps green and normalized bounds", panel.position == Vector2(10, 10) and panel.size == Vector2(50, 60)
		and panel.get_theme_stylebox("panel").border_color == Color(0.1, 0.65, 0.4))
	v.view.clear_selection_box()
	check("view.clear_selection_box releases the presenter's Panel", panel.is_queued_for_deletion())
	v.view.face_highlight(tri)
	var face: MeshInstance3D = pres.get_children().filter(func(n): return n is MeshInstance3D)[0]
	v.view.face_highlight(tri)
	check("view.face_highlight reuses a presenter-owned node with the hover material",
		face.mesh.surface_get_material(0) == scene.mat_hover and pres.get_children().filter(func(n): return n is MeshInstance3D).size() == 1)
	v.view.clear_face_highlight()
	check("view.clear_face_highlight clears it", face.mesh == null)
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
		overlay.mesh != null
		and calls.back() == ["tri", 3, mats["hover"]] and paint_tool.hint().begins_with("Paint with Black walnut:"))
	paint_tool.click(Vector2.ZERO)
	check("Paint click targets the whole assembly through the context",
		doc.ops.back().targets == ["b1", "b2"], doc.ops.back())
	count = doc.ops.size()
	paint_infer.hit = {"hit": false}
	paint_tool.mouse_moved(Vector2.ZERO)
	paint_tool.click(Vector2.ZERO)
	check("Paint clears hover and ignores a click off the model", overlay.mesh == null and doc.ops.size() == count)

	# Select also runs without Main: real selection/presenter and real camera projection.
	paint_infer.projection = infer
	var select = load("res://tools/select_tool.gd").new()
	select.setup_context(ToolContext.new(paint_parts))
	paint_infer.hit = {"hit": true, "body": "b1"}
	select.mouse_moved(Vector2.ZERO)
	select.click(Vector2.ZERO)
	select.release(Vector2.ZERO)
	check("context-only Select previews and selects the assembly", overlay.mesh != null and sel.selection == ["b1", "b2"])
	select.double_click(Vector2.ZERO)
	check("Select double-click enters the assembly through the context", sel.context == "assembly:a1")
	sel.context = ""
	paint_infer.hit = {"hit": false}
	select.mouse_moved(Vector2.ZERO)
	select.click(Vector2.ZERO); select.release(Vector2.ZERO)
	check("Select clears hover and selection off the model", overlay.mesh == null and sel.selection.is_empty())
	var screen_tri := PackedVector3Array()
	for pixel in [Vector2(100, 100), Vector2(200, 100), Vector2(150, 200)]:
		var ray: Dictionary = ctx.pick.ray(pixel)
		screen_tri.append(ray.origin + ray.direction * 500.0)
	pres.body_tris = {"b1": screen_tri, "b2": screen_tri, "b3": screen_tri}
	var start := Vector2(90, 90); var finish := Vector2(210, 210)
	check("Select window contains the whole assembly and independent board", select.box_ids(start, finish) == ["b1", "b2", "b3"])
	check("Select small window excludes partial triangles", select.box_ids(Vector2(145, 135), Vector2(155, 145)).is_empty())
	check("Select crossing includes triangle interiors without vertices", select.box_ids(Vector2(155, 135), Vector2(145, 145)) == ["b1", "b2", "b3"])
	sel.context = "assembly:a1"
	sel.set_selection(["b3"])
	select.click(start); select.mouse_moved(finish)
	check("Select drag shows the box through the presenter", select.in_gesture()
		and pres.get_children().any(func(n): return n is Panel and not n.is_queued_for_deletion()))
	select.reset()
	check("Select reset restores the pre-drag selection", sel.selection == ["b3"] and not select.in_gesture())
	select.click(start); select.additive = true; select.mouse_moved(finish); select.release(finish)
	check("Select additive box retains an earlier board outside the box units", sel.selection == ["b1", "b2", "b3"])
	sel.context = "assembly:a1"
	check("Select box excludes boards outside the entered context", select.box_ids(start, finish) == ["b1", "b2"])
	sel.body_hidden = {"b2": true}
	check("Select box excludes hidden assembly members", select.box_ids(start, finish) == ["b1"])
	sel.show_hidden = true; sel.body_deleted = {"b2": true}
	check("Select box excludes deleted members even with hidden geometry on", select.box_ids(start, finish) == ["b1"])
	sel.context = ""; sel.body_hidden = {}; sel.body_deleted = {}; sel.show_hidden = false
	pres.body_tris = {"b3": screen_tri.duplicate()}
	pres.body_tris.b3[0] = behind_pt
	check("Select skips triangles with a vertex behind the camera in either box direction",
		select.box_ids(start, finish).is_empty() and select.box_ids(finish, start).is_empty())
	pres.body_tris.b3.append_array(screen_tri)
	check("behind-camera vertices reject enclosure but allow a separate visible crossing triangle",
		select.box_ids(start, finish).is_empty() and select.box_ids(finish, start) == ["b3"])

	# Circle runs without Main too: centre click, radius from the ray, the op through the document (T88 step 3).
	var cinfer := CircleInference.new()
	var cpres := ProfilePresenter.new(); cpres.real = pres
	var cparts: Dictionary = vparts.duplicate()
	var cmeasure := FakeMeasure.new()
	cparts.merge({"infer": cinfer, "pres": cpres, "measure": cmeasure}, true)
	var circle = load("res://tools/circle_tool.gd").new()
	circle.setup_context(ToolContext.new(cparts))
	cinfer.hit = {"hit": true, "point": Vector3(10, 20, 0), "normal": Vector3(0, 0, 1), "body": "", "rect": ""}
	circle.mouse_moved(Vector2.ZERO)
	check("context-only Circle shows the snap marker before the centre", calls.back()[0] == "marker" and not circle.busy())
	circle.click(Vector2.ZERO)
	cinfer.ray_at = Vector3(10 + 30.25, 20, 0)
	circle.mouse_moved(Vector2(50, 0))
	check("Circle's radius comes from the ray on the centre's plane", circle.busy() and absf(circle.state["radius"] - 30.25) < 1e-4
		and circle.vcb_value() == "~30 mm" and cmeasure.updates == 1, [circle.state, circle.vcb_value()])
	check("Circle previews its disc in the profile style with a 64-segment outline", overlay.mesh != null and overlay_lines.mesh != null
		and calls.any(func(c): return c == ["tri", 62 * 3, mats["profile"]]) and calls.any(func(c): return c == ["lines", 128, Color(0.1, 0.2, 0.6)]))
	var c_count: int = doc.ops.size(); var c_seq: int = doc.seq
	circle.click(Vector2(50, 0))
	var cop: Dictionary = doc.ops.back()
	check("Circle commits one circle op through the document: next id, the exact radius, the plane",
		doc.ops.size() == c_count + 1 and cop["type"] == "circle" and String(cop["id"]).begins_with("r")
		and absf(cop["radius"] - 30.25) < 1e-4 and cop["plane"] == {"origin": [10.0, 20.0, 0.0], "normal": [0.0, 0.0, 1.0]}, cop)
	check("Circle registers a copy as a profile, clears its preview and syncs", cpres.registered.size() == 1
		and cpres.registered[0]["id"] == cop["id"] and cop["radius"] > 0 and overlay.mesh == null and overlay_lines.mesh == null
		and doc.seq == c_seq + 1 and not circle.busy())
	cinfer.hit = {"hit": true, "point": Vector3(12, 22, 0), "normal": Vector3(0, 0, 1), "body": "", "rect": cop["id"]}
	circle.click(Vector2.ZERO)
	check("Circle on a drawn profile reads the profile's board through ctx.model", circle.busy() and circle.state["on"] == "board-under")
	cinfer.ray_at = Vector3(12, 22, 0); cinfer.snap_kind = "endpoint"
	circle.mouse_moved(Vector2.ZERO)
	cinfer.snap_kind = "grid"
	check("Circle at its own centre falls back to the grid (no zero circle)", cinfer.calls.back() == "on_grid" and circle.state["radius"] < 0.001)
	circle.typed("-12.5")
	check("Circle's typed radius is taken whole and positive", absf(doc.ops.back()["radius"] - 12.5) < 1e-9 and not circle.busy())
	sel.context = ""
	cinfer.hit = {"hit": true, "point": Vector3(0, 0, 5), "normal": Vector3(0, 0, 1), "body": "b1", "rect": ""}
	circle.click(Vector2.ZERO)
	check("Circle won't start on an assembly's board from outside (ctx.selection.edit_blocked)", not circle.busy())

	# Rectangle uses the same context without Main, preserving its plane and signed dimension rules.
	var rinfer := CircleInference.new()
	var rpres := ProfilePresenter.new(); rpres.real = pres
	var rmeasure := FakeMeasure.new()
	var rparts: Dictionary = vparts.duplicate()
	rparts.merge({"infer": rinfer, "pres": rpres, "measure": rmeasure}, true)
	var rect = load("res://tools/rect_tool.gd").new()
	rect.setup_context(ToolContext.new(rparts))
	rinfer.hit = {"hit": false}
	var r_count: int = doc.ops.size()
	rect.click(Vector2.ZERO)
	check("context-only Rectangle ignores empty space", not rect.busy() and doc.ops.size() == r_count)
	rinfer.hit = {"hit": true, "point": Vector3(10, 20, 0), "normal": Vector3(0, 0, 1), "body": "", "rect": ""}
	rect.mouse_moved(Vector2.ZERO)
	check("Rectangle shows the snap marker before its first corner", calls.back()[0] == "marker")
	rect.click(Vector2.ZERO)
	rinfer.ray_at = Vector3(40.25, 60.125, 0)
	rinfer.snap_kind = "endpoint"; rinfer.snap_at = Vector3(10, 60, 0)
	rect.mouse_moved(Vector2(50, 50))
	check("Rectangle ignores a snap leaving one side zero and falls back to the cursor grid",
		rinfer.calls.back() == "on_grid" and not rect.state["point_snap"]
		and absf(rect.state["du"] - 30.25) < 1e-5 and absf(rect.state["dv"] - 40.125) < 1e-5, rect.state)
	check("Rectangle previews two triangles and four edges in the profile style and updates dimensions",
		overlay.mesh != null and overlay_lines.mesh != null and rmeasure.updates == 1
		and rect.vcb_label() == "Dimensions" and rect.vcb_value() == "~30 mm, ~40 mm"
		and calls.any(func(c): return c == ["tri", 6, mats["profile"]])
		and calls.any(func(c): return c == ["lines", 8, Color(0.1, 0.2, 0.6)]))
	var r_seq: int = doc.seq
	rect.click(Vector2(50, 50))
	var rop: Dictionary = doc.ops.back()
	check("Rectangle commits one op with exact unrounded dimensions and a document id",
		doc.ops.size() == r_count + 1 and rop["type"] == "rect" and String(rop["id"]).begins_with("r")
		and rop["size"] == [30.25, 40.125] and rop["corner"] == [0.0, 0.0]
		and rop["plane"] == {"origin": [10.0, 20.0, 0.0], "normal": [0.0, 0.0, 1.0]}, rop)
	check("Rectangle registers a profile copy, clears its preview and syncs",
		rpres.registered == [rop] and not rop.has("radius") and not rect.in_gesture() and rect.busy()
		and overlay.mesh == null and overlay_lines.mesh == null and doc.seq == r_seq + 1)

	# A tilted profile resolves its supporting board and preserves the drag quadrant for typed sizes.
	rinfer.snap_at = null; rinfer.snap_kind = "grid"
	var rn := Vector3(0, 0.6, 0.8)
	var rb := Geo.plane_basis(rn)
	var origin := Vector3(12, 22, 5)
	rinfer.hit = {"hit": true, "point": origin, "normal": rn, "body": "", "rect": rop["id"]}
	rect.click(Vector2.ZERO)
	check("Rectangle on a profile reads its supporting board through the model", rect.state["on"] == "board-under")
	rinfer.ray_at = origin - rb[0] * 12.5 + rb[1] * 7.25
	rect.mouse_moved(Vector2(50, 50))
	check("Rectangle ray intersects the tilted drawing plane in its local basis",
		absf(rect.state["du"] + 12.5) < 1e-4 and absf(rect.state["dv"] - 7.25) < 1e-4, rect.state)
	rect.typed("-12.375,0.125")
	rop = doc.ops.back()
	check("Rectangle typed fractional and sub-millimetre sizes keep the quadrant and exact plane",
		rop["size"] == [12.375, 0.125] and rop["corner"] == [-12.375, 0.0]
		and rop["plane"] == {"on": {"body": "board-under", "normal": Geo.arr3(rn), "point": Geo.arr3(origin)}}
		and not rect.in_gesture() and rect.busy(), rop)
	rinfer.hit = {"hit": true, "point": Vector3.ZERO, "normal": Vector3(0, 0, 1), "body": "b1", "rect": ""}
	rect.click(Vector2.ZERO)
	check("Rectangle won't start on an assembly board from outside", not rect.busy())

	_test_push()
	_test_move()
	_test_profile_contracts()

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
	for path in ["res://tool_context.gd", "res://tool_geometry.gd", "res://inference.gd", "res://appearance.gd", "res://tools/paint_tool.gd", "res://tools/select_tool.gd", "res://tools/circle_tool.gd", "res://tools/rect_tool.gd", "res://tools/line_tool.gd", "res://tools/push_tool.gd", "res://tools/move_tool.gd", "res://tools/tool.gd"]:
		var code := code_only(FileAccess.get_file_as_string(path))
		var bad := []
		for needle in ['preload("res://main.gd")', 'load("res://main.gd")', "Main.", "Main)", ": Main", "infer.m", "\tm.", " m.", "(m."]:
			if code.contains(needle): bad.append(needle)
		check("%s has no main.gd reference in its code" % path.get_file(), bad.is_empty(), bad)

	cam.queue_free()
	for n in made: if is_instance_valid(n): n.free()
	print("TOOL CONTEXT TESTS: %d passed, %d failed" % [passed, failed])
	quit(1 if failed > 0 else 0)


func _test_push() -> void:
	var t := make()
	var pres: Presenter = t.pres
	var scene := DraftScene.new()
	pres.m = scene
	made.append(scene.drafts_root); made.append(scene.bodies_root)
	var infer := PaintInference.new()
	var parts: Dictionary = t.parts.duplicate()
	parts.merge({"infer": infer, "push_filter": pres.draft_tests.filter}, true)
	var ctx := ToolContext.new(parts)
	var push = load("res://tools/push_tool.gd").new()
	push.setup_context(ctx)
	var normal := Vector3(0, 0, 1)
	var plane := {"origin": [0, 0, 0], "normal": [0, 0, 1]}
	var rect := {"id": "profile", "type": "rect", "plane": plane, "corner": [0, 0], "size": [10, 10]}
	ctx.document.append(rect)
	ctx.view.register_profile(rect)
	var profile_node: Node = pres.drafts.profile
	infer.hit = {"hit": true, "point": Vector3(4, 4, 0), "normal": normal, "rect": "profile", "body": ""}
	push.click(Vector2.ZERO)
	push.typed("6.25")
	var op: Dictionary = t.doc.ops.back()
	var board: String = op.body
	var predicted := Geo.prism(ctx.model.profile("profile").tris, normal, 6.25)
	var surface: MeshInstance3D = pres.drafts[op.id].get_child(0)
	var colliders := surface.find_children("*", "StaticBody3D", true, false)
	check("context-only Push makes a board, consumes the profile and syncs",
		not push.busy() and op.distance == 6.25 and op.target.rect == "profile"
		and not pres.drafts.has("profile") and profile_node.is_queued_for_deletion() and t.doc.seq == 1)
	check("new draft is pickable with its vertices and edges installed together",
		colliders.size() == 1 and colliders[0].get_meta("body_id") == board and colliders[0].collision_layer == 1
		and ctx.model.triangles(board) == predicted and pres.body_verts[board] == Geo.unique_verts(predicted)
		and pres.body_edges[board] == Geo.feature_edges(predicted))
	var w: Dictionary = pres.op_waves[op.id]
	check("new draft owns the wave and records bounds", w.bodies == [board] and w.links[0][0] == surface
		and w.links[0][1] == surface.get_child(0) and w.og == Geo.m2g(Vector3(4, 4, 6.25))
		and pres.draft_tests.bounds[board] == [[0.0, 0.0, 0.0], [10.0, 10.0, 6.25]])
	var root: Node = pres.drafts[op.id]
	pres.drop_confirmed_drafts({})
	check("confirmation frees the whole draft root", root.is_queued_for_deletion() and not pres.drafts.has(op.id))

	var confirmed := MeshInstance3D.new()
	confirmed.name = board
	confirmed.mesh = pres.tri_mesh(predicted, scene.mat_rect)
	var edges := MeshInstance3D.new()
	confirmed.add_child(edges); confirmed.set_meta("edges", edges)
	scene.bodies_root.add_child(confirmed)
	infer.hit.point.z = 6.25
	for distance in [2.0, -6.25]:
		var id := "join" if distance > 0 else "cut"
		var profile := rect.duplicate(true)
		profile.id = id
		profile.plane = {"on": {"body": board, "normal": [0, 0, 1], "point": [0, 0, 6.25]}}
		ctx.document.append(profile); ctx.view.register_profile(profile)
		infer.hit.rect = id
		push.click(Vector2.ZERO); push.typed(str(distance))
		var edit: Dictionary = t.doc.ops.back()
		var patch: MeshInstance3D = pres.drafts[edit.id].get_child(0)
		check("context-only %s edits the existing board and waves on its confirmed mesh" % id,
			not edit.has("body") and edit.target == {"rect": id} and edit.distance == distance
			and edit.get("through", false) == (distance < 0) and pres.op_waves[edit.id].links[0][0] == confirmed
			and patch.mesh.surface_get_material(0) == (scene.mat_cut if distance < 0 else scene.mat_draft)
			and patch.find_children("*", "StaticBody3D", true, false).is_empty() and ctx.model.triangles(board) == predicted)

	pres.draft_tests.reject_next = true
	infer.hit.rect = ""; infer.hit.body = board
	push.click(Vector2.ZERO); push.typed("1")
	check("a face push leaves the profile rejection armed", pres.draft_tests.reject_next and t.doc.ops.back().target.has("face"))
	rect.id = "rejected-profile"
	ctx.document.append(rect); ctx.view.register_profile(rect)
	infer.hit.rect = rect.id; infer.hit.body = ""; infer.hit.point.z = 0
	push.click(Vector2.ZERO); push.typed("3")
	var rejected: Dictionary = t.doc.ops.back()
	var doomed: Node = pres.drafts[rejected.id]
	check("only the submitted profile target changes on forced rejection", not pres.draft_tests.reject_next
		and rejected.target == {"rect": "r_missing"} and not pres.drafts.has(rect.id))
	pres.op_waves[rejected.id].state = "rejected"
	pres.drop_confirmed_drafts({})
	check("the rejected draft survives confirmation until rollback", pres.drafts.has(rejected.id) and not doomed.is_queued_for_deletion())
	t.doc.op_removed.connect(func(removed): pres.forget_op(removed, t.doc.ops, {}))
	ctx.document.remove(rejected.id)
	check("rollback removes the op, wave, draft root and all three prediction caches", ctx.document.op(rejected.id).is_empty()
		and doomed.is_queued_for_deletion() and not pres.drafts.has(rejected.id) and not pres.op_waves.has(rejected.id)
		and not ctx.model.has_body(rejected.body) and not pres.body_edges.has(rejected.body) and not pres.body_verts.has(rejected.body))

	# A multi-piece draft exercises replacement and verifies that caller-owned arrays remain snapshots.
	var tris := predicted.duplicate()
	var piece := {"tris": tris, "style": "draft", "line_color": Color.RED, "body_id": board, "replace": true}
	var wave := {"origin": Vector3.ZERO, "tris": tris, "is_new": false, "bodies": [board], "attach": "drafts"}
	ctx.view.present_draft({"id": "replacement", "type": "move"}, [piece, piece.merged({"body_id": ""}, true)], wave)
	piece.tris[0] = Vector3.INF
	wave.bodies.clear()
	check("present_draft hides replaced meshes and attaches ordered pieces under one root",
		not confirmed.visible and pres.drafts.replacement.get_child_count() == 2 and pres.op_waves.replacement.links.size() == 2
		and ctx.model.triangles(board) == predicted and pres.op_waves.replacement.bodies == [board])


func _test_move() -> void:
	var t := make()
	var scene := DraftScene.new()
	var pres: Presenter = t.pres
	pres.m = scene
	made.append(scene.drafts_root); made.append(scene.bodies_root)
	scene.overlay = MeshInstance3D.new()
	scene.overlay_lines = MeshInstance3D.new()
	made.append(scene.overlay); made.append(scene.overlay_lines)
	var infer := CircleInference.new()
	var ctx := ToolContext.new(t.parts.merged({"infer": infer}, true))
	var move = load("res://tools/move_tool.gd").new()
	move.setup_context(ctx)
	var tris := PackedVector3Array([Vector3.ZERO, Vector3.RIGHT, Vector3.UP])
	var corners := PackedVector3Array([Vector3.ZERO, Vector3.RIGHT, Vector3.RIGHT + Vector3.UP, Vector3.UP])
	for axis in [-1, 0, 1, 2]:
		ctx.view.mirror_preview(tris, corners, axis)
		var mesh := scene.overlay.mesh
		var color: Color = Presenter.AXIS_COLORS[axis] if axis >= 0 else Color(0.85, 0.35, 0.6, 0.3)
		check("mirror preview draws the ghost, plane and perimeter for axis %d" % axis,
			mesh.get_surface_count() == 2 and mesh.surface_get_material(0) == scene.mat_draft
			and mesh.surface_get_material(1).albedo_color.is_equal_approx(color)
			and mesh.surface_get_array_len(1) == 6 and scene.overlay_lines.mesh.surface_get_array_len(0) == 28)
	ctx.view.guides(Vector3.ZERO, 1, -1)
	check("axis guide draws its 200 dashes", pres.guides.mesh.surface_get_array_len(0) == 800)
	ctx.view.guides(Vector3.ZERO, -1, 1)
	check("plane guide draws its grid", pres.guides.mesh.surface_get_array_len(0) == 104)
	ctx.view.clear_guides()
	check("clearing guides removes the guide mesh", pres.guides.mesh == null)

	var confirmed := MeshInstance3D.new()
	confirmed.name = "board"
	confirmed.mesh = pres.tri_mesh(tris, scene.mat_rect)
	var edges := MeshInstance3D.new()
	confirmed.add_child(edges); confirmed.set_meta("edges", edges)
	scene.bodies_root.add_child(confirmed)
	pres.body_tris.board = tris
	infer.hit = {"hit": true, "body": "board", "normal": Vector3.BACK, "point": Vector3.ZERO}
	move.click(Vector2.ZERO)
	move.commit_move(Vector3.RIGHT * 10)
	var op: Dictionary = t.doc.ops.back()
	check("context-only Move replaces the board at its destination",
		op.targets == ["board"] and not confirmed.visible and pres.body_tris.board[0] == Vector3.RIGHT * 10
		and pres.op_waves[op.id].links[0][0] == pres.drafts[op.id].get_child(0))

	move.copy = true
	move.click(Vector2.ZERO)
	move.commit_move(Vector3.UP * 20, 2)
	op = t.doc.ops.back()
	var wave: Dictionary = pres.op_waves[op.id]
	check("context-only copy array gives each copy a draft and ends the wave at the last offset",
		op.new_ids.size() == 2 and wave.bodies == op.new_ids and wave.links.size() == 2
		and wave.og == Geo.m2g(Vector3.UP * 40) and pres.draft_tests.bounds[op.new_ids[1]][0] == [10.0, 40.0, 0.0])

	move.click(Vector2.ZERO)
	move.commit_mirror(Vector3.ZERO, Vector3.RIGHT)
	op = t.doc.ops.back()
	check("context-only mirror copy reflects the board into its reserved body",
		op.type == "mirror" and op.has("group") and op.targets == ["board"]
		and pres.body_tris[op.new_ids[0]] == Geo.reflect_tris(pres.body_tris.board, Vector3.ZERO, Vector3.RIGHT)
		and pres.op_waves[op.id].bodies == op.new_ids)

	pres.body_cuts.board = [{"kind": "cut", "op": "hole", "lo": Vector3.ZERO, "hi": Vector3.ONE}]
	move.click(Vector2.ZERO)
	move.commit_move(Vector3.RIGHT * 5, 2)
	op = t.doc.ops.back()
	wave = pres.op_waves[op.id]
	var patch: MeshInstance3D = pres.drafts[op.id].get_child(0)
	check("context-only cut array keeps its wave on the confirmed board and its edges",
		op.cut == {"body": "board", "op": "hole"} and op.count == 2 and pres.drafts[op.id].get_child_count() == 2
		and patch.mesh.surface_get_material(0) == scene.mat_cut and patch.get_child_count() == 1
		and wave.body == "board" and wave.links.size() == 1 and wave.links[0][0] == confirmed
		and wave.links[0][1] == edges and wave.og == Geo.m2g(Vector3.RIGHT * 10) and t.doc.seq == 4)


func _test_profile_contracts() -> void:
	var contracts_path := ProjectSettings.globalize_path("res://").path_join("../tests/op_contracts.json")
	var contracts = JSON.parse_string(FileAccess.get_file_as_string(contracts_path))
	check("H191: tests/op_contracts.json loads for tool and draft checks", contracts is Dictionary and not contracts.is_empty())
	if not (contracts is Dictionary): return

	var t := make()
	var pres: Presenter = t.pres
	var scene := DraftScene.new()
	pres.m = scene
	made.append(scene.drafts_root); made.append(scene.bodies_root)
	var infer := CircleInference.new()
	var measure := FakeMeasure.new()
	var parts: Dictionary = t.parts.merged({"infer": infer, "measure": measure}, true)
	var ctx := ToolContext.new(parts)

	# 1. Tool check: each of the 5 profile tools commits an op with every required field and no undocumented field.
	var tool_ops := {}

	var circle = load("res://tools/circle_tool.gd").new()
	circle.setup_context(ctx)
	infer.hit = {"hit": true, "point": Vector3(0, 0, 0), "normal": Vector3(0, 0, 1), "body": "", "rect": ""}
	circle.click(Vector2.ZERO)
	infer.ray_at = Vector3(20, 0, 0)
	circle.mouse_moved(Vector2(50, 0))
	circle.click(Vector2(50, 0))
	tool_ops["circle"] = t.doc.ops.back()

	var rect = load("res://tools/rect_tool.gd").new()
	rect.setup_context(ctx)
	infer.hit = {"hit": true, "point": Vector3(0, 0, 0), "normal": Vector3(0, 0, 1), "body": "", "rect": ""}
	rect.click(Vector2.ZERO)
	infer.ray_at = Vector3(20, 30, 0)
	rect.mouse_moved(Vector2(50, 50))
	rect.click(Vector2(50, 50))
	tool_ops["rect"] = t.doc.ops.back()

	var polygon = load("res://tools/polygon_tool.gd").new()
	polygon.setup_context(ctx)
	infer.hit = {"hit": true, "point": Vector3(0, 0, 0), "normal": Vector3(0, 0, 1), "body": "", "rect": ""}
	polygon.click(Vector2.ZERO)
	infer.ray_at = Vector3(20, 0, 0)
	polygon.mouse_moved(Vector2(50, 0))
	polygon.click(Vector2(50, 0))
	tool_ops["polygon"] = t.doc.ops.back()

	var line = load("res://tools/line_tool.gd").new()
	line.setup_context(ctx)
	infer.hit = {"hit": true, "point": Vector3(0, 0, 0), "normal": Vector3(0, 0, 1), "body": "", "rect": ""}
	line.click(Vector2.ZERO)
	infer.ray_at = Vector3(20, 0, 0)
	line.mouse_moved(Vector2(50, 0))
	line.click(Vector2(50, 0))
	tool_ops["line"] = t.doc.ops.back()

	var arc = load("res://tools/arc_tool.gd").new()
	arc.setup_context(ctx)
	infer.hit = {"hit": true, "point": Vector3(0, 0, 0), "normal": Vector3(0, 0, 1), "body": "", "rect": ""}
	arc.click(Vector2.ZERO)
	infer.ray_at = Vector3(20, 0, 0)
	arc.mouse_moved(Vector2(50, 0))
	arc.click(Vector2(50, 0))
	infer.ray_at = Vector3(10, 5, 0)
	arc.mouse_moved(Vector2(25, 25))
	arc.click(Vector2(25, 25))
	tool_ops["arc"] = t.doc.ops.back()

	for op_type in ["circle", "rect", "polygon", "line", "arc"]:
		var contract: Dictionary = contracts.get(op_type, {})
		var op: Dictionary = tool_ops[op_type]
		var fields: Dictionary = contract.get("fields", {})
		var missing_req := []
		for fname in fields:
			if fields[fname].get("required", true) and not op.has(fname):
				missing_req.append(fname)
		var extra := []
		for k in op:
			if k != "id" and k != "type" and not fields.has(k):
				extra.append(k)
		check("H191: %s tool commits op matching contract (missing=%s extra=%s)" % [op_type, missing_req, extra],
			op.get("type", "") == op_type and missing_req.is_empty() and extra.is_empty(), op)

		# 2. Draft check: register_rect / register_line draws both required-only and full ops from the contract.
		for include_optional: bool in [false, true]:
			var tag := "full" if include_optional else "required"
			var draft_id := "draft_%s_%s" % [op_type, tag]
			var draft_op := _build_contract_op(draft_id, contract, include_optional)
			if op_type in ["line", "arc"]:
				pres.register_line(draft_op)
				var has_line := pres.drafts.has("line:" + draft_id)
				var has_outline: bool = (not include_optional) or op_type != "line" or pres.drafts.has(draft_id)
				check("H191: register_line draws %s %s op" % [tag, op_type], has_line and has_outline, draft_op)
			else:
				pres.register_rect(draft_op)
				check("H191: register_rect draws %s %s op" % [tag, op_type], pres.drafts.has(draft_id), draft_op)

	# 3. H192: Appearance builders (set_material, turn_grain) match their contracts.
	var Appearance = load("res://appearance.gd")
	var app = Appearance.new(t.doc)
	app.wood_library["white-oak"] = {"key": "white-oak", "name": "White Oak"}
	app.paint_material = "white-oak"
	app.set_boards([{"id": "b1", "material": "white-oak"}])
	var app_start: int = t.doc.ops.size()
	app.apply(["b1"])
	app.turn_grain("b1")
	var app_ops := {}
	for i in range(app_start, t.doc.ops.size()):
		app_ops[t.doc.ops[i]["type"]] = t.doc.ops[i]
	for op_type in ["set_material", "turn_grain"]:
		var contract: Dictionary = contracts.get(op_type, {})
		var op: Dictionary = app_ops.get(op_type, {})
		var fields: Dictionary = contract.get("fields", {})
		var missing_req := []
		for fname in fields:
			if fields[fname].get("required", true) and not op.has(fname):
				missing_req.append(fname)
		var extra := []
		for k in op:
			if k != "id" and k != "type" and not fields.has(k):
				extra.append(k)
		check("H192: appearance %s matches contract (missing=%s extra=%s)" % [op_type, missing_req, extra],
			op.get("type", "") == op_type and missing_req.is_empty() and extra.is_empty(), op)


static func _sample_contract_value(spec: Dictionary, fname: String) -> Variant:
	var kind: String = spec.get("kind", "")
	if kind == "Plane":
		return {"origin": [0, 0, 0], "normal": [0, 0, 1]}
	if kind == "number":
		return maxf(float(spec.get("min", 1.0)) * 10.0, 10.0)
	if kind == "integer":
		return int(spec.get("min", 1))
	if kind == "bool":
		return not bool(spec.get("default", false))
	if kind == "[number, number]":
		return spec.get("default", [5.0, 5.0]).duplicate()
	if kind == "[number, number, number]":
		if fname == "mid":
			return [5.0, 5.0, 0.0]
		return [10.0, 0.0, 0.0]
	if kind == "[[number, number, number]]":
		return [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0]]
	return null


static func _build_contract_op(op_id: String, contract: Dictionary, include_optional: bool) -> Dictionary:
	var op := {"id": op_id, "type": contract["type"]}
	var fields: Dictionary = contract.get("fields", {})
	for fname in fields:
		var spec: Dictionary = fields[fname]
		if spec.get("required", true) or include_optional:
			op[fname] = _sample_contract_value(spec, fname)
	return op


static func _same(a: Array, b: Array) -> bool:
	var x := a.duplicate(); var y := b.duplicate()
	x.sort(); y.sort()
	return x == y


static func _minus(a: Array, b: Array) -> Array:
	return a.filter(func(e): return not b.has(e))
