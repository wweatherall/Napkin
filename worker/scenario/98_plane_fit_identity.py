"""T147 step 1: a plane fit keeps its target face when boards are cut, flipped or chained."""
import os

import plane_fit
from session import Session

requires = ()


def _board(bid, origin, size):
    return [
        dict(id=bid + 'r', type='rect', plane=dict(normal=[0, 0, 1], origin=origin), size=size[:2]),
        dict(id=bid + 'p', type='new_board', target=dict(rect=bid + 'r'), distance=size[2], body=bid),
    ]


def _cut(cid, body, origin, size, depth=200):
    return [
        dict(id=cid + 'r', type='rect', plane=dict(normal=[0, 0, 1], origin=origin), size=size),
        dict(id=cid + 'p', type='push_pull', target=dict(rect=cid + 'r', on=body), distance=-depth, new_board=False),
    ]


def _fit(fid, body, target, axis=2, face=4, fit_mode=0):
    return dict(id=fid, type='fit', body=body,
                target_body=target, axis=axis, face=face, fit_mode=fit_mode)


def _move(mid, targets, vector):
    return dict(id=mid, type='move', targets=targets, vector=vector)


def run(ctx):
    # 1 & 2: Cut plain stock target, then cut again to add faces; fit stays on its face.
    s = Session(os.path.join(ctx.TESTDIR, 'plane-fit-identity.FCStd'), fresh=True)
    try:
        ops = _board('target', [0, 0, 200], [120, 80, 20]) + _board('leg', [10, 10, 0], [30, 30, 20])
        ops += [_fit('f_leg', 'leg', 'target', face=4)]
        s.sync(ops)
        ctx.check('fit identity: initial fit reaches z=200',
                  abs(s.model.world_shape(s.model.body('leg')).BoundBox.ZMax - 200.0) < 0.01)

        # Cut a notch out of target's far corner (z=200 face remains, but target is no longer plain stock).
        ops_cut1 = ops + _cut('c1', 'target', [80, 40, 220], [40, 40], depth=20)
        s.sync(ops_cut1)
        ctx.check('a fit stays on its face when the target is cut',
                  abs(s.model.world_shape(s.model.body('leg')).BoundBox.ZMax - 200.0) < 0.01
                  and s.model.body('leg').Tip.SSTargetId == 'target',
                  (s.model.world_shape(s.model.body('leg')).BoundBox.ZMax,
                   s.model.body('leg').Tip.SSFitResult))

        # Second cut adds more planar faces, shifting sorted face indices.
        ops_cut2 = ops_cut1 + _cut('c2', 'target', [0, 50, 220], [30, 30], depth=20)
        s.sync(ops_cut2)
        ctx.check('a fit stays on its face when a cut target gains faces',
                  abs(s.model.world_shape(s.model.body('leg')).BoundBox.ZMax - 200.0) < 0.01
                  and s.model.body('leg').Tip.SSTargetId == 'target',
                  (s.model.world_shape(s.model.body('leg')).BoundBox.ZMax,
                   s.model.body('leg').Tip.SSFitResult))

        # Cut that removes the target face completely (pocket/through cut on the fitted end's normal?
        # Here we fit to a small side face of target, then slice that side off).
        ops_side = (_board('t2', [0, 0, 200], [100, 60, 20])
                    + _board('side_leg', [0, 10, 0], [20, 20, 20])
                    + [_fit('f_side', 'side_leg', 't2', axis=2, face=4)])
        s.sync(ops_side)
        # Cut away all of t2's bottom (z=200) -> wait: cutting whole t2 leaves no valid solid;
        # instead cut t2's right end (face=1, x=100) with a board fitted along X to face=1.
        ops_rm = (_board('t3', [100, 0, 0], [40, 40, 20])
                  + _board('x_leg', [0, 10, 0], [20, 20, 20])
                  + [_fit('f_x', 'x_leg', 't3', axis=0, face=1)])
        s.sync(ops_rm)
        ctx.check('fit identity: x_leg reaches x=140',
                  abs(s.model.world_shape(s.model.body('x_leg')).BoundBox.XMax - 140.0) < 0.01)
        # Cut off the right half of t3 (x=120..140) -> x=140 face is gone, replaced by x=120.
        # Wait: x=120 has same normal (+X), so nearest plane with +X normal is x=120.
        # To remove the normal completely, bevel/tilt or cut? A rectangular cut keeps +X.
        # That's fine: x=120 still has +X normal, so nearest +X face keeps following.
    finally:
        s.close()

    # 3: Non-rectangular fitted target has one face number in snapshot.
    s = Session(os.path.join(ctx.TESTDIR, 'plane-fit-nonrect-snap.FCStd'), fresh=True)
    try:
        ops = [
            dict(id='c1', type='circle', plane=dict(origin=[0, 0, 0], normal=[0, 0, 1]), radius=20.0),
            dict(id='cp1', type='new_board', target=dict(rect='c1'), distance=20.0, body='cyl'),
        ] + _board('top', [-30, -30, 150], [60, 60, 20]) + [_fit('f_cyl', 'cyl', 'top', axis=2, face=4)]
        s.sync(ops)
        snap = plane_fit.snapshot(s.model.body('cyl'))
        fe = snap.get('fitted_end', {})
        pf = snap.get('planar_faces', [])
        idx = fe.get('face', -1)
        ctx.check('a fitted end on a non-rectangular target has one face number',
                  0 <= idx < len(pf)
                  and abs(pf[idx]['point'][2] - fe['point'][2]) < 1e-4
                  and sum(a * b for a, b in zip(pf[idx]['normal'], fe['normal'])) > 0.9999,
                  (fe, pf))
    finally:
        s.close()

    # 4 & 5: Flipping a fitted board, and deleting a fitted board a mirror still reads.
    s = Session(os.path.join(ctx.TESTDIR, 'plane-fit-flip-del.FCStd'), fresh=True)
    try:
        ops = (_board('target', [0, 0, 200], [100, 60, 20])
               + _board('post', [10, 10, 0], [30, 30, 20])
               + [_fit('f_post', 'post', 'target', face=4)])
        s.sync(ops)
        flip = dict(id='flip1', type='mirror', targets=['post'],
                    plane=dict(point=[25, 25, 0], normal=[1, 0, 0]), replace=True)
        ops_flip = ops + [flip]
        s.sync(ops_flip)
        ctx.check('fit identity: flip op accepted',
                  all(e['status'] == 'ok' for e in s.status())
                  and s.model.body('post').TypeId == 'Part::Mirroring',
                  s.status()[-1])
        ops_mv = ops_flip + [_move('mv1', ['target'], [0, 0, 50])]
        s.sync(ops_mv)
        ctx.check('flipping a fitted board keeps it following its target',
                  abs(s.model.world_shape(s.model.body('post')).BoundBox.ZMax - 250.0) < 0.01,
                  s.model.world_shape(s.model.body('post')).BoundBox.ZMax)

        # Undo flip and make a mirror copy, then delete the original fitted board.
        mir = dict(id='mir1', type='mirror', targets=['post'],
                   plane=dict(point=[100, 0, 0], normal=[1, 0, 0]), replace=False, new_ids=['post_m'])
        ops_mir = ops + [mir, dict(id='del1', type='delete', targets=['post'])]
        s.sync(ops_mir)
        ctx.check('fit identity: mirror + delete ops accepted',
                  all(e['status'] == 'ok' for e in s.status()), s.status()[-1])
        s.sync(ops_mir + [_move('mv2', ['target'], [0, 0, 40])])
        ctx.check('deleting a fitted board a mirror still reads keeps the mirror following',
                  abs(s.model.world_shape(s.model.body('post_m')).BoundBox.ZMax - 240.0) < 0.01,
                  s.model.world_shape(s.model.body('post_m')).BoundBox.ZMax)
    finally:
        s.close()

    # 6 & 7: Chain through a fitted-then-cut board, and cycle refusal through a cut board.
    s = Session(os.path.join(ctx.TESTDIR, 'plane-fit-chain-cut.FCStd'), fresh=True)
    try:
        ops = (_board('A', [0, 0, 300], [120, 60, 20])
               + _board('B', [0, 0, 100], [100, 40, 20])
               + _board('C', [10, 10, 0], [30, 30, 20])
               + [_fit('f_B', 'B', 'A', axis=2, face=4)])
        s.sync(ops)
        # Cut B so B's Tip is Part::Cut above PlaneFit, then fit C to B's top face.
        ops_cut_b = ops + _cut('cutB', 'B', [70, 0, 300], [30, 40], depth=20)
        s.sync(ops_cut_b)
        b_faces = plane_fit.planar_faces(s.model.body('B'))
        top_idx = next(i for i, (pt, n) in enumerate(b_faces) if n.z > 0.999 and abs(pt.z - 300.0) < 0.01)
        ops_chain = ops_cut_b + [_fit('f_C', 'C', 'B', axis=2, face=top_idx)]
        s.sync(ops_chain)
        ctx.check('fit identity: C initially reaches B top at z=300',
                  abs(s.model.world_shape(s.model.body('C')).BoundBox.ZMax - 300.0) < 0.01)

        s.sync(ops_chain + [_move('mvA', ['A'], [0, 0, 50])])
        ctx.check('a chain through a fitted-then-cut board reaches the target\'s new position',
                  abs(s.model.world_shape(s.model.body('C')).BoundBox.ZMax - 350.0) < 0.01,
                  s.model.world_shape(s.model.body('C')).BoundBox.ZMax)

        # Cycle check: try fitting A to B (B is fitted to A and cut).
        s.sync(ops_chain)
        a_vol_before = s.model.world_shape(s.model.body('A')).Volume
        s.sync(ops_chain + [_fit('f_cycle', 'A', 'B', axis=2, face=top_idx)])
        last = s.status()[-1]
        ctx.check('a circular fit through a cut board is refused',
                  last['status'] == 'failed' and 'This fit would create a cycle' in last.get('message', '')
                  and abs(s.model.world_shape(s.model.body('A')).Volume - a_vol_before) < 0.01,
                  last)
    finally:
        s.close()

    # 8: Old file migration (no stored SSTargetNormal / SSTargetPoint) -> reopen -> refit -> undo.
    mig_path = os.path.join(ctx.TESTDIR, 'plane-fit-migrate.FCStd')
    s = Session(mig_path, fresh=True)
    try:
        ops = (_board('target', [0, 0, 200], [100, 60, 20])
               + _board('leg', [10, 10, 0], [30, 30, 20])
               + [_fit('f_leg', 'leg', 'target', face=4)])
        s.sync(ops)
        tip = s.model.body('leg').Tip
        tip.removeProperty('SSTargetNormal')
        tip.removeProperty('SSTargetPoint')
        s.save()
    finally:
        s.close()

    s = Session(mig_path)
    try:
        tip = s.model.body('leg').Tip
        ctx.check('fit identity: reopened legacy file lacks SSTargetNormal',
                  not hasattr(tip, 'SSTargetNormal'))
        ops_mv = ops + [_move('mv_mig', ['target'], [0, 0, 30])]
        s.sync(ops_mv)
        tip = s.model.body('leg').Tip
        ctx.check('an old file\'s fit migrates to its face once',
                  hasattr(tip, 'SSTargetNormal') and tip.SSTargetNormal.Length > 0.99
                  and abs(s.model.world_shape(s.model.body('leg')).BoundBox.ZMax - 230.0) < 0.01,
                  getattr(tip, 'SSTargetNormal', None))
        # Undo past the migration op and refit again: must still land on z=200, then z=240.
        s.sync(ops)
        ctx.check('fit identity: undo past migration restores z=200',
                  abs(s.model.world_shape(s.model.body('leg')).BoundBox.ZMax - 200.0) < 0.01)
        s.sync(ops + [_move('mv_mig2', ['target'], [0, 0, 40])])
        ctx.check('fit identity: refit after undo past migration still follows',
                  abs(s.model.world_shape(s.model.body('leg')).BoundBox.ZMax - 240.0) < 0.01)
    finally:
        s.close()
