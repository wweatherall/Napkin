extends RefCounted
## A tool owns its state; main.gd hands it the cursor, clicks, keys and typed values (T4). All tools snap
## through the one engine in inference.gd (`infer`). `m` is the viewport (main.gd).

const Main := preload("res://main.gd")
const Inference := preload("res://inference.gd")
var m: Main
var infer: Inference


func setup(viewport: Main) -> void:
	m = viewport
	infer = viewport.infer


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
	return ch in "0123456789.,-+*/()^" or (m.vcb != "" and ch.to_lower() in " \"'abcdefghijklmnopqrstuvwxyz")


## a key the tool handles itself (modifiers, axis locks); true = handled
func key(_e: InputEventKey) -> bool:
	return false


## a value typed into the measurement box, then Return
func typed(_txt: String) -> void:
	pass


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
var _press := {}              # while the button that started a gesture is down: {"at", "t0", "moved"}


func press_started(screen: Vector2) -> void:
	"""Call when a press starts a gesture."""
	_press = {"at": screen, "t0": Time.get_ticks_msec(), "moved": false}


func press_moved(screen: Vector2) -> void:
	"""Call on every cursor move."""
	if not _press.is_empty() and screen.distance_to(_press["at"]) > DRAG_PX:
		_press["moved"] = true


func press_released() -> Dictionary:
	"""Call on release: {} if no gesture's press was down; else {"drag": true} for a drag or a hold (end the
	gesture now), {"drag": false} for a click (the next click ends it). "moved" says whether the cursor travelled."""
	if _press.is_empty(): return {}
	var p := _press
	_press = {}
	return {"drag": p["moved"] or Time.get_ticks_msec() - int(p["t0"]) >= HOLD_MS, "moved": p["moved"]}


func press_reset() -> void:
	_press = {}
