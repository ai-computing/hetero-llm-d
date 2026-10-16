"""Real terminal navigation and option selection only; never submit or apply."""
import os,pty,fcntl,termios,struct,subprocess,time,select,json
from pathlib import Path
out=Path(__file__).resolve().parents[1]/'docs/presentations/ETRI_NPU_Editable_v14/assets'
out.mkdir(parents=True,exist_ok=True)
cols,rows=176,44
master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',rows,cols,0,0))
env={**os.environ,'TERM':'xterm-256color','COLORTERM':'truecolor','LMD_THEME':'soft'};env.pop('NO_COLOR',None)
p=subprocess.Popen(['lmd-top/target/release/lmd-top','--mode','admin'],stdin=slave,stdout=slave,stderr=slave,env=env,start_new_session=True)
os.close(slave);start=time.monotonic();events=[];sent=set()
schedule=[(4,b'4'),(5,b'j'),(6,b'j'),(7,b'j'),(8,b'j'),(9,b']'),(10,b'jj'),(11,b'jj'),(12,b'jj'),(13,b'jj'),(14,b'jj'),(15,b'['),(16,b'k'),(17,b'k'),(18,b'k'),(19,b'c'),(20,b'l'),(21,b'j'),(22,b'h'),(23,b'j'),(24,b'l'),(25,b'j'),(26,b'l'),(27,b'j'),(28,b'l'),(29,b'\x1b'),(30,b'd'),(31,b'l'),(32,b'j'),(33,b'l'),(34,b'j'),(35,b'l'),(36,b'j'),(37,b'l'),(39,b'\x1b')]
try:
    while time.monotonic()-start<40:
        elapsed=time.monotonic()-start
        for i,(t,keys) in enumerate(schedule):
            if elapsed>=t and i not in sent:os.write(master,keys);sent.add(i)
        if select.select([master],[],[],.08)[0]:
            try:data=os.read(master,262144)
            except OSError:break
            events.append([round(elapsed,3),'o',data.decode('utf-8','replace')])
finally:
    os.write(master,b'q')
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.terminate();p.wait()
    os.close(master)
with (out/'dynamic.cast').open('w') as f:
    f.write(json.dumps({'version':2,'width':cols,'height':rows,'timestamp':int(time.time())})+'\n')
    for e in events:f.write(json.dumps(e)+'\n')
print(out/'dynamic.cast')
