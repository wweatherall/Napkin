extends Node

var m: Node


func _init(window: Node) -> void:
	m = window


# ---------------- closing the window (I55, T79) ----------------
# Closing (the window's close button, Cmd+Q) waits until the latest revision is on disk. If it can't be saved, a
# dialog says why: Retry, Close without saving (the journal still has the actions), or Cancel.
const CLOSE_WAIT_S := 10.0          # FreeCAD hasn't answered closing's save in this long: ask (tunable)
var _close_asking := false          # the dialog is up
var _close_try := 0                 # numbers each try, so an old try's timer can't ask during a newer one
var close_asked: Array = []         # tests: the reasons the dialog would have given (it isn't shown in test mode)
var close_done := false             # tests: close_now ran (the window would have gone)


func request_close() -> void:
	if _close_asking or m.doc.closing: return      # already waiting, or asking
	if m.doc.begin_close():
		close_now()
		return
	m.worker.say_worker("saving %s before closing…" % m.model_path.get_file())
	_close_try += 1
	var try_then := _close_try
	get_tree().create_timer(CLOSE_WAIT_S).timeout.connect(func() -> void:
		if m.doc.closing and not _close_asking and _close_try == try_then:
			m.doc.cancel_close()
			ask_close("FreeCAD hasn't answered"))


func ask_close(reason: String) -> void:
	_close_asking = true
	var text := "%s couldn't be saved: %s.\nIts actions are kept in its journal beside the file." % [m.model_path.get_file(), reason]
	if m.test_mode:
		close_asked.append(reason)
		return
	if DisplayServer.has_feature(DisplayServer.FEATURE_NATIVE_DIALOG):
		DisplayServer.dialog_show("Couldn't save", text, PackedStringArray(["Retry", "Close without saving", "Cancel"]),
			func(i: int) -> void: close_choice(["retry", "discard", "cancel"][clampi(i, 0, 2)]))
		return
	var dlg := ConfirmationDialog.new()
	dlg.title = "Couldn't save"
	dlg.dialog_text = text
	dlg.ok_button_text = "Retry"
	dlg.add_button("Close without saving", true, "discard")
	dlg.confirmed.connect(func() -> void: dlg.queue_free(); close_choice("retry"))
	dlg.canceled.connect(func() -> void: dlg.queue_free(); close_choice("cancel"))
	dlg.custom_action.connect(func(_a: StringName) -> void: dlg.queue_free(); close_choice("discard"))
	add_child(dlg)
	dlg.popup_centered()


func close_choice(choice: String) -> void:
	_close_asking = false
	match choice:
		"retry": request_close()
		"discard":
			print("SHOPSKETCH closing without saving %s (rev %d not saved: %s)" % [m.model_path, m.doc.pending_rev, m.doc.save_error])
			close_now()
		_:
			m.doc.cancel_close()
			m.ui.update_saved()
			m.ui_sync.text = ""


func close_now() -> void:
	close_done = true
	if m.test_mode: return                # tests check close_done; the run goes on
	m.worker.shutdown_worker()
	get_tree().quit()


# ---------------- outside saves (A36, T64) ----------------
# FreeCAD saved the open model. The document reloads it once nothing is on its way; if actions haven't landed in
# OUTSIDE_SAVE_WAIT, a dialog asks: Use FreeCAD's version (reload; the unfinished actions stay in the journal) or
# Keep Shop Sketch's (FreeCAD's file copied aside first). The worker writes nothing over FreeCAD's save meanwhile.
const OUTSIDE_SAVE_WAIT := 10.0     # seconds actions pending at an outside save get to land before asking (tunable)
var _outside_try := 0               # numbers each wait, so an old wait's timer can't ask
var _outside_dialog: ConfirmationDialog
var outside_question_model := ""  # the open Godot dialog, or the question simulated in test mode
var _outside_closed_model := ""    # report an automatically closed question when its reload lands
var _outside_question_text := ""
var _outside_question_reason := ""
var outside_asked: Array = []       # tests: the reasons the dialog would have given (it isn't shown in test mode)
var outside_closed := 0            # tests: questions that automatically closed when the actions landed
var reload_waves: Array = []        # tests: the boards the last reload's wave ran on


func on_outside_waiting() -> void:
	m.worker.say_worker("FreeCAD saved %s - waiting for Shop Sketch's last actions to land" % m.model_path.get_file())
	_outside_try += 1
	var try_then := _outside_try
	get_tree().create_timer(OUTSIDE_SAVE_WAIT).timeout.connect(func() -> void:
		if _outside_try == try_then and not m.doc.outside.is_empty() and m.doc.outside_seq < 0:
			ask_outside())


func ask_outside() -> void:
	if outside_question_model == m.model_path: return
	var reason := "they hadn't landed after %d s" % int(OUTSIDE_SAVE_WAIT)
	if not m.client.connected or (m.worker.worker_pid > 0 and not OS.is_process_running(m.worker.worker_pid)):
		reason = "the FreeCAD worker stopped"
	elif m.doc.in_flight:
		reason = "the FreeCAD worker hasn't answered for %d s (it may be stuck)" % int(OUTSIDE_SAVE_WAIT)
	m.worker.log_worker("outside save of %s with actions pending: %s; asking" % [m.model_path, reason])
	var text := ("%s was saved in FreeCAD while Shop Sketch still had actions on their way: %s.\n\n"
		+ "Use FreeCAD's version: its file becomes the model; Shop Sketch's unfinished actions stay in the journal.\n"
		+ "Keep Shop Sketch's: FreeCAD's file is first copied aside as %s.freecad-<time>.FCStd.") % [
		m.model_path.get_file(), reason, m.model_path.get_file().get_basename()]
	_show_outside_question(text, reason)


