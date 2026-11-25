extends RefCounted
## Lengths are millimetres internally. Commas separate pairs, never decimals.
## Array syntax (3x, /3) belongs to tools and is deliberately rejected here.
## A minus between numbers always means subtraction (William, 2026-11-21: 1-1/2" is 1/2", 1'-6" is 6"); this
## parser does no arithmetic, so it rejects those forms. Mixed numbers take a space: 1 1/2", 1' 6 1/2".

static func _error(text: String) -> Dictionary:
	return {"ok": false, "mm": 0.0, "error": "can't read '%s'" % text}

static func _factor(unit: String) -> float:
	match unit:
		"mm": return 1.0
		"cm": return 10.0
		"m": return 1000.0
		"in", "\"": return 25.4
		"ft", "'": return 304.8
	return 0.0

static func _number(text: String) -> Dictionary:
	var re := RegEx.new()
	re.compile("^(?:(\\d+) +)?(\\d+)\\s*/\\s*(\\d+)$")
	var fraction := re.search(text)
	if fraction:
		var denominator := float(fraction.get_string(3))
		if denominator == 0.0:
			return _error(text)
		var value := float(fraction.get_string(2)) / denominator
		if not fraction.get_string(1).is_empty():
			value += float(fraction.get_string(1))
		return {"ok": is_finite(value), "value": value}
	re.compile("^(?:\\d+(?:\\.\\d*)?|\\.\\d+)$")
	if not re.search(text):
		return _error(text)
	var value := float(text)
	return {"ok": is_finite(value), "value": value}

static func parse_length(text: String, default_unit := "mm") -> Dictionary:
	var original := text
	var remaining := text.strip_edges().to_lower()
	var default_factor := _factor(default_unit.strip_edges().to_lower())
	if remaining.is_empty() or default_factor == 0.0:
		return _error(original)
	var sign_value := 1.0
	if remaining.begins_with("-") or remaining.begins_with("+"):
		if remaining.begins_with("-"): sign_value = -1.0
		remaining = remaining.substr(1).strip_edges()
	var re := RegEx.new()
	# Greedy mixed fractions before plain decimals; every character must be consumed.
	re.compile("^((?:\\d+ +)?\\d+\\s*/\\s*\\d+|(?:\\d+(?:\\.\\d*)?|\\.\\d+))\\s*(mm|cm|ft|in|m|\"|')?")
	var total := 0.0
	var units: Array[String] = []
	while not remaining.is_empty():
		var found := re.search(remaining)
		if not found:
			return _error(original)
		var numeric := _number(found.get_string(1))
		if not numeric.ok:
			return _error(original)
		var unit := found.get_string(2)
		var factor := default_factor if unit.is_empty() else _factor(unit)
		units.append(unit)
		total += float(numeric.value) * factor
		remaining = remaining.substr(found.get_end()).strip_edges()
		# Only compound feet + explicit inches is accepted; no ambiguous bare tails.
		if units.size() > 2 or (not remaining.is_empty() and unit not in ["ft", "'"]):
			return _error(original)
	if units.is_empty() or (units.size() == 2 and (units[0] not in ["ft", "'"] or units[1] not in ["in", "\""])):
		return _error(original)
	if not is_finite(total):
		return _error(original)
	return {"ok": true, "mm": sign_value * total, "error": ""}

static func parse_pair(text: String, default_unit := "mm") -> Dictionary:
	var parts := text.split(",", true)
	if parts.size() != 2:
		return {"ok": false, "a_mm": 0.0, "b_mm": 0.0, "error": "enter two lengths separated by a comma"}
	var a := parse_length(parts[0], default_unit)
	var b := parse_length(parts[1], default_unit)
	if not a.ok or not b.ok:
		return {"ok": false, "a_mm": 0.0, "b_mm": 0.0, "error": a.error if not a.ok else b.error}
	return {"ok": true, "a_mm": a.mm, "b_mm": b.mm, "error": ""}

