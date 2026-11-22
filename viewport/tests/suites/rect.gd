extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# a rectangle started with a click ends with a click; started with press-and-drag, it ends on release
	await harness._view(Vector3(300, 200, 0), -30, -50, 1.4)
	m.set_tool("rect")
	# 1. press, drag, release
	await harness._drag_to(Vector3(0, 0, 0), 4)
	await harness._button(true)
	await harness._drag_to(Vector3(200, 100, 0), 12)
	await harness._button(false)
	var drag := harness._last_rect()
	# 2. click, move, click (no button held while moving)
	await harness._drag_to(Vector3(300, 0, 0), 6)
	await harness._button(true); await harness._button(false)
	await harness._drag_to(Vector3(400, 150, 0), 12)
	var before_second := harness._last_rect()
	await harness._button(true); await harness._button(false)
	var click := harness._last_rect()
	# 3. a click that wobbles 3 px between press and release is still a click
	await harness._drag_to(Vector3(0, 300, 0), 6)
	await harness._button(true)
	m.cursor2d.position += Vector2(3, 0)
	var wob := InputEventMouseMotion.new(); wob.position = m.cursor2d.position; wob.global_position = m.cursor2d.position
	Input.parse_input_event(wob); await harness._frames(1)
	await harness._button(false)
	await harness._drag_to(Vector3(100, 400, 0), 10)
	var wobble_waiting: bool = harness._last_rect()[0] == 2 and m.tools["rect"].state.get("active", false)
	await harness._button(true); await harness._button(false)
	var wobble := harness._last_rect()
	print("RECTTEST drag: %d rect, size %s (want 1, [200, 100]) | click: after first click and move %d rects (want 1), after second %d, size %s (want [100, 150]) | wobbly click still waiting %s, then size %s (want [100, 100])" % [
		drag[0], drag[1], before_second[0], click[0], click[1], wobble_waiting, wobble[1]])
	print("RECTTEST done")
	harness.get_tree().quit()
