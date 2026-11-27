"""Writes tests/length_cases.json: what FreeCAD's length input (worker/length_input.py evaluate) gives for a fixed
set of typed lengths, plus random expressions built from the same pieces people type. Both sides are checked
against it: worker/test_length_input.py (FreeCAD still gives these answers) and viewport/test_units.gd (the
local evaluate_length gives the same answer, or declines). Regenerate after changing length_input.py:

  freecadcmd tools/length_cases.py
"""
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[-1] if sys.argv[-1].endswith(".py") else __file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
sys.dont_write_bytecode = True

CURATED = r"""150|19|19mm|1.9cm|0.019m|3/4"|0.75in|1 1/2"|1 1/2 in|1'|1'6"|1' 6"|1' 6 1/2"|1'6 1/2"|-12|+5| 3/4 in |
5in + 23mm|1in + 5mm|(24in - 2*19mm)/3|2 * 19mm|-1ft 6in|1-1/2"|1'-6"|1ft 6in|1 ft 6 in|2ft - 3in|-1' 6"|
-2^2|2^2|2^3^2|-(2)^2|8/2/2|2*3+4|2+3*4|(1+2)*3|2*3^2|2^3*2|sin(30)|sin(30)*10|cos(60)*10|tan(45)*10|sqrt(16)|
sqrt(16mm)|abs(-5)|abs(-5mm)|pi|pi*10|e|2e3|1e2mm|1.5e1|.5|5.|1 + 2 mm|6/2mm|2mm*3|2*3mm|mm|2 mm|1in + 5|1/0|
0/0|3 kg|1 1/2|--5|-(-5)|5-|(5|5)|2(3)|2 3|1in 2in|3/4|1/2/2"|(1/2)"|2^0.5*1mm|10mm/2mm|10mm/2|2*(3mm+4mm)|
1m - 1mm|1cm+1mm|0.5ft|1"+1"|1""|"|5 in|5in|5 IN|5Mm|1 m|1m|1mm + 1|-(1in)|-1in|-1/2"|1 -1/2"|1 - 1/2"|1+1/2"|
3/4"+1"|1 1/2" + 1|12 1/2 mm|2 1/4'|1' 1 1/2"|-1' 1 1/2"|2^-1|(1+1)mm|(1+1)mm + 1in|2*mm|1mm 2mm|sin(30mm)|
2mm^2|4mm^0.5|sqrt(16mm^2)|sqrt(16mm*1mm)|abs(1in)|2^(1/2)|(2mm)^2/1mm|1in*2|1in/2in*3mm|-sqrt(4)|2--1|2+-1|
2*-1|2^2^0.5|1in^1|pi mm|2pi|cos(0)|1e400|1/3|1 / 2 mm|1 in + 1 ft|2 ' 3 "|2'3"|1ft 6|1' 6|6" 1'|1in 2|1in 2mm|
1ft (6in)|1'(6")|1' (6+1)"|sqrt(2)*sqrt(2)mm|1.5.5|1..5|00012|1,5|1e|e2|2e|pi2|sqrt 4|abs(-3)mm|-abs(-3mm)|
((2))|()|2+|*2|2**3|1mm/0mm|10cm/2cm*1mm|(1in)"|1 1/2" 1/2"|1-1/2 in|1 + 1/2 in|1/2 + 1/4 in|-1 1/2"|
- 1' 6"|-1 ft 6 in|-1ft - 6in|-2ft 3in + 1in|12 1/2|1 1/2mm + 1mm|3/4 in + 1 1/2 in|1 1/2 in - 3/4 in|10mm*2/4|
2.5mm*2.5|1in*1in/1in|sin(90)*1in|cos(180)*2in|tan(0)|0|-0|1/16"|15/16"|23 15/16"|8' 11 15/16"|1/64 in"""

CURATED = [c for c in CURATED.replace("\n", "").split("|") if c != ""]

DEFAULT_UNIT = [
    ("12", "in"),
    ("0.75", "in"),
    ("3/4", "in"),
    ("2 + 3", "in"),
    ("(24 - 2) / 4", "in"),
    ("-6", "in"),
    ("0", "in"),
    ("19mm", "in"),
    ("1ft", "in"),
    ("1' 6\"", "in"),
    ("1 1/2\"", "in"),
    ("8' 3 1/4\"", "in"),
    ("99 1/4\"", "in"),
    ("99.25\"", "in"),
    ("1in + 5mm", "in"),
    ("1/0", "in"),
    ("2 + 19mm", "in"),
    ("2", "cm"),
    ("12.5", "cm"),
    ("1.5", "m"),
    ("0.25", "m"),
]


def pieces(rng):
    """Numbers and lengths the way people type them."""
    n = rng.choice([str(rng.randint(0, 40)), "%d.%d" % (rng.randint(0, 9), rng.randint(0, 99)),
                    ".%d" % rng.randint(1, 9), "%d/%d" % (rng.randint(1, 15), rng.choice([2, 4, 8, 16, 3])),
                    "%d %d/%d" % (rng.randint(1, 12), rng.randint(1, 7), 8)])
    unit = rng.choice(["", "", "mm", "cm", "m", "in", "ft", "'", '"', " mm", " in", " ft"])
    if rng.random() < 0.15:
        return "%d' %s\"" % (rng.randint(1, 9), rng.choice(["3", "6 1/2", "11", "0", "1/4"]))
    if rng.random() < 0.05:
        return rng.choice(["pi", "e", "sqrt(%d)" % rng.randint(0, 50), "abs(-%d)" % rng.randint(0, 9),
                           "sin(%d)" % rng.choice([0, 30, 45, 90]), "cos(%d)" % rng.choice([0, 60, 180])])
    return n + unit


def expression(rng, depth=0):
    if depth > 2 or rng.random() < 0.4:
        e = pieces(rng)
    else:
        e = expression(rng, depth + 1) + rng.choice([" + ", " - ", "+", "-", " * ", "*", " / ", "/", "^", " "]) + \
            expression(rng, depth + 1)
    if rng.random() < 0.15:
        e = "(" + e + ")"
    if rng.random() < 0.1:
        e = "-" + e
    return e


def main():
    if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
        print(__doc__)
        return
    from length_input import evaluate
    rng = random.Random(42)
    texts = list(dict.fromkeys(CURATED))
    while len(texts) < 2500:
        t = expression(rng)
        if t not in texts:
            texts.append(t)
    cases = []
    for t in texts:
        try:
            mm = evaluate(t)
        except Exception:
            mm = None
        cases.append({"text": t, "mm": mm})
    for t, unit in DEFAULT_UNIT:
        try:
            mm = evaluate(t, unit)
        except Exception:
            mm = None
        cases.append({"text": t, "default_unit": unit, "mm": mm})
    out = os.path.join(ROOT, "tests", "length_cases.json")
    with open(out, "w") as f:
        json.dump({"made_by": "tools/length_cases.py with FreeCAD's length_input.evaluate", "cases": cases}, f,
                  indent=0)
    print("LENGTH CASES: %d written (%d lengths, %d errors) to %s" % (
        len(cases), sum(c["mm"] is not None for c in cases), sum(c["mm"] is None for c in cases), out))


if __name__ == "__main__":
    main()
