extends SceneTree
## Unit parsing, display formatting (I57, I59, I62), FreeCAD evaluator agreement (P21), and MeasureBox units sync /
## link-drop / open-race / settings persistence checks (H052).
## Run: Godot --headless --path viewport --script res://test_units.gd
const Units = preload("res://units.gd")
const MeasureBox = preload("res://measure_box.gd")
const Document = preload("res://document.gd")
var passed := 0
var failed := 0
var made: Array = []


class FakeClient:
	var sent: Array = []
	func send(d: Dictionary) -> void: sent.append(d.duplicate(true))
	func by_cmd(cmd: String) -> Array: return sent.filter(func(d): return d.get("cmd", "") == cmd)


class FakeTool:
	var state := {"active": true}
	var last_typed := ""
	func vcb_label() -> String: return "Distance"
	func vcb_value() -> String: return ""
	func typed(txt: String) -> void: last_typed = txt


class FakeMenus:
	var updates := 0
	func update_units_menu() -> void: updates += 1


class FakeMain:
	var doc
	var client
	var model_path := "/tmp/units-test.FCStd"
	var seq := 0
	var tool := "push"
	var tools := {}
	var ui_sync := {"text": ""}
	var menus := FakeMenus.new()


func check(label: String, condition: bool, detail = "") -> void:
	if condition:
		passed += 1
		print("PASS ", label)
	else:
		failed += 1
		print("FAIL ", label, "  ", detail)


func _rounded_step_mm(spec: String) -> float:
	var p := Units.parse_spec(spec)
	var fmt: String = p["format"]
	var prec: String = p["precision"]
	if fmt in ["ft-in", "in-frac"]: return 25.4 / float(int(prec.substr(2)))
	var factor := 25.4 if fmt == "in-dec" else (1000.0 if fmt == "m" else (10.0 if fmt == "cm" else 1.0))
	return float(prec) * factor


