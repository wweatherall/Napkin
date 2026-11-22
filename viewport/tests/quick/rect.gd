extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 1. Rectangle: click-click, press-drag-release, a wobbly click (I43)
	await harness._fresh("rect")
	await harness._view(Vector3(300, 200, 0), -30, -50, 1.4)
	m.set_tool("rect")
	await harness._drag_to(Vector3(0, 0, 0), 4); await harness._button(true)
	await harness._drag_to(Vector3(200, 100, 0), 9); await harness._button(false)
	var r: Array = harness._last_rect()
	harness._ok("press-drag-release draws a 200 x 100", r[0] == 1 and r[1] == [200.0, 100.0], r)
	await harness._drag_to(Vector3(300, 0, 0), 4); await harness._button(true); await harness._button(false)
	await harness._drag_to(Vector3(400, 150, 0), 9)
	harness._ok("after one click and a move, nothing is made yet", harness._last_rect()[0] == 1, harness._last_rect())
	await harness._button(true); await harness._button(false)
	r = harness._last_rect()
	harness._ok("the second click finishes a 100 x 150", r[0] == 2 and r[1] == [100.0, 150.0], r)