# ---------- the same answer FreeCAD gives, worked out here ----------
## evaluate_length() answers what worker/length_input.py evaluate() would (FreeCAD's expressions: arithmetic,
## mixed units, I35's minus), so a typed value never waits for the worker. It ports that file's rewriting step by
## step, then evaluates the result with FreeCAD's rules: ^ reads left to right and after a leading minus (-2^2 = 4),
## trig takes degrees, a unit belongs to the number just before it. Whenever it isn't sure (a unit power like
## 2mm^2, a unit after a bracket, an unknown word) it declines ({ok: false, declined: true}) and the caller asks
## FreeCAD, which also gives the real error message. It must never answer differently from FreeCAD:
## tests/length_cases.json (made by FreeCAD, tools/length_cases.py) checks every answer it gives.
const _UNITS := {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "\"": 25.4, "ft": 304.8, "'": 304.8}
const _FUNCS := ["sqrt", "abs", "sin", "cos", "tan"]
const _WORDS := ["mm", "cm", "m", "in", "ft", "sqrt", "abs", "sin", "cos", "tan", "pi", "e"]

static func _declined() -> Dictionary:
	return {"ok": false, "mm": 0.0, "declined": true, "error": ""}

static func _rx(pattern: String) -> RegEx:
	var re := RegEx.new()
	re.compile(pattern)
	return re

static func evaluate_length(text: String, default_unit := "mm") -> Dictionary:
	var t := text.strip_edges()
	if not default_unit in ["mm", "cm", "m", "in", "ft"] or t.is_empty() or t.length() > 512:
		return _declined()
	# The rewriting in length_input.py, in the same order.
	var negative := t.begins_with("-") and _rx("(?:ft|')\\s*\\d").search(t) != null
	if negative: t = t.substr(1)
	t = _rx("(\\d+) +(\\d+\\s*/\\s*\\d+)\\s*(in|ft|mm|cm|m|['\"])").sub(t, "($1 + $2) * 1 $3", true)
	t = _rx("(?<=\\d)\\s*(['\"])\\s*(?=[\\d(])").sub(t, "$1 + ", true)
	t = _rx("(ft|in)\\s+(?=[\\d(])").sub(t, "$1 + ", true)
	var scalar := _rx("^([0-9 .+*/()^-]+)\\s*(mm|cm|m|in|ft|['\"])$").search(t)
	if scalar: t = "(" + scalar.get_string(1) + ") * 1 " + scalar.get_string(2)
	t = _rx("(\\d+\\s*/\\s*\\d+)\\s*(in|ft|mm|cm|m|['\"])").sub(t, "($1) * 1 $2", true)
	for w in _rx("[A-Za-z_]+").search_all(t):
		if not w.get_string() in _WORDS: return _declined()
	if _rx("[^0-9A-Za-z_ .+*/()^'\"-]").search(t) != null: return _declined()
	var tokens := _tokens(t)
	if tokens.is_empty(): return _declined()
	var at := [0]
	var q := _expr(tokens, at)
	if q.is_empty() or at[0] != tokens.size(): return _declined()
	var mm: float
	if q[1] == 0: mm = q[0] * _UNITS[default_unit]          # a bare number is in the default unit
	elif q[1] == 1: mm = q[0]
	else: return _declined()
	if not is_finite(mm): return _declined()
	return {"ok": true, "mm": -mm if negative else mm, "declined": false, "error": ""}

static func evaluate_pair(text: String, default_unit := "mm") -> Dictionary:
	var parts := text.split(",", true)
	if parts.size() != 2: return {"ok": false, "a_mm": 0.0, "b_mm": 0.0, "declined": true}
	var a := evaluate_length(parts[0], default_unit)
	var b := evaluate_length(parts[1], default_unit)
	if not a.ok or not b.ok: return {"ok": false, "a_mm": 0.0, "b_mm": 0.0, "declined": true}
	return {"ok": true, "a_mm": a.mm, "b_mm": b.mm, "declined": false}

## Tokens: [kind, value]: "n" number, "u" unit, "w" word (function or constant), "o" operator or bracket.
static func _tokens(t: String) -> Array:
	var out := []
	var number := _rx("^(?:\\d+\\.\\d+|\\d+|\\.\\d+)(?:[eE][+-]?\\d+)?")
	var word := _rx("^[A-Za-z_][A-Za-z_0-9]*")
	var i := 0
	while i < t.length():
		var c := t[i]
		if c == " ": i += 1; continue
		var rest := t.substr(i)
		var n := number.search(rest)
		if n:
			var after := rest.substr(n.get_end(), 1)
			if after in [".", "_"] or (after != "" and after.is_valid_int()): return []   # 1.5.5, 1..5, 5.
			out.append(["n", n.get_string().to_float()])
			i += n.get_end(); continue
		var w := word.search(rest)
		if w:
			var name := w.get_string()
			out.append(["u" if _UNITS.has(name) else "w", name])
			i += w.get_end(); continue
		if c in ["'", "\""]: out.append(["u", c]); i += 1; continue
		if c in ["+", "-", "*", "/", "^", "(", ")"]: out.append(["o", c]); i += 1; continue
		return []
	return out

