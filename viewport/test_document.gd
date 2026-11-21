extends SceneTree
## The document controller (document.gd, A31, T39) on its own, with no window and no worker: a stand-in client
## records what it sends, and the tests answer for the worker. Checks the sequencing that keeps a stale reply
## from ever reaching the screen: rapid edits, delayed and out-of-date answers, reconnects, model switches, undo.
## Run: Godot --headless --path viewport --script res://test_document.gd
const Document = preload("res://document.gd")
var passed := 0
var failed := 0
var made: Array = []


class FakeClient:
	var sent: Array = []
	func send(d: Dictionary) -> void: sent.append(d)
	func last() -> Dictionary: return sent.back() if not sent.is_empty() else {}
	func syncs() -> Array: return sent.filter(func(d): return d["cmd"] == "sync")


func check(label: String, condition: bool) -> void:
	if condition:
		passed += 1
		print("PASS ", label)
	else:
		failed += 1
		print("FAIL ", label)


func make() -> Array:
	var d := Document.new()
	made.append(d)
	var c := FakeClient.new()
	d.client = c
	d.model_path = "/tmp/doc-test.FCStd"
	d.out_dir = "/tmp/doc-test"
	var seen := {"synced": [], "failed": [], "idle": 0, "started": 0, "saves": 0, "removed_ops": [], "removed": 0}
	d.synced.connect(func(r): seen["synced"].append(r))
	d.sync_failed.connect(func(e): seen["failed"].append(e))
	d.idle.connect(func(): seen["idle"] += 1)
	d.sync_started.connect(func(): seen["started"] += 1)
	d.save_changed.connect(func(): seen["saves"] += 1)
	d.op_removed.connect(func(op): seen["removed_ops"].append(op["id"]))
	d.removed.connect(func(): seen["removed"] += 1)
	return [d, c, seen]


func reply(d, ok_ids: Array, seq_no: int, extra := {}) -> Dictionary:
	var ops := []
	for i in ok_ids: ops.append({"id": i, "status": "ok"})
	var res := {"ops": ops, "how": "applied", "rev": 1}
	res.merge(extra, true)
	return {"ok": true, "seq": seq_no, "result": res, "outdir": d.out_dir}


func op(id: String) -> Dictionary:
	return {"id": id, "type": "rect", "plane": {}}


