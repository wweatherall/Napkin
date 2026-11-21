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
signal preview_changed(lines: PackedVector3Array)
var direct_link := false
var picking_axis := -1
var pending := {}
var summary: VBoxContainer
var result: Label
var mode_picker: OptionButton
var apply_fit: Button
const FACE_NAMES := ["Left", "Right", "Front", "Back", "Bottom", "Top"]


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
	summary = VBoxContainer.new()
	column.add_child(summary)
	visibility_changed.connect(func(): if not visible: cancel_pick())
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
	cancel_pick()
	summary.hide()
	status.text = text
	for child in fields.get_children(): child.queue_free()

func display(snapshot: Dictionary) -> void:
	data = snapshot
	reference_picker.get_popup().clear()
	for ref in data.get("references", []): reference_picker.get_popup().add_item("%s (%s)" % [ref.label, ref.name])
	ready_to_edit = true
	cancel_pick()
	_build_summary()
	status.text = str(data.objects[0].label)
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

func cancel_pick() -> void:
	direct_link = false
	picking_axis = -1
	pending.clear()
	preview_changed.emit(PackedVector3Array())
	if is_instance_valid(apply_fit): apply_fit.disabled = true

func _build_summary() -> void:
	for child in summary.get_children():
		summary.remove_child(child)
		child.queue_free()
	var board: Dictionary = data.boards.get(data.body, {})
	summary.visible = not board.is_empty()
	if board.is_empty(): return
	var title := Label.new()
	title.text = "Axis     Dimensions             Placement"
	summary.add_child(title)
	for i in 3:
		var row := HBoxContainer.new()
		summary.add_child(row)
		var axis := Label.new()
		axis.text = "XYZ"[i]
		row.add_child(axis)
		var field := LineEdit.new()
		field.text = "%s mm" % board.sizes[i]
		if board.linked_axis == i: field.text = str(board.result).split(" · ")[0]
		if board.linked_axis == i: field.focus_entered.connect(func(): field.select_all.call_deferred())
		field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		field.custom_minimum_size.x = 62
		field.tooltip_text = "Enter a new length to remove the fit" if board.linked_axis == i else "Size along the stock axis · Enter to apply"
		row.add_child(field)
		if not board.fitted or board.linked_axis == i:
			field.gui_input.connect(func(event):
				if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
					cancel_pick()
					direct_link = true
					picking_axis = i
					result.text = "Type a length or click a face, edge or corner to link.")
		var root: Dictionary = data.objects[0]
		var path := "Placement.Base." + "xyz"[i]
		for entry in root.fields:
			if entry.path != path: continue
			var position_input := LineEdit.new()
			position_input.text = entry.value
			position_input.custom_minimum_size.x = 60
			position_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			position_input.editable = entry.editable and entry.expression == ""
			position_input.tooltip_text = "Position in the parent frame · Enter to apply"
			row.add_child(position_input)
			position_input.focus_entered.connect(cancel_pick)
			position_input.text_submitted.connect(func(value):
				edit_requested.emit({"body":data.body,"object":root.name,"property":entry.path,"value":value,"mode":"value","expected":{"value":entry.value,"expression":entry.expression}}))
		var native_name: String = board.extrusion if i == 2 else board.plane
		var prop: String = ["Length", "Width", "LengthFwd"][i]
		field.text_submitted.connect(func(value):
			if board.linked_axis == i:
				edit_requested.emit({"body":data.body,"mode":"replace_fit","axis":i,"value":value})
				return
			for obj in data.objects:
				if obj.name != native_name: continue
				for entry in obj.fields:
					if entry.path == prop and entry.expression == "":
						edit_requested.emit({"body":data.body,"object":native_name,"property":prop,"value":value,"mode":"value","expected":{"value":entry.value,"expression":""}})
					elif entry.path == prop: status.text = "Edit the existing expression in native properties.")
		var pick := Button.new()
		pick.text = "Pick face…"
		pick.disabled = board.fitted and board.linked_axis != i
		pick.pressed.connect(func():
			cancel_pick()
			picking_axis = i
			result.text = "Click a face, edge or corner on another rectangular board · Esc cancels")
		row.add_child(pick)
	var actions := HBoxContainer.new()
	summary.add_child(actions)
	mode_picker = OptionButton.new()
	for item in ["Butt to plane","Slice at plane","Fully reach plane"]: mode_picker.add_item(item)
	mode_picker.item_selected.connect(func(_i): _preview())
	actions.add_child(mode_picker)
	apply_fit = Button.new()
	apply_fit.text = "Apply fit"
	apply_fit.disabled = true
	apply_fit.pressed.connect(func():
		if not pending.is_empty():
			edit_requested.emit({"body":data.body,"mode":"plane_fit","axis":pending.axis,"target_body":pending.target,"face":pending.face,"fit_mode":mode_picker.selected,"reverse":board.get("reverse",false)}))
	actions.add_child(apply_fit)
	result = Label.new()
	result.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	result.text = board.result
	summary.add_child(result)

