extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func _until(cond: Callable, ms := 10000) -> bool:
	var t0 := Time.get_ticks_msec()
	while not cond.call() and Time.get_ticks_msec() - t0 < ms: await harness._frames(1)
	return cond.call()


func _ids() -> Array:
	return m.ops.map(func(o): return o["id"])


func run() -> void:
	# An outside save (T64, A36): the model's file changes on disk while it's open (here an earlier revision of it put
	# back, as FreeCAD saves the copy it had open). The worker notices without a sync, the window reloads it, the
	# board it brings back runs the wave, the delete the file didn't have is dropped, and undo stops there.
	var planks: Array = harness._plank(1, Vector3.ZERO, Vector3(300, 100, 18))
	planks.append_array(harness._plank(2, Vector3(0, 200, 0), Vector3(300, 100, 18)))
	await harness._fresh("outside_save", planks, true)
	await _until(func(): return m.pending_rev > 0 and m.saved_rev >= m.pending_rev)
	var model: String = m.model_path
	var rev1 := model + ".rev1"
	DirAccess.copy_absolute(model, rev1)
	m.ops.append({"id": "del1", "type": "delete", "targets": ["b2"]})
	m._restore_counters()
	m.sync()
	await harness._wait_confirm()
	await _until(func(): return m.saved_rev >= m.pending_rev)
	harness._ok("the delete is saved before FreeCAD's save comes in", not m.body_tris.has(harness.id("b2")) and m.saved_rev >= 2,
		[m.body_tris.keys(), m.saved_rev])

	var reloads := [0]
	m.doc.reloaded.connect(func(_r): reloads[0] += 1)
	DirAccess.rename_absolute(rev1, model)
	await _until(func(): return reloads[0] > 0, 5000)
	harness._ok("an outside save is reloaded with no action from Shop Sketch's side", reloads[0] == 1, reloads)
	harness._ok("the board FreeCAD's save has is back, and the wave runs over it",
		m.body_tris.has(harness.id("b2")) and m.reload_waves == [harness.id("b2")] and m.pres.op_waves.has("reload:b2"),
		[m.body_tris.keys(), m.reload_waves, m.pres.op_waves.keys()])
	harness._ok("the delete it didn't have leaves the list and is kept as dropped",
		_ids() == [harness.id("r1"), harness.id("pp1"), harness.id("r2"), harness.id("pp2")] and m.doc.dropped.map(func(o): return o["id"]) == [harness.id("del1")], [_ids(), m.doc.dropped])
	harness._ok("the status line says what came in", m.ui_sync.text.begins_with("↻ took FreeCAD's save"), m.ui_sync.text)
	m.undo()
	harness._ok("undo stops at the FreeCAD change", _ids().size() == 4 and m.doc.at_undo_floor(), _ids())

	# The dialog's wiring (the wait itself is the document test's): asked, Keep Shop Sketch's copies the file aside.
	m.doc.outside = {"rev": 1, "unsaved": true}
	m._ask_outside()
	harness._ok("with actions still out after the wait it asks, saying why",
		m.outside_asked == ["they hadn't landed after 10 s"], m.outside_asked)
	var kept := [""]
	m.doc.kept_mine.connect(func(r): kept[0] = String(r.get("aside", "")))
	m._outside_choice("mine")
	await _until(func(): return kept[0] != "", 5000)
	harness._ok("Keep Shop Sketch's copies FreeCAD's file aside as <model>.freecad-<time>.FCStd",
		kept[0].get_file().begins_with("quick_outside_save.freecad-") and FileAccess.file_exists(kept[0]), kept)
	m.outside_asked.clear()

	# Inject the error reply a failed reload would send and verify the prompt in the window.
	m.doc.outside = {"rev": m.saved_rev, "unsaved": false}
	m.doc.outside_seq = m.seq
	m._on_worker({"cmd": "reload", "ok": false, "seq": m.seq, "error": "Invalid project file"})
	harness._ok("a failed reload immediately asks with the worker's exact error",
		m.outside_asked == ["couldn't open FreeCAD's save: Invalid project file"], m.outside_asked)
	m._outside_choice("freecad")
	await _until(func(): return reloads[0] == 2, 5000)
	harness._ok("Use FreeCAD's version retries the failed reload", reloads[0] == 2, reloads)

	# Set up an in-flight sync and the question on the same frame. Check the stale click before the reload reply.
	var dismissed := [false]
	m.doc.outside_actions_landed.connect(func():
		var reload_seq := m.doc.outside_seq
		m._outside_choice("mine")
		dismissed[0] = m.outside_closed == 1 and reload_seq >= 0 and m.doc.outside_seq == reload_seq \
			and not m.doc.outside.is_empty())
	m.sync()
	m.doc.on_outside_save({"model": model, "rev": m.saved_rev, "unsaved": true})
	m._ask_outside()
	await _until(func(): return reloads[0] == 3, 5000)
	harness._ok("landing actions close the outside-save question and a stale click sends no keep_mine",
		dismissed[0] and reloads[0] == 3, [dismissed[0], m.outside_closed, reloads[0]])
	harness._ok("the reload status explains why the question closed",
		m.ui_sync.text.ends_with(" (Shop Sketch's actions landed while you were deciding, so the question closed)"),
		m.ui_sync.text)
