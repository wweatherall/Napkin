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
	# --- identities survive undo, abandoned futures and a journal round trip ---
	var ids_doc = make()[0]
	var allocated := {}
	for prefix in ids_doc.counters:
		var before: String = ids_doc.next_id(prefix)
		ids_doc.ops.append(op(before))
		ids_doc.undo()
		var after: String = ids_doc.next_id(prefix)
		check("undo never reuses a %s identity" % prefix, before != after and before.length() > 32
			and ids_doc.reserved_ids.has(before) and ids_doc.reserved_ids.has(after))
		allocated[before] = true
		allocated[after] = true
	var restored = make()[0]
	restored.on_opened({"ops": [], "reserved_ids": ids_doc.oplog().reserved_ids}, true)
	for prefix in restored.counters:
		var fresh: String = restored.next_id(prefix)
		check("reopening reserves abandoned %s identities and friendly numbers" % prefix,
			not allocated.has(fresh) and fresh.begins_with(prefix + "3_"))
	var nested := {"id": "mv8", "type": "move", "new_ids": ["b42"],
		"groups": {"a7": ["a9", "a10"]}, "target": {"face": {"body": "native-old"}}}
	restored.ops = [nested]
	restored.restore_counters()
	check("legacy references and nested assembly lists seed reservations verbatim",
		restored.ops == [nested] and restored.reserved_ids.has("native-old")
		and restored.counters.b == 42 and restored.counters.a == 10)

	var board_id: String = ids_doc.next_id("b")
	var action_id: String = ids_doc.next_id("pp")
	check("random board IDs keep readable tree and status names", Document.board_name(board_id) == "Board 3"
		and Document.board_name("b7") == "Board 7" and Document.board_name("bottom") == "bottom")
	check("random tokens stay out of displayed board, tooltip and rejection messages",
		Document.readable_ids("%s: unknown board '%s'" % [action_id, board_id]) == "pp3: unknown board 'Board 3'")

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
	d.on_sync_reply({"ok": false, "error": "boom", "seq": 1})
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

	# --- late replies (T70): an open for a model since left, a reply from before a reconnect, lifecycle replies ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.open("/tmp/doc-a.FCStd", false)
	var open_a: Dictionary = c.last()
	d.reset(); d.open("/tmp/doc-b.FCStd", false)
	var open_b: Dictionary = c.last()
	check("each open carries its own seq", open_a.has("seq") and open_b["seq"] > open_a["seq"])
	var late_a := {"ok": true, "cmd": "open", "model": "/tmp/doc-a.FCStd", "seq": open_a["seq"], "rev": 1, "ops": [op("r1")]}
	check("a quick A -> B switch: A's open reply, arriving late, is ignored", not d.is_current_open(late_a))
	check("so is a refusal for the old open (it can't send the window back)", not d.is_current_open(
		{"ok": false, "cmd": "open", "error": "already_open", "model": "/tmp/doc-a.FCStd", "seq": open_a["seq"]}))
	check("a reply with the right seq for another model is ignored", not d.is_current_open(
		{"ok": true, "cmd": "open", "model": "/tmp/doc-a.FCStd", "seq": open_b["seq"]}))
	check("B's own open reply counts", d.is_current_open(
		{"ok": true, "cmd": "open", "model": "/tmp/doc-b.FCStd", "seq": open_b["seq"], "rev": 0, "ops": []}))
	d.open("/tmp/doc-b.FCStd", false)
	check("reopening the same model: only the latest open counts", not d.is_current_open(
		{"ok": true, "cmd": "open", "model": "/tmp/doc-b.FCStd", "seq": open_b["seq"]}))

	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.ops.append(op("r1")); d.sync()
	d.on_sync_reply({"ok": true, "cmd": "flush", "seq": null})
	d.on_sync_reply({"ok": true, "cmd": "bye"})
	check("a lifecycle reply doesn't touch sync state", d.in_flight and seen["synced"].is_empty() and seen["idle"] == 0
		and seen["failed"].is_empty())

	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.opened = true
	d.ops.append(op("r1")); d.sync()
	var lost_seq: int = d.seq
	d.on_link_up()                                      # a new worker: the model goes again
	d.ops.append(op("r2")); d.sync()                    # an edit while that resend is in flight
	var syncs_before: int = c.syncs().size()
	d.on_sync_reply(reply(d, ["r1"], lost_seq))         # an answer from before the restart
	check("a reply from before a reconnect doesn't clear in_flight", d.in_flight and d.dirty
		and c.syncs().size() == syncs_before and seen["synced"].is_empty())
	d.on_sync_reply(reply(d, ["r1"], c.syncs().back()["seq"]))
	check("the resend's answer sends the next state", c.syncs().size() == syncs_before + 1
		and c.last()["oplog"]["ops"].size() == 2 and d.in_flight)
	d.on_sync_reply(reply(d, ["r1", "r2"], d.seq))
	check("and that one is shown", seen["synced"].size() == 1 and not d.in_flight)

	# --- drawing requests are consumed by the next send, idle or busy ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.request_drawing()
	check("idle drawing request sends immediately", c.syncs().size() == 1 and c.last()["drawing"] == true)
	d.on_sync_reply(reply(d, [], d.seq))
	d.sync()
	check("sent drawing request clears before the next sync", c.syncs().size() == 2 and c.last()["drawing"] == false)

	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.sync()
	d.request_drawing()
	check("drawing request during sync waits", c.syncs().size() == 1 and d.dirty and not c.last()["drawing"])
	d.ops.append(op("r1")); d.sync()
	d.request_drawing()
	d.on_sync_reply(reply(d, [], 1))
	check("busy drawing requests coalesce with latest edits into the follow-up", c.syncs().size() == 2
		and c.last()["drawing"] == true and c.last()["seq"] == d.seq
		and c.last()["oplog"]["ops"].size() == 1 and not d.dirty and d.in_flight)
	d.on_sync_reply(reply(d, ["r1"], d.seq))
	check("drawing reply settles without an extra request", c.syncs().size() == 2 and seen["idle"] == 1)
	d.sync()
	check("follow-up consumes drawing flag once", c.syncs().size() == 3 and c.last()["drawing"] == false)

	# A queued drawing belongs to its model, not the model switched to afterwards.
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.sync(); d.request_drawing()
	var drawing_seq: int = d.seq
	d.reset()
	d.open("/tmp/doc-other.FCStd", false)
	d.on_sync_reply(reply(d, [], drawing_seq - 1))     # the answer to the sync in flight (the drawing was queued)
	d.sync()
	check("switching models clears a queued drawing request", c.last()["model"] == "/tmp/doc-other.FCStd"
		and c.last()["drawing"] == false)

	# --- test hook: delay goes out once ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.test_delay_ms = 300; d.sync()
	d.on_sync_reply(reply(d, [], 1)); d.sync()
	check("delay_ms is sent once", c.syncs()[0]["delay_ms"] == 300 and c.syncs()[1]["delay_ms"] == 0)

	# --- a failed save (T79, I54) and closing (I55) ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	var closes := {"ready": 0, "blocked": []}
	d.close_ready.connect(func(): closes["ready"] += 1)
	d.close_blocked.connect(func(r): closes["blocked"].append(r))
	d.on_opened({"ok": true, "rev": 3}, false)
	check("closing with everything saved can go at once, asking the worker nothing",
		d.begin_close() and c.sent.is_empty() and not d.closing)
	d.ops.append(op("r1")); d.sync()
	d.on_sync_reply(reply(d, ["r1"], d.seq, {"rev": 4}))
	d.on_save_failed({"cmd": "save_failed", "model": "/tmp/other.FCStd", "rev": 4, "error": "OSError: x"})
	check("another model's failed save is ignored", d.save_error == "")
	d.on_save_failed({"ok": false, "cmd": "save_failed", "model": d.model_path, "rev": 4,
		"error": "PermissionError: the folder x is read-only"})
	check("a failed save keeps its reason, without the exception's name", d.save_error == "the folder x is read-only"
		and d.unsaved() and d.saved_rev == 3)
	d.ops.append(op("r2")); d.sync()
	check("closing while a sync is in flight waits for it before asking for a save",
		not d.begin_close() and d.closing and c.last()["cmd"] == "sync")
	d.on_sync_reply(reply(d, ["r1", "r2"], d.seq, {"rev": 4}))
	var fl: Dictionary = c.last()
	check("then it asks the worker to save this model", fl["cmd"] == "flush" and fl["model"] == d.model_path
		and fl["seq"] == d.close_seq)
	d.on_flush_reply({"ok": false, "cmd": "flush", "seq": fl["seq"], "saved": [],
		"failed": [{"model": d.model_path, "rev": 4, "error": "PermissionError: the folder x is read-only"}],
		"error": "couldn't save doc-test.FCStd: PermissionError: the folder x is read-only"})
	check("a flush that couldn't save blocks closing, with the reason", closes["ready"] == 0 and not d.closing
		and closes["blocked"] == ["the folder x is read-only"])
	check("Retry asks again", not d.begin_close() and c.last()["cmd"] == "flush" and c.last()["seq"] == d.close_seq)
	d.on_flush_reply({"ok": false, "cmd": "flush", "seq": d.close_seq - 1, "saved": [], "failed": []})
	check("an answer to an older flush doesn't decide", closes["blocked"].size() == 1 and closes["ready"] == 0)
	var retry_seq: int = d.close_seq
	d.on_saved({"cmd": "saved", "model": d.model_path, "rev": 4})
	check("a save landing clears the failure", d.save_error == "" and not d.unsaved())
	d.on_flush_reply({"ok": true, "cmd": "flush", "seq": retry_seq, "saved": [{"model": d.model_path, "rev": 4}], "failed": []})
	check("and the flush that saved it lets the window close", closes["ready"] == 1 and not d.closing)
	d.ops.append(op("r3")); d.sync(); d.on_sync_reply(reply(d, ["r1", "r2", "r3"], d.seq, {"rev": 5}))
	d.begin_close(); d.cancel_close()
	d.on_flush_reply({"ok": true, "cmd": "flush", "seq": c.last()["seq"], "saved": [], "failed": []})
	check("Cancel: the flush's answer no longer closes the window", closes["ready"] == 1 and not d.closing)
	d.on_save_failed({"cmd": "save_failed", "model": d.model_path, "rev": 5, "error": "OSError: Failed to open file"})
	d.reset()
	check("switching models forgets the old model's failed save", d.save_error == "")

	# --- a recovered save (A32): the open reply's recovered field, shown once ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.on_opened({"ok": true, "rev": 6, "ops": [op("r1")], "recovered": {"from": "prev", "rev": 6, "why": "the journal was missing"}}, true)
	check("an open that recovered says so in the save indicator", d.recovered_note == "Recovered the last whole save (rev 6)")
	d.on_saved({"cmd": "saved", "model": d.model_path, "rev": 7})
	check("... once: the next save that lands clears it", d.recovered_note == "")
	d.on_opened({"ok": true, "rev": 7, "ops": [op("r1")]}, true)
	check("an open with nothing recovered says nothing", d.recovered_note == "")
	check("finishing a save that stopped part way reads differently",
		d.recovered_text({"from": "new", "rev": 8, "why": "x"}) == "Finished the last save (rev 8)")
	d.on_opened({"ok": true, "rev": 8, "ops": [], "recovered": {"from": "new", "rev": 8, "why": "x"}}, true)
	d.reset()
	check("switching models forgets the note", d.recovered_note == "")

	# --- outside saves (A36, T64): FreeCAD saved the model ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	var waits := [0]
	var reloads: Array = []
	var kept: Array = []
	d.outside_waiting.connect(func(): waits[0] += 1)
	d.reloaded.connect(func(r): reloads.append(r))
	d.on_opened({"ok": true, "rev": 2, "ops": [op("r1"), op("r2")]}, true)
	d.on_outside_save({"cmd": "outside_save", "model": "/tmp/other.FCStd", "rev": 2, "unsaved": false})
	check("another model's outside save is ignored", d.outside.is_empty() and c.sent.is_empty())
	d.on_outside_save({"cmd": "outside_save", "model": d.model_path, "rev": 2, "unsaved": false})
	var rl: Dictionary = c.last()
	check("with nothing on its way, an outside save is reloaded at once",
		rl["cmd"] == "reload" and rl["model"] == d.model_path and rl["outdir"] == d.out_dir and waits[0] == 0)
	d.ops.append(op("r3")); d.sync()
	check("an action drawn while the reload is out waits for it (no sync on the old file)", c.syncs().is_empty())
	d.on_sync_reply(reply(d, ["r1", "r2", "r3"], rl["seq"]))
	check("a sync answer can't pass for the reload's", d.outside_seq == rl["seq"] and seen["synced"].is_empty())
	d.on_reload_reply({"ok": true, "cmd": "reload", "seq": rl["seq"], "model": d.model_path, "rev": 2,
		"ops": [op("r1")], "undo_floor": 1, "changed": ["b1"], "removed": ["b2"], "dropped": [op("r2")]})
	check("the reload's ops are the list, with the action drawn meanwhile on top",
		d.ops.map(func(o): return o["id"]) == ["r1", "r3"] and reloads.size() == 1)
	check("what FreeCAD's save didn't have is dropped from the list and remembered",
		seen["removed_ops"] == ["r2"] and d.dropped.map(func(o): return o["id"]) == ["r2"])
	check("undo stops at the FreeCAD change", d.undo_floor == 1 and d.saved_rev == 2 and d.outside.is_empty())
	check("then the action drawn meanwhile is synced on top", c.last()["cmd"] == "sync"
		and c.last()["oplog"]["ops"].map(func(o): return o["id"]) == ["r1", "r3"])

	t = make(); d = t[0]; c = t[1]; seen = t[2]
	waits = [0]
	d.outside_waiting.connect(func(): waits[0] += 1)
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.ops.append(op("r2")); d.sync()
	var s1: int = d.seq
	d.on_outside_save({"cmd": "outside_save", "model": d.model_path, "rev": 1, "unsaved": true})
	check("with a sync on its way, an outside save waits (main gives it OUTSIDE_SAVE_WAIT)",
		waits[0] == 1 and c.last()["cmd"] == "sync" and not d.outside.is_empty())
	d.on_sync_reply(reply(d, ["r1", "r2"], s1))
	check("once it lands, the reload goes", c.last()["cmd"] == "reload" and seen["idle"] == 0)
	d.on_reload_reply({"ok": true, "cmd": "reload", "seq": c.last()["seq"], "model": d.model_path, "rev": 1,
		"ops": [op("r1")], "undo_floor": 1, "changed": [], "removed": ["b2"], "dropped": [op("r2")]})
	check("and the landed action FreeCAD's save lacks is dropped", d.ops.size() == 1 and d.dropped.size() == 1
		and seen["idle"] == 1)

	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.ops.append(op("r2")); d.sync()
	d.on_outside_save({"cmd": "outside_save", "model": d.model_path, "rev": 1, "unsaved": true})
	d.send_reload()
	var forced: Dictionary = c.last()
	check("'Use FreeCAD's version' reloads even with a sync out", forced["cmd"] == "reload")
	d.on_sync_reply(reply(d, ["r1", "r2"], forced["seq"] - 1))
	check("the stuck sync's late answer then counts for nothing", seen["synced"].is_empty() and d.outside_seq == forced["seq"])

	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.kept_mine.connect(func(r): kept.append(r))
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.ops.append(op("r2")); d.sync()
	var s2: int = d.seq
	d.on_outside_save({"cmd": "outside_save", "model": d.model_path, "rev": 1, "unsaved": true})
	d.send_keep_mine()
	var km: Dictionary = c.last()
	check("'Keep Shop Sketch's' asks the worker to keep both", km["cmd"] == "keep_mine" and km["model"] == d.model_path
		and d.outside.is_empty())
	d.on_sync_reply(reply(d, ["r1", "r2"], s2, {"rev": 2}))
	check("its actions carry on landing, and no reload follows", seen["synced"].size() == 1 and c.last()["cmd"] == "keep_mine")
	d.on_keep_mine_reply({"ok": true, "cmd": "keep_mine", "seq": km["seq"], "model": d.model_path,
		"aside": "/tmp/doc-test.freecad-20261122-120000.FCStd", "rev": 2})
	check("the answer says where FreeCAD's file went and the save landed", kept.size() == 1 and d.saved_rev == 2)

	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.ops.append(op("r2")); d.sync()
	d.on_outside_save({"cmd": "outside_save", "model": d.model_path, "rev": 1, "unsaved": true})
	var n_sent: int = c.sent.size()
	d.on_link_up()
	check("a worker back after a crash gets no sync while the choice is open", c.sent.size() == n_sent and d.dirty)
	d.send_keep_mine()
	check("the choice then sends the model again", c.sent[-2]["cmd"] == "keep_mine" and c.last()["cmd"] == "sync")
	d.reset()
	check("switching models forgets an outside save", d.outside.is_empty() and d.dropped.is_empty())

	for n in made: n.free()
	print("DOCUMENT TESTS: %d passed, %d failed" % [passed, failed])
	quit(1 if failed > 0 else 0)
