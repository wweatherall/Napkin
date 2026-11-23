extends Node
## The measurements box (VCB, T75): the typed value at the bottom right, what it's labelled, and where the typed
## text goes. `m.measure`; main.gd forwards the old names (`m.vcb`, `m.typing`, `m.apply_vcb()`, `m._update_vcb()`,
## `m.length_pending`, `m.ui_vcb_box`, ...), so tools and tests don't change.
##
## Move counts and Centre Arc angles reach the tool as typed. Lengths are worked out by units.gd and handed
## to the tool in mm; only what it declines waits for a `length` reply from FreeCAD (T32).
## `typing` (I48): once the box is clicked or typed in, Delete / Backspace edit it until a click in the view or a
## new selection.

const Units := preload("res://units.gd")

var m                               # main.gd: tools, tool, ui_sync, client, doc, model_path, seq, styling helpers
var vcb := ""                       # the text typed so far
var typing := false                 # the measurements box has Delete/Backspace: since a click on it or a typed key, until a click in the view (I48)
var length_id := 0
var length_pending := {}            # a length FreeCAD is working out: {id, tool, model, seq, state}

# Display units (I57, I59, I62): shown immediately, saved in the model's .FCStd Meta via set_units.
var units := Units.DEFAULT_SPEC     # canonical '<format>:<rounding>'
var fallback_spec := Units.DEFAULT_SPEC
var settings_path := ""             # user://settings.cfg in the app; "" in tests unless a test supplies a temp path
var pref_default_units := ""        # from preferences.json units.default (I62, I63); "" if not set
var units_dirty := false            # local choice not yet acknowledged by the worker (resent on reconnect)
var units_user_set := false         # user picked units for this model before its open reply arrived
var units_pending_rev := 0          # revision a set_units reply said it will save as (resent if worker restarts unsaved)
var units_seq := 0                  # numbers set_units requests; stale replies are ignored

var ui_label: Label                 # what the box measures (the tool's vcb_label)
var ui_box: PanelContainer
var ui_value: Label
var _style: StyleBoxFlat
var _style_typing: StyleBoxFlat


func init_units(cfg_path := "", fallback := Units.DEFAULT_SPEC) -> void:
	settings_path = cfg_path
	fallback_spec = fallback
	units = default_units()
	units_dirty = false
	units_user_set = false
	units_pending_rev = 0


func default_units() -> String:
	"""Preference default (I62, I63), else last units used (settings.cfg), else fallback_spec (fractional inches 1/16\" in the app, mm in tests; I57)."""
	if pref_default_units != "":
		var pref := Units.parse_spec(pref_default_units)
		if pref.ok: return pref.spec
	if settings_path != "":
		var cfg := ConfigFile.new()
		if cfg.load(settings_path) == OK:
			var saved := Units.parse_spec(String(cfg.get_value("units", "last", "")))
			if saved.ok: return saved.spec
	return fallback_spec


func _remember_units(spec: String) -> void:
	if settings_path == "": return
	var cfg := ConfigFile.new()
	cfg.load(settings_path)
	cfg.set_value("units", "last", spec)
	cfg.save(settings_path)


func default_unit() -> String:
	"""The unit a bare typed number takes (I59)."""
	return Units.default_unit_of(units)


func format_length(mm: float) -> String:
	return Units.format_length(mm, units)


func _is_opened() -> bool:
	return m != null and m.doc != null and m.doc.opened


func _send_units() -> void:
	if m == null or m.client == null or m.model_path == "": return
	units_seq += 1
	m.client.send({"cmd": "set_units", "model": m.model_path, "units": units, "seq": units_seq})


func _notify_units_changed() -> void:
	update()
	if m == null: return
	if m.has_method("_update_units_menu"): m._update_units_menu()
	if m.has_method("_update_tip") and m.has_method("_cursor_pos") and m.get("ui_tip") != null:
		m._update_tip(m._cursor_pos())


func set_units(spec: String, from_user := true) -> bool:
	"""Switch display units immediately (never waits on FreeCAD) and persist to the model."""
	var parsed := Units.parse_spec(spec)
	if not parsed.ok: return false
	units = parsed.spec
	if from_user:
		units_user_set = true
		_remember_units(units)
	units_dirty = true
	_notify_units_changed()
	if _is_opened(): _send_units()
	return true


func set_format(fmt: String) -> bool:
	return set_units(Units.with_format(units, fmt), true)


func set_precision(prec: String) -> bool:
	return set_units(Units.with_precision(units, prec), true)


func reset_for_model() -> void:
	"""Switching models: forget the old model's in-flight units request and start from last units used."""
	units_seq += 1
	units_user_set = false
	units_dirty = false
	units_pending_rev = 0
	units = default_units()
	_notify_units_changed()


func on_opened(resp: Dictionary, adopt := true) -> void:
	"""Model opened: adopt its saved units unless the user already picked units meanwhile; if none saved (new or
	pre-T66 / unreadable file, I62), keep last units used and save them to the model."""
	if not adopt:
		if units_user_set: _send_units()
		return
	if units_user_set:
		_send_units()
		return
	var saved := Units.parse_spec(String(resp.get("units", "")))
	if saved.ok:
		units = saved.spec
		units_dirty = false
		units_pending_rev = 0
		_notify_units_changed()
	else:
		units_dirty = true
		_send_units()


