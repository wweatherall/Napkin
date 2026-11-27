extends RefCounted
## The tool registry: every script in tools/ that declares a `TOOL` constant is a tool (see tools/CLAUDE.md).
## main.gd builds the tools, the toolbar and the Tools menu from it; keys.gd maps the tool keys. Adding a tool is
## one new file in tools/: nothing shared lists the tools.
##
## Uses `ResourceLoader.list_directory` so the exported pack (`.gd.remap`/`.gdc`) lists the same tools; checks for
## repeated ids and keys.
## Entry points: found, menu_label, problems.
##
## A tool's TOOL: {"id": "rect", "label": "Rectangle", "tip": "Rectangle (R)", "key": KEY_R, "order": 30}
##   id      what set_tool() and the menus call it          label  the toolbar segment's text
##   tip     the segment's tooltip                          key    the key that picks it (KEY_NONE: none)
##   order   left-to-right place in the toolbar and the Tools menu (lowest first)
##   show_links  optional, true: over a linked board, its copies get the soft tint (I28)
##
## Listing: ResourceLoader.list_directory (Godot 4.4+) gives the scripts' own names both from source and in an
## exported pack, where the folder itself holds `.gd.remap` / `.gdc` files (tools/build_app.sh, A30).

const DIR := "res://tools/"


static func found() -> Array:
	"""Every tool's TOOL dictionary plus "script", sorted by order (then id)."""
	var out: Array = []
	for f in ResourceLoader.list_directory(DIR):
		if not f.ends_with(".gd"): continue
		var s: Script = load(DIR + f)
		if s == null: continue
		var meta: Dictionary = s.get_script_constant_map().get("TOOL", {})
		if meta.is_empty(): continue
		var t := meta.duplicate()
		t["script"] = s
		out.append(t)
	out.sort_custom(func(a, b): return a["id"] < b["id"] if a["order"] == b["order"] else a["order"] < b["order"])
	return out


static func menu_label(t: Dictionary) -> String:
	"""The Tools menu's item: the label, with the key in brackets when there is one ("Select (Space)")."""
	var key: int = t.get("key", KEY_NONE)
	return t["label"] if key == KEY_NONE else "%s (%s)" % [t["label"], OS.get_keycode_string(key)]


static func problems(tools: Array) -> Array:
	"""What's wrong with the declared tools: a missing field, a repeated id or key."""
	var out: Array = []
	var ids := {}
	var keys := {}
	for t in tools:
		for k in ["id", "label", "tip", "key", "order"]:
			if not t.has(k): out.append("%s: TOOL has no \"%s\"" % [t.get("script").resource_path, k])
		var id: String = t.get("id", "")
		if ids.has(id): out.append("two tools are called \"%s\"" % id)
		ids[id] = true
		var key: int = t.get("key", KEY_NONE)
		if key != KEY_NONE:
			if keys.has(key): out.append("%s and %s both use %s" % [keys[key], id, OS.get_keycode_string(key)])
			keys[key] = id
	return out
