import time
import random
import config

class LidarSensor:
    def __init__(self, port='/dev/ttyUSB0'):
        self.port = port
        self.running = False
        print(f"Lidar initialized on {port} (Stub)")

    def start(self):
        self.running = True
        print("Lidar scanning started.")

    def get_scan(self):
        """Returns a list of (angle_deg, distance_m)"""
        if not self.running: return []
        
        # Simulated scan: 360 points
        scan = []
        for i in range(360):
            # Simulate some walls at 2m
            dist = 2.0 + random.uniform(-0.02, 0.02)
            scan.append((float(i), dist))
        
        time.sleep(0.1) # 10Hz
        return scan

    def stop(self):
        self.running = False
        print("Lidar scanning stopped.")
