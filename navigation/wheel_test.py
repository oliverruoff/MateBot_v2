"""Explicit, offline commissioning test: ONE raised wheel, at most one second.

Run on the Pi after stopping the navigation container. Normal driving remains
uncalibrated. Every pulse train expires after 80 ms even if this process dies.
"""
import argparse
import math
from pathlib import Path
import signal
import subprocess
import time

from core import finite_wave


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel',choices=['FL','FR','BL','BR'],required=True)
    parser.add_argument('--raised',action='store_true',help='Operator confirms all wheels are clear of the floor')
    args=parser.parse_args()
    if not args.raised:
        parser.error('All wheels must be securely raised before this test')
    import fcntl
    import pigpio
    import yaml
    cfg=yaml.safe_load((Path(__file__).parent/'config/robot.yaml').read_text())
    status=subprocess.run(['sudo','-n','docker','inspect','-f','{{.State.Running}}',
                           'matebot-navigation'],capture_output=True,text=True,check=True)
    if status.stdout.strip()!='false':
        raise RuntimeError('Stop the navigation container before commissioning')
    lease=open('/tmp/matebot-wheel-test.lock','w')
    fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    index=['FL','FR','BL','BR'].index(args.wheel)
    def interrupted(*_):
        raise KeyboardInterrupt('Wheel test interrupted')
    signal.signal(signal.SIGTERM,interrupted)
    pi=pigpio.pi('127.0.0.1')
    if not pi.connected:
        raise RuntimeError('pigpiod unavailable')
    wave=-1
    completed=0
    try:
        pi.wave_tx_stop()
        for pin in cfg['step_pins']:
            pi.set_mode(pin,pigpio.OUTPUT)
            pi.set_PWM_dutycycle(pin,0)
            pi.write(pin,0)
        pi.set_mode(cfg['enable_pin'],pigpio.OUTPUT)
        pi.write(cfg['enable_pin'],int(cfg['enable_active_low']))
        pin=cfg['direction_pins'][index]
        pi.set_mode(pin,pigpio.OUTPUT)
        pi.write(pin,int(cfg['direction_signs'][index]>0))
        frequencies=[0.,0.,0.,0.]
        frequencies[index]=1200.
        pi.wave_add_generic([pigpio.pulse(*p) for p in finite_wave(frequencies,cfg['step_pins'])])
        wave=pi.wave_create()
        if wave<0:
            raise RuntimeError('Could not allocate finite test wave')
        time.sleep(.01)
        pi.write(cfg['enable_pin'],int(not cfg['enable_active_low']))
        deadline=time.monotonic()+1.2
        for _ in range(10):
            if time.monotonic()+.085>deadline:
                break
            pi.wave_send_once(wave)
            while pi.wave_tx_busy() and time.monotonic()<deadline:
                time.sleep(.005)
            if pi.wave_tx_busy():
                raise RuntimeError('Test deadline exceeded')
            completed+=1
        print({'wheel':args.wheel,'completed_trains':completed,
               'commanded_pulses':completed*96,'step_frequency_hz':1200,
               'normal_motion_verified':cfg['motion_verified']},flush=True)
    finally:
        pi.wave_tx_stop()
        for pin in cfg['step_pins']:
            pi.write(pin,0)
        pi.write(cfg['enable_pin'],int(cfg['enable_active_low']))
        if wave>=0:
            pi.wave_delete(wave)
        pi.stop()
        lease.close()


if __name__=='__main__':
    main()
