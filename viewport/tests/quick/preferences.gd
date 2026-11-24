extends RefCounted
## Preferences wired in (T111 step 2, I63, I62): live tunables, test-mode guard, 0.5 s watch timer,
## status bar messages, bad file at start / mid-run / deleted, mid-gesture update, default units on File > New,
## and Shop Sketch > Preferences… (⌘,) in NativeMenu.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
const Inference := preload("res://inference.gd")
const Tool := preload("res://tools/tool.gd")
const CameraRig := preload("res://camera_rig.gd")
const Preferences := preload("res://preferences.gd")
const Units := preload("res://units.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func _write(path: String, text: String) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	assert(f != null, "failed to write preferences test file: " + path)
	f.store_string(text)
	f.close()


func _until(cond: Callable, ms := 5000) -> bool:
	var t0 := Time.get_ticks_msec()
	while not cond.call() and Time.get_ticks_msec() - t0 < ms:
		await harness._frames(1)
	return cond.call()


func run() -> void:
	await harness._fresh("preferences", [], true)
	await harness._view(Vector3(100, 75, 0), -30, -50, 1.4)

	# 1. Each live value equals its built-in constant at start.
	harness._ok("all 9 live values equal their constants at start",
		is_equal_approx(Inference.grid, Inference.GRID)
		and is_equal_approx(Inference.snap_px, Inference.SNAP_PX)
		and is_equal_approx(Inference.edge_px, Inference.EDGE_PX)
		and is_equal_approx(Inference.infer_deg, Inference.INFER_DEG)
		and is_equal_approx(Inference.release_deg, Inference.RELEASE_DEG)
		and is_equal_approx(Tool.drag_px, Tool.DRAG_PX)
		and Tool.hold_ms == Tool.HOLD_MS
		and is_equal_approx(m.camera_rig.trackpad_px, CameraRig.TRACKPAD_PX)
		and is_equal_approx(m.camera_rig.zoom_step, CameraRig.ZOOM_STEP)
		and is_equal_approx(m.tool_ctx.pick.grid_step(), Inference.GRID)
		and is_equal_approx(m.tool_ctx.pick.snap_radius(), Inference.SNAP_PX))

	# 2. Test mode never reads preferences.json (startup path is skipped).
	var skip_path := m.out_dir.path_join("test_mode_skip_preferences.json")
	_write(skip_path, "{\"tuning\": {\"SNAP_PX\": 30}}\n")
	m.preferences_path = skip_path
	m._init_preferences()
	harness._ok("test mode skips startup preferences load even when file has SNAP_PX 30",
		m._prefs_timer == null and not m.prefs._has_disk_state
		and is_equal_approx(Inference.snap_px, Inference.SNAP_PX),
		[m._prefs_timer, m.prefs._has_disk_state, Inference.snap_px])
	DirAccess.remove_absolute(skip_path)

	# 3. _apply_preferences sets each of the nine live values, pick.grid_step/snap_radius, and default units.
	m._apply_preferences({
		"units": {"default": "cm:0.1"},
		"tuning": {
			"SNAP_PX": 22.0,
			"EDGE_PX": 11.0,
			"INFER_DEG": 10.0,
			"RELEASE_DEG": 16.0,
			"DRAG_PX": 9.0,
			"HOLD_MS": 450,
			"TRACKPAD_PX": 66.0,
			"ZOOM_STEP": 0.90,
			"GRID": 25.0,
		},
	})
	harness._ok("_apply_preferences sets all 9 live values, pick capability and default units",
		is_equal_approx(Inference.snap_px, 22.0)
		and is_equal_approx(Inference.edge_px, 11.0)
		and is_equal_approx(Inference.infer_deg, 10.0)
		and is_equal_approx(Inference.release_deg, 16.0)
		and is_equal_approx(Tool.drag_px, 9.0)
		and Tool.hold_ms == 450
		and is_equal_approx(m.camera_rig.trackpad_px, 66.0)
		and is_equal_approx(m.camera_rig.zoom_step, 0.90)
		and is_equal_approx(Inference.grid, 25.0)
		and is_equal_approx(m.tool_ctx.pick.grid_step(), 25.0)
		and is_equal_approx(m.tool_ctx.pick.snap_radius(), 22.0)
		and m.measure.pref_default_units == "cm:0.1")

	# Live trackpad_px and zoom_step drive input directly.
	var y0: float = m.camera_rig.yaw
	var pan := InputEventPanGesture.new()
	pan.delta = Vector2(100.0 / 66.0, 0.0)
	await harness._gesture(pan)
	var d0: float = m.camera_rig.dist
	var wh := InputEventMouseButton.new()
	wh.button_index = MOUSE_BUTTON_WHEEL_UP
	wh.pressed = true
	wh.factor = 1.0
	wh.position = m.cursor2d.position
	m._unhandled_input(wh)
	harness._ok("live trackpad_px and zoom_step drive orbit and wheel zoom",
		is_equal_approx(m.camera_rig.yaw, y0 - 0.8) and is_equal_approx(m.camera_rig.dist, d0 * 0.90),
		[m.camera_rig.yaw - y0, m.camera_rig.dist / d0])
	m._apply_preferences(Preferences.DEFAULTS)
	await harness._view(Vector3(100, 75, 0), -30, -50, 1.4)

	# 4. Bad file at start: built-ins hold and the status line says the problem.
	var pref_path := m.out_dir.path_join("quick_preferences.json")
	_write(pref_path, "{\"tuning\": {\"SNAP_PX\": ")
	m.prefs = Preferences.new()
	m.preferences_path = pref_path
	m._start_preferences()
	harness._ok("bad file at start keeps built-ins and reports problem in status line",
		is_equal_approx(Inference.snap_px, Inference.SNAP_PX)
		and m.ui_sync.text.begins_with("preferences.json isn't readable ("),
		[Inference.snap_px, m.ui_sync.text])

	# 5. Live save picked up by 0.5 s timer: applies values and updates status line.
	_write(pref_path, "{\"tuning\": {\"SNAP_PX\": 18, \"ZOOM_STEP\": 0.9}}\n")
	await _until(func(): return is_equal_approx(Inference.snap_px, 18.0))
	harness._ok("live edit applies SNAP_PX and ZOOM_STEP via timer and reports them",
		is_equal_approx(Inference.snap_px, 18.0)
		and is_equal_approx(m.tool_ctx.pick.snap_radius(), 18.0)
		and is_equal_approx(m.camera_rig.zoom_step, 0.9)
		and m.ui_sync.text == "Preferences: SNAP_PX 18, ZOOM_STEP 0.9",
		[Inference.snap_px, m.camera_rig.zoom_step, m.ui_sync.text])

	# 6. Bad edit after a good one: last good values stay (not built-ins), status line says problem.
	_write(pref_path, "{broken json")
	await _until(func(): return m.ui_sync.text.begins_with("preferences.json isn't readable ("))
	harness._ok("bad edit after good keeps last good values (not built-ins) and reports problem",
		is_equal_approx(Inference.snap_px, 18.0)
		and is_equal_approx(m.camera_rig.zoom_step, 0.9)
		and m.ui_sync.text.begins_with("preferences.json isn't readable ("),
		[Inference.snap_px, m.camera_rig.zoom_step, m.ui_sync.text])

	# Multiple problems report the first plus "(and N more)".
	_write(pref_path, "{\"bogus\": 1, \"tuning\": {\"SNAP_PX\": 999}}\n")
	await _until(func(): return m.ui_sync.text.ends_with(" (and 1 more)"))
	harness._ok("multiple problems show first plus (and N more) and keep last good SNAP_PX",
		m.ui_sync.text.begins_with("preferences.json: ")
		and m.ui_sync.text.ends_with(" (and 1 more)")
		and is_equal_approx(Inference.snap_px, 18.0),
		[m.ui_sync.text, Inference.snap_px])

	# 7. Deleting the file while running keeps last good values and says nothing.
	m.ui_sync.text = "unchanged"
	DirAccess.remove_absolute(pref_path)
	await m._prefs_timer.timeout
	await m._prefs_timer.timeout
	harness._ok("deleting file while running keeps last good values and says nothing",
		is_equal_approx(Inference.snap_px, 18.0) and m.ui_sync.text == "unchanged",
		[Inference.snap_px, m.ui_sync.text])

	# 8. Change while a gesture is under way: change DRAG_PX between press and release; action completes.
	_write(pref_path, "{\"tuning\": {\"DRAG_PX\": 6}}\n")
	await _until(func(): return is_equal_approx(Tool.drag_px, 6.0))
	m.set_tool("rect")
	var n := m.ops.size()
	await harness._drag_to(Vector3(0, 0, 0), 2)
	await harness._button(true)
	_write(pref_path, "{\"tuning\": {\"DRAG_PX\": 20}}\n")
	await _until(func(): return is_equal_approx(Tool.drag_px, 20.0))
	await harness._drag_to(Vector3(200, 150, 0), 2)
	await harness._button(false)
	await harness._wait_confirm()
	harness._ok("changing DRAG_PX mid-gesture applies at once and the action completes cleanly",
		is_equal_approx(Tool.drag_px, 20.0)
		and m.ops.size() == n + 1
		and m.ops.back()["type"] == "rect"
		and not m.tools["rect"].busy(),
		[Tool.drag_px, m.ops.size() - n, m.tools["rect"].busy()])

	# 9. Default units changed while a model is open: open model keeps its units; File > New opens in new default.
	m.set_units(Units.TEST_SPEC)
	await _until(func(): return not m.measure.units_dirty)
	_write(pref_path, "{\"units\": {\"default\": \"in-dec:0.01\"}, \"tuning\": {\"DRAG_PX\": 20}}\n")
	await _until(func(): return m.measure.pref_default_units == "in-dec:0.01")
	harness._ok("changing default units reports status and leaves open model's units alone",
		m.ui_sync.text == "Preferences: default units in-dec:0.01" and m.measure.units == Units.TEST_SPEC,
		[m.ui_sync.text, m.measure.units])
	var new_model := m.out_dir.path_join("quick_prefs_new.FCStd")
	m.switch_model(new_model, true)
	await _until(func(): return m.opened)
	await _until(func(): return not m.measure.units_dirty)
	harness._ok("File > New model opens in the preference's default units",
		m.measure.units == "in-dec:0.01", m.measure.units)

	# 10. Shop Sketch > Preferences… menu item exists with ⌘, (where global menu is supported).
	# Note: Godot 4.6's macOS get_item_accelerator() maps keyEquivalent "," via find_keycode_from_string(","),
	# which returns 0 (KEY_NONE) for punctuation while preserving KEY_MASK_META; check both the registered item
	# and the accelerator constant passed to NativeMenu.add_item.
	if NativeMenu.has_feature(NativeMenu.FEATURE_GLOBAL_MENU) and NativeMenu.has_system_menu(NativeMenu.APPLICATION_MENU_ID):
		var app_menu := NativeMenu.get_system_menu(NativeMenu.APPLICATION_MENU_ID)
		var found := false
		var detail := []
		for i in NativeMenu.get_item_count(app_menu):
			if NativeMenu.get_item_tag(app_menu, i) == "preferences":
				var label := NativeMenu.get_item_text(app_menu, i)
				var accel := NativeMenu.get_item_accelerator(app_menu, i)
				detail = [label, accel, Main.PREFERENCES_KEY]
				found = label == "Preferences…" \
					and Main.PREFERENCES_KEY == (KEY_MASK_META | KEY_COMMA) \
					and (accel == (KEY_MASK_META | KEY_COMMA) or accel == KEY_MASK_META)
				break
		harness._ok("Shop Sketch > Preferences… exists in application menu with ⌘,", found, detail)
	else:
		harness._ok("Shop Sketch > Preferences… menu check (SKIP: no global menu)", true)

	# Cleanup: stop poll timer, remove temp file, restore built-in defaults and test units for any later section.
	if m._prefs_timer != null:
		m._prefs_timer.stop()
		m._prefs_timer.queue_free()
		m._prefs_timer = null
	DirAccess.remove_absolute(pref_path)
	m.prefs = Preferences.new()
	m.preferences_path = Main.PREFERENCES_PATH
	m._apply_preferences(Preferences.DEFAULTS)
	m.set_units(Units.TEST_SPEC)
	await _until(func(): return not m.measure.units_dirty)