static func _peek(tokens: Array, at: Array, value: String) -> bool:
	return at[0] < tokens.size() and tokens[at[0]][0] == "o" and tokens[at[0]][1] == value

## Each returns [value, length power] (0 = a plain number, 1 = a length, in mm), or [] to decline.
static func _expr(tokens: Array, at: Array) -> Array:
	var a := _term(tokens, at)
	while not a.is_empty() and (_peek(tokens, at, "+") or _peek(tokens, at, "-")):
		var op: String = tokens[at[0]][1]; at[0] += 1
		var b := _term(tokens, at)
		if b.is_empty() or b[1] != a[1]: return []           # FreeCAD: unit mismatch
		a = [a[0] + b[0] if op == "+" else a[0] - b[0], a[1]]
	return a

static func _term(tokens: Array, at: Array) -> Array:
	var a := _power(tokens, at)
	while not a.is_empty() and (_peek(tokens, at, "*") or _peek(tokens, at, "/")):
		var op: String = tokens[at[0]][1]; at[0] += 1
		var b := _power(tokens, at)
		if b.is_empty(): return []
		if op == "*": a = [a[0] * b[0], a[1] + b[1]]
		elif b[0] == 0.0: return []                          # FreeCAD: division by zero
		else: a = [a[0] / b[0], a[1] - b[1]]
	return a

static func _power(tokens: Array, at: Array) -> Array:
	var a := _unary(tokens, at)
	while not a.is_empty() and _peek(tokens, at, "^"):          # left to right: 2^3^2 = 64
		at[0] += 1
		var b := _unary(tokens, at)
		if b.is_empty() or a[1] != 0 or b[1] != 0: return []  # powers of units: let FreeCAD decide
		var v := pow(a[0], b[0])
		if not is_finite(v): return []
		a = [v, 0]
	return a

static func _unary(tokens: Array, at: Array) -> Array:
	if _peek(tokens, at, "-") or _peek(tokens, at, "+"):
		var minus: bool = tokens[at[0]][1] == "-"; at[0] += 1
		var a := _unary(tokens, at)
		if a.is_empty(): return []
		return [-a[0] if minus else a[0], a[1]]
	return _primary(tokens, at)

static func _primary(tokens: Array, at: Array) -> Array:
	if at[0] >= tokens.size(): return []
	var tok: Array = tokens[at[0]]
	at[0] += 1
	if tok[0] == "n":
		var v: float = tok[1]
		if at[0] < tokens.size() and tokens[at[0]][0] == "u":     # a unit belongs to the number before it
			v *= _UNITS[tokens[at[0]][1]]; at[0] += 1
			if _peek(tokens, at, "^"): return []                 # 2mm^2 is a unit power in FreeCAD
			return [v, 1]
		return [v, 0]
	if tok[0] == "o" and tok[1] == "(":
		var a := _expr(tokens, at)
		if a.is_empty() or not _peek(tokens, at, ")"): return []
		at[0] += 1
		return a
	if tok[0] == "w":
		if tok[1] == "pi": return [PI, 0]
		if tok[1] == "e": return [exp(1.0), 0]
		if tok[1] in _FUNCS and _peek(tokens, at, "("):
			at[0] += 1
			var a := _expr(tokens, at)
			if a.is_empty() or not _peek(tokens, at, ")"): return []
			at[0] += 1
			match tok[1]:
				"abs": return [absf(a[0]), a[1]]
				"sqrt":
					if a[0] < 0.0 or a[1] % 2 != 0: return []
					return [sqrt(a[0]), a[1] / 2]
				_:
					if a[1] != 0: return []                      # trig takes a plain number of degrees
					var r := deg_to_rad(a[0])
					return [sin(r) if tok[1] == "sin" else cos(r) if tok[1] == "cos" else tan(r), 0]
	return []

# ---------- display formatting (I57, I59, I62) ----------
## Canonical display unit specs: "<format>:<rounding>". Saved in doc.Meta["ShopSketchUnits"] and settings.cfg.
## Default (I57): fractional inches at 1/16". Tests start in mm:0.1 so existing bare-number mm suites stay unchanged.
const DEFAULT_SPEC := "in-frac:1/16"
const TEST_SPEC := "mm:0.1"
const ROUND_TOL_MM := 0.0005  # absorbs float32 mesh/ray noise (~1e-4 mm) while catching any real >=0.001 mm rounding

