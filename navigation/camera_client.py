"""Same-origin proxy to the host camera service. No user-controlled URLs."""
import json
import math
import urllib.request


class CameraClient:
    def __init__(self):self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def frame(self):
        with self.opener.open('http://127.0.0.1:8082/frame.jpg',timeout=2.5) as response:
            data=response.read(2*1024*1024+1)
            sequence=int(response.headers['X-Frame-Sequence'])
            age=float(response.headers['X-Frame-Age-Ms'])
            if len(data)>2*1024*1024 or not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
                raise ValueError('Ungültiges Kamerabild')
            if not math.isfinite(age) or not 0<=age<700:raise ValueError('Kamerabild ist veraltet')
            return data,sequence,age
    def status(self):
        with self.opener.open('http://127.0.0.1:8082/health',timeout=1) as response:
            return json.loads(response.read(8192))
