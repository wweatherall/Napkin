#!/usr/bin/env python3
"""Rank the principles by asking William which of two wins when they conflict (Elo ratings), so "a lower principle
can be overridden by a higher one" (comitatus principle 01) has an order to go by (T140).

  python3 tools/SORT_PRINCIPLES.py              ask pairs until you quit; the ranking is saved as you go
  python3 tools/SORT_PRINCIPLES.py --ranking    print the ranking so far, ask nothing
  python3 tools/SORT_PRINCIPLES.py --set org    only comitatus's principles (org), only Napkin's G principles
                                                (napkin), or both (all, the default)

Each round shows two principles: type 1 or 2 for the one that should win if they ever pull against each other,
= for "equal", s to skip the pair, q to stop. Pairs are chosen so every principle gets compared, the closest
ratings first. Ratings start at 1000 and move by up to 32 a comparison (K). Everything lives in comitatus/01_Principles:
principle_ratings.json (ratings and every answer, keyed by the principle's text, so rewording one starts it
afresh) and ranking.md (generated; don't edit)."""
import datetime
import hashlib
import json
import os
import random
import re
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
START, K = 1000.0, 32.0


def main_root():
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=TOOLS, capture_output=True,
                            text=True).stdout.strip()
    return os.path.dirname(os.path.realpath(os.path.join(TOOLS, common)))


def org_dir(root):
    parent = os.path.dirname(root)
    if os.path.basename(parent) != "08_Code_Bases":
        return None
    return os.path.dirname(parent)


def org_principles(text):
    """[(id, text)] from comitatus/01_Principles/principles.md: '02. ...' numbered, '- ...' unnumbered (U1, U2 ...);
    01 (a higher principle overrides a lower one) is left out: it is what the ranking is for."""
    out, n = [], 0
    for line in text.split("\n"):
        m = re.match(r"^(\d+)\.\s+(.*)$", line.strip())
        if m and m.group(1) != "01":        # 01 is the rule this ranking serves, not one to rank
            out.append((f"org {m.group(1)}", m.group(2).strip()))
        elif line.startswith("- "):
            n += 1
            out.append((f"org U{n}", line[2:].strip()))
    return out


def napkin_principles(root):
    """[(id, text)] for Active and Tentative G principles, from 03_Past_Decisions/rulings/G*.md."""
    folder = os.path.join(root, "03_Past_Decisions", "rulings")
    out = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not re.match(r"^G\d+[a-z]*\.md$", name):
            continue
        text = open(os.path.join(folder, name), encoding="utf-8").read()
        status = re.search(r"^Status: (\w+)", text, re.M)
        if status and status.group(1) not in ("Active", "Tentative"):
            continue
        body = [l for l in text.split("\n\n")[2:] if l.strip() and not l.startswith(("#", "Why:"))]
        out.append((f"Napkin {name[:-3]}", " ".join(body[0].split()) if body else name[:-3]))
    return out


def key_of(text):
    return hashlib.sha1(" ".join(text.split()).encode()).hexdigest()[:12]


def expected(ra, rb):
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def update(ra, rb, score_a, k=K):
    """New (ra, rb) after a comparison: score_a 1 (a wins), 0 (b wins), 0.5 (equal)."""
    ea = expected(ra, rb)
    return ra + k * (score_a - ea), rb + k * ((1 - score_a) - (1 - ea))


