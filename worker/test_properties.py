"""Properties through the same journal/sync path used by Godot."""
import os, sys, tempfile, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import test_load  # Configure the FreeCAD test runtime before loading worker modules.
import FreeCAD as App
from session import Session
from object_properties import inspect  # noqa: E402
passed = 0

def check(name, cond):
    global passed
    assert cond, name
    passed += 1
    print('PASS ' + name, flush=True)

folder = os.environ.get('TESTDIR') or tempfile.mkdtemp(prefix='shop-properties-')
os.makedirs(folder, exist_ok=True)
s = Session(os.path.join(folder,'properties.FCStd'), fresh=True)
ops = [
 {'id':'r1','type':'rect','plane':{'normal':[0,0,1],'origin':[0,0,0]},'size':[100,50]},
 {'id':'pp1','type':'push_pull','target':{'rect':'r1'},'distance':20,'body':'b1'},
 {'id':'r2','type':'rect','plane':{'normal':[0,0,1],'origin':[300,0,0]},'size':[80,40]},
 {'id':'pp2','type':'push_pull','target':{'rect':'r2'},'distance':15,'body':'b2'},
]
s.sync(ops)
root = s.model.body('b1')
plane = s.model.rect_obj('r1')
plane2 = s.model.rect_obj('r2')
root_name, plane_name, other_name = root.Name, plane.Name, plane2.Name
snapshot = inspect(s.model,'b1')
check('snapshot is JSON serializable', bool(json.dumps(snapshot)))
check('board includes native rectangle feature', plane_name in [o['name'] for o in snapshot['objects']])

def row(obj, path):
    return next(f for o in inspect(s.model,'b1')['objects'] if o['name']==obj for f in o['fields'] if f['path']==path)

def edit(obj, prop, text, mode='value', expected=None):
    current = row(obj,prop)
    op = dict(id='pr'+str(len(ops)),type='property_edit',body='b1',object=obj,property=prop,value=text,mode=mode,
              expected=expected or {'value':current['value'],'expression':current['expression']})
    ops.append(op); s.sync(ops)
    return s.status()[-1]

check('native dimension is editable', row(plane_name,'Length')['editable'])
check('metadata is read-only', not row(root_name,'BodyId')['editable'])
check('label edit succeeds',edit(root_name,'Label','Side rail')['status']=='ok')
check('label lives on native object', s.doc.getObject(root_name).Label=='Side rail')
check('mixed unit dimension succeeds',edit(plane_name,'Length','5in + 23mm')['status']=='ok')
check('geometry recomputes', abs(s.model.world_shape(s.model.body('b1')).Volume-150*50*20)<1e-6)
check('placement edit succeeds', edit(root_name,'Placement.Base.x','1in')['status']=='ok')
check('placement has exact value',abs(s.model.body('b1').Placement.Base.x-25.4)<1e-8)
check('linked expression succeeds',edit(plane_name,'Length',other_name+'.Length * 2','expression')['status']=='ok')
check('expression result and formula exposed',row(plane_name,'Length')['expression']!='' and abs(s.doc.getObject(plane_name).Length.Value-160)<1e-8)
# Editing referenced board through a native property op must update the first board.
ops.append(dict(id='ref1',type='property_edit',body='b2',object=other_name,property='Length',value='90mm',mode='value'))
s.sync(ops)
check('linked measurement follows source',abs(s.doc.getObject(plane_name).Length.Value-180)<1e-8)
s.save()
path=s.path;App.closeDocument(s.doc.Name)
s=Session(path)
check('saved expressions survive reopen',row(plane_name,'Length')['expression']!='' and abs(s.doc.getObject(plane_name).Length.Value-180)<1e-8)
prior=len(ops)
check('explicit value replaces expression',edit(plane_name,'Length','200mm')['status']=='ok')
check('formula cleared only by explicit value mode',row(plane_name,'Length')['expression']=='')
s.sync(ops[:prior])
check('undo restores expression',row(plane_name,'Length')['expression']!='')
s.sync(ops)
check('redo restores value',abs(s.doc.getObject(plane_name).Length.Value-200)<1e-8)
check('stale edit rejected',edit(plane_name,'Length','300mm',expected={'value':'obsolete','expression':''})['status']=='failed')
ops.pop();s.sync(ops)
check('wrong units rejected',edit(plane_name,'Length','3kg')['status']=='failed')
ops.pop();s.sync(ops)
check('metadata edit rejected',edit(root_name,'BodyId','bad')['status']=='failed')
ops.pop();s.sync(ops)
check('cycle rejected',edit(plane_name,'Length',plane_name+'.Length * 2','expression')['status']=='failed')
ops.pop();s.sync(ops)
check('failed expression leaves value intact',abs(s.doc.getObject(plane_name).Length.Value-200)<1e-8 and row(plane_name,'Length')['expression']=='')
s.save()
path=s.path;App.closeDocument(s.doc.Name)
s=Session(path)
check('reopen retains label and geometry',s.doc.getObject(root_name).Label=='Side rail' and abs(s.doc.getObject(plane_name).Length.Value-200)<1e-8)
s.sync(ops[:prior])
check('reopened undo rebuild restores expression',row(plane_name,'Length')['expression']!='')
# A component instance exposes its shared definition and dimension edits affect its family.
s.sync(ops[:prior])
family_ops=ops[:prior]+[dict(id='copy1',type='move',targets=['b1'],vector=[0,200,0],copy=True,new_ids=['b3'])]
s.sync(family_ops)
instance=inspect(s.model,'b3')
check('instance exposes shared definition',plane_name in [o['name'] for o in instance['objects']])
family_ops.append(dict(id='prop_family',type='property_edit',body='b3',object=plane_name,property='Length',value='210mm',mode='value'))
s.sync(family_ops)
check('instance dimension edit succeeds',s.status()[-1]['status']=='ok')
check('shared dimension updates both copies', all(abs(s.model.world_shape(s.model.body(b)).Volume-210000)<1e-6 for b in ['b1','b3']))
# Tilt a target about Y: the near and far ends differ by 100 mm at 45 degrees.
fit_session = Session(os.path.join(folder,'fit.FCStd'), fresh=True)
base_ops = ops[:4]
fit_session.sync(base_ops)
target = fit_session.model.body('b2')
target.Placement = App.Placement(App.Vector(0,0,200), App.Rotation(App.Vector(0,1,0),45))
# Keep the target rectangle origin at its board origin.
pl = fit_session.model.rect_obj('r2')
pose = pl.Placement
pose.Base = App.Vector()
pl.Placement = pose
fit_session.doc.recompute()
for mode, expected in enumerate([500000,750000,1000000]):
    fit = dict(type='fit',id='fit'+str(mode),body='b1',
               target_body='b2',axis=2,face=4,fit_mode=mode)
    fit_ops = base_ops + [fit]
    fit_session.sync(fit_ops)
    check('tilted fit mode '+str(mode),fit_session.status()[-1]['status']=='ok' and
          abs(fit_session.model.world_shape(fit_session.model.body('b1')).Volume-expected)<0.01)
