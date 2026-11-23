extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 0. The worker's hello hash is the one the window computes from the worker's files (W13, T42: all modules)
	var theirs: String = m.worker.probe_worker(m.worker.worker_port)
	harness._ok("the window and its worker agree on the worker's hash", theirs != "" and theirs == m.worker.worker_identity(), [theirs, m.worker.worker_identity()])
