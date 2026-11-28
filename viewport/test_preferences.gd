extends SceneTree
## Headless tests for viewport/preferences.gd (I63, T111 step 1): defaults, validation, ranges,
## partial recovery on bad edits, deletion while running, deep copy, changed_on_disk and write_defaults.
## Run: Godot --headless --path viewport --script res://test_preferences.gd
const Preferences = preload("res://preferences.gd")
const MeasureBox = preload("res://measure_box.gd")
const Units = preload("res://units.gd")
const Menus = preload("res://menus.gd")

var passed := 0
var failed := 0
var tmp_dir := ""
var own_tmp := false


func check(label: String, condition: bool) -> void:
	if condition:
		passed += 1
		print("PASS ", label)
	else:
		failed += 1
		print("FAIL ", label)


func write_text(path: String, text: String) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	assert(f != null, "failed to write test file: " + path)
	f.store_string(text)
	f.close()


func read_text(path: String) -> String:
	return FileAccess.get_file_as_string(path)


func cleanup_dir(dir_path: String) -> void:
	var d := DirAccess.open(dir_path)
	if d == null:
		return
	d.list_dir_begin()
	var name := d.get_next()
	while not name.is_empty():
		if name != "." and name != "..":
			var child := dir_path.path_join(name)
			if d.current_is_dir():
				cleanup_dir(child)
			else:
				DirAccess.remove_absolute(child)
		name = d.get_next()
	d.list_dir_end()
	DirAccess.remove_absolute(dir_path)


func _init() -> void:
	var env_dir := OS.get_environment("TESTDIR")
	if not env_dir.is_empty():
		tmp_dir = env_dir
	else:
		tmp_dir = ProjectSettings.globalize_path("res://").path_join("../scratch/test_preferences_%d" % OS.get_process_id())
		own_tmp = true
	DirAccess.make_dir_recursive_absolute(tmp_dir)

	_test_missing_and_empty()
	_test_all_keys_good()
	_test_half_written_and_bad_json()
	_test_deleted_while_running()
	_test_wrong_types()
	_test_hold_ms_and_infer_release()
	_test_unknown_keys_and_sections()
	_test_range_boundaries()
	_test_changed_across_loads()
	_test_deep_copy()
	_test_changed_on_disk()
	_test_write_defaults()
	_test_units_validation()
	_test_measure_box_default_units()
	_test_dialog_start()

	if own_tmp:
		cleanup_dir(tmp_dir)

	print("PREFERENCES TESTS: %d passed, %d failed" % [passed, failed])
	quit(1 if failed else 0)


func _test_dialog_start() -> void:
	"""New and Open start in 04_Napkin_Drawings/ beside models/ (I78), else in the open model's folder."""
	var root := tmp_dir.path_join("dialog_start")
	DirAccess.make_dir_recursive_absolute(root.path_join("models"))
	check("dialog start: no drawings folder, the model's folder", Menus.dialog_start(root.path_join("models/model.FCStd")) == root.path_join("models"))
	DirAccess.make_dir_recursive_absolute(root.path_join(Menus.DRAWINGS))
	check("dialog start: the app's working file, 04_Napkin_Drawings", Menus.dialog_start(root.path_join("models/model.FCStd")) == root.path_join(Menus.DRAWINGS))
	check("dialog start: one of William's models, its own folder", Menus.dialog_start(root.path_join(Menus.DRAWINGS + "/stool/stool.FCStd")) == root.path_join(Menus.DRAWINGS + "/stool"))


func _test_missing_and_empty() -> void:
	var prefs := Preferences.new()
	var p := tmp_dir.path_join("missing.json")
	var r := prefs.load_from(p)
	check("missing file returns defaults", r["values"] == Preferences.DEFAULTS)
	check("missing file has no problems", r["problems"].is_empty())
	check("missing file has no changes", r["changed"].is_empty())

	var ep := tmp_dir.path_join("empty_obj.json")
	write_text(ep, "{}\n")
	var re := prefs.load_from(ep)
	check("empty object returns defaults", re["values"] == Preferences.DEFAULTS)
	check("empty object has no problems", re["problems"].is_empty())
	check("empty object has no changes", re["changed"].is_empty())


