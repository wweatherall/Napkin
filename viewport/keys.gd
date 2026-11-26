extends Node
## The keyboard (T75): tool keys (each tool declares its own, tool_registry.gd), shortcuts, Esc, Enter, Delete / Backspace, typed values, Tab / ⌥ for Push/Pull.
## `m.keys`. main.gd's `_input` and `_unhandled_input` stay the entry points (tests call `m._unhandled_input`); they
## hand key presses here, after what comes first for every event (a press drops a length FreeCAD is still working
## out; Esc while Properties picks a face cancels the pick). The mouse stays in main.gd.

var m                               # main.gd: tools, tool, measure, sel, set_tool, _menu, ...


func before_gui(e: InputEvent) -> bool:
	"""Push/Pull into a face (I40): Tab switches the face, Option the end condition. Before the GUI, which takes
	Tab. True when the tool used the key."""
	return e is InputEventKey and e.pressed and not e.echo and e.keycode in [KEY_TAB, KEY_ALT] and m.tool == "push" \
			and m.tools.has(m.tool) and m.tools[m.tool].key(e)


func press(e: InputEventKey) -> void:
	"""A key press the GUI didn't take (not an echo)."""
	var cmd: bool = e.ctrl_pressed or e.meta_pressed
	if cmd and e.shift_pressed and e.keycode == KEY_Z: m.menus.run("redo"); return    # Shift+Cmd+Z
	if cmd and e.keycode == KEY_Z: m.menus.run("undo"); return    # Cmd+Z on a Mac
	if cmd and e.shift_pressed and e.keycode == KEY_N: m.menus.run("newwindow"); return
	if cmd and e.keycode == KEY_N: m.menus.run("new"); return
	if cmd and e.keycode == KEY_G: m.menus.run("assemble"); return
	if cmd and e.keycode == KEY_O: m.menus.run("open"); return
	var box = m.measure
	match e.keycode:
		KEY_ESCAPE:                        # the gesture first, then the selection, then the assembly you're in (T31)
			if m.tools[m.tool].in_gesture() or box.vcb != "": m.set_tool(m.tool)
			elif not m.selection.is_empty(): m.sel.set_selection([])
			elif m.context != "": m.sel.leave_context()
			else: m.set_tool(m.tool)
			return
		KEY_ENTER, KEY_KP_ENTER: box.apply(); return
		KEY_DELETE, KEY_BACKSPACE:              # in the measurements box they edit it; otherwise they delete (I48)
			if box.vcb != "": box.backspace()
			elif box.typing: pass                     # emptied the box: the next press doesn't delete boards
			elif m.tool == "move" and m.tools["move"].in_gesture():
				var grabbed: Dictionary = m.tools["move"].state       # mid-move: what's being moved goes
				if grabbed.get("cut", {}).is_empty():                 # (a hole being moved: deleting holes isn't built)
					var ids: Array = grabbed.get("unit", {}).get("bodies", [grabbed.get("body", "")])
					m.set_tool("move"); m.sel.set_selection(ids); m.sel.delete_selected()
			else: m.menus.run("delete")
			return
	var ch := char(e.unicode) if e.unicode > 0 else ""
	var t = m.tools[m.tool]
	if not (box.vcb != "" and e.keycode == KEY_SHIFT) and t.key(e): return   # the tool's own keys (Move: modifiers, axis locks); while typing, Shift is for " and '
	if t.busy() and ch != "" and t.accepts(ch):
		box.type_char(ch); return
	# Only a tool with accepts_idle takes characters before a gesture (Polygon's `8s`).
	if not t.busy() and not cmd and ch != "" and t.has_method("accepts_idle") and t.accepts_idle(ch, box.vcb):
		box.type_char(ch); return
	if m.tool_keys.has(e.keycode): m.set_tool(m.tool_keys[e.keycode]); return   # each tool's own key (its TOOL)
	match e.keycode:
		KEY_G: m.menus.run("grid")
		KEY_B: m.menus.run("newboard")
		KEY_D: m.export_drawing()
		KEY_U: m.menus.run("unique")
		KEY_H: m.menus.run("unhide_all" if e.shift_pressed else "hide")
		KEY_T: m.appearance.turn_grain(m.hover_body)