func _init() -> void:
	# --- parsing ---
	var cases := {"19": 19.0, "19mm": 19.0, "1.9cm": 19.0, "0.019m": 19.0,
		"3/4\"": 19.05, "0.75in": 19.05, "1 1/2\"": 38.1,
		"1'": 304.8, "1'6\"": 457.2, "1'6 1/2\"": 469.9, "1' 6 1/2\"": 469.9, "-12": -12.0,
		"+5": 5.0, " 3/4 in ": 19.05, "-1' 6\"": -457.2,
		".5 m": 500.0, "2 FT 3 IN": 685.8, "1 / 2 mm": 0.5, "0": 0.0}
	for input in cases:
		var result := Units.parse_length(input)
		check(input, result.ok and absf(result.mm - cases[input]) < 0.00001)
	check("default inches", is_equal_approx(Units.parse_length("3/4", "in").mm, 19.05))
	check("default cm", is_equal_approx(Units.parse_length("2", "cm").mm, 20.0))
	for input in ["", "abc", "3//4", "1/0", "3x", "/3", "1 2", "1mm junk", "1'6", "1in2in", "--2", "1--1/2", "1 -1/2", "1.2.3", "1mm 2cm", "1,5", "nan", "inf", "1e3", "1-2-3/4", "1'2'", "1/2/3", "1 +2", "2m-1m", "1'-", "1'-6", "1'--6\"", "6\"-1'", "1-1/2\"", "1'-6\"", "1'-6-1/2\"", "1'6-1/2\""]:
		var result := Units.parse_length(input)
		check("reject " + input, not result.ok and not result.error.is_empty())
	check("bad default unit", not Units.parse_length("2", "yards").ok)
	var pair := Units.parse_pair("1' 6\", 3/4\"")
	check("pair", pair.ok and is_equal_approx(pair.a_mm, 457.2) and is_equal_approx(pair.b_mm, 19.05))
	for input in ["1", "1,2,3", ",2", "1,", "bad,2"]:
		check("reject pair " + input, not Units.parse_pair(input).ok)

	# --- spec parsing and helpers (I57, I59) ---
	check("default spec is fractional inches at 1/16\"", Units.DEFAULT_SPEC == "in-frac:1/16" and Units.parse_spec(Units.DEFAULT_SPEC).ok)
	for bad in ["", "furlongs", "mm", "mm:0.001", "in-frac:1/7", "ft-in:0.1", "in-dec:1/16", "m:1", "cm:0.001"]:
		check("reject invalid spec " + bad, not Units.parse_spec(bad).ok)
	check("default_unit_of maps formats to bare units (I59)",
		Units.default_unit_of("ft-in:1/16") == "in" and Units.default_unit_of("in-frac:1/32") == "in"
		and Units.default_unit_of("in-dec:0.01") == "in" and Units.default_unit_of("m:0.001") == "m"
		and Units.default_unit_of("cm:0.1") == "cm" and Units.default_unit_of("mm:1") == "mm")
	check("with_format keeps compatible rounding and resets incompatible",
		Units.with_format("ft-in:1/32", "in-frac") == "in-frac:1/32"
		and Units.with_format("in-frac:1/32", "in-dec") == "in-dec:0.01"
		and Units.with_format("mm:0.01", "cm") == "cm:0.01"
		and Units.with_format("mm:1", "m") == "m:0.001")
	check("with_precision switches rounding within format",
		Units.with_precision("ft-in:1/16", "1/64") == "ft-in:1/64"
		and Units.with_precision("mm:0.1", "1") == "mm:1"
		and Units.with_precision("mm:0.1", "1/16") == "mm:0.1")

	# --- detect_typed_spec (T124, I67) ---
	var detect_cases := {
		"": "",
		"   ": "",
		"100": "",
		"12, 6": "",
		"3/4": "",
		"3x": "",
		"/3": "",
		"x5": "",
		"*4": "",
		"sin(30)": "",
		"4\"": "in-frac:1/16",
		"4.25\"": "in-dec:0.01",
		"0.75in": "in-dec:0.01",
		"3/4 in": "in-frac:1/16",
		"1 1/2 in": "in-frac:1/16",
		"1' 6\"": "ft-in:1/16",
		"1'6\"": "ft-in:1/16",
		"1' 6\" - 2\"": "ft-in:1/16",
		"2ft": "ft-in:1/16",
		"1ft^1": "ft-in:1/16",
		"120mm": "mm:0.1",
		"15cm": "cm:0.1",
		"1.5m": "m:0.01",
		"4\", 5\"": "in-frac:1/16",
		"4, 5\"": "in-frac:1/16",
		"4.5\", 5\"": "in-dec:0.01",
		"5in + 23mm": "in-frac:1/16",
		"23mm + 5in": "mm:0.1",
		"6\" + 1'": "ft-in:1/16",
	}
	for input in detect_cases:
		var got := Units.detect_typed_spec(input)
		check("detect_typed_spec(%s) == %s" % [JSON.stringify(input), JSON.stringify(detect_cases[input])],
			got == detect_cases[input], got)

	# --- formatting: every format, every rounding, exact vs ~ (I57) ---
	var sample_in := 99.25 * 25.4   # 2520.95 mm = 8' 3 1/4" = 99 1/4" = 99.25"
	check("feet and inches exact (8' 3 1/4\")", Units.format_length(sample_in, "ft-in:1/16") == "8' 3 1/4\"", Units.format_length(sample_in, "ft-in:1/16"))
	check("inches as fractions exact (99 1/4\")", Units.format_length(sample_in, "in-frac:1/16") == "99 1/4\"", Units.format_length(sample_in, "in-frac:1/16"))
	check("inches as decimals exact (99.25\")", Units.format_length(sample_in, "in-dec:0.01") == "99.25\"", Units.format_length(sample_in, "in-dec:0.01"))
	check("inches as decimals 0.1 rounds with ~", Units.format_length(sample_in, "in-dec:0.1") == "~99.3\"", Units.format_length(sample_in, "in-dec:0.1"))
	check("inches as decimals 0.001 trims trailing zero", Units.format_length(sample_in, "in-dec:0.001") == "99.25\"", Units.format_length(sample_in, "in-dec:0.001"))
	check("inches as decimals 0.001 keeps 1/8\" = 0.125\"", Units.format_length(25.4 / 8.0, "in-dec:0.001") == "0.125\"")
	check("inches as decimals 0.01 rounds 0.125\" to ~0.13\"", Units.format_length(25.4 / 8.0, "in-dec:0.01") == "~0.13\"")
	check("feet and inches 1/8 rounds 3/16\" to ~1/4\"", Units.format_length(25.4 * 3.0 / 16.0, "ft-in:1/8") == "~1/4\"")
	check("feet and inches 1/16 exact 3/16\"", Units.format_length(25.4 * 3.0 / 16.0, "ft-in:1/16") == "3/16\"")
	check("feet and inches 1/32 exact 1/32\"", Units.format_length(25.4 / 32.0, "ft-in:1/32") == "1/32\"")
	check("feet and inches 1/64 exact 1/64\"", Units.format_length(25.4 / 64.0, "ft-in:1/64") == "1/64\"")
	check("inches as fractions never shows feet (12\")", Units.format_length(304.8, "in-frac:1/16") == "12\"")
	check("feet and inches carries to feet (1' 0\")", Units.format_length(304.8, "ft-in:1/16") == "1' 0\"")
	check("carry feet with ~ when rounded", Units.format_length(304.79, "ft-in:1/16") == "~1' 0\"", Units.format_length(304.79, "ft-in:1/16"))
	check("feet and a fraction (1' 1/2\")", Units.format_length(304.8 + 12.7, "ft-in:1/16") == "1' 1/2\"")
	check("under an inch (3/4\")", Units.format_length(19.05, "in-frac:1/16") == "3/4\"")
	check("19 mm in inches shows ~3/4\"", Units.format_length(19.0, "in-frac:1/16") == "~3/4\"")
	check("negative exact (-1' 6\")", Units.format_length(-457.2, "ft-in:1/16") == "-1' 6\"")
	check("negative rounded (~-3/4\")", Units.format_length(-19.0, "in-frac:1/16") == "~-3/4\"")
	check("negative tiny rounds to ~0\" (no minus)", Units.format_length(-0.01, "ft-in:1/16") == "~0\"", Units.format_length(-0.01, "ft-in:1/16"))
	check("exact zero has no ~", Units.format_length(0.0, "in-frac:1/16") == "0\"" and Units.format_length(0.0, "mm:0.1") == "0 mm")
	check("float32 noise does not trigger false ~", Units.format_length(19.05 + 0.0001, "in-frac:1/16") == "3/4\""
		and Units.format_length(100.0 - 0.0001, "mm:1") == "100 mm")
	check("metric mm 1 / 0.1 / 0.01",
		Units.format_length(19.0, "mm:1") == "19 mm" and Units.format_length(19.06, "mm:1") == "~19 mm"
		and Units.format_length(19.06, "mm:0.1") == "~19.1 mm" and Units.format_length(19.06, "mm:0.01") == "19.06 mm"
		and Units.format_length(19.064, "mm:0.01") == "~19.06 mm")
	check("metric cm 1 / 0.1 / 0.01",
		Units.format_length(20.0, "cm:1") == "2 cm" and Units.format_length(19.0, "cm:1") == "~2 cm"
		and Units.format_length(19.0, "cm:0.1") == "1.9 cm" and Units.format_length(19.5, "cm:0.1") == "~2 cm"
		and Units.format_length(19.5, "cm:0.01") == "1.95 cm")
	check("metric m 0.1 / 0.01 / 0.001",
		Units.format_length(1200.0, "m:0.1") == "1.2 m" and Units.format_length(1250.0, "m:0.1") == "~1.3 m"
		and Units.format_length(1250.0, "m:0.01") == "1.25 m" and Units.format_length(1234.0, "m:0.01") == "~1.23 m"
		and Units.format_length(1234.0, "m:0.001") == "1.234 m" and Units.format_length(1234.4, "m:0.001") == "~1.234 m")
	check("legacy format_length aliases still work",
		Units.format_length(19.0, "metric") == "19 mm" and Units.format_length(38.1, "imperial") == "1 1/2\""
		and Units.format_length(25.4 / 64.0, "imperial", 64) == "1/64\"")
	check("invalid spec or non-finite returns empty",
		Units.format_length(10.0, "furlongs") == "" and Units.format_length(NAN, "mm:0.1") == "" and Units.format_length(INF, "in-frac:1/16") == "")

	# --- round trip: every format and rounding parses back via both parse_length and evaluate_length ---
	var all_specs := []
	for fmt in Units.FORMAT_ORDER:
		for prec in Units.FORMATS[fmt]["precisions"]:
			all_specs.append(fmt + ":" + prec)
	var rt_bad := []
	for spec in all_specs:
		var step := _rounded_step_mm(spec)
		var du := Units.default_unit_of(spec)
		for mm in [-2520.95, -1234.567, -304.8, -25.4, -0.01, 0.0, 0.4, 19.0, 19.05, 304.8, 317.5, 2520.95, 2000.123]:
			var shown := Units.format_length(mm, spec)
			var approx := shown.begins_with("~")
			var clean := shown.substr(1) if approx else shown
			var p1 := Units.parse_length(clean, du)
			var p2 := Units.evaluate_length(clean, du)
			if not p1.ok or not p2.ok or absf(p1.mm - p2.mm) > 1e-6:
				rt_bad.append([spec, mm, shown, p1, p2])
				continue
			if absf(p1.mm - mm) > step * 0.5 + 0.00001:
				rt_bad.append(["range", spec, mm, shown, p1.mm, step])
			if (not approx) and absf(p1.mm - mm) > Units.ROUND_TOL_MM + 1e-6:
				rt_bad.append(["missing ~", spec, mm, shown, p1.mm])
			if approx and absf(p1.mm - mm) <= Units.ROUND_TOL_MM - 1e-6:
				rt_bad.append(["spurious ~", spec, mm, shown, p1.mm])
	check("all %d format/rounding specs round-trip cleanly through parse_length & evaluate_length" % all_specs.size(), rt_bad.is_empty(), rt_bad.slice(0, 5))

	_freecad_agreement()
	_measure_box_units_lifecycle()
	for n in made: if is_instance_valid(n): n.free()
	print("UNITS TESTS: %d passed, %d failed" % [passed, failed])
	quit(1 if failed else 0)


