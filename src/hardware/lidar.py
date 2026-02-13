from src.hardware.ld19 import LD19

class LidarSensor:
    def __init__(self, port='/dev/ttyUSB0'):
        self.driver = LD19(port=port)

    def start(self):
        self.driver.start()

    def get_scan(self):
        return self.driver.get_scan()

    def stop(self):
        self.driver.stop()
