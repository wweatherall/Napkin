extends "res://tools/tool.gd"
## Paint: click a board to give it the wood picked in the Wood menu (T15). From outside, an assembly or an array
## row is painted whole; a linked board paints its family (they share one definition). T turns the grain.

const TOOL := {"id": "paint", "label": "Paint", "tip": "Paint (pick the wood in the Wood menu)", "key": KEY_NONE, "order": 20,
		"show_links": true}   # the toolbar, the Tools menu and the key (tool_registry.gd)


func uses_main() -> bool:
	return false


func hint() -> String:
	var name := ctx.paint.current_name()
	return "Paint with %s: click a board. Pick the wood in the Wood menu; T turns a board's grain" % (name if name != "" else "wood")


func mouse_moved(screen: Vector2) -> void:
	var p := ctx.pick.hit(screen)
	ctx.view.clear_preview()
	if p.get("hit", false) and p.get("body", "") != "":
		ctx.view.preview(ctx.model.unit_triangles(ctx.selection.unit_of(p["body"])), "hover")


func click(screen: Vector2) -> void:
	var p := ctx.pick.hit(screen)
	if not p.get("hit", false) or p.get("body", "") == "": return
	ctx.paint.apply(ctx.selection.unit_of(p["body"])["bodies"])
