extends SceneTree
const Units = preload("res://units.gd")
var passed := 0
var failed := 0

func check(label: String, condition: bool) -> void:
	if condition:
		passed += 1
		print("PASS ", label)
	else:
		failed += 1
		print("FAIL ", label)

func _init() -> void:
	var cases := {"19": 19.0, "19mm": 19.0, "1.9cm": 19.0, "0.019m": 19.0,
		"3/4\"": 19.05, "0.75in": 19.05, "1-1/2\"": 38.1, "1 1/2\"": 38.1,
		"1'": 304.8, "1'6\"": 457.2, "1'6-1/2\"": 469.9, "-12": -12.0,
		"+5": 5.0, " 3/4 in ": 19.05, "-1' 6\"": -457.2,
		".5 m": 500.0, "2 FT 3 IN": 685.8, "1 / 2 mm": 0.5, "0": 0.0}
	for input in cases:
		var result := Units.parse_length(input)
		check(input, result.ok and absf(result.mm - cases[input]) < 0.00001)
	check("default inches", is_equal_approx(Units.parse_length("3/4", "in").mm, 19.05))
	check("default cm", is_equal_approx(Units.parse_length("2", "cm").mm, 20.0))
	for input in ["", "abc", "3//4", "1/0", "3x", "/3", "1 2", "1mm junk", "1'6", "1in2in", "--2", "1--1/2", "1 -1/2", "1.2.3", "1mm 2cm", "1,5", "nan", "inf", "1e3", "1-2-3/4", "1'2'", "1/2/3", "1 +2", "2m-1m"]:
		var result := Units.parse_length(input)
		check("reject " + input, not result.ok and not result.error.is_empty())
	check("bad default unit", not Units.parse_length("2", "yards").ok)
	var pair := Units.parse_pair("1' 6\", 3/4\"")
	check("pair", pair.ok and is_equal_approx(pair.a_mm, 457.2) and is_equal_approx(pair.b_mm, 19.05))
	for input in ["1", "1,2,3", ",2", "1,", "bad,2"]:
		check("reject pair " + input, not Units.parse_pair(input).ok)
	check("metric trim", Units.format_length(19.0, "metric") == "19 mm")
	check("metric round", Units.format_length(19.06, "metric") == "19.1 mm")
	check("fraction reduced", Units.format_length(38.1, "imperial") == "1 1/2\"")
	check("carry feet", Units.format_length(304.79, "imperial") == "1' 0\"")
	check("negative zero", Units.format_length(-0.01, "imperial") == "0\"")
	check("1/64", Units.format_length(25.4 / 64, "imperial", 64) == "0 1/64\"")
	for mm in [-1234.567, -25.4, -0.01, 0.0, 0.4, 19.05, 304.8, 2000.123]:
		for denominator in [16, 32, 64]:
			var formatted := Units.format_length(mm, "imperial", denominator)
			var parsed := Units.parse_length(formatted)
			check("round trip " + formatted, parsed.ok and absf(parsed.mm - mm) <= 25.4 / denominator / 2.0 + 0.000001)
		var parsed := Units.parse_length(Units.format_length(mm, "metric"))
		check("metric round trip " + str(mm), parsed.ok and absf(parsed.mm - mm) <= 0.050001)
	print("UNITS TESTS: %d passed, %d failed" % [passed, failed])
	quit(1 if failed else 0)