const FORMAT_ORDER := ["ft-in", "in-frac", "in-dec", "m", "cm", "mm"]
const FORMATS := {
	"ft-in": {"label": "Feet and inches (8' 3 1/4\")", "unit": "in", "default": "1/16", "precisions": ["1/8", "1/16", "1/32", "1/64"]},
	"in-frac": {"label": "Inches as fractions (99 1/4\")", "unit": "in", "default": "1/16", "precisions": ["1/8", "1/16", "1/32", "1/64"]},
	"in-dec": {"label": "Inches as decimals (99.25\")", "unit": "in", "default": "0.01", "precisions": ["0.1", "0.01", "0.001"]},
	"m": {"label": "Metric — m", "unit": "m", "default": "0.001", "precisions": ["0.1", "0.01", "0.001"]},
	"cm": {"label": "Metric — cm", "unit": "cm", "default": "0.1", "precisions": ["1", "0.1", "0.01"]},
	"mm": {"label": "Metric — mm", "unit": "mm", "default": "0.1", "precisions": ["1", "0.1", "0.01"]},
}


static func parse_spec(spec: String) -> Dictionary:
	"""Validate a canonical '<format>:<rounding>' string. Returns {ok, spec, format, precision, unit} or {ok: false}."""
	var parts := spec.strip_edges().split(":", true)
	if parts.size() != 2: return {"ok": false}
	var fmt: String = parts[0]
	var prec: String = parts[1]
	if not FORMATS.has(fmt): return {"ok": false}
	var info: Dictionary = FORMATS[fmt]
	if prec not in info["precisions"]: return {"ok": false}
	return {"ok": true, "spec": fmt + ":" + prec, "format": fmt, "precision": prec, "unit": info["unit"]}


static func default_unit_of(spec: String) -> String:
	"""The unit a bare typed number takes for this display spec (I59)."""
	var parsed := parse_spec(spec)
	return parsed["unit"] if parsed.ok else FORMATS[parse_spec(DEFAULT_SPEC)["format"]]["unit"]


static func detect_typed_spec(text: String) -> String:
	"""Infer a canonical display unit spec from the first explicit unit in a typed length or pair (T124, I67).
	Returns '' for bare numbers, array counts (3x, /3), or strings without a recognized unit suffix."""
	var raw := text.strip_edges().to_lower()
	if raw.is_empty(): return ""
	if _rx("^(?:[0-9]+x|[x*][0-9]+|/[0-9]+)$").search(raw) != null: return ""
	var unit_re := _rx("(?<![a-z_0-9.])((?:\\d+\\s+)?\\d+\\s*/\\s*\\d+|(?:\\d+\\.\\d*|\\.\\d+)|\\d+|\\))\\s*(mm|cm|ft|in|m|\"|')(?![a-z_])")
	for part in raw.split(",", true):
		var matches := unit_re.search_all(part)
		if matches.is_empty(): continue
		var first_spec := ""
		var has_ft := false
		for m in matches:
			var num: String = m.get_string(1)
			var u: String = m.get_string(2)
			if u in ["ft", "'"]:
				has_ft = true
				if first_spec == "": first_spec = "ft-in:1/16"
			elif first_spec == "":
				match u:
					"in", "\"":
						var is_dec := num.contains(".") and not num.contains("/")
						first_spec = "in-dec:0.01" if is_dec else "in-frac:1/16"
					"mm": first_spec = "mm:0.1"
					"cm": first_spec = "cm:0.1"
					"m": first_spec = "m:0.01"
		if has_ft and first_spec in ["in-frac:1/16", "in-dec:0.01", "ft-in:1/16"]:
			return "ft-in:1/16"
		if first_spec != "":
			return first_spec
	return ""


static func precision_label(fmt: String, prec: String) -> String:
	if fmt in ["ft-in", "in-frac", "in-dec"]: return prec + "\""
	return prec + " " + fmt


static func with_format(spec: String, new_fmt: String) -> String:
	"""Switch format, keeping the current rounding if the new format offers it, else its default."""
	if not FORMATS.has(new_fmt): return DEFAULT_SPEC
	var cur := parse_spec(spec)
	var prec: String = cur["precision"] if cur.ok and cur["precision"] in FORMATS[new_fmt]["precisions"] else FORMATS[new_fmt]["default"]
	return new_fmt + ":" + prec


