extends RefCounted
## The viewport interface (T24: Mac-like).
# System font, macOS colours (light or dark, your accent colour), a segmented control for the tools,
# push buttons, a quiet status bar and a measurements field that lights up while you type.
const Units := preload("res://units.gd")

var m                                # main.gd: scene, document, tool registry and commands
var dark := false
var accent := Color(0.0, 0.48, 1.0)
var tool_buttons := {}
var _toggle_buttons := {}


func _init(main) -> void:
	m = main


func update_saved() -> void:
	if m.ui_saved == null: return
	if m.doc.save_error != "":            # stays until a save lands (I54); the worker retries on the next change
		m.ui_saved.text = "Couldn't save: %s" % m.doc.save_error
		m.ui_saved.add_theme_color_override("font_color", Color(0.75, 0.1, 0.1))
	elif m.doc.recovered_note != "" and m.pending_rev <= m.saved_rev:     # until the next save lands (A32)
		m.ui_saved.text = m.doc.recovered_note
		m.ui_saved.remove_theme_color_override("font_color")
	else:
		m.ui_saved.text = "Saving…" if m.pending_rev > m.saved_rev else "Saved"
		m.ui_saved.remove_theme_color_override("font_color")
	if m.test_mode and (m.saved_shown.is_empty() or m.saved_shown.back() != m.ui_saved.text): m.saved_shown.append(m.ui_saved.text)


func c(light: Color, dark_c: Color) -> Color:
	return dark_c if dark else light


func box(bg: Color, radius := 6, border := Color(0, 0, 0, 0), bw := 0, pad := Vector2(10, 4)) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.set_corner_radius_all(radius)
	if bw > 0:
		s.border_color = border
		s.set_border_width_all(bw)
	s.content_margin_left = pad.x; s.content_margin_right = pad.x
	s.content_margin_top = pad.y; s.content_margin_bottom = pad.y
	s.anti_aliasing = true
	return s


func _make_theme() -> Theme:
	var t := Theme.new()
	var f := SystemFont.new()
	f.font_names = PackedStringArray([".AppleSystemUIFont", "SF Pro Text", "Helvetica Neue", "Arial"])
	t.default_font = f
	t.default_font_size = 13
	var text := c(Color(0.11, 0.11, 0.12), Color(0.92, 0.92, 0.93))
	t.set_color("font_color", "Label", text)
	for st in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_focus_color"]:
		t.set_color(st, "Button", text)
	# push buttons
	var edge := c(Color(0.77, 0.77, 0.79), Color(0.36, 0.36, 0.38))
	t.set_stylebox("normal", "Button", box(c(Color(1, 1, 1), Color(0.36, 0.36, 0.38)), 6, edge, 1, Vector2(12, 3)))
	t.set_stylebox("hover", "Button", box(c(Color(0.97, 0.97, 0.98), Color(0.4, 0.4, 0.42)), 6, edge, 1, Vector2(12, 3)))
	t.set_stylebox("pressed", "Button", box(c(Color(0.86, 0.86, 0.88), Color(0.46, 0.46, 0.48)), 6, edge, 1, Vector2(12, 3)))
	t.set_stylebox("hover_pressed", "Button", t.get_stylebox("pressed", "Button"))
	t.set_stylebox("focus", "Button", StyleBoxEmpty.new())
	# segments: flat inside a grey track; the selected one is a raised white tile
	t.set_type_variation("Segment", "Button")
	var flat := box(Color(0, 0, 0, 0), 5, Color(0, 0, 0, 0), 0, Vector2(11, 3))
	var hov := box(c(Color(0, 0, 0, 0.05), Color(1, 1, 1, 0.06)), 5, Color(0, 0, 0, 0), 0, Vector2(11, 3))
	var sel := box(c(Color(1, 1, 1), Color(0.43, 0.43, 0.46)), 5, Color(0, 0, 0, 0), 0, Vector2(11, 3))
	sel.shadow_color = Color(0, 0, 0, 0.18); sel.shadow_size = 2; sel.shadow_offset = Vector2(0, 1)
	t.set_stylebox("normal", "Segment", flat)
	t.set_stylebox("hover", "Segment", hov)
	t.set_stylebox("pressed", "Segment", sel)
	t.set_stylebox("hover_pressed", "Segment", sel)
	t.set_stylebox("focus", "Segment", StyleBoxEmpty.new())
	t.set_type_variation("Quiet", "Label")
	t.set_color("font_color", "Quiet", c(Color(0.43, 0.43, 0.45), Color(0.62, 0.62, 0.65)))
	t.set_font_size("font_size", "Quiet", 11)
	return t


