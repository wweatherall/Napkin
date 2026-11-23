extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 5c. Assemblies you enter (T20, I32): select two boards, Cmd+G, move them as one, enter, draw inside, leave
	await harness._fresh("assembly", harness._plank(1, Vector3.ZERO, Vector3(100, 50, 18)) + harness._plank(2, Vector3(0, 100, 0), Vector3(100, 50, 18))
		+ harness._plank(3, Vector3(300, 0, 0), Vector3(100, 50, 18)))
	await harness._view(Vector3(200, 75, 0), -25, -50, 1.4)
	await harness._key(KEY_SPACE)
	await harness._click_at(Vector3(50, 25, 18))
	await harness._key_state(KEY_SHIFT, true)
	await harness._click_at(Vector3(50, 125, 18))
	await harness._key_state(KEY_SHIFT, false)
	harness._ok("Select: click, then Shift-click adds", m.selection == [harness.id("b1"), harness.id("b2")], m.selection)
	await harness._key_cmd(KEY_G)
	await harness._wait_wave()
	harness._ok("Cmd+G makes an assembly of them", m.body_assembly.get(harness.id("b1"), "") != "" and m.body_assembly[harness.id("b1")] == m.body_assembly.get(harness.id("b2"), "")
		and m.body_assembly.get(harness.id("b3"), "") == "", m.body_assembly)
	harness._ok("from outside, a board stands for its assembly", m.sel.unit_of(harness.id("b1"))["bodies"].size() == 2, m.sel.unit_of(harness.id("b1")))
	m.set_tool("move")
	await harness._grab(Vector3(50, 25, 18))
	await harness._key(KEY_UP)
	await harness._drag_to(Vector3(50, 25, 60), 6)
	await harness._type("100\n")
	await harness._wait_wave()
	harness._ok("moving one of its boards moves the whole assembly", harness._bbox(harness.id("b1"))[2] == 100.0 and harness._bbox(harness.id("b2"))[2] == 100.0 and harness._bbox(harness.id("b3"))[2] == 0.0,
		[harness._bbox(harness.id("b1")), harness._bbox(harness.id("b2")), harness._bbox(harness.id("b3"))])
	m.set_tool("rect")
	var n_rects: int = m.rects.size()
	await harness._click_at(Vector3(50, 25, 118))
	harness._ok("from outside, drawing on an assembly's board is refused with a hint", m.rects.size() == n_rects and not m.tools["rect"].state.get("active", false),
		m.ui_sync.text)
	await harness._key(KEY_ESCAPE)
	m.set_tool("select")
	await harness._double_click_at(Vector3(50, 25, 118))
	harness._ok("double-click enters the assembly", m.context == "assembly:" + m.body_assembly[harness.id("b1")] and not m.sel.in_context(harness.id("b3")), m.context)
	m.set_tool("rect")
	await harness._rect(Vector3(20, 10, 118), Vector3(60, 40, 118), "40,30")
	await harness._push(Vector3(40, 25, 118), Vector3(40, 25, 108), "-18")
	await harness._wait_wave()
	harness._ok("inside, a hole on its board works", harness._bodies()[harness.id("b1")]["volume_mm3"] == 100.0 * 50 * 18 - 40 * 30 * 18, harness._bodies()[harness.id("b1")]["volume_mm3"])
	await harness._key(KEY_ESCAPE)
	await harness._key(KEY_ESCAPE)
	harness._ok("Esc leaves", m.context == "", m.context)
	# Copying a whole assembly (I47): the copy is a new assembly of linked copies; rows are checked in assembly_row.gd
	m.set_tool("move")
	var before := m.ops.size()
	await harness._grab(Vector3(50, 25, 118))
	await harness._key(KEY_ALT)
	await harness._key(KEY_RIGHT)
	await harness._drag_to(Vector3(150, 25, 118), 6)
	await harness._type("500\n")
	await harness._wait_wave()
	var made: Array = m.ops.back().get("new_ids", [])
	var old_aid: String = m.body_assembly.get(harness.id("b1"), "")
	var new_aid: String = m.body_assembly.get(made[0], "") if made.size() == 2 else ""
	harness._ok("copying an assembly makes a new assembly of its boards", m.ops.size() == before + 1 and new_aid != "" and new_aid != old_aid
		and m.body_assembly.get(made[1], "") == new_aid and m.sel.unit_of(harness.id("b1"))["bodies"].size() == 2, [m.ops.back(), m.body_assembly])