func _init() -> void:
	# --- one edit, answered ---
	var t := make(); var d = t[0]; var c = t[1]; var seen = t[2]
	d.ops.append(op("r1")); d.sync()
	check("sync sends the whole op list with its seq", c.syncs().size() == 1 and c.last()["seq"] == 1
		and c.last()["oplog"]["ops"].size() == 1 and c.last()["model"] == d.model_path and d.in_flight)
	d.on_sync_reply(reply(d, ["r1"], 1))
	check("the answer for the current state is passed on", seen["synced"].size() == 1 and not d.in_flight)
	check("its ops count as confirmed", d.confirmed_ids.has("r1"))
	check("a change will be saved as the reply's revision", d.pending_rev == 1 and seen["saves"] == 1)
	check("settled: idle", seen["idle"] == 1)

	# --- rapid edits coalesce; the stale answer is ignored, the latest list is sent ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.ops.append(op("r1")); d.sync()
	d.ops.append(op("r2")); d.sync()
	d.ops.append(op("r3")); d.sync()
	check("edits while one is in flight wait (one request)", c.syncs().size() == 1 and d.dirty and d.seq == 3)
	d.on_sync_reply(reply(d, ["r1"], 1))
	check("the out-of-date answer is not shown", seen["synced"].is_empty() and not d.confirmed_ids.has("r1"))
	check("then the latest list goes, once", c.syncs().size() == 2 and c.last()["seq"] == 3
		and c.last()["oplog"]["ops"].size() == 3 and not d.dirty and d.in_flight)
	check("not idle while catching up", seen["idle"] == 0)
	d.on_sync_reply(reply(d, ["r1", "r2", "r3"], 3))
	check("the current answer is shown", seen["synced"].size() == 1 and d.confirmed_ids.size() == 3)

	# --- a reply arriving after a newer edit (dirty) is ignored even if its seq matched when sent ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.ops.append(op("r1")); d.sync()
	d.ops.append(op("r2")); d.sync()
	d.on_sync_reply(reply(d, ["r1"], 2))         # seq claims the latest, but the request in flight is older
	check("dirty: an answer can't stand for the state on screen", seen["synced"].is_empty())

	# --- the worker failed ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.ops.append(op("r1")); d.sync()
	d.on_sync_reply({"ok": false, "error": "boom"})
	check("a worker error is reported, nothing confirmed", seen["failed"] == ["boom"] and seen["synced"].is_empty()
		and not d.in_flight and d.confirmed_ids.is_empty())

	# --- no change: nothing new to save ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.sync()
	d.on_sync_reply(reply(d, [], 1, {"how": "nothing", "rev": 9}))
	check("an answer that changed nothing doesn't move the save revision", d.pending_rev == 0 and seen["saves"] == 0)

	# --- saves ---
	d.on_saved({"cmd": "saved", "model": "/tmp/other.FCStd", "rev": 4})
	check("another model's save is ignored", d.saved_rev == 0)
	d.on_saved({"cmd": "saved", "model": d.model_path, "rev": 4})
	d.on_saved({"cmd": "saved", "model": d.model_path, "rev": 2})
	check("saved revision only moves forward", d.saved_rev == 4 and seen["saves"] == 2)

	# --- reconnect ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.on_link_up()
	check("link back before the open was answered: open again", c.last()["cmd"] == "open")
	d.on_opened({"ok": true, "rev": 3, "ops": [op("r1")]}, true)
	d.sync()
	var before: int = c.syncs().size()
	d.on_link_up()
	check("link back with a request lost in flight: send the model again", c.syncs().size() == before + 1
		and c.last()["seq"] == d.seq and d.in_flight)

	# --- opening ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.start_fresh = true
	d.send_open()
	check("tests: the first open starts fresh", c.last()["fresh"] == true)
	d.on_opened({"ok": true, "rev": 5, "ops": [op("r1"), {"id": "pp4", "type": "push_pull", "body": "b7", "target": {"rect": "r1"}}],
		"undo_floor": 1}, true)
	check("open adopts the file's history", d.ops.size() == 2 and d.undo_floor == 1 and d.opened)
	check("its ops are already confirmed (no wave)", d.confirmed_ids.has("r1") and d.confirmed_ids.has("pp4"))
	check("counters continue from the file's ids", d.counters["r"] == 1 and d.counters["pp"] == 4 and d.counters["b"] == 7)
	check("saved and pending start at the file's revision", d.saved_rev == 5 and d.pending_rev == 5)
	d.send_open()
	check("a later open keeps the file", c.last()["fresh"] == false)
	var t2 := make(); var d2 = t2[0]
	d2.on_opened({"ok": true, "rev": 2, "ops": [op("r1")]}, false)
	check("a test's first open doesn't adopt the history", d2.ops.is_empty() and d2.opened and d2.saved_rev == 2)
	check("consumed rects", d.consumed_rects() == {"r1": true})

	# --- undo floor ---
	d.undo()
	check("undo stops at changes made in FreeCAD", d.at_undo_floor() and d.ops.size() == 1 and seen["removed_ops"] == ["pp4"])

	# --- undo / redo ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	for i in 3: d.ops.append(op("r%d" % (i + 1)))
	d.undo()
	check("undo removes the last op and resyncs", d.ops.size() == 2 and seen["removed_ops"] == ["r3"]
		and seen["removed"] == 1 and seen["started"] == 1)
	d.undo()
	check("redo is available after undo", d.can_redo())
	var back: Dictionary = d.take_redo()
	check("redo brings back the most recent undo first", back["id"] == "r2" and d.ops.size() == 2)
	d.ops.append(op("r9"))
	check("a new action ends redo", not d.can_redo() and d.take_redo().is_empty() and d.redo_stack.is_empty())

	# --- remove several: one resync ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	for i in 3: d.ops.append(op("r%d" % (i + 1)))
	d.remove_ops(["r1", "r3"])
	check("removing several resyncs once", d.ops.size() == 1 and seen["removed_ops"] == ["r1", "r3"]
		and seen["removed"] == 1 and c.syncs().size() == 1)
	d.remove_op("nope")
	check("removing an unknown op does nothing", seen["removed"] == 1 and c.syncs().size() == 1)

	# --- switching models ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.ops.append(op("r1")); d.counters["r"] = 1; d.sync()
	var old_seq: int = d.seq
	d.reset()
	d.open("/tmp/doc-other.FCStd", true)
	check("switching clears the list and the counters", d.ops.is_empty() and d.counters["r"] == 0 and not d.opened)
	check("and opens the other file", c.last()["cmd"] == "open" and c.last()["model"] == "/tmp/doc-other.FCStd" and c.last()["fresh"])
	d.on_sync_reply(reply(d, ["r1"], old_seq))
	check("the old model's answer, still on its way, is ignored", seen["synced"].is_empty() and d.confirmed_ids.is_empty())

	# --- drawing request ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.request_drawing()
	check("a drawing request asks for the drawing", c.last()["drawing"] == true)
	d.request_drawing()
	check("one in flight: it waits", c.syncs().size() == 1 and d.dirty)

	# --- test hook: delay goes out once ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.test_delay_ms = 300; d.sync()
	d.on_sync_reply(reply(d, [], 1)); d.sync()
	check("delay_ms is sent once", c.syncs()[0]["delay_ms"] == 300 and c.syncs()[1]["delay_ms"] == 0)

	for n in made: n.free()
	print("DOCUMENT TESTS: %d passed, %d failed" % [passed, failed])
	quit(1 if failed > 0 else 0)
