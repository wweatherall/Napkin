extends Node
## Selection and context (A33b, T41): what a click stands for and what's picked.
## It owns the selection, the context you've entered (an assembly or an array row), which board belongs to which
## assembly / row / family / array / mirror pair (from FreeCAD's bodies.json), which boards are hidden (from the ops),
## and the board under the cursor. Its actions (hide, unhide, make an assembly, make unique, detach) append ops to
## the document (document.gd) and sync. It draws nothing: main.gd (later the presenter) draws what the signals say.
##
## From outside, a board in an assembly stands for the whole assembly, and a copy in an array for its whole row
## (T20, I32). Double-click (Select) enters one: the rest greys out and can't be picked; new boards drawn inside
## join the assembly; inside an array a copy moves alone (it leaves the row). Esc clears the selection, then leaves.
## Hide (T28, I37) is an ordinary undoable op ("hide", saved as each board's SSHidden), so the hidden set follows
## from the ops at once: hide and its undo show at once.

signal selection_changed            # `selection` was set
signal context_changed              # entered or left an assembly / array
signal hidden_changed(by_op: bool)  # the hidden set or View > Hidden geometry changed (by_op: a hide / unhide op)
signal links_changed                # a board left its family or array (the sibling highlight is out of date)
signal say(txt: String)             # a status-bar message

var doc                             # document.gd: ops, counters, sync()
var has_board: Callable = func(_b): return true   # is this board in the model (confirmed or drafted)

var selection: Array = []
var context := ""                   # "" outside; "assembly:<id>", "row:<original>", or "component:<bid>" inside
var _context_parent := ""           # parent context when entering a component from inside an assembly
var body_assembly := {}             # board id -> assembly id, "" if none
var body_row := {}                  # board id -> the original its array row was copied from, "" if none
var body_family := {}               # board id -> its family (shared definition), "" if it isn't linked
var body_array := {}                # board id -> the array it's a copy in, "" if none
var body_mirror_plane := {}         # mirrored board id -> [point, normal] of its plane (model mm)
var body_deleted := {}             # board ids removed by delete ops (immediate prediction)
var body_hidden := {}               # board id -> true while it's hidden (refresh_hidden() works it out from the ops)
var show_hidden := false            # View > Hidden geometry: hidden boards ghosted and pickable
var hover_body := ""                # the board under the cursor (Make unique / Detach / Hide act on it)


# ---------------- what FreeCAD says each board belongs to ----------------

func set_boards(data: Array) -> void:
	"""bodies.json entries: each board's family, array, assembly, row and mirror plane."""
	var previous := body_row.duplicate()
	body_family = {}; body_array = {}; body_assembly = {}; body_row = {}
	for b in data:
		var bid: String = b["id"]
		body_family[bid] = b.get("family", ""); body_array[bid] = b.get("array", "")
		body_assembly[bid] = b.get("assembly", ""); body_row[bid] = b.get("row", "")
		var mp: Array = b.get("mirror_plane", [])
		if mp.size() == 2: body_mirror_plane[bid] = [Vector3(mp[0][0], mp[0][1], mp[0][2]), Vector3(mp[1][0], mp[1][1], mp[1][2])]
		else: body_mirror_plane.erase(bid)

	if context.begins_with("row:"):
		var source := context.substr(4)
		if not body_row.values().has(source):
			var next := ""
			for b in body_row:
				if previous.get(b, "") == source and body_row[b] != "": next = "row:" + body_row[b]; break
			context = next
			context_changed.emit()
	elif context.begins_with("component:"):
		var entered := context.substr(10)
		if not body_family.has(entered):
			var next := _context_parent if (_context_parent != "" and body_assembly.values().has(_context_parent.substr(9))) else ""
			_context_parent = ""
			context = next
			context_changed.emit()
	selection = selection.filter(func(b): return body_family.has(b))


# ---------------- queries ----------------

func unit_of(bid: String) -> Dictionary:
	"""What a tool acts on when you point at this board from where you are."""
	if bid == "": return {}
	if context == "":
		var assembly_row := _assembly_row(bid)
		if not assembly_row.is_empty(): return assembly_row
	if context == "" or context.begins_with("row:"):
		var a: String = body_assembly.get(bid, "")
		if a != "":
			return {"id": a, "kind": "assembly", "bodies": body_assembly.keys().filter(func(b): return body_assembly[b] == a)}
		var r: String = body_row.get(bid, "")
		if r != "":
			return {"id": bid, "kind": "row", "bodies": body_row.keys().filter(func(b): return body_row[b] == r)}
	return {"id": bid, "kind": "board", "bodies": [bid]}


