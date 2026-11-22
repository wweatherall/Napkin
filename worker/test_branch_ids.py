"""T67: document-wide ID claims reject collisions and preserve logical creations across amendments and undo."""
import os
import sys
import uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OpError, board_label
from session import IdRegistry

R = [0, 0]
def check(name, condition):
    R[0 if condition else 1] += 1
    print(('PASS ' if condition else 'FAIL ') + name, flush=True)

def fresh(prefix): return prefix + uuid.uuid4().hex

def rejects(name, registry, ops):
    before = (set(registry.reserved), dict(registry.owners))
    try:
        registry.accept(ops)
        check(name, False)
    except OpError:
        check(name, before == (registry.reserved, registry.owners))

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
rejects('a reservation without a claim is never reassigned', r,
        [dict(id=fresh('as1_'), type='make_assembly', new_id=unclaimed)])
copy = fresh('mv1_'); b1, b2 = fresh('b4_'), fresh('b5_')
r.accept([dict(id=copy, type='move', new_ids=[b1,b2])])
rejects('array members cannot exchange identities', r, [dict(id=copy, type='move', new_ids=[b2,b1])])
check('friendly Board names accept random IDs and preserve old names',
      board_label(body) == 'Board 3' and board_label('b3') == 'Board 3' and board_label('bottom') == 'bottom')
check('random identifiers are never rewritten in reservations', body in r.reserved and profile in r.reserved)
print('BRANCH IDS TESTS: %d passed, %d failed' % tuple(R))
