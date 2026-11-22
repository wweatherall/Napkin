extends RefCounted
## Wood library and the current Paint choice (T88 step 1). Rendering and menus stay with their consumers.
const ToolContext := preload("res://tool_context.gd")
const Document := preload("res://document.gd")

signal status(text: String)

var wood_library := {}
var wood_keys: Array = []
var paint_material := "white-oak"
var _document


func _init(doc) -> void:
	_document = ToolContext.DocumentCapability.new({"doc": doc})


func load_library(dir: String) -> bool:
	var data = JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("materials.json")))
	if typeof(data) != TYPE_ARRAY: return false
	wood_keys = []
	for e in data:
		wood_library[e["key"]] = e
		wood_keys.append(e["key"])
	return true


func select_wood(key: String) -> bool:
	if not wood_library.has(key): return false
	paint_material = key
	return true


func current_name() -> String:
	return String(wood_library.get(paint_material, {}).get("name", ""))


func apply(targets: Array) -> void:
	if targets.is_empty() or not wood_library.has(paint_material): return
	_document.append({"id": _document.next_id("sm"), "type": "set_material",
		"targets": targets, "material": paint_material})
	_document.sync()
	status.emit("%s: %s" % [", ".join(targets.map(func(b): return Document.board_name(b))), current_name()])
