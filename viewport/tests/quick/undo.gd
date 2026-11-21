extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 6. Undo (A28): every undo shows at once, the 21st rebuilds in FreeCAD
	await harness._fresh("undo")
	var seen := {0: []}
	for i in 11:
		m.ops.append_array(harness._plank(i + 1, Vector3(120.0 * i, 0, 0), Vector3(100, 50, 18 + 4 * i)))
		m.sync(); await harness._wait_confirm(); seen[m.ops.size()] = harness._shown_ids()
	m._restore_counters()
	var bad := []
	var rebuilt := false
	for n in range(m.ops.size(), 0, -1):
		m.test_delay_ms = 60
		m.undo()
		if harness._shown_ids() != seen.get(n - 1, harness._shown_ids()) and n % 2 == 1: bad.append(n - 1)
		await harness._wait_confirm()
		rebuilt = rebuilt or m.ui_sync.text.contains("rebuilt")
	harness._ok("each undo shows the earlier boards at once", bad.is_empty(), bad)
	harness._ok("undoing past FreeCAD's 20 steps rebuilds", rebuilt)
	harness._ok("everything undone", m.ops.is_empty() and harness._shown_ids().is_empty(), [m.ops.size(), harness._shown_ids()])
	# Redo (T31): Shift+Cmd+Z puts undone actions back, remembered states at once; a new action ends redo
	var redo_bad := []
	for n in range(1, 5):
		await harness.get_tree().create_timer(0.16, true, false, true).timeout   # _menu drops a repeat within 150 ms
		await harness._key_cmd_shift(KEY_Z)
		if m.ops.size() != n or (n % 2 == 0 and harness._shown_ids() != seen[n]): redo_bad.append([n, m.ops.size(), harness._shown_ids()])
		await harness._wait_confirm()
	harness._ok("Shift+Cmd+Z redoes, each one shown at once", redo_bad.is_empty(), redo_bad)
	harness._ok("FreeCAD has the redone boards", harness._shown_ids() == seen[4] and m.ops.all(func(o): return m.confirmed_ids.has(o["id"])),
		[harness._shown_ids(), seen[4]])
	m.undo(); await harness._wait_confirm()
	await harness._view(Vector3(400, 0, 0), -25, -50, 1.6)
	await harness._rect(Vector3(400, 0, 0), Vector3(440, 30, 0), "40,30")
	var n_ops: int = m.ops.size()
	await harness._key_cmd_shift(KEY_Z)
	harness._ok("after a new action there's nothing to redo", m.ops.size() == n_ops and m.ui_sync.text == "Nothing to redo",
		[m.ops.size(), n_ops, m.ui_sync.text])
	await harness._wait_confirm()
	# Esc (T31): the gesture first, then the selection
	m.set_selection(["b1"])
	await harness._key(KEY_R)
	await harness._drag_to(Vector3(500, 0, 0), 4); await harness._press()
	await harness._drag_to(Vector3(540, 30, 0), 4)
	var drawing: bool = m.tools["rect"].busy()
	await harness._key(KEY_ESCAPE)
	harness._ok("Esc cancels the gesture and keeps the selection", drawing and not m.tools["rect"].busy() and m.selection == ["b1"],
		[drawing, m.selection])
	await harness._key(KEY_ESCAPE)
	harness._ok("a second Esc clears the selection", m.selection.is_empty(), m.selection)
