"""Actual UI demo: forms only. No Enter, apply, write, or execution keys."""
import os,pty,fcntl,termios,struct,subprocess,time,select,json
from pathlib import Path
out=Path(__file__).resolve().parents[1]/'docs/presentations/ETRI_NPU_Editable_v12/assets'
out.mkdir(parents=True,exist_ok=True)
master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',36,132,0,0))
env={**os.environ,'TERM':'xterm-256color','COLORTERM':'truecolor','LMD_THEME':'soft'};env.pop('NO_COLOR',None)
p=subprocess.Popen(['lmd-top/target/release/lmd-top','--mode','admin'],stdin=slave,stdout=slave,stderr=slave,env=env,start_new_session=True)
os.close(slave);start=time.monotonic();events=[];sent=set()
schedule=[(5,b'4'),(9,b']'),(14,b'['),(17,b'c'),(21,b'j'),(23,b'l'),(26,b'\x1b'),(28,b'd'),(32,b'j'),(34,b'l'),(38,b'\x1b')]
try:
    while time.monotonic()-start<40:
        elapsed=time.monotonic()-start
        for i,(t,keys) in enumerate(schedule):
            if elapsed>=t and i not in sent:os.write(master,keys);sent.add(i)
        if select.select([master],[],[],.1)[0]:
            try:data=os.read(master,262144)
            except OSError:break
            events.append([round(elapsed,3),'o',data.decode('utf-8','replace')])
finally:
    os.write(master,b'q')
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.terminate();p.wait()
    os.close(master)
with (out/'options.cast').open('w') as f:
    f.write(json.dumps({'version':2,'width':132,'height':36,'timestamp':int(time.time())})+'\n')
    for e in events:f.write(json.dumps(e)+'\n')
print(out/'options.cast')
