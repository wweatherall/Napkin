"""T84: exact regular polygon sketches, extruded and cut by Push/Pull, with transaction/reopen parity."""
import math
import FreeCAD as App
from session import Session
from scenario.context import face, ok, only, snap

requires = ()


def run(ctx):
    def polygon(rid, origin, sides=6, radius=20, normal=(0, 0, 1), on=None, **extra):
        plane = {'on': face(on, normal, origin)} if on else {'origin': origin, 'normal': normal}
        return dict(id=rid, type='polygon', plane=plane, radius=radius, sides=sides, **extra)

    def push(oid, rid, distance, **extra):
        return dict(id=oid, type='new_board' if 'body' in extra else 'push_pull', target={'rect': rid}, distance=distance, **extra)

    def area(sides, radius):
        return 0.5 * sides * radius ** 2 * math.sin(2 * math.pi / sides)

    # loose sketches: exact, constrained, one edge per side
    loose = [polygon('hex', [800, 0, 0], 6), polygon('oct', [900, 0, 0], 8, x=[1, 1, 0])]

    def sketches(st, a, b):
        out = [ok(st, 2)]
        for rid, sides, centre, turn in (('hex', 6, 800, 0.0), ('oct', 8, 900, math.pi / 4)):
            sk = ctx.S.model.rect_obj(rid)
            edges = sk.Shape.Edges
            first = App.Vector(centre + 20 * math.cos(turn), 20 * math.sin(turn), 0)
            out += [('%s is a fully constrained sketch' % rid, sk.TypeId == 'Sketcher::SketchObject' and sk.FullyConstrained, sk.TypeId),
                    ('%s has %d straight edges' % (rid, sides), len(edges) == sides and all(e.Curve.__class__.__name__ == 'Line' for e in edges), len(edges)),
                    ('%s sides are exact' % rid, all(abs(e.Length - 40 * math.sin(math.pi / sides)) < 1e-7 for e in edges), [e.Length for e in edges]),
                    ('%s has a corner toward its x' % rid, min(v.Point.distanceToPoint(first) for v in sk.Shape.Vertexes) < 1e-7, str(first))]
        return out
    ctx.step('hexagon and octagon sketches', ctx.FIX + loose, sketches)

    prism = loose + [push('hex_push', 'hex', 100, body='prism')]
    ctx.step('polygon to prism', ctx.FIX + prism, lambda st, a, b: [ok(st, 3), only(a, b, {'prism'}),
        ('exact prism volume', abs(b['boards'].get('prism', {}).get('vol', 0) - area(6, 20) * 100) < 0.02, b['boards'].get('prism')),
        ('six sides and two ends', len(ctx.S.model.world_shape(ctx.S.model.body('prism')).Faces) == 8, '')])
    for oid, sides, at in (('cut6', 6, [100, 200, 18]), ('cut8', 8, [180, 200, 18])):
        cut = [polygon(oid, at, sides, 12, on='bottom'), push(oid + '_push', oid, -18, through=True)]
        ctx.step('%d-sided through cut' % sides, ctx.FIX + cut, lambda st, a, b: [ok(st, 2), only(a, b, {'bottom'}),
            ('exact volume removed', abs(a['boards']['bottom']['vol'] - b['boards']['bottom']['vol'] - area(sides, 12) * 18) < 0.02, b['boards']['bottom']['vol'])])
    twice = prism + [push('hex_again', 'hex', -20, body='other_prism')]
    ctx.step('polygon reused for a second board', ctx.FIX + twice, lambda st, a, b: [ok(st, 4),
        ('both prisms remain', all(abs(b['boards'].get(bid, {}).get('vol', 0) - area(6, 20) * length) < 0.02 for bid, length in [('prism', 100), ('other_prism', 20)]), '')])

    for label, extra in [('2 sides', dict(sides=2)), ('100 sides', dict(sides=100)), ('6.5 sides', dict(sides=6.5)),
                         ('zero radius', dict(radius=0)), ('negative radius', dict(radius=-2))]:
        bad = polygon('bad_polygon', [800, 0, 0])
        bad.update(extra)
        ctx.step('reject polygon with ' + label, ctx.FIX + [bad],
                 lambda st, a, b: [('rejected', st[-1]['status'] == 'failed', st[-1]), ('fixture unchanged', a == b, '')])

    story = ctx.FIX + prism + [polygon('bore', [100, 200, 18], 6, 12, on='bottom'), push('bore_push', 'bore', -18, through=True)]
    ctx.S.sync(story)
    live = snap(ctx.S)
    fresh = Session(None)
    try:
        fresh.sync(story)
        ctx.check('polygon story: live equals fresh build', snap(fresh) == live)
    finally:
        fresh.close()
    ctx.S.sync(story[:-1])
    ctx.check('polygon story: undo push leaves the loose sketch', ctx.S.model.rect_obj('bore').getParentGeoFeatureGroup() is None)
    ctx.S.sync(story)
    ctx.check('polygon story: replay equals original', snap(ctx.S) == live)
    ctx.S.save()
    path = ctx.S.path
    ctx.S.close()
    ctx.S = Session(path)
    ctx.check('polygon story: reopen equals fresh build', snap(ctx.S) == live)
    reopened = ctx.S.model.rect_obj('hex')
    ctx.check('polygon story: reopened sides and radius', ctx.S.model.polygon_world(reopened)[4:] == (20.0, 6), ctx.S.model.polygon_world(reopened)[4:])
    ctx.S.sync(ctx.FIX)
    ctx.check('polygon story: undo back to fixture', snap(ctx.S) == ctx.S0)
