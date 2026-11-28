"""T81: exact circular stock, bores and bosses, with transaction/reopen parity."""
import math
from session import Session
from scenario.context import face, ok, only, snap

requires = ()


def run(ctx):
    def circle(rid, origin, radius=10, normal=(0, 0, 1), on=None):
        plane = {'on': face(on, normal, origin)} if on else {'origin': origin, 'normal': normal}
        return dict(id=rid, type='circle', plane=plane, radius=radius)

    def push(oid, rid, distance, **extra):
        return dict(id=oid, type='new_board' if 'body' in extra else 'push_pull', target={'rect': rid}, distance=distance, **extra)

    dowel = [circle('round', [800, 0, 0]), push('round_push', 'round', 100, body='dowel')]

    def exact(st, a, b):
        model = ctx.S.model
        base = model.rect_obj('round')
        sh = model.world_shape(model.body('dowel'))
        return [ok(st, 2), only(a, b, {'dowel'}),
                ('exact cylinder volume', abs(sh.Volume - math.pi * 10**2 * 100) < 1e-5, sh.Volume),
                ('editable fully constrained sketch', base.TypeId == 'Sketcher::SketchObject' and base.FullyConstrained, base.TypeId),
                ('native circular edge, not polygon', any(e.Curve.__class__.__name__ == 'Circle' for e in sh.Edges), str(sh))]
    ctx.step('circle to dowel', ctx.FIX + dowel, exact)
    bore = [circle('bore', [100, 200, 18], 10, on='bottom'), push('bore_push', 'bore', -18, through=True)]
    ctx.step('round through hole', ctx.FIX + bore, lambda st, a, b: [ok(st, 2), only(a, b, {'bottom'}),
        ('exact round volume removed', abs(a['boards']['bottom']['vol'] - b['boards']['bottom']['vol'] - math.pi * 100 * 18) < 0.02, b['boards']['bottom']['vol']),
        ('through expressions retained', bool(ctx.S.model.body('bottom').Tip.Tool.Links[0].ExpressionEngine), '')])
    boss = [circle('boss', [180, 200, 18], 12, on='bottom'), push('boss_push', 'boss', 20)]
    ctx.step('round boss', ctx.FIX + boss, lambda st, a, b: [ok(st, 2), only(a, b, {'bottom'}),
        ('exact round volume added', abs(b['boards']['bottom']['vol'] - a['boards']['bottom']['vol'] - math.pi * 144 * 20) < 0.02, b['boards']['bottom']['vol'])])
    separate = [circle('sep', [250, 200, 18], on='bottom'), push('sep_push', 'sep', 30, body='separate')]
    ctx.step('round separate board on face', ctx.FIX + separate, lambda st, a, b: [ok(st, 2), only(a, b, {'separate'}),
        ('exact separate cylinder', abs(b['boards'].get('separate', {}).get('vol', 0) - math.pi * 100 * 30) < 0.02, b['boards'].get('separate'))])
    # A mirrored board exercises world-to-definition placement conversion on a vertical face.
    side = [circle('side', [18, 200, 300], 8, normal=(1, 0, 0), on='left'), push('side_push', 'side', -18, through=True)]
    ctx.step('round hole on vertical mirrored stock', ctx.FIX + side, lambda st, a, b: [ok(st, 2),
        ('left and mirror both lose a circular bore', all(abs(a['boards'][bid]['vol'] - b['boards'][bid]['vol'] - math.pi * 64 * 18) < 0.02 for bid in ('left', 'right')), b['boards']['left']['vol'])])
    linked = [circle('linked_circle', [100, 100, 558], 8, on='shelf2'), push('linked_circle_push', 'linked_circle', 20)]
    ctx.step('round boss on translated linked shelf', ctx.FIX + linked, lambda st, a, b: [ok(st, 2), only(a, b, {'shelf', 'shelf2'}),
        ('definition and copy both gain the exact boss', all(abs(b['boards'][bid]['vol'] - a['boards'][bid]['vol'] - math.pi * 64 * 20) < 0.02 for bid in ('shelf', 'shelf2')), '')])
    tilted = [circle('tilted_circle', [800, 0, 0], 8, normal=(1, 1, 1)), push('tilted_push', 'tilted_circle', 50, body='tilted')]
    ctx.step('circle on arbitrary plane', ctx.FIX + tilted, lambda st, a, b: [ok(st, 2), only(a, b, {'tilted'}),
        ('exact tilted cylinder volume', abs(b['boards'].get('tilted', {}).get('vol', 0) - math.pi * 64 * 50) < 0.02, b['boards'].get('tilted'))])
    # Pushing an already consumed profile again must clone a native sketch, rather than reparent its base.
    twice = dowel + [push('round_again', 'round', -20, body='other_dowel')]
    ctx.step('circle reused for second board', ctx.FIX + twice, lambda st, a, b: [ok(st, 3),
        ('both solid cylinders remain', all(abs(b['boards'].get(bid, {}).get('vol', 0)-v) < 0.02 for bid,v in [('dowel', math.pi*100*100), ('other_dowel', math.pi*100*20)]), '')])
    for radius in (0, -2):
        ctx.step('reject circle radius %s' % radius, ctx.FIX + [circle('bad_circle', [800, 0, 0], radius)],
                 lambda st, a, b: [('radius rejected', st[-1]['status'] == 'failed', st[-1]), ('fixture unchanged', a == b, '')])
    story = ctx.FIX + dowel + bore + boss + separate
    ctx.S.sync(story)
    live = snap(ctx.S)
    fresh = Session(None)
    try:
        fresh.sync(story)
        ctx.check('circle story: live equals fresh build', snap(fresh) == live)
    finally:
        fresh.close()
    # Undo restores the exact loose sketch and replay reuses it before saving.
    ctx.S.sync(story[:-1])
    ctx.check('circle story: undo push leaves loose exact circle', ctx.S.model.rect_obj('sep').getParentGeoFeatureGroup() is None)
    ctx.S.sync(story)
    ctx.check('circle story: replay equals original', snap(ctx.S) == live)
    ctx.S.save()
    path = ctx.S.path
    ctx.S.close()
    ctx.S = Session(path)
    ctx.check('circle story: reopen equals fresh build', snap(ctx.S) == live)
    ctx.check('circle story: reopened native radius', abs(ctx.S.model.rect_obj('round').Geometry[0].Radius - 10) < 1e-8)
    ctx.S.sync(ctx.FIX)
    ctx.check('circle story: undo back to fixture', snap(ctx.S) == ctx.S0)
