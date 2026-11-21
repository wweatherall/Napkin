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

static func format_length(mm: float, system: String, precision: int = 16) -> String:
	# precision is the imperial fraction denominator: 16 (default), 32, or 64.
	# Metric always displays 0.1 mm. Invalid system/precision/nonfinite => empty.
	if not is_finite(mm): return ""
	if system in ["metric", "mm"]:
		var rounded := snappedf(mm, 0.1)
		if is_zero_approx(rounded): rounded = 0.0
		var s := "%.1f" % rounded
		if s.ends_with(".0"): s = s.left(-2)
		return s + " mm"
	if system not in ["imperial", "in"] or precision not in [16, 32, 64]: return ""
	var ticks := roundi(absf(mm) / 25.4 * precision)
	# int conversion is explicit to avoid integer-division warnings in strict builds.
	var feet := int(float(ticks) / float(12 * precision))
	var rest := ticks % (12 * precision)
	var inches := int(float(rest) / float(precision))
	var numerator := rest % precision
	var denominator := precision
	while numerator > 0 and numerator % 2 == 0:
		numerator = int(float(numerator) / 2.0)
		denominator = int(float(denominator) / 2.0)
	# Under an inch reads 3/4", not 0 3/4".
	var result := str(inches)
	if numerator > 0:
		var fraction := "%d/%d" % [numerator, denominator]
		result = fraction if inches == 0 else result + " " + fraction
	result += "\""
	if feet > 0: result = "%d' %s" % [feet, result]
	if mm < 0.0 and ticks > 0: result = "-" + result
	return result
