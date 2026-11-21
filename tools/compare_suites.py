"""Compare viewport suite results with the reference runs: python3 tools/compare_suites.py <runs dir> [suite...]
Each suite's final boards must match (volume within 0.1 mm³, world box within 0.001 mm, hole list) and so must
every op's status. Exit 1 if any differ."""
import json, os, sys

REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "reference")
runs = sys.argv[1]
suites = sys.argv[2:] or sorted(os.listdir(REF))
bad_any = False
for suite in suites:
    pa, pb = os.path.join(REF, suite), os.path.join(runs, suite, "out")
    try:
        a = {x["id"]: x for x in json.load(open(os.path.join(pa, "bodies.json")))}
        b = {x["id"]: x for x in json.load(open(os.path.join(pb, "bodies.json")))}
        sa = [(o["id"], o["status"]) for o in json.load(open(os.path.join(pa, "status.json")))["ops"]]
        sb = [(o["id"], o["status"]) for o in json.load(open(os.path.join(pb, "status.json")))["ops"]]
    except OSError as e:
        print(f"{suite:11s} MISSING {e}"); bad_any = True; continue
    cuts = lambda x: sorted((c["op"], tuple(round(v, 3) for v in c["lo"])) for c in x.get("cuts", []))
    bad = [k for k in sorted(set(a) | set(b)) if k not in a or k not in b
           or abs(a[k]["volume_mm3"] - b[k]["volume_mm3"]) > 0.1
           or any(abs(x - y) > 1e-3 for x, y in zip(a[k]["world_bbox"], b[k]["world_bbox"])) or cuts(a[k]) != cuts(b[k])]
    same = not bad and sa == sb
    bad_any |= not same
    print(f"{suite:11s} {'same' if same else 'DIFFERENT'} | {len(b)} boards, {len(sb)} ops"
          + ("" if same else f" | boards differing: {bad} | op statuses same: {sa == sb}"))
sys.exit(1 if bad_any else 0)
