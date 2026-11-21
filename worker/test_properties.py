"""Properties through the same journal/sync path used by Godot."""
import os, sys, tempfile, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
def load_worker():
    namespace = {'__file__': str(HERE/'replay.py')}
    source = (HERE/'replay.py').read_text().replace('\nmain()\n', '\n')
    exec(compile(source, str(HERE/'replay.py'), 'exec'), namespace)
    return namespace
W = load_worker()
from object_properties import inspect
App = W['App']
Session = W['Session']
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
print('PROPERTY TESTS: %d passed, 0 failed' % passed)