## evaluate_length must give FreeCAD's answer whenever it answers (tests/length_cases.json, made by FreeCAD with
## tools/length_cases.py), and answer what people type, so typed values don't wait for the worker.
func _freecad_agreement() -> void:
	var path := ProjectSettings.globalize_path("res://").path_join("../tests/length_cases.json")
	var table = JSON.parse_string(FileAccess.get_file_as_string(path))
	check("FreeCAD's length table loads", typeof(table) == TYPE_DICTIONARY and table.cases.size() > 1000)
	if typeof(table) != TYPE_DICTIONARY: return
	var answered := 0
	var inch_cases := 0
	var wrong: Array = []
	for c in table.cases:
		var du: String = String(c.get("default_unit", "mm"))
		if du == "in": inch_cases += 1
		var here := Units.evaluate_length(c.text, du)
		if not here.ok: continue
		answered += 1
		var want = c.mm
		if want == null or absf(here.mm - float(want)) > 1e-9 * maxf(1.0, absf(float(want))):
			wrong.append([c.text, du, here.mm, want])
	check("length table includes bare-number-in-inches cases (P21)", inch_cases >= 5, inch_cases)
	check("local answers agree with FreeCAD on all %d it gave (of %d cases)" % [answered, table.cases.size()], wrong.is_empty(), wrong.slice(0, 5))
	for w in wrong.slice(0, 10): print("  DISAGREES ", w)
	var lengths := 0
	for c in table.cases: if c.mm != null: lengths += 1
	print("  local evaluator answered %d of FreeCAD's %d lengths at once" % [answered, lengths])
	check("it answers at least 95% of FreeCAD's lengths at once", answered >= 0.95 * lengths)
	for t in ["150", "3/4\"", "1' 6 1/2\"", "5in + 23mm", "1'-6\"", "(24in - 2*19mm)/3", "2 * 19mm", "-1ft 6in", "19mm", "1 1/2 in"]:
		check("typed without waiting: " + t, Units.evaluate_length(t).ok)
	check("bare number in inches evaluates at once (I59)", is_equal_approx(Units.evaluate_length("12", "in").mm, 304.8)
		and is_equal_approx(Units.evaluate_length("3/4", "in").mm, 19.05)
		and is_equal_approx(Units.evaluate_length("19mm", "in").mm, 19.0))
	check("pair in inches evaluates bare numbers as inches (I59)",
		Units.evaluate_pair("12, 6", "in").ok and is_equal_approx(Units.evaluate_pair("12, 6", "in").a_mm, 304.8)
		and is_equal_approx(Units.evaluate_pair("12, 6", "in").b_mm, 152.4))
	check("pair: 5in + 23mm, 3/4\"", Units.evaluate_pair("5in + 23mm, 3/4\"").ok and is_equal_approx(Units.evaluate_pair("5in + 23mm, 3/4\"").b_mm, 19.05))