def load(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {"ratings": {}, "answers": []}


def save(path, state):
    tmp = path + ".tmp"
    json.dump(state, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def rating(state, p):
    return state["ratings"].get(key_of(p[1]), {}).get("rating", START)


def times(state, p):
    return state["ratings"].get(key_of(p[1]), {}).get("comparisons", 0)


def pick_pair(principles, state, rng=random):
    """The least-compared principle against the one closest to it in rating that it has been compared with least."""
    if len(principles) < 2:
        return None
    done = {}
    for a in state["answers"]:
        pair = tuple(sorted((a["a"], a["b"])))
        done[pair] = done.get(pair, 0) + 1
    first = min(principles, key=lambda p: (times(state, p), rng.random()))
    others = [p for p in principles if p is not first]
    second = min(others, key=lambda p: (done.get(tuple(sorted((key_of(first[1]), key_of(p[1])))), 0),
                                        abs(rating(state, p) - rating(state, first)), rng.random()))
    return (first, second) if rng.random() < 0.5 else (second, first)


def record(state, a, b, score_a, now=None):
    ka, kb = key_of(a[1]), key_of(b[1])
    ra, rb = update(rating(state, a), rating(state, b), score_a)
    for k, p, r in ((ka, a, ra), (kb, b, rb)):
        e = state["ratings"].setdefault(k, {"rating": START, "comparisons": 0})
        e.update(rating=round(r, 2), comparisons=e["comparisons"] + 1, id=p[0], text=p[1])
    state["answers"].append({"a": ka, "b": kb, "score_a": score_a,
                             "when": f"{(now or datetime.datetime.now()):%Y-%m-%d %H:%M}"})


def ranking(principles, state):
    return sorted(principles, key=lambda p: (-rating(state, p), p[0]))


def ranking_text(principles, state):
    lines = ["# Principles, ranked", "",
             "<!-- generated by Napkin's tools/SORT_PRINCIPLES.py from principle_ratings.json; don't edit -->", "",
             "Higher wins when two pull against each other (principle 01). From William's answers, by Elo.", "",
             "| # | Rating | Compared | Principle | |", "|---|---|---|---|---|"]
    for n, p in enumerate(ranking(principles, state), 1):
        lines.append(f"| {n} | {rating(state, p):.0f} | {times(state, p)} | {p[0]} | {p[1]} |")
    return "\n".join(lines) + "\n"


def collect(root, which):
    org = org_dir(root)
    out = []
    if which in ("org", "all") and org:
        path = os.path.join(org, "01_Principles", "principles.md")
        if os.path.isfile(path):
            out += org_principles(open(path, encoding="utf-8").read())
    if which in ("napkin", "all"):
        out += napkin_principles(root)
    return out


def main(argv=None, ask=input, out=print):
    argv = sys.argv[1:] if argv is None else argv
    which = argv[argv.index("--set") + 1] if "--set" in argv and argv.index("--set") + 1 < len(argv) else "all"
    root = main_root()
    org = org_dir(root)
    if org is None:
        out("SORT_PRINCIPLES: this checkout isn't in comitatus/08_Code_Bases")
        return 1
    principles = collect(root, which)
    folder = os.path.join(org, "01_Principles")
    state_path, rank_path = os.path.join(folder, "principle_ratings.json"), os.path.join(folder, "ranking.md")
    state = load(state_path)
    if "--ranking" in argv:
        out(ranking_text(principles, state))
        return 0
    out(f"{len(principles)} principles. Which should win if the two pull against each other? 1, 2, = (equal), "
        "s (skip), q (stop).")
    while True:
        pair = pick_pair(principles, state)
        if pair is None:
            out("need at least two principles")
            return 1
        a, b = pair
        out(f"\n1. {a[1]}   [{a[0]}]\n2. {b[1]}   [{b[0]}]")
        answer = ask("> ").strip().lower()
        if answer in ("q", "quit", ""):
            break
        if answer == "s":
            continue
        score = {"1": 1.0, "2": 0.0, "=": 0.5}.get(answer)
        if score is None:
            out("type 1, 2, =, s or q")
            continue
        record(state, a, b, score)
        save(state_path, state)
        open(rank_path, "w", encoding="utf-8").write(ranking_text(principles, state))
    out(f"\n{len(state['answers'])} answers so far; ranking in {os.path.relpath(rank_path, org)}")
    out("\n".join(ranking_text(principles, state).split("\n")[6:6 + 2 + min(10, len(principles))]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nstopped; every answer so far is saved")
        sys.exit(0)