func _test_all_keys_good() -> void:
	var prefs := Preferences.new()
	var p := tmp_dir.path_join("all_good.json")
	write_text(p, JSON.stringify({
		"units": {"default": "in-dec:0.01"},
		"tuning": {
			"GRID": 12.5,
			"ZOOM_STEP": 0.92,
			"TRACKPAD_PX": 40.0,
			"HOLD_MS": 450,
			"DRAG_PX": 9.0,
			"RELEASE_DEG": 18.0,
			"INFER_DEG": 10.0,
			"EDGE_PX": 11.0,
			"SNAP_PX": 20.0,
		},
	}, "  ", false))
	var r := prefs.load_from(p)
	check("all good: no problems", r["problems"].is_empty())
	check("all good: units default preserved", r["values"]["units"] == {"default": "in-dec:0.01"})
	var t: Dictionary = r["values"]["tuning"]
	check("all good: SNAP_PX", is_equal_approx(t["SNAP_PX"], 20.0))
	check("all good: EDGE_PX", is_equal_approx(t["EDGE_PX"], 11.0))
	check("all good: INFER_DEG", is_equal_approx(t["INFER_DEG"], 10.0))
	check("all good: RELEASE_DEG", is_equal_approx(t["RELEASE_DEG"], 18.0))
	check("all good: DRAG_PX", is_equal_approx(t["DRAG_PX"], 9.0))
	check("all good: HOLD_MS is int 450", typeof(t["HOLD_MS"]) == TYPE_INT and t["HOLD_MS"] == 450)
	check("all good: TRACKPAD_PX", is_equal_approx(t["TRACKPAD_PX"], 40.0))
	check("all good: ZOOM_STEP", is_equal_approx(t["ZOOM_STEP"], 0.92))
	check("all good: GRID", is_equal_approx(t["GRID"], 12.5))
	var want_order := ["units.default", "SNAP_PX", "EDGE_PX", "INFER_DEG", "RELEASE_DEG", "DRAG_PX", "HOLD_MS", "TRACKPAD_PX", "ZOOM_STEP", "GRID"]
	check("all good: changed in DEFAULTS order", r["changed"] == want_order)


func _test_half_written_and_bad_json() -> void:
	var prefs := Preferences.new()
	var p := tmp_dir.path_join("half_written.json")
	write_text(p, "{\"tuning\": {\"SNAP_PX\": 22}}\n")
	var good := prefs.load_from(p)
	check("good before half-write: SNAP_PX 22", is_equal_approx(good["values"]["tuning"]["SNAP_PX"], 22.0))

	# Half-written JSON
	write_text(p, "{\"tuning\": {\"SNAP_PX\": 1")
	var bad := prefs.load_from(p)
	check("half-written keeps last good values", is_equal_approx(bad["values"]["tuning"]["SNAP_PX"], 22.0))
	check("half-written has no changes", bad["changed"].is_empty())
	check("half-written has one problem", bad["problems"].size() == 1)
	var msg: String = bad["problems"][0] if bad["problems"].size() > 0 else ""
	check("half-written message format and line",
		msg.begins_with("preferences.json isn't readable (")
		and ", line 1)" in msg
		and msg.ends_with("); keeping the last good settings"))

	# Multiline broken JSON names the line
	write_text(p, "{\n  \"tuning\": {\n    \"SNAP_PX\": }\n}\n")
	var multi := prefs.load_from(p)
	check("multiline bad JSON keeps last good values", is_equal_approx(multi["values"]["tuning"]["SNAP_PX"], 22.0))
	check("multiline bad JSON has one problem naming line 3",
		multi["problems"].size() == 1 and ", line 3)" in multi["problems"][0])

	# Not JSON at all
	write_text(p, "not json at all")
	var not_json := prefs.load_from(p)
	check("not JSON keeps last good values", is_equal_approx(not_json["values"]["tuning"]["SNAP_PX"], 22.0))
	check("not JSON has one problem", not_json["problems"].size() == 1
		and not_json["problems"][0].begins_with("preferences.json isn't readable ("))

	# Empty file (0 bytes)
	write_text(p, "")
	var empty_file := prefs.load_from(p)
	check("empty file keeps last good values", is_equal_approx(empty_file["values"]["tuning"]["SNAP_PX"], 22.0))
	check("empty file has one problem", empty_file["problems"].size() == 1)

	# Top-level non-object (array, string, number)
	for raw in ["[1, 2, 3]", "\"hello\"", "42", "null"]:
		write_text(p, raw)
		var r := prefs.load_from(p)
		check("non-object %s keeps last good" % raw, is_equal_approx(r["values"]["tuning"]["SNAP_PX"], 22.0))
		check("non-object %s has one problem" % raw, r["problems"].size() == 1
			and r["problems"][0].begins_with("preferences.json isn't readable (")
			and r["problems"][0].ends_with("); keeping the last good settings"))

	# Bad JSON before any good load keeps defaults
	var fresh := Preferences.new()
	write_text(p, "{\"tuning\": {\"SNAP_PX\": 1")
	var fresh_bad := fresh.load_from(p)
	check("bad JSON on first load keeps defaults", fresh_bad["values"] == Preferences.DEFAULTS)
	check("bad JSON on first load has one problem", fresh_bad["problems"].size() == 1)


