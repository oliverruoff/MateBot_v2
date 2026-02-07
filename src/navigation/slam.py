import numpy as np
import config

class SlamProcessor:
    def __init__(self):
        self.map_size = config.MAP_SIZE_PIXELS
        self.resolution = config.MAP_RESOLUTION
        # map_data: 0=unknown, 127=free, 255=occupied (typical SLAM convention or similar)
        # BreezySLAM often uses 0-255 grayscale
        self.map_data = np.full((self.map_size, self.map_size), 127, dtype=np.uint8)
        self.x, self.y, self.theta = self.map_size/2 * self.resolution, self.map_size/2 * self.resolution, 0.0
        print("BreezySLAM Wrapper initialized (Stub)")

    def update(self, scan_data, odometry=None):
        """
        scan_data: list of (angle, distance)
        odometry: (dx, dy, dtheta)
        Returns: (x, y, theta)
        """
        # TODO: Implement real BreezySLAM integration
        # For now, just update pose based on odometry if provided
        if odometry:
            dx, dy, dtheta = odometry
            self.x += dx
            self.y += dy
            self.theta += dtheta
            
        # Simulate mapping: just draw a small circle at current pose as 'free'
        px = int(self.x / self.resolution)
        py = int(self.y / self.resolution)
        if 0 <= px < self.map_size and 0 <= py < self.map_size:
            self.map_data[py-2:py+2, px-2:px+2] = 255 # Occupied at center for visibility in stub
            
        return self.x, self.y, self.theta

    def get_map(self):
        return self.map_data
