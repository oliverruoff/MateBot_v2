"""Derive upstream ROS configs from a single measured robot geometry."""
import math
from pathlib import Path
import yaml

ROOT = Path(__file__).parent


def generate(output_dir=Path('/data')):
    cfg = yaml.safe_load((ROOT / 'config/robot.yaml').read_text())
    nav = yaml.safe_load((ROOT / 'config/nav2.upstream.yaml').read_text())
    for section in nav.values():
        if 'ros__parameters' in section:
            section['ros__parameters']['enable_stamped_cmd_vel'] = False
    radius = math.hypot(cfg['footprint_length'], cfg['footprint_width']) / 2
    # Circumscribed circle is deliberately conservative, including during rotation.
    for key in ('local_costmap', 'global_costmap'):
        p = nav[key][key]['ros__parameters']
        p['robot_radius'] = radius + 0.05
        p['inflation_layer']['inflation_radius'] = radius + 0.30
        layer = p.get('voxel_layer', p.get('obstacle_layer'))
        layer['scan'].update(raytrace_max_range=10.0, obstacle_max_range=8.0,
                             expected_update_rate=0.3, inf_is_valid=False)
    nav['local_costmap']['local_costmap']['ros__parameters'].update(width=5, height=5)
    nav['local_costmap']['local_costmap']['ros__parameters']['plugins']=['static_layer','voxel_layer','inflation_layer']
    p = nav['controller_server']['ros__parameters']
    p.update(controller_frequency=10.0, min_y_velocity_threshold=0.001)
    p['progress_checker'].update(required_movement_radius=0.10, movement_time_allowance=20.0)
    p['general_goal_checker'].update(xy_goal_tolerance=0.15, yaw_goal_tolerance=0.25)
    p['FollowPath'] = {
        'plugin': 'dwb_core::DWBLocalPlanner', 'debug_trajectory_details': False,
        'min_vel_x': -0.06, 'max_vel_x': 0.08, 'min_vel_y': -0.06, 'max_vel_y': 0.06,
        'max_vel_theta': 0.18, 'min_speed_xy': 0.0, 'max_speed_xy': 0.08,
        'min_speed_theta': 0.0, 'acc_lim_x': 0.12, 'acc_lim_y': 0.12,
        'acc_lim_theta': 0.25, 'decel_lim_x': -0.15, 'decel_lim_y': -0.15,
        'decel_lim_theta': -0.3, 'vx_samples': 7, 'vy_samples': 7, 'vtheta_samples': 12,
        'sim_time': 2.0, 'linear_granularity': 0.025, 'angular_granularity': 0.025,
        'transform_tolerance': 0.3, 'xy_goal_tolerance': 0.15,
        'trans_stopped_velocity': 0.015, 'short_circuit_trajectory_evaluation': True,
        'stateful': True, 'critics': ['RotateToGoal', 'Oscillation', 'BaseObstacle',
                                     'GoalAlign', 'PathAlign', 'PathDist', 'GoalDist'],
        'BaseObstacle.scale': 0.05, 'PathAlign.scale': 24.0, 'PathAlign.forward_point_distance': 0.1,
        'GoalAlign.scale': 18.0, 'GoalAlign.forward_point_distance': 0.1,
        'PathDist.scale': 24.0, 'GoalDist.scale': 18.0, 'RotateToGoal.scale': 24.0,
        'RotateToGoal.slowing_factor': 5.0, 'RotateToGoal.lookahead_time': -1.0,
    }
    nav['planner_server']['ros__parameters']['GridBased'].update(allow_unknown=False, tolerance=0.15)
    p = nav['velocity_smoother']['ros__parameters']
    p.update(max_velocity=[0.08, 0.06, 0.18], min_velocity=[-0.06, -0.06, -0.18],
             max_accel=[0.12, 0.12, 0.25], max_decel=[-0.15, -0.15, -0.3], velocity_timeout=0.3)
    p = nav['behavior_server']['ros__parameters']
    p.update(max_rotational_vel=0.18, min_rotational_vel=0.05, rotational_acc_lim=0.25)
    nav['collision_monitor']['ros__parameters'].update(base_frame_id='base_link', source_timeout=0.4)
    # Include low-mounted lidar: Matebot's scan plane is only 14 cm above ground.
    nav['collision_monitor']['ros__parameters']['scan'].update(min_height=0.0, max_height=2.0)
    slam = yaml.safe_load((ROOT / 'config/slam.upstream.yaml').read_text())
    slam['slam_toolbox']['ros__parameters'].update(
        base_frame='base_link', map_update_interval=2.0, max_laser_range=12.0,
        min_laser_range=0.12, minimum_travel_distance=0.08,
        minimum_travel_heading=0.08, minimum_time_interval=0.2,
        transform_timeout=0.5, enable_interactive_mode=False)
    for name, value in [('nav2', nav), ('slam', slam)]:
        (output_dir / (name + '.yaml')).write_text(yaml.safe_dump(value))


if __name__ == '__main__':
    generate()