func _test_deleted_while_running() -> void:
	var prefs := Preferences.new()
	var p := tmp_dir.path_join("deleted.json")
	write_text(p, "{\"units\": {\"default\": \"in-frac:1/16\"}, \"tuning\": {\"SNAP_PX\": 25}}\n")
	var r1 := prefs.load_from(p)
	check("before delete: SNAP_PX 25", is_equal_approx(r1["values"]["tuning"]["SNAP_PX"], 25.0))
	check("before delete: changed_on_disk false", not prefs.changed_on_disk(p))

	DirAccess.remove_absolute(p)
	check("after delete: changed_on_disk true", prefs.changed_on_disk(p))
	var r2 := prefs.load_from(p)
	check("after delete: keeps last good SNAP_PX", is_equal_approx(r2["values"]["tuning"]["SNAP_PX"], 25.0))
	check("after delete: keeps last good units", r2["values"]["units"] == {"default": "in-frac:1/16"})
	check("after delete: no problem", r2["problems"].is_empty())
	check("after delete: changed is empty", r2["changed"].is_empty())
	check("after loading missing: changed_on_disk false", not prefs.changed_on_disk(p))

	write_text(p, "{\"units\": {\"default\": \"in-frac:1/16\"}, \"tuning\": {\"SNAP_PX\": 30}}\n")
	check("reappeared: changed_on_disk true", prefs.changed_on_disk(p))
	var r3 := prefs.load_from(p)
	check("reappeared: applies new SNAP_PX 30", is_equal_approx(r3["values"]["tuning"]["SNAP_PX"], 30.0))
	check("reappeared: changed has SNAP_PX", r3["changed"] == ["SNAP_PX"])


func _test_wrong_types() -> void:
	var prefs := Preferences.new()
	var p := tmp_dir.path_join("wrong_types.json")
	write_text(p, "{\"tuning\": {\"SNAP_PX\": 18, \"EDGE_PX\": 10}}\n")
	prefs.load_from(p)

	for bad_val in ["\"14\"", "null", "true", "[14]", "{\"a\": 1}"]:
		write_text(p, "{\"tuning\": {\"SNAP_PX\": %s, \"EDGE_PX\": 12}}\n" % bad_val)
		var r := prefs.load_from(p)
		check("wrong type %s keeps SNAP_PX 18" % bad_val, is_equal_approx(r["values"]["tuning"]["SNAP_PX"], 18.0))
		check("wrong type %s still applies EDGE_PX 12" % bad_val, is_equal_approx(r["values"]["tuning"]["EDGE_PX"], 12.0))
		check("wrong type %s reports one problem" % bad_val,
			r["problems"].size() == 1
			and r["problems"][0].begins_with("preferences.json: SNAP_PX must be a number from 2 to 60 (got "))

	# Non-object units and tuning
	write_text(p, "{\"units\": \"imperial\", \"tuning\": {\"SNAP_PX\": 20}}\n")
	var ru := prefs.load_from(p)
	check("non-object units reports problem", ru["problems"].size() == 1 and "units" in ru["problems"][0])
	check("non-object units still applies tuning", is_equal_approx(ru["values"]["tuning"]["SNAP_PX"], 20.0))

	write_text(p, "{\"units\": {\"default\": \"mm:1\"}, \"tuning\": [1, 2]}\n")
	var rt := prefs.load_from(p)
	check("non-object tuning reports problem", rt["problems"].size() == 1 and "tuning" in rt["problems"][0])
	check("non-object tuning keeps last good tuning", is_equal_approx(rt["values"]["tuning"]["SNAP_PX"], 20.0))
	check("non-object tuning still applies units", rt["values"]["units"] == {"default": "mm:1"})


