"""T147 step 2: circles and polygons fit flush against a sloped face."""
import math
import os
import FreeCAD as App

import plane_fit
from session import Session

requires = ()


def run(ctx):
    rad = math.radians(30)
    slope_n = [math.sin(rad) / math.sqrt(2), math.sin(rad) / math.sqrt(2), math.cos(rad)]

    s = Session(os.path.join(ctx.TESTDIR, 'plane-fit-flush.FCStd'), fresh=True)
    try:
        slope_ops = [
            dict(id='sr', type='rect', plane=dict(origin=[0, 0, 200], normal=slope_n), size=[400, 400]),
            dict(id='sp', type='push_pull', target=dict(rect='sr'), distance=20.0, body='slope'),
        ]
        s.sync(slope_ops)
        sc = s.model.world_shape(s.model.body('slope')).BoundBox.Center
        ops = slope_ops + [
            dict(id='sm', type='move', targets=['slope'], vector=[-sc.x, -sc.y, 0.0]),
            dict(id='cr', type='circle', plane=dict(origin=[0, 0, 0], normal=[0, 0, 1]), radius=50.0),
            dict(id='cp', type='push_pull', target=dict(rect='cr'), distance=20.0, body='cyl'),
            dict(id='cf', type='property_edit', mode='plane_fit', body='cyl',
                 target_body='slope', axis=2, face=4, fit_mode=0),
            dict(id='pr', type='polygon', plane=dict(origin=[0, 0, 0], normal=[0, 0, 1]), sides=6, radius=50.0),
            dict(id='pp', type='push_pull', target=dict(rect='pr'), distance=20.0, body='poly'),
            dict(id='pf', type='property_edit', mode='plane_fit', body='poly',
                 target_body='slope', axis=2, face=4, fit_mode=2),
            dict(id='rr', type='rect', plane=dict(origin=[-50, -50, 0], normal=[0, 0, 1]), size=[100, 100]),
            dict(id='rp', type='push_pull', target=dict(rect='rr'), distance=20.0, body='rect_b'),
            dict(id='rf', type='property_edit', mode='plane_fit', body='rect_b',
                 target_body='slope', axis=2, face=4, fit_mode=0),
        ]
        s.sync(ops)
        ctx.check('all flush-fit ops accepted',
                  all(e['status'] == 'ok' for e in s.status()),
                  s.status())

        pt, n = plane_fit.face_plane(s.model.body('slope'), 4)
        slope_shape = s.model.world_shape(s.model.body('slope'))

        # 1: 100 mm circle butted to a 30-degree sloped face touches it within 0.01 mm.
        cyl_shape = s.model.world_shape(s.model.body('cyl'))
        cyl_dist = cyl_shape.distToShape(slope_shape)[0]
        cyl_clear = all((v.Point - pt).dot(n) >= -0.01 for v in cyl_shape.Vertexes)
        ctx.check('a circle butted to a sloped face touches it',
                  cyl_dist < 0.01 and cyl_clear,
                  (cyl_dist, cyl_clear))

        # 2: polygon fully reaching a sloped face touches it at its far point.
        poly_shape = s.model.world_shape(s.model.body('poly'))
        poly_end_signed = [(v.Point - pt).dot(n) for v in poly_shape.Vertexes if v.Point.z > 50.0]
        ctx.check('a polygon fully reaching a sloped face touches it at its far point',
                  bool(poly_end_signed) and abs(max(poly_end_signed)) < 0.01,
                  poly_end_signed)

        # 3: rectangle's fit is unchanged.
        along = App.Vector(0, 0, 1)
        denom = n.dot(along)
        rect_corners = [App.Vector(x, y, 0) for x in (-50.0, 50.0) for y in (-50.0, 50.0)]
        expected_rect = min((pt - c).dot(n) / denom for c in rect_corners)
        rect_tip = s.model.body('rect_b').Tip
        actual_rect = (rect_tip.SSFitCorners[4] - rect_tip.SSFitCorners[0]).Length
        ctx.check("a rectangle's fit is unchanged",
                  abs(actual_rect - expected_rect) < 1e-6,
                  (actual_rect, expected_rect))

        # 4 (P21): viewport _edge_inference depth from the circle profile matches worker LengthFwd.
        vp_depth = min(
            n.dot(pt - App.Vector(50.0 * math.cos(2 * math.pi * i / 360),
                                  50.0 * math.sin(2 * math.pi * i / 360), 0.0)) / denom
            for i in range(360)
        )
        worker_len = plane_fit.source_frame(s.model.body('cyl'))[0].LengthFwd.Value
        ctx.check("the viewport's predicted fit length matches FreeCAD's",
                  abs(vp_depth - worker_len) < 0.01,
                  (vp_depth, worker_len))
    finally:
        s.close()
