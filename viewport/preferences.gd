extends RefCounted
## User preferences (I63, T111): reads, validates, watches and seeds a JSON file with default units and
## input-feel tunables. Holds no reference to Main or scene nodes; callers always pass the file path.

const DEFAULTS := {
	"units": {},
	"tuning": {
		"SNAP_PX": 14.0,
		"EDGE_PX": 8.0,
		"INFER_DEG": 8.0,
		"RELEASE_DEG": 12.0,
		"DRAG_PX": 6.0,
		"HOLD_MS": 300,
		"TRACKPAD_PX": 33.0,
		"ZOOM_STEP": 0.88,
		"GRID": 10.0,
	},
}

const RANGES := {
	"SNAP_PX": {"min": 2, "max": 60, "int": false},
	"EDGE_PX": {"min": 2, "max": 60, "int": false},
	"INFER_DEG": {"min": 1, "max": 30, "int": false},
	"RELEASE_DEG": {"min": 1, "max": 45, "int": false},
	"DRAG_PX": {"min": 1, "max": 40, "int": false},
	"HOLD_MS": {"min": 50, "max": 2000, "int": true},
	"TRACKPAD_PX": {"min": 5, "max": 200, "int": false},
	"ZOOM_STEP": {"min": 0.5, "max": 0.99, "int": false},
	"GRID": {"min": 0.1, "max": 1000, "int": false},
}

var _values: Dictionary = DEFAULTS.duplicate(true)
var _has_disk_state := false
var _disk_path := ""
var _disk_exists := false
var _disk_mtime := -1
var _disk_size := -1


func load_from(path: String) -> Dictionary:
	"""Read and validate preferences from path. Keeps last good values (defaults before any good load)
	when the file is missing, unreadable, or a key is invalid. Returns {"values", "problems", "changed"}."""
	# Record stat before reading so a concurrent write finishing mid-read is caught on the next poll.
	var exists := FileAccess.file_exists(path)
	_has_disk_state = true
	_disk_path = path
	_disk_exists = exists
	if exists:
		_disk_mtime = FileAccess.get_modified_time(path)
		_disk_size = FileAccess.get_size(path)
	else:
		_disk_mtime = -1
		_disk_size = -1
		return {"values": _values.duplicate(true), "problems": [], "changed": []}

	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		var err := FileAccess.get_open_error()
		return {
			"values": _values.duplicate(true),
			"problems": [_unreadable_problem(error_string(err), 1)],
			"changed": [],
		}
	var text := f.get_as_text()
	f.close()

	var json := JSON.new()
	var parse_err := json.parse(text)
	if parse_err != OK:
		var msg := json.get_error_message()
		if msg.is_empty():
			msg = error_string(parse_err)
		var line := json.get_error_line() + 1  # Godot's get_error_line() is 0-based
		return {
			"values": _values.duplicate(true),
			"problems": [_unreadable_problem(msg, line)],
			"changed": [],
		}

	if typeof(json.data) != TYPE_DICTIONARY:
		return {
			"values": _values.duplicate(true),
			"problems": [_unreadable_problem("expected a JSON object", 1)],
			"changed": [],
		}

	var data: Dictionary = json.data
	var problems: Array[String] = []
	for k in data:
		if k != "units" and k != "tuning":
			problems.append("preferences.json: unknown section %s" % str(k))

	var next_units: Dictionary
	if data.has("units"):
		if typeof(data["units"]) == TYPE_DICTIONARY:
			next_units = data["units"].duplicate(true)
		else:
			problems.append("preferences.json: units must be an object (got %s)" % _fmt_value(data["units"]))
			next_units = _values["units"].duplicate(true)
	else:
		next_units = DEFAULTS["units"].duplicate(true)

	var prev_tuning: Dictionary = _values["tuning"]
	var next_tuning: Dictionary
	if data.has("tuning"):
		if typeof(data["tuning"]) != TYPE_DICTIONARY:
			problems.append("preferences.json: tuning must be an object (got %s)" % _fmt_value(data["tuning"]))
			next_tuning = prev_tuning.duplicate(true)
		else:
			var raw_tuning: Dictionary = data["tuning"]
			for k in raw_tuning:
				if not DEFAULTS["tuning"].has(k):
					problems.append("preferences.json: unknown setting %s" % str(k))
			next_tuning = {}
			var release_ok := true
			for k in DEFAULTS["tuning"]:
				if not raw_tuning.has(k):
					next_tuning[k] = DEFAULTS["tuning"][k]
				else:
					var checked := _check_tuning(k, raw_tuning[k])
					if checked["ok"]:
						next_tuning[k] = checked["value"]
					else:
						problems.append(checked["problem"])
						next_tuning[k] = prev_tuning[k]
						if k == "RELEASE_DEG":
							release_ok = false
			if float(next_tuning["RELEASE_DEG"]) < float(next_tuning["INFER_DEG"]):
				if release_ok:	# a RELEASE_DEG already refused has its own problem
					problems.append("preferences.json: RELEASE_DEG must be at least INFER_DEG (%s)" % _fmt_num(float(next_tuning["INFER_DEG"])))
				next_tuning["RELEASE_DEG"] = next_tuning["INFER_DEG"]	# never below INFER_DEG: an axis would let go before it sticks
	else:
		next_tuning = DEFAULTS["tuning"].duplicate(true)

	var changed: Array[String] = []
	for k in DEFAULTS["tuning"]:
		if _tuning_differs(k, prev_tuning[k], next_tuning[k]):
			changed.append(k)

	_values = {"units": next_units, "tuning": next_tuning}
	return {
		"values": _values.duplicate(true),
		"problems": problems,
		"changed": changed,
	}


