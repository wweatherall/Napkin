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

	# Clean up test settings and return to mm for any section running after us in the lane.
	m.measure.settings_path = ""
	DirAccess.remove_absolute(tmp_cfg)
	m.set_units(Units.TEST_SPEC)
	await _until(func(): return not m.measure.units_dirty)
