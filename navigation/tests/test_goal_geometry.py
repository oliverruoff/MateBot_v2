import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]))
from goal_geometry import arrival_error


class GoalGeometryTests(unittest.TestCase):
    def setUp(self):
        self.cfg=dict(footprint_length=.41,footprint_width=.3,obstacle_margin=.04)
        self.grid=dict(width=40,height=40,resolution=.05,origin=[-1,-1,0],cells=[0]*1600)
    def test_known_free_footprint_accepts_any_heading(self):
        for yaw in (0.,.4,1.7):self.assertEqual(arrival_error(self.grid,0,0,yaw,self.cfg),'')
    def test_heading_changes_fit_even_when_target_center_is_free(self):
        obstacle=[(.23,0)]
        self.assertIn('Hindernis',arrival_error(self.grid,0,0,0,self.cfg,obstacle))
        self.assertEqual(arrival_error(self.grid,0,0,math.pi/2,self.cfg,obstacle),'')
    def test_unknown_under_robot_and_map_edge_are_rejected(self):
        self.grid['cells'][20*40+20]=-1
        self.assertIn('unbekannte',arrival_error(self.grid,0,0,0,self.cfg))
        self.assertIn('Kartenrand',arrival_error(self.grid,.9,0,0,self.cfg))
    def test_arrival_tolerance_is_included_in_clearance(self):
        self.assertEqual(arrival_error(self.grid,0,0,0,self.cfg,[(.28,0)]),'')
        self.assertIn('Hindernis',arrival_error(self.grid,0,0,0,{**self.cfg,'goal_position_tolerance':.06},[(.28,0)]))
    def test_rotated_map_origin_is_supported(self):
        self.grid['origin']=[0,0,math.pi/2]
        self.assertEqual(arrival_error(self.grid,-1,1,.7,self.cfg),'')


if __name__=='__main__':unittest.main()
