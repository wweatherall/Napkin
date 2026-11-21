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
