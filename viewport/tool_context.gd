extends RefCounted
## What a tool may use (T88, docs/specs/T88-tool-interface.md): one ToolContext, built once by main.gd and handed
## to every tool by `setup_context(ctx)`. It has seven named capabilities, each a small adapter that keeps its
## owner private and answers with snapshots (copies a tool may change freely):
##   pick       inference.gd: what's under the cursor, snaps, axis and plane moves, camera rays and projection
##   model      presenter.gd: boards' triangles, profiles (rectangles, circles), stock frames, cuts
##   selection  selection.gd: the selection, context, assemblies, what a board stands for
##   document   document.gd: new ids, op snapshots, append, remove, sync
##   view       presenter / main.gd: previews, the snap marker, guides, the selection box, face highlight,
##              registering a drawn profile
##   ui         the measurements box, the tooltip, the rejection note, the window's New board option
##   paint      the wood the Paint tool puts on, and painting
## No adapter gives out Main, a controller, a scene node, a shared material or a live cache map (test_tool_context.gd
## checks each adapter's public members against an allowlist). Owners are passed in once, in `_init`; a part left
## out is null (the headless tests build contexts with stand-ins).
##
## The adapters arrived in step 0 (H051); Line and Paint now use only the context. Where a
## body still lives in main.gd (the mesh and line helpers, the marker, guides, the tooltip) the adapter
## calls it through one narrowly bound Callable; each body moves to its owner when its first tool migrates.
## Not yet here: view.present_draft (Push/Pull, step 5), view.mirror_preview (Move, step 6) and the Push/Pull
## test rejection filter (step 5): each arrives with the tool that first needs it.

var pick: PickCapability
var model: ModelCapability
var selection: SelectionCapability
var document: DocumentCapability
var view: ViewCapability
var ui: UiCapability
var paint: PaintCapability


func _init(parts := {}) -> void:
	"""parts: infer, pres, sel, doc, measure (owner objects); cursor, show_marker, hide_marker, guides, clear_guides,
	tri_mesh, lines, add_node, refresh_tip, clear_rejection, new_board (Callables); appearance (wood/paint owner);
	overlay, overlay_lines (nodes); materials (style -> Material). Anything missing is null / a no-op."""
	pick = PickCapability.new(parts)
	model = ModelCapability.new(parts)
	selection = SelectionCapability.new(parts)
	document = DocumentCapability.new(parts)
	view = ViewCapability.new(parts)
	ui = UiCapability.new(parts)
	paint = PaintCapability.new(parts)


const Inference := preload("res://inference.gd")


class _Capability extends RefCounted:
	static func _call(f, args := []) -> Variant:
		"""A bound Callable from main.gd, or nothing when a stand-in context left it out."""
		return f.callv(args) if f is Callable and f.is_valid() else null


# ---------------------------------------------------------------- picking and snapping (inference.gd)
class PickCapability extends _Capability:
	var _infer
	var _cursor

	func _init(parts: Dictionary) -> void:
		_infer = parts.get("infer")
		_cursor = parts.get("cursor")

	func hit(screen: Vector2) -> Dictionary:
		"""What's under the cursor: inference.gd pick (same keys; a profile wins over the face it lies on)."""
		return _infer.pick(screen)

	func snap(p: Dictionary, screen: Vector2) -> Dictionary:
		"""A point on a plane snapped (endpoint > midpoint > on edge, else the grid). Returns the answer; the
		dictionary passed in is left as it was."""
		return _infer.snap(p.duplicate(true), screen)

	func on_grid(p: Dictionary) -> Dictionary:
		"""A point on a plane put on the grid along it (unchanged while grid snap is off). p is left as it was."""
		return _infer.on_grid(p.duplicate(true))

	func point(screen: Vector2, exclude: String, plane := {}, with_rects := false, not_on := {}) -> Dictionary:
		return _infer.point(screen, exclude, plane, with_rects, not_on)

	func axis(screen: Vector2, anchor: Vector3, axes: Array, current: int) -> int:
		return _infer.axis(screen, anchor, axes, current)

	func axis_dest(screen: Vector2, ref: Vector3, ax: int, exclude := "") -> Variant:
		return _infer.axis_dest(screen, ref, ax, exclude)

	func plane_dest(screen: Vector2, ref: Vector3, n: Vector3) -> Variant:
		return _infer.plane_dest(screen, ref, n)

	func ray(screen: Vector2) -> Dictionary:
		"""{origin (mm), direction} of the camera ray through a screen point, in model space."""
		return _infer.ray(screen)

	func project(p: Vector3) -> Dictionary:
		"""{screen, behind} for a model point."""
		return _infer.project(p)

	func cursor() -> Vector2:
		"""Where the cursor is (in test mode, the simulated cursor)."""
		var c = _call(_cursor)
		return c if c is Vector2 else Vector2.ZERO

	func grid_enabled() -> bool:
		return bool(_infer.grid_enabled.call())

	func grid_step() -> float:
		return Inference.GRID

	func snap_radius() -> float:
		return Inference.SNAP_PX


