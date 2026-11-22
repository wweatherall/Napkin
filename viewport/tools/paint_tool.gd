extends "res://tools/tool.gd"
## Paint: click a board to give it the wood picked in the Wood menu (T15). From outside, an assembly or an array
## row is painted whole; a linked board paints its family (they share one definition). T turns the grain.

const TOOL := {"id": "paint", "label": "Paint", "tip": "Paint (pick the wood in the Wood menu)", "key": KEY_NONE, "order": 20,
		"show_links": true}   # the toolbar, the Tools menu and the key (tool_registry.gd)


func hint() -> String:
	var e: Dictionary = m.wood_library.get(m.paint_material, {})
	return "Paint with %s: click a board. Pick the wood in the Wood menu; T turns a board's grain" % e.get("name", "wood")


func mouse_moved(screen: Vector2) -> void:
	var p := m.pick(screen)
	m.overlay.mesh = null
	if p.get("hit", false) and p.get("body", "") != "":
		m.overlay.mesh = m._tri_mesh(m.unit_tris(m.unit_of(p["body"])), m.mat_hover)


func click(screen: Vector2) -> void:
	var p := m.pick(screen)
	if not p.get("hit", false) or p.get("body", "") == "": return
	m.paint(m.unit_of(p["body"])["bodies"])
