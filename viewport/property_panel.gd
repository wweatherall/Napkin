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
var piece_header: VBoxContainer
var piece_title: Label
var piece_subtitle: Label
var parametric_badge: Label
var native_toggle: Button
var native_section: VBoxContainer
var format_length: Callable = func(mm: float) -> String: return "%.2f mm" % mm
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
	piece_header = VBoxContainer.new()
	piece_header.visible = false
	column.add_child(piece_header)
	var title_row := HBoxContainer.new()
	piece_header.add_child(title_row)
	piece_title = Label.new()
	piece_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	piece_title.add_theme_font_size_override("font_size", 15)
	title_row.add_child(piece_title)
	parametric_badge = Label.new()
	parametric_badge.text = "Parametric"
	parametric_badge.add_theme_font_size_override("font_size", 11)
	parametric_badge.add_theme_color_override("font_color", Color(0.18, 0.55, 0.85))
	parametric_badge.visible = false
	title_row.add_child(parametric_badge)
	piece_subtitle = Label.new()
	piece_subtitle.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	piece_subtitle.add_theme_font_size_override("font_size", 11)
	piece_subtitle.add_theme_color_override("font_color", Color(0.65, 0.65, 0.7))
	piece_header.add_child(piece_subtitle)
	summary = VBoxContainer.new()
	column.add_child(summary)
	visibility_changed.connect(func(): if not visible: cancel_pick())
	native_toggle = Button.new()
	native_toggle.text = "Native FreeCAD properties"
	native_toggle.toggle_mode = true
	native_toggle.button_pressed = false
	native_toggle.visible = false
	column.add_child(native_toggle)
	native_section = VBoxContainer.new()
	native_section.visible = false
	native_section.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(native_section)
	native_toggle.toggled.connect(func(on): native_section.visible = on)
	object_picker = OptionButton.new()
	object_picker.item_selected.connect(func(_index): _show_feature())
	native_section.add_child(object_picker)
	help = Label.new()
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	help.text = "Feature dimensions can affect linked copies. Locations are local to their parent. Use ObjectName.Property for references."
	help.add_theme_font_size_override("font_size", 11)
	native_section.add_child(help)
	reference_picker = MenuButton.new()
	reference_picker.text = "Insert object reference…"
	reference_picker.tooltip_text = "Choose an expression field first, then insert a native object name"
	reference_picker.get_popup().id_pressed.connect(func(index):
		if is_instance_valid(active_input):
			active_input.insert_text_at_caret(str(data.references[index].name) + ".")
			active_input.grab_focus())
	native_section.add_child(reference_picker)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	native_section.add_child(scroll)
	fields = VBoxContainer.new()
	fields.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(fields)

func message(text: String) -> void:
	ready_to_edit = false
	cancel_pick()
	piece_header.hide()
	summary.hide()
	native_toggle.hide()
	native_section.hide()
	status.visible = true
	status.text = text
	for child in fields.get_children(): child.queue_free()

func display(snapshot: Dictionary) -> void:
	data = snapshot
	reference_picker.get_popup().clear()
	for ref in data.get("references", []): reference_picker.get_popup().add_item("%s (%s)" % [ref.label, ref.name])
	ready_to_edit = true
	cancel_pick()
	var sum: Dictionary = data.get("summary", {})
	piece_title.text = str(sum.get("label", data.objects[0].label if not data.get("objects", []).is_empty() else ""))
	piece_subtitle.text = str(sum.get("context", ""))
	piece_subtitle.visible = piece_subtitle.text != ""
	parametric_badge.visible = bool(sum.get("parametric", false))
	piece_header.show()
	status.visible = false
	status.text = piece_title.text
	native_toggle.show()
	native_section.visible = native_toggle.button_pressed
	_build_summary()
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

func _format_mm(mm: float) -> String:
	return str(format_length.call(mm))


func _parse_mm(text: String) -> float:
	var s := text.strip_edges()
	if s.ends_with(" mm"): s = s.substr(0, s.length() - 3).strip_edges()
	return float(s)


