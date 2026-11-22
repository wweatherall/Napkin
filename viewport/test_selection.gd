extends SceneTree
## Selection and context (selection.gd, A33b, T41) on their own, with no window and no worker: a stand-in document
## records ops and syncs. Checks what a board stands for from outside and inside an assembly or array row, entering
## and leaving, the hidden set following the ops (hide, unhide, undo), View > Hidden geometry, siblings, and the ops
## that hide, assemble, make unique and detach add.
## Run: Godot --headless --path viewport --script res://test_selection.gd
const Selection = preload("res://selection.gd")
var passed := 0
var failed := 0
var made: Array = []


class FakeDoc:
	var ops: Array = []
	var counters := {"hd": 0, "as": 0, "a": 0, "mu": 0, "dt": 0, "del": 0}
	var syncs := 0
	func sync() -> void: syncs += 1


func check(label: String, condition: bool) -> void:
	if condition:
		passed += 1
		print("PASS ", label)
	else:
		failed += 1
		print("FAIL ", label)


# b1, b2 in assembly a1 (a mirror pair); b3 the original of an array row with copies b4, b5 (one family);
# b6 on its own.
const BOARDS := [
	{"id": "b1", "assembly": "a1", "mirror_plane": [[0, 0, 0], [1, 0, 0]]},
	{"id": "b2", "assembly": "a1"},
	{"id": "b3", "family": "f1", "array": "", "row": ""},
	{"id": "b4", "family": "f1", "array": "ar1", "row": "b3"},
	{"id": "b5", "family": "f1", "array": "ar1", "row": "b3"},
	{"id": "b6"},
]


func make() -> Array:
	var s := Selection.new()
	made.append(s)
	var d := FakeDoc.new()
	s.doc = d
	s.set_boards(BOARDS)
	var seen := {"selection": 0, "context": 0, "hidden": [], "links": 0, "say": []}
	s.selection_changed.connect(func(): seen["selection"] += 1)
	s.context_changed.connect(func(): seen["context"] += 1)
	s.hidden_changed.connect(func(by_op): seen["hidden"].append(by_op))
	s.links_changed.connect(func(): seen["links"] += 1)
	s.say.connect(func(t): seen["say"].append(t))
	return [s, d, seen]


func sorted(a: Array) -> Array:
	var b := a.duplicate(); b.sort(); return b


