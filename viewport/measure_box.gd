extends Node
## The measurements box (VCB, T75): the typed value at the bottom right, what it's labelled, and where the typed
## text goes. `m.measure`; main.gd forwards the old names (`m.vcb`, `m.typing`, `m.apply_vcb()`, `m._update_vcb()`,
## `m.length_pending`, `m.ui_vcb_box`, ...), so tools and tests don't change.
##
## Typed values: Move's count syntax (`3x`, `/3`) goes to the tool as typed; a length is worked out by units.gd at
## once and handed to the tool in mm; only what it declines waits for a `length` reply from FreeCAD (T32).
## `typing` (I48): once the box is clicked or typed in, Delete / Backspace edit it until a click in the view or a
## new selection.

const Units := preload("res://units.gd")

var m                               # main.gd: tools, tool, ui_sync, client, model_path, seq, styling helpers
var vcb := ""                       # the text typed so far
var typing := false                 # the measurements box has Delete/Backspace: since a click on it or a typed key, until a click in the view (I48)
var length_id := 0
var length_pending := {}            # a length FreeCAD is working out: {id, tool, model, seq, state}

var ui_label: Label                 # what the box measures (the tool's vcb_label)
var ui_box: PanelContainer
var ui_value: Label
var _style: StyleBoxFlat
var _style_typing: StyleBoxFlat


func build(row: Container) -> void:
	"""The label and the box, at the end of the status bar's row."""
	ui_label = Label.new(); ui_label.theme_type_variation = "Quiet"
	ui_box = PanelContainer.new()
	ui_box.custom_minimum_size = Vector2(150, 0)
	_style = m._box(m._c(Color(1, 1, 1), Color(0.11, 0.11, 0.12)), 5, m._c(Color(0.75, 0.75, 0.77), Color(0.33, 0.33, 0.35)), 1, Vector2(8, 2))
	_style_typing = _style.duplicate()
	_style_typing.border_color = m.accent; _style_typing.set_border_width_all(2)
	ui_box.add_theme_stylebox_override("panel", _style)
	ui_box.gui_input.connect(func(ev):
		if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
			typing = true; update())
	ui_value = Label.new()
	ui_value.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	ui_box.add_child(ui_value)
	row.add_child(ui_label); row.add_child(ui_box)


func update() -> void:
	var t = m.tools[m.tool]
	var val: String = vcb if vcb != "" else t.vcb_value()
	ui_label.text = t.vcb_label()
	ui_value.text = (val + " mm") if val != "" else ""
	ui_box.add_theme_stylebox_override("panel", _style_typing if vcb != "" or typing else _style)   # typing: accent ring


func type_char(ch: String) -> void:
	vcb += ch; typing = true; update()


func backspace() -> void:
	vcb = vcb.left(-1); update()


func stop_typing() -> void:
	"""A click in the view or a new selection gives Delete back to the model (I48)."""
	if typing: typing = false; update()


func apply() -> void:
	var tool: String = m.tool
	var tools: Dictionary = m.tools
	var txt := vcb.strip_edges()
	vcb = ""
	if txt != "":
		var counts := RegEx.new()
		counts.compile("^(?:[0-9]+x|[x*][0-9]+|/[0-9]+)$")
		if tool == "move" and counts.search(txt.to_lower()) != null:
			length_pending = {}
			tools[tool].typed(txt)
		elif tool in ["rect", "circle", "line", "push", "move"]:
			var texts := txt.split(",") if tool == "rect" else PackedStringArray([txt])
			# Worked out here, at once, the way FreeCAD would (units.gd evaluate_length: 150, 3/4", 1' 6 1/2",
			# 5in + 23mm, 1'-6" = 6", I35): drafts never wait for FreeCAD. What it declines goes to FreeCAD (T32).
			var here := Units.evaluate_pair(txt) if tool == "rect" else Units.evaluate_length(txt)
			if here.ok:
				length_pending = {}
				tools[tool].typed("%.12f,%.12f" % [here.a_mm, here.b_mm] if tool == "rect" else "%.12f" % here.mm)
			elif texts.size() != (2 if tool == "rect" else 1):
				m.ui_sync.text = "Enter two lengths separated by a comma"
			else:
				length_id += 1
				length_pending = {"id": length_id, "tool": tool, "model": m.model_path, "seq": m.seq,
					"state": tools[tool].state.duplicate(true)}
				m.client.send({"cmd": "length", "id": length_id, "texts": Array(texts), "default_unit": "mm"})
				m.ui_sync.text = "Evaluating length…"
	update()


func on_length(resp: Dictionary) -> void:
	if length_pending.is_empty() or resp.get("id") != length_pending.id: return
	var pending := length_pending
	length_pending = {}
	var tool: String = m.tool
	if tool != pending.tool or m.model_path != pending.model or m.seq != pending.seq: return
	if m.tools[tool].state != pending.state: return
	if not resp.get("ok", false):
		m.ui_sync.text = "Length: " + str(resp.get("error", "Invalid input"))
		return
	var values := PackedStringArray()
	for value in resp.values: values.append("%.12f" % float(value))
	m.tools[tool].typed(",".join(values))
	update()
