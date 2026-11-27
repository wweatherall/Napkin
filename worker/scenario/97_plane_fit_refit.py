"""T54: refit only changed inputs, including expression-driven stock and fitted targets."""
import os
import statistics
import time

import plane_fit
from session import Session
from scenario.context import snap

requires = ()


def run(ctx):
    s = Session(os.path.join(ctx.TESTDIR, 'plane-refit.FCStd'), fresh=True)
    fresh = None
    original = plane_fit.update
    calls = []

    class CountRecomputes:
        def __init__(self, doc):
            self.doc = doc
            self.count = 0

        def recompute(self):
            self.count += 1
            return self.doc.recompute()

        def __getattr__(self, name):
            return getattr(self.doc, name)

    def tracked(model, board, tip):
        calls.append(board.BodyId)
        return original(model, board, tip)

    def board(bid, z):
        return [dict(id=bid+'r', type='rect', plane=dict(normal=[0,0,1], origin=[0,0,z]), size=[40,20]),
                dict(id=bid+'p', type='push_pull', target=dict(rect=bid+'r'), distance=20, body=bid)]

    def fit(bid, target):
        return dict(id=bid+'fit', type='fit', body=bid,
                    target_body=target, axis=2, face=4, fit_mode=0)

    def move(bid, delta):
        return dict(id='move'+bid, type='move', targets=[bid], vector=delta)

    def signature(sess):
        return snap(sess), {o.Name: (o.SSTargetId, o.SSFitResult, [tuple(p) for p in o.SSFitCorners])
                            for o in sess.doc.Objects if hasattr(o, 'SSFitResult')}

    def sync(ops):
        calls.clear()
        s.sync(ops)
        ctx.check('plane refit: operations accepted', all(e['status']=='ok' for e in s.status()), s.status()[-1])

    try:
        ops = board('target', 300) + board('other', 600)
        for i in range(10):
            bid = 'leg'+str(i)
            ops += board(bid, 0) + [fit(bid, 'target')]
        s.sync(ops)
        ctx.check('plane refit: ten fits built', all(e['status']=='ok' for e in s.status()))
        plane_fit.update = tracked
        before = signature(s)
        counter = CountRecomputes(s.doc)
        s.model.doc = counter
        sync(ops + [move('other', [10,0,0])])
        s.model.doc = s.doc
        ctx.check('plane refit: unrelated move needs only native recompute', counter.count==1, counter.count)
        ctx.check('plane refit: unrelated move updates no fits', calls == [], calls)
        ctx.check('plane refit: unrelated move reports only its board', s.status()[-1]['changed']==['other'], s.status()[-1])
        s.sync(ops)
        ctx.check('plane refit: undo restores shapes and fit text', signature(s)==before)
        samples = []
        for _ in range(15):
            start = time.perf_counter()
            s.sync(ops + [move('other', [10,0,0])])
            samples.append((time.perf_counter()-start)*1000)
            s.sync(ops)
        print('PLANE REFIT TIMING: unrelated move, 10 fits, median %.3f ms (15 samples)' % statistics.median(samples), flush=True)
        counter.count = 0
        s.model.doc = counter
        sync(ops + [move('target', [0,0,10])])
        s.model.doc = s.doc
        ctx.check('plane refit: ten fits share one additional recompute', counter.count==2, counter.count)
        ctx.check('plane refit: moving target updates all its fits once', sorted(calls)==['leg'+str(i) for i in range(10)], calls)
        ctx.check('plane refit: no duplicate changed boards', len(s.status()[-1]['changed'])==11, s.status()[-1])
        ctx.check('plane refit: target movement changes fitted geometry',
                  abs(s.model.world_shape(s.model.body('leg0')).Volume-40*20*310)<0.01)
        s.sync(ops)
        sync(ops + [move('leg0', [0,0,10])])
        ctx.check('plane refit: source movement updates only that fit', calls==['leg0'], calls)
        s.sync(ops)
        name = s.model.body('target').Name
        rename = dict(id='rename', type='property_edit', body='target', object=name, property='Label', value='Top rail', mode='value')
        sync(ops + [rename])
        ctx.check('plane refit: renamed target updates fit text', len(calls)==10 and 'Top rail' in s.model.body('leg0').Tip.SSFitResult, calls)
        other_name = s.model.rect_obj('otherr').Name
        # A third board drives a fit target dimension through a native expression.
        expression = dict(id='expression', type='property_edit', body='target', object=name,
                          property='Placement.Base.z', value=other_name+'.Length + 300 mm', mode='expression')
        expr_ops = ops + [expression]
        sync(expr_ops)
        edit = dict(id='dimension', type='property_edit', body='other', object=other_name,
                    property='Length', value='80 mm', mode='value')
        sync(expr_ops + [edit])
        ctx.check('plane refit: indirect expression change updates target fits', len(calls)==10 and
                  abs(s.model.world_shape(s.model.body('leg0')).Volume-40*20*680)<0.01, calls)
        s.sync(ops)
        # T60: when a previously plain target becomes fitted, its dependents stay tied and match a fresh build.
        chain_ops = ops + [fit('target', 'other')]
        sync(chain_ops)
        ctx.check('plane refit: fitted target keeps dependents tied',
                  s.model.body('target').Tip.SSTargetId == 'other' and
                  all(s.model.body('leg'+str(i)).Tip.SSTargetId == 'target' and
                      abs(s.model.world_shape(s.model.body('leg'+str(i))).Volume - 40*20*300) < 0.01 for i in range(10)))
        fresh = Session(os.path.join(ctx.TESTDIR, 'plane-refit-chain.FCStd'), fresh=True)
        fresh.sync(chain_ops)
        ctx.check('plane refit: fitted target agrees with fresh build', signature(fresh)==signature(s))
        fresh.close()
        fresh = None
        s.sync(ops)
        final_ops = ops + [move('target', [0,0,10])]
        sync(final_ops)
        expected = signature(s)
        fresh = Session(os.path.join(ctx.TESTDIR, 'plane-refit-fresh.FCStd'), fresh=True)
        fresh.sync(final_ops)
        ctx.check('plane refit: incremental geometry and text equal fresh build', signature(fresh)==expected)
        s.save()
        path = s.path
        s.close()
        s = Session(path)
        ctx.check('plane refit: reopen retains geometry and text', signature(s)==expected)
        sync(final_ops + [move('other', [10,0,0])])
        ctx.check('plane refit: reopened unrelated operation updates no fits', calls==[], calls)
        s.sync(final_ops)
        ctx.check('plane refit: reopened undo retains geometry and text', signature(s)==expected)
        s.sync(ops)
        sync(ops + [dict(id='delete-target', type='delete', targets=['target'])])
        ctx.check('plane refit: deleted target detaches dependent fits', len(calls)==10 and
                  all(s.model.body('leg'+str(i)).Tip.SSTargetId=='' for i in range(10)), calls)
    finally:
        plane_fit.update = original
        s.close()
        if fresh:
            fresh.close()
