extends RefCounted
## History & worker replies: open, undo, redo, worker sync dispatch, and confirmed-board glue (`m.history`).
## `m.history`; main.gd forwards `undo`, `redo`, `sync`, `_rebuild_rect_drafts`, `_on_worker`, `_on_sync_failed`,
## and `_ops_key` so tools, menus, prompts and tests don't change.
## Entry points: _on_open, undo, redo, _on_op_removed, _on_removed, _rebuild_rect_drafts, oplog, sync,
## _on_sync_started, _on_worker, _on_sync_failed, _on_synced, _apply_confirmed, _on_boards_read, _ops_key.

const Document := preload("res://document.gd")

var m                               # main.gd: doc, pres, measure, sel, appearance, menus, worker, ui_sync, ...


func _init(main = null) -> void:
	m = main


# ---------------- open, undo ----------------
func _on_open(resp: Dictionary) -> void:
	if not m.doc.is_current_open(resp):           # an answer to an older open (a model since left): ignored (T70)
		print("NAPKIN ignored a late open reply for %s" % resp.get("model", "?"))
		return
	if resp.get("error", "") == "already_open":
		if m._model_before == "":
			# launched on a model another window has: that window came forward, this one isn't needed (W13)
			print("NAPKIN %s is open in another window: closing this one" % m.model_path)
			m.get_tree().quit()
		else:
			var name: String = m.model_path.get_file()
			m.switch_model(m._model_before)
			m.worker.say_worker("%s is open in another window" % name)
		return
	m._model_before = ""
	if not resp.get("ok", false):
		m.ui_sync.text = "✗ couldn't open %s: %s" % [m.model_path, resp.get("error", "?")]
		m.ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))
		return
	var adopt: bool = not (m.test_mode and not m.heavy_test and m._first_open)   # tests start clean; a model opened later (switch_model) adopts its history
	m._first_open = false
	m.doc.on_opened(resp, adopt)
	m.measure.on_opened(resp, adopt)
	if not adopt: return
	_rebuild_rect_drafts()
	sync()
	if resp.get("external", false):
		m.reject_note = ""
		m.ui_sync.text = "opened %s - changed in FreeCAD since Napkin last saved it" % m.model_path.get_file()


func undo() -> void:
	if m.doc.at_undo_floor():
		m.ui_sync.text = "✗ can't undo past changes made in FreeCAD (yet)"
		m.ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))
		return
	m.doc.undo()


# ---------------- redo (T31) ----------------
# Linear redo (the document controller keeps the stack and says when it's over); here it's drawn again.
func redo() -> void:
	var op: Dictionary = m.doc.take_redo()
	if op.is_empty():
		m._say_status("Nothing to redo")
		return
	if op.type in ["line", "arc"]:
		m.pres.register_line(op)
	elif op["type"] in ["rect", "circle", "polygon"]:
		if not m.rects.has(op["id"]): m._register_rect(op)
	elif op["type"] in ["push_pull", "new_board"] and not op["target"].has("region"):
		var rid: String = op["target"].get("rect", "")
		if m.drafts.has(rid): m.drafts[rid].queue_free(); m.drafts.erase(rid)
	m._show_state(_ops_key(m.ops))                 # the state it led to, if remembered: on screen at once
	m._apply_context()
	sync()
	m.ui_sync.text = "↷ redone - FreeCAD catching up (%d ops)" % m.ops.size()


func _on_op_removed(op: Dictionary) -> void:
	"""The document dropped an op (undo, rejection): take away what it drew."""
	m.pres.forget_op(op, m.ops, m.doc.consumed_rects())


func _on_removed() -> void:
	var k := _ops_key(m.ops)
	if k != m.shown_key and m._show_state(k):      # undo: the state before this op, remembered, on screen at once
		m.predicted_undo = true
	m._apply_context()                           # an undone hide shows its boards again at once (T28)


func _rebuild_rect_drafts() -> void:
	m.pres.rebuild_rect_drafts(m.ops, m.doc.consumed_rects())


# ---------------- worker sync ----------------
func oplog() -> Dictionary:
	return m.doc.oplog()


func sync() -> void:
	m.doc.sync()


func _on_sync_started() -> void:
	m.properties_seq = -1
	if m.properties_panel != null and m.properties_panel.visible: m.properties_panel.message("Waiting for FreeCAD…")
	m.ui_sync.text = "● draft - FreeCAD catching up (%d ops)" % m.ops.size()
	if m.predicted_undo:
		m.ui_sync.text = "↶ undone - FreeCAD catching up (%d ops)" % m.ops.size()
		m.predicted_undo = false
	m.ui_sync.add_theme_color_override("font_color", Color(0.75, 0.45, 0.0))