## MeasureBox units sync: last-used settings, open races, link drop & reconnect, reload, and default_unit (H052 P42).
func _measure_box_units_lifecycle() -> void:
	var cfg := OS.get_temp_dir().path_join("shopsketch-units-test-%d.cfg" % OS.get_process_id())
	DirAccess.remove_absolute(cfg)
	var doc := Document.new(); made.append(doc)
	var client := FakeClient.new()
	doc.client = client; doc.model_path = "/tmp/u1.FCStd"
	var fm := FakeMain.new()
	fm.doc = doc; fm.client = client; fm.model_path = doc.model_path
	var ft := FakeTool.new()
	fm.tools = {"push": ft}
	var mb := MeasureBox.new(); made.append(mb)
	mb.m = fm
	mb.init_units(cfg, Units.DEFAULT_SPEC)
	check("fresh MeasureBox starts in fractional inches at 1/16\"", mb.units == "in-frac:1/16")

	# New model: open reply has no units -> keeps last-used/default without locking or sending set_units (I67).
	doc.on_opened({"ok": true, "rev": 0, "ops": []}, true)
	mb.on_opened({"ok": true, "rev": 0, "ops": []}, true)
	check("new model with no saved units stays unset and does not send set_units yet",
		client.by_cmd("set_units").is_empty() and not mb.units_dirty and not mb.units_explicit)
	check("fresh missing settings_path reports has_saved_default_units() == false (I70)",
		not mb.has_saved_default_units())

	# I70: bare length on fresh install (missing settings_path, no pref) prompts without committing or locking.
	mb.vcb = "10"
	mb.apply()
	check("fresh install bare length prompts without committing and leaves units unlocked (I70)",
		ft.last_typed == "" and not mb.units_explicit and client.by_cmd("set_units").is_empty()
		and fm.ui_sync.text == MeasureBox.FIRST_UNIT_PROMPT, [ft.last_typed, mb.units_explicit, fm.ui_sync.text])
	# Also for a FreeCAD-evaluated bare expression on a fresh install.
	fm.ui_sync.text = ""
	mb.vcb = "sqrt(4) * foo"
	mb.apply()
	var fresh_bare_id: int = client.by_cmd("length").back()["id"]
	mb.on_length({"cmd": "length", "id": fresh_bare_id, "ok": true, "values": [254.0]})
	check("fresh install FreeCAD-evaluated bare length prompts without committing (I70)",
		ft.last_typed == "" and not mb.units_explicit and client.by_cmd("set_units").is_empty()
		and fm.ui_sync.text == MeasureBox.FIRST_UNIT_PROMPT, [ft.last_typed, mb.units_explicit, fm.ui_sync.text])

	# First valid typed length with an explicit unit right after commits, adopts, and populates settings.cfg (I67, I70).
	mb.vcb = "120mm"
	mb.apply()
	var su := client.by_cmd("set_units")
	check("first typed explicit unit adopts mm:0.1, locks units, and sends set_units",
		mb.units == "mm:0.1" and mb.units_explicit and mb.units_dirty and su.size() == 1
		and su.back()["units"] == "mm:0.1" and absf(float(ft.last_typed) - 120.0) < 1e-6 and mb.has_saved_default_units())
	mb.on_set_units_reply({"ok": true, "cmd": "set_units", "model": fm.model_path, "units": "mm:0.1", "rev": 1, "seq": su.back()["seq"]})
	check("set_units reply clears dirty and advances pending_rev for save indicator / close",
		not mb.units_dirty and doc.pending_rev == 1 and doc.unsaved())
	doc.on_saved({"cmd": "saved", "model": fm.model_path, "rev": 1})
	# Subsequent explicit unit in another system converts without flipping units.
	mb.vcb = "4\""
	mb.apply()
	check("subsequent explicit unit converts without flipping locked units",
		mb.units == "mm:0.1" and absf(float(ft.last_typed) - 101.6) < 1e-6, [mb.units, ft.last_typed])

	# Link drops between menu choice and reply: UI updates at once, and reconnect resends set_units.
	var before_n := client.by_cmd("set_units").size()
	mb.set_units("ft-in:1/32", true)
	check("menu choice updates display immediately and sends set_units", mb.units == "ft-in:1/32" and mb.units_dirty
		and client.by_cmd("set_units").size() == before_n + 1 and fm.menus.updates > 0)
	# Simulate link drop before reply arrives: reconnect resends set_units.
	doc.on_link_up()
	mb.on_link_up()
	check("reconnect after lost set_units reply resends set_units", client.by_cmd("set_units").size() == before_n + 2
		and client.by_cmd("set_units").back()["units"] == "ft-in:1/32")
	var resent_seq: int = client.by_cmd("set_units").back()["seq"]
	mb.on_set_units_reply({"ok": true, "cmd": "set_units", "model": fm.model_path, "units": "ft-in:1/32", "rev": 2, "seq": resent_seq})
	check("worker crash after set_units reply but before autosave lands still resends on reconnect",
		not mb.units_dirty and mb.units_pending_rev == 2 and doc.saved_rev == 1)
	var before_crash := client.by_cmd("set_units").size()
	doc.on_link_up(); mb.on_link_up()
	check("unsaved units resent after crash", client.by_cmd("set_units").size() == before_crash + 1)

	# New model starts in last units used (settings.cfg), and a user choice made before open reply isn't overwritten.
	doc.reset(); doc.opened = false; fm.model_path = "/tmp/u2.FCStd"; doc.model_path = fm.model_path
	mb.reset_for_model()
	check("new model loads last units used from settings.cfg", mb.units == "ft-in:1/32")
	mb.set_units("cm:0.1", true)      # user changes units while open is still in flight
	var sent_before_open := client.by_cmd("set_units").size()
	doc.on_opened({"ok": true, "rev": 3, "ops": [], "units": "mm:1"}, true)
	mb.on_opened({"ok": true, "rev": 3, "ops": [], "units": "mm:1"}, true)
	check("open reply does not overwrite a choice the user made meanwhile, and sends it once open",
		mb.units == "cm:0.1" and client.by_cmd("set_units").size() == sent_before_open + 1
		and client.by_cmd("set_units").back()["units"] == "cm:0.1")

	# Opening a model with saved units adopts them and locks units_explicit; unreadable/missing units stay unlocked (I62/I67).
	doc.reset(); doc.opened = false; fm.model_path = "/tmp/u3.FCStd"; doc.model_path = fm.model_path
	mb.reset_for_model()
	doc.on_opened({"ok": true, "rev": 1, "ops": [], "units": "in-dec:0.001"}, true)
	mb.on_opened({"ok": true, "rev": 1, "ops": [], "units": "in-dec:0.001"}, true)
	check("opening a model with saved units adopts them and locks units_explicit",
		mb.units == "in-dec:0.001" and mb.units_explicit and not mb.units_dirty)

	# Outside save reload adopts FreeCAD file's units.
	mb.on_reloaded({"ok": true, "cmd": "reload", "units": "mm:0.01"})
	check("reload adopts the units from FreeCAD's file", mb.units == "mm:0.01" and mb.units_explicit and not mb.units_dirty)

	# FreeCAD-evaluated (declined) length on unset model: rejected does NOT adopt; ok adopts (I67).
	doc.reset(); doc.opened = false; fm.model_path = "/tmp/u4.FCStd"; doc.model_path = fm.model_path
	mb.reset_for_model()
	doc.on_opened({"ok": true, "rev": 0, "ops": []}, true)
	mb.on_opened({"ok": true, "rev": 0, "ops": []}, true)
	var before_bad_units: String = mb.units
	mb.vcb = "abc mm"
	mb.apply()
	var bad_id: int = client.by_cmd("length").back()["id"]
	mb.on_length({"cmd": "length", "id": bad_id, "ok": false, "error": "bad"})
	check("rejected FreeCAD length with unit does not change or lock units",
		mb.units == before_bad_units and not mb.units_explicit)
	mb.vcb = "1ft^1"
	mb.apply()
	var ok_id: int = client.by_cmd("length").back()["id"]
	mb.on_length({"cmd": "length", "id": ok_id, "ok": true, "values": [304.8]})
	check("accepted FreeCAD length adopts ft-in:1/16 and locks units",
		mb.units == "ft-in:1/16" and mb.units_explicit and absf(float(ft.last_typed) - 304.8) < 1e-6)

	# First typed length is bare when settings.cfg is populated: commits immediately, keeps default units and locks (I70).
	doc.reset(); doc.opened = false; fm.model_path = "/tmp/u5.FCStd"; doc.model_path = fm.model_path
	mb.reset_for_model()
	doc.on_opened({"ok": true, "rev": 0, "ops": []}, true)
	mb.on_opened({"ok": true, "rev": 0, "ops": []}, true)
	var before_bare_units: String = mb.units
	ft.last_typed = ""
	mb.vcb = "10"
	mb.apply()
	check("bare first typed length with saved settings.cfg commits immediately and locks default units (I70)",
		mb.has_saved_default_units() and mb.units == before_bare_units and mb.units_explicit and ft.last_typed != "")
	mb.vcb = "120mm"
	mb.apply()
	check("explicit unit after bare first typed length converts without flipping units",
		mb.units == before_bare_units and absf(float(ft.last_typed) - 120.0) < 1e-6, [mb.units, ft.last_typed])

	# has_saved_default_units() is true for test isolation (settings_path == "") and for valid pref_default_units.
	var mb_iso := MeasureBox.new(); made.append(mb_iso)
	mb_iso.init_units("", Units.TEST_SPEC)
	check("test-isolation empty settings_path reports has_saved_default_units() == true", mb_iso.has_saved_default_units())
	mb_iso.settings_path = cfg + ".missing"
	check("missing settings_path with no pref reports has_saved_default_units() == false", not mb_iso.has_saved_default_units())
	mb_iso.pref_default_units = "mm:0.1"
	check("valid pref_default_units reports has_saved_default_units() == true", mb_iso.has_saved_default_units())

	# Typed bare number uses model's default_unit, both locally and when sent to worker (I59).
	mb.set_units("in-frac:1/16", true)
	mb.vcb = "12"
	mb.apply()
	check("typed bare number in inches converts to 304.8 mm at once", absf(float(ft.last_typed) - 304.8) < 1e-6, ft.last_typed)
	mb.vcb = "50mm"
	mb.apply()
	check("explicit unit wins over model units (I59)", absf(float(ft.last_typed) - 50.0) < 1e-6, ft.last_typed)
	var lens_before := client.by_cmd("length").size()
	mb.vcb = "sqrt(4) * foo"     # declined locally -> goes to worker with default_unit = "in"
	mb.apply()
	var lens := client.by_cmd("length")
	check("declined length request carries the model's default_unit",
		lens.size() == lens_before + 1 and lens.back()["default_unit"] == "in", lens)
	DirAccess.remove_absolute(cfg)