func _test_hold_ms_and_infer_release() -> void:
	var prefs := Preferences.new()
	var p := tmp_dir.path_join("hold_infer.json")
	write_text(p, "{\"tuning\": {\"HOLD_MS\": 400}}\n")
	var r1 := prefs.load_from(p)
	check("HOLD_MS 400 applies", r1["values"]["tuning"]["HOLD_MS"] == 400 and r1["problems"].is_empty())

	write_text(p, "{\"tuning\": {\"HOLD_MS\": 300.5}}\n")
	var r2 := prefs.load_from(p)
	check("HOLD_MS 300.5 rejected", r2["problems"].size() == 1 and "HOLD_MS" in r2["problems"][0])
	check("HOLD_MS 300.5 keeps last good 400", r2["values"]["tuning"]["HOLD_MS"] == 400)

	# INFER_DEG raised over RELEASE_DEG in one edit (both explicit and omitted RELEASE_DEG)
	var p2 := tmp_dir.path_join("infer_release.json")
	var prefs2 := Preferences.new()
	write_text(p2, "{\"tuning\": {\"INFER_DEG\": 20, \"RELEASE_DEG\": 12}}\n")
	var r3 := prefs2.load_from(p2)
	check("INFER_DEG > RELEASE_DEG: INFER_DEG applies (20)", is_equal_approx(r3["values"]["tuning"]["INFER_DEG"], 20.0))
	check("INFER_DEG > RELEASE_DEG: RELEASE_DEG rises to INFER_DEG (20), never below it", is_equal_approx(r3["values"]["tuning"]["RELEASE_DEG"], 20.0))
	check("INFER_DEG > RELEASE_DEG: exact problem",
		r3["problems"] == ["preferences.json: RELEASE_DEG must be at least INFER_DEG (20)"])
	check("INFER_DEG > RELEASE_DEG: changed INFER_DEG and RELEASE_DEG", r3["changed"] == ["INFER_DEG", "RELEASE_DEG"])

	# Omitting RELEASE_DEG while raising INFER_DEG over default 12
	var prefs3 := Preferences.new()
	write_text(p2, "{\"tuning\": {\"INFER_DEG\": 15}}\n")
	var r4 := prefs3.load_from(p2)
	check("INFER_DEG 15 with default RELEASE_DEG: INFER_DEG applies", is_equal_approx(r4["values"]["tuning"]["INFER_DEG"], 15.0))
	check("INFER_DEG 15 with default RELEASE_DEG: RELEASE_DEG problem",
		r4["problems"] == ["preferences.json: RELEASE_DEG must be at least INFER_DEG (15)"])

	# Equal INFER_DEG and RELEASE_DEG passes
	write_text(p2, "{\"tuning\": {\"INFER_DEG\": 20, \"RELEASE_DEG\": 20}}\n")
	var r5 := prefs2.load_from(p2)
	check("INFER_DEG == RELEASE_DEG passes", r5["problems"].is_empty()
		and is_equal_approx(r5["values"]["tuning"]["INFER_DEG"], 20.0)
		and is_equal_approx(r5["values"]["tuning"]["RELEASE_DEG"], 20.0))
	check("RELEASE_DEG already at INFER_DEG: nothing changed", r5["changed"].is_empty())


func _test_unknown_keys_and_sections() -> void:
	var prefs := Preferences.new()
	var p := tmp_dir.path_join("unknown.json")
	write_text(p, JSON.stringify({
		"camera": {"fov": 45},
		"tuning": {"SNAP_PX": 18, "MYSTERY": 99},
	}, "  ", false))
	var r := prefs.load_from(p)
	check("unknown section problem", "preferences.json: unknown section camera" in r["problems"])
	check("unknown setting problem", "preferences.json: unknown setting MYSTERY" in r["problems"])
	check("unknown count is 2", r["problems"].size() == 2)
	check("valid sibling SNAP_PX still applies", is_equal_approx(r["values"]["tuning"]["SNAP_PX"], 18.0))
	check("unknown setting not added to values", not r["values"]["tuning"].has("MYSTERY"))
	check("unknown section not added to values", not r["values"].has("camera"))


