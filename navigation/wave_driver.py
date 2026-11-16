"""Gapless finite DMA waves: at most one 80 ms successor is queued."""
from core import finite_wave


class WaveDriver:
    duration=.080001  # finite_wave's terminal GPIO-clear pulse is one microsecond.
    def __init__(self,pi,cfg,pulse):
        self.pi=pi;self.cfg=cfg;self.pulse=pulse;self.records=[];self.motion=[0.,0.,0.]
        self.signs=None;self.starts=0;self.underruns=0

    def account(self,now):
        for record in self.records:
            elapsed=max(0.,min(.08,now-record['start']))
            delta=max(0.,elapsed-record['integrated']);record['integrated']=elapsed
            self.motion=[a+v*delta for a,v in zip(self.motion,record['velocity'])]

    def take_motion(self,now):
        self.account(now);result=self.motion;self.motion=[0.,0.,0.];return result

    def stop(self,now):
        self.account(now)
        if self.records:
            self.pi.wave_tx_stop()
            for record in self.records:self.pi.wave_delete(record['id'])
            self.records=[]
        self.signs=None

    def pump(self,hz,velocity,now):
        self.account(now)
        signs=tuple(int(h*sign>0) for h,sign in zip(hz,self.cfg['direction_signs']))
        if self.signs is not None and signs!=self.signs:self.stop(now)
        had_records=bool(self.records)
        active=self.pi.wave_tx_at()
        # Only delete a completed wave after its successor has become active.
        while self.records and self.records[0]['id']!=active:
            if active not in [r['id'] for r in self.records] and self.pi.wave_tx_busy():break
            self.pi.wave_delete(self.records.pop(0)['id'])
        busy=bool(self.pi.wave_tx_busy())
        if len(self.records)>=2:return
        if busy and self.records and now-self.records[0]['start']<.025:return
        if not busy and had_records:self.underruns+=1
        self.signs=signs
        for pin,value in zip(self.cfg['direction_pins'],signs):self.pi.write(pin,value)
        self.pi.wave_add_generic([self.pulse(*p) for p in finite_wave(hz,self.cfg['step_pins'])])
        wave=self.pi.wave_create_and_pad(50)
        if wave<0:raise RuntimeError('pigpio wave_create fehlgeschlagen')
        self.pi.write(self.cfg['enable_pin'],0 if self.cfg['enable_active_low'] else 1)
        start=self.records[0]['start']+self.duration if busy and self.records else now
        self.pi.wave_send_using_mode(wave,2 if busy else 0)
        self.records.append(dict(id=wave,start=start,integrated=0.,velocity=list(velocity)))
        self.starts+=1
