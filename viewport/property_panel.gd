extends PanelContainer
## Native FreeCAD properties. Values and expressions are deliberately separate editing modes.
signal refresh_requested
signal edit_requested(change: Dictionary)
var data := {}
var object_picker: OptionButton
var fields: VBoxContainer
var status: Label
var help: Label
var feature_name := ""
var ready_to_edit := false
var reference_picker: MenuButton
var active_input: LineEdit

func _ready() -> void:
	custom_minimum_size.x = 350
	var column := VBoxContainer.new()
	add_child(column)
	var header := HBoxContainer.new()
	column.add_child(header)
	var title := Label.new()
	title.text = "Properties"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)
	var refresh := Button.new()
	refresh.text = "Refresh"
	refresh.pressed.connect(func(): refresh_requested.emit())
	header.add_child(refresh)
	var close := Button.new()
	close.text = "×"
	close.pressed.connect(hide)
	header.add_child(close)
	status = Label.new()
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status.text = "Select one piece to inspect its properties."
	column.add_child(status)
	object_picker = OptionButton.new()
	object_picker.item_selected.connect(func(_index): _show_feature())
	column.add_child(object_picker)
	help = Label.new()
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	help.text = "Feature dimensions can affect linked copies. Locations are local to their parent. Use ObjectName.Property for references."
	help.add_theme_font_size_override("font_size", 11)
	column.add_child(help)
	reference_picker = MenuButton.new()
	reference_picker.text = "Insert object reference…"
	reference_picker.tooltip_text = "Choose an expression field first, then insert a native object name"
	reference_picker.get_popup().id_pressed.connect(func(index):
		if is_instance_valid(active_input):
			active_input.insert_text_at_caret(str(data.references[index].name) + ".")
			active_input.grab_focus())
	column.add_child(reference_picker)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(scroll)
	fields = VBoxContainer.new()
	fields.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(fields)

func message(text: String) -> void:
	ready_to_edit = false
	status.text = text
	for child in fields.get_children(): child.queue_free()

func display(snapshot: Dictionary) -> void:
	data = snapshot
	reference_picker.get_popup().clear()
	for ref in data.get("references", []): reference_picker.get_popup().add_item("%s (%s)" % [ref.label, ref.name])
	ready_to_edit = true
	status.text = "Piece " + str(data.body)
	object_picker.clear()
	var selected := 0
	for i in data.objects.size():
		var obj: Dictionary = data.objects[i]
		object_picker.add_item("%s (%s)" % [obj.label, obj.name])
		if obj.name == feature_name: selected = i
	object_picker.select(selected)
	_show_feature()

func _show_feature() -> void:
	for child in fields.get_children():
		fields.remove_child(child)
		child.queue_free()
	if data.get("objects", []).is_empty(): return
	var obj: Dictionary = data.objects[object_picker.selected]
	feature_name = obj.name
	var identity := Label.new()
	identity.text = "%s · %s" % [obj.name, obj.type]
	identity.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	fields.add_child(identity)
	var details := VBoxContainer.new()
	for entry in obj.fields:
		if entry.path in ["Label", "Length", "Width", "Height", "LengthFwd", "LengthRev", "Radius", "Angle", "Count"] or entry.path.begins_with("Placement."):
			_add_field(obj, entry, fields)
		else:
			_add_field(obj, entry, details)
	var toggle := Button.new()
	toggle.text = "Other native properties"
	toggle.toggle_mode = true
	toggle.toggled.connect(func(on): details.visible = on)
	fields.add_child(toggle)
	fields.add_child(details)
	details.hide()

func _add_field(obj: Dictionary, entry: Dictionary, parent: VBoxContainer) -> void:
	var box := VBoxContainer.new()
	parent.add_child(box)
	var label := Label.new()
	label.text = entry.name
	box.add_child(label)
	if not entry.editable:
		var value := Label.new()
		value.text = str(entry.value)
		value.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		value.tooltip_text = "Read-only native property"
		box.add_child(value)
		return
	var input := LineEdit.new()
	input.text = entry.expression if entry.expression != "" else str(entry.value)
	input.tooltip_text = "Native property: " + entry.path
	if entry.kind == "enum": input.tooltip_text += " · " + ", ".join(entry.choices)
	box.add_child(input)
	input.focus_entered.connect(func(): active_input = input)
	var controls := HBoxContainer.new()
	box.add_child(controls)
	var mode := OptionButton.new()
	mode.add_item("Value")
	if entry.kind in ["number", "length", "angle"]: mode.add_item("Expression")
	mode.select(1 if entry.expression != "" else 0)
	controls.add_child(mode)
	var note := Label.new()
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	note.text = "= " + str(entry.value) if entry.expression != "" else ""
	controls.add_child(note)
	mode.item_selected.connect(func(index):
		input.text = entry.expression if index == 1 else str(entry.value)
		note.text = "Replaces expression" if index == 0 and entry.expression != "" else "")
	var apply := Button.new()
	apply.text = "Apply"
	controls.add_child(apply)
	var submit := func():
		if not ready_to_edit: return
		edit_requested.emit({"body": data.body, "object": obj.name, "property": entry.path,
			"mode": "expression" if mode.selected == 1 else "value", "value": input.text,
			"expected": {"value": entry.value, "expression": entry.expression}})
	apply.pressed.connect(submit)
	input.text_submitted.connect(func(_text): submit.call())
