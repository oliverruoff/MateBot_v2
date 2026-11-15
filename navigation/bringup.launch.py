from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, ExecuteProcess, RegisterEventHandler, EmitEvent, GroupAction
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node, SetRemap
from ament_index_python.packages import get_package_share_directory
import yaml


def generate_launch_description():
    cfg = yaml.safe_load(open('/app/config/robot.yaml'))
    bridge = ExecuteProcess(cmd=['python3', '/app/bridge.py'], output='screen')
    return LaunchDescription([
        RegisterEventHandler(OnProcessExit(target_action=bridge,
            on_exit=[EmitEvent(event=Shutdown(reason='Robot bridge exited'))])),
        Node(package='tf2_ros', executable='static_transform_publisher', arguments=[
            '--x', str(cfg['lidar_x']), '--y', str(cfg['lidar_y']), '--z', str(cfg['lidar_z']),
            '--yaw', str(cfg['lidar_yaw']), '--frame-id', 'base_link', '--child-frame-id', 'laser']),
        GroupAction([SetRemap(src='/map',dst='/slam_map'), IncludeLaunchDescription(PythonLaunchDescriptionSource(
            get_package_share_directory('slam_toolbox') + '/launch/online_async_launch.py'),
            launch_arguments={'slam_params_file': '/data/slam.yaml',
                              'use_sim_time': 'false', 'autostart': 'true'}.items())]),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(
            get_package_share_directory('nav2_bringup') + '/launch/navigation_launch.py'),
            launch_arguments={'params_file': '/data/nav2.yaml', 'use_sim_time': 'false',
                              'autostart': 'true', 'use_composition': 'False'}.items()),
        # Launch a plain Python ROS node without a separate colcon build.
        bridge,
    ])
