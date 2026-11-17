"""Continuous pigpio PWM, owned by a daemon-side command/watchdog script."""
import bisect
import json
import math
from pathlib import Path
import secrets
import time

from core import twist


def output_rates(hz,cfg,available,limits):
    """Nearest PWM bins; fall back downwards if body speed limits are exceeded."""
    if len(hz)!=4 or not all(math.isfinite(h) for h in hz):
        raise ValueError('Ungültige PWM-Geschwindigkeit')
    steps_m=cfg['steps_per_revolution']*cfg['microsteps']/(math.pi*cfg['wheel_diameter'])
    requested=list(hz)
    for attempt in range(24):
        freq=[]
        for h in requested:
            index=bisect.bisect_right(available,abs(h)+1e-8)-1
            if index<0:freq.append(0);continue
            if not attempt and index+1<len(available) and available[index+1]-abs(h)<abs(h)-available[index]:index+=1
            freq.append(available[index])
        actual=twist([math.copysign(f,h)/steps_m if f else 0. for f,h in zip(freq,hz)],cfg['wheelbase'],cfg['track_width'])
        ratio=max(math.hypot(*actual[:2])/limits[0],abs(actual[2])/limits[1])
        if ratio<=1.000001:return freq,actual
        requested=[h*min(.99,.99/ratio) for h in requested]
    return [0]*4,(0.,0.,0.)


def pwm_script(cfg):
    """p0: even committed generation; p1..4: Hz; p5..8: DIR; p9: ack.

    An odd generation marks an incomplete transaction. Only complete frames
    refresh the watchdog. Repeated frames do not restart existing PWM outputs.
    """
    step, direction = cfg['step_pins'], cfg['direction_pins']
    off = int(cfg['enable_active_low']); on = 1-off
    lines = ['ld v0 -1', 'ld v1 0', 'ld v40 0']
    lines += [f'ld v{i} -1' for i in range(20,28)]
    lines += ['tag 0', 'mils 10', 'inr v1', 'lda v1', 'cmp 30', 'jp 99',
              'lda p0', 'and 1', 'jnz 0', 'lda p0', 'cmp v0', 'jz 0',
              'ld v10 p0']
    lines += [f'ld v{i+11} p{i+1}' for i in range(8)]
    lines += ['lda p0', 'cmp v10', 'jnz 0', 'ld v0 v10', 'ld v1 0',
              'lda v11', 'add v12', 'add v13', 'add v14', 'jz 80',
              'lda v40', 'cmp 0', 'jnz 20', f'w {cfg["enable_pin"]} {on}',
              'mils 10', 'ld v40 1', 'tag 20']
    for i, (s,d) in enumerate(zip(step,direction)):
        tag = 30+i*5
        f, dc, fc, desired_dir = 11+i, 24+i, 20+i, 15+i
        lines += [f'lda v{desired_dir}', f'cmp v{dc}', f'jz {tag}',
                  f'p {s} 0', f'w {d} v{desired_dir}', f'ld v{dc} v{desired_dir}',
                  f'ld v{fc} 0', 'mics 10', f'tag {tag}',
                  f'lda v{f}', f'cmp v{fc}', f'jz {tag+3}', f'lda v{f}',
                  'cmp 0', f'jz {tag+2}', f'pfs {s} v{f}', f'lda v{fc}',
                  'cmp 0', f'jnz {tag+1}',
                  f'p {s} 128', f'tag {tag+1}', f'ld v{fc} v{f}',
                  f'jmp {tag+3}', f'tag {tag+2}', f'p {s} 0',
                  f'ld v{fc} 0', f'tag {tag+3}']
    lines += ['ld p9 v10', 'jmp 0', 'tag 80']
    lines += [f'p {s} 0' for s in step]
    lines += [f'w {cfg["enable_pin"]} {off}', 'ld v40 0']
    lines += [f'ld v{i} 0' for i in range(20,24)]
    lines += ['ld p9 v10', 'jmp 0', 'tag 99']
    lines += [f'p {s} 0' for s in step]
    lines += [f'w {cfg["enable_pin"]} {off}', 'halt']
    return '\n'.join(lines)


