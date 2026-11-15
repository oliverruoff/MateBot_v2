"""Actual Nav2 planner, synthetic map, isolated ROS domain. NO motor controller."""
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import yaml
sys.path.insert(0,str(Path(__file__).parents[1]))
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile,DurabilityPolicy,ReliabilityPolicy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import OccupancyGrid
from nav2_msgs.action import ComputePathToPose
from lifecycle_msgs.srv import ChangeState
from tf2_ros import StaticTransformBroadcaster
from spatial import overlay_indices

assert os.environ.get('ROS_DOMAIN_ID') not in (None,'42'), 'Use isolated ROS_DOMAIN_ID, never robot domain'


def wait(node,future,timeout=15):
    rclpy.spin_until_future_complete(node,future,timeout_sec=timeout)
    if not future.done():raise RuntimeError('ROS test timed out')
    return future.result()


def main():
    root=Path(__file__).parents[1]
    cfg=yaml.safe_load((root/'config/robot.yaml').read_text())
    radius=math.hypot(cfg['footprint_length'],cfg['footprint_width'])/2+.05
    params=dict(planner_server={'ros__parameters':dict(planner_plugins=['GridBased'],
        expected_planner_frequency=1.,GridBased=dict(plugin='nav2_navfn_planner::NavfnPlanner',
        tolerance=.1,use_astar=True,allow_unknown=False))},
        global_costmap={'global_costmap':{'ros__parameters':dict(global_frame='map',robot_base_frame='base_link',
            update_frequency=5.,publish_frequency=1.,resolution=.1,robot_radius=radius,
            track_unknown_space=True,plugins=['static_layer','inflation_layer'],
            static_layer=dict(plugin='nav2_costmap_2d::StaticLayer',map_subscribe_transient_local=True),
            inflation_layer=dict(plugin='nav2_costmap_2d::InflationLayer',inflation_radius=radius+.15,cost_scaling_factor=3.))}})
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'planner.yaml';path.write_text(yaml.safe_dump(params))
        log=open(Path(folder)/'planner.log','w+')
        child=subprocess.Popen(['ros2','run','nav2_planner','planner_server','--ros-args',
                               '--params-file',str(path)],stdout=log,stderr=subprocess.STDOUT)
        node=None
        try:
            rclpy.init();node=Node('isolated_planner_test')
            qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL,reliability=ReliabilityPolicy.RELIABLE)
            pub=node.create_publisher(OccupancyGrid,'map',qos)
            tf=StaticTransformBroadcaster(node)
            transform=TransformStamped();transform.header.frame_id='map';transform.child_frame_id='base_link'
            transform.header.stamp=node.get_clock().now().to_msg();transform.transform.rotation.w=1.;tf.sendTransform(transform)
            grid=OccupancyGrid();grid.header.frame_id='map';grid.info.width=grid.info.height=80;grid.info.resolution=.1
            grid.info.origin.position.x=grid.info.origin.position.y=-4.;grid.info.origin.orientation.w=1.;grid.data=[0]*6400
            for row in range(80):
                for col in range(80):
                    if row in (0,79) or col in (0,79) or (col==48 and not 54<=row<66):grid.data[row*80+col]=100
            def publish():grid.header.stamp=node.get_clock().now().to_msg();pub.publish(grid)
            node.create_timer(.3,publish);publish()
            lifecycle=node.create_client(ChangeState,'/planner_server/change_state')
            if not lifecycle.wait_for_service(timeout_sec=20):raise RuntimeError('Planner not available')
            for transition in (1,3):
                request=ChangeState.Request();request.transition.id=transition
                if not wait(node,lifecycle.call_async(request),20).success:raise RuntimeError('Planner lifecycle failed')
            client=ActionClient(node,ComputePathToPose,'compute_path_to_pose')
            if not client.wait_for_server(timeout_sec=10):raise RuntimeError('Planner action unavailable')
            def plan():
                goal=ComputePathToPose.Goal();goal.planner_id='GridBased';goal.use_start=True
                goal.start.header.frame_id=goal.goal.header.frame_id='map'
                goal.start.pose.orientation.w=goal.goal.pose.orientation.w=1.
                goal.goal.pose.position.x=2.5
                handle=wait(node,client.send_goal_async(goal))
                if not handle.accepted:raise RuntimeError('Plan request rejected')
                return wait(node,handle.get_result_async(),15)
            deadline=time.monotonic()+1.5
            while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.1)
            result=plan();points=result.result.path.poses
            assert result.status==4 and points,'No path around wall'
            assert max(p.pose.position.y for p in points)>1.4,'Path did not route through doorway'
            baseline_count=len(points)
            zones={(x,y) for x in (2,3,4) for y in range(5,11)}
            for index in overlay_indices(80,80,.1,[-4.,-4.,0.],zones,.25):grid.data[index]=100
            publish();deadline=time.monotonic()+2.
            while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.1)
            blocked=plan()
            assert blocked.status!=4 and not blocked.result.path.poses,'No-go zone was crossed'
            print(json.dumps(dict(path_around_wall=True,path_points=baseline_count,
                                  max_y=max(p.pose.position.y for p in points),
                                  no_go_closes_doorway=True,motor_controller_started=False)),flush=True)
        except Exception:
            log.flush();log.seek(0);print(log.read()[-14000:],flush=True);raise
        finally:
            child.terminate()
            try:child.wait(timeout=8)
            except subprocess.TimeoutExpired:child.kill();child.wait()
            if node:node.destroy_node()
            if rclpy.ok():rclpy.shutdown()
            log.close()


if __name__=='__main__':main()
