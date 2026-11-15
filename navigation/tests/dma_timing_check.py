"""Stationary DMA timing check. Stop robot service first; enable is forced OFF."""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).parents[1]))
import pigpio
import yaml
from wave_driver import WaveDriver

cfg=yaml.safe_load((Path(__file__).parents[1]/'config/robot.yaml').read_text())
pi=pigpio.pi('127.0.0.1')
assert pi.connected
disabled=1 if cfg['enable_active_low'] else 0
assert pi.read(cfg['enable_pin'])==disabled,'Motor enable must already be OFF'
assert not pi.wave_tx_busy(),'Another controller is active'

class Disabled:
    def __getattr__(self,name):return getattr(pi,name)
    def write(self,pin,value):
        return pi.write(pin,disabled if pin==cfg['enable_pin'] else value)

ticks=[];callback=None;driver=WaveDriver(Disabled(),cfg,pigpio.pulse)
try:
    callback=pi.callback(cfg['step_pins'][0],pigpio.RISING_EDGE,lambda gpio,level,tick:ticks.append(tick))
    started=time.monotonic()
    while time.monotonic()-started<1.5:
        now=time.monotonic();driver.take_motion(now)
        driver.pump([1000]*4,[.1,0,0],now)
        assert pi.read(cfg['enable_pin'])==disabled
        time.sleep(.01)
    driver.stop(time.monotonic());time.sleep(.05)
    gaps=[pigpio.tickDiff(a,b) for a,b in zip(ticks,ticks[1:])]
    result=dict(edges=len(ticks),max_interval_us=max(gaps),min_interval_us=min(gaps),
                underruns=driver.underruns,motors_disabled=pi.read(cfg['enable_pin'])==disabled)
    print(json.dumps(result))
    assert len(ticks)>1200 and max(gaps)<2000 and driver.underruns==0,result
finally:
    driver.stop(time.monotonic());pi.write(cfg['enable_pin'],disabled)
    for pin in cfg['step_pins']:pi.write(pin,0)
    if callback:callback.cancel()
    pi.stop()
