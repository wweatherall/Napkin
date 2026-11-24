extends SceneTree
## The document controller (document.gd, A31, T39) on its own, with no window and no worker: a stand-in client
## records what it sends, and the tests answer for the worker. Checks the sequencing that keeps a stale reply
## from ever reaching the screen: rapid edits, delayed and out-of-date answers, reconnects, model switches, undo.
## Run: Godot --headless --path viewport --script res://test_document.gd
const Document = preload("res://document.gd")
var passed := 0
var failed := 0
var made: Array = []


# Stand-in client for document.gd tests (T110, P42):
# - last_of(cmd) / drain(): inspect what Document sent without matching raw indices.
# - Reply builders below match each request's seq; deliver replies in any order for P42
#   late/out-of-order replies, error_reply() for failed open/reload/keep_mine/save,
#   and d.on_link_up() for P42 worker gone.
class FakeClient:
	var sent: Array = []
	var _drained := 0
	func send(d: Dictionary) -> void: sent.append(d)
	func last() -> Dictionary: return sent.back() if not sent.is_empty() else {}
	func last_of(cmd: String) -> Dictionary:
		for i in range(sent.size() - 1, -1, -1):
			if sent[i].get("cmd", "") == cmd:
				return sent[i]
		return {}
	func drain() -> Array:
		var out := sent.slice(_drained)
		_drained = sent.size()
		return out
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


# Reply and event builders (T110, P42): each reply takes the request it answers so seq matches.
# Use reply() / reload_reply() / keep_mine_reply() / open_reply() / error_reply() in any order
# for P42 late/out-of-order replies or failed commands, and outside_save() for FreeCAD saves.
func reply(d, ok_ids: Array, seq_no: int, extra := {}) -> Dictionary:
	var ops := []
	for i in ok_ids: ops.append({"id": i, "status": "ok"})
	var res := {"ops": ops, "how": "applied", "rev": 1}
	res.merge(extra, true)
	return {"ok": true, "seq": seq_no, "result": res, "outdir": d.out_dir}


func reload_reply(req: Dictionary, ops: Array, extra := {}) -> Dictionary:
	var r := {"ok": true, "cmd": "reload", "seq": req.get("seq"), "model": req.get("model", ""),
		"rev": 1, "ops": ops, "undo_floor": ops.size(), "changed": [], "removed": [], "dropped": []}
	r.merge(extra, true)
	return r


func keep_mine_reply(req: Dictionary, extra := {}) -> Dictionary:
	var r := {"ok": true, "cmd": "keep_mine", "seq": req.get("seq"), "model": req.get("model", ""),
		"aside": "/tmp/doc-test.freecad-20261122-120000.FCStd", "rev": 2}
	r.merge(extra, true)
	return r


func open_reply(req: Dictionary, ops: Array, extra := {}) -> Dictionary:
	var r := {"ok": true, "cmd": "open", "seq": req.get("seq"), "model": req.get("model", ""),
		"rev": 0, "ops": ops}
	r.merge(extra, true)
	return r


func error_reply(req: Dictionary, message: String, extra := {}) -> Dictionary:
	var r := {"ok": false, "cmd": req.get("cmd", ""), "seq": req.get("seq"), "error": message}
	if req.has("model"): r["model"] = req["model"]
	r.merge(extra, true)
	return r


