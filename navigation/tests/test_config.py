from pathlib import Path
import math
import json
import sys
import tempfile
import unittest
import yaml
sys.path.insert(0,str(Path(__file__).parents[1]))
from configure import generate, ROOT


class ConfigurationTests(unittest.TestCase):
    def test_navigation_keeps_unknown_space_blocked_and_chassis_inside_footprint(self):
        with tempfile.TemporaryDirectory() as directory:
            generate(Path(directory))
            nav=yaml.safe_load((Path(directory)/'nav2.yaml').read_text())
            cfg=yaml.safe_load((ROOT/'config/robot.yaml').read_text())
            slam=yaml.safe_load((Path(directory)/'slam.yaml').read_text())
            self.assertTrue(slam['slam_toolbox']['ros__parameters']['restamp_tf'])
            self.assertFalse(cfg['motion_verified'])
            self.assertFalse(nav['planner_server']['ros__parameters']['GridBased']['allow_unknown'])
            chassis=math.hypot(cfg['footprint_width'],cfg['footprint_length'])/2
            for name in ['global_costmap','local_costmap']:
                p=nav[name][name]['ros__parameters']
                self.assertGreater(p['robot_radius'],chassis)
                padding=cfg.get('self_filter_padding',0.)
                self.assertGreaterEqual(p['robot_radius'],math.hypot(cfg['footprint_length']/2+padding,cfg['footprint_width']/2+padding))
                self.assertGreater(p['inflation_layer']['inflation_radius'],p['robot_radius'])
            controller=nav['controller_server']['ros__parameters']['FollowPath']
            local=nav['local_costmap']['local_costmap']['ros__parameters']
            footprint=json.loads(local['footprint'])
            self.assertGreaterEqual(max(abs(p[0]) for p in footprint),cfg['footprint_length']/2+padding)
            self.assertGreaterEqual(max(abs(p[1]) for p in footprint),cfg['footprint_width']/2+padding)
            self.assertIn('ObstacleFootprint',controller['critics'])
            self.assertEqual(controller['xy_goal_tolerance'],cfg['goal_position_tolerance'])
            self.assertIn('static_layer',nav['local_costmap']['local_costmap']['ros__parameters']['plugins'])
            self.assertGreater(controller['max_vel_y'],0)
            self.assertLess(controller['min_vel_y'],0)
            self.assertEqual(nav['collision_monitor']['ros__parameters']['cmd_vel_out_topic'],'cmd_vel')
            scan=nav['collision_monitor']['ros__parameters']['scan']
            self.assertLessEqual(scan['min_height'],cfg['lidar_z'])
            self.assertGreaterEqual(scan['max_height'],cfg['lidar_z'])


if __name__=='__main__':unittest.main()