fit_session.sync(fit_ops+[dict(type='move',id='translate',targets=['b2'],vector=[0,0,10])])
check('target movement updates fit',abs(fit_session.model.world_shape(fit_session.model.body('b1')).Volume-1050000)<0.01)
fit_session.save()
fit_path=fit_session.path
App.closeDocument(fit_session.doc.Name)
fit_session=Session(fit_path)
check('reopened fit retains target and result',fit_session.model.body('b1').Tip.SSTargetId=='b2' and
      'Bottom face' in fit_session.model.body('b1').Tip.SSFitResult)
detach = dict(type='unfit',id='replace',body='b1',axis=2,value='2 cm')
fit_session.sync([item["op"] for item in fit_session.applied] + [detach])
check('explicit length detaches fit',fit_session.model.body('b1').Tip.TypeId=='Part::Extrusion' and
      abs(fit_session.model.world_shape(fit_session.model.body('b1')).Volume-100000)<0.01)
# A new extruded rectangle and its edge-inferred face tie share one journal entry.
edge_session = Session(os.path.join(folder,'edge.FCStd'), fresh=True)
rail = [dict(base_ops[2],plane={'normal':[0,0,1],'origin':[0,0,80]}),base_ops[3]]
new_leg = dict(base_ops[1],edge_fit={'target_body':'b2','face':4})
edge_ops = rail + [base_ops[0],new_leg]
edge_session.sync(edge_ops)
def piece_volume():
    return edge_session.model.world_shape(edge_session.model.body('b1')).Volume
check('rectangle edge push reaches rail underside', abs(piece_volume()-400000)<0.01)
edge_session.sync(edge_ops+[dict(type='move',id='raise',targets=['b2'],vector=[0,0,10])])
check('edge push follows raised rail',abs(piece_volume()-450000)<0.01)
edge_session.sync(edge_ops[:-1])
check('one undo removes the extruded piece and fit','b1' not in edge_session.model.bodies())
# The three end conditions through a push (I41), here to a level rail: all three give the same 400000 mm3.
for mode in (1, 2):
    edge_session.sync(rail + [base_ops[0], dict(new_leg, id='pp1_'+str(mode), edge_fit={'target_body':'b2','face':4,'fit_mode':mode})])
    check('push end condition '+str(mode)+' is stored', edge_session.model.body('b1').Tip.SSMode == mode and abs(piece_volume()-400000)<0.01)
edge_session.sync(edge_ops)
# Pull the low end of a board down to a rail. Replacing its length keeps the high end fixed.
raised_leg = dict(base_ops[0],plane={'normal':[0,0,1],'origin':[0,0,200]})
low_fit = dict(type='push_pull',id='low',target={'face':{'body':'b1','normal':[0,0,-1],'point':[40,20,200]}},
               distance=105,edge_fit={'target_body':'b2','face':5})
low_ops = rail+[raised_leg,base_ops[1],low_fit]
edge_session.sync(low_ops)
check('push from low end anchors the high end',abs(piece_volume()-625000)<0.01)
edge_session.sync(low_ops+[dict(detach,id='low_replace')])
bounds=edge_session.model.world_shape(edge_session.model.body('b1')).BoundBox
check('detaching low end preserves high end',abs(bounds.ZMax-220)<0.01 and abs(bounds.ZMin-200)<0.01)
# Detach to a numeric length, then pull the entire top another 990 mm.
test_board = edge_session.model.body('b1')
pick = test_board.Shape.BoundBox
repull = dict(type='push_pull',id='repull',distance=990,resize_stock=True,
              target={'face':{'body':'b1','normal':[0,0,1],'point':[40,20,pick.ZMax]}})
recent = [item['op'] for item in edge_session.applied]
edge_session.sync(recent+[repull])
frame = inspect(edge_session.model,'b1')['boards']['b1']
check('numeric re-pull keeps dimensions editable',abs(frame['sizes'][2]-1010)<0.001 and
      abs(edge_session.model.world_shape(edge_session.model.body('b1')).BoundBox.ZMin-200)<0.001)
edge_session.sync(recent)
check('undo numeric re-pull restores dimension',abs(piece_volume()-100000)<0.01)
# Pushing a tied end again detaches it (I26b, I40). A leg fitted up to a rail's underside at 300, pushed 50 more:
# square ends go back to plain stock (dimensions editable), a sloped end keeps its shape; the rail no longer drags it.
re_session = Session(os.path.join(folder,'repush.FCStd'), fresh=True)
re_ops = [
 {'id':'r1','type':'rect','plane':{'normal':[0,0,1],'origin':[0,0,0]},'size':[40,20]},
 {'id':'pp1','type':'push_pull','target':{'rect':'r1'},'distance':100,'body':'b1'},
 {'id':'r2','type':'rect','plane':{'normal':[0,0,1],'origin':[-50,-50,300]},'size':[200,200]},
 {'id':'pp2','type':'push_pull','target':{'rect':'r2'},'distance':20,'body':'b2'},
 dict(type='fit',id='fit',body='b1',target_body='b2',axis=2,face=4,fit_mode=0),
 {'id':'again','type':'push_pull','target':{'face':{'body':'b1','normal':[0,0,1],'point':[20,10,300]}},'distance':50},
]
re_session.sync(re_ops)
leg = lambda: re_session.model.world_shape(re_session.model.body('b1')).BoundBox
check('pushing the tied end again detaches it', re_session.status()[-1]['status']=='ok' and abs(leg().ZMax-350)<0.01
      and re_session.model.body('b1').Tip.TypeId=='Part::Extrusion' and inspect(re_session.model,'b1')['boards']['b1']['sizes'][2]==350)