func _on_worker(resp: Dictionary) -> void:
	if resp.get("cmd", "") == "inspect_properties":
		m._on_properties(resp)
		return
	if resp.get("cmd", "") == "length":
		m._on_length(resp)
		return
	if resp.get("cmd", "") == "focus":               # someone tried to open this window's model: come forward
		DisplayServer.window_move_to_foreground()
		return
	if resp.get("cmd", "") == "open":
		_on_open(resp)
		return
	if resp.get("cmd", "") == "saved":
		m.doc.on_saved(resp)
		return
	if resp.get("cmd", "") == "save_failed":         # T79: the indicator says why (I54)
		m.doc.on_save_failed(resp)
		return
	if resp.get("cmd", "") == "flush":               # what it saved and couldn't (T79); closing waits on it
		m.doc.on_flush_reply(resp)
		return
	if resp.get("cmd", "") == "outside_save":        # FreeCAD saved this model (A36, T64)
		m.doc.on_outside_save(resp)
		return
	if resp.get("cmd", "") == "reload":
		m.doc.on_reload_reply(resp)
		return
	if resp.get("cmd", "") == "keep_mine":
		m.doc.on_keep_mine_reply(resp)
		return
	if resp.get("cmd", "") == "set_units":
		m.measure.on_set_units_reply(resp)
		return
	if not resp.get("cmd", "") in ["sync", "replay"]:   # flush, hello, bye, quit, or an error for some other request:
		if not resp.get("ok", false):                    # never sync state (T70)
			m.worker.say_worker("✗ worker error: %s" % resp.get("error", "?"))
		return
	if m.true_latency and resp.get("ok", false) and resp.has("wall_ms") and not resp.get("_released", false):
		m.held_resp = resp
		return
	m.doc.on_sync_reply(resp)


func _on_sync_failed(error: String) -> void:
	m.ui_sync.text = "✗ worker error: %s" % error
	m.ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))


func _on_synced(resp: Dictionary) -> void:
	"""FreeCAD's answer for what's on screen: confirmed boards replace drafts, waves finish or go red."""
	var res: Dictionary = resp["result"]
	var drop_now := []
	for o in res["ops"]:
		var w = m.op_waves.get(o["id"])
		if o["status"] == "ok":
			if w != null and w["state"] == "pending": w["state"] = "ok"
		else:
			m._on_rejected(o, w, drop_now)
	var ok_ids := {}
	for o in res["ops"]:
		if o["status"] == "ok": ok_ids[o["id"]] = true
	var key := _ops_key(m.ops.filter(func(op): return ok_ids.has(op["id"])))
	m.pres.show_confirmed(resp["outdir"], key)          # unless already on screen (an undo shown from the cache)
	m.pres.drop_confirmed_drafts(m.doc.consumed_rects())  # a rejected draft stays until its red wave is done
	if m.true_latency: m.doc.last_sync_ms = int((m.movie_clock - float(m.sent_clock.get(m.seq, m.movie_clock))) * 1000.0)
	m.ui_sync.text = "✓ FreeCAD confirmed  (round trip %d ms)" % m.last_sync_ms
	if res.get("how", "") == "rebuilt":
		m.ui_sync.text = "✓ FreeCAD rebuilt the model (undo past its 20-step history, %d ms)" % m.last_sync_ms
	m.ui_sync.add_theme_color_override("font_color", Color(0.1, 0.5, 0.15))
	if m.reject_note != "":
		m.ui_sync.text = "✗ rejected " + m.doc.readable_ids(m.reject_note)
		m.ui_sync.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))
	elif m.live_prefs._startup_prefs_problem != "":
		m._say_status(m.live_prefs._startup_prefs_problem)
		m.live_prefs._startup_prefs_problem = ""
	m.confirmed.emit(m.seq)
	if resp["result"].has("export_ms") and m.drawing_pending:
		m.drawing_pending = false
		m._run_drawing_script()
	for oid in drop_now:
		m.doc.remove_op(oid)


# ---------------- confirmed boards (presenter.gd) ----------------
func _apply_confirmed(dir: String, key: String) -> void:
	m.pres.apply_confirmed(dir, key)


func _on_boards_read(data: Array, dir: String) -> void:
	"""bodies.json, before the presenter builds from it: what each board belongs to, and its wood."""
	m.sel.set_boards(data)
	if m.appearance.wood_library.is_empty() and m.appearance.load_library(dir): m.menus.build_materials_menu()
	m.appearance.set_boards(data)
	m.pres.forget_siblings()


static func _ops_key(list: Array) -> String:
	return Document.ops_key(list)
