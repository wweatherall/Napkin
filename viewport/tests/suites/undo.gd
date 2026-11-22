extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# T10: undo shows the remembered state at once, even past FreeCAD's 20-step history (it rebuilds meanwhile)
	m.cursor2d.visible = false
	await harness._view(Vector3(600, 25, 0), -30, -35, 2.5)
	var seen := {0: []}            # ops count -> boards on screen once FreeCAD confirmed it
	var full := []
	for i in 11:
		m.ops.append({"id": "r%d" % (i + 1), "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [120.0 * i, 0, 0]}, "size": [100, 50]})
		m.sync(); await harness._wait_confirm(); seen[m.ops.size()] = harness._shown_ids()
		m.ops.append({"id": "pp%d" % (i + 1), "type": "push_pull", "target": {"rect": "r%d" % (i + 1)}, "distance": 18 + 4 * i, "body": "b%d" % (i + 1)})
		m.sync(); await harness._wait_confirm(); seen[m.ops.size()] = harness._shown_ids()
	full = m.ops.duplicate(true)
	print("UNDOTEST built %d ops, %d boards" % [m.ops.size(), seen[m.ops.size()].size()])
	# 1. one Ctrl+Z at a time; FreeCAD answers 300 ms late, so right after Ctrl+Z the screen shows the remembered state
	var instant_bad := []; var after_bad := []; var reloads := 0; var rebuilt := []
	for n in range(m.ops.size(), 0, -1):
		m.test_delay_ms = 100 if harness.quick else 300      # late enough: the check below runs in the same frame (T48)
		m.undo()
		if harness._shown_ids() != seen[n - 1]: instant_bad.append([n - 1, harness._shown_ids(), seen[n - 1]])
		var sc: Node = m.bodies_root.get_child(0) if m.bodies_root.get_child_count() > 0 else null
		await harness._wait_confirm()
		if m.ui_sync.text.contains("rebuilt"): rebuilt.append(full.size() - (n - 1))
		if harness._shown_ids() != seen[n - 1]: after_bad.append([n - 1, harness._shown_ids(), seen[n - 1]])
		if m.bodies_root.get_child_count() > 0 and m.bodies_root.get_child(0) != sc: reloads += 1
	print("UNDOTEST one at a time: shown at once right %s %s | right after FreeCAD %s %s | reloads after FreeCAD answered: %d | FreeCAD rebuilt at undo no. %s" % [
		instant_bad.is_empty(), instant_bad.slice(0, 2), after_bad.is_empty(), after_bad.slice(0, 2), reloads, rebuilt])
	# 2. all of it again, then 22 Ctrl+Z as fast as you can press them
	m.ops = full.duplicate(true)
	m.sync(); await harness._wait_confirm()
	var fast_bad := []
	var t0 := Time.get_ticks_msec()
	for n in range(m.ops.size(), 0, -1):
		m.undo()
		if harness._shown_ids() != seen[n - 1]: fast_bad.append([n - 1, harness._shown_ids()])
		await harness._frames(1)
	var t_all := Time.get_ticks_msec() - t0
	await harness._wait_confirm()
	print("UNDOTEST fast: 22 undos shown at once %s %s in %d ms of frames | after FreeCAD: %s, ops %d | %s" % [
		fast_bad.is_empty(), fast_bad.slice(0, 2), t_all, harness._shown_ids(), m.ops.size(), m.ui_sync.text])
	print("UNDOTEST done")
	harness.get_tree().quit()
