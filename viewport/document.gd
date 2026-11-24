extends Node
## The document controller (A31, T39): one model's action list and its sync with FreeCAD.
## It owns the model path, the ops, ID reservations and friendly counters, request numbering, which ops FreeCAD has confirmed, the undo floor,
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
signal outside_waiting              # FreeCAD saved the model while actions were on their way (A36): main waits, then asks
signal outside_failed(error: String) # FreeCAD's save couldn't be opened: ask what to do with both versions
signal outside_keep_failed(error: String) # Shop Sketch's version could not be saved
signal outside_actions_landed       # the pending actions landed and the automatic reload was sent (A39)
signal reloaded(resp: Dictionary)   # FreeCAD's save is the model now: main shows it, with the wave on changed boards
signal kept_mine(resp: Dictionary)  # Shop Sketch's version went over FreeCAD's save (copied aside first)

var client                          # anything with send(Dictionary) (worker_client.gd; a stand-in in tests)
var model_path := ""                # the FreeCAD file: the model itself (A21)
var out_dir := ""                   # where the worker writes this model's meshes and exports

var ops: Array = []
var counters := {"pr": 0, "r": 0, "b": 0, "pp": 0, "m": 0, "mv": 0, "mu": 0, "dt": 0, "as": 0, "a": 0, "sm": 0, "tg": 0, "hd": 0, "del": 0}
# Reservations outlive undo, rejected actions and abandoned futures; only reset() changes documents.
var reserved_ids := {}
var _crypto := Crypto.new()
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
# Outside saves (A36, T64): FreeCAD saved this model. Once nothing is on its way the worker reloads it; while a
# reload is out, syncs wait (they'd build on the old file) and actions drawn meanwhile go on top of the reloaded one.
var outside := {}                   # {"rev", "unsaved", optional "hold_sync"}: a save awaiting resolution
var outside_seq := -1               # the seq of the reload / keep_mine out: only its answer counts
var _outside_command := ""          # the resolution request in flight
var _next_outside := {}            # newer notice received while a choice is in flight
var _ops_at_reload := -1             # ops past this were drawn after the reload left
var dropped: Array = []             # the ops the last reload took out (FreeCAD's save didn't have them; T65)

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
	reserve_values(ops)
	return {"format": "oplog/0.1", "units": "mm", "name": "Shop Sketch session", "ops": ops,
		"reserved_ids": reserved_ids.keys()}


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
	if outside.get("hold_sync", false):
		dirty = true
		return
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
	var ok: bool = resp.get("ok", false)
	if not ok:
		sync_failed.emit(str(resp.get("error", "?")))
		if not outside.is_empty():
			dirty = true
			outside["hold_sync"] = true
			return
	elif not dirty and (seq_of(resp) == seq or _outside_command == "keep_mine"):
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
		if not outside.is_empty():
			if ok and outside_seq < 0 and not outside.get("hold_sync", false):
				send_reload()           # everything landed: now FreeCAD's save can be the model (A36)
				outside_actions_landed.emit()
			return
		idle.emit()
		_flush_when_closing()


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
	if not unsaved() and not busy() and outside.is_empty(): return true
	closing = true
	close_seq = -1
	if dirty and not in_flight and outside.is_empty():
		_send()
	_flush_when_closing()
	return false


func cancel_close() -> void:
	closing = false
	close_seq = -1


func _flush_when_closing() -> void:
	if closing and close_seq < 0 and not busy() and outside.is_empty():
		_send_close_flush()


func _send_close_flush() -> void:
	close_seq = seq                 # numbers the flush without making the latest sync's answer out of date
	client.send({"cmd": "flush", "model": model_path, "seq": close_seq})


func on_flush_reply(resp: Dictionary) -> void:
	"""flush's answer: saved and failed lists (T79). While closing, it decides whether the window may go."""
	for f in resp.get("failed", []):
		on_save_failed(f)
	if not closing or seq_of(resp) != close_seq: return
	close_seq = -1
	if busy() or not outside.is_empty(): return
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
	elif not outside.is_empty():
		if _outside_command == "keep_mine":
			dirty = true               # the lost worker may still have had unsaved actions
			send_keep_mine()
		elif _outside_command == "reload":
			send_reload()
		else:
			outside["hold_sync"] = true
			dirty = true               # a sync would build on FreeCAD's file before the choice (A36)
			outside_waiting.emit()
	else:
		sync()


# ---------------- outside saves (A36, T64) ----------------
func busy() -> bool:
	"""Actions on their way to FreeCAD (or waiting to be sent)."""
	return in_flight or dirty


func on_outside_save(resp: Dictionary) -> void:
	"""The worker says FreeCAD saved this model. Nothing on its way: reload now; else wait for it to land (main
	gives it OUTSIDE_SAVE_WAIT, then asks)."""
	if not opened or resp.get("model", "") != model_path.simplify_path(): return
	var notice := {"rev": resp.get("rev"), "unsaved": bool(resp.get("unsaved", false))}
	if outside_seq >= 0:
		_next_outside = notice
		return
	notice["hold_sync"] = outside.get("hold_sync", false)
	outside = notice
	if busy() or outside["hold_sync"]:
		outside_waiting.emit()
	else:
		send_reload()


