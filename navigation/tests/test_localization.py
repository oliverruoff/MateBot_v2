from pathlib import Path
import math
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[1]))
from localization import ScanMatcher,angle_delta


def fixture(asymmetric=True):
    cells=np.zeros((100,140),dtype=int)
    cells[[0,-1],:]=100;cells[:,[0,-1]]=100
    if asymmetric:
        cells[38:72,80:82]=100;cells[70:72,80:112]=100
    grid=dict(width=140,height=100,resolution=.05,origin=[-1.,-2.,.23],cells=cells.ravel().tolist())
    return grid,cells


def scan(grid,cells,position):
    # Independently ray-cast a 360-degree synthetic scan in local grid coordinates.
    x,y,heading=position;points=[]
    for angle in np.linspace(-math.pi,math.pi,360,endpoint=False):
        for distance in np.arange(.1,10,.015):
            px=x+distance*math.cos(angle+heading);py=y+distance*math.sin(angle+heading)
            ix=int(px/.05);iy=int(py/.05)
            if not (0<=ix<140 and 0<=iy<100):break
            if cells[iy,ix]>=65:
                points.append([distance*math.cos(angle),distance*math.sin(angle)]);break
    return points


class LocalizationTests(unittest.TestCase):
    def test_finds_moved_rotated_robot_without_using_saved_pose(self):
        grid,cells=fixture();position=(1.4,2.1,.72)
        match=ScanMatcher(grid).match(scan(grid,cells,position),dict(x=4,y=-1,yaw=-2))
        self.assertIsNotNone(match)
        a=grid['origin'][2];x,y,h=position
        self.assertAlmostEqual(match['x'],grid['origin'][0]+x*math.cos(a)-y*math.sin(a),delta=.12)
        self.assertAlmostEqual(match['y'],grid['origin'][1]+x*math.sin(a)+y*math.cos(a),delta=.12)
        self.assertLess(abs(angle_delta(match['yaw'],h+a)),.06)
    def test_ambiguous_rectangle_is_not_accepted_as_certain(self):
        grid,cells=fixture(False)
        self.assertIsNone(ScanMatcher(grid).match(scan(grid,cells,(2.,2.,.4))))
    def test_no_match_for_missing_or_unrelated_scan(self):
        grid,_=fixture();matcher=ScanMatcher(grid)
        self.assertIsNone(matcher.match([]))
        self.assertIsNone(matcher.match([[.1,.1]]*200))


if __name__=='__main__':unittest.main()
