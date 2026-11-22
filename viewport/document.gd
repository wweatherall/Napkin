extends Node
## The document controller (A31, T39): one model's action list and its sync with FreeCAD.
## It owns the model path, the ops, id counters, request numbering, which ops FreeCAD has confirmed, the undo floor,
## the redo stack and the save revisions. Tools append to `ops` and call sync(); FreeCAD's replies come in here and
## go out as signals. It knows nothing of meshes, shaders or the camera: main.gd draws what the signals say.
## Undo and (later) branching history (U01, T36) go through here.

signal sync_started                 # a new desired state is on its way to FreeCAD (sync())
signal sent(seq_no: int)            # a sync request left, with this seq
signal synced(resp: Dictionary)     # FreeCAD's answer for the current state (nothing newer waiting)
signal sync_failed(error: String)   # the worker couldn't run the sync
signal save_changed                 # pending_rev, saved_rev or save_error moved
signal close_ready                  # closing (begin_close): the latest revision is on disk, the window may go
signal close_blocked(reason: String)   # closing: the latest revision couldn't be saved (I55: ask what to do)
signal op_removed(op: Dictionary)   # one op left the list (undo, rejection): drop what it drew
signal removed                      # done removing (one or several): show the state before resyncing
signal idle                         # nothing in flight and nothing waiting

var client                          # anything with send(Dictionary) (worker_client.gd; a stand-in in tests)
var model_path := ""                # the FreeCAD file: the model itself (A21)
var out_dir := ""                   # where the worker writes this model's meshes and exports

var ops: Array = []
var counters := {"pr": 0, "r": 0, "b": 0, "pp": 0, "m": 0, "mv": 0, "mu": 0, "dt": 0, "as": 0, "a": 0, "sm": 0, "tg": 0, "hd": 0, "del": 0}
var seq := 0                        # numbers each desired state; a reply counts only for the latest
var in_flight := false
var in_flight_seq := -1             # the seq of the sync in flight: only its answer clears in_flight (T70)
var open_seq := -1                  # the seq of the latest open: an older open's answer is ignored (T70)
var dirty := false                  # changed since the request in flight: send again when it returns
var _drawing_pending := false       # include drawing=true in the next sync sent for this model
var sent_at := {}                   # seq -> msec
var last_sync_ms := 0
var undo_floor := 0                 # ops before this came from a file FreeCAD has since edited
var confirmed_ids := {}             # op ids FreeCAD has already confirmed
var opened := false                 # the worker has answered our "open"
var start_fresh := false            # tests: the first open starts the file empty
var pending_rev := 0                # the model revision the last confirmed change will be saved as
var saved_rev := 0                  # the revision the worker last said it saved
var save_error := ""                # why the last save failed ("" once a save lands): the indicator says so (I54)
var recovered_note := ""            # opening fell back to the newest whole save (A32): shown until the next save lands
var closing := false                # begin_close(): waiting for the latest revision to be saved (I55)
var close_seq := -1                 # the seq of closing's flush: only its answer counts
var test_delay_ms := 0              # test hook (P02): ask the worker to sit on its next answer

# Linear redo (T31), until branch history (U01) keeps the paths you leave: each undo puts its action here with the
# action list it left behind. Redo puts it back only while the list is still that one, so any new action (or an
# amend, a rejection, another model) ends redo, as in SketchUp.
var redo_stack: Array = []          # [{"op", "key": ops key right after its undo}], newest last


static func seq_of(resp: Dictionary) -> int:
	"""A reply's seq, or -1 when it has none (null or missing: it answers no request of ours)."""
	var s = resp.get("seq")
	return int(s) if typeof(s) in [TYPE_INT, TYPE_FLOAT] else -1


static func ops_key(list: Array) -> String:
	return JSON.stringify(list).sha256_text()


func oplog() -> Dictionary:
	return {"format": "oplog/0.1", "units": "mm", "name": "Shop Sketch session", "ops": ops}


# ---------------- sync ----------------
func sync() -> void:
	seq += 1
	dirty = true
	sync_started.emit()
	if not in_flight:
		_send()


func request_drawing() -> void:
	"""Ask for the drawing page with the next sync (export_drawing)."""
	seq += 1
	_drawing_pending = true
	if not in_flight:
		_send()
	else:
		dirty = true


