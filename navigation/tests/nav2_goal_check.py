"""Real Nav2 closed-loop goal test in an isolated domain. NO GPIO connection."""
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile,DurabilityPolicy,ReliabilityPolicy
from geometry_msgs.msg import Twist,TransformStamped
from nav_msgs.msg import OccupancyGrid,Odometry
from sensor_msgs.msg import LaserScan
from nav2_msgs.action import NavigateToPose
from lifecycle_msgs.srv import GetState
from tf2_ros import TransformBroadcaster,StaticTransformBroadcaster

assert os.environ.get('ROS_DOMAIN_ID') not in (None,'42'),'Isolated domain required'


class World(Node):
    def __init__(self):
        super().__init__('goal_test_world');self.x=self.y=self.yaw=0.;self.command=Twist();self.moves=0;self.at=time.monotonic();self.count=0
        self.tf=TransformBroadcaster(self);self.static=StaticTransformBroadcaster(self)
        fixed=TransformStamped();fixed.header.frame_id='map';fixed.child_frame_id='odom';fixed.transform.rotation.w=1.;self.static.sendTransform(fixed)
        qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL,reliability=ReliabilityPolicy.RELIABLE)
        self.map_pub=self.create_publisher(OccupancyGrid,'map',qos)
        self.odom_pub=self.create_publisher(Odometry,'odom',10);self.scan_pub=self.create_publisher(LaserScan,'scan',10)
        self.create_subscription(Twist,'cmd_vel',self.velocity,10)
        self.create_timer(.05,self.tick)
    def velocity(self,msg):
        self.command=msg
        if abs(msg.linear.x)+abs(msg.linear.y)+abs(msg.angular.z)>.001:self.moves+=1
    def tick(self):
        now=time.monotonic();dt=min(now-self.at,.1);self.at=now;v=self.command
        self.x+=(v.linear.x*math.cos(self.yaw)-v.linear.y*math.sin(self.yaw))*dt
        self.y+=(v.linear.x*math.sin(self.yaw)+v.linear.y*math.cos(self.yaw))*dt;self.yaw+=v.angular.z*dt
        stamp=self.get_clock().now().to_msg();tf=TransformStamped();tf.header.frame_id='odom';tf.header.stamp=stamp;tf.child_frame_id='base_link'
        tf.transform.translation.x=self.x;tf.transform.translation.y=self.y;tf.transform.rotation.z=math.sin(self.yaw/2);tf.transform.rotation.w=math.cos(self.yaw/2);self.tf.sendTransform(tf)
        odom=Odometry();odom.header=tf.header;odom.child_frame_id='base_link';odom.pose.pose.position.x=self.x;odom.pose.pose.position.y=self.y;odom.pose.pose.orientation=tf.transform.rotation;odom.twist.twist=v;self.odom_pub.publish(odom)
        self.count+=1
        if self.count%2==0:
            scan=LaserScan();scan.header.frame_id='base_link';scan.header.stamp=stamp;scan.angle_min=-math.pi;scan.angle_max=math.pi-math.pi/180;scan.angle_increment=math.pi/180;scan.range_min=.12;scan.range_max=12.;scan.ranges=[]
            for i in range(360):
                a=self.yaw-math.pi+i*math.pi/180;c=math.cos(a);s=math.sin(a)
                tx=((3.9 if c>0 else -3.9)-self.x)/c if abs(c)>1e-8 else 100.
                ty=((3.9 if s>0 else -3.9)-self.y)/s if abs(s)>1e-8 else 100.
                scan.ranges.append(float(min(tx,ty)))
            self.scan_pub.publish(scan)
        if self.count%20==1:
            grid=OccupancyGrid();grid.header.frame_id='map';grid.header.stamp=stamp;grid.info.width=grid.info.height=160;grid.info.resolution=.05;grid.info.origin.position.x=grid.info.origin.position.y=-4.;grid.info.origin.orientation.w=1.;grid.data=[0]*25600
            for i in range(160):grid.data[i]=grid.data[159*160+i]=grid.data[i*160]=grid.data[i*160+159]=100
            self.map_pub.publish(grid)


def main():
    with tempfile.TemporaryDirectory() as folder:
        log=open(Path(folder)/'nav.log','w+')
        child=subprocess.Popen(['ros2','launch','nav2_bringup','navigation_launch.py','params_file:=/data/nav2.yaml','use_sim_time:=false','autostart:=true','use_composition:=False'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        node=None
        try:
            rclpy.init();node=World();action=ActionClient(node,NavigateToPose,'navigate_to_pose');ready=node.create_client(GetState,'/collision_monitor/get_state');bt=node.create_client(GetState,'/bt_navigator/get_state');deadline=time.monotonic()+45
            while time.monotonic()<deadline:
                rclpy.spin_once(node,timeout_sec=.03)
                if action.server_is_ready() and ready.service_is_ready() and bt.service_is_ready():
                    f=ready.call_async(GetState.Request());rclpy.spin_until_future_complete(node,f,timeout_sec=1.)
                    if f.done() and f.result().current_state.id==3:
                        b=bt.call_async(GetState.Request());rclpy.spin_until_future_complete(node,b,timeout_sec=1.)
                        if b.done() and b.result().current_state.id==3:break
            else:raise RuntimeError('Nav2 startup timeout')
            goal=NavigateToPose.Goal();goal.pose.header.frame_id='map';goal.pose.header.stamp=node.get_clock().now().to_msg();goal.pose.pose.position.x=.35;goal.pose.pose.orientation.z=math.sin(.5);goal.pose.pose.orientation.w=math.cos(.5)
            f=action.send_goal_async(goal);rclpy.spin_until_future_complete(node,f,timeout_sec=5);handle=f.result();assert handle.accepted
            result=handle.get_result_async();deadline=time.monotonic()+45
            while not result.done() and time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.03)
            status=result.result().status if result.done() else None
            data=dict(status=status,x=node.x,y=node.y,yaw=node.yaw,nonzero_commands=node.moves);print(json.dumps(data),flush=True)
            assert status==4 and math.hypot(node.x-.35,node.y)<.12 and abs(node.yaw-1.)<.15 and node.moves>5,data
        except Exception:
            log.flush();log.seek(0);print(log.read()[-10000:]);raise
        finally:
            if node:node.destroy_node();rclpy.shutdown()
            os.killpg(child.pid,signal.SIGINT)
            try:child.wait(timeout=12)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            log.close()


if __name__=='__main__':main()
