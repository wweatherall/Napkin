# runner: python3 (it starts freecadcmd itself)
"""Real worker socket: length replies are isolated from model sync."""
import json, os, socket, subprocess, tempfile, time
from pathlib import Path
with tempfile.TemporaryDirectory(dir=os.environ.get('TESTDIR') if os.path.isdir(os.environ.get('TESTDIR', '')) else None) as tmp:
    with open(Path(tmp)/'worker.log','w') as log:
        proc=subprocess.Popen(['/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd',str(Path(__file__).resolve().with_name('replay.py'))],env=dict(os.environ,SERVE_PORT='0',SERVE_PORT_FILE=str(Path(tmp)/'worker.port')),stdout=log,stderr=log)
        try:
            for _ in range(600):
                if (Path(tmp)/'worker.port').exists(): break
                time.sleep(.05)
            port=int((Path(tmp)/'worker.port').read_text())
            for _ in range(100):
                try: conn=socket.create_connection(('127.0.0.1',port),timeout=2); break
                except OSError: time.sleep(.1)
            else: raise AssertionError('worker did not start')
            conn.settimeout(10); stream=conn.makefile('r')
            for ident, texts, expected in [(1,['1in + 5mm','3/4"'],[30.4,19.05]),(2,['1-1/2"'],[12.7]),(3,['19'],[19])]:
                conn.sendall((json.dumps(dict(cmd='length',id=ident,texts=texts))+'\n').encode())
                reply=json.loads(stream.readline())
                assert reply['cmd']=='length' and reply['id']==ident,reply
                assert reply['ok']==(expected is not None),reply
                if expected:
                    assert all(abs(a-b)<1e-8 for a,b in zip(reply['values'],expected)),reply
            conn.close()
            print('LENGTH PROTOCOL TESTS: 3 passed, 0 failed')
        finally:
            proc.terminate(); proc.wait(timeout=10)