func outside_save(d, unsaved := false, extra := {}) -> Dictionary:
	var r := {"cmd": "outside_save", "model": d.model_path, "rev": d.saved_rev, "unsaved": unsaved}
	r.merge(extra, true)
	return r


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
	var t_reg := make(); var d_reg = t_reg[0]
	d_reg.ops = [op("r1"), {"id": "pp1", "type": "push_pull", "body": "b1",
		"target": {"rect": "r1", "region": {"outline": [[0, 0, 0], [100, 0, 0], [100, 200, 0], [0, 200, 0]], "holes": [], "lines": ["r2"], "normal": [0, 0, 1]}}}]
	check("region push leaves consumed_rects empty", d_reg.consumed_rects().is_empty())
	d_reg.ops.append({"id": "pp2", "type": "push_pull", "body": "b2", "target": {"rect": "r1"}})
	check("whole-profile push still consumes its rect", d_reg.consumed_rects() == {"r1": true})

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
	var open_a: Dictionary = c.last_of("open")
	d.reset(); d.open("/tmp/doc-b.FCStd", false)
	var open_b: Dictionary = c.last_of("open")
	check("each open carries its own seq", open_a.has("seq") and open_b["seq"] > open_a["seq"])
	var late_a := open_reply(open_a, [op("r1")], {"rev": 1})
	check("a quick A -> B switch: A's open reply, arriving late, is ignored", not d.is_current_open(late_a))
	check("so is a refusal for the old open (it can't send the window back)",
		not d.is_current_open(error_reply(open_a, "already_open")))
	check("a reply with the right seq for another model is ignored",
		not d.is_current_open(open_reply(open_b, [], {"model": "/tmp/doc-a.FCStd"})))
	check("B's own open reply counts", d.is_current_open(open_reply(open_b, [])))
	d.open("/tmp/doc-b.FCStd", false)
	check("reopening the same model: only the latest open counts", not d.is_current_open(open_reply(open_b, [])))

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
	d.on_outside_save(outside_save(d, false, {"model": "/tmp/other.FCStd"}))
	check("another model's outside save is ignored", d.outside.is_empty() and c.sent.is_empty())
	d.on_outside_save(outside_save(d))
	var rl: Dictionary = c.last_of("reload")
	check("with nothing on its way, an outside save is reloaded at once",
		rl["cmd"] == "reload" and rl["model"] == d.model_path and rl["outdir"] == d.out_dir and waits[0] == 0)
	d.ops.append(op("r3")); d.sync()
	check("an action drawn while the reload is out waits for it (no sync on the old file)", c.syncs().is_empty())
	d.on_sync_reply(reply(d, ["r1", "r2", "r3"], rl["seq"]))
	check("a sync answer can't pass for the reload's", d.outside_seq == rl["seq"] and seen["synced"].is_empty())
	d.on_reload_reply(reload_reply(rl, [op("r1")], {"rev": 2, "changed": ["b1"], "removed": ["b2"], "dropped": [op("r2")]}))
	check("the reload's ops are the list, with the action drawn meanwhile on top",
		d.ops.map(func(o): return o["id"]) == ["r1", "r3"] and reloads.size() == 1)
	check("what FreeCAD's save didn't have is dropped from the list and remembered",
		seen["removed_ops"] == ["r2"] and d.dropped.map(func(o): return o["id"]) == ["r2"])
	check("undo stops at the FreeCAD change", d.undo_floor == 1 and d.saved_rev == 2 and d.outside.is_empty())
	check("then the action drawn meanwhile is synced on top", c.last()["cmd"] == "sync"
		and c.last()["oplog"]["ops"].map(func(o): return o["id"]) == ["r1", "r3"])

	t = make(); d = t[0]; c = t[1]; seen = t[2]
	var errors: Array = []
	d.outside_failed.connect(func(error): errors.append(error))
	d.on_opened({"ok": true, "rev": 2, "ops": [op("r1")]}, true)
	d.on_outside_save(outside_save(d))
	var original_reload: Dictionary = c.last_of("reload")
	d.ops.append(op("r2")); d.sync()
	d.on_link_up()
	var retry: Dictionary = c.last_of("reload")
	check("reconnecting with a reload out sends another reload with a fresh sequence",
		retry["cmd"] == "reload" and retry["seq"] > original_reload["seq"] and d.in_flight)
	d.on_reload_reply(error_reply(original_reload, "stale reply"))
	check("the lost reload's reply leaves the retry in flight", errors.is_empty() and d.outside_seq == retry["seq"])
	c.drain()
	d.on_reload_reply(error_reply(retry, "Invalid project file"))
	check("a failed reload keeps the save pending and emits its error without sending anything",
		d.outside.get("rev") == 2 and d.outside_seq == -1 and not d.in_flight
		and errors == ["Invalid project file"] and c.drain().is_empty())
	d.ops.append(op("r3")); d.sync()
	check("further actions wait for the choice after a failed reload", d.dirty and c.drain().is_empty())

	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.on_opened({"ok": true, "rev": 2, "ops": [op("r1")]}, true)
	d.on_outside_save(outside_save(d))
	d.ops.append(op("r2")); d.sync()
	d.on_link_up()
	d.on_reload_reply(reload_reply(c.last_of("reload"), [op("r1")], {"rev": 2}))
	check("a retried reload still syncs the actions drawn after the first request on top",
		c.last()["cmd"] == "sync" and d.ops.map(func(o): return o["id"]) == ["r1", "r2"])

	t = make(); d = t[0]; c = t[1]; seen = t[2]
	waits = [0]
	d.outside_waiting.connect(func(): waits[0] += 1)
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.ops.append(op("r2")); d.sync()
	var s1: int = d.seq
	d.on_outside_save(outside_save(d, true))
	check("with a sync on its way, an outside save waits (main gives it OUTSIDE_SAVE_WAIT)",
		waits[0] == 1 and c.last()["cmd"] == "sync" and not d.outside.is_empty())
	d.on_sync_reply(reply(d, ["r1", "r2"], s1))
	check("once it lands, the reload goes", c.last()["cmd"] == "reload" and seen["idle"] == 0)
	d.on_reload_reply(reload_reply(c.last_of("reload"), [op("r1")], {"removed": ["b2"], "dropped": [op("r2")]}))
	check("and the landed action FreeCAD's save lacks is dropped", d.ops.size() == 1 and d.dropped.size() == 1
		and seen["idle"] == 1)

	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.ops.append(op("r2")); d.sync()
	d.on_outside_save(outside_save(d, true))
	d.send_reload()
	var forced: Dictionary = c.last_of("reload")
	check("'Use FreeCAD's version' reloads even with a sync out", forced["cmd"] == "reload")
	d.on_sync_reply(reply(d, ["r1", "r2"], forced["seq"] - 1))
	check("the stuck sync's late answer then counts for nothing", seen["synced"].is_empty() and d.outside_seq == forced["seq"])

	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.kept_mine.connect(func(r): kept.append(r))
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.ops.append(op("r2")); d.sync()
	var s2: int = d.seq
	d.on_outside_save(outside_save(d, true))
	d.send_keep_mine()
	var km: Dictionary = c.last_of("keep_mine")
	check("'Keep Shop Sketch's' asks the worker to keep both", km["cmd"] == "keep_mine" and km["model"] == d.model_path
		and not d.outside.is_empty())
	d.on_sync_reply(reply(d, ["r1", "r2"], s2, {"rev": 2}))
	check("its actions carry on landing, and no reload follows", seen["synced"].size() == 1 and c.last()["cmd"] == "keep_mine")
	d.on_keep_mine_reply(keep_mine_reply(km))
	check("the answer says where FreeCAD's file went and the save landed", kept.size() == 1 and d.saved_rev == 2)

	t = make(); d = t[0]; c = t[1]; seen = t[2]
	waits = [0]
	d.outside_waiting.connect(func(): waits[0] += 1)
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.ops.append(op("r2")); d.sync()
	d.on_outside_save(outside_save(d, true))
	c.drain()
	d.on_link_up()
	check("reconnecting while waiting for actions starts a new wait without sending a sync",
		c.drain().is_empty() and d.dirty and waits[0] == 2)
	d.send_keep_mine()
	var kept_request: Dictionary = c.last_of("keep_mine")
	d.on_keep_mine_reply(keep_mine_reply(kept_request))
	check("the choice then sends the model again", kept_request["cmd"] == "keep_mine" and c.last()["cmd"] == "sync")
	d.reset()
	check("switching models forgets an outside save", d.outside.is_empty() and d.dropped.is_empty())

	# --- H098 outside-save regressions ---
	var h098_checks := [
		"outside_save with rev null reloads instead of aborting",
		"retrying a failed reload keeps actions drawn after the first reload left",
		"a failed sync while waiting on an outside save does not auto-reload or close the question",
		"a failed keep_mine keeps the outside save pending instead of syncing on a held model",
		"reconnecting while keep_mine is in flight retries keep_mine instead of syncing over FreeCAD's file",
		"a late reload reply after keep_mine cannot hijack the pending keep_mine",
		"a second outside_save while a reload is out is reloaded after the first finishes",
		"a second outside_save while sync is held keeps sync held",
		"a second outside_save while keep_mine is in flight reloads once keep_mine lands",
		"begin_close does not close immediately when unsynced actions are held after a failed reload",
	]
	# 1. outside_save with rev: null (unreadable or foreign FreeCAD file)
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.on_opened({"ok": true, "rev": 2, "ops": [op("r1")]}, true)
	d.on_outside_save(outside_save(d, false, {"rev": null}))
	check(h098_checks[0],
		not d.outside.is_empty() and c.last().get("cmd", "") == "reload")

	# 2. retrying a failed reload preserves actions drawn after the first reload left
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.on_opened({"ok": true, "rev": 2, "ops": [op("r1")]}, true)
	d.on_outside_save(outside_save(d))
	var first_rl: Dictionary = c.last_of("reload")
	d.ops.append(op("r2")); d.sync()
	d.on_reload_reply(error_reply(first_rl, "Invalid project file"))
	d.send_reload()
	d.on_reload_reply(reload_reply(c.last_of("reload"), [op("r1")], {"rev": 2}))
	check(h098_checks[1],
		d.ops.map(func(o): return o["id"]) == ["r1", "r2"] and c.last().get("cmd", "") == "sync"
		and c.last()["oplog"]["ops"].map(func(o): return o["id"]) == ["r1", "r2"])

	# 3. failed sync while waiting on an outside save does not auto-reload or close the question
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	var landed := [0]
	d.outside_actions_landed.connect(func(): landed[0] += 1)
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.ops.append(op("r2")); d.sync()
	d.on_outside_save(outside_save(d, true))
	d.on_sync_reply(error_reply(c.last_of("sync"), "OpError: boom"))
	check(h098_checks[2],
		landed[0] == 0 and c.last().get("cmd", "") != "reload" and d.outside_seq == -1
		and d.dirty and d.outside.get("hold_sync", false))

	# 4. failed keep_mine keeps the outside save pending and sync held
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.ops.append(op("r2")); d.sync()
	d.on_outside_save(outside_save(d, true))
	d.on_link_up()
	d.send_keep_mine()
	d.on_keep_mine_reply(error_reply(c.last_of("keep_mine"), "PermissionError: read-only"))
	c.drain()
	d.ops.append(op("r3")); d.sync()
	check(h098_checks[3],
		not d.outside.is_empty() and c.drain().is_empty())

	# 5. worker lost while keep_mine is in flight
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.ops.append(op("r2")); d.sync()
	d.on_outside_save(outside_save(d, true))
	d.send_keep_mine()
	c.drain()
	d.on_link_up()
	var sent_on_reconn: Array = c.drain()
	check(h098_checks[4],
		not sent_on_reconn.is_empty() and sent_on_reconn[0]["cmd"] == "keep_mine")

	# 6. late reload reply after keep_mine cannot hijack the pending keep_mine
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	var late_reloads: Array = []
	var late_kept: Array = []
	d.reloaded.connect(func(r): late_reloads.append(r))
	d.kept_mine.connect(func(r): late_kept.append(r))
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1"), op("r2")]}, true)
	d.on_outside_save(outside_save(d))
	var rl_for_km: Dictionary = c.last_of("reload")
	d.on_reload_reply(error_reply(rl_for_km, "Invalid project file"))
	d.send_keep_mine()
	var km_sent: Dictionary = c.last_of("keep_mine")
	d.on_reload_reply(reload_reply(rl_for_km, [op("r1")], {"dropped": [op("r2")]}))
	d.on_keep_mine_reply(keep_mine_reply(km_sent, {"aside": "/tmp/a.FCStd"}))
	check(h098_checks[5],
		late_reloads.is_empty() and d.ops.size() == 2 and late_kept.size() == 1)

	# 7. second outside_save while a reload is in flight
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.on_outside_save(outside_save(d))
	var rl_first: Dictionary = c.last_of("reload")
	d.on_outside_save(outside_save(d, false, {"rev": 2}))
	d.on_reload_reply(reload_reply(rl_first, [op("r1")]))
	check(h098_checks[6],
		c.sent.filter(func(x): return x["cmd"] == "reload").size() == 2 or not d.outside.is_empty())

	# 8. second outside_save while hold_sync is set with pending actions
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.on_outside_save(outside_save(d))
	d.on_reload_reply(error_reply(c.last_of("reload"), "Invalid project file"))
	d.ops.append(op("r2")); d.sync()
	d.on_outside_save(outside_save(d, true))
	c.drain()
	d.ops.append(op("r3")); d.sync()
	check(h098_checks[7],
		c.drain().all(func(x): return x["cmd"] != "sync"))

	# 9. second outside_save while keep_mine is in flight
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.on_outside_save(outside_save(d))
	d.on_reload_reply(error_reply(c.last_of("reload"), "Invalid project file"))
	d.send_keep_mine()
	var km_only: Dictionary = c.last_of("keep_mine")
	d.on_outside_save(outside_save(d, false, {"rev": 2}))
	d.on_keep_mine_reply(keep_mine_reply(km_only, {"aside": "/tmp/a.FCStd"}))
	check(h098_checks[8],
		c.last().get("cmd", "") == "reload")

	# 10. begin_close when unsynced actions are held after a failed reload
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.on_opened({"ok": true, "rev": 2, "ops": [op("r1")]}, true)
	d.on_outside_save(outside_save(d))
	d.on_reload_reply(error_reply(c.last_of("reload"), "Invalid project file"))
	d.ops.append(op("r2")); d.sync()
	check(h098_checks[9],
		not d.begin_close())

	# --- T110 helper checks: last_of/drain + reload_reply/error_reply + out-of-order sync replies ---
	t = make(); d = t[0]; c = t[1]; seen = t[2]
	var h_errs: Array = []
	d.outside_failed.connect(func(e): h_errs.append(e))
	d.on_opened({"ok": true, "rev": 1, "ops": [op("r1")]}, true)
	d.on_outside_save(outside_save(d))
	var first_reload_req: Dictionary = c.last_of("reload")
	d.on_reload_reply(error_reply(first_reload_req, "broken file"))
	d.send_reload()
	var second_reload_req: Dictionary = c.last_of("reload")
	d.on_reload_reply(reload_reply(second_reload_req, [op("r1")], {"rev": 2}))
	check("helpers reload_reply and error_reply built from last_of(\"reload\") match seq and recover on retry",
		h_errs == ["broken file"] and second_reload_req["seq"] > first_reload_req["seq"]
		and d.outside.is_empty() and d.saved_rev == 2 and d.undo_floor == 1)

	t = make(); d = t[0]; c = t[1]; seen = t[2]
	d.opened = true
	d.ops.append(op("r1")); d.sync()
	var sync_old: Dictionary = c.last_of("sync")
	d.on_link_up()                                      # resend under a newer seq
	var sync_new: Dictionary = c.last_of("sync")
	d.on_sync_reply(reply(d, ["r1"], sync_new["seq"], {"rev": 2}))
	var synced_after_new: int = seen["synced"].size()
	var saves_after_new: int = seen["saves"]
	d.on_sync_reply(reply(d, ["r1"], sync_old["seq"], {"rev": 1}))
	check("delivering two sync replies in the wrong order: the older one changes nothing",
		sync_new["seq"] > sync_old["seq"] and synced_after_new == 1 and seen["synced"].size() == 1
		and seen["saves"] == saves_after_new and d.pending_rev == 2 and not d.in_flight)

	for n in made: n.free()
	print("DOCUMENT TESTS: %d passed, %d failed" % [passed, failed])
	quit(1 if failed > 0 else 0)