func on_outside_failed(error: String) -> void:
	_outside_try += 1
	_outside_closed_model = ""
	var reason := "couldn't open FreeCAD's save: " + error
	m.worker.log_worker("outside save of %s: %s; asking" % [m.model_path, reason])
	var text := ("%s was saved in FreeCAD, but Shop Sketch couldn't open FreeCAD's save: %s.\n\n"
		+ "Use FreeCAD's version: try opening it again.\n"
		+ "Keep Shop Sketch's: FreeCAD's file is first copied aside as %s.freecad-<time>.FCStd.") % [
		m.model_path.get_file(), error, m.model_path.get_file().get_basename()]
	_show_outside_question(text, reason)


func on_outside_keep_failed(error: String) -> void:
	m._on_sync_failed(error)
	m.worker.log_worker("outside save of %s: %s" % [m.model_path, error])
	_outside_try += 1
	var try_then := _outside_try
	# The macOS alert handles its choice on the same call stack. Reopen on the next turn.
	var ask_again := func() -> void:
		if _outside_try != try_then or m.doc.outside.is_empty() or m.doc.outside_seq >= 0:
			return
		if _outside_question_text.is_empty():
			ask_outside()
		else:
			_show_outside_question(_outside_question_text, _outside_question_reason)
	ask_again.call_deferred()


func _show_outside_question(text: String, reason: String) -> void:
	dismiss_outside_question()
	_outside_question_text = text
	_outside_question_reason = reason
	if m.test_mode:
		outside_question_model = m.model_path
		outside_asked.append(reason)
		return
	var title := "FreeCAD saved this model while Shop Sketch was busy"
	if DisplayServer.has_feature(DisplayServer.FEATURE_NATIVE_DIALOG):
		DisplayServer.dialog_show(title, text, PackedStringArray(["Use FreeCAD's version", "Keep Shop Sketch's"]),
			func(i: int) -> void: outside_choice("mine" if i == 1 else "freecad"))
		return
	var dlg := ConfirmationDialog.new()
	_outside_dialog = dlg
	outside_question_model = m.model_path
	dlg.title = title
	dlg.dialog_text = text
	dlg.ok_button_text = "Use FreeCAD's version"
	dlg.cancel_button_text = "Keep Shop Sketch's"
	dlg.confirmed.connect(func() -> void: outside_choice("freecad"))
	dlg.canceled.connect(func() -> void: outside_choice("mine"))
	add_child(dlg)
	dlg.popup_centered()


func dismiss_outside_question() -> void:
	outside_question_model = ""
	if is_instance_valid(_outside_dialog):
		_outside_dialog.hide()
		_outside_dialog.queue_free()
		_outside_dialog = null


func on_outside_actions_landed() -> void:
	if outside_question_model != m.model_path: return
	dismiss_outside_question()
	_outside_closed_model = m.model_path
	if m.test_mode: outside_closed += 1


func outside_choice(choice: String) -> void:
	if m.doc.outside.is_empty() or m.doc.outside_seq >= 0: return
	dismiss_outside_question()
	if choice == "mine":
		m.measure.flush_units_if_dirty()
		m.doc.send_keep_mine()
	else: m.doc.send_reload()


func on_reloaded(resp: Dictionary) -> void:
	"""FreeCAD's save is on screen, with the wave over the boards it changed."""
	m.measure.on_reloaded(resp)
	m.pres._states.clear(); m.pres._state_lru.clear()     # remembered states are of the file before FreeCAD's save
	var data = JSON.parse_string(FileAccess.get_file_as_string(String(resp.get("outdir", m.out_dir)).path_join("bodies.json")))
	reload_waves = []
	if typeof(data) == TYPE_ARRAY:
		for b in data:
			if not b["id"] in resp.get("changed", []): continue
			var bb: Array = b["world_bbox"]
			var lo := Vector3(bb[0], bb[1], bb[2]); var hi := Vector3(bb[3], bb[4], bb[5])
			m.pres.begin_wave("reload:" + b["id"], (lo + hi) * 0.5, PackedVector3Array([lo, hi]), false, b["id"])
			m.pres.op_waves["reload:" + b["id"]]["state"] = "ok"
			reload_waves.append(b["id"])
	m.pres.apply_confirmed(String(resp.get("outdir", m.out_dir)), m._ops_key(resp.get("ops", [])))
	m._rebuild_rect_drafts()
	m.pres.apply_context()
	var n: int = resp.get("changed", []).size()
	var dropped: int = resp.get("dropped", []).size()
	m.ui_sync.text = "↻ took FreeCAD's save of %s: %d board%s changed%s" % [m.model_path.get_file(), n, "" if n == 1 else "s",
		"" if dropped == 0 else "; %d Shop Sketch action%s it didn't have kept in the journal" % [dropped, "" if dropped == 1 else "s"]]
	if _outside_closed_model == m.model_path:
		m.ui_sync.text += " (Shop Sketch's actions landed while you were deciding, so the question closed)"
	_outside_closed_model = ""
	m.ui_sync.add_theme_color_override("font_color", Color(0.1, 0.5, 0.15))


func on_kept_mine(resp: Dictionary) -> void:
	var aside = resp.get("aside")
	m.ui_sync.text = "kept Shop Sketch's %s" % m.model_path.get_file()
	if aside is String and aside != "":
		m.ui_sync.text += "; FreeCAD's save is beside it as %s" % aside.get_file()
	m.ui_sync.add_theme_color_override("font_color", Color(0.1, 0.5, 0.15))


func reset_outside_question() -> void:
	_outside_try += 1
	dismiss_outside_question()
	_outside_closed_model = ""
	_outside_question_text = ""
	_outside_question_reason = ""
