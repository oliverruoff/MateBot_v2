import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]))
from session import Session,ControlLease
from spatial import overlay_indices,zone_collision,sweep_hits_zones,obstacle_risk,laser_to_base,self_return


class DurableRasterTests(unittest.TestCase):
    def test_restart_negative_cells_and_revision_conflict(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Session(folder)
            old=store.get()
            doc=store.edit_zones([[-2,3],[0,0]],[],.25,old['revision'])
            loaded=Session(folder).get()
            self.assertEqual(loaded,doc)
            with self.assertRaises(ValueError):store.edit_zones([],[[0,0]],.25,old['revision'])
            self.assertEqual(len(store.get()['zones']),2)

    def test_resize_is_conservative_and_does_not_erase_existing_zone(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Session(folder)
            d=store.edit_zones([[-1,-1],[2,3]],[],.25,0)
            d=store.edit_zones([],[],.1,d['revision'])
            cells={tuple(c) for c in d['zones']}
            self.assertTrue(zone_collision(-.24,-.24,0,cells,.1))
            self.assertTrue(zone_collision(.74,.99,0,cells,.1))
            self.assertFalse(zone_collision(2,2,0,cells,.1))

    def test_corruption_fails_closed_instead_of_removing_zones(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Session(folder)
            store.edit_zones([[4,5]],[],.25,0)
            (Path(folder)/'session.json').write_text('{broken')
            with self.assertRaises(ValueError):Session(folder)

    def test_favorites_settings_and_old_map_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            s=Session(folder)
            s.favorite('Küche',1.,-2.)
            s.settings(calibration=dict(translation=True,lateral=False,rotation=False,stopping=False))
            old=s.get()
            new=s.new_map()
            self.assertNotEqual(old['map_id'],new['map_id'])
            self.assertEqual(new['favorites'],[])
            self.assertTrue(new['calibration']['translation'])
            archived=json.loads(next((Path(folder)/'archives').glob('session-*')).read_text(encoding='utf-8'))
            self.assertEqual(archived,old)

    def test_overlay_stays_at_same_world_location_when_map_origin_grows(self):
        zones={(2,-1)}
        for origin in [(0.,-1.,0.),(-2.,-3.,0.),(2.,-3.,math.pi/2)]:
            indices=overlay_indices(100,100,.05,origin,zones,.25)
            self.assertTrue(indices)
            for i in indices:
                row,col=divmod(i,100)
                a=origin[2]
                x=origin[0]+(col+.5)*.05*math.cos(a)-(row+.5)*.05*math.sin(a)
                y=origin[1]+(col+.5)*.05*math.sin(a)+(row+.5)*.05*math.cos(a)
                self.assertTrue(.46<=x<=.79 and -.29<=y<=.04)

    def test_robot_radius_and_future_sweep_respect_zone(self):
        cfg=dict(footprint_length=.41,footprint_width=.30)
        zones={(2,0)}
        self.assertFalse(zone_collision(0,0,.29,zones,.25))
        self.assertTrue(zone_collision(.3,0,.29,zones,.25))
        self.assertTrue(sweep_hits_zones(dict(x=.2,y=.1,yaw=0.,age=0),[.1,0,0],cfg,zones,.25))
        self.assertTrue(sweep_hits_zones(None,[0,0,0],cfg,zones,.25))

    def test_obstacle_allows_retreat_and_self_returns_do_not_clear_free_space(self):
        cfg=dict(footprint_length=.41,footprint_width=.30,lidar_yaw=-math.pi/2,lidar_x=0.,lidar_y=0.)
        self.assertTrue(obstacle_risk([(.25,0.)],cfg,[.03,0,0]))
        self.assertFalse(obstacle_risk([(.25,0.)],cfg,[-.03,0,0]))
        self.assertTrue(self_return(.1,.1,cfg))
        self.assertFalse(self_return(.4,0.,cfg))
        self.assertTrue(self_return(.231,-.016,{**cfg,'self_filter_padding':.03}))
        x,y=laser_to_base(0.,.5,cfg)
        self.assertAlmostEqual(x,.5)
        self.assertAlmostEqual(y,0.)


class LeaseTests(unittest.TestCase):
    def test_reader_and_other_browser_cannot_keep_motion_alive(self):
        lease=ControlLease()
        token=lease.acquire(10.)
        with self.assertRaises(ValueError):lease.check('wrong',10.5,refresh=True)
        self.assertEqual(lease.at,10.)
        with self.assertRaises(ValueError):lease.acquire(10.8)
        lease.check(token,10.8,refresh=True)
        lease.check(token,11.8)
        with self.assertRaises(ValueError):lease.check(token,13.4)
        new=lease.acquire(13.5)
        self.assertNotEqual(new,token)
        lease.clear()
        with self.assertRaises(ValueError):lease.check(new,13.6)


if __name__=='__main__':unittest.main()
