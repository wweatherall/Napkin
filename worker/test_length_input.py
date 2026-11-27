import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from length_input import evaluate, handle
passed = 0
for text, expected in [('19',19), ('3/4"',19.05), ('1 1/2"',38.1), ('1\'6"',457.2), ('1in + 5mm',30.4), ('(24in - 2*19mm)/3',190.5333333333333), ('+5',5), ('2 * 19mm',38), ('-12',-12), ('-1ft 6in',-457.2), ('1-1/2\"',12.7), ("1'-6\"",152.4), ("1' 6 1/2\"",469.9), ('19-3',16), ('1in-5mm',20.4)]:
    print("CASE", text, flush=True)
    value = evaluate(text)
    assert abs(value-expected)<1e-8, (text,value,expected)
    passed += 1
for text in ['1/0','3kg','2mm * 3mm','Probe.Length','', '3//4']:
    try: evaluate(text)
    except Exception: passed += 1
    else: raise AssertionError(text)
assert abs(evaluate('3/4','in')-19.05)<1e-8
assert handle({'cmd': 'length', 'request_id': 7, 'texts': ['2in', '1 + 2'], 'default_unit': 'mm'}) == {
    'cmd': 'length', 'request_id': 7, 'ok': True, 'values': [50.8, 3.0],
}
err_resp = handle({'cmd': 'length', 'request_id': 8, 'texts': ['1/0']})
assert err_resp['cmd'] == 'length' and err_resp['request_id'] == 8 and err_resp['ok'] is False and 'error' in err_resp
assert handle({'cmd': 'length', 'texts': ['10']})['request_id'] is None
passed += 3
# FreeCAD still gives the answers in tests/length_cases.json (the table viewport/test_units.gd holds the local
# evaluator to). If this fails after a FreeCAD update, rerun tools/length_cases.py and check test_units.gd.
import json
table = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tests', 'length_cases.json')))
changed = []
for case in table['cases']:
    du = case.get('default_unit', 'mm')
    try: got = evaluate(case['text'], du)
    except Exception: got = None
    want = case['mm']
    if (got is None) != (want is None) or (got is not None and abs(got - want) > 1e-9 * max(1.0, abs(want))):
        changed.append((case['text'], du, got, want))
assert not changed, changed[:10]
passed += 1
print('LENGTH TESTS: %d passed, 0 failed (FreeCAD matches all %d table cases)' % (passed+1, len(table['cases'])))
