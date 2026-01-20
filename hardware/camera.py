import cv2
import numpy as np

class Camera:
    def __init__(self):
        # 0 ist meistens die Standard Raspberry Pi Kamera (/dev/video0)
        self.video = cv2.VideoCapture(0)
        # Auflösung reduzieren für flüssiges Streaming im WLAN
        self.video.set(3, 640)
        self.video.set(4, 480)
        
        self.is_opened = self.video.isOpened()
        if not self.is_opened:
            print("WARNUNG: Kamera konnte nicht geöffnet werden.")
        self.placeholder = self._create_placeholder()

    def __del__(self):
        if self.is_opened:
            self.video.release()

    def get_frame(self):
        if not self.is_opened:
            return self.placeholder

        success, image = self.video.read()
        if not success:
            # Wenn das Lesen fehlschlägt, gib das Platzhalterbild zurück
            return self.placeholder
        
        # Encode als JPEG
        ret, jpeg = cv2.imencode('.jpg', image)
        if not ret:
            # Wenn die Kodierung fehlschlägt, gib das Platzhalterbild zurück
            return self.placeholder

        return jpeg.tobytes()

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