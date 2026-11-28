extends RefCounted
## Model files: settings, last model, output folders, window title, and switching models (`m.files`).
## `m.files`; main.gd keeps `SETTINGS`, `_beside_project`, `_model_before`, `switch_model`, and `_reset_model_state`
## so `ui.gd`, `worker_process.gd`, `history.gd`, `menus.gd`, and tests don't change.
## Entry points: _beside_project, _last_model, _remember_model, _out_for, _set_title, switch_model, _reset_model_state.

const SETTINGS := "user://settings.cfg"

var m                               # main.gd: doc, pres, sel, measure, prompts, tools, ui_sync, marker, ...
var out_root := ""                  # each model's outputs go in a folder of their own under here
var _model_before := ""             # the model this window had before an Open (to go back if it's taken)


func _init(main = null) -> void:
	m = main


# Napkin works on one FreeCAD file at a time. File > New / Open switch files without restarting; the last
# file reopens next time.
func _beside_project(rel: String) -> String:
	"""A file shipped next to the viewport: the repo when run from source, the app bundle's Resources otherwise."""
	var src := ProjectSettings.globalize_path("res://")
	if src != "" and FileAccess.file_exists(src.path_join("..").path_join(rel).simplify_path()):
		return src.path_join("..").path_join(rel).simplify_path()
	return OS.get_executable_path().get_base_dir().path_join("../Resources").path_join(rel).simplify_path()


func _last_model() -> String:
	var cfg := ConfigFile.new()
	if cfg.load(SETTINGS) == OK:
		var p: String = cfg.get_value("files", "last_model", "")
		if p != "" and (FileAccess.file_exists(p) or DirAccess.dir_exists_absolute(p.get_base_dir())):
			return p
	var docs := OS.get_system_dir(OS.SYSTEM_DIR_DOCUMENTS).path_join("Napkin")
	DirAccess.make_dir_recursive_absolute(docs)
	return docs.path_join("Untitled.FCStd")


func _remember_model(path: String) -> void:
	var cfg := ConfigFile.new()
	cfg.load(SETTINGS)
	cfg.set_value("files", "last_model", path)
	cfg.save(SETTINGS)


func _out_for(path: String) -> String:
	return out_root.path_join("%s-%s" % [path.get_file().get_basename(), path.md5_text().left(8)])


func _set_title() -> void:
	if m.test_mode: return
	DisplayServer.window_set_title("%s — Napkin" % m.model_path.get_file().get_basename())


func switch_model(path: String, fresh := false) -> void:
	"""Close the current model (the worker keeps it saved) and open another; fresh = start it empty."""
	if path.get_extension().to_lower() != "fcstd": path += ".FCStd"
	if path == m.model_path and not fresh: return
	if m.opened: _model_before = m.model_path
	_reset_model_state()
	m.model_path = path
	if not m.test_mode:
		m.out_dir = _out_for(path)
		_remember_model(path)
	DirAccess.make_dir_recursive_absolute(m.out_dir)
	_set_title()
	m.doc.open(path, fresh)
	m.ui_sync.text = "opening %s" % path.get_file()


func _reset_model_state() -> void:
	m.prompts.reset_outside_question()
	m.properties_seq = -1
	m.properties_request += 1
	m.sel.set_selection([])
	m.doc.reset()                     # a reply still on its way belongs to the old model: it's ignored
	m.measure.reset_for_model()
	m.pres.reset()
	m.reject_note = ""
	m.tools["move"].last_oid = ""; m.tools["move"].memo.clear()
	m.set_tool(m.tool)
	m.marker.visible = false