# ---------------------------------------------------------------- model reads (presenter.gd)
class ModelCapability extends _Capability:
	var _pres

	func _init(parts: Dictionary) -> void:
		_pres = parts.get("pres")

	func body_ids() -> Array:
		return _pres.body_tris.keys()

	func has_body(id: String) -> bool:
		return _pres.body_tris.has(id)

	func triangles(id: String) -> PackedVector3Array:
		return PackedVector3Array(_pres.body_tris.get(id, PackedVector3Array()))

	func profile(id: String) -> Dictionary:
		"""A drawn rectangle or circle: {tris, n, on, pts, kind}; {} if there's none (a missing kind: a rectangle)."""
		return _pres.rects.get(id, {}).duplicate(true)

	func lines_on(body: String, normal: Vector3, point: Vector3) -> Array:
		"""Saved segment snapshots on this body/plane, including ids."""
		return _pres.lines_on(body, normal, point)

	func stock_frame(id: String) -> Dictionary:
		return _pres.stock_frames.get(id, {}).duplicate(true)

	func unit_triangles(unit: Dictionary) -> PackedVector3Array:
		"""Every triangle of what a click stands for (selection.unit_of's bodies)."""
		var t := PackedVector3Array()
		for b in unit.get("bodies", []): t.append_array(_pres.body_tris.get(b, PackedVector3Array()))
		return t

	func cut_at(body: String, p: Vector3) -> Dictionary:
		return _pres.cut_at(body, p).duplicate(true)

	func cut_triangles(body: String, op_id: String) -> PackedVector3Array:
		return PackedVector3Array(_pres.cut_tris(body, op_id))

	func circle_geometry(center: Vector3, normal: Vector3, radius: float) -> Dictionary:
		return _pres.circle_geometry(center, normal, radius).duplicate(true)


# ---------------------------------------------------------------- selection and context (selection.gd)
class SelectionCapability extends _Capability:
	var _sel

	func _init(parts: Dictionary) -> void:
		_sel = parts.get("sel")

	func ids() -> Array:
		return _sel.selection.duplicate()

	func context() -> String:
		return _sel.context

	func assembly_of(body: String) -> String:
		return String(_sel.body_assembly.get(body, ""))

	func members_of(assembly: String) -> Array:
		return _sel.members_of(assembly).duplicate()

	func unit_of(body: String) -> Dictionary:
		return _sel.unit_of(body).duplicate(true)

	func in_context(body: String) -> bool:
		return _sel.in_context(body)

	func is_hidden(body: String) -> bool:
		return _sel.is_hidden(body)

	func context_assembly() -> String:
		return _sel.context_assembly()

	func edit_blocked(body: String) -> bool:
		"""True (and selection says why in the status bar) when this board can't be edited from here."""
		return _sel.edit_blocked(body)

	func set_ids(ids: Array) -> void:
		"""Make these boards the selection (the spec's `set`: Object.set can't be overridden)."""
		_sel.set_selection(ids.duplicate())

	func enter(body: String) -> void:
		"""Enter the assembly or array this board is in (Select's double-click)."""
		_sel.enter_context_of(body)


# ---------------------------------------------------------------- the op list (document.gd)
class DocumentCapability extends _Capability:
	var _doc

	func _init(parts: Dictionary) -> void:
		_doc = parts.get("doc")

	func next_id(prefix: String) -> String:
		"""Allocate through the document's permanent reservation registry."""
		return _doc.next_id(prefix)

	func op(id: String) -> Dictionary:
		"""A copy of the op with this id; {} if there's none."""
		return _doc.op_of(id).duplicate(true)

	func append(o: Dictionary) -> void:
		"""Add an op (a copy of it) at the end. Doesn't sync: draw it, then call sync()."""
		_doc.ops.append(o.duplicate(true))

	func remove(id: String, resync := true) -> void:
		"""Take an op out (document.gd remove_op): op_removed fires; with resync, removed and a sync follow."""
		_doc.remove_op(id, resync)

	func sync() -> void:
		_doc.sync()


