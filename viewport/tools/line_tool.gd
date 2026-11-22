extends "res://tools/tool.gd"
## I58: click-click chain or a single press-drag-release segment. Model mm throughout.
const TOOL := {"id": "line", "label": "Line", "tip": "Line (L)", "key": KEY_L, "order": 37, "show_links": true}
var state := {}

func uses_main() -> bool: return false

func reset() -> void:
	state = {}
	press_reset()
	if ctx != null: ctx.view.clear_preview()

func busy() -> bool: return not state.is_empty()
func hint() -> String: return "Line: click points to chain lines, click the start to close; Esc ends; drag for one line"
func vcb_label() -> String: return "Length"
func vcb_value() -> String: return DISTANCE_DISPLAY_FORMAT % state.a.distance_to(state.b) if busy() else ""

func mouse_moved(screen: Vector2) -> void:
	press_moved(screen)
	if busy(): _drag(screen)
	else: ctx.view.marker(ctx.pick.snap(ctx.pick.hit(screen), screen))

func click(screen: Vector2) -> void:
	if busy():
		_drag(screen)
		_finish(false)
		return
	var p: Dictionary = ctx.pick.snap(ctx.pick.hit(screen), screen)
	if not p.get("hit", false): return
	var on: String = p.body
	if p.rect != "": on = ctx.model.profile(p.rect).on
	if ctx.selection.edit_blocked(on): return
	state = {"a": p.point, "b": p.point, "n": p.normal, "on": on, "chain": [p.point]}
	press_started(screen)

func release(screen: Vector2) -> void:
	if busy() and press_released().get("drag", false):
		_drag(screen)
		_finish(true)

func _drag(screen: Vector2) -> void:
	var ray: Dictionary = ctx.pick.ray(screen)
	var den: float = ray.direction.dot(state.n)
	if absf(den) < 1e-8: return
	var q: Vector3 = ray.origin + ray.direction * ((state.a - ray.origin).dot(state.n) / den)
	var p: Dictionary = ctx.pick.snap({"hit": true, "point": q, "normal": state.n, "body": state.on, "rect": ""}, screen)
	state.b = p.point
	state.snapped = p.get("snap", "") in ["endpoint", "midpoint", "on edge"]
	ctx.view.marker(p)
	ctx.view.preview(PackedVector3Array(), "profile", PackedVector3Array([state.a, state.b]), Color(0.1, 0.2, 0.6))
	ctx.ui.refresh_measurements()

func typed(txt: String) -> void:
	if not busy(): return
	var delta: Vector3 = state.b - state.a
	var length := float(txt)
	if not is_finite(length) or length < GEOMETRY_TOLERANCE_MM or delta.length() < GEOMETRY_TOLERANCE_MM: return
	state.b = state.a + delta.normalized() * length
	_commit(false)

func _finish(single: bool) -> void:
	if state.a.distance_to(state.b) < GEOMETRY_TOLERANCE_MM: return
	if pointer_distance_ok(state.a.distance_to(state.b), state.get("snapped", false)): _commit(single)

func _commit(single: bool) -> void:
	var a: Vector3 = state.a; var b: Vector3 = state.b
	var plane := {"origin": [a.x, a.y, a.z], "normal": [state.n.x, state.n.y, state.n.z]}
	if state.on != "": plane = {"on": {"body": state.on, "normal": plane.normal, "point": plane.origin}}
	var op := {"id": ctx.document.next_id("r"), "type": "line", "plane": plane, "end": [b.x, b.y, b.z]}
	var chain: Array = state.chain
	var closed := chain.size() >= 3 and b.distance_to(chain[0]) < GEOMETRY_TOLERANCE_MM
	if closed: op["outline"] = chain.map(func(v): return [v.x, v.y, v.z])
	ctx.ui.clear_rejection()
	ctx.document.append(op)
	ctx.view.register_line(op)
	if single or closed: reset()
	else:
		chain.append(b)
		state.a = b
		ctx.view.clear_preview()
	ctx.document.sync()