static func with_precision(spec: String, new_prec: String) -> String:
	"""Switch rounding within the current format."""
	var cur := parse_spec(spec)
	if not cur.ok: cur = parse_spec(DEFAULT_SPEC)
	var fmt: String = cur["format"]
	if new_prec not in FORMATS[fmt]["precisions"]: return cur["spec"]
	return fmt + ":" + new_prec


static func _resolve_spec(system_or_spec: String, precision: int) -> Dictionary:
	var parsed := parse_spec(system_or_spec)
	if parsed.ok: return parsed
	if system_or_spec in ["metric", "mm"] and precision == 0:
		return parse_spec("mm:0.1")
	if system_or_spec in ["imperial", "in"]:
		var denom := 16 if precision == 0 else precision
		return parse_spec("ft-in:1/%d" % denom)
	if FORMATS.has(system_or_spec) and precision == 0:
		return parse_spec(system_or_spec + ":" + FORMATS[system_or_spec]["default"])
	return {"ok": false}


static func _format_fraction_inches(mm: float, denom: int, with_feet: bool) -> String:
	var ticks := roundi(absf(mm) / 25.4 * float(denom) + 1e-9)
	var rounded_mm := float(ticks) * 25.4 / float(denom)
	if mm < 0.0 and ticks > 0: rounded_mm = -rounded_mm
	var approx := absf(mm - rounded_mm) > ROUND_TOL_MM
	var feet := 0
	var rest := ticks
	if with_feet:
		feet = floori(float(ticks) / float(12 * denom))
		rest = ticks % (12 * denom)
	var inches := floori(float(rest) / float(denom))
	var numerator := rest % denom
	var denominator := denom
	while numerator > 0 and numerator % 2 == 0:
		numerator = floori(float(numerator) / 2.0)
		denominator = floori(float(denominator) / 2.0)
	var result := str(inches)
	if numerator > 0:
		var fraction := "%d/%d" % [numerator, denominator]
		result = fraction if inches == 0 else result + " " + fraction
	result += "\""
	if feet > 0: result = "%d' %s" % [feet, result]
	if mm < 0.0 and ticks > 0: result = "-" + result
	return ("~" + result) if approx else result


static func _format_decimal(mm: float, factor: float, suffix: String, prec: String) -> String:
	var dot := prec.find(".")
	var dec := 0 if dot < 0 else (prec.length() - dot - 1)
	var scale := pow(10.0, float(dec))
	var val := mm / factor
	var steps: float = round(absf(val) * scale + 1e-9)
	var rounded_abs: float = steps / scale
	var rounded_mm: float = (-rounded_abs if (val < 0.0 and steps > 0.0) else rounded_abs) * factor
	var approx := absf(mm - rounded_mm) > ROUND_TOL_MM
	var s := ("%.*f" % [dec, rounded_abs]) if dec > 0 else ("%.0f" % rounded_abs)
	if dec > 0:
		while s.ends_with("0"): s = s.left(-1)
		if s.ends_with("."): s = s.left(-1)
	var result := ("-" if (val < 0.0 and steps > 0.0) else "") + s + suffix
	return ("~" + result) if approx else result


static func format_length(mm: float, system_or_spec: String = DEFAULT_SPEC, precision: int = 0) -> String:
	"""Format a length in mm for display (I57). Accepts a canonical spec ('ft-in:1/16', 'in-frac:1/16',
	'in-dec:0.01', 'm:0.001', 'cm:0.1', 'mm:0.1') or legacy ('metric'/'imperial', denom). Prepends '~' when
	rounding changed the length beyond ROUND_TOL_MM. Non-finite or invalid spec => ''."""
	if not is_finite(mm): return ""
	var spec := _resolve_spec(system_or_spec, precision)
	if not spec.ok: return ""
	var fmt: String = spec["format"]
	var prec: String = spec["precision"]
	match fmt:
		"ft-in": return _format_fraction_inches(mm, int(prec.substr(2)), true)
		"in-frac": return _format_fraction_inches(mm, int(prec.substr(2)), false)
		"in-dec": return _format_decimal(mm, 25.4, "\"", prec)
		"m": return _format_decimal(mm, 1000.0, " m", prec)
		"cm": return _format_decimal(mm, 10.0, " cm", prec)
		"mm": return _format_decimal(mm, 1.0, " mm", prec)
	return ""
