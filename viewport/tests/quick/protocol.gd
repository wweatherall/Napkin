extends RefCounted
## The protocol version (docs/protocol.md): the worker reports it in hello, and a window shares a worker only when
## the version and the worker hash both match (main.gd _worker_of); otherwise it starts its own.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	await harness._fresh("protocol")
	var r = m._hello(m.worker_port)
	harness._ok("this window's worker says hello with the window's protocol version", typeof(r) == TYPE_DICTIONARY
		and int(r.get("protocol", -1)) == Main.PROTOCOL_VERSION and m._worker_of(r, m.worker_port) == m._worker_identity(), r)
	# a stand-in hello: the same worker hash, another protocol version, isn't adopted (as with another hash)
	var mine := m._worker_identity()
	var same := {"ok": true, "cmd": "hello", "app": "shopsketch", "worker": mine, "protocol": Main.PROTOCOL_VERSION}
	var newer := same.duplicate(); newer["protocol"] = Main.PROTOCOL_VERSION + 1
	var older := same.duplicate(); older.erase("protocol")
	harness._ok("a worker with the same hash and protocol is shared", m._worker_of(same, 0) == mine and mine != "")
	harness._ok("one speaking another protocol version is not (the window starts its own)",
		m._worker_of(newer, 0) == "" and m._worker_of(older, 0) == "", [m._worker_of(newer, 0), m._worker_of(older, 0)])