func _send() -> void:
	var drawing := _drawing_pending
	_drawing_pending = false
	in_flight = true
	in_flight_seq = seq
	dirty = false
	sent_at[seq] = Time.get_ticks_msec()
	sent.emit(seq)
	client.send({"cmd": "sync", "model": model_path, "oplog": oplog(), "outdir": out_dir, "seq": seq,
		"drawing": drawing, "delay_ms": test_delay_ms})
	test_delay_ms = 0


func on_sync_reply(resp: Dictionary) -> void:
	"""The worker's answer to a sync. Only the answer for the latest state, with nothing newer waiting, counts.
	An answer to a request that isn't the one in flight (sent before a reconnect, T70) changes nothing."""
	if not in_flight or seq_of(resp) != in_flight_seq: return
	in_flight = false
	if not resp.get("ok", false):
		sync_failed.emit(str(resp.get("error", "?")))
	elif int(resp["seq"]) == seq and not dirty:
		var res: Dictionary = resp["result"]
		for o in res["ops"]:
			if o["status"] == "ok": confirmed_ids[o["id"]] = true
		if res.get("how", "nothing") != "nothing":
			pending_rev = maxi(pending_rev, int(res.get("rev", 0)))
			save_changed.emit()
		last_sync_ms = Time.get_ticks_msec() - int(sent_at.get(seq, Time.get_ticks_msec()))
		synced.emit(resp)
	if dirty and not in_flight:
		_send()
	elif not in_flight:
		idle.emit()
		if closing and close_seq < 0: _send_close_flush()


func on_saved(resp: Dictionary) -> void:
	if resp.get("model", "") == model_path.simplify_path():
		saved_rev = maxi(saved_rev, int(resp.get("rev", 0)))
		save_error = ""
		recovered_note = ""
		save_changed.emit()


func on_save_failed(resp: Dictionary) -> void:
	"""The worker couldn't save this model (T79): it keeps the save and tries again on the next change or flush."""
	if resp.get("model", "") != model_path.simplify_path(): return
	save_error = short_reason(str(resp.get("error", "?")))
	save_changed.emit()


static func short_reason(error: String) -> String:
	"""'PermissionError: the folder x is read-only' -> 'the folder x is read-only' (the exception's name is for the log)."""
	var m := RegEx.create_from_string("^[A-Za-z_.]*(Error|Exception): ").search(error)
	return error.substr(m.get_end()) if m else error


func unsaved() -> bool:
	"""Something confirmed isn't on disk yet, or its save failed."""
	return opened and (pending_rev > saved_rev or save_error != "")


# ---------------- closing the window (I55) ----------------
func begin_close() -> bool:
	"""Closing: true if the window can go now. Otherwise wait for what's in flight, ask the worker to save this
	model, and answer with close_ready or close_blocked. Calling it again (Retry) asks again."""
	if not unsaved() and not in_flight: return true
	closing = true
	close_seq = -1
	if not in_flight: _send_close_flush()
	return false


func cancel_close() -> void:
	closing = false
	close_seq = -1


func _send_close_flush() -> void:
	close_seq = seq                 # numbers the flush without making the latest sync's answer out of date
	client.send({"cmd": "flush", "model": model_path, "seq": close_seq})


func on_flush_reply(resp: Dictionary) -> void:
	"""flush's answer: saved and failed lists (T79). While closing, it decides whether the window may go."""
	for f in resp.get("failed", []):
		on_save_failed(f)
	if not closing or seq_of(resp) != close_seq: return
	close_seq = -1
	if resp.get("ok", false) and pending_rev <= saved_rev:
		closing = false
		close_ready.emit()
	else:
		closing = false             # asking now: Retry calls begin_close again
		close_blocked.emit(save_error if save_error != "" else short_reason(str(resp.get("error", "it isn't saved yet"))))


func on_link_up() -> void:
	"""A new worker (or the same one back): whatever was in flight is gone, so send the model again."""
	in_flight = false
	in_flight_seq = -1
	if not opened:
		send_open()
	else:
		sync()


# ---------------- opening and switching models ----------------
func send_open(fresh := start_fresh and not opened) -> void:
	seq += 1                        # a sync answer still on its way is now out of date too
	open_seq = seq
	client.send({"cmd": "open", "model": model_path, "fresh": fresh, "seq": seq})


func is_current_open(resp: Dictionary) -> bool:
	"""An open reply answers the latest open, for the model this window has now (T70). A refusal or error for an
	older open (a quick A -> B switch) is ignored as well, so it can't send the window back."""
	if seq_of(resp) != open_seq: return false
	return not resp.has("model") or String(resp["model"]) == model_path.simplify_path()


