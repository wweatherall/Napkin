extends RefCounted
## Wood library, board materials, and Paint and grain commands (T15, M03).
##
## Never references Main (takes Document and `_beside_project` for texture paths). Caches textures and supplies wood
## shader materials to presenter.gd; appends `set_material` and `turn_grain` ops through ToolContext.DocumentCapability;
## emits `status` and `wood_selected`.
## Entry points: load_library, set_boards, wood_material, select_wood, set_paint_material, turn_grain, current_name, apply.
const ToolContext := preload("res://tool_context.gd")
const Document := preload("res://document.gd")
const Geo := preload("res://tool_geometry.gd")

# The worker writes materials.json (the library) beside bodies.json; each board's material, grain and across
# directions come in bodies.json. Textures live in materials/textures beside the project (or in the app bundle).
const WOOD := preload("res://wood.gdshader")

signal status(text: String)
signal wood_selected(key: String)

var wood_library := {}
var wood_keys: Array = []
var paint_material := "white-oak"
var _body_material := {}            # board id -> material key
var _wood_tex := {}                 # texture file -> ImageTexture
var _document
var _beside_project: Callable


func _init(doc, beside_project := Callable()) -> void:
	_beside_project = beside_project
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


func set_boards(data: Array) -> void:
	for b in data: _body_material[b["id"]] = b.get("material", "")


func _wood_texture(file: String) -> Texture2D:
	if not _wood_tex.has(file):
		var img := Image.load_from_file(_beside_project.call("materials/textures/" + file))
		if img == null or img.is_empty():
			_wood_tex[file] = null
		else:
			img.generate_mipmaps()
			_wood_tex[file] = ImageTexture.create_from_image(img)
	return _wood_tex[file]


func wood_material(bid: String, b: Dictionary, base: Color) -> ShaderMaterial:
	var e: Dictionary = wood_library.get(b.get("material", ""), {})
	if e.is_empty(): return null
	var side := _wood_texture(e["texture"]); var end := _wood_texture(e["end_texture"])
	if side == null or end == null: return null
	var sm := ShaderMaterial.new(); sm.shader = WOOD
	sm.set_shader_parameter("side_tex", side); sm.set_shader_parameter("end_tex", end)
	var g: Array = b.get("grain", [1, 0, 0]); var a: Array = b.get("across", [0, 1, 0])
	sm.set_shader_parameter("grain", Geo.m2g(Vector3(g[0], g[1], g[2])))
	sm.set_shader_parameter("across", Geo.m2g(Vector3(a[0], a[1], a[2])))
	sm.set_shader_parameter("side_size", float(e["size_mm"]) / 1000.0)
	sm.set_shader_parameter("side_grain_v", e["grain"] == "v")
	sm.set_shader_parameter("end_size", float(e["end_size_mm"]) / 1000.0)
	var et := end.get_size()
	sm.set_shader_parameter("end_aspect", et.y / maxf(et.x, 1.0))
	var h := hash(bid)
	sm.set_shader_parameter("offset", Vector2(float(h & 1023) / 1024.0, float((h >> 10) & 1023) / 1024.0))
	sm.set_shader_parameter("base_color", base)
	return sm


func set_paint_material(k: String) -> void:
	if not select_wood(k): return
	wood_selected.emit(k)


func turn_grain(bid: String) -> void:
	if bid == "" or _body_material.get(bid, "") == "":
		status.emit("Point at a painted board to turn its grain"); return
	_document.append({"id": _document.next_id("tg"), "type": "turn_grain", "targets": [bid]})
	_document.sync()
	status.emit("%s: grain turned 90°" % Document.board_name(bid))