func _assembly_row(bid: String) -> Dictionary:
	"""Join the parallel board rows through their assemblies, using existing worker metadata."""
	var members := [bid]
	var rows := []
	var assemblies := []
	var cursor := 0
	while cursor < members.size():
		var b: String = members[cursor]
		cursor += 1
		var row: String = body_row.get(b, "")
		var assembly: String = body_assembly.get(b, "")
		if row != "" and not rows.has(row): rows.append(row)
		if assembly != "" and not assemblies.has(assembly): assemblies.append(assembly)
		for other in body_row:
			if members.has(other): continue
			if (row != "" and body_row[other] == row) or (assembly != "" and body_assembly.get(other, "") == assembly):
				members.append(other)
	if rows.is_empty() or assemblies.size() < 2: return {}
	rows.sort()
	return {"id": bid, "kind": "row", "source": rows[0], "bodies": members}


func in_context(bid: String) -> bool:
	if context == "" or bid == "": return true
	if context.begins_with("assembly:"): return body_assembly.get(bid, "") == context.substr(9)
	if context.begins_with("component:"): return bid == context.substr(10)
	var row := _assembly_row(bid)
	return row.get("source", body_row.get(bid, "")) == context.substr(4)


func is_context_sibling(bid: String) -> bool:
	if not context.begins_with("component:") or bid == "": return false
	return siblings_of(context.substr(10)).has(bid)


func context_assembly() -> String:
	return context.substr(9) if context.begins_with("assembly:") else ""


func members_of(assembly: String) -> Array:
	return body_assembly.keys().filter(func(b): return body_assembly[b] == assembly)


func mirror_plane_of_context() -> Array:
	"""Inside a mirror group: [point, normal] of its plane; else []."""
	var a := context_assembly()
	if a == "": return []
	for b in members_of(a):
		if body_mirror_plane.has(b): return body_mirror_plane[b]
	return []


func edit_blocked(bid: String) -> bool:
	"""From outside, an assembly's boards are edited by entering it (SketchUp)."""
	if not context.begins_with("assembly:") and not context.begins_with("component:") and body_assembly.get(bid, "") != "":
		say.emit("Double-click the assembly (Select tool) to edit inside it")
		return true
	return false


func siblings_of(bid: String) -> Array:
	var fam: String = body_family.get(bid, "")
	if fam == "": return []
	return body_family.keys().filter(func(b): return b != bid and body_family[b] == fam)


func hidden_boards() -> Dictionary:
	var out := {}
	for op in doc.ops:
		if op["type"] != "hide": continue
		for b in op["targets"]:
			if op.get("hidden", true): out[b] = true
			else: out.erase(b)
	return out


func refresh_hidden() -> void:
	body_hidden = hidden_boards()
	body_deleted = {}
	for op in doc.ops:
		if op["type"] == "delete":
			for b in op["targets"]: body_deleted[b] = true


func is_hidden(bid: String) -> bool:
	"""Hidden and out of sight: not picked, not snapped to."""
	return body_deleted.has(bid) or (body_hidden.has(bid) and not show_hidden)


# ---------------- selection and context ----------------

func set_selection(ids: Array) -> void:
	selection = ids
	selection_changed.emit()


func enter_context_of(bid: String) -> void:
	if bid == "" or context.begins_with("component:"): return
	if context.begins_with("assembly:"):
		if body_family.get(bid, "") == "" or body_assembly.get(bid, "") != context.substr(9): return
		_context_parent = context
		context = "component:" + bid
		set_selection([])
		context_changed.emit()
		return
	var row := _assembly_row(bid)
	if context == "" and not row.is_empty(): context = "row:" + row["source"]
	elif body_assembly.get(bid, "") != "": context = "assembly:" + body_assembly[bid]
	elif body_row.get(bid, "") != "": context = "row:" + body_row[bid]
	elif body_family.get(bid, "") != "": context = "component:" + bid
	else: return
	_context_parent = ""
	set_selection([])
	context_changed.emit()


