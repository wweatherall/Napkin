extends RefCounted
## The tool registry (tool_registry.gd): the toolbar, the Tools menu and the tool keys come from each tool's TOOL.
## Pins what William sees: these nine tools, in this order, with these tooltips and keys.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m

const WANT := [
	["select", "Select (Space)", "Select (Space)", KEY_SPACE],
	["paint", "Paint", "Paint (pick the wood in the Wood menu)", KEY_NONE],
	["rect", "Rectangle (R)", "Rectangle (R)", KEY_R],
	["circle", "Circle (C)", "Circle (C)", KEY_C],
	["polygon", "Polygon", "Polygon", KEY_NONE],
	["line", "Line (L)", "Line (L)", KEY_L],
	["arc", "Arc (A)", "Arc (A)", KEY_A],
	["push", "Push/Pull (P)", "Push/Pull (P)", KEY_P],
	["move", "Move (M)", "Move (M)", KEY_M],
]


func run() -> void:
	await harness._fresh("registry")
	# the toolbar's segments, left to right: [id, label, tooltip]
	var bar: Array = []
	var row: Node = m.ui.tool_buttons.values()[0].get_parent() if not m.ui.tool_buttons.is_empty() else null
	if row != null:
		for b in row.get_children():
			for id in m.ui.tool_buttons:
				if m.ui.tool_buttons[id] == b: bar.append([id, b.text, b.tooltip_text])
	var want_bar: Array = WANT.map(func(w): return [w[0], w[1], w[2]])
	harness._ok("the toolbar is Select, Paint, Rectangle, Circle, Polygon, Line, Arc, Push/Pull, Move with their tooltips", bar == want_bar, bar)
	var registry := preload("res://tool_registry.gd")
	var labels: Array = m.tool_list.map(func(t): return [t["id"], registry.menu_label(t)])
	harness._ok("every toolbar tool button shows its registry menu label", bar.map(func(b): return [b[0], b[1]]) == labels, bar)
	if row == null: return
	var toolbar: HBoxContainer = row.get_parent().get_parent()
	var fixed: Array = toolbar.find_children("*", "Button", true, false).filter(func(b): return b.get_parent() != row)
	var fixed_labels: Array = fixed.map(func(b): return b.text)
	harness._ok("the fixed toolbar buttons show their shortcuts", fixed_labels == [
		"Undo (⌘Z)", "Redo (⇧⌘Z)", "Drawing (D)", "Grid snap (G)", "New board (B)", "Properties"], fixed_labels)
	var toolbar_width: float = toolbar.get_parent().get_combined_minimum_size().x
	harness._ok("the whole toolbar fits at 1280 pixels", toolbar_width <= 1280, toolbar_width)
	var menu: Array = []
	if NativeMenu.has_feature(NativeMenu.FEATURE_GLOBAL_MENU):
		var tools_menu: RID = m.menus.menus["Tools"]
		for i in NativeMenu.get_item_count(tools_menu):
			menu.append([NativeMenu.get_item_tag(tools_menu, i), NativeMenu.get_item_text(tools_menu, i)])
	else:
		menu = labels
	harness._ok("the Tools menu names them the same way", menu == WANT.map(func(w): return [w[0], w[1]]), menu)
	harness._ok("the declared tools have no problems (fields, repeated ids or keys)", registry.problems(m.tool_list).is_empty(), registry.problems(m.tool_list))
	# each tool key picks its tool; Paint has none
	var picked: Array = []
	for w in WANT:
		if w[3] == KEY_NONE: continue
		m.set_tool("paint")
		await harness._key(w[3])
		picked.append([OS.get_keycode_string(w[3]), m.tool])
	harness._ok("Space, R, C, L, A, P and M pick Select, Rectangle, Circle, Line, Arc, Push/Pull and Move", picked == [["Space", "select"], ["R", "rect"], ["C", "circle"], ["L", "line"], ["A", "arc"], ["P", "push"], ["M", "move"]], picked)
	harness._ok("the keys map only those seven", m.tool_keys == {KEY_SPACE: "select", KEY_R: "rect", KEY_C: "circle", KEY_L: "line", KEY_A: "arc", KEY_P: "push", KEY_M: "move"}, m.tool_keys)
	# a toolbar segment and a Tools menu item pick their tool (the menu's tag is the tool's id)
	m.ui.tool_buttons["move"].pressed.emit()
	var by_button := m.tool
	m.menus.menu_last.clear()
	m.menus.run("push")
	harness._ok("the toolbar and the Tools menu pick tools by id", [by_button, m.tool] == ["move", "push"] and m.ui.tool_buttons["push"].button_pressed, [by_button, m.tool])
	m.set_tool("rect")
