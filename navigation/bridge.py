"""Robot IO, fail-closed motion interlock, ROS navigation and local web UI."""
import atexit
from contextlib import closing
import json
import copy
import hashlib
import math
import os
from pathlib import Path
import signal
import statistics
import threading
import time

import pigpio
import serial
import smbus
import yaml
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy, qos_profile_sensor_data
from rclpy.time import Time
from geometry_msgs.msg import Twist, TransformStamped
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry, OccupancyGrid, Path as RosPath
from nav2_msgs.action import NavigateToPose
from slam_toolbox.srv import SerializePoseGraph, DeserializePoseGraph, Reset
from tf2_ros import TransformBroadcaster, Buffer, TransformListener
from waitress import serve
from PIL import Image

from core import LD19, wheels, finite_wave
from session import Session, ControlLease, atomic_json
from spatial import overlay_indices, zone_collision, laser_to_base, self_return, obstacle_risk, sweep_hits_zones
from api import create_app

ROOT = Path(__file__).parent
DATA = Path('/data')
CFG = yaml.safe_load((ROOT / 'config/robot.yaml').read_text())


def yaw(q):
    return math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))


class Bridge(Node):
    def __init__(self):
        super().__init__('matebot_bridge')
        self.lock = threading.RLock()
        self.save_lock = threading.Lock()
        self.session=Session(DATA)
        self.lease=ControlLease()
        self.annotations=self.session.get()
        self.zones={tuple(c) for c in self.annotations['zones']}
        self.map_accept_after=0
        self.closed=False
        self.save_event=threading.Event()
        self.running = True
        self.estop = True
        self.adopt_legacy_map()
        self.localized = self.active_snapshot() is None
        self.restored = False
        self.pose_confirmed = False
        self.scan_at = self.imu_at = self.cmd_at = 0.0
        self.scan_count = self.valid_points = 0
        self.nearest = float('inf')
        self.scan_points = []
        self.base_points=[]
        self.self_points=0
        self.map = None
        self.map_version = 0
        self.path = []
        self.goal_handle = None
        self.goal_pending = False
        self.goal_generation = 0
        self.goal_status = 'Bereit'
        self.stop_reason='Gestoppt – Steuerung vor Ort freigeben'
        self.error = ''
        self.saved_at = self.read_runtime().get('saved_at')
        self.gyro_bias = None
        self.command = [0., 0., 0.]
        self.applied_cmd = [0., 0., 0.]
        self.manual_until = 0.
        self.operator_at = 0.
        self.wave_started = 0.
        self.wave_integrated = 0.
        self.wave_velocity = [0., 0., 0.]
        self.burst_pulses=0
        self.burst_exhausted=False
        self.last_manual_sequence=-1
        self.x = self.y = self.heading = 0.
        self.pose = None
        self.last_tick = time.monotonic()
        self.last_wave = -1
        self.pi = pigpio.pi('127.0.0.1')
        if not self.pi.connected:
            raise RuntimeError('pigpiod nicht erreichbar; kein Simulations-Fallback')
        for p in CFG['step_pins'] + CFG['direction_pins'] + [CFG['enable_pin']]:
            self.pi.set_mode(p, pigpio.OUTPUT)
        self.stop_hardware()
        self.tf = TransformBroadcaster(self)
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.scan_pub = self.create_publisher(LaserScan, 'scan', qos_profile_sensor_data)
        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.create_subscription(Twist, 'cmd_vel', self.velocity, 10)
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                         reliability=ReliabilityPolicy.RELIABLE)
        self.map_pub=self.create_publisher(OccupancyGrid,'map',qos)
        self.publish_navigation_map()
        self.create_subscription(OccupancyGrid, 'slam_map', self.receive_map, qos)
        self.create_subscription(RosPath, 'plan', self.receive_path, 1)
        self.navigator = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.serialize = self.create_client(SerializePoseGraph, '/slam_toolbox/serialize_map')
        self.deserialize = self.create_client(DeserializePoseGraph, '/slam_toolbox/deserialize_map')
        self.reset_client=self.create_client(Reset,'/slam_toolbox/reset')
        self.create_timer(0.05, self.tick)
        self.create_timer(0.25, self.update_pose)
        threading.Thread(target=self.lidar_loop, daemon=True).start()
        threading.Thread(target=self.imu_loop, daemon=True).start()
        threading.Thread(target=self.autosave_loop, daemon=True).start()

    def navigation_ready(self):
        return all(self.annotations['calibration'].values())

    def adopt_legacy_map(self):
        folder=DATA/'current'
        if (folder/'house.posegraph').exists() and not (folder/'session.json').exists():
            atomic_json(folder/'session.json',self.annotations)

    def active_snapshot(self):
        pointer=DATA/'current'
        if not pointer.exists():
            if not self.annotations.get('fresh',True):raise RuntimeError('Gespeicherte Karte fehlt – Sicherung wiederherstellen')
            return None
        folder=pointer.resolve()
        if folder.parent!=DATA.resolve():raise RuntimeError('Kartenverweis außerhalb des Datenordners')
        metadata=folder/'session.json'
        if not metadata.exists():raise RuntimeError('Karten-Metadaten fehlen – Fahrfreigabe gesperrt')
        doc=json.loads(metadata.read_text(encoding='utf-8'))
        if doc.get('map_id')==self.annotations['map_id']:return folder
        if not self.annotations.get('fresh',True):raise RuntimeError('Karte und Sperrzonen gehören nicht zusammen')
        return None

    def read_runtime(self):
        try:
            doc=json.loads((DATA/'runtime.json').read_text(encoding='utf-8'))
            return doc if doc.get('map_id')==self.annotations['map_id'] else {}
        except (OSError,ValueError):return {}

    def persist_runtime(self):
        if not self.localized:return
        atomic_json(DATA/'runtime.json',dict(map_id=self.annotations['map_id'],
                    pose=self.pose,saved_at=self.saved_at,updated_at=time.time()))

    def saved_map_json(self):
        folder=self.active_snapshot()
        if folder is None:return None
        raw=folder/'map.json'
        if raw.exists():return json.loads(raw.read_text(encoding='utf-8'))
        info=yaml.safe_load((folder/'house.yaml').read_text())
        with Image.open(folder/'house.pgm') as source:
            image=source.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            return dict(width=image.width,height=image.height,resolution=info['resolution'],
                        origin=info['origin'],cells=[-1 if v==205 else 0 if v>220 else 100 for v in image.tobytes()],version=-1)

    def refresh_annotations(self):
        self.annotations=self.session.get()
        self.zones={tuple(c) for c in self.annotations['zones']}
        self.publish_navigation_map()

    def publish_navigation_map(self):
        if not self.localized:
            saved=self.saved_map_json()
            if not saved:return
            msg=OccupancyGrid()
            msg.header.frame_id='map';msg.header.stamp=self.get_clock().now().to_msg()
            msg.info.width=saved['width'];msg.info.height=saved['height'];msg.info.resolution=saved['resolution']
            msg.info.origin.position.x=saved['origin'][0];msg.info.origin.position.y=saved['origin'][1]
            msg.info.origin.orientation.z=math.sin(saved['origin'][2]/2);msg.info.origin.orientation.w=math.cos(saved['origin'][2]/2)
            msg.data=saved['cells']
        elif self.map is not None:msg=copy.deepcopy(self.map)
        else:return
        origin=[msg.info.origin.position.x,msg.info.origin.position.y,yaw(msg.info.origin.orientation)]
        key=(msg.info.width,msg.info.height,msg.info.resolution,*origin,self.annotations['revision'])
        if getattr(self,'overlay_key',None)!=key:
            self.overlay_cells=overlay_indices(msg.info.width,msg.info.height,msg.info.resolution,
                                               origin,self.zones,self.annotations['grid_size'])
            self.overlay_key=key
        for index in self.overlay_cells:msg.data[index]=100
        self.map_pub.publish(msg)

    def arm(self,mode,on_site):
        with self.lock:
            if on_site is not True:raise ValueError('Freigabe nur bei Aufsicht vor Ort')
            if mode!=self.annotations['mode']:raise ValueError('Modus wurde geändert – Ansicht aktualisieren')
            reason=self.readiness(mode,include_stop=False)
            if reason:raise ValueError(reason)
            token=self.lease.acquire(time.monotonic())
            self.estop=False
            self.command=[0.,0.,0.]
            self.burst_pulses=0
            self.burst_exhausted=False
            self.last_manual_sequence=-1
            self.goal_status='Steuerung freigegeben'
            return dict(token=token)

    def heartbeat(self,token):
        with self.lock:self.lease.check(token,time.monotonic(),refresh=True)

    def manual(self,token,vx,vy,wz,sequence=None):
        with self.lock:
            self.lease.check(token,time.monotonic())
            if type(sequence) is not int or sequence<0 or sequence>2**53:
                raise ValueError('Ungültige Befehlsfolge')
            if sequence<=self.last_manual_sequence:return
            self.last_manual_sequence=sequence
            if self.annotations['mode']!='mapping':raise ValueError('Manuelle Steuerung nur im Einlernmodus')
            if not all(math.isfinite(v) for v in (vx,vy,wz)):raise ValueError('Ungültige Geschwindigkeit')
            if not any((vx,vy,wz)):
                self.command=[0.,0.,0.]
                self.applied_cmd=[0.,0.,0.]
                self.burst_pulses=0
                self.burst_exhausted=False
                self.stop_hardware()
                return
            reason=self.readiness(cmd=[vx,vy,wz])
            if reason:raise ValueError(reason)
            if self.burst_exhausted:raise ValueError('Prüfimpuls beendet – loslassen und erneut drücken')
            if math.hypot(vx,vy)>CFG['manual_max_linear_speed']+.00001 or abs(wz)>CFG['manual_max_angular_speed']+.00001:
                raise ValueError('Geschwindigkeit zu hoch')
            self.command=[vx,vy,wz]
            self.manual_until=time.monotonic()+.3
            self.cmd_at=time.monotonic()

    def edit_zones(self,paint,erase,size,revision):
        with self.lock:
            self.stop('Sperrzonen geändert – erneut freigeben')
            self.session.edit_zones(paint,erase,size,revision)
            self.refresh_annotations()
            return self.annotations

    def settings(self,mode=None,calibration=None,title=None):
        with self.lock:
            self.stop('Einstellungen geändert – erneut freigeben')
            self.session.settings(mode,calibration,title)
            self.refresh_annotations()
            return self.annotations

    def favorite(self,name,x,y,delete=False):
        with self.lock:
            self.session.favorite(name,x,y,delete)
            self.refresh_annotations()
            return self.annotations

    def new_map(self):
        with self.save_lock:return self._new_map()

    def _new_map(self):
        with self.lock:
            self.map_transition=True
            self.awaiting_new_map=False
            self.stop('Neue Karte wird vorbereitet')
        try:
            if not self.reset_client.wait_for_service(timeout_sec=2):raise ValueError('SLAM noch nicht bereit')
            with self.lock:self.x=self.y=self.heading=0.
            time.sleep(.12)  # Publish fresh odom before the first scan of the new graph.
            req=Reset.Request()
            req.pause_new_measurements=False
            self.wait_future(self.reset_client.call_async(req))
            with self.lock:
                previous=self.active_snapshot()
                if previous:
                    atomic_json(DATA/'archives'/('map-'+self.annotations['map_id']+'.json'),
                                dict(snapshot=previous.name,session=self.annotations))
                self.session.new_map()
                self.annotations=self.session.get()
                self.zones=set()
                self.map=None
                self.x=self.y=self.heading=0.
                self.localized=True
                self.restored=False
                self.pose=None
                self.map_accept_after=self.get_clock().now().nanoseconds
                self.awaiting_new_map=True
                self.map_version+=1
                self.saved_at=None
                self.stop_reason='Neue Karte bereit – Steuerung vor Ort freigeben'
        except Exception:
            self.map_transition=False
            raise

    def readiness(self,mode=None,include_stop=True,cmd=None):
        now = time.monotonic()
        mode=mode or self.annotations['mode']
        if getattr(self,'map_transition',False):return 'Karte wird geladen – bitte kurz warten'
        if not CFG.get('manual_ready',False):return 'Radrichtungen noch nicht geprüft'
        if mode=='navigation' and not self.navigation_ready():return 'Zielmodus: zuerst die vier Bodenprüfungen bestätigen'
        if include_stop and self.estop:return self.stop_reason
        if now-self.scan_at>.4 or self.valid_points<80:return 'LiDAR nicht bereit'
        if now-self.imu_at>.4:return 'IMU nicht bereit'
        if not self.localized:return 'Startposition setzen oder eine neue Karte beginnen'
        if not self.pose or self.pose.get('age',99)>.5:return 'Roboterposition nicht aktuell'
        if sweep_hits_zones(self.pose,cmd or [0.,0.,0.],CFG,self.zones,self.annotations['grid_size']):
            return 'Sperrzone: Roboter oder Fahrweg überschneidet rote Zellen'
        if cmd and obstacle_risk(self.base_points,CFG,cmd):return 'Hindernis im Fahrweg – gestoppt'
        return ''

    def reason(self):
        return self.readiness(cmd=self.command)

    def stop_hardware(self):
        self.pi.wave_tx_stop()
        for p in CFG['step_pins']:
            self.pi.set_PWM_dutycycle(p, 0)
            self.pi.write(p, 0)
        self.pi.write(CFG['enable_pin'], 1 if CFG['enable_active_low'] else 0)
        self.wave_velocity = [0., 0., 0.]

    def stop(self,reason='Gestoppt – Steuerung vor Ort freigeben'):
        with self.lock:
            self.estop = True
            self.stop_reason=reason
            self.lease.clear()
            self.goal_generation += 1
            self.command = [0., 0., 0.]
            self.applied_cmd = [0., 0., 0.]
            self.manual_until = 0.
            self.burst_pulses=0
            self.burst_exhausted=False
            self.stop_hardware()
            if self.goal_handle:
                self.goal_handle.cancel_goal_async()
                self.goal_handle = None
            self.goal_status = 'Gestoppt'
            self.path=[]
            self.save_event.set()

    def velocity(self, msg):
        with self.lock:
            if self.estop or self.annotations['mode']!='navigation' or not self.navigation_ready():return
            if self.manual_until > time.monotonic():
                return
            values = [msg.linear.x, msg.linear.y, msg.angular.z]
            if not all(math.isfinite(x) for x in values):
                self.stop()
                return
            v = CFG['max_linear_speed']
            self.command = [max(-v, min(v, x)) for x in values[:2]] + [
                max(-CFG['max_angular_speed'], min(CFG['max_angular_speed'], values[2]))]
            magnitude = math.hypot(*self.command[:2])
            if magnitude > v:
                self.command[:2] = [x*v/magnitude for x in self.command[:2]]
            self.cmd_at = time.monotonic()

    def tick(self):
        with self.lock:
            if not self.running:return
            now = time.monotonic()
            dt = min(now-self.last_tick, 0.15)
            self.last_tick = now
            if not self.estop and now-self.lease.at>1.2:
                self.stop('Verbindung zur Steuerung abgelaufen – gestoppt')
            if not self.estop:
                reason=self.reason()
                if reason:self.stop(reason)
            cmd = list(self.command)
            if self.reason() or now-self.cmd_at > 0.25:
                cmd = [0., 0., 0.]
                self.applied_cmd = [0., 0., 0.]
            elif any(abs(v)>0.001 for v in cmd):
                limits=[0.12*dt,0.12*dt,0.25*dt]
                cmd=[old+max(-limit,min(limit,target-old))
                     for old,target,limit in zip(self.applied_cmd,cmd,limits)]
                self.applied_cmd=list(cmd)
            else:
                self.applied_cmd = [0., 0., 0.]
            # IMU supplies heading; commanded steps estimate translation only.
            # Integrate only the active part of finite wave trains, excluding idle gaps.
            elapsed = max(0., min(now-self.wave_started, 0.08))
            active_dt = max(0., elapsed-self.wave_integrated)
            self.wave_integrated = elapsed
            vx, vy, wz = self.wave_velocity
            self.x += (vx*math.cos(self.heading)-vy*math.sin(self.heading))*active_dt
            self.y += (vx*math.sin(self.heading)+vy*math.cos(self.heading))*active_dt
            try:
                if any(abs(v) > 0.001 for v in cmd):
                    if not self.pi.wave_tx_busy():
                        if self.last_wave >= 0:
                            self.pi.wave_delete(self.last_wave)
                            self.last_wave = -1
                        speeds = wheels(*cmd, CFG['wheelbase'], CFG['track_width'])
                        steps_m = CFG['steps_per_revolution']*CFG['microsteps']/(math.pi*CFG['wheel_diameter'])
                        hz = [s*steps_m for s in speeds]
                        factor = min(1., 4800/max(max(abs(h) for h in hz),1.))
                        hz = [h*factor for h in hz]
                        if not self.annotations['calibration']['translation']:
                            remaining=CFG['floor_test_pulse_limit']-self.burst_pulses
                            if remaining<=0:
                                self.burst_exhausted=True
                                self.command=[0.,0.,0.]
                                self.stop_hardware()
                                hz=[0.,0.,0.,0.]
                            else:
                                floor_factor=min(1.,CFG['floor_test_max_frequency']/max(max(abs(h) for h in hz),1.),
                                                 remaining/(.08*max(max(abs(h) for h in hz),1.)))
                                hz=[h*floor_factor for h in hz]
                                factor*=floor_factor
                                self.burst_pulses+=int(max(abs(h) for h in hz)*.08+1e-8)
                        for p, h, sign in zip(CFG['direction_pins'], hz, CFG['direction_signs']):
                            self.pi.write(p, int(h*sign > 0))
                        pulses = [pigpio.pulse(*p) for p in finite_wave(hz, CFG['step_pins'])]
                        self.pi.wave_add_generic(pulses)
                        self.last_wave = self.pi.wave_create()
                        if self.last_wave < 0:
                            raise RuntimeError('pigpio wave_create fehlgeschlagen')
                        self.pi.write(CFG['enable_pin'], 0 if CFG['enable_active_low'] else 1)
                        self.pi.wave_send_once(self.last_wave)
                        self.wave_started = now
                        self.wave_integrated = 0.
                        self.wave_velocity = [v*factor for v in cmd]
                        if self.burst_exhausted:self.wave_velocity=[0.,0.,0.]
                else:
                    self.stop_hardware()
            except Exception as exc:
                self.error = str(exc)
                self.stop()
            stamp = self.get_clock().now().to_msg()
            tf = TransformStamped()
            tf.header.stamp = stamp
            tf.header.frame_id = 'odom'
            tf.child_frame_id = 'base_link'
            tf.transform.translation.x, tf.transform.translation.y = self.x, self.y
            tf.transform.rotation.z = math.sin(self.heading/2)
            tf.transform.rotation.w = math.cos(self.heading/2)
            self.tf.sendTransform(tf)
            odom = Odometry()
            odom.header = tf.header
            odom.child_frame_id = 'base_link'
            odom.pose.pose.position.x, odom.pose.pose.position.y = self.x, self.y
            odom.pose.pose.orientation = tf.transform.rotation
            odom.twist.twist.linear.x, odom.twist.twist.linear.y = vx, vy
            odom.twist.twist.angular.z = wz
            for index in (0, 7, 35):
                odom.pose.covariance[index] = 0.1
                odom.twist.covariance[index] = 0.1
            self.odom_pub.publish(odom)

    def lidar_loop(self):
        while self.running:
            try:
                port = CFG['lidar_port']
                # Device mapped into container by its kernel name; host by-id remains in config.
                if not Path(port).exists():
                    port = '/dev/ttyUSB0'
                decoder = LD19()
                ranges = [float('nan')]*360
                previous = None
                begun = False
                start = self.get_clock().now()
                with serial.Serial(port, 230400, timeout=0.2, exclusive=True) as source:
                    while self.running:
                        for packet in decoder.feed(source.read(470)):
                            for angle, distance, confidence in packet:
                                if previous is not None and previous-angle > 180:
                                    if begun:
                                        self.publish_scan(ranges, start)
                                    begun = True
                                    ranges = [float('nan')]*360
                                    start = self.get_clock().now()
                                previous = angle
                                if 0.12 <= distance <= 12.0 and confidence >= 15:
                                    # LD19 clockwise -> REP-103 counter-clockwise.
                                    index = int(round((-angle) % 360)) % 360
                                    ranges[index] = distance
            except Exception as exc:
                self.error = 'LiDAR: ' + str(exc)
                time.sleep(1)

    def publish_scan(self, ranges, start):
        ranges=list(ranges)
        base_points=[]
        filtered=0
        for i,d in enumerate(ranges):
            if not math.isfinite(d):continue
            bx,by=laser_to_base(d*math.cos(i*math.pi/180),d*math.sin(i*math.pi/180),CFG)
            if self_return(bx,by,CFG):
                ranges[i]=float('nan')
                filtered+=1
            else:base_points.append((bx,by))
        scan = LaserScan()
        scan.header.frame_id = 'laser'
        scan.header.stamp = start.to_msg()
        scan.angle_min = 0.0
        scan.angle_increment = math.pi/180
        scan.angle_max = 359*math.pi/180
        scan.scan_time = (self.get_clock().now()-start).nanoseconds/1e9
        # Binned clockwise acquisition is not time-ordered in ROS angle order.
        scan.time_increment = 0.0
        scan.range_min, scan.range_max = 0.12, 12.0
        scan.ranges = ranges
        valid = [(i, d) for i,d in enumerate(ranges) if math.isfinite(d)]
        with self.lock:
            self.scan_at = time.monotonic()
            self.valid_points = len(valid)
            self.base_points=base_points
            self.self_points=filtered
            self.nearest = min((d for _,d in valid), default=float('inf'))
            self.scan_count += 1
            self.scan_points = [[round(d*math.cos(i*math.pi/180),3),
                                 round(d*math.sin(i*math.pi/180),3)] for i,d in valid]
        self.scan_pub.publish(scan)

    def imu_loop(self):
        while self.running:
            try:
                with closing(smbus.SMBus(1)) as bus:
                    addr = CFG['imu_address']
                    if bus.read_byte_data(addr, 0x75) != 0x68:
                        raise RuntimeError('MPU6050 WHO_AM_I stimmt nicht')
                    bus.write_byte_data(addr, 0x6B, 0)
                    bus.write_byte_data(addr, 0x1B, 0)
                    bus.write_byte_data(addr, 0x1A, 3)
                    # Startup remains stopped while stationary gyro bias is measured.
                    time.sleep(0.5)
                    samples=[]
                    for _ in range(150):
                        values=bus.read_i2c_block_data(addr,0x47,2)
                        raw=(values[0]<<8)|values[1]
                        samples.append((raw-65536 if raw>=32768 else raw)/131.)
                        time.sleep(0.01)
                    if statistics.pstdev(samples)>0.3 or abs(statistics.mean(samples))>5:
                        raise RuntimeError('Zur Gyro-Kalibrierung bitte stillstehen')
                    self.gyro_bias=statistics.mean(samples)
                    last = time.monotonic()
                    while self.running:
                        values = bus.read_i2c_block_data(addr, 0x47, 2)  # gyro Z, NOT X (0x43)
                        raw = (values[0]<<8) | values[1]
                        if raw >= 32768:
                            raw -= 65536
                        now = time.monotonic()
                        rate = (raw/131.0-self.gyro_bias)*math.pi/180*CFG['imu_yaw_sign']
                        with self.lock:
                            self.heading += rate*min(now-last, 0.05)
                            self.imu_at = now
                        last = now
                        time.sleep(0.01)
            except Exception as exc:
                self.error = 'IMU: ' + str(exc)
                time.sleep(1)

    def update_pose(self):
        try:
            tf = self.buffer.lookup_transform('map', 'base_link', Time())
            age = (self.get_clock().now().nanoseconds -
                   (tf.header.stamp.sec*10**9+tf.header.stamp.nanosec))/1e9
            self.pose = {'x': tf.transform.translation.x, 'y': tf.transform.translation.y,
                         'yaw': yaw(tf.transform.rotation), 'age': age}
            if time.monotonic()-getattr(self,'last_persist',0)>10:
                self.last_persist=time.monotonic()
                self.persist_runtime()
        except Exception:
            self.pose = None

    def receive_path(self, msg):
        self.path = [[p.pose.position.x, p.pose.position.y] for p in msg.poses]

    def receive_map(self, msg):
        with self.lock:
            stamp=msg.header.stamp.sec*10**9+msg.header.stamp.nanosec
            if stamp<self.map_accept_after:return
            if getattr(self,'map_transition',False) and not getattr(self,'awaiting_new_map',False):return
            self.map = msg
            self.map_transition=False
            self.awaiting_new_map=False
            self.map_version += 1
            self.publish_navigation_map()

    def state(self):
        with self.lock:
            return dict(calibrated=self.navigation_ready(),manual_ready=CFG.get('manual_ready',False),estop=self.estop,
                        blocked=self.reason(), lidar_age=time.monotonic()-self.scan_at,
                        imu_age=time.monotonic()-self.imu_at, valid_points=self.valid_points,
                        scan_count=self.scan_count, points=self.scan_points,
                        lidar_transform=[CFG['lidar_x'],CFG['lidar_y'],CFG['lidar_yaw']],
                        pose=self.pose, path=self.path, map_version=self.map_version,
                        saved_at=self.saved_at, goal_status=self.goal_status,
                        gyro_bias=self.gyro_bias,
                        error=self.error, localized=self.localized,
                        saved_map=self.active_snapshot() is not None,
                        annotations=self.annotations, control_active=self.lease.token is not None,
                        self_points=self.self_points, last_pose=self.read_runtime().get('pose'),
                        initial_floor_test=not self.annotations['calibration']['translation'],
                        manual_limits=[CFG['manual_max_linear_speed'],CFG['manual_max_angular_speed']],
                        camera_view=dict(yaw=CFG.get('camera_yaw',0.),horizontal_fov=CFG.get('camera_horizontal_fov',53.5)),
                        geometry=[CFG['footprint_length'],CFG['footprint_width']])

    def map_json(self):
        with self.lock:
            if (not self.localized or getattr(self,'map_transition',False)) and self.active_snapshot():return self.saved_map_json()
            m = self.map
            if m is None:
                return None
            return dict(width=m.info.width, height=m.info.height,
                        resolution=m.info.resolution,
                        origin=[m.info.origin.position.x,m.info.origin.position.y,
                                yaw(m.info.origin.orientation)], cells=list(m.data),
                        version=self.map_version)

    def wait_future(self, future, timeout=15):
        deadline = time.monotonic()+timeout
        while not future.done() and time.monotonic()<deadline and self.running:
            time.sleep(0.05)
        if not future.done():
            raise RuntimeError('ROS-Dienst antwortet nicht rechtzeitig')
        result = future.result()
        if result is None:
            raise RuntimeError('ROS-Dienst fehlgeschlagen')
        return result

    def save_map(self,timeout=30):
        if not self.save_lock.acquire(blocking=False):
            raise ValueError('Speichern läuft bereits')
        try:
            if self.map is None or getattr(self,'map_transition',False):
                raise ValueError('Noch keine Karte vorhanden')
            # Never overwrite a saved house map with a fresh boot scan.
            if self.active_snapshot() is not None and not self.localized:
                raise ValueError('Gespeicherte Karte zuerst mit Position fortsetzen')
            if not self.serialize.wait_for_service(timeout_sec=2):
                raise RuntimeError('SLAM-Speicherdienst nicht bereit')
            name = 'map-' + time.strftime('%Y%m%d-%H%M%S')+'-'+str(time.time_ns())[-9:]
            folder = DATA/name
            folder.mkdir()
            prefix = str(folder/'house')
            req = SerializePoseGraph.Request()
            req.filename = prefix
            result = self.wait_future(self.serialize.call_async(req), timeout)
            if result.result != 0:
                raise RuntimeError('SLAM konnte Posegraph nicht speichern')
            if not all(Path(prefix+'.'+ext).stat().st_size>0 for ext in ('posegraph','data')):
                raise RuntimeError('SLAM-Snapshot ist unvollständig')
            m = self.map_json()
            atomic_json(folder/'map.json',m)
            atomic_json(folder/'session.json',self.session.get())
            atomic_json(folder/'pose.json',self.pose)
            pixels = bytes(205 if c<0 or 25<=c<65 else 254 if c<25 else 0 for c in m['cells'])
            Image.frombytes('L',(m['width'],m['height']),pixels).transpose(
                Image.Transpose.FLIP_TOP_BOTTOM).save(prefix+'.pgm')
            (folder/'house.yaml').write_text(yaml.safe_dump(dict(
                image='house.pgm', resolution=m['resolution'], origin=m['origin'],
                negate=0, occupied_thresh=0.65, free_thresh=0.25)))
            digests={}
            for filename in ('house.posegraph','house.data','house.pgm','house.yaml','map.json','session.json','pose.json'):
                path=folder/filename
                with path.open('rb') as stream:
                    os.fsync(stream.fileno())
                    digests[filename]=hashlib.sha256(stream.read()).hexdigest()
            atomic_json(folder/'manifest.json',dict(schema=1,map_id=self.annotations['map_id'],
                        saved_at=time.time(),sha256=digests))
            # Atomic pointer switches entire graph+data pair together.
            tmp = DATA/'current.next'
            tmp.unlink(missing_ok=True)
            tmp.symlink_to(name, target_is_directory=True)
            os.replace(tmp, DATA/'current')
            for suffix in ('posegraph','data'):
                alias = DATA/('current.'+suffix)
                if not alias.is_symlink():
                    alias.symlink_to('current/house.'+suffix)
            self.saved_at = time.strftime('%Y-%m-%d %H:%M:%S')
            with self.lock:
                self.session.mark_saved()
                self.refresh_annotations()
            self.persist_runtime()
            atomic_json(DATA/'latest.json',dict(snapshot=name,map_id=self.annotations['map_id']))
            # Keep the last 20 complete snapshots, never remove the current target.
            import shutil
            folders=[]
            for candidate in sorted(DATA.glob('map-*')):
                try:
                    meta=json.loads((candidate/'session.json').read_text(encoding='utf-8'))
                    if meta.get('map_id')==self.annotations['map_id']:folders.append(candidate)
                except (OSError,ValueError):continue
            for old in folders[:-20]:
                if old.is_dir() and old.name != name:
                    shutil.rmtree(old)
            return {'saved': name}
        finally:
            self.save_lock.release()

    def restore(self, x, y, heading):
        with self.save_lock:return self._restore(x,y,heading)

    def _restore(self,x,y,heading):
        self.stop()
        folder=self.active_snapshot()
        if folder is None:
            raise ValueError('Keine gespeicherte Karte vorhanden')
        manifest=folder/'manifest.json'
        if manifest.exists():
            doc=json.loads(manifest.read_text(encoding='utf-8'))
            for filename,digest in doc['sha256'].items():
                if filename not in ('house.posegraph','house.data','house.pgm','house.yaml','map.json','session.json','pose.json'):
                    raise ValueError('Ungültiges Sicherungsmanifest')
                if hashlib.sha256((folder/filename).read_bytes()).hexdigest()!=digest:
                    raise ValueError('Karten-Sicherung beschädigt; Fahrfreigabe gesperrt')
        if not self.deserialize.wait_for_service(timeout_sec=2):
            raise ValueError('SLAM-Ladedienst noch nicht bereit')
        req = DeserializePoseGraph.Request()
        req.filename = str(folder/'house')
        req.match_type = 2
        # Jazzy uses Pose2D (the upstream ros2 branch has since changed to Pose).
        req.initial_pose.x, req.initial_pose.y = x,y
        req.initial_pose.theta = heading
        self.map_transition=True
        self.awaiting_new_map=False
        try:result = self.wait_future(self.deserialize.call_async(req), 30)
        except Exception:
            self.map_transition=False
            raise
        # Jazzy acknowledges with an empty response; newer releases have a result code.
        code=getattr(result,'result',0)
        if code != 0:
            self.map_transition=False
            raise ValueError('Karte konnte nicht geladen werden: '+str(code))
        self.restored = self.localized = True
        self.map_accept_after=self.get_clock().now().nanoseconds
        self.awaiting_new_map=True
        self.stop_reason='Position gesetzt – Ausrichtung prüfen und Steuerung freigeben'
        return {'loaded': True}

    def autosave_loop(self):
        while self.running:
            self.save_event.wait(30)
            self.save_event.clear()
            if not self.running:return
            if self.map is None or not self.localized or getattr(self,'map_transition',False):continue
            try:
                self.save_map()
            except Exception as exc:
                self.get_logger().warning('Autosave: '+str(exc))

    def goal(self, x, y,token):
        with self.lock:
            self.lease.check(token,time.monotonic())
            if self.annotations['mode']!='navigation':raise ValueError('Bitte zuerst den Zielmodus wählen')
            reason = self.reason()
            if reason:
                raise ValueError(reason)
            if self.goal_pending or self.goal_handle:
                raise ValueError('Ziel läuft bereits – zuerst stoppen')
            if not self.pose or self.pose['age']>0.5 or self.map is None:
                raise ValueError('Karte oder aktuelle Position fehlen')
            m = self.map
            # Map origin orientation is normally zero, handle arbitrary yaw too.
            a = yaw(m.info.origin.orientation)
            dx,dy = x-m.info.origin.position.x,y-m.info.origin.position.y
            col = math.floor((dx*math.cos(a)+dy*math.sin(a))/m.info.resolution)
            row = math.floor((-dx*math.sin(a)+dy*math.cos(a))/m.info.resolution)
            if not (0<=col<m.info.width and 0<=row<m.info.height):
                raise ValueError('Ziel außerhalb der Karte')
            cell = m.data[row*m.info.width+col]
            if cell<0 or cell>=25:
                raise ValueError('Bitte eine bekannte freie Fläche wählen')
            radius=math.hypot(CFG['footprint_length'],CFG['footprint_width'])/2+.05
            if zone_collision(x,y,radius,self.zones,self.annotations['grid_size']):
                raise ValueError('Ziel liegt in oder zu nah an einer Sperrzone')
            if not self.navigator.server_is_ready():
                raise ValueError('Navigation noch nicht bereit')
            goal = NavigateToPose.Goal()
            goal.pose.header.frame_id='map'
            goal.pose.header.stamp=self.get_clock().now().to_msg()
            goal.pose.pose.position.x,goal.pose.pose.position.y=x,y
            goal.pose.pose.orientation.w=1.0
            self.goal_pending=True
            generation = self.goal_generation
            f=self.navigator.send_goal_async(goal)
        try:
            handle=self.wait_future(f,5)
        except Exception:
            with self.lock:
                self.goal_pending=False
                self.goal_generation+=1
            # A delayed acceptance must never start an orphaned goal.
            def cancel_late(future):
                handle=future.result()
                if handle and handle.accepted:
                    handle.cancel_goal_async()
            f.add_done_callback(cancel_late)
            raise
        with self.lock:
            self.goal_pending=False
            if generation!=self.goal_generation:
                if handle.accepted:
                    handle.cancel_goal_async()
                raise ValueError('Ziel durch Stopp verworfen')
            if not handle.accepted:
                raise ValueError('Ziel vom Navigator abgelehnt')
            self.goal_handle=handle
            self.goal_status='Unterwegs'
            handle.get_result_async().add_done_callback(
                lambda future: self.goal_result(future,generation))
        return {'accepted':True}

    def goal_result(self, future, generation):
        with self.lock:
            if generation!=self.goal_generation:
                return
            self.goal_handle=None
            status=future.result().status
            self.goal_status={4:'Ziel erreicht',5:'Abgebrochen',6:'Kein sicherer Weg gefunden'}.get(status,'Beendet')
            self.command=[0.,0.,0.]
            self.stop_hardware()

    def close(self):
        if self.closed:return
        self.closed=True
        self.running=False
        self.stop()
        self.save_event.set()
        self.pi.stop()



if __name__=='__main__':
    from rclpy.signals import SignalHandlerOptions
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    robot=Bridge()
    app=create_app(robot)
    atexit.register(robot.close)
    def spin():
        try:rclpy.spin(robot)
        except Exception:
            if robot.running:
                robot.stop('ROS-Verbindung ausgefallen')
                os._exit(1)
    threading.Thread(target=spin,daemon=True).start()
    def shutdown(*_):
        robot.stop('Dienst wird beendet')
        try:robot.persist_runtime()
        except OSError:pass
        robot.close()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM,shutdown)
    signal.signal(signal.SIGINT,shutdown)
    serve(app,host='0.0.0.0',port=int(os.environ.get('MATEBOT_PORT','8080')),threads=8,
          channel_timeout=10,max_request_body_size=256*1024)
