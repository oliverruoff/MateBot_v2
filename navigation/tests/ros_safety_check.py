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
    def wave_delete(self,*_):pass
    def wave_add_generic(self,pulses):self.pending=pulses
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
        self.pi=FakeGPIO();self.tf=Output();self.odom_pub=Output();self.scan_pub=Output();self.map_pub=Output()
        self.map=None;self.map_version=0;self.scan_count=0


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
    def test_unverified_floor_command_has_hard_pulse_budget(self):
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
        self.advance(1.3);r.tick()
        self.assertTrue(r.estop);self.assertIsNone(r.lease.token)
        self.assertEqual(r.pi.pins[bridge.CFG['enable_pin']],1)
        self.assertTrue(all(r.pi.pins[pin]==0 for pin in bridge.CFG['step_pins']))
    def test_navigation_is_locked_but_manual_is_available_for_commissioning(self):
        r=self.robot
        with self.assertRaises(ValueError):r.arm('navigation',True)
        self.assertFalse(r.pi.sent)
        r.arm('mapping',True)
        msg=Twist();msg.linear.x=.03;r.velocity(msg)
        self.assertEqual(r.command,[0.,0.,0.])
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
