import cv2
import numpy as np
import io
import threading
from picamera2 import Picamera2
from picamera2.encoders import MjpegEncoder
from picamera2.outputs import FileOutput

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

class Camera:
    def __init__(self):
        self.picam2 = None
        self.placeholder = self._create_placeholder()
        self.output = StreamingOutput()
        try:
            self.picam2 = Picamera2()
            config = self.picam2.create_video_configuration(main={"size": (640, 480)})
            self.picam2.configure(config)
            self.picam2.start_recording(MjpegEncoder(), FileOutput(self.output))
            print("INFO: Picamera2 initialisiert und Aufnahme gestartet.")
        except Exception as e:
            print(f"WARNUNG: Picamera2 konnte nicht initialisiert werden: {e}")
            self.picam2 = None

    def __del__(self):
        if self.picam2:
            self.picam2.stop_recording()

    def get_frame(self):
        if not self.picam2:
            return self.placeholder

        try:
            with self.output.condition:
                self.output.condition.wait()
                frame = self.output.frame
            return frame
        except Exception as e:
            print(f"FEHLER: Frame konnte nicht gelesen werden: {e}")
            return self.placeholder

    def _create_placeholder(self):
        # Schwarzes Bild erstellen
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Text hinzufügen
        text = "NO SIGNAL"
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(text, font, 2, 3)[0]
        text_x = (img.shape[1] - text_size[0]) // 2
        text_y = (img.shape[0] + text_size[1]) // 2
        cv2.putText(img, text, (text_x, text_y), font, 2, (255, 255, 255), 3)
        
        # Als JPEG kodieren
        ret, jpeg = cv2.imencode('.jpg', img)
        return jpeg.tobytes()
