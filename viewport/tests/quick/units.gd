extends RefCounted
## Display units (T66, I57, I59, I62): Units menu, measurements box display across tools, bare typed numbers
## in the model's units, persistence across save & reopen, undo invariance, and new model inheriting last units used.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
const Units := preload("res://units.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func _until(cond: Callable, ms := 10000) -> bool:
	var t0 := Time.get_ticks_msec()
	while not cond.call() and Time.get_ticks_msec() - t0 < ms: await harness._frames(1)
	return cond.call()


func run() -> void:
	await harness._fresh("units", [], true)
	await harness._view(Vector3(200, 150, 0), -30, -50, 1.4)

	# 1. Switch units and read the measurements box during live drags (exact and ~ rounded).
	m.set_tool("rect")
	await harness._drag_to(Vector3(0, 0, 0), 2); await harness._press()
	await harness._drag_to(Vector3(300, 200, 0), 2)
	m.menus.on_units_menu("format:mm")
	m.menus.on_units_menu("prec:1")
	harness._ok("mm format shows exact mm in the measurements box", m.ui_vcb.text == "300 mm, 200 mm", m.ui_vcb.text)

	m.menus.on_units_menu("format:cm")
	m.menus.on_units_menu("prec:0.1")
	harness._ok("cm format updates the measurements box immediately", m.ui_vcb.text == "30 cm, 20 cm", m.ui_vcb.text)

	m.menus.on_units_menu("format:m")
	m.menus.on_units_menu("prec:0.01")
	harness._ok("m format updates the measurements box immediately", m.ui_vcb.text == "0.3 m, 0.2 m", m.ui_vcb.text)

	m.menus.on_units_menu("format:in-frac")
	m.menus.on_units_menu("prec:1/16")
	harness._ok("fractional inches shows ~ for rounded mm lengths (300 mm ≈ 11 13/16\", 200 mm ≈ 7 7/8\")",
		m.ui_vcb.text == "~11 13/16\", ~7 7/8\"", m.ui_vcb.text)

	m.menus.on_units_menu("format:in-dec")
	m.menus.on_units_menu("prec:0.01")
	harness._ok("decimal inches shows ~11.81\", ~7.87\"", m.ui_vcb.text == "~11.81\", ~7.87\"", m.ui_vcb.text)

	# 2. Bare typed numbers are in the model's units (I59); explicit units always win.
	m.menus.on_units_menu("format:ft-in")
	m.menus.on_units_menu("prec:1/16")
	var units_menu: RID = m.menus.units_menu_rid
	if units_menu.is_valid():
		var checked := []
		for i in NativeMenu.get_item_count(units_menu):
			if NativeMenu.is_item_checked(units_menu, i): checked.append(NativeMenu.get_item_tag(units_menu, i))
		harness._ok("Units menu checks the current format and rounding", checked == ["format:ft-in", "prec:1/16"], checked)
	await harness._type("12, 6\n")
	await harness._wait_confirm()
	var rect_op: Dictionary = m.ops.back()
	harness._ok("bare typed numbers in feet-and-inches mean inches (12, 6 -> 304.8 x 152.4 mm)",
		rect_op["type"] == "rect" and is_equal_approx(float(rect_op["size"][0]), 304.8)
		and is_equal_approx(float(rect_op["size"][1]), 152.4), rect_op)

	# Push the rectangle up with an explicit mm unit while still in feet-and-inches.
	m.set_tool("push")
	await harness._drag_to(Vector3(150, 75, 0), 2); await harness._press()
	await harness._drag_to(Vector3(150, 75, 40), 2)
	harness._ok("Push/Pull box shows feet-and-inches while dragging", m.ui_vcb.text.ends_with("\""), m.ui_vcb.text)
	await harness._type("50mm\n")
	await harness._wait_confirm()
	var b1 := harness.id("b1")
	harness._ok("explicit unit wins over model units (50mm -> 50 mm thick)",
		harness._bbox(b1).size() == 6 and is_equal_approx(harness._bbox(b1)[5], 50.0), harness._bbox(b1))

	# Circle, Line and Move read the model's units too.
	m.set_tool("circle")
	await harness._drag_to(Vector3(100, 75, 50), 2); await harness._press()
	await harness._drag_to(Vector3(150, 75, 50), 2)
	harness._ok("Circle box shows inches when model is in inches", m.ui_vcb.text.ends_with("\""), m.ui_vcb.text)
	m.tools["circle"].reset()
	m.set_tool("line")
	await harness._drag_to(Vector3(50, 50, 50), 2); await harness._press()
	await harness._drag_to(Vector3(150, 50, 50), 2)
	harness._ok("Line box shows inches when model is in inches", m.ui_vcb.text.ends_with("\""), m.ui_vcb.text)
	m.tools["line"].reset()
	m.set_tool("move")
	await harness._drag_to(Vector3(50, 50, 50), 2); await harness._press()
	await harness._drag_to(Vector3(150, 50, 50), 2)
	harness._ok("Move box and tooltip show inches when model is in inches",
		m.ui_vcb.text.ends_with("\"") and m.tools["move"].tip().contains("\""), [m.ui_vcb.text, m.tools["move"].tip()])
	m.tools["move"].reset()

	# 3. Units survive save & reopen, and undo doesn't change the units.
	var saved_model: String = m.model_path
	m.set_units("ft-in:1/32")
	await _until(func(): return not m.measure.units_dirty and m.saved_rev >= m.pending_rev and m.pending_rev > 0)
	m.undo()
	await harness._wait_confirm()
	harness._ok("undo after changing units leaves the units alone", m.measure.units == "ft-in:1/32", m.measure.units)
	await _until(func(): return m.saved_rev >= m.pending_rev)

	# 4. Last units used (settings.cfg): a new model inherits them, and reopening the first model restores its own.
	var tmp_cfg := m.out_dir.path_join("units_test_settings.cfg")
	DirAccess.remove_absolute(tmp_cfg)
	m.measure.settings_path = tmp_cfg
	m.set_units("in-dec:0.001")
	await _until(func(): return not m.measure.units_dirty and m.saved_rev >= m.pending_rev)

	var model_b := m.out_dir.path_join("quick_units_new.FCStd")
	m.switch_model(model_b, true)
	await _until(func(): return m.opened)
	await _until(func(): return not m.measure.units_dirty and m.saved_rev >= m.pending_rev)
	harness._ok("a new model starts with the last units used (settings.cfg)", m.measure.units == "in-dec:0.001", m.measure.units)

	m.set_units("cm:0.01")
	await _until(func(): return not m.measure.units_dirty and m.saved_rev >= m.pending_rev)
	m.switch_model(saved_model, false)
	await _until(func(): return m.opened)
	await harness._wait_confirm()
	harness._ok("reopening a saved model restores its own saved units", m.measure.units == "in-dec:0.001", m.measure.units)

	# 5. Auto-set document units from first typed length with an explicit unit (T124, I67).
	# 5a. New/unset model stays on previous settings (mm:0.1) with units_explicit == false; malformed input does not flip.
	m.set_units("mm:0.1")
	await _until(func(): return not m.measure.units_dirty and m.saved_rev >= m.pending_rev)
	var model_auto := m.out_dir.path_join("quick_units_auto.FCStd")
	m.switch_model(model_auto, true)
	await _until(func(): return m.opened)
	await harness._view(Vector3(100, 100, 0), -30, -50, 1.2)
	harness._ok("new/unset model starts on previous settings and stays unlocked",
		m.measure.units == "mm:0.1" and not m.measure.units_explicit, [m.measure.units, m.measure.units_explicit])

	m.set_tool("rect")
	await harness._drag_to(Vector3(0, 0, 0), 2); await harness._press()
	await harness._drag_to(Vector3(80, 80, 0), 2)
	await harness._type("abc mm, 3//4\"\n")
	await _until(func(): return m.length_pending.is_empty())
	harness._ok("malformed typed input with unit does not change or lock document units",
		m.measure.units == "mm:0.1" and not m.measure.units_explicit, [m.measure.units, m.measure.units_explicit])

	# 5b. First valid typed length with explicit unit (4", 5") adopts in-frac:1/16, saves to .FCStd, and remembers last used.
	await harness._type("4\", 5\"\n")
	await harness._wait_confirm()
	await _until(func(): return not m.measure.units_dirty and m.saved_rev >= m.pending_rev)
	var auto_rect: Dictionary = m.ops.back()
	var cfg_check := ConfigFile.new()
	cfg_check.load(tmp_cfg)
	harness._ok("first typed 4\", 5\" on unset model adopts in-frac:1/16 and remembers as last used",
		m.measure.units == "in-frac:1/16" and m.measure.units_explicit
		and String(cfg_check.get_value("units", "last", "")) == "in-frac:1/16"
		and auto_rect["type"] == "rect" and is_equal_approx(float(auto_rect["size"][0]), 101.6)
		and is_equal_approx(float(auto_rect["size"][1]), 127.0),
		[m.measure.units, m.measure.units_explicit, cfg_check.get_value("units", "last", ""), auto_rect])

	# 5c. Subsequent typed length in another unit (19mm) converts without flipping document units back.
	m.set_tool("push")
	await harness._drag_to(Vector3(50, 60, 0), 2); await harness._press()
	await harness._drag_to(Vector3(50, 60, 30), 2)
	await harness._type("19mm\n")
	await harness._wait_confirm()
	var auto_b := harness.id("b1")
	harness._ok("subsequent 19mm in same model converts to 19 mm without flipping units back",
		m.measure.units == "in-frac:1/16" and harness._bbox(auto_b).size() == 6
		and is_equal_approx(harness._bbox(auto_b)[5], 19.0), [m.measure.units, harness._bbox(auto_b)])

	# 5d. Reopen after auto-adoption restores the adopted unit and stays locked.
	m.switch_model(saved_model, false)
	await _until(func(): return m.opened)
	m.switch_model(model_auto, false)
	await _until(func(): return m.opened)
	harness._ok("reopening auto-adopted model restores in-frac:1/16 and locks units_explicit",
		m.measure.units == "in-frac:1/16" and m.measure.units_explicit, [m.measure.units, m.measure.units_explicit])

	# 5e. Model already has saved ShopSketchUnits (mm:0.1): typing 4", 5" converts without flipping units.
	var model_saved_mm := m.out_dir.path_join("quick_units_saved_mm.FCStd")
	m.switch_model(model_saved_mm, true)
	await _until(func(): return m.opened)
	m.set_units("mm:0.1")
	await _until(func(): return not m.measure.units_dirty and m.saved_rev >= m.pending_rev)
	m.switch_model(saved_model, false)
	await _until(func(): return m.opened)
	m.switch_model(model_saved_mm, false)
	await _until(func(): return m.opened)
	await harness._view(Vector3(100, 100, 0), -30, -50, 1.2)
	m.set_tool("rect")
	await harness._drag_to(Vector3(0, 0, 0), 2); await harness._press()
	await harness._drag_to(Vector3(80, 80, 0), 2)
	await harness._type("4\", 5\"\n")
	await harness._wait_confirm()
	var mm_rect: Dictionary = m.ops.back()
	harness._ok("model with saved mm:0.1 converts 4\", 5\" without flipping document units",
		m.measure.units == "mm:0.1" and m.measure.units_explicit
		and mm_rect["type"] == "rect" and is_equal_approx(float(mm_rect["size"][0]), 101.6)
		and is_equal_approx(float(mm_rect["size"][1]), 127.0), [m.measure.units, mm_rect])

	# 5f. Manual Units menu pick on a new model locks units so typing 50mm afterward converts without flipping.
	var model_menu := m.out_dir.path_join("quick_units_menu_lock.FCStd")
	m.switch_model(model_menu, true)
	await _until(func(): return m.opened)
	await harness._view(Vector3(100, 100, 0), -30, -50, 1.2)
	m.menus.on_units_menu("format:in-dec")
	await _until(func(): return not m.measure.units_dirty and m.saved_rev >= m.pending_rev)
	m.set_tool("line")
	await harness._drag_to(Vector3(0, 0, 0), 2); await harness._press()
	await harness._drag_to(Vector3(80, 0, 0), 2)
	await harness._type("50mm\n")
	await harness._wait_confirm()
	harness._ok("manual Units menu pick locks units so subsequent 50mm does not flip them",
		m.measure.units == "in-dec:0.01" and m.measure.units_explicit, [m.measure.units, m.measure.units_explicit])

	# 5g. FreeCAD-evaluated expression on unset model (declined locally -> worker evaluates) adopts ft-in:1/16.
	var model_fc := m.out_dir.path_join("quick_units_freecad_eval.FCStd")
	m.switch_model(model_fc, true)
	await _until(func(): return m.opened)
	await harness._view(Vector3(100, 100, 0), -30, -50, 1.2)
	m.set_tool("line")
	await harness._drag_to(Vector3(0, 0, 0), 2); await harness._press()
	await harness._drag_to(Vector3(80, 0, 0), 2)
	await harness._type("1ft^1\n")
	await _until(func(): return m.length_pending.is_empty())
	await harness._wait_confirm()
	await _until(func(): return not m.measure.units_dirty and m.saved_rev >= m.pending_rev)
	harness._ok("FreeCAD-evaluated expression on unset model adopts ft-in:1/16 once accepted",
		m.measure.units == "ft-in:1/16" and m.measure.units_explicit, [m.measure.units, m.measure.units_explicit])

	# Clean up test settings and return to mm for any section running after us in the lane.
	m.measure.settings_path = ""
	DirAccess.remove_absolute(tmp_cfg)
	m.set_units(Units.TEST_SPEC)
	await _until(func(): return not m.measure.units_dirty)