re_session.sync(re_ops+[dict(type='move',id='mv',targets=['b2'],vector=[0,0,100])])
check('a detached end stays put when the rail moves', abs(leg().ZMax-350)<0.01)
re_session.sync(re_ops[:-1])
check('undoing the push ties the end again', hasattr(re_session.model.body('b1').Tip,'SSStock') and abs(leg().ZMax-300)<0.01)
# A sloped (Slice) end pushed again: shape kept, tie gone, the push added on.
tilt = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,1,0),20))
slice_ops = re_ops[:4]
re_session.sync(slice_ops)
rail = re_session.model.body('b2'); rail.Placement = App.Placement(App.Vector(-50,-50,300), App.Rotation(App.Vector(0,1,0),20)).multiply(App.Placement(App.Vector(50,50,-300), App.Rotation()))
re_session.doc.recompute()
slice_fit = dict(re_ops[4], id='slicefit', fit_mode=1)
re_session.sync(slice_ops+[slice_fit])
end = __import__('plane_fit').fitted_end(re_session.model.body('b1'))
check('slice fit has a sloped end', re_session.status()[-1]['status']=='ok' and end is not None and end[0].z < 0.99)
up = dict(id='slice_again',type='push_pull',distance=30,target={'face':{'body':'b1','normal':list(end[0]),'point':list(end[1])}})
re_session.sync(slice_ops+[slice_fit,up])
tip = re_session.model.body('b1').Tip
fit_obj = next(o for o in re_session.doc.Objects if hasattr(o,'SSFitResult'))
check('pushing a sloped tied end detaches it and adds the push', re_session.status()[-1]['status']=='ok' and fit_obj.SSTargetId=='' and not hasattr(tip,'SSStock'))
# Result lines are written in mm to 0.1, never as 1.05e+03.
import plane_fit
check('fit lengths read as millimetres', plane_fit.mm(1050.0)=='1050 mm' and plane_fit.mm(302.46)=='302.5 mm')

# T60: chains of face ties (A <- B <- C), sloped targets, cycle rejection, invalid move rollback, delete detach.
chain_session = Session(os.path.join(folder, 'chain.FCStd'), fresh=True)
# Create C (b3) before B (b2) in doc.Objects to verify topological propagation order.
chain_base = [
    {'id':'ca_r','type':'rect','plane':{'normal':[0,0,1],'origin':[0,0,300]},'size':[200,60]},
    {'id':'ca_p','type':'push_pull','target':{'rect':'ca_r'},'distance':20,'body':'b1'},
    {'id':'cc_r','type':'rect','plane':{'normal':[0,0,1],'origin':[10,10,0]},'size':[40,20]},
    {'id':'cc_p','type':'push_pull','target':{'rect':'cc_r'},'distance':20,'body':'b3'},
    {'id':'cb_r','type':'rect','plane':{'normal':[0,0,1],'origin':[0,0,100]},'size':[100,40]},
    {'id':'cb_p','type':'push_pull','target':{'rect':'cb_r'},'distance':20,'body':'b2'},
]
fit_ba = dict(type='fit', id='fit_ba', body='b2', target_body='b1', axis=2, face=4, fit_mode=0)
fit_cb = dict(type='fit', id='fit_cb', body='b3', target_body='b2', axis=2, face=5, fit_mode=0)
chain_ops = chain_base + [fit_ba, fit_cb]
chain_session.sync(chain_ops)
cvol = lambda bid: chain_session.model.world_shape(chain_session.model.body(bid)).Volume
cbbox = lambda bid: chain_session.model.world_shape(chain_session.model.body(bid)).BoundBox
b_snap = plane_fit.snapshot(chain_session.model.body('b2'))
check('chain A <- B <- C initial volumes and snapshot fitted_end',
      all(e['status'] == 'ok' for e in chain_session.status())
      and abs(cvol('b2') - 100 * 40 * 200) < 0.01 and abs(cbbox('b2').ZMax - 300) < 0.01
      and abs(cvol('b3') - 40 * 20 * 300) < 0.01 and abs(cbbox('b3').ZMax - 300) < 0.01
      and b_snap.get('fitted_end', {}).get('face') == 5
      and abs(b_snap['fitted_end']['point'][2] - 300) < 0.01)
# Moving A updates both B and C even though C precedes B in doc.Objects.
move_a = dict(type='move', id='move_a', targets=['b1'], vector=[0, 0, 50])
chain_session.sync(chain_ops + [move_a])
check('chain moving A updates B and C',
      chain_session.status()[-1]['status'] == 'ok'
      and abs(cvol('b2') - 100 * 40 * 250) < 0.01 and abs(cbbox('b2').ZMax - 350) < 0.01
      and abs(cvol('b3') - 40 * 20 * 350) < 0.01 and abs(cbbox('b3').ZMax - 350) < 0.01)
# Undo restores both B and C.
chain_session.sync(chain_ops)
check('chain undo restores B and C',
      abs(cvol('b2') - 100 * 40 * 200) < 0.01 and abs(cvol('b3') - 40 * 20 * 300) < 0.01)
# Save + reopen preserves both ties and keeps following further moves of A.
chain_session.save()
chain_path = chain_session.path
App.closeDocument(chain_session.doc.Name)
chain_session = Session(chain_path)
check('chain reopen preserves both ties',
      chain_session.model.body('b2').Tip.SSTargetId == 'b1'
      and chain_session.model.body('b3').Tip.SSTargetId == 'b2')
chain_session.sync(chain_ops + [dict(type='move', id='move_a2', targets=['b1'], vector=[0, 0, 25])])
check('chain reopened follows further moves of A',
      abs(cvol('b2') - 100 * 40 * 225) < 0.01 and abs(cvol('b3') - 40 * 20 * 325) < 0.01)
chain_session.sync(chain_ops)
# Direct (A -> B -> A) and 3-board (A -> C -> B -> A) cycles are rejected cleanly.
cyc2 = dict(type='fit', id='cyc2', body='b1', target_body='b2', axis=2, face=5, fit_mode=0)
chain_session.sync(chain_ops + [cyc2])
check('direct 2-board cycle rejected and leaves prior fits intact',
      chain_session.status()[-1]['status'] == 'failed'
      and 'cycle' in chain_session.status()[-1].get('message', '').lower()
      and chain_session.model.body('b2').Tip.SSTargetId == 'b1'
      and chain_session.model.body('b3').Tip.SSTargetId == 'b2'
      and abs(cvol('b2') - 100 * 40 * 200) < 0.01 and abs(cvol('b3') - 40 * 20 * 300) < 0.01)