# ---------------------------------------------------------------- what's drawn (presenter / main.gd)
class ViewCapability extends _Capability:
	const STYLES := ["hover", "profile", "draft", "cut", "cut_highlight"]
	var _tri_mesh
	var _lines
	var _overlay
	var _overlay_lines
	var _materials: Dictionary
	var _show_marker
	var _hide_marker
	var _guides
	var _clear_guides
	var _add_node
	var _pres
	var _box: Panel
	var _face: MeshInstance3D

	func _init(parts: Dictionary) -> void:
		_tri_mesh = parts.get("tri_mesh"); _lines = parts.get("lines")
		_overlay = parts.get("overlay"); _overlay_lines = parts.get("overlay_lines")
		_materials = parts.get("materials", {})
		_show_marker = parts.get("show_marker"); _hide_marker = parts.get("hide_marker")
		_guides = parts.get("guides"); _clear_guides = parts.get("clear_guides")
		_add_node = parts.get("add_node")
		_pres = parts.get("pres")

	func preview(tris: PackedVector3Array, style: String, lines := PackedVector3Array(), line_color := Color(0.6, 0.35, 0)) -> void:
		"""Show the shared preview: tris in a style (hover, profile, draft, cut, cut_highlight) and outline lines.
		Each replaces what was there; an empty array clears it."""
		if not style in STYLES: push_error("ToolContext.view.preview: no style \"%s\"" % style)
		if is_instance_valid(_overlay):
			_overlay.mesh = null if tris.is_empty() else _call(_tri_mesh, [tris, _materials.get(style)])
		if is_instance_valid(_overlay_lines):
			_overlay_lines.mesh = null if lines.size() < 2 else _call(_lines, [lines, line_color]).mesh

	func clear_preview() -> void:
		"""Clear the preview and its outline (not the marker, guides or face highlight)."""
		if is_instance_valid(_overlay): _overlay.mesh = null
		if is_instance_valid(_overlay_lines): _overlay_lines.mesh = null

	func marker(hit: Dictionary) -> void:
		"""The snap marker at hit.point, coloured by hit.snap; hidden when hit.hit is false."""
		_call(_show_marker, [hit.duplicate(true)])

	func hide_marker() -> void:
		_call(_hide_marker)

	func guides(ref: Vector3, axis: int, plane_axis: int) -> void:
		"""Move's dotted axis line or plane grid through ref (-1: none)."""
		_call(_guides, [ref, axis, plane_axis])

	func clear_guides() -> void:
		_call(_clear_guides)

	func selection_box(start: Vector2, finish: Vector2) -> void:
		"""Select's drag box: blue dragging right (enclosed), green dragging left (crossing)."""
		if not is_instance_valid(_box):
			_box = Panel.new()
			_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
			_call(_add_node, [_box])
		var style := StyleBoxFlat.new()
		var color := Color(0.2, 0.45, 0.95) if finish.x >= start.x else Color(0.1, 0.65, 0.4)
		style.bg_color = Color(color, 0.12)
		style.border_color = color
		style.set_border_width_all(1)
		_box.add_theme_stylebox_override("panel", style)
		var rect := Rect2(start, finish - start).abs()
		_box.position = rect.position; _box.size = rect.size

	func clear_selection_box() -> void:
		if is_instance_valid(_box): _box.queue_free()
		_box = null

	func face_highlight(tris: PackedVector3Array) -> void:
		"""Push/Pull's highlight of the face an edge offers, in the hover style."""
		if not is_instance_valid(_face):
			_face = MeshInstance3D.new()
			_call(_add_node, [_face])
		_face.mesh = null if tris.is_empty() else _call(_tri_mesh, [tris, _materials.get("hover")])

	func clear_face_highlight() -> void:
		if is_instance_valid(_face): _face.mesh = null

	func register_profile(o: Dictionary) -> void:
		"""Draw a just-made rect or circle op as a pickable profile (presenter.gd register_rect)."""
		_pres.register_rect(o.duplicate(true))

	func register_line(o: Dictionary) -> void:
		"""Preserve a loose segment and its optional closed outline in the presenter."""
		_pres.register_line(o.duplicate(true))


# ---------------------------------------------------------------- measurements, tooltip, options
class UiCapability extends _Capability:
	var _measure
	var _refresh_tip
	var _clear_rejection
	var _new_board

	func _init(parts: Dictionary) -> void:
		_measure = parts.get("measure")
		_refresh_tip = parts.get("refresh_tip"); _clear_rejection = parts.get("clear_rejection")
		_new_board = parts.get("new_board")

	func typed_text() -> String:
		"""What's in the measurements box so far."""
		return _measure.vcb

	func refresh_measurements() -> void:
		_measure.update()

	func refresh_tip(screen: Vector2) -> void:
		_call(_refresh_tip, [screen])

	func clear_rejection() -> void:
		"""Clear the last rejection's status note (a new action starts)."""
		_call(_clear_rejection)

	func new_board() -> bool:
		"""The window's New board option (B, I04b)."""
		return _call(_new_board) == true


# ---------------------------------------------------------------- paint
class PaintCapability extends _Capability:
	var _appearance

	func _init(parts: Dictionary) -> void:
		_appearance = parts.get("appearance")

	func current_name() -> String:
		"""The name of the wood the Paint tool puts on ("" if none is picked)."""
		return _appearance.current_name() if _appearance != null else ""

	func apply(targets: Array) -> void:
		"""Paint these boards with the current wood (one set_material op; nothing for an empty list)."""
		if _appearance != null: _appearance.apply(targets.duplicate())
