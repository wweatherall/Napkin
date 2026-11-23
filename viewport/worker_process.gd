extends RefCounted

# ---------------- the FreeCAD worker (T6) ----------------
# Shop Sketch starts its own worker (freecadcmd worker/replay.py) on a free port, watches it, and starts it
# again if it stops; the request that was lost with it is sent again. On quit the worker saves and stops.
const FREECAD_CANDIDATES := ["/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd",
	"/Applications/FreeCAD.app/Contents/Resources/bin/FreeCADCmd", "/Applications/FreeCAD.app/Contents/MacOS/freecadcmd",
	"/Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd", "/usr/bin/freecadcmd", "/usr/local/bin/freecadcmd"]
const WORKER_MAX_RESTARTS := 5      # in a minute; after that, say so and stop trying
var freecad_path := ""
var worker_script := ""
var worker_log := ""
var worker_port := -1
var worker_pid := -1                # -1: not ours (tests pass --port), or given up
var _port_file := ""                # tests: where our worker reports the port it bound (T47)
var _worker_restarts: Array = []
var _worker_check := 0.0
var lifecycle_test := false
var _worker_shut := false
var m: Node


func _init(window: Node) -> void:
	m = window


func _free_port(from: int) -> int:
	for p in range(from, from + 100):
		var srv := TCPServer.new()
		if srv.listen(p, "127.0.0.1") == OK:
			srv.stop()
			return p
	return from


static func _sh(s: String) -> String:
	return "'" + s.replace("'", "'\\''") + "'"


# One FreeCAD worker serves every window (W13): each window has its own document, and a model is open in one
# window at a time. A window uses the worker on SHARED_PORT if it runs the same worker script; else it starts it
# there; a different version (say the repo and the built app at once) gets a worker of its own. Tests never share.
var SHARED_PORT := 7878             # --shared-port=N: another one (to try windows sharing next to a running app)
const SHARED_IDLE_EXIT := 10        # seconds the shared worker waits after the last window leaves
var shared_worker := false
var _down_since := -1.0
var _gave_up := false


func _worker_files() -> void:
	if freecad_path == "":
		for c in FREECAD_CANDIDATES:
			if FileAccess.file_exists(c): freecad_path = c; break
	if worker_script == "":
		worker_script = m._beside_project("worker/replay.py")


func worker_identity() -> String:
	"""The same hash the worker reports in hello (serve.py worker_identity): MD5 of every worker .py except the
	tests, one after another in name order. A change to any worker module means a different worker."""
	var folder := worker_script.get_base_dir()
	var names: Array = Array(DirAccess.get_files_at(folder)).filter(
		func(n: String) -> bool: return n.ends_with(".py") and not n.begins_with("test_"))
	if names.is_empty(): return ""
	names.sort()
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_MD5)
	for n in names:
		ctx.update(FileAccess.get_file_as_bytes(folder.path_join(n)))
	return ctx.finish().hex_encode()


func _port_free(p: int) -> bool:
	var srv := TCPServer.new()
	if srv.listen(p, "127.0.0.1") != OK: return false
	srv.stop()
	return true


func probe_worker(p: int) -> String:
	"""Ask whatever listens on port p who it is: the worker's script hash, or "" if it isn't a Shop Sketch worker
	this window can use (worker_of)."""
	return worker_of(hello(p), p)


func worker_of(r, p: int) -> String:
	"""A hello reply's worker hash, or "": not a Shop Sketch worker, or one speaking another protocol version
	(then it's treated like a different worker: this window starts its own, and says why)."""
	if typeof(r) != TYPE_DICTIONARY or r.get("app", "") != "shopsketch": return ""
	if int(r.get("protocol", 0)) != m.PROTOCOL_VERSION:
		print("SHOPSKETCH the worker on port %d speaks protocol %s, this window %d: not sharing it" % [p, str(r.get("protocol", "none")), m.PROTOCOL_VERSION])
		return ""
	return String(r.get("worker", ""))


func hello(p: int):
	"""The hello reply from whatever listens on port p (a separate short-lived connection), or null."""
	var peer := StreamPeerTCP.new()
	if peer.connect_to_host("127.0.0.1", p) != OK: return null
	var t0 := Time.get_ticks_msec()
	var buf := ""
	var sent := false
	while Time.get_ticks_msec() - t0 < 3000:
		peer.poll()
		var st := peer.get_status()
		if st == StreamPeerTCP.STATUS_ERROR or st == StreamPeerTCP.STATUS_NONE: return null
		if st == StreamPeerTCP.STATUS_CONNECTED:
			if not sent:
				peer.put_data((JSON.stringify({"cmd": "hello"}) + "\n").to_utf8_buffer()); sent = true
			var n := peer.get_available_bytes()
			if n > 0:
				buf += peer.get_utf8_string(n)
				if buf.contains("\n"):
					var r = JSON.parse_string(buf.get_slice("\n", 0))
					peer.disconnect_from_host()
					return r
		OS.delay_msec(10)
	peer.disconnect_from_host()
	return null


func pick_worker() -> int:
	_worker_files()
	if m.test_mode:                                   # tests: a worker of their own, on a port it picks itself (T47)
		_start_worker()
		return worker_port
	var mine := worker_identity()
	if _port_free(SHARED_PORT):
		shared_worker = true
		worker_port = SHARED_PORT
		_start_worker()
	elif probe_worker(SHARED_PORT) == mine and mine != "":
		shared_worker = true                       # another window's worker: use it
		worker_port = SHARED_PORT
		print("SHOPSKETCH sharing the worker on port %d" % SHARED_PORT)
	else:
		worker_port = _free_port(SHARED_PORT + 1)   # something else (or another version) has the port
		_start_worker()
	return worker_port