func send_reload() -> void:
	"""Take FreeCAD's save as the model (also 'Use FreeCAD's version'): a sync still out is answered too late to count."""
	if _ops_at_reload < 0:
		_ops_at_reload = ops.size()  # retry from the original boundary, including after an error
	seq += 1
	outside_seq = seq
	_outside_command = "reload"
	in_flight = true                # syncs wait for the reload: sync() only marks dirty meanwhile
	in_flight_seq = seq
	client.send({"cmd": "reload", "model": model_path, "outdir": out_dir, "seq": seq})


func send_keep_mine() -> void:
	"""Copy FreeCAD's file aside before saving ours. Wait for the save before sending more edits."""
	seq += 1
	outside_seq = seq
	_outside_command = "keep_mine"
	outside["hold_sync"] = true
	client.send({"cmd": "keep_mine", "model": model_path, "outdir": out_dir, "seq": outside_seq})


func _finish_outside_request() -> void:
	outside_seq = -1
	_outside_command = ""
	if not _next_outside.is_empty():
		outside = _next_outside
	_next_outside = {}


func on_reload_reply(resp: Dictionary) -> void:
	"""FreeCAD's save is the model: its ops become ours (undo stops at them), actions drawn since go on top."""
	if _outside_command != "reload" or seq_of(resp) != outside_seq: return
	var newer_save := not _next_outside.is_empty()
	_finish_outside_request()
	in_flight = false
	if not resp.get("ok", false):
		outside["hold_sync"] = true
		outside_failed.emit(str(resp.get("error", "?")))
		return
	if not newer_save: outside = {}
	var later: Array = ops.slice(_ops_at_reload)
	var keep := {}
	for o in resp.get("ops", []): keep[o["id"]] = true
	for o in ops.slice(0, _ops_at_reload):
		if not keep.has(o["id"]):
			confirmed_ids.erase(o["id"])
			op_removed.emit(o)
	reserve_values(resp.get("reserved_ids", []))
	ops = resp.get("ops", []).duplicate(true)
	_ops_at_reload = ops.size() if newer_save else -1
	ops.append_array(later)
	undo_floor = int(resp.get("undo_floor", 0))
	saved_rev = int(resp.get("rev", 0)); pending_rev = saved_rev
	save_error = ""
	redo_stack.clear()
	dropped = resp.get("dropped", [])
	restore_counters()
	for o in resp.get("ops", []): confirmed_ids[o["id"]] = true
	save_changed.emit()
	reloaded.emit(resp)
	if newer_save:
		send_reload()
	elif not later.is_empty() or dirty:
		sync()
	else:
		idle.emit()
		_flush_when_closing()


func on_keep_mine_reply(resp: Dictionary) -> void:
	if _outside_command != "keep_mine" or seq_of(resp) != outside_seq: return
	var newer_save := not _next_outside.is_empty()
	_finish_outside_request()
	if not resp.get("ok", false):
		outside["hold_sync"] = true
		outside_keep_failed.emit(str(resp.get("error", "?")))
		return
	if not newer_save: outside = {}
	_ops_at_reload = -1
	saved_rev = maxi(saved_rev, int(resp.get("rev", 0)))
	save_error = ""
	save_changed.emit()
	kept_mine.emit(resp)
	if newer_save:
		if not busy():
			send_reload()
			return
		outside_waiting.emit()
	if not in_flight:
		if dirty:
			_send()
		else:
			idle.emit()
			_flush_when_closing()


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
	reserve_values(resp.get("reserved_ids", []))
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
	outside = {}
	_next_outside = {}
	_finish_outside_request()
	_ops_at_reload = -1
	dropped = []
	confirmed_ids.clear()
	reserved_ids.clear()
	ops.clear()
	redo_stack.clear()
	_rejected.clear()
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
func reserve_values(value) -> void:
	# Conservatively reserve strings from old ops too: legacy IDs have no required spelling.
	if value is String:
		if value != "": reserved_ids[value] = true
	elif value is Array:
		for item in value: reserve_values(item)
	elif value is Dictionary:
		for key in value:
			reserve_values(key)
			reserve_values(value[key])


func next_id(prefix: String) -> String:
	if not counters.has(prefix):
		push_error("Document.next_id: unknown prefix \"%s\"" % prefix)
		return ""
	reserve_values(ops)
	counters[prefix] += 1             # friendly number only; random bytes provide identity
	while true:
		var bytes := _crypto.generate_random_bytes(16)
		if bytes.size() != 16:
			push_error("Document.next_id: secure random bytes unavailable")
			return ""
		var id := "%s%d_%s" % [prefix, counters[prefix], bytes.hex_encode()]
		if not reserved_ids.has(id):
			reserved_ids[id] = true
			return id
	return ""


static func board_name(identity: String) -> String:
	var match_id := RegEx.create_from_string("^b([0-9]+)(?:_[0-9a-f]{32})?$").search(identity)
	return "Board " + match_id.get_string(1) if match_id else identity


