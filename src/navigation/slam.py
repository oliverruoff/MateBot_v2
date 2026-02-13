import numpy as np
import config

class SlamProcessor:
    def __init__(self):
        self.map_size = config.MAP_SIZE_PIXELS
        self.resolution = config.MAP_RESOLUTION
        # 0=unknown, 127=free, 255=occupied
        self.map_data = np.full((self.map_size, self.map_size), 0, dtype=np.uint8)
        self.x, self.y, self.theta = self.map_size/2 * self.resolution, self.map_size/2 * self.resolution, 0.0

    def update(self, scan_data, odometry=None):
        # 1. Update pose from odometry (if we had it)
        if odometry:
            dx, dy, dtheta = odometry
            self.x += dx
            self.y += dy
            self.theta += dtheta
            
        # 2. Mark current area as free
        cx, cy = int(self.x / self.resolution), int(self.y / self.resolution)
        if 0 <= cx < self.map_size and 0 <= cy < self.map_size:
            # Clear a small area around the robot
            r = int(0.5 / self.resolution)
            self.map_data[max(0, cy-r):min(self.map_size, cy+r), 
                          max(0, cx-r):min(self.map_size, cx+r)] = 127
            
        # 3. Project Lidar scan onto map
        for angle_deg, dist_m in scan_data:
            if dist_m < 0.15 or dist_m > 8.0: continue
            
            # Convert polar to cartesian in world frame
            # Lidar 0 is Front, but CCW or CW? LD19 is usually CCW
            angle_rad = np.radians(angle_deg) + self.theta
            ox = self.x + dist_m * np.cos(angle_rad)
            oy = self.y + dist_m * np.sin(angle_rad)
            
            px, py = int(ox / self.resolution), int(oy / self.resolution)
            if 0 <= px < self.map_size and 0 <= py < self.map_size:
                self.map_data[py, px] = 255
                
        # 4. Draw robot indicator (always visible)
        self.map_data[cy-1:cy+1, cx-1:cx+1] = 255
                
        return self.x, self.y, self.theta

    def get_map(self):
        return self.map_data

    def reset_map(self):
        """Clear the occupancy grid map data"""
        self.map_data.fill(0)
        # Reset position to center (optional, but usually desired on reset)
        self.x, self.y, self.theta = self.map_size/2 * self.resolution, self.map_size/2 * self.resolution, 0.0