func _start_worker() -> void:
	if freecad_path == "":
		for c in FREECAD_CANDIDATES:
			if FileAccess.file_exists(c): freecad_path = c; break
	if worker_script == "":
		worker_script = m._beside_project("worker/replay.py")
	if worker_log == "":
		worker_log = ProjectSettings.globalize_path("user://worker.log")
	if freecad_path == "" or not FileAccess.file_exists(worker_script):
		say_worker("✗ couldn't find FreeCAD's command-line program (freecadcmd) or worker/replay.py")
		worker_pid = -1
		return
	# a test's worker binds port 0 and writes the port the system gave it to a file: two test runs at once can't
	# pick the same port before either binds it (T47). The app's workers keep their known ports (W13).
	var port_file := ""
	if m.test_mode:
		port_file = OS.get_temp_dir().path_join("shopsketch-worker-%d.port" % OS.get_process_id())
		DirAccess.remove_absolute(port_file)
		worker_port = 0
	if OS.get_name() == "Windows":
		OS.set_environment("SERVE_PORT", str(worker_port))
		OS.set_environment("SERVE_PORT_FILE", port_file)
		worker_pid = OS.create_process(freecad_path, [worker_script])
	else:
		worker_pid = OS.create_process("/bin/sh", ["-c", "SERVE_PORT=%d SERVE_PORT_FILE=%s SERVE_IDLE_EXIT=%d exec %s %s >> %s 2>&1" % [
			worker_port, _sh(port_file), SHARED_IDLE_EXIT, _sh(freecad_path), _sh(worker_script), _sh(worker_log)]])   # never outlives its windows
	_port_file = port_file
	if port_file != "" and m.client != null:           # a restarted worker: wait for its new port
		worker_port = _await_port_file()
		m.client.port = worker_port
	print("SHOPSKETCH worker pid %d %s: %s (log %s)" % [worker_pid, "port pending" if worker_port == 0 else
		"on port %d" % worker_port, worker_script, worker_log])


func resolve_port(port: int) -> int:
	if port == 0 and _port_file != "":
		worker_port = _await_port_file()           # the worker has been starting while the window was built
		return worker_port
	return port


func _await_port_file() -> int:
	"""Tests only: wait for the worker to report the port it bound (it starts in about a second)."""
	var path := _port_file
	var t0 := Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 60000:
		if FileAccess.file_exists(path):
			var p := int(FileAccess.get_file_as_string(path).strip_edges())
			DirAccess.remove_absolute(path)
			if p > 0:
				print("SHOPSKETCH worker on port %d" % p)
				return p
		if worker_pid > 0 and not OS.is_process_running(worker_pid): break
		OS.delay_msec(20)
	push_error("SHOPSKETCH the worker didn't report its port: see %s" % worker_log)
	return -1


func watch_worker(delta: float) -> void:
	_worker_check -= delta
	if _worker_check > 0.0: return
	_worker_check = 1.0
	if shared_worker:
		# whoever started it, it's everyone's: when it's gone and its port is free, this window starts it again
		if m.client.connected:
			_down_since = -1.0; return
		var now_s := Time.get_ticks_msec() / 1000.0
		if _down_since < 0.0: _down_since = now_s
		if now_s - _down_since < 1.5 or not _port_free(worker_port) or _gave_up: return
		_down_since = -1.0
	elif worker_pid <= 0 or OS.is_process_running(worker_pid):
		return
	if not _can_restart():
		say_worker("✗ the FreeCAD worker keeps stopping - see %s" % worker_log)
		worker_pid = -1
		_gave_up = true
		return
	say_worker("✗ the FreeCAD worker stopped - starting it again")
	_start_worker()


func _can_restart() -> bool:
	var now := Time.get_ticks_msec()
	_worker_restarts = _worker_restarts.filter(func(t): return now - t < 60000)
	_worker_restarts.append(now)
	return _worker_restarts.size() <= WORKER_MAX_RESTARTS


func say_worker(txt: String) -> void:
	m.ui_sync.text = m.doc.readable_ids(txt)
	m.ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))


func shutdown_worker() -> void:
	if _worker_shut: return
	_worker_shut = true
	if shared_worker:
		# other windows may be using it: hand back this window's model (saved first) and leave it running;
		# it stops by itself a few seconds after the last window has gone
		if m.client.connected:
			m.client.send({"cmd": "bye"})
			var t0 := Time.get_ticks_msec()
			while m.client.connected and Time.get_ticks_msec() - t0 < 4000:
				m.client.peer.poll()
				if m.client.peer.get_status() != StreamPeerTCP.STATUS_CONNECTED: break
				if m.client.peer.get_available_bytes() > 0 and m.client.peer.get_utf8_string(m.client.peer.get_available_bytes()).contains("bye"): break
				OS.delay_msec(20)
		return
	if worker_pid <= 0 or not OS.is_process_running(worker_pid): return
	m.client.send({"cmd": "quit"})            # it saves anything pending, then stops
	var t0 := Time.get_ticks_msec()
	while OS.is_process_running(worker_pid) and Time.get_ticks_msec() - t0 < 4000:
		m.client.peer.poll()
		OS.delay_msec(50)
	if OS.is_process_running(worker_pid):
		OS.kill(worker_pid)
	worker_pid = -1


func log_worker(line: String) -> void:
	"""A line in worker.log from this window (A36: a stuck or stopped worker at an outside save)."""
	print("SHOPSKETCH " + line)
	if worker_log == "": return
	var f := FileAccess.open(worker_log, FileAccess.READ_WRITE) if FileAccess.file_exists(worker_log) else FileAccess.open(worker_log, FileAccess.WRITE)
	if f == null: return
	f.seek_end()
	f.store_line("SHOPSKETCH %s %s" % [Time.get_datetime_string_from_system(), line])
