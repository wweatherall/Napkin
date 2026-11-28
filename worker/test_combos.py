"""H007 feature combinations; no worker patches. TESTDIR selects disposable outputs.
Run: TESTDIR=/tmp/combo-run freecadcmd worker/test_combos.py
Failures print a replayable op list. Exceptions are caught to prevent freecadcmd's rerun.
"""
import os
import json
import traceback
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_load  # Configure the FreeCAD test runtime before loading worker modules.
import FreeCAD as App
from session import Session
ROOT = Path(os.environ.get('TESTDIR', '/tmp/napkin-combos'))
ROOT.mkdir(parents=True, exist_ok=True)
R = [0, 0]
SERIAL = 0
CURRENT = []
FAILURES = []

def check(name, condition, detail=None):
    R[0 if condition else 1] += 1
    print(('PASS ' if condition else 'FAIL ') + name, flush=True)
    if not condition:
        entry = {'name': name, 'detail': detail, 'ops': CURRENT}
        FAILURES.append(entry)
        print(json.dumps(entry, default=str), flush=True)

def rect(rid='r1', x=0, width=100):
    return {'id':rid,'type':'rect','plane':{'normal':[0,0,1],'origin':[x,0,0]},'size':[width,50]}
def push(pid='p1', rid='r1', bid='b1'):
    return {'id':pid,'type':'new_board','target':{'rect':rid},'distance':18,'body':bid}
def move(oid, target, vector, **kw):
    return dict(id=oid,type='move',targets=[target],vector=vector,**kw)
def mirror(target='b2', group=True):
    op={'id':'mi','type':'mirror','targets':[target], 'plane':{'point':[400,0,0],'normal':[1,0,0]},'new_ids':['b4']}
    if group:op['group']='g1'
    return op
BASE=[rect(),push()]
ARRAY=BASE+[move('array','b1',[150,0,0],copy=True,count=2,new_ids=['b2','b3'])]

def exported(sess):
    global SERIAL
    SERIAL += 1
    out=ROOT/('out'+str(SERIAL));sess.export(str(out))
    return {x['id']:x for x in json.loads((out/'bodies.json').read_text())}

def snapshot(sess):
    entries=exported(sess)
    # Normalize generated definition names to sibling sets, not FreeCAD object names.
    families={k:tuple(sorted(i for i,e in entries.items() if e['family']==v['family'])) if v['family'] else () for k,v in entries.items()}
    boards={}
    for bid,obj in sess.model.bodies().items():
        sh=sess.model.world_shape(obj);bb=sh.BoundBox;e=entries[bid]
        boards[bid]={'volume':round(sh.Volume,4),'bbox':tuple(round(v,4) for v in (bb.XMin,bb.YMin,bb.ZMin,bb.XMax,bb.YMax,bb.ZMax)),
                     'family':families[bid], **{k:e[k] for k in ('material','grain','across','assembly','array','row','mirror_plane')}}
    groups={k:(getattr(g,'SSKind',''),tuple(sorted(getattr(o,'BodyId','') for o in g.Group))) for k,g in sess.model.assemblies().items()}
    return {'boards':boards,'groups':groups}

def fresh(ops):
    s=Session(None)
    try:s.sync(ops);return snapshot(s)
    finally:s.close()

def persisted(name,ops):
    global CURRENT
    CURRENT=ops
    path=ROOT/(name+'.FCStd');s=Session(str(path),fresh=True)
    s.sync(ops)
    check(name+' accepted',all(x['status']=='ok' for x in s.status()),s.status())
    expected=fresh(ops);check(name+' fresh equality',snapshot(s)==expected)
    s.save();s.close();s=Session(str(path))
    check(name+' reopen equals fresh',snapshot(s)==expected,{'actual':snapshot(s),'expected':expected})
    check(name+' no invalid objects',not [o.Name for o in s.doc.Objects if 'Invalid' in o.State])
    return s

def undo_assembly():
    global CURRENT
    ops=ARRAY+[mirror(group=False),{'id':'assembly','type':'make_assembly','targets':['b1','b2','b3','b4'],'new_id':'a1'},move('move_group','a1',[0,0,80])]
    s=Session(None);s.sync(ops)
    try:
        for prefix in (ops[:4],ops[:3],ops[:2],ops):
            CURRENT=prefix;how,_=s.sync(prefix)
            check('live undo/redo assembly equals fresh at '+str(len(prefix)),snapshot(s)==fresh(prefix),how)
    finally:s.close()
    s=persisted('undo_assembly',ops)
    try:
        for prefix in (ops[:4],ops[:3],ops[:2],ops):
            CURRENT=prefix;s.sync(prefix)
            check('undo/redo assembly equals fresh at '+str(len(prefix)),snapshot(s)==fresh(prefix))
    finally:s.close()

def mirrored_array():
    global CURRENT
    ops=ARRAY+[mirror(),move('move_group','g1',[0,0,80]),move('detach_move','b2',[0,20,0],detach=True),{'id':'unique','type':'make_unique','targets':['b3']}]
    s=persisted('mirrored_array',ops)
    try:
        e=exported(s)
        check('detached member retains linked family',not e['b2']['array'] and e['b2']['family']==e['b1']['family']!='',e)
        check('unique member retains array but leaves family',bool(e['b3']['array']) and not e['b3']['family'],e['b3'])
        # Mirror source is b2: its reflected displacement must still agree after detaching.
        a=s.model.world_shape(s.model.body('b2')).BoundBox
        b=s.model.world_shape(s.model.body('b4')).BoundBox
        check('mirror after detach reflects source',abs(a.XMin+b.XMax-800)<1e-6 and abs(a.YMin-b.YMin)<1e-6,(a,b))
    finally:s.close()