func changed_on_disk(path: String) -> bool:
	"""Cheap poll (stat only, no read): true when path's existence, modified time or size differs from
	the last load_from()."""
	var exists := FileAccess.file_exists(path)
	if not _has_disk_state:
		return exists
	if path != _disk_path:
		return _disk_exists or exists
	if exists != _disk_exists:
		return true
	if not exists:
		return false
	return FileAccess.get_modified_time(path) != _disk_mtime or FileAccess.get_size(path) != _disk_size


func write_defaults(path: String) -> Error:
	"""When path is missing, write the current values as indented JSON with tuning keys in DEFAULTS
	order and units as {} if empty. Never overwrites an existing file (returns ERR_ALREADY_EXISTS)."""
	if FileAccess.file_exists(path):
		return ERR_ALREADY_EXISTS
	var global_dir := ProjectSettings.globalize_path(path).get_base_dir()
	if not global_dir.is_empty():
		DirAccess.make_dir_recursive_absolute(global_dir)
	var ordered_tuning := {}
	for k in DEFAULTS["tuning"]:
		ordered_tuning[k] = _values["tuning"][k]
	var units_val: Dictionary = _values["units"].duplicate(true) if typeof(_values.get("units")) == TYPE_DICTIONARY else {}
	var payload := {
		"units": units_val,
		"tuning": ordered_tuning,
	}
	var text := JSON.stringify(payload, "  ", false)
	if units_val.is_empty():
		text = text.replace("\"units\": {\n\n  }", "\"units\": {}")
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		var err := FileAccess.get_open_error()
		return err if err != OK else ERR_CANT_CREATE
	f.store_string(text + "\n")
	f.close()
	return OK


static func _unreadable_problem(msg: String, line: int) -> String:
	return "preferences.json isn't readable (%s, line %d); keeping the last good settings" % [msg, line]


static func _check_tuning(key: String, raw: Variant) -> Dictionary:
	var spec: Dictionary = RANGES[key]
	var lo: float = float(spec["min"])
	var hi: float = float(spec["max"])
	var want_int: bool = spec["int"]
	var t := typeof(raw)
	if t != TYPE_INT and t != TYPE_FLOAT:
		return {"ok": false, "problem": _range_problem(key, spec, raw, false)}
	var v := float(raw)
	if is_nan(v) or is_inf(v) or v < lo or v > hi:
		return {"ok": false, "problem": _range_problem(key, spec, raw, false)}
	if want_int:
		if v != floor(v):
			return {"ok": false, "problem": _range_problem(key, spec, raw, true)}
		return {"ok": true, "value": int(round(v))}
	return {"ok": true, "value": v}


static func _range_problem(key: String, spec: Dictionary, raw: Variant, whole_only: bool) -> String:
	var kind := "whole number" if whole_only else "number"
	return "preferences.json: %s must be a %s from %s to %s (got %s)" % [
		key, kind, str(spec["min"]), str(spec["max"]), _fmt_value(raw)
	]


static func _tuning_differs(key: String, a: Variant, b: Variant) -> bool:
	if RANGES[key]["int"]:
		return int(a) != int(b)
	return absf(float(a) - float(b)) > 1e-9


static func _fmt_num(v: float) -> String:
	if is_finite(v) and v == floor(v) and absf(v) < 1e12:
		return str(int(v))
	return str(v)


static func _fmt_value(raw: Variant) -> String:
	match typeof(raw):
		TYPE_NIL:
			return "null"
		TYPE_BOOL:
			return "true" if raw else "false"
		TYPE_INT:
			return str(raw)
		TYPE_FLOAT:
			return _fmt_num(raw)
		TYPE_STRING:
			return JSON.stringify(raw)
		_:
			return JSON.stringify(raw)