class PwmDriver:
    max_frequency = 8000

    def __init__(self, pi, cfg, checkpoint=None):
        limit=cfg.get('motor_max_frequency',8000)
        if isinstance(limit,bool) or not isinstance(limit,(int,float)) or not math.isfinite(limit) or not 10<=limit<=8000:
            raise ValueError('Ungültige maximale Motorfrequenz')
        self.max_frequency=limit
        self.pi=pi; self.cfg=cfg; self.path=Path(checkpoint) if checkpoint else None
        self.starts=0; self.underruns=0; self.active=False; self.closed=False
        self.started_at=None; self.startup_signs=None
        self.motion=[0.,0.,0.]; self.velocity=[0.,0.,0.]; self.integrated_at=None
        self.last_publish=0.; self.frames={}; self.sequence=0
        self.base=(secrets.randbelow((1<<18)-1)+1)<<12
        if self.path and self.path.exists():
            old=json.loads(self.path.read_text())
            try:
                _, params=pi.script_status(old['id'])
                if params[0]>>12==old['base']>>12:
                    self._halt(old['id']); pi.delete_script(old['id'])
            except Exception:
                pass  # Daemon restart can remove the previous script.
        for pin in cfg['step_pins']:
            pi.set_PWM_dutycycle(pin,0); pi.set_PWM_range(pin,255)
        # Discover actual available bins with PWM off.
        requests=[10,20,40,50,80,100,160,200,250,320,400,500,800,1000,1600,2000,4000,8000]
        self.frequencies=sorted({pi.set_PWM_frequency(cfg['step_pins'][0],f) for f in requests})
        self.frequencies=[f for f in self.frequencies if 0<f<=self.max_frequency]
        self.sid=pi.store_script(pwm_script(cfg))
        if self.sid<0:raise RuntimeError('PWM-Watchdog konnte nicht geladen werden')
        deadline=time.monotonic()+1
        while pi.script_status(self.sid)[0]==0:
            if time.monotonic()>deadline:raise RuntimeError('PWM-Watchdog startet nicht')
            time.sleep(.005)
        pi.update_script(self.sid,[self.base,0,0,0,0,0,0,0,0,0])
        if self.path:
            temporary=self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(dict(id=self.sid,base=self.base)))
            temporary.replace(self.path)
        self._force_off()

    @property
    def records(self):
        return [True] if self.active else []

    def _force_off(self):
        errors=[]
        actions=[*[lambda pin=pin:self.pi.set_PWM_dutycycle(pin,0) for pin in self.cfg['step_pins']],
                 *[lambda pin=pin:self.pi.write(pin,0) for pin in self.cfg['step_pins']],
                 lambda:self.pi.write(self.cfg['enable_pin'],int(self.cfg['enable_active_low']))]
        for action in actions:
            try:action()
            except Exception as error:errors.append(error)
        if errors:raise errors[0]

    def _halt(self,sid):
        self.pi.stop_script(sid)
        deadline=time.monotonic()+.1
        while self.pi.script_status(sid)[0] in (2,3):
            if time.monotonic()>deadline:raise RuntimeError('PWM-Watchdog konnte nicht angehalten werden')
            time.sleep(.001)

    def account(self,now):
        if self.integrated_at is not None:
            end=min(now,self.last_publish+.31)
            dt=max(0.,end-self.integrated_at)
            self.motion=[a+b*dt for a,b in zip(self.motion,self.velocity)]
        self.integrated_at=now

    def take_motion(self,now):
        self.account(now); result=self.motion; self.motion=[0.,0.,0.]; return result

    def _publish(self,freq,dirs,velocity,now):
        self.sequence=(self.sequence+2)&4094
        seq=self.base+self.sequence
        self.pi.update_script(self.sid,[seq|1])
        self.pi.update_script(self.sid,[seq|1,*freq,*dirs])
        self.pi.update_script(self.sid,[seq])
        self.frames[seq]=list(velocity)
        if len(self.frames)>64:self.frames.pop(next(iter(self.frames)))
        self.last_publish=now
        return seq

    def startup_rates(self,hz,now):
        signs=tuple(1 if h>0 else -1 if h<0 else 0 for h in hz)
        if not any(signs):
            self.started_at=None; self.startup_signs=None
            return hz
        if self.started_at is None or self.startup_signs and any(a*b<0 for a,b in zip(signs,self.startup_signs)):
            self.started_at=now
        self.startup_signs=signs
        if now-self.started_at<self.cfg.get('motor_start_seconds',0.):
            scale=min(1.,self.cfg.get('motor_start_frequency',40)/max(abs(h) for h in hz))
            return [h*scale for h in hz]
        return hz

    def pump(self,hz,velocity,now):
        self.account(now)
        state,params=self.pi.script_status(self.sid)
        if self.active and state not in (2,3):
            self.underruns+=1; self.velocity=[0.,0.,0.]
            raise RuntimeError('PWM-Watchdog hat die Motoren gestoppt')
        if params[9] in self.frames:self.velocity=self.frames[params[9]]
        limits=getattr(self,'limits',(self.cfg['manual_max_linear_speed'],self.cfg['manual_max_angular_speed']))
        freq,actual=output_rates(self.startup_rates(hz,now),self.cfg,self.frequencies,limits)
        dirs=[int(h*s>0) for h,s in zip(hz,self.cfg['direction_signs'])]
        if state not in (2,3):
            self._publish([0]*4,dirs,[0.,0.,0.],now)
            self.pi.run_script(self.sid)
        self._publish(freq,dirs,actual,now)
        if getattr(self,'last_output',None)!=(freq,dirs):
            self.starts+=1; self.last_output=(freq,dirs)
        self.active=any(freq)

    def stop(self,now):
        self.account(now)
        try:
            state,_=self.pi.script_status(self.sid)
            if state in (2,3):
                seq=self._publish([0]*4,[0]*4,[0.,0.,0.],now)
                deadline=time.monotonic()+.35
                while time.monotonic()<deadline:
                    state,params=self.pi.script_status(self.sid)
                    if state not in (2,3) or params[9]==seq:break
                    time.sleep(.002)
                self._halt(self.sid)
        finally:
            self._force_off(); self.active=False; self.velocity=[0.,0.,0.]
            self.last_output=None
            self.started_at=None; self.startup_signs=None

    def close(self):
        if self.closed:return
        self.stop(time.monotonic()); self.pi.delete_script(self.sid); self.closed=True
        if self.path and self.path.exists():
            saved=json.loads(self.path.read_text())
            if saved.get('id')==self.sid and saved.get('base')==self.base:self.path.unlink()
