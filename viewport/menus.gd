extends RefCounted
## The native menu bar and menu command dispatch (T113). Main and its controllers own the actions.
##
## Builds application, File, Edit, Tools (from tool_registry), View, Units and Wood menus; keeps RIDs and check marks;
## drops duplicate commands arriving via both menu shortcut and window key; shows New/Open dialogs.
## Entry points: make_menus, run, update_menu_checks, update_units_menu, build_materials_menu, update_wood_checks.

const Units := preload("res://units.gd")

var m                                     # main.gd: tool registry, window and model commands


func _init(main) -> void:
	m = main


# menus: tag -> action. Menu shortcuts and the same keys in the window may both arrive: act once.
var menu_last := {}
var menus := {}                    # name -> menu RID (for check marks)


func make_menus() -> void:
	if not NativeMenu.has_feature(NativeMenu.FEATURE_GLOBAL_MENU): return
	if NativeMenu.has_system_menu(NativeMenu.APPLICATION_MENU_ID):
		var app_menu := NativeMenu.get_system_menu(NativeMenu.APPLICATION_MENU_ID)
		if app_menu.is_valid():
			NativeMenu.add_item(app_menu, "Preferences…", run, Callable(), "preferences", m.PREFERENCES_KEY)
	var main_menu := NativeMenu.get_system_menu(NativeMenu.MAIN_MENU_ID)
	var spec := [
		["File", [["New Window", "newwindow", KEY_MASK_META | KEY_MASK_SHIFT | KEY_N], ["New…", "new", KEY_MASK_META | KEY_N],
				  ["Open…", "open", KEY_MASK_META | KEY_O], [],
				  ["Show in Finder", "reveal", 0], [], ["Drawing and cut list (D)", "drawing", 0]]],
		["Edit", [["Undo", "undo", KEY_MASK_META | KEY_Z], ["Redo", "redo", KEY_MASK_META | KEY_MASK_SHIFT | KEY_Z], [], ["Make assembly", "assemble", KEY_MASK_META | KEY_G],
				  ["Delete (⌫)", "delete", 0], ["Make unique (U)", "unique", 0], ["Detach from array", "detach", 0], [],
				  ["Hide (H)", "hide", 0], ["Unhide selected", "unhide_selected", 0], ["Unhide last", "unhide_last", 0],
				  ["Unhide all (Shift+H)", "unhide_all", 0]]],
		["Tools", m.tool_list.map(func(t): return [load("res://tool_registry.gd").menu_label(t), t["id"], 0])],
		["View", [["Grid snap (G)", "grid", -1], ["New board on faces (B)", "newboard", -1], ["Hidden geometry", "hiddengeom", -1]]],
	]
	for group in spec:
		var rid := NativeMenu.create_menu()
		menus[group[0]] = rid
		for it in group[1]:
			if it.is_empty():
				NativeMenu.add_separator(rid)
			elif it[2] == -1:
				NativeMenu.add_check_item(rid, it[0], run, Callable(), it[1])
			else:
				NativeMenu.add_item(rid, it[0], run, Callable(), it[1], it[2])
		NativeMenu.add_submenu_item(main_menu, group[0], rid)
	update_menu_checks()
	_build_units_menu()


var units_menu_rid := RID()


func _build_units_menu() -> void:
	"""The Units menu (I57): display format and rounding, saved per model."""
	if not NativeMenu.has_feature(NativeMenu.FEATURE_GLOBAL_MENU) or units_menu_rid.is_valid(): return
	var bar := NativeMenu.get_system_menu(NativeMenu.MAIN_MENU_ID)
	units_menu_rid = NativeMenu.create_menu()
	NativeMenu.add_submenu_item(bar, "Units", units_menu_rid)
	update_units_menu()


func update_units_menu() -> void:
	if not units_menu_rid.is_valid(): return
	NativeMenu.clear(units_menu_rid)
	var cur := Units.parse_spec(m.measure.units)
	var fmt: String = cur["format"] if cur.ok else "in-frac"
	var prec: String = cur["precision"] if cur.ok else "1/16"
	for f in Units.FORMAT_ORDER:
		if f == "m": NativeMenu.add_separator(units_menu_rid)
		var i := NativeMenu.add_radio_check_item(units_menu_rid, Units.FORMATS[f]["label"], on_units_menu, Callable(), "format:" + f)
		NativeMenu.set_item_checked(units_menu_rid, i, f == fmt)
	NativeMenu.add_separator(units_menu_rid)
	var hdr := NativeMenu.add_item(units_menu_rid, "Rounding")
	NativeMenu.set_item_disabled(units_menu_rid, hdr, true)
	for p in Units.FORMATS[fmt]["precisions"]:
		var i := NativeMenu.add_radio_check_item(units_menu_rid, Units.precision_label(fmt, p), on_units_menu, Callable(), "prec:" + p)
		NativeMenu.set_item_checked(units_menu_rid, i, p == prec)


