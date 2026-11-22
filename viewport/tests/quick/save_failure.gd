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


func run() -> void:
	# A failed save (T79): the indicator says why and stays (I-new-1); closing asks Retry / Close without saving /
	# Cancel and goes once the save lands (I-new-2). The model sits in a folder of its own, made read-only.
	harness._q_lap("save_failure")
	var folder := m.out_dir.path_join("savefail_ro")
	DirAccess.make_dir_recursive_absolute(folder)
	OS.execute("chmod", ["755", folder])
	m.switch_model(folder.path_join("quick_savefail.FCStd"), true)
	await _until(func(): return m.opened, 20000)
	m.ops.append_array(harness._plank(1, Vector3.ZERO, Vector3(300, 100, 18)))
	m._restore_counters()
	m.sync()
	await harness._wait_confirm()
	await _until(func(): return m.saved_rev >= m.pending_rev and m.pending_rev > 0)
	harness._ok("a model in a writable folder saves", m.ui_saved.text == "Saved", m.ui_saved.text)

	OS.execute("chmod", ["555", folder])
	m.ops.append_array(harness._plank(2, Vector3(0, 200, 0), Vector3(300, 100, 18)))
	m._restore_counters()
	m.sync()
	await harness._wait_confirm()
	await _until(func(): return m.doc.save_error != "")
	harness._ok("a failed save shows in the save indicator, with the reason",
		m.ui_saved.text == "Couldn't save: the folder savefail_ro is read-only", m.ui_saved.text)
	await harness._frames(10)
	harness._ok("and stays (the timer doesn't clear it)", m.ui_saved.text.begins_with("Couldn't save"), m.ui_saved.text)

	m._request_close()
	await _until(func(): return m.close_asked.size() == 1)
	harness._ok("closing with the save failing asks, with the reason, and doesn't close",
		m.close_asked == ["the folder savefail_ro is read-only"] and not m.close_done, [m.close_asked, m.close_done])
	m._close_choice("cancel")
	harness._ok("Cancel keeps the window, still saying it couldn't save",
		not m.doc.closing and not m.close_done and m.ui_saved.text.begins_with("Couldn't save"), m.ui_saved.text)
	m._request_close()
	await _until(func(): return m.close_asked.size() == 2)
	m._close_choice("retry")
	await _until(func(): return m.close_asked.size() == 3)
	harness._ok("Retry tries again and asks again while it still fails", m.close_asked.size() == 3 and not m.close_done,
		m.close_asked)

	OS.execute("chmod", ["755", folder])
	m._close_choice("retry")
	await _until(func(): return m.close_done)
	harness._ok("Retry once the folder is writable saves the latest revision and closes",
		m.close_done and m.saved_rev == m.pending_rev and m.ui_saved.text == "Saved", [m.close_done, m.saved_rev, m.pending_rev, m.ui_saved.text])
	m.close_done = false
	m._close_choice("discard")
	harness._ok("Close without saving closes", m.close_done)
	m.close_done = false
	m.close_asked.clear()