cyc3 = dict(type='fit', id='cyc3', body='b1', target_body='b3', axis=2, face=5, fit_mode=0)
chain_session.sync(chain_ops + [cyc3])
check('3-board cycle rejected and leaves prior fits intact',
      chain_session.status()[-1]['status'] == 'failed'
      and 'cycle' in chain_session.status()[-1].get('message', '').lower()
      and chain_session.model.body('b2').Tip.SSTargetId == 'b1'
      and chain_session.model.body('b3').Tip.SSTargetId == 'b2')
chain_session.sync(chain_ops)
# Moving A past B's start rejects the move and leaves A, B, and C at last valid geometry.
bad_move = dict(type='move', id='move_past_b', targets=['b1'], vector=[0, 0, -250])
chain_session.sync(chain_ops + [bad_move])
check('moving A past B start rolls back A, B, and C',
      chain_session.status()[-1]['status'] == 'failed'
      and abs(cbbox('b1').ZMin - 300) < 0.01
      and abs(cvol('b2') - 100 * 40 * 200) < 0.01
      and abs(cvol('b3') - 40 * 20 * 300) < 0.01)
chain_session.sync(chain_ops)
# Deleting intermediate B detaches C with unavailable message while keeping C's last geometry.
del_b = dict(type='delete', id='del_b', targets=['b2'])
chain_session.sync(chain_ops + [del_b])
check('deleting intermediate B detaches C and retains geometry',
      chain_session.status()[-1]['status'] == 'ok'
      and chain_session.model.body('b3').Tip.SSTargetId == ''
      and chain_session.model.body('b3').Tip.SSFitResult == 'Reference unavailable · last geometry retained'
      and abs(cvol('b3') - 40 * 20 * 300) < 0.01 and abs(cbbox('b3').ZMax - 300) < 0.01)
App.closeDocument(chain_session.doc.Name)

# Chain through a sloped Slice at plane target: B sliced to tilted A, C sliced to B's sloped fitted end.
sloped_session = Session(os.path.join(folder, 'chain_sloped.FCStd'), fresh=True)
sloped_base = [
    {'id':'sa_r','type':'rect','plane':{'normal':[0,0,1],'origin':[0,0,0]},'size':[150,80]},
    {'id':'sa_p','type':'push_pull','target':{'rect':'sa_r'},'distance':15,'body':'b1'},
    {'id':'sb_r','type':'rect','plane':{'normal':[0,0,1],'origin':[0,0,0]},'size':[100,50]},
    {'id':'sb_p','type':'push_pull','target':{'rect':'sb_r'},'distance':20,'body':'b2'},
    {'id':'sc_r','type':'rect','plane':{'normal':[0,0,1],'origin':[20,0,0]},'size':[40,20]},
    {'id':'sc_p','type':'push_pull','target':{'rect':'sc_r'},'distance':10,'body':'b3'},
]
sloped_session.sync(sloped_base)
sa = sloped_session.model.body('b1')
sa.Placement = App.Placement(App.Vector(0, 0, 200), App.Rotation(App.Vector(0, 1, 0), 45))
sloped_session.doc.recompute()
s_fit_ba = dict(type='fit', id='sfit_ba', body='b2', target_body='b1', axis=2, face=4, fit_mode=1)
s_fit_cb = dict(type='fit', id='sfit_cb', body='b3', target_body='b2', axis=2, face=5, fit_mode=1)
sloped_ops = sloped_base + [s_fit_ba, s_fit_cb]
sloped_session.sync(sloped_ops)
svol = lambda bid: sloped_session.model.world_shape(sloped_session.model.body(bid)).Volume
end_b = plane_fit.fitted_end(sloped_session.model.body('b2'))
end_c = plane_fit.fitted_end(sloped_session.model.body('b3'))
check('chain through sloped Slice target meets B actual sloped plane',
      all(e['status'] == 'ok' for e in sloped_session.status())
      and abs(svol('b2') - 100 * 50 * 150) < 0.01
      and abs(svol('b3') - 40 * 20 * 160) < 0.01
      and end_b is not None and end_c is not None and end_b[0].dot(end_c[0]) > 0.9999)
sloped_session.sync(sloped_ops + [dict(type='move', id='smove_a', targets=['b1'], vector=[0, 0, 20])])
check('chain through sloped Slice target follows when A moves',
      sloped_session.status()[-1]['status'] == 'ok'
      and abs(svol('b2') - 100 * 50 * 170) < 0.01
      and abs(svol('b3') - 40 * 20 * 180) < 0.01)
App.closeDocument(sloped_session.doc.Name)

# T61: face ties on linked copies (component definitions and instances).
lc_session = Session(os.path.join(folder, 'linked_copies.FCStd'), fresh=True)
lc_base = [
    {'id':'lt_r','type':'rect','plane':{'normal':[0,0,1],'origin':[0,0,200]},'size':[260,120]},
    {'id':'lt_p','type':'push_pull','target':{'rect':'lt_r'},'distance':20,'body':'t1'},
    {'id':'lb_r','type':'rect','plane':{'normal':[0,0,1],'origin':[0,0,0]},'size':[40,20]},
    {'id':'lb_p','type':'push_pull','target':{'rect':'lb_r'},'distance':50,'body':'b1'},
    {'id':'lb_cp','type':'move','targets':['b1'],'vector':[100,0,0],'copy':True,'new_ids':['b2']},
    {'id':'lc_r','type':'rect','plane':{'normal':[0,0,1],'origin':[100,40,0]},'size':[30,20]},
    {'id':'lc_p','type':'push_pull','target':{'rect':'lc_r'},'distance':30,'body':'c1'},
]
lc_fit_b1 = dict(type='fit', id='lc_fit_b1', body='b1', target_body='t1', axis=2, face=4, fit_mode=0)
lc_ops = lc_base + [lc_fit_b1]
lc_session.sync(lc_ops)
lvol = lambda bid: lc_session.model.world_shape(lc_session.model.body(bid)).Volume
lbbox = lambda bid: lc_session.model.world_shape(lc_session.model.body(bid)).BoundBox
check('T61 fit linked copy updates both siblings',
      all(e['status'] == 'ok' for e in lc_session.status())
      and abs(lvol('b1') - 40 * 20 * 200) < 0.01 and abs(lvol('b2') - 40 * 20 * 200) < 0.01
      and abs(lbbox('b1').ZMax - 200) < 0.01 and abs(lbbox('b2').ZMax - 200) < 0.01)
