"""Properties through the same journal/sync path used by Godot."""
import os, sys, tempfile, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
from test_load import *  # noqa: E402,F403  (the worker's modules, T42)
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
    fit = dict(type='property_edit',id='fit'+str(mode),mode='plane_fit',body='b1',
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
detach = dict(type='property_edit',id='replace',mode='replace_fit',body='b1',axis=2,value='2 cm')
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
print('PROPERTY TESTS: %d passed, 0 failed' % passed)
