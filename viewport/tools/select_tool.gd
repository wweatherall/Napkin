extends "res://tools/tool.gd"
## Select (Space): click a board (from outside, its whole assembly or array row) to select it; Shift-click adds or
## removes; click empty space to clear. Double-click enters an assembly or an array (T20); Esc leaves.

const TOOL := {"id": "select", "label": "Select", "tip": "Select (Space)", "key": KEY_SPACE, "order": 10}   # the toolbar, the Tools menu and the key (tool_registry.gd)


func uses_main() -> bool: return false


func hint() -> String:
	return "Select: click or drag a box (right = enclosed, left = crossing), Shift adds. Double-click an assembly or array to edit inside it. Cmd+G makes an assembly"


func mouse_moved(screen: Vector2) -> void:
	if pressed and screen.distance_to(anchor) > 6.0:
		dragging = true
		_show_box(screen)
		return
	var p := ctx.pick.hit(screen)
	ctx.view.clear_preview()
	if p.get("hit", false) and p.get("body", "") != "":
		ctx.view.preview(ctx.model.unit_triangles(ctx.selection.unit_of(p["body"])), "hover")


func click(screen: Vector2) -> void:
	anchor = screen; pressed = true; dragging = false
	before = ctx.selection.ids()
	additive = Input.is_key_pressed(KEY_SHIFT)
	var p := ctx.pick.hit(screen)
	var unit := ctx.selection.unit_of(p.get("body", "")) if p.get("hit", false) else {}
	if unit.is_empty():
		if not additive: ctx.selection.set_ids([])
		return
	var ids: Array = unit["bodies"]
	var sel: Array = ctx.selection.ids()
	if additive:
		var all_in := ids.all(func(b): return sel.has(b))
		for b in ids:
			if all_in: sel.erase(b)
			elif not sel.has(b): sel.append(b)
	else:
		sel = ids.duplicate()
	ctx.selection.set_ids(sel)


func double_click(screen: Vector2) -> void:
	reset()
	var p := ctx.pick.hit(screen)
	if p.get("hit", false): ctx.selection.enter(p.get("body", ""))


var anchor := Vector2.ZERO
var pressed := false
var dragging := false
var additive := false
var before: Array = []


func in_gesture() -> bool:
	return dragging


func reset() -> void:
	if dragging: ctx.selection.set_ids(before)
	pressed = false; dragging = false
	ctx.view.clear_selection_box()


func _show_box(screen: Vector2) -> void:
	ctx.view.selection_box(anchor, screen)


func release(screen: Vector2) -> void:
	if not pressed: return
	if screen.distance_to(anchor) > 6.0: dragging = true
	if dragging:
		var ids := box_ids(anchor, screen)
		if additive:
			for b in before:
				if not ids.has(b): ids.append(b)
		ctx.selection.set_ids(ids)
	pressed = false; dragging = false
	ctx.view.clear_selection_box()


func box_ids(start: Vector2, finish: Vector2) -> Array:
	var rect := Rect2(start, finish - start).abs()
	var crossing := finish.x < start.x
	var units := {}
	for b in ctx.model.body_ids():
		if not ctx.selection.in_context(b) or ctx.selection.is_hidden(b): continue
		var unit := ctx.selection.unit_of(b)
		var key: String = str(unit["bodies"])
		units[key] = unit
	var ids: Array = []
	for unit in units.values():
		var contained := true
		var intersects := false
		var any := false
		for b in unit["bodies"]:
			if ctx.selection.is_hidden(b): continue
			var tris: PackedVector3Array = ctx.model.triangles(b)
			for i in range(0, tris.size(), 3):
				var triangle := PackedVector2Array()
				for j in 3:
					var point := ctx.pick.project(tris[i + j])
					if point["behind"]:
						contained = false
						continue
					triangle.append(point["screen"])
				if triangle.size() != 3: continue
				any = true
				for v in triangle:
					if not rect.has_point(v): contained = false
				if _triangle_crosses(rect, triangle): intersects = true
		if any and (intersects if crossing else contained):
			for b in unit["bodies"]:
				if not ctx.selection.is_hidden(b) and not ids.has(b): ids.append(b)
	return ids


static func _triangle_crosses(rect: Rect2, tri: PackedVector2Array) -> bool:
	for v in tri:
		if rect.has_point(v): return true
	var corners := PackedVector2Array([rect.position, Vector2(rect.end.x, rect.position.y), rect.end,
									 Vector2(rect.position.x, rect.end.y)])
	for corner in corners:
		if Geometry2D.is_point_in_polygon(corner, tri): return true
	for i in 3:
		for j in 4:
			if Geometry2D.segment_intersects_segment(tri[i], tri[(i + 1) % 3], corners[j], corners[(j + 1) % 4]) != null:
				return true
	return false