lc_move_t1 = dict(type='move', id='lc_mv_t1', targets=['t1'], vector=[0, 0, 30])
lc_session.sync(lc_ops + [lc_move_t1])
check('T61 moving target updates both linked siblings',
      lc_session.status()[-1]['status'] == 'ok'
      and abs(lvol('b1') - 40 * 20 * 230) < 0.01 and abs(lvol('b2') - 40 * 20 * 230) < 0.01)
lc_session.sync(lc_ops)
check('T61 undo restores both linked siblings',
      abs(lvol('b1') - 40 * 20 * 200) < 0.01 and abs(lvol('b2') - 40 * 20 * 200) < 0.01)
lc_session.save()
lc_path = lc_session.path
App.closeDocument(lc_session.doc.Name)
lc_session = Session(lc_path)
lc_dfn = lc_session.model.body('b1').LinkedObject
check('T61 save and reopen preserves shared tie on definition',
      lc_dfn.Tip.SSTargetId == 't1' and lc_dfn.Tip.SSSourceBodyId == 'b1')
lc_session.sync(lc_ops + [dict(type='move', id='lc_mv_t1_reopen', targets=['t1'], vector=[0, 0, 20])])
check('T61 reopened linked tie follows target movement',
      abs(lvol('b1') - 40 * 20 * 220) < 0.01 and abs(lvol('b2') - 40 * 20 * 220) < 0.01)
lc_session.sync(lc_ops)

# T61 Slice mode on linked copies with tilted target.
lc_slice_session = Session(os.path.join(folder, 'linked_slice.FCStd'), fresh=True)
lc_slice_base = lc_base[:5]
lc_slice_session.sync(lc_slice_base)
st1 = lc_slice_session.model.body('t1')
st1.Placement = App.Placement(App.Vector(0, 0, 200), App.Rotation(App.Vector(0, 1, 0), 45))
st1_pl = lc_slice_session.model.rect_obj('lt_r')
sp = st1_pl.Placement; sp.Base = App.Vector(); st1_pl.Placement = sp
lc_slice_session.doc.recompute()
lc_slice_fit = dict(type='fit', id='lc_sfit', body='b1', target_body='t1', axis=2, face=4, fit_mode=1)
lc_slice_session.sync(lc_slice_base + [lc_slice_fit])
lsvol = lambda bid: lc_slice_session.model.world_shape(lc_slice_session.model.body(bid)).Volume
check('T61 Slice mode updates both linked copies',
      lc_slice_session.status()[-1]['status'] == 'ok'
      and abs(lsvol('b1') - 40 * 20 * 180) < 0.01 and abs(lsvol('b2') - 40 * 20 * 180) < 0.01)
lc_slice_session.sync(lc_slice_base + [lc_slice_fit, dict(type='move', id='lc_smv', targets=['t1'], vector=[0, 0, 10])])
check('T61 Slice mode follows moved tilted target on both copies',
      abs(lsvol('b1') - 40 * 20 * 190) < 0.01 and abs(lsvol('b2') - 40 * 20 * 190) < 0.01)
App.closeDocument(lc_slice_session.doc.Name)

# T61 Check 2: chain t1 <- (b1, b2) <- c1 (c1 fitted to linked sibling b2's fitted end).
lc_fit_c1 = dict(type='fit', id='lc_fit_c1', body='c1', target_body='b2', axis=2, face=5, fit_mode=0)
lc_chain_ops = lc_ops + [lc_fit_c1]
lc_session.sync(lc_chain_ops)
check('T61 board c1 fits to linked sibling b2 fitted end',
      lc_session.status()[-1]['status'] == 'ok'
      and abs(lvol('c1') - 30 * 20 * 200) < 0.01 and abs(lbbox('c1').ZMax - 200) < 0.01)
lc_session.sync(lc_chain_ops + [dict(type='move', id='lc_mv_chain', targets=['t1'], vector=[0, 0, 40])])
check('T61 moving t1 ripples through linked family (b1, b2) to c1',
      abs(lvol('b1') - 40 * 20 * 240) < 0.01 and abs(lvol('b2') - 40 * 20 * 240) < 0.01
      and abs(lvol('c1') - 30 * 20 * 240) < 0.01)
lc_session.sync(lc_chain_ops)

# T61 Check 3: self-sibling fit (b1 -> b2) and cross-sibling cycle (b1 -> c1 -> b2) rejected cleanly.
lc_self_sib = dict(type='fit', id='lc_self_sib', body='b1', target_body='b2', axis=0, face=0, fit_mode=0)
lc_session.sync(lc_chain_ops + [lc_self_sib])
check('T61 self-sibling fit rejected without mutating',
      lc_session.status()[-1]['status'] == 'failed'
      and 'different board' in lc_session.status()[-1].get('message', '')
      and lc_session.model.body('b1').LinkedObject.Tip.SSTargetId == 't1'
      and abs(lvol('b1') - 40 * 20 * 200) < 0.01)
lc_cross_cyc = dict(type='fit', id='lc_cross_cyc', body='b1', target_body='c1', axis=2, face=5, fit_mode=0)
lc_session.sync(lc_chain_ops + [lc_cross_cyc])
check('T61 cross-sibling cycle b1 -> c1 -> b2 rejected without mutating',
      lc_session.status()[-1]['status'] == 'failed'
      and 'cycle' in lc_session.status()[-1].get('message', '').lower()
      and lc_session.model.body('b1').LinkedObject.Tip.SSTargetId == 't1'
      and lc_session.model.body('c1').Tip.SSTargetId == 'b2'
      and abs(lvol('b1') - 40 * 20 * 200) < 0.01)
lc_session.sync(lc_ops)

# T61 Check 4: Make unique on non-driving b2 and on driving b1 (with b2 & b3 remaining).
lc_cp3 = {'id':'lb_cp3','type':'move','targets':['b1'],'vector':[200,0,0],'copy':True,'new_ids':['b3']}
lc_three = lc_ops + [lc_cp3]
lc_session.sync(lc_three + [dict(type='make_unique', id='lc_uniq_b2', targets=['b2']),
                            dict(type='move', id='lc_mv_after_u2', targets=['t1'], vector=[0, 0, 25])])
check('T61 make unique on non-driving b2 detaches b2 while b1 and b3 follow t1',
      lc_session.status()[-1]['status'] == 'ok'
      and lc_session.model.body('b2').TypeId == 'App::Part'
      and lc_session.model.body('b2').Tip.SSTargetId == ''
      and lc_session.model.body('b2').Tip.SSFitResult == 'Detached · shape kept'
      and abs(lvol('b2') - 40 * 20 * 200) < 0.01
      and abs(lvol('b1') - 40 * 20 * 225) < 0.01
      and abs(lvol('b3') - 40 * 20 * 225) < 0.01)
