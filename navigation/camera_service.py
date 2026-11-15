"""Host-side CSI camera. Binds loopback only; frames stay in RAM, on demand."""
import io
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import signal
import threading
import time
import yaml


class Frames(io.BufferedIOBase):
    def __init__(self):
        self.condition=threading.Condition()
        self.frame=None
        self.sequence=0
        self.at=0.
        self.demand_at=0.
        self.active=False
        self.error='Kamera startet'

    def write(self,data):
        with self.condition:
            self.frame=bytes(data)
            self.at=time.monotonic()
            self.sequence+=1
            self.error=''
            self.condition.notify_all()
        return len(data)

    def get_frame(self,timeout=1.8):
        deadline=time.monotonic()+timeout
        with self.condition:
            self.demand_at=time.monotonic()
            self.condition.notify_all()
            while time.monotonic()<deadline:
                if self.frame and time.monotonic()-self.at<.7:
                    return self.frame,self.sequence,(time.monotonic()-self.at)*1000
                self.condition.wait(min(.2,max(0.,deadline-time.monotonic())))
            raise TimeoutError(self.error or 'Kein frisches Kamerabild')

    def status(self):
        with self.condition:
            age=time.monotonic()-self.at if self.at else None
            return dict(active=self.active,ready=age is not None and age<.7,
                        age_ms=round(age*1000) if age is not None else None,
                        sequence=self.sequence,error=self.error)


def camera_worker(frames,cfg,stopping):
    while not stopping.is_set():
        with frames.condition:
            if time.monotonic()-frames.demand_at>4:
                frames.condition.wait(.5)
                continue
        camera=None
        try:
            from picamera2 import Picamera2
            from picamera2.encoders import MJPEGEncoder
            from picamera2.outputs import FileOutput
            from libcamera import Transform
            rotation=cfg.get('camera_rotation',180)
            if rotation not in (0,180):raise ValueError('Only 0/180 degree rotation supported')
            camera=Picamera2()
            config=camera.create_video_configuration(
                main={'size':(640,360)},controls={'FrameRate':12},buffer_count=3,
                transform=Transform(hflip=rotation==180,vflip=rotation==180))
            camera.configure(config)
            camera.start_recording(MJPEGEncoder(bitrate=1800000),FileOutput(frames))
            with frames.condition:frames.active=True
            while not stopping.wait(.25):
                if time.monotonic()-frames.demand_at>4:break
        except Exception as exc:
            with frames.condition:
                frames.error='Kamera nicht verfügbar: '+str(exc)
                frames.condition.notify_all()
            print(frames.error,flush=True)
            stopping.wait(1.5)
        finally:
            if camera:
                try:camera.stop_recording()
                except Exception:pass
                try:camera.close()
                except Exception:pass
            with frames.condition:
                frames.active=False
                frames.frame=None


def handler_for(frames,cfg):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def send_json(self,code,value):
            data=json.dumps(value).encode('utf-8')
            self.send_response(code);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers()
            self.wfile.write(data)
        def do_GET(self):
            try:
                if self.path=='/health':
                    self.send_json(200,{**frames.status(),'width':640,'height':360,
                        'rotation':cfg.get('camera_rotation',180),'target_fps':12})
                elif self.path=='/frame.jpg':
                    try:frame,sequence,age=frames.get_frame()
                    except TimeoutError as exc:self.send_json(503,{'error':str(exc)});return
                    self.send_response(200);self.send_header('Content-Type','image/jpeg')
                    self.send_header('Content-Length',str(len(frame)))
                    self.send_header('Cache-Control','no-store, max-age=0')
                    self.send_header('X-Frame-Sequence',str(sequence))
                    self.send_header('X-Frame-Age-Ms',str(round(age)))
                    self.end_headers();self.wfile.write(frame)
                else:self.send_json(404,{'error':'Not found'})
            except (BrokenPipeError,ConnectionResetError):pass
    return Handler


if __name__=='__main__':
    cfg=yaml.safe_load((Path(__file__).parent/'config/robot.yaml').read_text())
    frames=Frames();stopping=threading.Event()
    threading.Thread(target=camera_worker,args=(frames,cfg,stopping),daemon=True).start()
    server=ThreadingHTTPServer(('127.0.0.1',8082),handler_for(frames,cfg))
    server.daemon_threads=True
    def stop(*_):
        stopping.set()
        threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:server.serve_forever(poll_interval=.2)
    finally:stopping.set();server.server_close()
