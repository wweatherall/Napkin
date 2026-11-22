"""T33: sub-millimetre stock, pushes, cuts and moves through real FreeCAD transactions."""
from scenario.context import face, ok, only

requires = ()


def run(ctx):
    fix = ctx.FIX
    for distance in (0.2, 25.4 / 64, 0.0012):
        move = dict(id='small_move', type='move', targets=['bottom'], vector=[distance,0,0])
        ctx.step('small move %.6f mm' % distance, fix+[move], lambda st,a,b,d=distance: [
            ok(st,1), only(a,b,{'bottom'}),
            ('exact translation', abs(ctx.S.model.body('bottom').Placement.Base.x-d)<1e-8,
             list(ctx.S.model.body('bottom').Placement.Base))])
        push = dict(id='small_push', type='push_pull',
                    target={'face':face('bottom',[0,-1,0],[300,0,9])}, distance=distance)
        ctx.step('small push %.6f mm' % distance, fix+[push], lambda st,a,b,d=distance: [
            ok(st,1), only(a,b,{'bottom'}),
            ('exact added strip', abs(b['boards']['bottom']['vol']-a['boards']['bottom']['vol']-564*18*d)<0.02,
             b['boards']['bottom']['vol'])])
    small = [dict(id='tinyrect', type='rect', plane={'normal':[0,0,1],'origin':[800,0,0]},size=[0.2,20]),
             dict(id='tinypush',type='push_pull',target={'rect':'tinyrect'},distance=0.2,body='tiny')]
    ctx.step('small rectangular stock', fix+small, lambda st,a,b: [ok(st,2), only(a,b,{'tiny'}),
        ('exact small stock volume', abs(b['boards'].get('tiny',{}).get('vol',0)-0.8)<0.01,b['boards'].get('tiny'))])