func _build_summary() -> void:
	for child in summary.get_children():
		summary.remove_child(child)
		child.queue_free()
	var board: Dictionary = data.boards.get(data.body, {})
	if board.is_empty() or not board.get("rectangular", true):
		var dims: Array = data.get("summary", {}).get("dimensions", [])
		summary.visible = not dims.is_empty() or not board.is_empty()
		if not dims.is_empty():
			var ro_title := Label.new()
			ro_title.text = "Dimensions (read-only)"
			summary.add_child(ro_title)
			for dim in dims:
				var row := HBoxContainer.new()
				summary.add_child(row)
				var k := Label.new()
				k.text = str(dim.get("label", ""))
				k.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				row.add_child(k)
				var v := Label.new()
				v.text = _format_mm(float(dim.get("value_mm", 0.0)))
				row.add_child(v)
		if not board.is_empty() and str(board.get("extrusion", "")) != "":
			var pick := Button.new()
			pick.text = "Pick face…"
			pick.pressed.connect(func():
				cancel_pick()
				picking_axis = 2
				result.text = "Click a planar face, edge or corner on another board · Esc cancels")
			summary.add_child(pick)
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
			result.text = str(board.get("result", ""))
			summary.add_child(result)
		return
	summary.visible = true
	var title := Label.new()
	title.text = "Axis     Dimensions             Placement"
	summary.add_child(title)
	var sum_dims: Array = data.get("summary", {}).get("dimensions", [])
	var linked_dim: Dictionary = {}
	for i in 3:
		var row := HBoxContainer.new()
		summary.add_child(row)
		var axis := Label.new()
		axis.text = "XYZ"[i]
		row.add_child(axis)
		var field := LineEdit.new()
		field.text = _format_mm(float(board.sizes[i]))
		if board.linked_axis == i:
			field.focus_entered.connect(func(): field.select_all.call_deferred())
			if i < sum_dims.size(): linked_dim = sum_dims[i]
		field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		field.custom_minimum_size.x = 62
		field.tooltip_text = "Current evaluated length · Enter a new length to remove the fit" if board.linked_axis == i else "Size along the stock axis · Enter to apply"
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
			position_input.text = _format_mm(_parse_mm(str(entry.value)))
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
	if not linked_dim.is_empty():
		var linked_label := Label.new()
		linked_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		var tgt := str(linked_dim.get("target_label", ""))
		var face := str(linked_dim.get("target_face", ""))
		var off := float(linked_dim.get("offset_mm", 0.0))
		var header_txt := "🔗 %s · %s" % [tgt, face] if face != "" else "🔗 %s" % tgt
		if absf(off) > 1e-6: header_txt += " (offset %s)" % _format_mm(off)
		linked_label.text = "%s\nCurrent evaluated length: %s" % [header_txt, _format_mm(float(linked_dim.get("value_mm", board.sizes[board.linked_axis])))]
		summary.add_child(linked_label)

func _vec(a: Array) -> Vector3:
	return Vector3(a[0],a[1],a[2])

func _target_face_plane(b: Dictionary, face: int) -> Dictionary:
	var fe = b.get("fitted_end", null)
	if fe is Dictionary and int(fe.get("face", -1)) == face:
		return {"point": _vec(fe.point), "normal": _vec(fe.normal)}
	if not b.get("rectangular", true):
		var pfaces: Array = b.get("planar_faces", [])
		if face >= 0 and face < pfaces.size():
			return {"point": _vec(pfaces[face].point), "normal": _vec(pfaces[face].normal)}
		return {}
	var i := floori(face / 2.0)
	var axis_n := _vec(b.axes[i])
	var side := face % 2
	return {"point": _vec(b.origin) + axis_n * float(b.sizes[i]) * side, "normal": axis_n if side else -axis_n}

func pick_reference(hit: Dictionary) -> void:
	var target: String = hit.get("body","")
	if target == data.body or not data.boards.has(target):
		result.text = "Pick a planar face on another board."
		return
	var src_ext := str(data.boards.get(data.body, {}).get("extrusion", ""))
	var dst_ext := str(data.boards[target].get("extrusion", ""))
	if src_ext != "" and src_ext == dst_ext:
		result.text = "Pick a planar face on another board."
		return
	var b: Dictionary = data.boards[target]
	var direction := _vec(data.boards[data.body].axes[picking_axis])
	var edge_point: Vector3 = hit.get("edge_point",hit.get("point",Vector3.ZERO))
	var candidates := []
	var face_count: int = 6 if b.get("rectangular", true) else b.get("planar_faces", []).size()
	for face in face_count:
		var plane := _target_face_plane(b, face)
		if plane.is_empty(): continue
		var outward: Vector3 = plane.normal
		var score := absf(outward.dot(direction))
		if hit.has("normal"):
			if outward.dot(hit.normal) < 0.999: continue
		else:
			if absf(outward.dot(edge_point - plane.point)) > 0.002: continue
		candidates.append({"face": face, "score": score})
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
	var plane := _target_face_plane(b, face)
	var n: Vector3 = plane.normal
	var point: Vector3 = plane.point
	var d := _vec(a.axes[axis])
	var o := _vec(a.origin)
	if a.get("reverse",false):
		o += d * float(a.sizes[axis])
		d = -d
	var denom := d.dot(n)
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
	var face_z := n
	var face_x := Vector3.RIGHT
	if b.get("rectangular", true):
		face_x = _vec(b.axes[(i+1)%3])
		if absf(face_x.dot(face_z)) > 0.999: face_x = _vec(b.axes[(i+2)%3])
	else:
		face_x = Vector3.RIGHT if absf(face_z.x) < 0.9 else Vector3.UP
		face_x = face_z.cross(face_x).normalized()
	var face_y := face_z.cross(face_x).normalized()
	face_x = face_y.cross(face_z).normalized()
	var source_x := _vec(a.axes[0])
	var source_z := _vec(a.axes[2])
	var relative := Basis(source_x,source_z.cross(source_x),source_z).inverse()*Basis(face_x,face_y,face_z)
	var angles := relative.get_euler(EULER_ORDER_ZYX)*180.0/PI
	var size_text := _format_mm(depths.min())
	if mode_picker.selected == 2: size_text = _format_mm(depths.max())
	elif mode_picker.selected == 1: size_text = "%s–%s" % [_format_mm(depths.min()), _format_mm(depths.max())]
	result.text = "%s → %s face\nResult: %s · X %.1f°  Y %.1f°  Z %.1f°" % [b.label,FACE_NAMES[face],size_text,angles.x,angles.y,angles.z]
	apply_fit.disabled = false
