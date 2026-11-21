"""Hole arrays and hole moves (Move on a cut-out). Run: freecadcmd worker/test_arrays.py"""
import os, json, time
src=open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'replay.py')).read().replace("\nmain()\n","\n")
exec(compile(src,'replay.py','exec'))
ok=[0,0]
def check(n,c,d=""):
    ok[0 if c else 1]+=1; print(("PASS " if c else "FAIL ")+n+("" if c else f"  {d}"), flush=True)
base=[{"id":"r1","type":"rect","plane":{"normal":[0,0,1],"origin":[0,0,0]},"size":[600,300]},
      {"id":"pp1","type":"push_pull","target":{"rect":"r1"},"distance":18,"body":"b1"},
      {"id":"r2","type":"rect","plane":{"on":{"body":"b1","normal":[0,0,1],"point":[30,30,18]}},"size":[20,20]},
      {"id":"pp2","type":"push_pull","target":{"rect":"r2"},"distance":-18}]
V0=600*300*18; H=20*20*18
arr={"id":"mv1","type":"move","targets":[],"cut":{"body":"b1","op":"pp2"},"vector":[60,0,0],"copy":True,"count":5,"divide":False}
os.makedirs(os.environ.get("TESTDIR", "/tmp/arrt") + "",exist_ok=True)
s=Session(os.environ.get("TESTDIR", "/tmp/arrt") + "/model.FCStd",fresh=True); s.sync(base+[arr])
st=s.status(); check("array op ok", st[-1]["status"]=="ok", st[-1])
vol=s.model.world_shape(s.model.body("b1")).Volume
check("6 holes cut (original + 5 copies)", abs(vol-(V0-6*H))<1e-3, vol)
s.export(os.environ.get("TESTDIR", "/tmp/arrt") + ""); cuts=json.load(open(os.environ.get("TESTDIR", "/tmp/arrt") + "/bodies.json"))[0]["cuts"]
check("bodies.json lists 6 cut-outs, all from pp2", len(cuts)==6 and {c["op"] for c in cuts}=={"pp2"}, cuts[:2])
check("FreeCAD tree has a Draft array", any(getattr(getattr(o,"Proxy",None),"__class__",type(None)).__name__=="Array" for o in s.doc.Objects))
# amend: 5x -> divide /4 across 240
s.sync(base+[dict(arr, count=4, divide=True, vector=[240,0,0])])
check("retyped as /4 over 240 mm: 5 holes", abs(s.model.world_shape(s.model.body("b1")).Volume-(V0-5*H))<1e-3)
# undo the array
how,_=s.sync(base); check("undo the array uses FreeCAD undo", how.startswith("undid 1"), how)
check("back to one hole", abs(s.model.world_shape(s.model.body("b1")).Volume-(V0-H))<1e-3)
# move the single hole
mv={"id":"mv2","type":"move","targets":[],"cut":{"body":"b1","op":"pp2"},"vector":[100,50,0],"copy":False}
s.sync(base+[mv]); s.export(os.environ.get("TESTDIR", "/tmp/arrt") + ""); c1=json.load(open(os.environ.get("TESTDIR", "/tmp/arrt") + "/bodies.json"))[0]["cuts"]
check("moved hole now at x 130..150, y 80..100", s.status()[-1]["status"]=="ok" and [round(v) for v in c1[0]["lo"][:2]]==[130,80], c1)
off={"id":"mv3","type":"move","targets":[],"cut":{"body":"b1","op":"pp2"},"vector":[5000,0,0],"copy":False}
s.sync(base+[mv,off]); check("moving a hole off the board is rejected", s.status()[-1]["status"]=="failed", s.status()[-1])
# array + save + FreeCAD edit of the count
s.sync(base+[arr]); s.save(os.environ.get("TESTDIR", "/tmp/arrt") + ""); s.close()
d=App.openDocument(os.environ.get("TESTDIR", "/tmp/arrt") + "/model.FCStd"); a=[o for o in d.Objects if o.Label.startswith("mv1 array")][0]; a.NumberX=9; d.recompute(); d.save(); App.closeDocument(d.Name)
s=Session(os.environ.get("TESTDIR", "/tmp/arrt") + "/model.FCStd")
check("count changed in FreeCAD (9) shows on reopen", abs(s.model.world_shape(s.model.body("b1")).Volume-(V0-9*H))<1e-3)
s.close()
print(f"ARRAY TESTS: {ok[0]} passed, {ok[1]} failed")