func on_opened(resp: Dictionary, adopt: bool) -> void:
	"""The worker opened the model. adopt: take its history as ours (tests start clean instead)."""
	opened = true
	saved_rev = int(resp.get("rev", 0)); pending_rev = saved_rev
	save_error = ""
	recovered_note = recovered_text(resp.get("recovered", {}))
	save_changed.emit()
	if not adopt: return
	ops = resp.get("ops", [])
	undo_floor = int(resp.get("undo_floor", 0))
	restore_counters()
	for op in ops: confirmed_ids[op["id"]] = true     # already in the file: no wave


static func recovered_text(rec) -> String:
	"""The save indicator's line for an open reply's recovered field (A32); "" when there's none."""
	if not (rec is Dictionary) or rec.is_empty(): return ""
	if rec.get("from", "") == "new":
		return "Finished the last save (rev %d)" % int(rec.get("rev", 0))
	return "Recovered the last whole save (rev %d)" % int(rec.get("rev", 0))


func reset() -> void:
	"""Forget this model's actions (switching models). A reply still on its way is for the old one: ignored."""
	seq += 1
	dirty = false
	_drawing_pending = false
	save_error = ""
	recovered_note = ""
	confirmed_ids.clear()
	ops.clear()
	redo_stack.clear()
	for k in counters: counters[k] = 0
	undo_floor = 0


func open(path: String, fresh: bool) -> void:
	model_path = path
	opened = false
	send_open(fresh)


# ---------------- removing, undo, redo ----------------
func remove_op(oid: String, resync := true) -> void:
	"""Remove one op (undo, or FreeCAD rejected it) and resync."""
	var idx := -1
	for i in ops.size():
		if ops[i]["id"] == oid: idx = i
	if idx < 0: return
	var op: Dictionary = ops[idx]
	ops.remove_at(idx)
	confirmed_ids.erase(oid)
	op_removed.emit(op)
	if resync: _after_removal()


func remove_ops(ids: Array) -> void:
	"""Remove several ops together (a rejection and what built on it): one resync."""
	for oid in ids: remove_op(oid, false)
	_after_removal()


func _after_removal() -> void:
	removed.emit()
	sync()


func at_undo_floor() -> bool:
	return not ops.is_empty() and ops.size() <= undo_floor


func undo() -> void:
	if ops.is_empty() or at_undo_floor(): return
	var op: Dictionary = ops.back().duplicate(true)
	if not redo_stack.is_empty() and redo_stack.back()["key"] != ops_key(ops): redo_stack.clear()
	remove_op(op["id"])
	redo_stack.append({"op": op, "key": ops_key(ops)})


func can_redo() -> bool:
	return not redo_stack.is_empty() and redo_stack.back()["key"] == ops_key(ops)


func take_redo() -> Dictionary:
	"""Put the last undone action back in the list (no sync yet: the caller draws it first). {} if redo is over."""
	if not can_redo():
		redo_stack.clear()
		return {}
	var op: Dictionary = redo_stack.pop_back()["op"]
	ops.append(op)
	return op


# ---------------- what the ops say ----------------
func restore_counters() -> void:
	for op in ops:
		var id: String = op["id"]
		for k in ["del", "pr", "pp", "mv", "mu", "dt", "as", "sm", "tg", "hd", "r", "m"]:
			if id.begins_with(k) and id.substr(k.length()).is_valid_int():
				counters[k] = maxi(counters[k], int(id.substr(k.length())))
				break
		var aids: Array = op.get("groups", {}).values()
		aids.append(String(op.get("new_id", "")) if op["type"] == "make_assembly" else String(op.get("group", "")))
		for aid in aids:
			if String(aid).begins_with("a") and String(aid).substr(1).is_valid_int():
				counters["a"] = maxi(counters["a"], int(String(aid).substr(1)))
		var made: Array = op.get("new_ids", [])
		if op.has("body"): made = [op["body"]]
		for bid in made:
			if String(bid).begins_with("b") and String(bid).substr(1).is_valid_int():
				counters["b"] = maxi(counters["b"], int(String(bid).substr(1)))


func op_of(oid: String) -> Dictionary:
	for op in ops:
		if op["id"] == oid: return op
	return {}


func consumed_rects() -> Dictionary:
	"""Rectangles a push/pull has used."""
	var c := {}
	for op in ops:
		if op["type"] == "push_pull" and op["target"].has("rect"):
			c[op["target"]["rect"]] = true
	return c
