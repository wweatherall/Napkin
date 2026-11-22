extends SceneTree
## The tool registry with no window (in the feature tests): tools/ lists exactly the five tools, in toolbar order,
## with their labels, tooltips, keys and menu names. Also run inside the built app's pack (tools/build_app.sh
## --check), where tools/ holds .gd.remap / .gdc files, to prove discovery works there too.
const Registry = preload("res://tool_registry.gd")
var passed := 0
var failed := 0


func check(label: String, condition: bool, detail = "") -> void:
	if condition:
		passed += 1
		print("PASS ", label)
	else:
		failed += 1
		print("FAIL ", label, "  ", detail)


func _init() -> void:
	var found := Registry.found()
	var got: Array = found.map(func(t): return [t["id"], t["label"], t["tip"], t["key"], Registry.menu_label(t), t.get("show_links", false)])
	var want := [
		["select", "Select", "Select (Space)", KEY_SPACE, "Select (Space)", false],
		["paint", "Paint", "Paint (pick the wood in the Wood menu)", KEY_NONE, "Paint", true],
		["rect", "Rectangle", "Rectangle (R)", KEY_R, "Rectangle (R)", true],
		["push", "Push/Pull", "Push/Pull (P)", KEY_P, "Push/Pull (P)", true],
		["move", "Move", "Move (M)", KEY_M, "Move (M)", true],
	]
	check("tools/ declares Select, Paint, Rectangle, Push/Pull, Move in that order", got.map(func(g): return g[0]) == want.map(func(w): return w[0]), got)
	for i in mini(got.size(), want.size()):
		check("%s: label, tooltip, key, menu name, linked tint" % want[i][0], got[i] == want[i], got[i])
	check("no problems (fields, repeated ids or keys)", Registry.problems(found).is_empty(), Registry.problems(found))
	check("the base tool.gd is not a tool", not found.any(func(t): return t["script"].resource_path.ends_with("/tool.gd")))
	var dup := [{"id": "a", "label": "A", "tip": "", "key": KEY_R, "order": 1, "script": found[0]["script"]},
		{"id": "a", "label": "B", "tip": "", "key": KEY_R, "order": 2, "script": found[0]["script"]}]
	check("a repeated id and a repeated key are reported", Registry.problems(dup).size() == 2, Registry.problems(dup))
	print("  %s holds %s; the registry lists %s" % [Registry.DIR, Array(DirAccess.get_files_at(Registry.DIR)).filter(
			func(f): return not f.ends_with(".uid")), Array(ResourceLoader.list_directory(Registry.DIR))])
	print("TOOL TESTS: %d passed, %d failed" % [passed, failed])
	quit(1 if failed > 0 else 0)