func _test_range_boundaries() -> void:
	var cases := [
		["SNAP_PX", 2, 60, 1.99, 60.01, {}],
		["EDGE_PX", 2, 60, 1.99, 60.01, {}],
		["INFER_DEG", 1, 30, 0.99, 30.01, {"RELEASE_DEG": 30}],
		["RELEASE_DEG", 1, 45, 0.99, 45.01, {"INFER_DEG": 1}],
		["DRAG_PX", 1, 40, 0.99, 40.01, {}],
		["HOLD_MS", 50, 2000, 49, 2001, {}],
		["TRACKPAD_PX", 5, 200, 4.99, 200.01, {}],
		["ZOOM_STEP", 0.5, 0.99, 0.49, 0.991, {}],
		["GRID", 0.1, 1000, 0.09, 1000.01, {}],
	]
	var p := tmp_dir.path_join("ranges.json")
	for c in cases:
		var k: String = c[0]
		var lo = c[1]
		var hi = c[2]
		var below = c[3]
		var above = c[4]
		var extra: Dictionary = c[5]

		var prefs_lo := Preferences.new()
		var d_lo := extra.duplicate()
		d_lo[k] = lo
		write_text(p, JSON.stringify({"tuning": d_lo}))
		var r_lo := prefs_lo.load_from(p)
		check("%s min (%s) passes" % [k, str(lo)], r_lo["problems"].is_empty() and is_equal_approx(float(r_lo["values"]["tuning"][k]), float(lo)))

		var prefs_hi := Preferences.new()
		var d_hi := extra.duplicate()
		d_hi[k] = hi
		write_text(p, JSON.stringify({"tuning": d_hi}))
		var r_hi := prefs_hi.load_from(p)
		check("%s max (%s) passes" % [k, str(hi)], r_hi["problems"].is_empty() and is_equal_approx(float(r_hi["values"]["tuning"][k]), float(hi)))

		var prefs_below := Preferences.new()
		var d_below := extra.duplicate()
		d_below[k] = below
		write_text(p, JSON.stringify({"tuning": d_below}))
		var r_below := prefs_below.load_from(p)
		check("%s below min (%s) fails" % [k, str(below)],
			r_below["problems"].size() == 1
			and r_below["problems"][0].begins_with("preferences.json: %s must be a number from " % k)
			and is_equal_approx(float(r_below["values"]["tuning"][k]), float(Preferences.DEFAULTS["tuning"][k])))

		var prefs_above := Preferences.new()
		var d_above := extra.duplicate()
		d_above[k] = above
		write_text(p, JSON.stringify({"tuning": d_above}))
		var r_above := prefs_above.load_from(p)
		check("%s above max (%s) fails" % [k, str(above)],
			r_above["problems"].size() == 1
			and r_above["problems"][0].begins_with("preferences.json: %s must be a number from " % k)
			and is_equal_approx(float(r_above["values"]["tuning"][k]), float(Preferences.DEFAULTS["tuning"][k])))


func _test_changed_across_loads() -> void:
	var prefs := Preferences.new()
	var p := tmp_dir.path_join("changed.json")
	write_text(p, "{\"tuning\": {\"GRID\": 5, \"SNAP_PX\": 18}}\n")
	var r1 := prefs.load_from(p)
	check("load 1 changed in DEFAULTS order", r1["changed"] == ["SNAP_PX", "GRID"])

	write_text(p, "{\"tuning\": {\"SNAP_PX\": 18, \"ZOOM_STEP\": 0.9, \"GRID\": 5}}\n")
	var r2 := prefs.load_from(p)
	check("load 2 changed only ZOOM_STEP", r2["changed"] == ["ZOOM_STEP"])

	var r3 := prefs.load_from(p)
	check("load 3 unchanged is empty", r3["changed"].is_empty())

	write_text(p, "{\"tuning\": {\"SNAP_PX\": 18, \"ZOOM_STEP\": 0.9}}\n")
	var r4 := prefs.load_from(p)
	check("load 4 removing GRID reverts to default and lists GRID",
		is_equal_approx(r4["values"]["tuning"]["GRID"], 10.0) and r4["changed"] == ["GRID"])


