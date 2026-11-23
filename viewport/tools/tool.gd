extends RefCounted
## A tool owns its state; main.gd hands it the cursor, clicks, keys and typed values (T4). All tools snap
## through the one engine in inference.gd and use the capabilities offered by ctx.

const ToolContext := preload("res://tool_context.gd")
const Geo := preload("res://tool_geometry.gd")
# Independent policies (T33): pointer intent, native model resolution, and text only.
const ACCIDENTAL_DRAG_MM := 0.5
const GEOMETRY_TOLERANCE_MM := 0.001  # worker/common.py TOL; never the drag threshold
const DISTANCE_DISPLAY_FORMAT := "%d"  # existing whole-mm display; never round an op with this
const DIMENSIONS_DISPLAY_FORMAT := "%d, %d"

var ctx: ToolContext   # every tool gets this (setup_context)


static func pointer_distance_ok(distance: float, point_snap: bool) -> bool:
	return absf(distance) >= ACCIDENTAL_DRAG_MM or point_snap


static func clean_pointer_distance(distance: float) -> float:
	# Float32 mesh/ray arithmetic can put an integer plane a few microns away.
	# Only remove that noise near whole mm; retain fractional snaps and never touch typed values.
	var whole := roundf(distance)
	return whole if absf(distance - whole) < GEOMETRY_TOLERANCE_MM * 0.1 else distance


func setup_context(context: ToolContext) -> void:
	"""Every tool: what it may use (tool_context.gd)."""
	ctx = context


## forget any operation in progress (switching tools, Esc)
func reset() -> void:
	pass


## the hint shown in the status bar
func hint() -> String:
	return ""


func mouse_moved(_screen: Vector2) -> void:
	pass


func click(_screen: Vector2) -> void:
	pass


## a double click (Select: enter an assembly or array)
func double_click(_screen: Vector2) -> void:
	pass


## the left button let go (a tool started by press-and-drag finishes here)
func release(_screen: Vector2) -> void:
	pass


## in the middle of an operation: typed characters go to the measurement box
func busy() -> bool:
	return false


func in_gesture() -> bool:
	"""In the middle of drawing, pushing or moving (Esc cancels this before anything else, T31)."""
	return busy()


func accepts(ch: String) -> bool:
	return ch in "0123456789.,-+*/()^" or (ctx.ui.typed_text() != "" and ch.to_lower() in " \"'abcdefghijklmnopqrstuvwxyz")


## a key the tool handles itself (modifiers, axis locks); true = handled
func key(_e: InputEventKey) -> bool:
	return false


## a value typed into the measurement box, then Return
func typed(_txt: String) -> void:
	pass


## Whether the current measurement is raw text rather than a length.
func typed_raw() -> bool:
	return false


func vcb_label() -> String:
	return "Distance"


func vcb_value() -> String:
	return ""


## the tooltip by the cursor
func tip() -> String:
	return ""


# ---------------- press and drag, or click and click (I43) ----------------
# A tool starts on the press and follows the cursor at once; on release it decides what the press was. A drag
# (the cursor moved more than DRAG_PX with the button down) or a hold (over HOLD_MS) ends on release; anything
# else was a click, and the next click ends it. Rectangle, Push/Pull and Move share this rule.
const DRAG_PX := 6.0          # the cursor moved this far with the button down: it's a drag
const HOLD_MS := 300          # ...or the button stayed down this long
static var drag_px := DRAG_PX # live values (I63, preferences.gd); constants above stay the built-in defaults
static var hold_ms := HOLD_MS
var _press := {}              # while the button that started a gesture is down: {"at", "t0", "moved"}


func press_started(screen: Vector2) -> void:
	"""Call when a press starts a gesture."""
	_press = {"at": screen, "t0": Time.get_ticks_msec(), "moved": false}


func press_moved(screen: Vector2) -> void:
	"""Call on every cursor move."""
	if not _press.is_empty() and screen.distance_to(_press["at"]) > drag_px:
		_press["moved"] = true


func press_released() -> Dictionary:
	"""Call on release: {} if no gesture's press was down; else {"drag": true} for a drag or a hold (end the
	gesture now), {"drag": false} for a click (the next click ends it). "moved" says whether the cursor travelled."""
	if _press.is_empty(): return {}
	var p := _press
	_press = {}
	return {"drag": p["moved"] or Time.get_ticks_msec() - int(p["t0"]) >= hold_ms, "moved": p["moved"]}


func press_reset() -> void:
	_press = {}