lc_session.sync(lc_three + [dict(type='make_unique', id='lc_uniq_b1', targets=['b1']),
                            dict(type='move', id='lc_mv_after_u1', targets=['t1'], vector=[0, 0, 25])])
check('T61 make unique on driving b1 hands driving duty to surviving sibling so b2 and b3 follow t1',
      lc_session.status()[-1]['status'] == 'ok'
      and lc_session.model.body('b1').TypeId == 'App::Part'
      and lc_session.model.body('b1').Tip.SSTargetId == ''
      and lc_session.model.body('b2').LinkedObject.Tip.SSSourceBodyId in ('b2', 'b3')
      and abs(lvol('b1') - 40 * 20 * 200) < 0.01
      and abs(lvol('b2') - 40 * 20 * 225) < 0.01
      and abs(lvol('b3') - 40 * 20 * 225) < 0.01)

# T61 Check 5: push_fitted_end and replace_fit on linked copy detach and update all siblings.
lc_push_end = {'id':'lc_push_end','type':'push_pull','distance':30,
               'target':{'face':{'body':'b2','normal':[0,0,1],'point':[120,10,200]}}}
lc_session.sync(lc_ops + [lc_push_end])
check('T61 pushing linked copy tied end detaches and updates all siblings',
      lc_session.status()[-1]['status'] == 'ok'
      and lc_session.model.body('b1').LinkedObject.Tip.TypeId == 'Part::Extrusion'
      and abs(lvol('b1') - 40 * 20 * 230) < 0.01 and abs(lvol('b2') - 40 * 20 * 230) < 0.01)
lc_session.sync(lc_ops + [lc_push_end, dict(type='move', id='lc_mv_detached', targets=['t1'], vector=[0, 0, 50])])
check('T61 detached linked siblings stay put when former target moves',
      abs(lvol('b1') - 40 * 20 * 230) < 0.01 and abs(lvol('b2') - 40 * 20 * 230) < 0.01)
lc_replace = dict(type='unfit', id='lc_replace', body='b2', axis=2, value='120 mm')
lc_session.sync(lc_ops + [lc_replace])
check('T61 replace_fit on linked copy detaches and updates all siblings',
      lc_session.status()[-1]['status'] == 'ok'
      and lc_session.model.body('b1').LinkedObject.Tip.TypeId == 'Part::Extrusion'
      and abs(lvol('b1') - 40 * 20 * 120) < 0.01 and abs(lvol('b2') - 40 * 20 * 120) < 0.01)
App.closeDocument(lc_session.doc.Name)

# T127: enriched summary in inspect() for plain, assembly, linked, fitted, and cut/non-rectangular boards.
sum_session = Session(os.path.join(folder, 'summary.FCStd'), fresh=True)
sum_ops = [
    {'id': 'sr1', 'type': 'rect', 'plane': {'normal': [0, 0, 1], 'origin': [0, 0, 0]}, 'size': [120, 60]},
    {'id': 'sp1', 'type': 'push_pull', 'target': {'rect': 'sr1'}, 'distance': 20, 'body': 'b1'},
    {'id': 'sr2', 'type': 'rect', 'plane': {'normal': [0, 0, 1], 'origin': [0, 0, 200]}, 'size': [150, 80]},
    {'id': 'sp2', 'type': 'push_pull', 'target': {'rect': 'sr2'}, 'distance': 20, 'body': 'b2'},
]
sum_session.sync(sum_ops)
s_plain = inspect(sum_session.model, 'b1')['summary']
check('plain board summary has label, Board context, non-parametric, 3 editable dims',
      s_plain['label'] == sum_session.model.body('b1').Label
      and s_plain['context'] == 'Board'
      and s_plain['parametric'] is False
      and len(s_plain['dimensions']) == 3
      and all(d['editable'] and not d['linked'] for d in s_plain['dimensions']))

sum_session.sync(sum_ops + [
    {'id': 'scp', 'type': 'move', 'targets': ['b1'], 'vector': [200, 0, 0], 'copy': True, 'new_ids': ['b3']},
    {'id': 'sas', 'type': 'make_assembly', 'targets': ['b1'], 'new_id': 'a1', 'name': 'Leg Frame'},
    {'id': 'sfit', 'type': 'fit', 'body': 'b1', 'target_body': 'b2', 'axis': 2, 'face': 4, 'fit_mode': 0},
])
s_linked_asm = inspect(sum_session.model, 'b1')['summary']
check('linked + assembly + fitted summary has context, parametric=True, and target info',
      'Part within Leg Frame' in s_linked_asm['context']
      and 'Linked component (2 instances)' in s_linked_asm['context']
      and s_linked_asm['parametric'] is True
      and s_linked_asm['dimensions'][2]['linked'] is True
      and s_linked_asm['dimensions'][2]['target_label'] == sum_session.model.body('b2').Label
      and s_linked_asm['dimensions'][2]['target_face'] == 'Bottom face')

# Cut/non-rectangular board (no plane_fit snapshot) still gets read-only BoundBox summary dimensions.
cut_shape = sum_session.model.body('b2').Tip.Shape.cut(
    __import__('Part').makeBox(30, 30, 30, App.Vector(0, 0, 195))
)
cut_feat = sum_session.doc.addObject('Part::Feature', 'CutBoard')
cut_feat.Shape = cut_shape
b2_body = sum_session.model.body('b2')
b2_body.Tip = cut_feat
sum_session.doc.recompute()
s_cut = inspect(sum_session.model, 'b2')['summary']
check('cut board summary falls back to read-only BoundBox extents',
      not inspect(sum_session.model, 'b2')['boards']['b2'].get('rectangular', True)
      and len(s_cut['dimensions']) == 3
      and all(not d['editable'] and d['value_mm'] > 0 for d in s_cut['dimensions']))
App.closeDocument(sum_session.doc.Name)

