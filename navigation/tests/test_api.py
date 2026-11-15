from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]))
from api import create_app


class FakeRobot:
    def __init__(self):self.calls=[]
    def state(self):return {'estop':True,'control_active':False}
    def arm(self,mode,on_site):
        if on_site is not True:raise ValueError('Aufsicht fehlt')
        self.calls.append(('arm',mode))
        return {'token':'test-lease'}
    def heartbeat(self,token):
        if token!='test-lease':raise ValueError('Steuerung abgelaufen')
    def manual(self,token,*values,sequence=None):
        if token!='test-lease':raise ValueError('Steuerung abgelaufen')
        self.calls.append(('manual',values))
    def stop(self):self.calls.append(('stop',))


class APITests(unittest.TestCase):
    def setUp(self):
        self.robot=FakeRobot()
        self.client=create_app(self.robot).test_client()
        self.headers={'X-Matebot-Control':'1'}

    def test_cross_origin_form_cannot_move_or_arm(self):
        response=self.client.post('/api/manual',json={'vx':.01,'vy':0,'wz':0})
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.robot.calls,[])

    def test_release_does_not_assume_operator_presence(self):
        r=self.client.post('/api/release',json={'mode':'mapping'},headers=self.headers)
        self.assertEqual(r.status_code,409)
        self.assertEqual(self.robot.calls,[])

    def test_lease_required_and_nan_rejected_before_command(self):
        for value in [float('nan'),float('inf'),10000]:
            r=self.client.post('/api/manual',json={'vx':value,'vy':0,'wz':0},headers=self.headers)
            self.assertEqual(r.status_code,409)
        r=self.client.post('/api/manual',json={'vx':.01,'vy':0,'wz':0},headers=self.headers)
        self.assertEqual(r.status_code,409)
        self.assertEqual(self.robot.calls,[])

    def test_stop_remains_available_without_owning_motion_lease(self):
        r=self.client.post('/api/stop',json={},headers=self.headers)
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.robot.calls,[('stop',)])


if __name__=='__main__':unittest.main()
