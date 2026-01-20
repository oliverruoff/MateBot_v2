import cv2

class Camera:
    def __init__(self):
        # 0 ist meistens die Standard Raspberry Pi Kamera (/dev/video0)
        self.video = cv2.VideoCapture(0)
        # Auflösung reduzieren für flüssiges Streaming im WLAN
        self.video.set(3, 640)
        self.video.set(4, 480)

    def __del__(self):
        self.video.release()

    def get_frame(self):
        success, image = self.video.read()
        if not success:
            return None
        # Encode als JPEG
        ret, jpeg = cv2.imencode('.jpg', image)
        return jpeg.tobytes()