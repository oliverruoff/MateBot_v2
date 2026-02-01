import io
import time
import cv2
import numpy as np
from picamera2 import Picamera2
from libcamera import Transform

class Camera:
    def __init__(self):
        self.picam2 = None
        self.placeholder = self._create_placeholder()
        
        try:
            print("INFO: Initialisiere Picamera2 mit 180° Rotation...")
            self.picam2 = Picamera2()
            
            # Rotation um 180 Grad mittels Transform
            config = self.picam2.create_video_configuration(
                main={"size": (640, 480), "format": "RGB888"},
                transform=Transform(hflip=True, vflip=True)
            )
            self.picam2.configure(config)
            
            # Kamera starten
            self.picam2.start()
            
            # Kurz warten (Warmup)
            time.sleep(2)
            print("INFO: Picamera2 erfolgreich gestartet.")
            
        except Exception as e:
            print(f"WARNUNG: Picamera2 konnte nicht initialisiert werden: {e}")
            import traceback
            traceback.print_exc()
            self.picam2 = None

    def __del__(self):
        if self.picam2:
            try:
                self.picam2.stop()
            except:
                pass

    def get_frame(self):
        if not self.picam2:
            return self.placeholder

        try:
            # Bild direkt als JPEG holen
            stream = io.BytesIO()
            self.picam2.capture_file(stream, format="jpeg")
            return stream.getvalue()
            
        except Exception as e:
            print(f"FEHLER: Frame konnte nicht gelesen werden: {e}")
            return self.placeholder

    def _create_placeholder(self):
        try:
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            text = "NO SIGNAL"
            font = cv2.FONT_HERSHEY_SIMPLEX
            text_size = cv2.getTextSize(text, font, 2, 3)[0]
            text_x = (img.shape[1] - text_size[0]) // 2
            text_y = (img.shape[0] + text_size[1]) // 2
            cv2.putText(img, text, (text_x, text_y), font, 2, (255, 255, 255), 3)
            ret, jpeg = cv2.imencode('.jpg', img)
            return jpeg.tobytes()
        except:
            return b''