func on_units_menu(tag) -> void:
	var s := String(tag)
	if s.begins_with("format:"): m.measure.set_format(s.substr(7))
	elif s.begins_with("prec:"): m.measure.set_precision(s.substr(5))


func update_menu_checks() -> void:
	if not menus.has("View"): return
	NativeMenu.set_item_checked(menus["View"], 0, m.grid_snap)
	NativeMenu.set_item_checked(menus["View"], 1, m.new_board)
	NativeMenu.set_item_checked(menus["View"], 2, m.show_hidden)


func run(tag) -> void:
	var now := Time.get_ticks_msec()
	if now - int(menu_last.get(tag, -1000)) < 150: return        # the menu and the key both fired
	menu_last[tag] = now
	if m.tools.has(tag): m.set_tool(tag); return      # a tool's id (tool_registry.gd)
	match tag:
		"preferences": m._open_preferences()
		"newwindow": m.new_window()
		"new": _file_dialog(true)
		"open": _file_dialog(false)
		"reveal": OS.shell_show_in_file_manager(m.model_path)
		"drawing": m.export_drawing()
		"undo": m.undo()
		"redo": m.redo()
		"assemble": m.sel.make_assembly()
		"unique": m.sel.linked_op("make_unique")
		"detach": m.sel.linked_op("detach")
		"delete": m.tools[m.tool].reset(); m.sel.delete_selected()
		"hide": m.sel.hide_selected()
		"unhide_selected": m.sel.unhide("selected")
		"unhide_last": m.sel.unhide("last")
		"unhide_all": m.sel.unhide("all")
		"hiddengeom": m.sel.toggle_hidden_geometry()
		"grid": m.grid_snap = not m.grid_snap; m.ui.update_toggles()
		"newboard": m.new_board = not m.new_board; m.ui.update_toggles()


func build_materials_menu() -> void:
	"""The Wood menu: pick what Paint puts on (picking one switches to Paint)."""
	if not NativeMenu.has_feature(NativeMenu.FEATURE_GLOBAL_MENU) or _wood_menu_rid.is_valid(): return
	var bar := NativeMenu.get_system_menu(NativeMenu.MAIN_MENU_ID)
	_wood_menu_rid = NativeMenu.create_menu()
	for k in m.appearance.wood_keys:
		var i := NativeMenu.add_radio_check_item(_wood_menu_rid, m.appearance.wood_library[k]["name"], _on_wood_menu, Callable(), k)
		NativeMenu.set_item_checked(_wood_menu_rid, i, k == m.appearance.paint_material)
	NativeMenu.add_separator(_wood_menu_rid)
	NativeMenu.add_item(_wood_menu_rid, "Turn grain 90° (T)", _on_wood_menu, Callable(), "turn")
	NativeMenu.add_submenu_item(bar, "Wood", _wood_menu_rid)


var _wood_menu_rid := RID()


func _on_wood_menu(tag) -> void:
	if tag == "turn":
		m.appearance.turn_grain(m.hover_body); return
	m.appearance.set_paint_material(String(tag))


func update_wood_checks(k: String) -> void:
	if _wood_menu_rid.is_valid():
		for i in NativeMenu.get_item_count(_wood_menu_rid):
			NativeMenu.set_item_checked(_wood_menu_rid, i, NativeMenu.get_item_tag(_wood_menu_rid, i) == k)


const DRAWINGS := "04_Napkin_Drawings"   # William's own models (I78): New and Open start here


static func dialog_start(model_path: String) -> String:
	"""Where New and Open start: 04_Napkin_Drawings/ beside the app's models/ working folder, else the model's own folder."""
	var dir := model_path.get_base_dir()
	if dir.get_file() == "models":
		var drawings := dir.get_base_dir().path_join(DRAWINGS)
		if DirAccess.dir_exists_absolute(drawings): return drawings
	return dir


func _file_dialog(new: bool) -> void:
	var start: String = dialog_start(m.model_path)
	var name := "Untitled.FCStd" if new else ""
	var filters := PackedStringArray(["*.FCStd ; FreeCAD model"])
	var mode := DisplayServer.FILE_DIALOG_MODE_SAVE_FILE if new else DisplayServer.FILE_DIALOG_MODE_OPEN_FILE
	var done := func(ok: bool, paths: PackedStringArray, _filter: int) -> void:
		if ok and not paths.is_empty(): m.switch_model(paths[0], new)
	if DisplayServer.has_feature(DisplayServer.FEATURE_NATIVE_DIALOG_FILE):
		DisplayServer.file_dialog_show("New model" if new else "Open a model", start, name, false, mode, filters, done)
	else:
		var fd := FileDialog.new()
		fd.access = FileDialog.ACCESS_FILESYSTEM
		fd.file_mode = FileDialog.FILE_MODE_SAVE_FILE if new else FileDialog.FILE_MODE_OPEN_FILE
		fd.filters = filters
		fd.current_dir = start
		fd.file_selected.connect(func(p: String) -> void: m.switch_model(p, new); fd.queue_free())
		m.add_child(fd)
		fd.popup_centered_ratio(0.6)