func _segments(items: Array, toggles: bool) -> PanelContainer:
	var track := PanelContainer.new()
	track.add_theme_stylebox_override("panel", box(c(Color(0.86, 0.86, 0.88), Color(0.24, 0.24, 0.26)), 7, Color(0, 0, 0, 0), 0, Vector2(2, 2)))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 2)
	track.add_child(row)
	var group := ButtonGroup.new()
	for it in items:
		var b := Button.new()
		b.text = it[0]; b.tooltip_text = it[2]
		b.theme_type_variation = "Segment"
		b.toggle_mode = true
		b.focus_mode = Control.FOCUS_NONE
		if not toggles: b.button_group = group
		b.pressed.connect(m.menus.run.bind(it[1]))
		row.add_child(b)
		(_toggle_buttons if toggles else tool_buttons)[it[1]] = b
	return track


func make_ui() -> void:
	dark = DisplayServer.is_dark_mode_supported() and DisplayServer.is_dark_mode()
	for a in OS.get_cmdline_user_args():
		if a == "--appearance=light": dark = false
		elif a == "--appearance=dark": dark = true
	var ac := DisplayServer.get_accent_color()
	if ac.a > 0.0: accent = ac
	var layer := CanvasLayer.new()
	m.add_child(layer)
	var root := Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = _make_theme()
	layer.add_child(root)
	# toolbar
	var bar := PanelContainer.new()
	bar.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	var bar_style := box(c(Color(0.93, 0.93, 0.94), Color(0.17, 0.17, 0.18)), 0, Color(0, 0, 0, 0), 0, Vector2(10, 7))
	bar_style.border_width_bottom = 1; bar_style.border_color = c(Color(0.8, 0.8, 0.82), Color(0.07, 0.07, 0.08))
	bar.add_theme_stylebox_override("panel", bar_style)
	root.add_child(bar)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	bar.add_child(row)
	row.add_child(_segments(m.tool_list.map(func(t): return [t["label"], t["id"], t["tip"]]), false))   # tool_registry.gd
	for spec in [["Undo", "undo", "Undo (⌘Z)"], ["Redo", "redo", "Redo (⇧⌘Z)"], ["Drawing", "drawing", "Drawing and cut list (D)"]]:
		var b := Button.new(); b.text = spec[0]; b.tooltip_text = spec[2]; b.focus_mode = Control.FOCUS_NONE
		b.pressed.connect(m.menus.run.bind(spec[1]))
		row.add_child(b)
	var gap := Control.new(); gap.size_flags_horizontal = Control.SIZE_EXPAND_FILL; gap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(gap)
	row.add_child(_segments([["Grid snap", "grid", "Snap to a 10 mm grid (G)"], ["New board", "newboard", "Pushing a profile drawn on a face makes a separate board (B)"]], true))
	var properties_button := Button.new()
	properties_button.text = "Properties"
	properties_button.focus_mode = Control.FOCUS_NONE
	properties_button.pressed.connect(func():
		m.properties_panel.visible = not m.properties_panel.visible
		if m.properties_panel.visible: m._request_properties())
	row.add_child(properties_button)
	m.properties_panel = load("res://property_panel.gd").new()
	root.add_child(m.properties_panel)
	m.properties_panel.set_anchors_and_offsets_preset(Control.PRESET_RIGHT_WIDE)
	m.properties_panel.offset_left = -360
	m.properties_panel.offset_right = -10
	m.properties_panel.offset_top = 60
	m.properties_panel.offset_bottom = -45
	m.properties_panel.add_theme_stylebox_override("panel", box(c(Color(0.96, 0.96, 0.97), Color(0.17, 0.17, 0.18)), 8, c(Color(0.7, 0.7, 0.72), Color(0.3, 0.3, 0.32)), 1, Vector2(12, 10)))
	m.properties_panel.hide()
	m.properties_panel.refresh_requested.connect(m._request_properties)
	m.properties_panel.edit_requested.connect(m._edit_property)
	var fit_outline := MeshInstance3D.new()          # the plane-fit preview (I40)
	m.add_child(fit_outline)
	m.properties_panel.preview_changed.connect(func(lines: PackedVector3Array):
		fit_outline.mesh = null
		if not lines.is_empty():
			var outline: MeshInstance3D = m._lines(lines, Color(0.9, 0.4, 0.05))
			fit_outline.mesh = outline.mesh
			outline.free())
	# status bar with the measurements field
	var status := PanelContainer.new()
	status.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	status.grow_vertical = Control.GROW_DIRECTION_BEGIN          # grow up from the bottom edge
	var st_style := box(c(Color(0.95, 0.95, 0.96), Color(0.15, 0.15, 0.16)), 0, Color(0, 0, 0, 0), 0, Vector2(12, 4))
	st_style.border_width_top = 1; st_style.border_color = c(Color(0.82, 0.82, 0.84), Color(0.07, 0.07, 0.08))
	status.add_theme_stylebox_override("panel", st_style)
	root.add_child(status)
	var srow := HBoxContainer.new()
	srow.add_theme_constant_override("separation", 14)
	status.add_child(srow)
	m.ui_hint = Label.new(); m.ui_hint.theme_type_variation = "Quiet"; m.ui_hint.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	m.ui_hint.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS; m.ui_hint.clip_text = true
	m.ui_sync = Label.new(); m.ui_sync.theme_type_variation = "Quiet"; m.ui_sync.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	m.ui_sync.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS; m.ui_sync.clip_text = true
	m.ui_saved = Label.new(); m.ui_saved.theme_type_variation = "Quiet"
	srow.add_child(m.ui_hint); srow.add_child(m.ui_sync); srow.add_child(m.ui_saved)
	m.measure.name = "MeasureBox"
	m.measure.m = m
	m.measure.init_units("" if m.test_mode else m.SETTINGS, Units.TEST_SPEC if m.test_mode else Units.DEFAULT_SPEC)
	m.add_child(m.measure)
	m.measure.build(srow)
	# tooltip by the cursor
	m.ui_tip = Label.new()
	m.ui_tip.add_theme_font_size_override("font_size", 11)
	var tip := box(c(Color(1, 1, 1, 0.97), Color(0.2, 0.2, 0.22, 0.97)), 6, c(Color(0.78, 0.78, 0.8), Color(0.33, 0.33, 0.35)), 1, Vector2(8, 4))
	tip.shadow_color = Color(0, 0, 0, 0.18); tip.shadow_size = 4; tip.shadow_offset = Vector2(0, 2)
	m.ui_tip.add_theme_stylebox_override("normal", tip)
	m.ui_tip.visible = false
	root.add_child(m.ui_tip)
	update_toggles()


func update_toggles() -> void:
	m.menus.update_menu_checks()
	if _toggle_buttons.has("grid"): _toggle_buttons["grid"].set_pressed_no_signal(m.grid_snap)
	if _toggle_buttons.has("newboard"): _toggle_buttons["newboard"].set_pressed_no_signal(m.new_board)
