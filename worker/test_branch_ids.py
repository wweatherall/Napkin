"""T67: document-wide ID claims reject collisions and preserve logical creations across amendments and undo."""
import json
import os
import sys
import uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OpError, board_label
from session import IdRegistry, Session, creations

R = [0, 0]
def check(name, condition):
    R[0 if condition else 1] += 1
    print(('PASS ' if condition else 'FAIL ') + name, flush=True)

def fresh(prefix): return prefix + uuid.uuid4().hex

def rejects(name, registry, ops, match=None):
    before = (set(registry.reserved), dict(registry.owners))
    try:
        registry.accept(ops)
        check(name, False)
    except OpError as e:
        ok = before == (registry.reserved, registry.owners)
        if match is not None:
            ok = ok and match in str(e)
        check(name, ok)

r = IdRegistry()
profile, push, body = fresh('r1_'), fresh('pp1_'), fresh('b3_')
ops = [dict(id=profile, type='rect'), dict(id=push, type='push_pull', body=body)]
r.accept(ops)
r.accept([])                                # undo every action
other = fresh('pp2_')
rejects('an abandoned board ID cannot belong to another creation', r,
        [dict(id=other, type='push_pull', body=body)])
rejects('an op ID cannot become a board ID', r,
        [dict(id=other, type='push_pull', body=profile)])
rejects('duplicate op IDs in one path are refused before any reservation changes', r, ops + [ops[0]])
rejects('an op identity cannot change operation kind', r, [dict(id=profile, type='circle')])
r.accept([dict(id=profile, type='rect', size=[20, 30]), dict(id=push, type='push_pull', body=body, distance=40)])
check('typed amendments keep the same logical profile, op and board', r.owners[body] == 'body:' + push)
unclaimed = fresh('a8_')
r.accept([], [unclaimed])
claimer = fresh('as1_')
r.accept([dict(id=claimer, type='make_assembly', new_id=unclaimed)])
check('an unowned reservation is claimed by the first op that creates it',
      r.owners.get(unclaimed) == 'assembly:' + claimer)
rejects('a claimed reservation cannot be reassigned to another op', r,
        [dict(id=fresh('as2_'), type='make_assembly', new_id=unclaimed)], 'ID collision')
copy = fresh('mv1_'); b1, b2 = fresh('b4_'), fresh('b5_')
r.accept([dict(id=copy, type='move', new_ids=[b1,b2])])
rejects('array members cannot exchange identities', r, [dict(id=copy, type='move', new_ids=[b2,b1])])
check('friendly Board names accept random IDs and preserve old names',
      board_label(body) == 'Board 3' and board_label('b3') == 'Board 3' and board_label('bottom') == 'bottom')
check('random identifiers are never rewritten in reservations', body in r.reserved and profile in r.reserved)

# H095: redo after undoing an op that never reached the worker (ID reserved, no owner yet)
s = Session(None)
try:
    sr, sp, sb1 = fresh('r10_'), fresh('pp10_'), fresh('b10_')
    sp2, sB = fresh('pp11_'), fresh('b11_')
    r_op = dict(id=sr, type='rect', plane=dict(origin=[0, 0, 0], normal=[0, 0, 1]), size=[100, 60])
    p_op = dict(id=sp, type='push_pull', target=dict(rect=sr), distance=20, body=sb1)
    p2_op = dict(id=sp2, type='push_pull',
                 target=dict(face=dict(body=sb1, normal=[0, 0, 1], point=[50, 30, 20])),
                 distance=15, body=sB)
    s.sync([r_op, p_op], [sp2, sB])
    check('unowned reserved board ID stays unowned after sync without its op',
          sB in s.ids.reserved and sB not in s.ids.owners)
    s.sync([r_op, p_op, p2_op], [sp2, sB])
    check('first op creating an unowned reserved board ID succeeds and claims it',
          all(e['status'] == 'ok' for e in s.status())
          and sB in s.model.bodies()
          and s.ids.owners.get(sB) == 'body:' + sp2)
    s.sync([r_op, p_op, p2_op], [sp2, sB])
    check('syncing the same op list again succeeds',
          all(e['status'] == 'ok' for e in s.status()) and s.ids.owners.get(sB) == 'body:' + sp2)
    other_push = dict(id=fresh('pp12_'), type='push_pull',
                      target=dict(face=dict(body=sb1, normal=[0, 0, 1], point=[50, 30, 20])),
                      distance=15, body=sB)
    try:
        s.sync([r_op, p_op, other_push])
        check('another push creating the claimed board ID is rejected with ID collision', False)
    except OpError as e:
        check('another push creating the claimed board ID is rejected with ID collision',
              'ID collision' in str(e) and s.ids.owners.get(sB) == 'body:' + sp2)
    other_type = dict(id=fresh('as3_'), type='make_assembly', targets=[sb1], new_id=sB)
    try:
        s.sync([r_op, p_op, other_type])
        check('another op type creating the claimed board ID is rejected with ID collision', False)
    except OpError as e:
        check('another op type creating the claimed board ID is rejected with ID collision',
              'ID collision' in str(e) and s.ids.owners.get(sB) == 'body:' + sp2)
    dup_b = fresh('b12_')
    s.sync([r_op, p_op], [dup_b])
    d1 = dict(id=fresh('pp13_'), type='push_pull',
              target=dict(face=dict(body=sb1, normal=[0, 0, 1], point=[50, 30, 20])),
              distance=10, body=dup_b)
    d2 = dict(id=fresh('pp14_'), type='push_pull',
              target=dict(face=dict(body=sb1, normal=[0, 0, 1], point=[50, 30, 20])),
              distance=12, body=dup_b)
    try:
        s.sync([r_op, p_op, d1, d2])
        check('unowned reserved ID created twice in one op list is rejected with ID collision', False)
    except OpError as e:
        check('unowned reserved ID created twice in one op list is rejected with ID collision',
              'ID collision' in str(e) and dup_b not in s.ids.owners)
finally:
    s.close()

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tests', 'op_creations.json')) as f:
    for idx, case in enumerate(json.load(f)):
        got = [i for i, _ in creations(case['op'])]
        check(f"creations matches tests/op_creations.json[{idx}] ({case['op'].get('type')})", got == case['makes'])

print('BRANCH IDS TESTS: %d passed, %d failed' % tuple(R))