# T62: face ties to and from circular, closed-line, and cut boards.
t62_session = Session(os.path.join(folder, 't62.FCStd'), fresh=True)
t62_ops = [
    {'id': 'r1', 'type': 'rect', 'plane': {'normal': [0, 0, 1], 'origin': [0, 0, 0]}, 'size': [40, 40]},
    {'id': 'p1', 'type': 'push_pull', 'target': {'rect': 'r1'}, 'distance': 20, 'body': 'b_rect'},
    {'id': 'c1', 'type': 'circle', 'plane': {'normal': [0, 0, 1], 'origin': [20, 20, 120]}, 'radius': 30},
    {'id': 'p2', 'type': 'push_pull', 'target': {'rect': 'c1'}, 'distance': 20, 'body': 'b_cyl'},
    {'id': 'r2', 'type': 'rect', 'plane': {'normal': [0, 0, 1], 'origin': [120, 0, 0]}, 'size': [80, 60]},
    {'id': 'p3', 'type': 'push_pull', 'target': {'rect': 'r2'}, 'distance': 30, 'body': 'b_cut'},
    {'id': 'rp', 'type': 'rect', 'plane': {'on': {'body': 'b_cut', 'normal': [0, 0, 1], 'point': [160, 30, 30]}}, 'corner': [-10, -10], 'size': [20, 20]},
    {'id': 'pp', 'type': 'push_pull', 'target': {'rect': 'rp'}, 'distance': -10},
    {'id': 'r3', 'type': 'rect', 'plane': {'normal': [0, 0, 1], 'origin': [0, 0, 220]}, 'size': [250, 120]},
    {'id': 'p4', 'type': 'push_pull', 'target': {'rect': 'r3'}, 'distance': 20, 'body': 'b_top'},
]
t62_session.sync(t62_ops)
check('T62 snapshots expose planar faces for circular and cut boards',
      not plane_fit.snapshot(t62_session.model.body('b_cyl'))['rectangular']
      and len(plane_fit.planar_faces(t62_session.model.body('b_cyl'))) == 2
      and not plane_fit.snapshot(t62_session.model.body('b_cut'))['rectangular']
      and len(plane_fit.planar_faces(t62_session.model.body('b_cut'))) >= 6)

# 1. Tie rectangular board to circular board's bottom face (z=120), then move circular board.
cyl_faces = plane_fit.planar_faces(t62_session.model.body('b_cyl'))
cyl_bot = next(i for i, (pt, n) in enumerate(cyl_faces) if n.z < -0.9)
fit_to_cyl = {'id': 'f_cyl', 'type': 'fit', 'body': 'b_rect',
              'target_body': 'b_cyl', 'axis': 2, 'face': cyl_bot, 'fit_mode': 0}
t62_session.sync(t62_ops + [fit_to_cyl])
check('T62 rectangular board ties to circular board planar face',
      t62_session.status()[-1]['status'] == 'ok'
      and abs(t62_session.model.body('b_rect').Shape.Volume - 40 * 40 * 120) < 0.01)
t62_session.sync(t62_ops + [fit_to_cyl, {'id': 'mv_cyl', 'type': 'move', 'targets': ['b_cyl'], 'vector': [0, 0, 30]}])
check('T62 moving circular target updates tied rectangular board live',
      abs(t62_session.model.body('b_rect').Shape.Volume - 40 * 40 * 150) < 0.01)

# 2. Tie rectangular board to cut board's top face (z=30 -> 130 after moving cut board), then move cut board.
cut_faces = plane_fit.planar_faces(t62_session.model.body('b_cut'))
cut_top = next(i for i, (pt, n) in enumerate(cut_faces) if n.z > 0.9 and abs(pt.z - 30) < 0.01)
fit_to_cut = {'id': 'f_cut', 'type': 'fit', 'body': 'b_rect',
              'target_body': 'b_cut', 'axis': 2, 'face': cut_top, 'fit_mode': 0}
mv_cut_up = {'id': 'mv_cut0', 'type': 'move', 'targets': ['b_cut'], 'vector': [0, 0, 80]}
t62_session.sync(t62_ops + [mv_cut_up, fit_to_cut])
check('T62 rectangular board ties to cut board planar face',
      t62_session.status()[-1]['status'] == 'ok'
      and abs(t62_session.model.body('b_rect').Shape.Volume - 40 * 40 * 110) < 0.01)
t62_session.sync(t62_ops + [mv_cut_up, fit_to_cut, {'id': 'mv_cut1', 'type': 'move', 'targets': ['b_cut'], 'vector': [0, 0, 25]}])
check('T62 moving cut target updates tied rectangular board live',
      abs(t62_session.model.body('b_rect').Shape.Volume - 40 * 40 * 135) < 0.01)

# 3. Circular board as source tied to b_top (z=220), moves live, and detaches cleanly on push.
fit_cyl_src = {'id': 'f_csrc', 'type': 'fit', 'body': 'b_cyl',
               'target_body': 'b_top', 'axis': 2, 'face': 4, 'fit_mode': 0}
t62_session.sync(t62_ops + [fit_cyl_src])
import math
cyl_area = math.pi * 30 * 30
check('T62 circular board ties its extrusion end to target face',
      t62_session.status()[-1]['status'] == 'ok'
      and abs(t62_session.model.body('b_cyl').Shape.Volume - cyl_area * 100) < 1.0)
t62_session.sync(t62_ops + [fit_cyl_src, {'id': 'mv_top', 'type': 'move', 'targets': ['b_top'], 'vector': [0, 0, 40]}])
check('T62 moving target updates circular board extrusion length live',
      abs(t62_session.model.body('b_cyl').Shape.Volume - cyl_area * 140) < 1.0)
push_cyl_end = {'id': 'p_cend', 'type': 'push_pull',
                'target': {'face': {'body': 'b_cyl', 'normal': [0, 0, 1], 'point': [20, 20, 220]}},
                'distance': 15}
t62_session.sync(t62_ops + [fit_cyl_src, push_cyl_end])
check('T62 pushing tied circular end detaches cleanly and resizes',
      t62_session.status()[-1]['status'] == 'ok'
      and t62_session.model.body('b_cyl').Tip.TypeId == 'Part::Extrusion'
      and abs(t62_session.model.body('b_cyl').Shape.Volume - cyl_area * 115) < 1.0)

# 4. Cut board as source tied along its extrusion axis to b_top (z=220), moves live.
fit_cut_src = {'id': 'f_cutsrc', 'type': 'fit', 'body': 'b_cut',
               'target_body': 'b_top', 'axis': 2, 'face': 4, 'fit_mode': 0}
t62_session.sync(t62_ops + [fit_cut_src])
check('T62 cut board ties its extrusion end to target face while keeping its pocket',
      t62_session.status()[-1]['status'] == 'ok'
      and abs(t62_session.model.body('b_cut').Shape.Volume - (80 * 60 * 220 - 20 * 20 * 10)) < 1.0)
