extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# T3: the freeze when FreeCAD's answer arrives, on 40 panels with 24 holes each; one more hole in one panel
	m.cursor2d.visible = false
	var o := [{"id": "r1", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, 0, 0]}, "size": [1200, 600]},
		{"id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": 18, "body": "b1"}]
	for k in 24:
		o.append({"id": "r%d" % (k + 2), "type": "rect", "plane": {"on": {"body": "b1", "normal": [0, 0, 1],
			"point": [50 + (k % 8) * 140, 50 + (k / 8) * 180, 18]}}, "size": [20, 20]})
		o.append({"id": "pp%d" % (k + 2), "type": "push_pull", "target": {"rect": "r%d" % (k + 2)}, "distance": -18})
	var copies := []
	for i in 39: copies.append("b%d" % (i + 2))
	o.append({"id": "mv1", "type": "move", "targets": ["b1"], "vector": [0, 0, 100], "copy": true, "count": 39, "new_ids": copies})
	m.ops = o
	m.counters["r"] = 25; m.counters["pp"] = 25; m.counters["b"] = 40; m.counters["mv"] = 1
	m.sync(); await harness._wait_confirm()
	await harness._view(Vector3(600, 300, 2000), -30, -20, 6.0)
	await harness._frames(20)
	var worst := []
	for trial in 3:
		var n: int = m.counters["r"] + 1
		m.ops.append({"id": "r%d" % n, "type": "rect", "plane": {"on": {"body": "b1", "normal": [0, 0, 1],
			"point": [120 + trial * 140, 140, 18]}}, "size": [20, 20]})
		m.ops.append({"id": "pp%d" % n, "type": "push_pull", "target": {"rect": "r%d" % n}, "distance": -18})
		m.counters["r"] = n; m.counters["pp"] = n
		m.sync()
		var w := 0
		var t := Time.get_ticks_usec()
		while m.dirty or m.in_flight:
			await harness.get_tree().process_frame
			var now := Time.get_ticks_usec(); w = maxi(w, now - t); t = now
		for f in 5:
			await harness.get_tree().process_frame
			var now := Time.get_ticks_usec(); w = maxi(w, now - t); t = now
		worst.append(w / 1000.0)
	print("PERFTEST %d boards on screen | worst frame while each of 3 answers is applied: %s ms" % [m.body_tris.size(), worst])
	print("PERFTEST done")
	harness.get_tree().quit()
