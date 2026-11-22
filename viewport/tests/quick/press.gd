extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# Press and drag, or click and click, in Rectangle, Push/Pull and Move (I43); no hold-ups at the start (I44, I45)
	await harness._fresh("press", harness._plank(1, Vector3.ZERO, Vector3(300, 200, 18)) + harness._plank(2, Vector3(400, 0, 0), Vector3(100, 50, 18)))
	await harness._view(Vector3(150, 100, 20), -30, -40, 1.0)
	m.set_tool("rect")
	await harness._drag_to(Vector3(0, 0, 18), 4); await harness._button(true)
	await _nudge(Vector3(60, 60, 18), 12)
	var st: Dictionary = m.tools["rect"].state
	harness._ok("a rectangle started on a corner grows at once, not held at its own corner (I44)", st.get("du", 0.0) != 0.0 or st.get("dv", 0.0) != 0.0, [st.get("du"), st.get("dv")])
	await harness._button(false); await harness._key(KEY_ESCAPE)

	var n := m.ops.size()
	m.set_tool("push")
	await harness._drag_to(Vector3(150, 100, 18), 4); await harness._button(true)
	await harness._drag_to(Vector3(150, 100, 40), 6); await harness._button(false)
	harness._ok("Push/Pull: press, drag, let go makes the push on release (I43)", m.ops.size() == n + 1 and m.ops.back()["type"] == "push_pull" and not m.tools["push"].busy(), [m.ops.size() - n, m.ops.back()])
	await harness._wait_wave()
	n = m.ops.size()
	await harness._drag_to(Vector3(250, 150, 18), 4); await harness._press()
	await _nudge(Vector3(250, 150, -40), 4)
	var pd: Dictionary = m.tools["push"].state
	harness._ok("Push/Pull: a click goes on until the next click", m.ops.size() == n and m.tools["push"].busy(), [m.ops.size() - n])
	harness._ok("pushing in follows the cursor before it snaps to the back face (I45)", pd.get("dist", 0.0) < 0.0 and pd.get("dist", 0.0) > -18.0 and pd.get("snap", "") == "", [pd.get("dist"), pd.get("snap")])
	await harness._key(KEY_ESCAPE)

	m.set_tool("move")
	await harness._drag_to(Vector3(500, 50, 18), 4); await harness._button(true)
	await harness._drag_to(Vector3(500, 150, 18), 6); await harness._button(false)
	await harness._wait_wave()
	harness._ok("Move: press, drag, let go makes the move on release (I43)", not m.tools["move"].in_gesture() and harness._bbox("b2").slice(0, 2) != [400.0, 0.0], harness._bbox("b2"))
	n = m.ops.size()
	await harness._drag_to(Vector3(450, 25 + harness._bbox("b2")[1], 18), 4); await harness._press()
	await _nudge(Vector3(600, 300, 18), 20)
	harness._ok("Move: a click goes on until the next click", m.ops.size() == n and m.tools["move"].in_gesture(), [m.ops.size() - n])
	await harness._key(KEY_ESCAPE)


func _nudge(toward_m: Vector3, px: float) -> void:
	"""Move the cursor px pixels on screen toward a model point, in one step."""
	var a: Vector2 = m.cursor2d.position
	var s := a + (m.cam.unproject_position(Main.m2g(toward_m)) - a).normalized() * px
	var ev := InputEventMouseMotion.new(); ev.position = s; ev.global_position = s
	Input.parse_input_event(ev)
	m.cursor2d.position = s
	await harness._frames(1)
