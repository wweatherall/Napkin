extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 7. A rejection takes what built on it (Q7)
	await harness._fresh("reject", harness._plank(1, Vector3.ZERO, Vector3(300, 200, 18)))
	await harness._view(Vector3(300, 150, 30), -30, -40, 1.6)
	m.test_delay_ms = 600
	m.last_reject_note = ""
	m.force_reject_next = true
	await harness._rect(Vector3(400, 0, 0), Vector3(500, 100, 0), "100,100")
	await harness._push(Vector3(450, 50, 0), Vector3(450, 50, 50), "50")
	await harness._rect(Vector3(420, 20, 50), Vector3(480, 80, 50), "60,60")
	await harness._push(Vector3(450, 50, 50), Vector3(450, 50, 70), "20")
	await harness._rect(Vector3(0, 300, 0), Vector3(100, 400, 0), "100,100")
	await harness._push(Vector3(50, 350, 0), Vector3(50, 350, 30), "30")
	var t0 := Time.get_ticks_msec()
	while m.last_reject_note == "" and Time.get_ticks_msec() - t0 < 5000: await harness._frames(1)   # until the red wave's message (T48)
	await harness._wait_wave()
	var note: String = m.last_reject_note
	var ids: Array = m.ops.map(func(o): return o["id"])
	harness._ok("the rejected board and the 2 actions built on it go; the rest stays",
		ids == [harness.id("r1"), harness.id("pp1"), harness.id("r2"), harness.id("r4"), harness.id("nb2")] and harness._shown_ids() == [harness.id("b1"), harness.id("b3")], [ids, harness._shown_ids()])
	harness._ok("one message for all three", note.contains("2 actions that built on it"), note)
