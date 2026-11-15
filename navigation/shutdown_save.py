"""PID 1 invokes this BEFORE stopping ROS, so serialization still has a server."""
import json
import os
import time
import urllib.error
import urllib.request

base='http://127.0.0.1:'+os.environ.get('MATEBOT_PORT','8080')+'/api/'
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(action):
    request=urllib.request.Request(base+action,data=b'{}',headers={
        'Content-Type':'application/json','X-Matebot-Control':'1'})
    with opener.open(request,timeout=8) as response:return json.load(response)


try:
    post('stop')
    deadline=time.monotonic()+12
    while time.monotonic()<deadline:
        try:
            print('Shutdown snapshot:',post('save'),flush=True)
            break
        except urllib.error.HTTPError as exc:
            message=exc.read().decode()
            if 'bereits' not in message:
                print('Shutdown snapshot skipped:',message,flush=True)
                break
            time.sleep(.3)
except Exception as exc:
    print('Shutdown snapshot unavailable; last complete snapshot retained:',exc,flush=True)
