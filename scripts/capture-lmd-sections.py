"""Read-only actual PTY capture for presentation screenshots and animation."""
import os,pty,fcntl,termios,struct,subprocess,time,select,json
from pathlib import Path
out=Path(__file__).resolve().parents[1]/'docs/presentations/ETRI_NPU_Editable_v11/assets'
out.mkdir(parents=True,exist_ok=True)
master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',36,132,0,0))
env={**os.environ,'TERM':'xterm-256color','COLORTERM':'truecolor','LMD_THEME':'soft'};env.pop('NO_COLOR',None)
p=subprocess.Popen(['lmd-top/target/release/lmd-top','--mode','observe'],stdin=slave,stdout=slave,stderr=slave,env=env,start_new_session=True)
os.close(slave);start=time.monotonic();events=[];sent=set()
schedule=[(5,b'4','library'),(10,b']','zoo'),(15,b'0','overview'),(23,b'3]','devices')]
def save(name):
    with (out/(name+'.cast')).open('w') as f:
        f.write(json.dumps({'version':2,'width':132,'height':36,'timestamp':int(time.time())})+'\n')
        for t,k,data in events:f.write(json.dumps([round(t/3,3),k,data])+'\n')
try:
    while time.monotonic()-start<30:
        elapsed=time.monotonic()-start
        for i,(t,keys,name) in enumerate(schedule):
            if elapsed>=t and i not in sent:
                if i:save(schedule[i-1][2])
                os.write(master,keys);sent.add(i)
        if select.select([master],[],[],.15)[0]:
            try:data=os.read(master,262144)
            except OSError:break
            events.append([elapsed,'o',data.decode('utf-8','replace')])
    save('devices')
finally:
    os.write(master,b'q')
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.terminate();p.wait()
    os.close(master)
print(out)
