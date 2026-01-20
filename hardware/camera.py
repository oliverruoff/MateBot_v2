import io
import time
import cv2
import numpy as np
from picamera2 import Picamera2

class Camera:
    def __init__(self):
        self.picam2 = None
        self.placeholder = self._create_placeholder()
        
        try:
            print("INFO: Initialisiere Picamera2...")
            self.picam2 = Picamera2()
            
            # Konfiguration: Wir nutzen einfach das Main-Interface
            # Format RGB888 ist gut als Basis, wir wandeln es beim Abruf in JPEG um
            config = self.picam2.create_configuration(main={"size": (640, 480), "format": "RGB888"})
            self.picam2.configure(config)
            
            # Kamera starten (im Preview/Video Modus laufen lassen)
            self.picam2.start()
            
            # Kurz warten, damit sich der Weißabgleich einpegelt (Warmup)
            time.sleep(2)
            print("INFO: Picamera2 erfolgreich gestartet.")
            
        except Exception as e:
            print(f"WARNUNG: Picamera2 konnte nicht initialisiert werden: {e}")
            self.picam2 = None

    def __del__(self):
        if self.picam2:
            self.picam2.stop()

    def get_frame(self):
        # Wenn Kamera nicht da ist (z.B. Fehler beim Init), Platzhalter senden
        if not self.picam2:
            return self.placeholder

        try:
            # Hier ist der Trick: Wir holen uns direkt das JPEG Bild
            # Das ist für Flask Streams performant genug
            stream = io.BytesIO()
            self.picam2.capture_file(stream, format="jpeg")
            return stream.getvalue()
            
        except Exception as e:
            print(f"FEHLER: Frame konnte nicht gelesen werden: {e}")
            # Falls die Kamera im Betrieb abstürzt, zeigen wir den Platzhalter
            return self.placeholder

    def _create_placeholder(self):
        """Erstellt ein schwarzes Bild mit 'NO SIGNAL' Text"""
        try:
            # Schwarzes Bild erstellen (480p)
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            
            # Text hinzufügen
            text = "NO SIGNAL"
            font = cv2.FONT_HERSHEY_SIMPLEX
            # Text zentrieren
            text_size = cv2.getTextSize(text, font, 2, 3)[0]
            text_x = (img.shape[1] - text_size[0]) // 2
            text_y = (img.shape[0] + text_size[1]) // 2
            
            cv2.putText(img, text, (text_x, text_y), font, 2, (255, 255, 255), 3)
            
            # Als JPEG kodieren
            ret, jpeg = cv2.imencode('.jpg', img)
            return jpeg.tobytes()
        except Exception as e:
            print(f"Fehler beim Erstellen des Platzhalters: {e}")
            return b''