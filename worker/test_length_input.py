import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from length_input import evaluate
passed = 0
for text, expected in [('19',19), ('3/4"',19.05), ('1 1/2"',38.1), ('1\'6"',457.2), ('1in + 5mm',30.4), ('(24in - 2*19mm)/3',190.5333333333333), ('+5',5), ('2 * 19mm',38), ('-12',-12), ('-1ft 6in',-457.2)]:
    print("CASE", text, flush=True)
    value = evaluate(text)
    assert abs(value-expected)<1e-8, (text,value,expected)
    passed += 1
for text in ['1-1/2"', '1\'-6"','1/0','3kg','2mm * 3mm','Probe.Length','', '3//4']:
    try: evaluate(text)
    except Exception: passed += 1
    else: raise AssertionError(text)
assert abs(evaluate('3/4','in')-19.05)<1e-8
print('LENGTH TESTS: %d passed, 0 failed' % (passed+1))