func _test_deep_copy() -> void:
	var prefs := Preferences.new()
	var p := tmp_dir.path_join("deepcopy.json")
	write_text(p, "{\"units\": {\"default\": \"mm:1\"}, \"tuning\": {\"SNAP_PX\": 18}}\n")
	var r1 := prefs.load_from(p)
	r1["values"]["tuning"]["SNAP_PX"] = 99.0
	r1["values"]["units"]["default"] = "hacked"
	var r2 := prefs.load_from(p)
	check("deep copy: tuning unaffected by caller mutation", is_equal_approx(r2["values"]["tuning"]["SNAP_PX"], 18.0))
	check("deep copy: units unaffected by caller mutation", r2["values"]["units"] == {"default": "mm:1"})
	check("deep copy: changed unaffected by caller mutation", r2["changed"].is_empty())


func _test_changed_on_disk() -> void:
	var prefs := Preferences.new()
	var p := tmp_dir.path_join("watch.json")
	prefs.load_from(p)
	check("watch missing: false right after load", not prefs.changed_on_disk(p))

	write_text(p, "{\"tuning\": {\"SNAP_PX\": 18}}\n")
	check("watch appeared: true", prefs.changed_on_disk(p))
	prefs.load_from(p)
	check("watch existing: false right after load", not prefs.changed_on_disk(p))

	# Rewrite with a different size (same second)
	write_text(p, "{\"tuning\": {\"SNAP_PX\": 18, \"GRID\": 20}}\n")
	check("watch different size: true", prefs.changed_on_disk(p))
	prefs.load_from(p)
	check("watch after reload: false", not prefs.changed_on_disk(p))

	# Rewrite with identical size, different mtime
	write_text(p, "{\"tuning\": {\"SNAP_PX\": 19, \"GRID\": 20}}\n")
	OS.execute("/usr/bin/touch", ["-t", "202001010000", p])
	check("watch same size different mtime: true", prefs.changed_on_disk(p))
	prefs.load_from(p)
	check("watch after mtime reload: false", not prefs.changed_on_disk(p))


func _test_write_defaults() -> void:
	var prefs := Preferences.new()
	var p := tmp_dir.path_join("nested/sub/written.json")
	var err := prefs.write_defaults(p)
	check("write_defaults on missing (and missing folder) returns OK", err == OK)
	var text := read_text(p)
	check("write_defaults writes units default as null", "\"units\":" in text and "\"default\": null" in text)
	var keys := ["SNAP_PX", "EDGE_PX", "INFER_DEG", "RELEASE_DEG", "DRAG_PX", "HOLD_MS", "TRACKPAD_PX", "ZOOM_STEP", "GRID"]
	var last_pos := -1
	var in_order := true
	for k in keys:
		var pos := text.find("\"%s\"" % k)
		if pos <= last_pos:
			in_order = false
		last_pos = pos
	check("write_defaults tuning keys in DEFAULTS order", in_order)

	var reader := Preferences.new()
	var r := reader.load_from(p)
	check("write_defaults reads back as DEFAULTS", r["values"] == Preferences.DEFAULTS)
	check("write_defaults reads back with no problems", r["problems"].is_empty())
	check("write_defaults reads back with no changes", r["changed"].is_empty())

	# Refuses to overwrite existing file
	var sentinel := "{\"custom\": true, \"tuning\": {\"SNAP_PX\": 24}}\n"
	var p2 := tmp_dir.path_join("existing.json")
	write_text(p2, sentinel)
	var err2 := prefs.write_defaults(p2)
	check("write_defaults over existing returns ERR_ALREADY_EXISTS", err2 == ERR_ALREADY_EXISTS)
	check("write_defaults over existing leaves bytes unchanged", read_text(p2) == sentinel)

	# Writes current values (after loading non-defaults and deleting file)
	var p3 := tmp_dir.path_join("current_values.json")
	write_text(p3, "{\"units\": {\"default\": \"in-dec:0.01\"}, \"tuning\": {\"SNAP_PX\": 21}}\n")
	prefs.load_from(p3)
	DirAccess.remove_absolute(p3)
	var err3 := prefs.write_defaults(p3)
	check("write_defaults writes current values after delete", err3 == OK)
	var r3 := Preferences.new().load_from(p3)
	check("write_defaults current values read back SNAP_PX 21", is_equal_approx(r3["values"]["tuning"]["SNAP_PX"], 21.0))
	check("write_defaults current values read back units default", r3["values"]["units"] == {"default": "in-dec:0.01"})


