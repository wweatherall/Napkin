extends RefCounted
## UI scenario; shared input, timing and assertions live in harness.gd.

const Main := preload("res://main.gd")
const Harness := preload("res://tests/harness.gd")
var harness: Harness
var m: Main:
	get: return harness.m


func run() -> void:
	# 9. Switching models (T8)
	harness._q_lap("models")
	var a: String = m.model_path
	await harness._fresh("models_b", harness._plank(1, Vector3.ZERO, Vector3(150, 200, 40)), true)
	m.switch_model(a)
	while not m.opened: await harness._frames(1)
	await harness._wait_confirm()
	harness._ok("switching back reopens the other model's boards", harness._shown_ids() == [harness.id("b1"), harness.id("b3")] and m.ops.size() == 5, [harness._shown_ids(), m.ops.size()])
	harness._ok("the menus exist", m.menus.menus.keys() == ["File", "Edit", "Tools", "View"] or not NativeMenu.has_feature(NativeMenu.FEATURE_GLOBAL_MENU), m.menus.menus.keys())
