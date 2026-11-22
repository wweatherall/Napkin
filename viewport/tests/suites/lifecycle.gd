extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# T6: the app starts its own worker; kill it mid-session and keep working; quitting stops the worker
	m.cursor2d.visible = false
	var t0 := Time.get_ticks_msec()
	while not m.opened and Time.get_ticks_msec() - t0 < 60000: await harness._frames(1)
	print("LIFECYCLETEST started worker pid %d port %d, opened %s in %d ms" % [m.worker_pid, m.worker_port, m.opened, Time.get_ticks_msec() - t0])
	m.ops.append({"id": "r1", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [0, 0, 0]}, "size": [300, 200]})
	m.ops.append({"id": "pp1", "type": "push_pull", "target": {"rect": "r1"}, "distance": 18, "body": "b1"})
	m.sync(); await harness._wait_confirm()
	var first := harness._shown_ids()
	var pid1 := m.worker_pid
	OS.kill(pid1)                                   # the worker crashes
	await harness._frames(2)
	m.ops.append({"id": "r2", "type": "rect", "plane": {"normal": [0, 0, 1], "origin": [400, 0, 0]}, "size": [300, 200]})
	m.ops.append({"id": "pp2", "type": "push_pull", "target": {"rect": "r2"}, "distance": 25, "body": "b2"})
	var t1 := Time.get_ticks_msec()
	m.sync(); await harness._wait_confirm()
	print("LIFECYCLETEST before crash %s | after crash: new pid %s (was %d), running %s, boards %s, confirmed after %d ms | %s" % [
		first, m.worker_pid, pid1, OS.is_process_running(m.worker_pid), harness._shown_ids(), Time.get_ticks_msec() - t1, m.ui_sync.text])
	print("LIFECYCLETEST worker pid at quit %d" % m.worker_pid)
	harness.get_tree().quit()