func _test_units_validation() -> void:
	var prefs := Preferences.new()
	var p := tmp_dir.path_join("units_check.json")

	# Valid specs accepted
	for spec in ["in-frac:1/16", "mm:1", "ft-in:1/32", "in-dec:0.01", "cm:0.1", "m:0.001"]:
		write_text(p, JSON.stringify({"units": {"default": spec}}))
		var r := prefs.load_from(p)
		check("units default %s accepted" % spec, r["problems"].is_empty() and r["values"]["units"] == {"default": spec})
		check("units default %s marks units.default changed" % spec, r["changed"] == ["units.default"])

	# Same spec again: unchanged
	var r_same := prefs.load_from(p)
	check("units default unchanged: changed empty", r_same["problems"].is_empty() and r_same["changed"].is_empty())

	# Explicit null clears default
	write_text(p, "{\"units\": {\"default\": null}}\n")
	var r_null := prefs.load_from(p)
	check("units default null accepted and clears", r_null["problems"].is_empty() and r_null["values"]["units"] == {"default": null})
	check("units default null marks units.default changed", r_null["changed"] == ["units.default"])

	# Set a good default, then test unknown key and bad values
	write_text(p, "{\"units\": {\"default\": \"mm:1\"}}\n")
	prefs.load_from(p)

	write_text(p, "{\"units\": {\"default\": \"in-dec:0.01\", \"precision\": 16}}\n")
	var r_unk := prefs.load_from(p)
	check("unknown units key reports exact problem",
		r_unk["problems"] == ["preferences.json: unknown units setting precision"])
	check("unknown units key still applies valid default and drops unknown",
		r_unk["values"]["units"] == {"default": "in-dec:0.01"})

	for bad_val in ["\"metric\"", "\"\"", "\"mm:0.001\"", "42", "true", "[1]", "{\"a\": 1}"]:
		write_text(p, "{\"units\": {\"default\": %s}}\n" % bad_val)
		var r_bad := prefs.load_from(p)
		check("bad units default %s keeps last good" % bad_val, r_bad["values"]["units"] == {"default": "in-dec:0.01"})
		check("bad units default %s reports exact format" % bad_val,
			r_bad["problems"].size() == 1
			and r_bad["problems"][0].begins_with('preferences.json: units default must be a units setting like "in-frac:1/16" (got '))
		check("bad units default %s has no change" % bad_val, r_bad["changed"].is_empty())

	# Omitting units section reverts default to null
	write_text(p, "{\"tuning\": {\"SNAP_PX\": 14}}\n")
	var r_omit := prefs.load_from(p)
	check("omitting units section reverts default to null",
		r_omit["problems"].is_empty() and r_omit["values"]["units"] == {"default": null} and r_omit["changed"] == ["units.default"])


func _test_measure_box_default_units() -> void:
	var mb := MeasureBox.new()
	var cfg_path := tmp_dir.path_join("mb_settings.cfg")
	mb.init_units(cfg_path, Units.DEFAULT_SPEC)
	check("default_units: fallback when no preference and no settings", mb.default_units() == Units.DEFAULT_SPEC)

	var cfg := ConfigFile.new()
	cfg.set_value("units", "last", "cm:0.1")
	cfg.save(cfg_path)
	check("default_units: last used wins over fallback", mb.default_units() == "cm:0.1")

	mb.pref_default_units = "in-dec:0.01"
	check("default_units: preference wins over last used and fallback", mb.default_units() == "in-dec:0.01")

	mb.pref_default_units = ""
	check("default_units: clearing preference falls back to last used", mb.default_units() == "cm:0.1")

	mb.pref_default_units = "not-a-spec"
	check("default_units: invalid preference falls back to last used", mb.default_units() == "cm:0.1")
	mb.free()
