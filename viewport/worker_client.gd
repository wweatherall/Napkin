extends Node
## Newline-delimited JSON client for the FreeCAD worker (worker/replay.py).
## Reconnects on its own; queues lines until connected. Tells the app when the link goes down and comes back,
## so a request lost with a stopped worker can be sent again.

signal replied(resp: Dictionary)
signal link_up(first: bool)       # connected; first = the first time since start
signal link_down

var host := "127.0.0.1"
var port := 7878
var peer := StreamPeerTCP.new()
var buf := PackedByteArray()
var pending: Array[String] = []
var _retry := 0.0
var connected := false
var _ever := false


func start(p_port: int) -> void:
	port = p_port
	peer.connect_to_host(host, port)


func send(obj: Dictionary) -> void:
	var line := JSON.stringify(obj, "", false, true) + "\n"
	if connected and peer.put_data(line.to_utf8_buffer()) == OK:
		return
	pending.append(line)


func _process(delta: float) -> void:
	peer.poll()
	var st := peer.get_status()
	if st == StreamPeerTCP.STATUS_CONNECTED:
		if not connected:
			connected = true
			for l in pending:
				peer.put_data(l.to_utf8_buffer())
			pending.clear()
			link_up.emit(not _ever)
			_ever = true
		var n := peer.get_available_bytes()
		if n > 0:
			var r := peer.get_partial_data(n)
			if r[0] == OK:
				buf.append_array(r[1])
				_drain()
	elif st == StreamPeerTCP.STATUS_ERROR or st == StreamPeerTCP.STATUS_NONE:
		if connected:
			connected = false
			buf.clear()
			link_down.emit()
		_retry -= delta
		if _retry <= 0.0:
			_retry = 0.5
			peer = StreamPeerTCP.new()
			peer.connect_to_host(host, port)


func _drain() -> void:
	while true:
		var i := buf.find(10)  # '\n'
		if i < 0:
			return
		var line := buf.slice(0, i).get_string_from_utf8()
		buf = buf.slice(i + 1)
		var parsed = JSON.parse_string(line)
		if typeof(parsed) == TYPE_DICTIONARY:
			replied.emit(parsed)
