extends "res://tools/tool.gd"
## Select (Space): click a board (from outside, its whole assembly or array row) to select it; Shift-click adds or
## removes; click empty space to clear. Double-click enters an assembly or an array (T20); Esc leaves.


func hint() -> String:
	return "Select: click a board, Shift-click to add. Double-click an assembly or array to edit inside it. Cmd+G makes an assembly"


func mouse_moved(screen: Vector2) -> void:
	var p := m.pick(screen)
	m.overlay.mesh = null
	if p.get("hit", false) and p.get("body", "") != "":
		m.overlay.mesh = m._tri_mesh(m.unit_tris(m.unit_of(p["body"])), m.mat_hover)


func click(screen: Vector2) -> void:
	var p := m.pick(screen)
	var unit := m.unit_of(p.get("body", "")) if p.get("hit", false) else {}
	var additive := Input.is_key_pressed(KEY_SHIFT)
	if unit.is_empty():
		if not additive: m.set_selection([])
		return
	var ids: Array = unit["bodies"]
	var sel: Array = m.selection.duplicate()
	if additive:
		var all_in := ids.all(func(b): return sel.has(b))
		for b in ids:
			if all_in: sel.erase(b)
			elif not sel.has(b): sel.append(b)
	else:
		sel = ids.duplicate()
	m.set_selection(sel)


func double_click(screen: Vector2) -> void:
	var p := m.pick(screen)
	if p.get("hit", false): m.enter_context_of(p.get("body", ""))