func leave_context() -> void:
	var parent := ""
	if context.begins_with("component:"):
		parent = _context_parent
		_context_parent = ""
	elif context.begins_with("assembly:"):
		var members := members_of(context.substr(9))
		if not members.is_empty():
			var row := _assembly_row(members[0])
			if not row.is_empty(): parent = "row:" + row["source"]
	context = parent
	context_changed.emit()


# ---------------- actions (each one op) ----------------

func _hide_op(targets: Array, hidden: bool) -> void:
	doc.ops.append({"id": doc.next_id("hd"), "type": "hide", "targets": targets, "hidden": hidden})
	set_selection(selection.filter(func(b): return not hidden or not targets.has(b)))
	hidden_changed.emit(true)
	doc.sync()


static func _boards_word(n: int) -> String:
	return "%d board%s" % [n, "" if n == 1 else "s"]


func hide_selected() -> void:
	"""Edit > Hide (H): the selection, else the board (or assembly) under the cursor."""
	var ids: Array = selection.duplicate()
	if ids.is_empty() and hover_body != "": ids = unit_of(hover_body).get("bodies", [])
	ids = ids.filter(func(b): return not body_hidden.has(b))
	if ids.is_empty():
		say.emit("Select the boards to hide first (Select tool)"); return
	_hide_op(ids, true)
	say.emit("Hid %s. Shift+H unhides all" % _boards_word(ids.size()))


func unhide(which: String) -> void:
	"""Edit > Unhide selected / last / all."""
	var ids: Array = []
	match which:
		"selected":
			ids = selection.filter(func(b): return body_hidden.has(b))
			if ids.is_empty():
				say.emit("Select hidden boards first (View > Hidden geometry shows them)"); return
		"last":
			for i in range(doc.ops.size() - 1, -1, -1):
				var op: Dictionary = doc.ops[i]
				if op["type"] == "hide" and op.get("hidden", true):
					ids = op["targets"].filter(func(b): return body_hidden.has(b))
					if not ids.is_empty(): break
		"all":
			ids = body_hidden.keys().filter(func(b): return has_board.call(b))
	if ids.is_empty():
		say.emit("Nothing is hidden"); return
	_hide_op(ids, false)
	say.emit("Unhid %s" % _boards_word(ids.size()))


func toggle_hidden_geometry() -> void:
	show_hidden = not show_hidden
	if not show_hidden: set_selection(selection.filter(func(b): return not body_hidden.has(b)))
	hidden_changed.emit(false)


func make_assembly() -> void:
	var ids := selection.filter(func(b): return body_assembly.get(b, "") == "")
	if ids.is_empty():
		say.emit("Select the boards first (Select tool, Shift-click to add)"); return
	var aid: String = doc.next_id("a")
	doc.ops.append({"id": doc.next_id("as"), "type": "make_assembly", "targets": ids,
					"new_id": aid, "name": "Assembly %d" % doc.counters["a"]})
	set_selection([])
	doc.sync()
	say.emit("Assembly of %d board%s: double-click it to edit inside" % [ids.size(), "" if ids.size() == 1 else "s"])


func linked_op(kind: String) -> void:
	"""Edit > Make unique (U) / Detach from array, on the board under the cursor."""
	var bid := hover_body
	if bid == "":
		say.emit("Point at a board first"); return
	if kind == "make_unique" and body_family.get(bid, "") == "":
		say.emit("%s isn't linked to anything" % doc.board_name(bid)); return
	if kind == "detach" and body_array.get(bid, "") == "":
		say.emit("%s isn't a copy in an array" % doc.board_name(bid)); return
	var prefix := "mu" if kind == "make_unique" else "dt"
	doc.ops.append({"id": doc.next_id(prefix), "type": kind, "targets": [bid]})
	links_changed.emit()
	doc.sync()
	say.emit(("%s is its own board now" if kind == "make_unique" else "%s no longer follows its array") % doc.board_name(bid))


func delete_selected() -> void:
	var ids := selection.filter(func(b): return has_board.call(b) and in_context(b))
	if ids.is_empty(): return
	doc.ops.append({"id": doc.next_id("del"), "type": "delete", "targets": ids})
	set_selection([])
	refresh_hidden()
	hidden_changed.emit(true)
	doc.sync()
