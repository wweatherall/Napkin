extends RefCounted
## Selection, context and sibling highlights (A33b), `pres.selection_view`: draws selection, ghosting, hidden boards, mirror plane and siblings from selection.gd.
##
## Owned and instantiated by presenter.gd, which keeps forwarders for main.gd, save_prompts.gd and tests
## (`plane_node`, `mat_ghost`, `mat_hidden_ghost`, `_sel_overlay`, `apply_context`, `show_selection`, `show_siblings`, `forget_siblings`).
## Entry points: apply_context, show_selection, show_siblings, forget_siblings.

const Geo := preload("res://tool_geometry.gd")

var pres                            # presenter.gd
var plane_node: MeshInstance3D      # the mirror plane, shown inside an entered mirror group (A11b)
var _sel_overlay: MeshInstance3D
var _sibling_overlay: MeshInstance3D
var _sibling_key := ""              # the siblings now tinted ("-": out of date, draw again)
var mat_ghost: StandardMaterial3D
var mat_hidden_ghost: StandardMaterial3D


func _init(p) -> void:
	pres = p


func _overlay_node() -> MeshInstance3D:
	var mi := MeshInstance3D.new(); pres.m.add_child(mi)
	return mi


func apply_context() -> void:
	"""Grey out, and make unpickable, every board outside the one you're in. Hidden boards (T28) are left out
	altogether, or shown ghosted (and pickable, to unhide them) with View > Hidden geometry."""
	if mat_ghost == null:
		mat_ghost = StandardMaterial3D.new()
		mat_ghost.albedo_color = Color(0.75, 0.75, 0.78, 0.35)
		mat_ghost.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	if mat_hidden_ghost == null:
		mat_hidden_ghost = StandardMaterial3D.new()
		mat_hidden_ghost.albedo_color = Color(0.55, 0.6, 0.7, 0.25)
		mat_hidden_ghost.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	pres.sel.refresh_hidden()
	for node in pres.m.bodies_root.get_children():
		if not node.has_meta("body_mesh"): continue
		var bid := String(node.name)
		var hidden: bool = pres.sel.body_hidden.has(bid)
		if pres.sel.body_deleted.has(bid) or (hidden and not pres.sel.show_hidden):
			node.visible = false; node.set_meta("ss_hidden", true)
		elif node.get_meta("ss_hidden", false):
			node.visible = true; node.set_meta("ss_hidden", false)
		var inside: bool = not pres.sel.body_deleted.has(bid) and pres.sel.in_context(bid) and (not hidden or pres.sel.show_hidden)
		var comp_sib: bool = not pres.sel.body_deleted.has(bid) and pres.sel.is_context_sibling(bid) and (not hidden or pres.sel.show_hidden)
		if inside:
			node.material_override = mat_hidden_ghost if hidden else null
		elif comp_sib:
			node.material_override = pres.m.mat_sibling
		else:
			node.material_override = mat_ghost
		var edges: MeshInstance3D = node.get_meta("edges")
		edges.visible = inside or comp_sib
		for c in node.get_children():
			if c is StaticBody3D: c.collision_layer = 1 if inside else 0
	for collider in pres.m.drafts_root.find_children("*", "StaticBody3D", true, false):
		var bid := String(collider.get_meta("body_id", ""))
		if pres.sel.body_deleted.has(bid):
			collider.set_meta("ss_deleted", true)
			collider.collision_layer = 0
			collider.get_parent().visible = false
		elif collider.get_meta("ss_deleted", false):
			collider.remove_meta("ss_deleted")
			collider.collision_layer = 1
			collider.get_parent().visible = true
	show_mirror_plane()


func show_mirror_plane() -> void:
	"""Inside a mirror group: its plane, as a soft sheet a little bigger than the pair."""
	if plane_node == null: plane_node = _overlay_node()
	plane_node.mesh = null
	var plane: Array = pres.sel.mirror_plane_of_context()
	if plane.is_empty(): return
	var lo := Vector3(INF, INF, INF); var hi := -lo
	for b in pres.sel.members_of(pres.sel.context_assembly()):
		for q in pres.body_tris.get(b, PackedVector3Array()):
			lo = lo.min(q); hi = hi.max(q)
	var p0: Vector3 = plane[0]; var n: Vector3 = plane[1]
	var basis: Array = Geo.plane_basis(n)
	var c := (lo + hi) * 0.5
	c -= n * (c - p0).dot(n)                       # the middle of the pair, on the plane
	var r := maxf((hi - lo).length() * 0.6, 50.0)
	var u: Vector3 = basis[0] * r; var v: Vector3 = basis[1] * r
	var quad := PackedVector3Array()
	for q in [c - u - v, c + u - v, c + u + v, c - u - v, c + u + v, c - u + v]: quad.append(q)
	plane_node.mesh = pres.tri_mesh(quad, pres.m.mat_plane)


func show_selection() -> void:
	if _sel_overlay == null: _sel_overlay = _overlay_node()
	var t := PackedVector3Array()
	for b in pres.sel.selection: t.append_array(pres.body_tris.get(b, PackedVector3Array()))
	_sel_overlay.mesh = pres.tri_mesh(t, pres.m.mat_selected) if not t.is_empty() else null


func show_siblings(sib: Array) -> void:
	"""Linked copies of the board you're pointing at, tinted (T12)."""
	var key := ",".join(sib)
	if key == _sibling_key: return
	_sibling_key = key
	if _sibling_overlay == null: _sibling_overlay = _overlay_node()
	_sibling_overlay.mesh = null
	var tris := PackedVector3Array()
	for b in sib: tris.append_array(pres.body_tris.get(b, PackedVector3Array()))
	if not tris.is_empty():
		_sibling_overlay.mesh = pres.tri_mesh(tris, pres.m.mat_sibling)


func forget_siblings() -> void:
	_sibling_key = "-"