static func readable_ids(text: String) -> String:
	var pattern := RegEx.create_from_string("\\bb([0-9]+)_[0-9a-f]{32}\\b")
	var names := pattern.sub(text, "Board $1", true)
	var ids := RegEx.create_from_string("\\b([a-z]+[0-9]+)_[0-9a-f]{32}\\b")
	return ids.sub(names, "$1", true)


func restore_counters() -> void:
	reserve_values(ops)
	reserve_values(dropped)
	# These numbers label boards and assemblies; they are never the source of identity.
	var pattern := RegEx.create_from_string("^([a-z]+)([0-9]+)(?:_[0-9a-f]{32})?$")
	for id in reserved_ids:
		var match_id := pattern.search(id)
		if match_id and counters.has(match_id.get_string(1)):
			var prefix := match_id.get_string(1)
			counters[prefix] = maxi(counters[prefix], int(match_id.get_string(2)))


func op_of(oid: String) -> Dictionary:
	for op in ops:
		if op["id"] == oid: return op
	return {}


func consumed_rects() -> Dictionary:
	"""Rectangles a push/pull has used (a region push takes one cell and leaves the profile)."""
	var c := {}
	for op in ops:
		if op["type"] == "push_pull" and op["target"].has("rect") and not op["target"].has("region"):
			c[op["target"]["rect"]] = true
	return c


# ---------------- rejections take what built on them (T16, Q7) ----------------
# FreeCAD rejects an action a moment after you did it; meanwhile you may have drawn on the board it made or the
# face it changed. Those later actions fail too (what they refer to is gone): they join the first rejection,
# go red with it and are removed together, with one message. Independent work stays.
const REJECT_WINDOW_MS := 15000     # a rejection collects its dependents for this long
var _rejected := {}                 # root op id -> {"ids", "bodies", "deps", "at", "note"}


static func _op_refs(op: Dictionary) -> Array:
	"""Ids an op refers to: the board or rectangle it acts on."""
	var out := []
	var pl: Dictionary = op.get("plane", {})
	if pl.has("on"): out.append(pl["on"]["body"])
	var tg: Dictionary = op.get("target", {})
	if op.has("edge_fit"): out.append(op["edge_fit"]["target_body"])
	if tg.has("region"): out.append_array(tg.region.get("lines", []))
	if tg.has("rect"): out.append(tg["rect"])
	if tg.has("face"): out.append(tg["face"]["body"])
	out.append_array(op.get("targets", []))
	if op.has("cut"): out.append_array([op["cut"]["body"], op["cut"]["op"]])
	if op["type"] in ["make_component", "property_edit"]: out.append(op["body"])
	return out


func _op_makes(op: Dictionary) -> Array:
	var out: Array = [op["id"]]
	if op["type"] == "push_pull" and op.has("body"): out.append(op["body"])
	out.append_array(op.get("new_ids", []))
	return out


func _op_touches(op: Dictionary) -> Array:
	"""Boards an op changes in place (a face on them may exist only because of it)."""
	var tg: Dictionary = op.get("target", {})
	if op["type"] == "push_pull" and not op.has("body"):
		if tg.has("rect"):
			var r := op_of(tg["rect"])
			if not r.is_empty() and r["plane"].has("on"): return [r["plane"]["on"]["body"]]
		if tg.has("face"): return [tg["face"]["body"]]
	if op["type"] == "move": return op.get("targets", []) + ([op["cut"]["body"]] if op.has("cut") else [])
	return []


func reject(oid: String, msg: String, now_ms: int, still_playing: Callable = Callable()) -> Dictionary:
	for r in _rejected.keys():
		if now_ms - int(_rejected[r]["at"]) > REJECT_WINDOW_MS and not (still_playing.is_valid() and still_playing.call(r)):
			_rejected.erase(r)
	var op := op_of(oid)
	if op.is_empty(): return {}
	var root := ""
	for r in _rejected:
		var e: Dictionary = _rejected[r]
		for ref in _op_refs(op):
			if e["ids"].has(ref): root = r
		for b in e["bodies"]:
			if msg.contains("'%s'" % b): root = r
		if root != "": break
	if root == "":                                   # a rejection of its own
		root = oid
		var e := {"ids": {}, "bodies": {}, "deps": [], "at": now_ms, "note": "%s: %s" % [oid, msg]}
		for x in _op_makes(op): e["ids"][x] = true
		for b in _op_touches(op): e["bodies"][b] = true
		_rejected[root] = e
		return {"root": root, "joined": false, "note": e["note"]}
	var e: Dictionary = _rejected[root]              # built on an earlier rejection: goes with it
	if not e["deps"].has(oid): e["deps"].append(oid)
	for x in _op_makes(op): e["ids"][x] = true
	for b in _op_touches(op): e["bodies"][b] = true
	var n: int = e["deps"].size()
	var note := "%s (and %d action%s that built on it)" % [e["note"], n, "" if n == 1 else "s"]
	return {"root": root, "joined": true, "note": note}


func rejected_ids(oid: String) -> Array:
	"""If oid is a rejection root, it and the actions that built on it; [] otherwise."""
	if not _rejected.has(oid): return []
	return [oid] + _rejected[oid]["deps"]
