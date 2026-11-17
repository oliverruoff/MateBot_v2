import copy
import math
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]))
from motor_tuning import MotorProfiles,validate_profile,test_command,driver_config

CFG=dict(steps_per_revolution=200,microsteps=32,wheel_diameter=.079,wheelbase=.31,track_width=.21,motor_max_frequency=100)
PROFILE=dict(frequency=1000,acceleration=20000,duty=50,start_frequency=40,warmup=0,enable_delay=100)


class MotorTuningTests(unittest.TestCase):
    def test_rejects_invalid_values_before_gpio_configuration(self):
        for key,value in [('frequency',float('nan')),('frequency',8001),('duty',0),('acceleration',True),('enable_delay',501),('warmup',-1),('start_frequency',2000)]:
            p=dict(PROFILE);p[key]=value
            with self.assertRaises(ValueError):validate_profile(p)
        for duration in [0,3.1,True,float('inf')]:
            with self.assertRaises(ValueError):test_command('forward',PROFILE,CFG,duration)
        with self.assertRaises(ValueError):test_command('unknown',PROFILE,CFG,1)

    def test_six_commands_use_requested_pulse_rate_with_correct_body_axes(self):
        for direction,axis,sign in [('forward',0,1),('backward',0,-1),('left',1,1),('right',1,-1),('turn_left',2,1),('turn_right',2,-1)]:
            cmd=test_command(direction,PROFILE,CFG,1)
            self.assertGreater(cmd[axis]*sign,0)
            self.assertTrue(all(abs(v)<1e-9 for i,v in enumerate(cmd) if i!=axis))
        self.assertAlmostEqual(test_command('forward',PROFILE,CFG,1)[0],1000*math.pi*.079/6400)

    def test_draft_does_not_change_active_profile_and_both_survive_reload(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'motor.json';store=MotorProfiles(path,CFG)
            original=copy.deepcopy(store.default)
            store.save(PROFILE);self.assertIsNone(store.active)
            self.assertEqual(MotorProfiles(path,CFG).draft,PROFILE)
            store.save(PROFILE,True)
            second=dict(PROFILE,frequency=2000)
            store.save(second)
            loaded=MotorProfiles(path,CFG)
            self.assertEqual(loaded.active,PROFILE);self.assertEqual(loaded.draft,second)
            self.assertEqual(loaded.default,original)
            cfg=driver_config(CFG,loaded.active)
            self.assertEqual(cfg['motor_max_frequency'],1000)
            self.assertEqual(cfg['motor_duty_percent'],50)