func _vec(a: Array) -> Vector3:
	return Vector3(a[0],a[1],a[2])

func pick_reference(hit: Dictionary) -> void:
	var target: String = hit.get("body","")
	if target == data.body or not data.boards.has(target) or data.boards[target].fitted:
		result.text = "Pick a face on another rectangular board."
		return
	var b: Dictionary = data.boards[target]
	var direction := _vec(data.boards[data.body].axes[picking_axis])
	var edge_point: Vector3 = hit.get("edge_point",hit.get("point",Vector3.ZERO))
	var candidates := []
	for i in 3:
		var normal := _vec(b.axes[i])
		for side in 2:
			var outward := normal if side else -normal
			var score := absf(normal.dot(direction))
			if hit.has("normal"):
				if outward.dot(hit.normal) < 0.999: continue
			else:
				var point := _vec(b.origin) + normal * float(b.sizes[i]) * side
				if absf(normal.dot(edge_point-point)) > 0.002: continue
			candidates.append({"face":2*i+side,"score":score})
	candidates.sort_custom(func(x,y): return x.score > y.score if x.score != y.score else x.face < y.face)
	var axis := picking_axis
	for candidate in candidates:
		pending = {"target":target,"face":candidate.face,"axis":axis}
		_preview()
		if apply_fit.disabled: continue
		picking_axis = -1
		if direct_link:
			direct_link = false
			apply_fit.pressed.emit()
		return
	pending.clear()
	result.text = "Choose a face reachable along this dimension."

func _preview() -> void:
	if pending.is_empty(): return
	var a: Dictionary = data.boards[data.body]
	var b: Dictionary = data.boards[pending.target]
	var axis: int = pending.axis
	var face: int = pending.face
	var i := floori(face / 2.0)
	var n := _vec(b.axes[i])
	var point := _vec(b.origin) + n * float(b.sizes[i]) * (face % 2)
	var d := _vec(a.axes[axis])
	var denom := d.dot(n)
	var o := _vec(a.origin)
	if a.get("reverse",false):
		o += d * float(a.sizes[axis])
		d = -d
	var u := (axis+1)%3
	var v := (axis+2)%3
	var dx := _vec(a.axes[u])*float(a.sizes[u])
	var dy := _vec(a.axes[v])*float(a.sizes[v])
	var corners := PackedVector3Array([o,o+dx,o+dx+dy,o+dy])
	var depths: Array[float] = []
	var lines := PackedVector3Array()
	apply_fit.disabled = true
	if absf(denom) > 0.000001:
		for c in corners: depths.append((point-c).dot(n)/denom)
	if depths.is_empty() or depths.min() <= 0.000001:
		result.text = "This plane cannot be reached along the selected axis."
		preview_changed.emit(lines)
		return
	var ends := PackedVector3Array()
	for j in 4:
		var length: float = [depths.min(),depths[j],depths.max()][mode_picker.selected]
		ends.append(corners[j]+d*length)
	for j in 4: lines.append_array(PackedVector3Array([corners[j],ends[j],ends[j],ends[(j+1)%4]]))
	preview_changed.emit(lines)
	var face_z := n if face%2 else -n
	var face_x := _vec(b.axes[(i+1)%3])
	var source_x := _vec(a.axes[0])
	var source_z := _vec(a.axes[2])
	var relative := Basis(source_x,source_z.cross(source_x),source_z).inverse()*Basis(face_x,face_z.cross(face_x),face_z)
	var angles := relative.get_euler(EULER_ORDER_ZYX)*180.0/PI
	var size_text := "%.2f mm" % depths.min()
	if mode_picker.selected == 2: size_text = "%.2f mm" % depths.max()
	elif mode_picker.selected == 1: size_text = "%.2f–%.2f mm" % [depths.min(),depths.max()]
	result.text = "%s → %s face\nResult: %s · X %.1f°  Y %.1f°  Z %.1f°" % [b.label,FACE_NAMES[face],size_text,angles.x,angles.y,angles.z]
	apply_fit.disabled = false
