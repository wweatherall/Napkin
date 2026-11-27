extends RefCounted
## Live preferences (I63, T111): loads, watches and applies user://preferences.json to live tunables and default units.
## `m.live_prefs`; main.gd forwards `PREFERENCES_PATH`, `PREFERENCES_KEY`, `preferences_path`, `prefs`, `_prefs_timer`,
## `_init_preferences`, `_start_preferences`, `_apply_preferences`, and `_open_preferences` so menus and tests don't change.
## Entry points: _init_preferences, _start_preferences, _apply_preferences, _open_preferences.

const Inference := preload("res://inference.gd")
const Preferences := preload("res://preferences.gd")
const Tool := preload("res://tools/tool.gd")

const PREFERENCES_PATH := "user://preferences.json"
const PREFERENCES_KEY := KEY_MASK_META | KEY_COMMA

var m                               # main.gd: test_mode, doc, measure, camera_rig, add_child, _say_status
var preferences_path := PREFERENCES_PATH
var prefs := Preferences.new()
var _prefs_timer: Timer
var _startup_prefs_problem := ""


func _init(main = null) -> void:
	m = main


func _init_preferences() -> void:
	if m.test_mode: return
	_start_preferences()


func _start_preferences() -> void:
	"""Load preferences_path and start the 0.5 s poll timer (skipped at startup in test_mode, I63)."""
	_load_preferences(true)
	if not m.doc.opened and not m.measure.units_user_set:
		m.measure.units = m.measure.default_units()
		m.measure.update()
	if _prefs_timer == null:
		_prefs_timer = Timer.new()
		_prefs_timer.name = "PreferencesTimer"
		_prefs_timer.wait_time = 0.5
		_prefs_timer.one_shot = false
		_prefs_timer.timeout.connect(_poll_preferences)
		m.add_child(_prefs_timer)
	_prefs_timer.start()


func _poll_preferences() -> void:
	if prefs.changed_on_disk(preferences_path):
		_load_preferences(false)


func _load_preferences(at_start: bool) -> void:
	var res := prefs.load_from(preferences_path)
	_apply_preferences(res["values"])
	var msg := _preferences_status(res, at_start)
	if msg != "":
		m._say_status(msg)
		if at_start and not m.doc.opened and not res["problems"].is_empty():
			_startup_prefs_problem = msg
	elif res["problems"].is_empty():
		_startup_prefs_problem = ""


func _apply_preferences(values: Dictionary) -> void:
	"""Apply preferences values ({units, tuning}, or a tuning dictionary) to live tunables and default units."""
	var t: Dictionary = values["tuning"] if typeof(values.get("tuning")) == TYPE_DICTIONARY else values
	if t.has("GRID"): Inference.grid = float(t["GRID"])
	if t.has("SNAP_PX"): Inference.snap_px = float(t["SNAP_PX"])
	if t.has("EDGE_PX"): Inference.edge_px = float(t["EDGE_PX"])
	if t.has("INFER_DEG"): Inference.infer_deg = float(t["INFER_DEG"])
	if t.has("RELEASE_DEG"): Inference.release_deg = float(t["RELEASE_DEG"])
	if t.has("DRAG_PX"): Tool.drag_px = float(t["DRAG_PX"])
	if t.has("HOLD_MS"): Tool.hold_ms = int(t["HOLD_MS"])
	if t.has("TRACKPAD_PX"): m.camera_rig.trackpad_px = float(t["TRACKPAD_PX"])
	if t.has("ZOOM_STEP"): m.camera_rig.zoom_step = float(t["ZOOM_STEP"])
	if typeof(values.get("units")) == TYPE_DICTIONARY:
		var def_u = values["units"].get("default")
		m.measure.pref_default_units = String(def_u) if typeof(def_u) == TYPE_STRING else ""


func _preferences_status(res: Dictionary, at_start: bool) -> String:
	var problems: Array = res.get("problems", [])
	if not problems.is_empty():
		var first: String = problems[0]
		if problems.size() > 1:
			return "%s (and %d more)" % [first, problems.size() - 1]
		return first
	if at_start:
		return ""
	var changed: Array = res.get("changed", [])
	if changed.is_empty():
		return ""
	var parts: Array[String] = []
	for k in changed:
		if k == "units.default":
			parts.append("default units %s" % (m.measure.pref_default_units if m.measure.pref_default_units != "" else "none"))
		else:
			parts.append("%s %s" % [k, Preferences.format_num(_live_tuning(k))])
	return "Preferences: " + ", ".join(parts)


func _live_tuning(key: String) -> float:
	match key:
		"GRID": return Inference.grid
		"SNAP_PX": return Inference.snap_px
		"EDGE_PX": return Inference.edge_px
		"INFER_DEG": return Inference.infer_deg
		"RELEASE_DEG": return Inference.release_deg
		"DRAG_PX": return Tool.drag_px
		"HOLD_MS": return float(Tool.hold_ms)
		"TRACKPAD_PX": return m.camera_rig.trackpad_px
		"ZOOM_STEP": return m.camera_rig.zoom_step
	return 0.0


func _open_preferences() -> void:
	var err := prefs.write_defaults(preferences_path)
	if err != OK and err != ERR_ALREADY_EXISTS:
		m._say_status("Couldn't write preferences.json: %s" % error_string(err))
		return
	OS.shell_open(ProjectSettings.globalize_path(preferences_path))
