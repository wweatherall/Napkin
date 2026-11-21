"""Native FreeCAD T38 experiment. Run with TESTDIR set to an empty output folder."""
import os, json, time, traceback, statistics
import FreeCAD as App
import Part
from BOPTools import SplitFeatures, SplitAPI
from CompoundTools.CompoundFilter import makeCompoundFilter
V = App.Vector
OUT = os.environ.get('TESTDIR', '/tmp/fretchup-t38-results')
os.makedirs(OUT, exist_ok=True)
results = {'freecad': App.Version(), 'cases': [], 'errors': []}

def metric(obj):
    s = obj.Shape
    return {'valid': s.isValid(), 'solids': len(s.Solids), 'volume': s.Volume,
            'zmin': s.BoundBox.ZMin, 'zmax': s.BoundBox.ZMax}

def run(kind, variant):
    d = App.newDocument('Spike')
    App.setActiveDocument(d.Name)
    profile = d.addObject('Part::Plane', 'Profile')
    profile.Length = 10; profile.Width = 10
    profile.Placement.Base = V(-5, -5, 0)
    p = d.addObject('Part::Extrusion', 'LongP')
    p.Base = profile; p.Dir = V(0,0,1); p.LengthFwd = 100; p.Solid = True
    seed = d.addObject('Part::Box', 'StartStencil')
    seed.Length=10; seed.Width=10; seed.Height=0.1; seed.Placement.Base=V(-5,-5,0)
    if kind in ('flat','angled'):
        raw = d.addObject('Part::Box','TargetBeforeCut')
        raw.Length=80; raw.Width=80; raw.Height=20
        raw.Placement.Base=V(-40,-40,40)
        if kind=='angled':
            rot=App.Rotation(V(0,1,0),30)
            raw.Placement=App.Placement(V(0,0,50)-rot.multVec(V(40,40,10)),rot)
    elif kind=='sphere':
        raw=d.addObject('Part::Sphere','TargetBeforeCut');raw.Radius=20;raw.Placement.Base=V(0,0,50)
    else:
        raw=d.addObject('Part::Cylinder','TargetBeforeCut');raw.Radius=20;raw.Height=80
        raw.Placement=App.Placement(V(0,-40,50),App.Rotation(V(0,0,1),V(0,1,0)))
    target=raw
    if variant=='target_link':
        target=d.addObject('App::Link','TargetLink');target.setLink(raw)
        target.Placement=raw.Placement
        target.Placement.Base += V(1,0,0)
    if variant=='target_mirror':
        target=d.addObject('Part::Mirroring','TargetMirror');target.Source=raw
        target.Base=V(0,0,50);target.Normal=V(0,0,1)
    if variant=='p_link':
        link=d.addObject('App::Link','PLink');link.setLink(p);p=link
    if variant=='p_mirror':
        mirror=d.addObject('Part::Mirroring','PMirror');mirror.Source=p
        mirror.Base=V(0,0,0);mirror.Normal=V(1,0,0);p=mirror
    cut=d.addObject('Part::Cut','AllRemnants');cut.Base=p;cut.Tool=target
    near=makeCompoundFilter('Near');near.Base=cut;near.FilterType='collision-pass';near.Stencil=seed
    common=d.addObject('Part::Common','InsideTarget');common.Base=p;common.Tool=target
    far=d.addObject('Part::MultiFuse','FarEnd');far.Shapes=[near,common];far.Refine=True
    socket=d.addObject('Part::Cut','TargetWithSocket');socket.Base=target;socket.Tool=far
    sliced=SplitFeatures.makeSlice('SliceBySolid');sliced.Base=p;sliced.Tools=[target];sliced.Mode='Split'
    fragments=SplitFeatures.makeBooleanFragments('Fragments');fragments.Objects=[p,target];fragments.Mode='Split'
    d.recompute()
    row={'kind':kind,'variant':variant,'initial':{o.Name:metric(o) for o in (cut,near,common,far,socket,sliced,fragments)}}
    samples=[]
    for n in range(5):
        # Alter original pre-cut source: this is the supported direction of dependency.
        if variant=='target_link': target.Placement.Base += V(0,0,1)
        else: raw.Placement.Base += V(0,0,1)
        if kind in ('flat','angled'): raw.Height = raw.Height.Value + 0.2
        else: raw.Radius = raw.Radius.Value + 0.1
        t=time.perf_counter();d.recompute();samples.append((time.perf_counter()-t)*1000)
    row['modified']={o.Name:metric(o) for o in (near,far,socket)}
    row['all_graph_recompute_ms']=samples
    row['invalid_states']={o.Name:list(o.State) for o in d.Objects if 'Invalid' in o.State}
    row['socket_overlap']=socket.Shape.common(far.Shape).Volume
    # Per-feature forced recomputes (warm document, upstream clean).
    row['feature_ms']={}
    for o in (cut,near,common,far,socket,sliced,fragments):
        times=[]
        for n in range(3):
            o.touch();t=time.perf_counter();d.recompute();times.append((time.perf_counter()-t)*1000)
        row['feature_ms'][o.Name]=times
    # Direct API alternatives: face slicing and half-space. These are geometry
    # probes, not parametric document features; keep that distinction in report.
    row['face_probes']=[]
    for face in target.Shape.Faces:
        probe={'surface':type(face.Surface).__name__}
        try:
            s=SplitAPI.slice(p.Shape,[face],'Split');probe['slice_solids']=len(s.Solids)
        except Exception as e: probe['slice_error']=str(e)
        try:
            half=Part.makeHalfSpace(face,V(0,0,0));clip=p.Shape.common(half)
            probe['halfspace']={'valid':clip.isValid(),'solids':len(clip.Solids),'volume':clip.Volume}
        except Exception as e: probe['halfspace_error']=str(e)
        row['face_probes'].append(probe)
    path=os.path.join(OUT,kind+'_'+variant+'.FCStd');d.recompute();d.saveAs(path)
    before=metric(far);App.closeDocument(d.Name);d=App.openDocument(path)
    d.recompute();row['reopen_equal']=abs(d.getObject('FarEnd').Shape.Volume-before['volume'])<1e-6
    row['checks']={'near_single':row['modified']['Near']['solids']==1,
                   'two_remnants':row['initial']['AllRemnants']['solids']==2,
                   'bounded_end':row['modified']['FarEnd']['zmax']<99,
                   'end_changed':abs(row['modified']['FarEnd']['zmax']-row['initial']['FarEnd']['zmax'])>1,
                   'far_single':row['modified']['FarEnd']['solids']==1,
                   'valid':all(x['valid'] for x in row['modified'].values()),
                   'no_overlap':row['socket_overlap']<1e-6,
                   'no_invalid':not row['invalid_states'],'reopen':row['reopen_equal']}
    App.closeDocument(d.Name)
    return row

try:
    for kind in ('flat','angled','cylinder','sphere'):
        for variant in ('plain','target_link','target_mirror','p_link','p_mirror'):
            try:
                row=run(kind,variant);results['cases'].append(row)
                print('CASE',kind,variant,row['checks'],flush=True)
            except Exception:
                results['errors'].append({'kind':kind,'variant':variant,'error':traceback.format_exc()})
                print(traceback.format_exc(),flush=True)
                for name in list(App.listDocuments()):App.closeDocument(name)
finally:
    with open(os.path.join(OUT,'results.json'),'w') as f:json.dump(results,f,indent=2)
    print('T38 RESULTS',len(results['cases']),'cases',len(results['errors']),'errors',flush=True)
