extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 10. The worker stops: Shop Sketch starts it again and carries on (A27)
	harness._q_lap("worker")
	if m.worker_pid > 0:
		var pid1: int = m.worker_pid
		OS.kill(pid1)
		await harness._frames(2)
		m.ops.append_array(harness._plank(9, Vector3(0, 600, 0), Vector3(50, 50, 10)))
		m._restore_counters()
		m.sync(); await harness._wait_confirm()
		harness._ok("a new worker took over and confirmed the next board", m.worker_pid != pid1 and OS.is_process_running(m.worker_pid) and harness.id("b9") in harness._shown_ids(), [m.worker_pid, harness._shown_ids()])
	else:
		harness._ok("the quick test runs with its own worker (no --port)", false)