func _init() -> void:
	# --- what a board stands for ---
	var r := make(); var s = r[0]; var d = r[1]; var seen = r[2]
	var u: Dictionary = s.unit_of("b1")
	check("outside, an assembly's board stands for the assembly", u["kind"] == "assembly" and u["id"] == "a1"
		and sorted(u["bodies"]) == ["b1", "b2"])
	u = s.unit_of("b4")
	check("outside, an array copy stands for its row", u["kind"] == "row" and sorted(u["bodies"]) == ["b4", "b5"])
	check("a loose board stands for itself", s.unit_of("b6") == {"id": "b6", "kind": "board", "bodies": ["b6"]})
	check("no board, no unit", s.unit_of("") == {})
	check("outside, every board is in context", s.in_context("b1") and s.in_context("b6"))
	check("editing an assembly's board from outside is blocked, with a message",
		s.edit_blocked("b1") and seen["say"].size() == 1)
	check("a loose board isn't blocked", not s.edit_blocked("b6"))
	check("siblings: the rest of the family", sorted(s.siblings_of("b4")) == ["b3", "b5"])
	check("no family, no siblings", s.siblings_of("b6").is_empty())
	check("no mirror plane outside", s.mirror_plane_of_context().is_empty())

	# --- entering and leaving ---
	s.set_selection(["b6"])
	s.enter_context_of("b2")
	check("double-click enters the assembly", s.context == "assembly:a1" and s.context_assembly() == "a1")
	check("entering clears the selection", s.selection.is_empty() and seen["context"] == 1)
	check("inside, its boards stand for themselves", s.unit_of("b1")["kind"] == "board")
	check("inside, the rest is out of context", s.in_context("b2") and not s.in_context("b6"))
	check("inside, its boards can be edited", not s.edit_blocked("b1"))
	check("inside a mirror group, its plane", s.mirror_plane_of_context() == [Vector3.ZERO, Vector3(1, 0, 0)])
	s.enter_context_of("b4")
	check("can't enter another from inside", s.context == "assembly:a1")
	s.leave_context()
	check("Esc leaves", s.context == "" and seen["context"] == 2)
	s.enter_context_of("b5")
	check("double-click on a copy enters its row", s.context == "row:b3" and s.in_context("b4")
		and not s.in_context("b3") and s.context_assembly() == "")
	s.leave_context()
	s.enter_context_of("b6")
	check("a loose board has nothing to enter", s.context == "" and seen["context"] == 4)

	# --- hide and unhide ---
	r = make(); s = r[0]; d = r[1]; seen = r[2]
	s.hide_selected()
	check("hiding nothing says so and adds no op", d.ops.is_empty() and seen["say"].size() == 1)
	s.hover_body = "b2"
	s.hide_selected()
	check("H with nothing selected hides the assembly under the cursor",
		d.ops.size() == 1 and d.ops[0]["type"] == "hide" and sorted(d.ops[0]["targets"]) == ["b1", "b2"]
		and d.ops[0]["id"] == "hd1" and d.syncs == 1 and seen["hidden"] == [true])
	check("the hidden set doesn't change until refreshed (main does it as it draws)", s.body_hidden.is_empty())
	s.refresh_hidden()
	check("the hidden set follows the ops", s.body_hidden.has("b1") and s.body_hidden.has("b2") and s.is_hidden("b1"))
	s.set_selection(["b6", "b1"])
	s.hide_selected()
	check("already hidden boards are left out", d.ops.back()["targets"] == ["b6"])
	s.refresh_hidden()
	check("hiding takes the hidden boards out of the selection", s.selection == ["b1"])
	s.unhide("last")
	check("Unhide last brings back the last hide", d.ops.back()["targets"] == ["b6"] and d.ops.back()["hidden"] == false)
	s.refresh_hidden()
	check("unhidden boards are shown", not s.body_hidden.has("b6") and s.body_hidden.has("b1"))
	s.has_board = func(b): return b != "b2"
	s.unhide("all")
	check("Unhide all: every hidden board still in the model", d.ops.back()["targets"] == ["b1"])
	d.ops.pop_back(); s.refresh_hidden()
	check("undoing an unhide hides again at once", s.body_hidden.has("b1"))
	s.set_selection(["b6"])
	s.unhide("selected")
	check("Unhide selected with no hidden board selected says so", d.ops.back()["type"] == "hide"
		and d.ops.back()["targets"] == ["b6"] and seen["say"].back().begins_with("Select hidden"))
	s.toggle_hidden_geometry()
	check("View > Hidden geometry: hidden boards seen and pickable", s.show_hidden and not s.is_hidden("b1")
		and seen["hidden"].back() == false)
	s.set_selection(["b1", "b6"])
	s.toggle_hidden_geometry()
	check("turning it off drops hidden boards from the selection", s.selection == ["b6"] and s.is_hidden("b1"))

	# --- assembly, make unique, detach ---
	r = make(); s = r[0]; d = r[1]; seen = r[2]
	s.set_selection(["b1", "b6", "b3"])
	s.make_assembly()
	check("Make assembly takes the selected boards not already in one",
		d.ops[0]["type"] == "make_assembly" and d.ops[0]["targets"] == ["b6", "b3"] and d.ops[0]["new_id"] == "a1"
		and d.ops[0]["id"] == "as1" and s.selection.is_empty() and d.syncs == 1)
	s.make_assembly()
	check("Make assembly with nothing selected says so", d.ops.size() == 1 and seen["say"].size() == 2)
	s.hover_body = "b6"
	s.linked_op("make_unique")
	check("Make unique on an unlinked board says so", d.ops.size() == 1)
	s.hover_body = "b4"
	s.linked_op("make_unique")
	check("Make unique on a linked board", d.ops.back() == {"id": "mu1", "type": "make_unique", "targets": ["b4"]}
		and seen["links"] == 1)
	s.hover_body = "b3"
	s.linked_op("detach")
	check("Detach on a board that isn't a copy says so", d.ops.size() == 2)
	s.hover_body = "b5"
	s.linked_op("detach")
	check("Detach a copy from its array", d.ops.back() == {"id": "dt1", "type": "detach", "targets": ["b5"]}
		and d.syncs == 3)
	s.hover_body = ""
	s.linked_op("detach")
	check("pointing at nothing says so", d.ops.size() == 3 and seen["say"].back() == "Point at a board first")

	s.set_boards([{"id": "b1"}])
	check("new boards from FreeCAD replace the tables", s.body_assembly == {"b1": ""} and s.body_mirror_plane.is_empty())

	r = make(); s = r[0]; d = r[1]
	s.set_selection(["b3", "b6"])
	s.delete_selected()
	check("Delete is one action for the selected boards", d.ops == [{"id": "del1", "type": "delete", "targets": ["b3", "b6"]}] and d.syncs == 1)
	check("Delete clears selection and predicts removal", s.selection.is_empty() and s.is_hidden("b3"))
	s.toggle_hidden_geometry()
	check("Hidden geometry never reveals deleted boards", s.is_hidden("b3"))
	d.ops.clear(); s.refresh_hidden()
	check("Undo restores deleted boards immediately", not s.is_hidden("b3"))
	s.set_selection(["b1", "b6"]); s.enter_context_of("b1"); s.set_selection(["b1", "b6"])
	s.delete_selected()
	check("Delete respects entered context", d.ops.back()["targets"] == ["b1"])
	s.set_boards([{"id": "b4", "row": "b3"}, {"id": "b5", "row": "b3"}]); s.context = "row:b3"
	s.set_boards([{"id": "b5", "row": "b5"}])
	check("Entered row follows promoted original", s.context == "row:b5")

	for n in made: n.free()
	print("SELECTION TESTS: %d passed, %d failed" % [passed, failed])
	quit(1 if failed else 0)
