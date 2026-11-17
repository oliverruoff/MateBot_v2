"""Run inside ROS image. Fake GPIO only: this test never connects to pigpiod."""
import copy
import math
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import bridge
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid
from session import Session,ControlLease
from motor_tuning import MotorProfiles


class Output:
    def __init__(self):self.messages=[]
    def publish(self,value):self.messages.append(value)
    def sendTransform(self,value):self.messages.append(value)


class FakeGPIO:
    def __init__(self):self.pins={};self.pending=[];self.sent=[]
    def wave_tx_stop(self):pass
    def set_PWM_dutycycle(self,*_):pass
    def write(self,pin,value):self.pins[pin]=value
    def wave_tx_busy(self):return False
    def wave_tx_at(self):return 9999
    def wave_send_using_mode(self,wave,mode):self.wave_send_once(wave)
    def wave_delete(self,*_):pass
    def wave_add_generic(self,pulses):self.pending=pulses
    def wave_create_and_pad(self,percent):return self.wave_create()
    def wave_create(self):return 1
    def wave_send_once(self,_):self.sent.append(self.pending)
    def stop(self):pass


class Harness(bridge.Bridge):
    def __init__(self,directory,now):
        # Deliberately bypass Bridge.__init__: no physical I/O and no subscriptions.
        Node.__init__(self,'matebot_safety_harness')
        self.lock=threading.RLock();self.save_lock=threading.Lock();self.save_event=threading.Event()
        self.session=Session(directory);self.annotations=self.session.get();self.zones=set();self.lease=ControlLease()
        self.localized=True;self.map_transition=False;self.running=True;self.closed=False;self.estop=True
        self.stop_reason='Gestoppt';self.scan_at=self.imu_at=now;self.valid_points=300
        self.command=[0.,0.,0.];self.applied_cmd=[0.,0.,0.];self.base_points=[];self.manual_until=0.
        self.last_manual_sequence=-1;self.burst_pulses=0;self.burst_exhausted=False
        self.pose=dict(x=0.,y=0.,yaw=0.,age=0.);self.goal_handle=None;self.goal_pending=False
        self.goal_generation=0;self.goal_status='Bereit';self.path=[];self.error=''
        self.wave_velocity=[0.,0.,0.];self.wave_started=0.;self.wave_integrated=0.
        self.x=self.y=self.heading=0.;self.last_tick=now-.05;self.cmd_at=now;self.last_wave=-1
        self.pi=FakeGPIO();self.wave_driver=bridge.WaveDriver(self.pi,bridge.CFG,bridge.pigpio.pulse);self.tf=Output();self.odom_pub=Output();self.scan_pub=Output();self.map_pub=Output()
        self.map=None;self.map_version=0;self.scan_count=0
        self.motor_profiles=MotorProfiles(Path(directory)/'motor-profiles.json',bridge.CFG)
        self.motor_test=None;self.manual_warning=''


class FakeTestPWM:
    def __init__(self,pi,cfg,*_):
        self.cfg=cfg;self.max_frequency=cfg['motor_max_frequency'];self.records=[]
        self.starts=0;self.underruns=0;self.last_output=None
    def stop(self,*_):self.records=[];self.last_output=None
    def close(self):self.stop()
    def take_motion(self,*_):return [0.,0.,0.]
    def pump(self,hz,velocity,now):self.records=[True];self.last_output=([abs(v) for v in hz],[])


class ROSMotorInterlockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):rclpy.init()
    @classmethod
    def tearDownClass(cls):rclpy.shutdown()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.now=[time.monotonic()]
        self.robot=Harness(self.temp.name,self.now[0])
        self.clock_patch=patch('bridge.time.monotonic',side_effect=lambda:self.now[0]);self.clock_patch.start()
    def tearDown(self):
        self.clock_patch.stop();self.robot.close();self.robot.destroy_node();self.temp.cleanup()
    def advance(self,seconds=.05):
        self.now[0]+=seconds;self.robot.scan_at=self.robot.imu_at=self.now[0]

    def start_test(self,duration=1,wheel='all',reverse=False):
        r=self.robot;profile=dict(r.motor_profiles.draft,frequency=1000,warmup=0)
        token=r.motor_test_arm()['token']
        return r.motor_test_start(profile,'forward',duration,token,wheel,reverse)

    def test_single_wheel_keeps_other_three_step_outputs_zero(self):
        r=self.robot
        for i,wheel in enumerate(['FL','FR','BL','BR']):
            with patch('bridge.PwmDriver',FakeTestPWM):self.start_test(1,wheel,True)
            self.advance(.05);r.tick()
            expected=[0.]*4;expected[i]=1000.
            self.assertEqual(r.wave_driver.last_output[0],expected)
            self.assertEqual(r.wave_driver.cfg['motor_channel_order'],[3,2,1,0])
            r.stop()

    def test_delayed_start_after_release_cannot_reactivate_motors(self):
        r=self.robot;token=r.motor_test_arm()['token'];r.stop()
        with patch('bridge.PwmDriver',FakeTestPWM):
            with self.assertRaises(ValueError):r.motor_test_start(r.motor_profiles.draft,'forward',1,token)
        self.assertTrue(r.estop);self.assertIsNone(r.motor_test)

    def test_test_deadline_is_not_extended_by_live_refresh_and_restores_normal_driver(self):
        r=self.robot;original=r.wave_driver
        with patch('bridge.PwmDriver',FakeTestPWM):result=self.start_test(.3)
        self.advance(.2);r.motor_test_refresh(result['token']);r.tick()
        self.assertIsNotNone(r.motor_test)
        with self.assertRaises(ValueError):r.manual(result['token'],.01,0,0,1)
        self.advance(.11);r.tick()
        self.assertTrue(r.estop);self.assertIsNone(r.motor_test);self.assertIs(r.wave_driver,original)

    def test_missing_test_refresh_stops_without_waiting_for_long_lease(self):
        r=self.robot
        with patch('bridge.PwmDriver',FakeTestPWM):self.start_test(3)
        self.advance(.51);r.tick()
        self.assertTrue(r.estop);self.assertIsNone(r.motor_test)

    def test_profile_apply_stops_and_persists_without_starting_outputs(self):
        r=self.robot;r.wave_driver=FakeTestPWM(r.pi,dict(bridge.CFG,motor_max_frequency=100))
        profile=dict(r.motor_profiles.draft,frequency=2000)
        with patch('bridge.PwmDriver',FakeTestPWM):r.motor_profile_save(profile,True)
        self.assertTrue(r.estop);self.assertFalse(r.wave_driver.records)
        self.assertEqual(r.motor_profiles.active['frequency'],2000)
    def test_manual_imu_scheduling_delay_does_not_drop_held_command(self):
        r=self.robot;token=r.take_control('mapping')['token']
        r.imu_at=self.now[0]-.47
        r.manual(token,.01,0.,0.,1);r.tick()
        self.assertFalse(r.estop)
        r.imu_at=self.now[0]-.81;r.tick()
        self.assertTrue(r.estop)
        with self.assertRaisesRegex(ValueError,'IMU nicht bereit'):
            r.manual(token,.01,0.,0.,2)
    def test_navigation_retains_tight_imu_timeout(self):
        r=self.robot;r.annotations['calibration']={key:True for key in r.annotations['calibration']}
        r.imu_at=self.now[0]-.47
        self.assertEqual(r.readiness('navigation',include_stop=False),'IMU nicht bereit')
    def test_unverified_floor_command_has_hard_pulse_budget(self):
        self.addCleanup(patch.stopall)
        patch.dict(bridge.CFG,{'floor_test_enabled':True}).start()
        r=self.robot;token=r.arm('mapping',True)['token'];r.manual(token,.03,0.,0.,1)
        for _ in range(40):
            self.advance();r.heartbeat(token);r.cmd_at=self.now[0];r.tick()
        self.assertTrue(r.burst_exhausted)
        for pin in bridge.CFG['step_pins']:
            emitted=sum(bool(p.gpio_on&(1<<pin)) for wave in r.pi.sent for p in wave)
            self.assertLessEqual(emitted,bridge.CFG['floor_test_pulse_limit'])
        with self.assertRaises(ValueError):r.manual(token,.03,0.,0.,2)
        r.manual(token,0.,0.,0.,3)
        r.manual(token,.03,0.,0.,2)  # Late command after release must be ignored.
        self.assertEqual(r.command,[0.,0.,0.])
        self.assertFalse(r.burst_exhausted)
    def test_lost_owner_stops_even_while_other_readers_poll(self):
        r=self.robot;token=r.arm('mapping',True)['token'];r.manual(token,.01,0.,0.,1);r.tick()
        self.advance(2.6);r.tick()
        self.assertTrue(r.estop);self.assertIsNone(r.lease.token)
        self.assertEqual(r.pi.pins[bridge.CFG['enable_pin']],1)
        self.assertTrue(all(r.pi.pins[pin]==0 for pin in bridge.CFG['step_pins']))
    def test_manual_gesture_drives_continuously_without_commissioning_pulse_limit(self):
        r=self.robot;token=r.take_control('mapping')['token']
        for sequence in range(1,61):
            self.advance();r.heartbeat(token);r.manual(token,.03,0.,0.,sequence);r.tick()
        self.assertFalse(r.estop);self.assertFalse(r.burst_exhausted)
        emitted=sum(bool(p.gpio_on&(1<<bridge.CFG['step_pins'][0])) for wave in r.pi.sent for p in wave)
        self.assertGreater(emitted,160)
        r.manual(token,0.,0.,0.,61)
        self.assertEqual(r.command,[0.,0.,0.])
        r.stop();token=r.take_control('mapping')['token']
        r.manual(token,.01,0.,0.,1)
        self.assertEqual(r.command,[.01,0.,0.])
    def test_navigation_is_locked_but_manual_is_available_for_commissioning(self):
        r=self.robot
        with self.assertRaises(ValueError):r.arm('navigation',True)
        self.assertFalse(r.pi.sent)
        r.arm('mapping',True)
        msg=Twist();msg.linear.x=.03;r.velocity(msg)
        self.assertEqual(r.command,[0.,0.,0.])
    def test_obstacle_blocks_only_motion_towards_it_and_keeps_same_owner(self):
        r=self.robot;token=r.take_control('mapping')['token'];r.base_points=[(.26,0.)]
        result=r.manual(token,.03,0.,0.,1)
        self.assertIn('Hindernis',result['blocked'])
        self.assertFalse(r.estop);self.assertEqual(r.lease.token,token)
        self.assertEqual(r.command,[0.,0.,0.]);self.assertFalse(r.pi.sent)
        r.manual(token,-.02,0.,0.,2)
        self.assertEqual(r.command,[-.02,0.,0.])
        r.base_points=[];r.manual(token,.03,0.,0.,3);r.base_points=[(.26,0.)]
        self.advance();r.tick()
        self.assertFalse(r.estop);self.assertEqual(r.command,[0.,0.,0.])
        r.manual(token,-.02,0.,0.,4)
        self.assertEqual(r.command,[-.02,0.,0.])
    def test_accepted_manual_packets_refresh_owner_without_separate_heartbeat(self):
        r=self.robot;token=r.take_control('mapping')['token']
        for sequence in range(1,31):
            self.advance(.1);r.manual(token,.01,0.,0.,sequence);r.tick()
        self.assertFalse(r.estop);self.assertEqual(r.lease.token,token)
        self.advance(2.6);r.tick()
        self.assertTrue(r.estop)
    def test_manual_does_not_depend_on_global_pose_without_keepouts(self):
        r=self.robot;r.localized=False;r.pose=None
        token=r.take_control('mapping')['token'];r.manual(token,.06,0.,0.,1)
        self.assertEqual(r.command,[.06,0.,0.])
        r.stop();r.zones={(20,20)}
        with self.assertRaises(ValueError):r.take_control('mapping')
    def test_command_watchdog_stops_before_lease_expires(self):
        r=self.robot;token=r.take_control('mapping')['token'];r.manual(token,.06,0.,0.,1);r.tick()
        self.advance(.6);r.tick()
        self.assertFalse(r.estop);self.assertEqual(r.applied_cmd,[0.,0.,0.])
        self.assertTrue(all(r.pi.pins[p]==0 for p in bridge.CFG['step_pins']))
    def test_observed_front_chassis_reflex_is_masked_but_real_front_obstacle_remains(self):
        from spatial import self_return,obstacle_risk
        self.assertTrue(self_return(.236,-.012,bridge.CFG))
        self.assertFalse(self_return(.28,0.,bridge.CFG))
        self.assertTrue(obstacle_risk([(.26,0.)],bridge.CFG,[.03,0.,0.]))
    def test_navigation_goal_transmits_selected_orientation(self):
        class ResultFuture:
            def add_done_callback(self,callback):self.callback=callback
        class Handle:
            accepted=True
            def cancel_goal_async(self):pass
            def get_result_async(self):return ResultFuture()
        class GoalFuture:
            def done(self):return True
            def result(self):return Handle()
        class Navigator:
            def server_is_ready(self):return True
            def send_goal_async(self,goal,feedback_callback=None):
                self.goal=goal;self.feedback=feedback_callback;return GoalFuture()
        r=self.robot;r.annotations['mode']='navigation'
        r.annotations['calibration']={k:True for k in r.annotations['calibration']}
        r.navigator=Navigator();r.nav_ready=True
        m=OccupancyGrid();m.info.width=m.info.height=80;m.info.resolution=.05
        m.info.origin.position.x=m.info.origin.position.y=-2.;m.info.origin.orientation.w=1.;m.data=[0]*6400;r.map=m
        token=r.take_control('navigation')['token'];r.goal(.5,.1,token,heading=1.2)
        q=r.navigator.goal.pose.pose.orientation
        self.assertAlmostEqual(q.z,math.sin(.6));self.assertAlmostEqual(q.w,math.cos(.6))
        self.assertEqual(r.goal_target,dict(x=.5,y=.1,yaw=1.2))
    def test_old_map_correction_composes_with_current_odometry(self):
        from geometry_msgs.msg import TransformStamped
        r=self.robot;tf=TransformStamped()
        tf.header.stamp.sec=int(r.get_clock().now().nanoseconds/1e9)-10
        tf.transform.translation.x=1.;tf.transform.translation.y=2.
        tf.transform.rotation.z=math.sin(.2);tf.transform.rotation.w=math.cos(.2)
        class Buffer:
            def lookup_transform(self,parent,child,stamp):
                assert (parent,child)==('map','odom');return tf
        r.buffer=Buffer();r.x=.2;r.y=.1;r.heading=.3;r.last_persist=self.now[0]
        r.update_pose()
        self.assertAlmostEqual(r.pose['x'],1.+.2*math.cos(.4)-.1*math.sin(.4))
        self.assertAlmostEqual(r.pose['y'],2.+.2*math.sin(.4)+.1*math.cos(.4))
        self.assertAlmostEqual(r.pose['yaw'],.7)
        self.assertLess(r.pose['age'],.1);self.assertGreater(r.map_correction_age,9.)
    def test_no_go_edit_cancels_owner_and_overlays_planner_map(self):
        r=self.robot;r.arm('mapping',True)
        m=OccupancyGrid();m.info.width=m.info.height=80;m.info.resolution=.05
        m.info.origin.position.x=m.info.origin.position.y=-2.;m.info.origin.orientation.w=1.;m.data=[0]*6400
        r.map=m;r.edit_zones([[0,0]],[],.25,0)
        self.assertTrue(r.estop);self.assertIsNone(r.lease.token)
        self.assertIn(100,r.map_pub.messages[-1].data)
        self.assertNotIn(100,r.map.data)  # Keepout must not burn into SLAM's raw map.
        with self.assertRaises(ValueError):r.arm('mapping',True)
    def test_chassis_returns_are_nan_not_free_rays(self):
        r=self.robot;ranges=[3.]*360;ranges[180]=.14
        r.publish_scan(ranges,r.get_clock().now())
        self.assertTrue(math.isnan(r.scan_pub.messages[-1].ranges[180]))
        self.assertEqual(r.self_points,1)


if __name__=='__main__':unittest.main(verbosity=2)
