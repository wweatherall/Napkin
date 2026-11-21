extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


# The quick test's sections, in the order one session runs them; --quick-lane=N runs lane N only, in a window
# with its own worker, so tools/quicktest.sh runs the lanes side by side (T49). A section starts from _fresh, so
# any lane order works, except reject -> trackpad -> models -> worker, which carry on from each other.
const QUICK_LANES := [
	["hash", "rect", "push", "faces", "snap", "move", "hole"],
	["linked", "assembly", "mirrorgroup", "faceplane", "wood", "hide"],
	["undo", "reject", "trackpad", "models", "worker", "properties"],
]


func run() -> void:
	harness.quick = true
	Engine.time_scale = 5.0                       # waves and breathing run 5x faster; the checks don't depend on them
	var t_start := Time.get_ticks_msec()
	while not m.opened: await harness._frames(1)

	var lane := -1
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--quick-lane="): lane = int(a.substr(13))
	var sections: Array = []
	for i in QUICK_LANES.size():
		if lane < 0 or lane == i + 1: sections.append_array(QUICK_LANES[i])
	for s in sections:
		var section = load("res://tests/quick/%s.gd" % s).new()
		section.harness = harness
		await section.run()

	harness._q_lap("")
	var laps := ""
	for t in harness._q_times: laps += "%s %.1f  " % [t[0], t[1] / 1000.0]
	print("QUICK timing (s): " + laps + "| opening fresh models %.1f" % (harness._q_fresh_ms / 1000.0))
	Engine.time_scale = 1.0
	print("QUICK %d passed, %d failed in %.1f s" % [harness._q[0], harness._q[1], (Time.get_ticks_msec() - t_start) / 1000.0])
	harness.get_tree().quit(1 if harness._q[1] > 0 else 0)