t62_session.sync(t62_ops + [fit_cut_src, {'id': 'mv_top2', 'type': 'move', 'targets': ['b_top'], 'vector': [0, 0, 30]}])
check('T62 moving target updates cut board extrusion length live',
      abs(t62_session.model.body('b_cut').Shape.Volume - (80 * 60 * 250 - 20 * 20 * 10)) < 1.0)
App.closeDocument(t62_session.doc.Name)

# T162: property_edit refuses plane_fit/replace_fit; opening pre-protocol-17 files upgrades fits in journal,
# dropped entries, and Meta ShopSketchOps, and first save writes the upgraded ops.
import json, shutil, zipfile
from session import generation, sha256

upg_dir = os.path.join(folder, 't162_upgrade')
shutil.rmtree(upg_dir, ignore_errors=True)
os.makedirs(upg_dir)
upg_path = os.path.join(upg_dir, 'model.FCStd')
upg_s = Session(upg_path, fresh=True)
upg_base = [
    {'id': 'ur1', 'type': 'rect', 'plane': {'normal': [0, 0, 1], 'origin': [0, 0, 0]}, 'size': [100, 100]},
    {'id': 'upp1', 'type': 'push_pull', 'target': {'rect': 'ur1'}, 'distance': 20, 'body': 'b1'},
    {'id': 'ur2', 'type': 'rect', 'plane': {'normal': [0, 0, 1], 'origin': [0, 0, 100]}, 'size': [100, 100]},
    {'id': 'upp2', 'type': 'push_pull', 'target': {'rect': 'ur2'}, 'distance': 20, 'body': 'b2'},
]
upg_fit = {'id': 'ufit1', 'type': 'fit', 'body': 'b1', 'target_body': 'b2', 'axis': 2, 'face': 4, 'fit_mode': 0}
upg_s.sync(upg_base + [{'id': 'bad_pf', 'type': 'property_edit', 'mode': 'plane_fit', 'body': 'b1',
                        'target_body': 'b2', 'axis': 2, 'face': 4, 'fit_mode': 0}])
check('T162 property_edit refuses mode=plane_fit',
      upg_s.status()[-1]['status'] == 'failed' and 'unknown property_edit mode' in upg_s.status()[-1]['message'])
upg_s.sync(upg_base + [{'id': 'bad_rf', 'type': 'property_edit', 'mode': 'replace_fit', 'body': 'b1',
                        'axis': 2, 'value': '50 mm'}])
check('T162 property_edit refuses mode=replace_fit',
      upg_s.status()[-1]['status'] == 'failed' and 'unknown property_edit mode' in upg_s.status()[-1]['message'])
upg_s.sync(upg_base + [upg_fit])
fitted_vol = upg_s.model.world_shape(upg_s.model.body('b1')).Volume
upg_s.save()
upg_s.close()

# Rewrite journal + Meta ShopSketchOps to pre-17 format (with a dropped legacy fit too).
g_upg = generation(upg_path)
legacy_fit = {'id': 'ufit1', 'type': 'property_edit', 'mode': 'plane_fit', 'body': 'b1',
              'target_body': 'b2', 'axis': 2, 'face': 4, 'fit_mode': 0}
legacy_dropped = {'op': {'id': 'ufit_drop', 'type': 'property_edit', 'mode': 'replace_fit',
                         'body': 'b1', 'axis': 2, 'value': '40 mm'},
                  'after_rev': 1, 'at': '2026-11-27T00:00:00'}
with open(g_upg['journal']) as f:
    j_old = json.load(f)
j_old['ops'] = upg_base + [legacy_fit]
j_old['dropped'] = [legacy_dropped]
# Also patch Document.xml Meta ShopSketchOps to legacy format and update file_sha256.
tmp_zip = upg_path + '.legacy.tmp'
with zipfile.ZipFile(upg_path, 'r') as zin, zipfile.ZipFile(tmp_zip, 'w') as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == 'Document.xml':
            xml_str = data.decode('utf-8')
            old_meta_ops = json.dumps(upg_base + [upg_fit], separators=(',', ':'))
            new_meta_ops = json.dumps(upg_base + [legacy_fit], separators=(',', ':'))
            xml_str = xml_str.replace(old_meta_ops, new_meta_ops)
            data = xml_str.encode('utf-8')
        zout.writestr(item, data)
os.replace(tmp_zip, upg_path)
j_old['file_sha256'] = sha256(upg_path)
with open(g_upg['journal'], 'w') as f:
    json.dump(j_old, f)

# Reopen old file: ops and dropped are upgraded, sync matches without rebuild, undo/redo works, save persists.
reopened = Session(upg_path)
check('T162 reopen upgrades journal ops and dropped entries without changing IDs',
      reopened.applied[-1]['op'] == upg_fit and 'mode' not in reopened.applied[-1]['op']
      and reopened.dropped[0]['op'] == {'id': 'ufit_drop', 'type': 'unfit', 'body': 'b1', 'axis': 2, 'value': '40 mm'}
      and abs(reopened.model.world_shape(reopened.model.body('b1')).Volume - fitted_vol) < 0.01)
how_same, _ = reopened.sync([e['op'] for e in reopened.applied])
check('T162 sync with upgraded ops after open does nothing (no undo or rebuild)',
      how_same == 'nothing')
# Check _file_ops upgrades Meta ShopSketchOps directly.
meta_ops = reopened._file_ops(upg_path, reopened.rev)
check('T162 _file_ops upgrades Meta ShopSketchOps',
      meta_ops[-1]['op'] == upg_fit)
# Undo across the fit and redo.
reopened.sync(upg_base)
check('T162 undo across upgraded fit restores plain stock',
      abs(reopened.model.world_shape(reopened.model.body('b1')).Volume - 100 * 100 * 20) < 0.01)
reopened.sync(upg_base + [upg_fit])
check('T162 redo upgraded fit restores fitted board',
      abs(reopened.model.world_shape(reopened.model.body('b1')).Volume - fitted_vol) < 0.01)
reopened.save()
reopened.close()

with open(g_upg['journal']) as f:
    saved_j = json.load(f)
with zipfile.ZipFile(upg_path, 'r') as z:
    saved_xml = z.read('Document.xml').decode('utf-8')
check('T162 first save after open writes upgraded ops to journal and Meta ShopSketchOps',
      saved_j['ops'][-1] == upg_fit and saved_j['dropped'][0]['op']['type'] == 'unfit'
      and 'plane_fit' not in saved_xml and 'replace_fit' not in saved_xml)

print('PROPERTY TESTS: %d passed, 0 failed' % passed)
