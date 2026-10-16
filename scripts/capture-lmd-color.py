"""Record real observe-mode PTY ANSI output; no synthetic data or actions."""
import os,pty,fcntl,termios,struct,subprocess,time,select,json
from pathlib import Path
out=Path(__file__).resolve().parents[1]/'docs/presentations/kcloud-etri-research-v7/assets'
out.mkdir(parents=True,exist_ok=True)
master,slave=pty.openpty();fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',36,132,0,0))
env={**os.environ,'TERM':'xterm-256color','COLORTERM':'truecolor','LMD_THEME':'soft'}
env.pop('NO_COLOR',None)
p=subprocess.Popen(['lmd-top/target/release/lmd-top','--mode','observe'],stdin=slave,stdout=slave,stderr=slave,env=env,start_new_session=True)
os.close(slave);start=time.monotonic();events=[];sent=False
while time.monotonic()-start<14:
    elapsed=time.monotonic()-start
    if elapsed>7 and not sent:os.write(master,b'4');sent=True
    if select.select([master],[],[],.2)[0]:
        try:data=os.read(master,262144)
        except OSError:break
        events.append([round(elapsed,3),'o',data.decode('utf-8','replace')])
os.write(master,b'q')
try:p.wait(timeout=5)
except subprocess.TimeoutExpired:p.terminate();p.wait()
os.close(master)
# Keep the live terminal's complete ANSI stream, condensed in time for a still.
with (out/'lmd-top-real.cast').open('w') as f:
    f.write(json.dumps({'version':2,'width':132,'height':36,'timestamp':int(time.time()),'env':{'TERM':'xterm-256color'}})+'\n')
    for event in events:
        event[0]=round(event[0]/50,4);f.write(json.dumps(event)+'\n')
print('Recorded',len(events),'live ANSI events')
