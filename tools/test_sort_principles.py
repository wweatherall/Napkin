#!/usr/bin/env python3
"""Checks tools/SORT_PRINCIPLES.py (T140): reading both sets of principles, Elo updates, pair choice that spreads
comparisons, the saved ranking, and a scripted session. Throwaway folders. Summary line: SORT PRINCIPLES TESTS: N passed, M failed."""
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import SORT_PRINCIPLES as S

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        print(f"FAIL {name}  {detail}")


org = S.org_principles("# P\n\n01. Higher wins.\n02. You are free.\nUnnumbered:\n- Work simply.\n- Take chances.\n")
check("comitatus's principles are read, numbered and unnumbered, leaving out 01 (the rule the ranking serves)",
      org == [("org 02", "You are free."), ("org U1", "Work simply."), ("org U2", "Take chances.")], org)
napkin = S.napkin_principles(S.main_root())
check("Napkin's Active G principles are read from their ruling files",
      len(napkin) >= 13 and napkin[0][0] == "Napkin G01" and "draft" in napkin[0][1].lower(), napkin[:2])

a, b = S.update(1000, 1000, 1.0)
check("equal ratings: the winner gains 16, the loser loses 16", (a, b) == (1016.0, 984.0), (a, b))
a, b = S.update(1000, 1000, 0.5)
check("a draw between equals changes nothing", (a, b) == (1000.0, 1000.0))
a, b = S.update(1200, 1000, 1.0)
check("an expected win moves the ratings less", 0 < a - 1200 < 16 and abs((a - 1200) + (b - 1000)) < 1e-9, (a, b))

ps = org + [("x", "Fourth.")]
state = {"ratings": {}, "answers": []}
rng = random.Random(1)
seen = set()
for _ in range(4):
    p, q = S.pick_pair(ps, state, rng)
    seen.update((p[0], q[0]))
    S.record(state, p, q, 1.0)
check("the least-compared principles are asked first, so four rounds reach all four", seen == {p[0] for p in ps}, seen)
check("a principle reworded starts afresh (ratings keyed by text)",
      S.rating(state, ("org 02", "You are free, and so is everyone.")) == S.START)
S.record(state, ps[0], ps[3], 1.0); S.record(state, ps[0], ps[3], 1.0)
check("the ranking puts the one that keeps winning first", S.ranking(ps, state)[0] == ps[0], S.ranking(ps, state))
check("ranking.md says it is generated", "<!-- generated" in S.ranking_text(ps, state))

answers, said = iter(["1", "x", "=", "s", "q"]), []
d = tempfile.mkdtemp()
orig = (S.main_root, S.org_dir, S.collect)
S.main_root, S.org_dir, S.collect = (lambda: d), (lambda r: d), (lambda r, w: ps)
os.makedirs(os.path.join(d, "01_Principles"))
try:
    S.main(["--set", "org"], ask=lambda _: next(answers), out=said.append)
finally:
    S.main_root, S.org_dir, S.collect = orig
saved = S.load(os.path.join(d, "01_Principles", "principle_ratings.json"))
check("a scripted session saves two answers (1 and =), ignores x, skips s, stops at q",
      len(saved["answers"]) == 2 and [x["score_a"] for x in saved["answers"]] == [1.0, 0.5]
      and any("type 1, 2" in s for s in said), saved["answers"])
check("the ranking file is written beside the ratings", os.path.isfile(os.path.join(d, "01_Principles", "ranking.md")))

print(f"SORT PRINCIPLES TESTS: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