func on_reloaded(resp: Dictionary) -> void:
	"""Outside save reloaded (A36): take the units from FreeCAD's file (or save ours if the file has none)."""
	units_user_set = false
	var saved := Units.parse_spec(String(resp.get("units", "")))
	if saved.ok:
		units = saved.spec
		units_dirty = false
		units_pending_rev = 0
		_notify_units_changed()
	else:
		units_dirty = true
		_send_units()


func on_set_units_reply(resp: Dictionary) -> void:
	if int(resp.get("seq", -1)) != units_seq: return
	if m != null and resp.has("model") and String(resp["model"]) != m.model_path.simplify_path(): return
	if not resp.get("ok", false): return
	units_dirty = false
	var rev := int(resp.get("rev", 0))
	if m != null and m.doc != null and rev > m.doc.saved_rev:
		units_pending_rev = maxi(units_pending_rev, rev)
		m.doc.pending_rev = maxi(m.doc.pending_rev, rev)
		m.doc.save_changed.emit()


func on_link_up() -> void:
	"""Worker link came back: if a units change hasn't been acknowledged (or saved before a crash), send it again.
	If the model isn't open yet, on_opened() sends it right after the open reply."""
	if not _is_opened(): return
	if not m.doc.outside.is_empty(): return
	if units_dirty or units_pending_rev > m.doc.saved_rev:
		_send_units()


func flush_units_if_dirty() -> void:
	if units_dirty and _is_opened(): _send_units()


func build(row: Container) -> void:
	"""The label and the box, at the end of the status bar's row."""
	ui_label = Label.new(); ui_label.theme_type_variation = "Quiet"
	ui_box = PanelContainer.new()
	ui_box.custom_minimum_size = Vector2(150, 0)
	_style = m._box(m._c(Color(1, 1, 1), Color(0.11, 0.11, 0.12)), 5, m._c(Color(0.75, 0.75, 0.77), Color(0.33, 0.33, 0.35)), 1, Vector2(8, 2))
	_style_typing = _style.duplicate()
	_style_typing.border_color = m.accent; _style_typing.set_border_width_all(2)
	ui_box.add_theme_stylebox_override("panel", _style)
	ui_box.gui_input.connect(func(ev):
		if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
			typing = true; update())
	ui_value = Label.new()
	ui_value.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	ui_box.add_child(ui_value)
	row.add_child(ui_label); row.add_child(ui_box)


func update() -> void:
	if ui_label == null or ui_value == null or ui_box == null or m == null: return
	var t = m.tools[m.tool]
	var val: String = vcb if vcb != "" else t.vcb_value()
	ui_label.text = t.vcb_label()
	ui_value.text = val
	ui_box.add_theme_stylebox_override("panel", _style_typing if vcb != "" or typing else _style)   # typing: accent ring


func type_char(ch: String) -> void:
	vcb += ch; typing = true; update()


func backspace() -> void:
	vcb = vcb.left(-1); update()


func stop_typing() -> void:
	"""A click in the view or a new selection gives Delete back to the model (I48)."""
	if typing: typing = false; update()


func apply() -> void:
	var tool: String = m.tool
	var active = m.tools[tool]
	var txt := vcb.strip_edges()
	vcb = ""
	if txt != "":
		var counts := RegEx.new()
		counts.compile("^(?:[0-9]+x|[x*][0-9]+|/[0-9]+)$")
		var raw: bool = active.has_method("typed_raw") and active.typed_raw()
		if raw or (tool == "move" and counts.search(txt.to_lower()) != null):
			length_pending = {}
			active.typed(txt)
		elif tool in ["rect", "circle", "line", "arc", "push", "move"]:
			var suffix := ""
			if tool == "arc" and active.radius_input() and txt.to_lower().ends_with("r"):
				suffix = "r"
				txt = txt.left(-1).strip_edges()
			var texts := txt.split(",") if tool == "rect" else PackedStringArray([txt])
			var du := default_unit()
			# Worked out here, at once, the way FreeCAD would (units.gd evaluate_length: 150, 3/4", 1' 6 1/2",
			# 5in + 23mm, 1'-6" = 6", I35; bare numbers in the model's units, I59): drafts never wait for FreeCAD.
			# What it declines goes to FreeCAD (T32).
			var here := Units.evaluate_pair(txt, du) if tool == "rect" else Units.evaluate_length(txt, du)
			if here.ok:
				length_pending = {}
				active.typed("%.12f,%.12f" % [here.a_mm, here.b_mm] if tool == "rect" else ("%.12f" % here.mm) + suffix)
			elif texts.size() != (2 if tool == "rect" else 1):
				m.ui_sync.text = "Enter two lengths separated by a comma"
			else:
				length_id += 1
				length_pending = {"id": length_id, "tool": tool, "model": m.model_path, "seq": m.seq,
					"state": active.state.duplicate(true), "suffix": suffix}
				m.client.send({"cmd": "length", "id": length_id, "texts": Array(texts), "default_unit": du})
				m.ui_sync.text = "Evaluating length…"
	update()


func on_length(resp: Dictionary) -> void:
	if length_pending.is_empty() or resp.get("id") != length_pending.id: return
	var pending := length_pending
	length_pending = {}
	var tool: String = m.tool
	if tool != pending.tool or m.model_path != pending.model or m.seq != pending.seq: return
	if m.tools[tool].state != pending.state: return
	if not resp.get("ok", false):
		m.ui_sync.text = "Length: " + str(resp.get("error", "Invalid input"))
		return
	var values := PackedStringArray()
	for value in resp.values: values.append("%.12f" % float(value))
	m.tools[tool].typed(",".join(values) + pending.get("suffix", ""))
	update()
