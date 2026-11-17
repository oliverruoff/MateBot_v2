"""Exercise daemon script behavior with a small interpreter, without GPIO."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]))
from pwm_driver import PwmDriver,pwm_script,output_rates
import math
from core import wheels


CFG=dict(step_pins=[9,22,13,5],direction_pins=[11,10,19,6],
         enable_pin=26,enable_active_low=True)


class ScriptMachine:
    def __init__(self):
        self.code=[line.split() for line in pwm_script(CFG).splitlines()]
        self.tags={int(line[1]):i for i,line in enumerate(self.code) if line[0]=='tag'}
        self.p=[0]*10;self.v=[0]*150;self.pc=0;self.a=self.flag=0
        self.ms=0.;self.halted=False;self.pwm={};self.gpio={};self.freq={};self.trace=[]

    def get(self,value):
        if value[0]=='p':return self.p[int(value[1:])]
        if value[0]=='v':return self.v[int(value[1:])]
        return int(value)

    def set(self,register,value):
        (self.p if register[0]=='p' else self.v)[int(register[1:])]=value

    def step(self):
        op,*args=self.code[self.pc];self.pc+=1
        if op=='tag':pass
        elif op=='ld':self.set(args[0],self.get(args[1]))
        elif op=='lda':self.a=self.get(args[0])
        elif op=='cmp':self.flag=self.a-self.get(args[0])
        elif op=='and':self.a&=self.get(args[0]);self.flag=self.a
        elif op=='add':self.a+=self.get(args[0]);self.flag=self.a
        elif op=='inr':
            value=self.get(args[0])+1;self.set(args[0],value);self.flag=value
        elif op in ('jmp','jz','jnz','jp'):
            if op=='jmp' or op=='jz' and self.flag==0 or op=='jnz' and self.flag!=0 or op=='jp' and self.flag>=0:
                self.pc=self.tags[int(args[0])]
        elif op in ('mils','mics'):self.ms+=self.get(args[0])/(1000 if op=='mics' else 1)
        elif op in ('p','w','pfs'):
            pin=int(args[0]);value=self.get(args[1]);self.trace.append((op,pin,value))
            (self.pwm if op=='p' else self.gpio if op=='w' else self.freq)[pin]=value
        elif op=='halt':self.halted=True
        else:raise AssertionError('Unsupported instruction '+op)

    def run(self,milliseconds):
        end=self.ms+milliseconds
        for _ in range(100000):
            if self.halted or self.ms>=end:return
            self.step()
        raise AssertionError('Script failed to yield')

    def frame(self,seq,freq=None,dirs=None):
        self.p[:9]=[seq,*(freq or [1000]*4),*(dirs or [0,1,0,1])]


class PwmScriptTests(unittest.TestCase):
    def test_startup_refreshes_do_not_restart_warmup_and_reversal_does(self):
        driver=PwmDriver.__new__(PwmDriver)
        driver.cfg=dict(motor_start_seconds=1.,motor_start_frequency=40)
        driver.started_at=None;driver.startup_signs=None
        self.assertEqual(driver.startup_rates([100]*4,0.),[40]*4)
        self.assertEqual(driver.startup_rates([100]*4,.9),[40]*4)
        self.assertEqual(driver.startup_rates([100]*4,1.1),[100]*4)
        self.assertEqual(driver.startup_rates([-100]*4,1.2),[-40]*4)
        self.assertEqual(driver.startup_rates([-100]*4,2.3),[-100]*4)
        driver.startup_rates([0]*4,2.4)
        self.assertEqual(driver.startup_rates([-100]*4,2.5),[-40]*4)

    def test_crawling_bins_cannot_jump_into_measured_stall_range(self):
        cfg=dict(steps_per_revolution=200,microsteps=32,wheel_diameter=.079,wheelbase=.31,track_width=.21)
        factor=6400/(math.pi*.079)
        for vx,vy,wz in [(.12,0,0),(-.12,0,0),(0,.12,0),(0,-.12,0),(0,0,.4),(0,0,-.4),(.08,.08,.3)]:
            hz=[v*factor for v in wheels(vx,vy,wz,.31,.21)]
            scale=min(1.,100/max(abs(h) for h in hz))
            freq,actual=output_rates([h*scale for h in hz],cfg,[10,20,40,50,80,100],(.12,.4))
            self.assertLessEqual(max(freq),100)
            self.assertGreater(max(freq),0)
            self.assertGreater(sum(a*b for a,b in zip(actual,[vx,vy,wz])),0)

    def test_invalid_frequency_limit_rejected_before_touching_gpio(self):
        for limit in [0,9,8001,float('nan'),True,'100']:
            with self.assertRaises(ValueError):PwmDriver(None,dict(motor_max_frequency=limit))

    def test_nearest_rates_preserve_six_cm_speed_without_exceeding_limits(self):
        cfg=dict(steps_per_revolution=200,microsteps=32,wheel_diameter=.079,wheelbase=.31,track_width=.21)
        bins=[10,20,40,50,80,100,160,200,250,320,400,500,800,1000,1600,2000,4000,8000]
        factor=6400/(math.pi*.079)
        freq,actual=output_rates([.06*factor]*4,cfg,bins,(.12,.4))
        self.assertEqual(freq,[1600]*4);self.assertAlmostEqual(actual[0],.062,places=3)
        for vx,vy,wz in [(.12,0,0),(.08,.08,.4),(.03,-.09,-.3),(0,0,.18)]:
            limits=(.12,.4) if wz!=.18 else (.08,.18)
            _,actual=output_rates([v*factor for v in wheels(vx,vy,wz,.31,.21)],cfg,bins,limits)
            self.assertLessEqual(math.hypot(*actual[:2]),limits[0]+1e-6)
            self.assertLessEqual(abs(actual[2]),limits[1]+1e-6)

    def test_repeated_identical_commands_keep_continuous_pwm_running(self):
        m=ScriptMachine();m.frame(2);m.run(60)
        self.assertEqual([m.pwm[p] for p in CFG['step_pins']],[128]*4)
        self.assertEqual([m.freq[p] for p in CFG['step_pins']],[1000]*4)
        m.trace.clear()
        for seq in range(4,40,2):m.p[0]=seq;m.run(30)
        self.assertEqual(m.trace,[])
        self.assertFalse(m.halted)

    def test_stale_command_stops_all_pwm_in_daemon_without_python(self):
        m=ScriptMachine();m.frame(2);m.run(60);m.run(320)
        self.assertTrue(m.halted)
        self.assertEqual([m.pwm[p] for p in CFG['step_pins']],[0]*4)
        self.assertEqual(m.gpio[26],1)

    def test_incomplete_frame_never_starts_new_outputs_or_refreshes_watchdog(self):
        m=ScriptMachine();m.frame(2);m.run(60);m.trace.clear()
        m.frame(3,[8000]*4,[1]*4);m.run(100)
        self.assertEqual(m.trace,[]);self.assertEqual(m.p[9],2)
        m.run(250);self.assertTrue(m.halted)
        self.assertEqual([m.pwm[p] for p in CFG['step_pins']],[0]*4)

    def test_zero_command_acknowledges_only_after_all_outputs_stop(self):
        m=ScriptMachine();m.frame(2);m.run(60);m.frame(4,[0]*4)
        for _ in range(1000):
            if m.p[9]==4:break
            m.step()
        self.assertEqual(m.p[9],4)
        self.assertEqual([m.pwm[p] for p in CFG['step_pins']],[0]*4)
        self.assertEqual(m.gpio[26],1)

    def test_direction_change_stops_only_affected_wheel_before_reversing(self):
        m=ScriptMachine();m.frame(2);m.run(60);m.trace.clear()
        m.frame(4,dirs=[1,1,0,1]);m.run(50)
        self.assertEqual(m.trace,[('p',9,0),('w',11,1),('pfs',9,1000),('p',9,128)])


if __name__=='__main__':unittest.main()
