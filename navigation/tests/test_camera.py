import io
import sys
import time
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]))
from camera_service import Frames
from api import create_app


class FakeCamera:
    def frame(self):return b'\xff\xd8test\xff\xd9',42,12
    def status(self):return dict(ready=True,sequence=42)


class CameraTests(unittest.TestCase):
    def test_buffer_returns_only_fresh_frames(self):
        frames=Frames();frames.write(b'frame')
        image,sequence,age=frames.get_frame(timeout=.01)
        self.assertEqual(image,b'frame');self.assertEqual(sequence,1);self.assertLess(age,100)
        frames.at=time.monotonic()-2
        with self.assertRaises(TimeoutError):frames.get_frame(timeout=.01)
    def test_same_origin_frame_headers(self):
        client=create_app(object(),camera=FakeCamera()).test_client()
        response=client.get('/api/camera/frame.jpg')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.mimetype,'image/jpeg')
        self.assertEqual(response.headers['X-Frame-Sequence'],'42')
        self.assertIn('no-store',response.headers['Cache-Control'])
    def test_camera_failure_returns_unavailable_not_a_stale_image(self):
        class Broken:
            def frame(self):raise OSError('offline')
        response=create_app(object(),camera=Broken()).test_client().get('/api/camera/frame.jpg')
        self.assertEqual(response.status_code,503)


if __name__=='__main__':unittest.main()