def materials():
    global CURRENT
    ops=ARRAY+[mirror(),{'id':'paint','type':'set_material','targets':['b2'],'material':'white-oak'},
               {'id':'unique','type':'make_unique','targets':['b3']},
               {'id':'repaint','type':'set_material','targets':['b3'],'material':'black-walnut'},
               {'id':'grain_instance','type':'turn_grain','targets':['b2']}]
    s=persisted('materials_instance',ops)
    try:
        e=exported(s)
        check('paint unique leaves family oak',all(e[b]['material']=='white-oak' for b in ['b1','b2','b4']) and e['b3']['material']=='black-walnut',e)
        check('instance grain shared, unique independent',e['b1']['grain']==e['b2']['grain']==e['b4']['grain']==[0,1,0] and e['b3']['grain']==[1,0,0],e)
    finally:s.close()
    ops += [{'id':'grain_mirror','type':'turn_grain','targets':['b4']}]
    s=persisted('materials_mirror',ops)
    try:
        e=exported(s)
        check('mirror grain reflected into world frame',e['b1']['grain']==e['b2']['grain']==[1,0,0] and e['b4']['grain']==[-1,0,0],e)
        check('across independent from grain',all(abs(sum(a*b for a,b in zip(x['grain'],x['across'])))<1e-6 for x in e.values()),e)
    finally:s.close()

def interleaved():
    global CURRENT
    # Identical IDs but different dimensions, materials, placements and Draft hole arrays.
    a=ARRAY+[{'id':'hole','type':'rect','plane':{'on':{'body':'b1','normal':[0,0,1],'point':[10,10,18]}},'size':[5,5]},
             {'id':'cut','type':'push_pull','target':{'rect':'hole'},'distance':-18},
             {'id':'hole_array','type':'move','targets':[],'cut':{'body':'b1','op':'cut'},'vector':[15,0,0],'copy':True,'count':2}]
    b=[rect(width=250),push()]+[move('array','b1',[0,100,0],copy=True,count=2,new_ids=['b2','b3']),{'id':'paint','type':'set_material','targets':['b1'],'material':'black-walnut'}]
    sa=Session(str(ROOT/'interleave_a.FCStd'),fresh=True);sb=Session(str(ROOT/'interleave_b.FCStd'),fresh=True)
    try:
        for n in range(1,max(len(a),len(b))+1):
            for sess,ops in ((sa,a),(sb,b)):
                CURRENT=ops[:n];sess.sync(CURRENT)
                check('interleaved '+('A' if sess is sa else 'B')+' prefix '+str(n),snapshot(sess)==fresh(CURRENT))
        for sess,ops in ((sa,a),(sb,b)):
            CURRENT=ops
            check('interleaved ops accepted',all(x['status']=='ok' for x in sess.status()),sess.status())
            expected=fresh(ops);sess.save();path=sess.path;sess.close()
            reopened=Session(path)
            try:check('interleaved reopen',snapshot(reopened)==expected)
            finally:reopened.close()
    finally:
        for sess in (sa,sb):
            if sess.doc and sess.doc.Name in App.listDocuments():sess.close()

def rejection(group_mirror):
    global CURRENT
    base=BASE+[mirror('b1')] if group_mirror else ARRAY+[{'id':'assembly','type':'make_assembly','targets':['b1','b2','b3'],'new_id':'a1'}]
    # Reject an attempt to regroup an already grouped board, then a move dependent on that rejected group.
    bad={'id':'bad_group','type':'make_assembly','targets':['b1'],'new_id':'bad'}
    dependent=move('dependent','bad',[0,0,50]);CURRENT=base+[bad,dependent]
    s=Session(None)
    try:
        s.sync(CURRENT)
        check('rejection statuses '+str(group_mirror),[x['status'] for x in s.status()[-2:]]==['failed','failed'],s.status())
        check('rejected grouping leaves valid group '+str(group_mirror),snapshot(s)==fresh(base),snapshot(s))
        # Dependency pruning belongs to the viewport; worker reports failures. Simulate accepted-prefix resend.
        s.sync(base);check('after rejected ops pruned '+str(group_mirror),snapshot(s)==fresh(base))
    finally:s.close()
    s=persisted('rejection_'+str(group_mirror),base);s.close()

for name,fn in [('undo assembly',undo_assembly),('mirrored array',mirrored_array),('materials',materials),('interleaved',interleaved),('assembly rejection',lambda:rejection(False)),('mirror rejection',lambda:rejection(True))]:
    try:fn()
    except Exception:
        check(name+' unexpected exception',False,traceback.format_exc())
    finally:
        for name in list(App.listDocuments()):App.closeDocument(name)
(ROOT/'failures.json').write_text(json.dumps(FAILURES,indent=2,default=str))
print('COMBO TESTS: %d passed, %d failed'%tuple(R),flush=True)
