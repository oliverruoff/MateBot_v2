"""
Simple SLAM mapper for MateBot v2
Creates an occupancy grid map from LiDAR data
"""

import numpy as np
import threading
import time
import math
from typing import Tuple, List, Dict, Optional
from loguru import logger


class OccupancyGridMapper:
    """
    Simple occupancy grid SLAM mapper
    
    Creates a 2D grid map where each cell can be:
    - Unknown (0)
    - Free space (1-50)
    - Occupied (51-100)
    """
    
    def __init__(self, 
                 width_m: float = 10.0, 
                 height_m: float = 10.0, 
                 resolution_cm: float = 5.0):
        """
        Initialize mapper
        
        Args:
            width_m: Map width in meters
            height_m: Map height in meters  
            resolution_cm: Grid cell size in centimeters
        """
        self.width_m = width_m
        self.height_m = height_m
        self.resolution_cm = resolution_cm
        self.resolution_m = resolution_cm / 100.0
        
        # Calculate grid dimensions
        self.grid_width = int(width_m / self.resolution_m)
        self.grid_height = int(height_m / self.resolution_m)
        
        # Occupancy grid (0=unknown, 1-50=free, 51-100=occupied)
        self._grid = np.zeros((self.grid_height, self.grid_width), dtype=np.uint8)
        
        # Robot position in map (starts at center)
        self._robot_x_m = width_m / 2.0
        self._robot_y_m = height_m / 2.0
        self._robot_heading_rad = 0.0  # Radians, 0 = facing up
        
        # Thread safety
        self._lock = threading.Lock()
        
        logger.info(f"Occupancy grid mapper initialized: {self.grid_width}x{self.grid_height} cells ({resolution_cm}cm resolution)")
    
    def world_to_grid(self, x_m: float, y_m: float) -> Tuple[int, int]:
        """
        Convert world coordinates (meters) to grid coordinates
        
        Args:
            x_m: X position in meters
            y_m: Y position in meters
            
        Returns:
            (grid_x, grid_y) tuple
        """
        grid_x = int(x_m / self.resolution_m)
        grid_y = int(y_m / self.resolution_m)
        return grid_x, grid_y
    
    def grid_to_world(self, grid_x: int, grid_y: int) -> Tuple[float, float]:
        """
        Convert grid coordinates to world coordinates (meters)
        
        Args:
            grid_x: Grid X coordinate
            grid_y: Grid Y coordinate
            
        Returns:
            (x_m, y_m) tuple
        """
        x_m = grid_x * self.resolution_m
        y_m = grid_y * self.resolution_m
        return x_m, y_m
    
    def is_valid_grid_pos(self, grid_x: int, grid_y: int) -> bool:
        """Check if grid position is within bounds"""
        return 0 <= grid_x < self.grid_width and 0 <= grid_y < self.grid_height
    
    def update_robot_pose(self, x_m: float, y_m: float, heading_rad: float) -> None:
        """
        Update robot position estimate
        
        Args:
            x_m: X position in meters
            y_m: Y position in meters
            heading_rad: Heading in radians (0 = north/up)
        """
        with self._lock:
            self._robot_x_m = x_m
            self._robot_y_m = y_m
            self._robot_heading_rad = heading_rad
    
    def get_robot_pose(self) -> Tuple[float, float, float]:
        """Get current robot pose estimate"""
        with self._lock:
            return self._robot_x_m, self._robot_y_m, self._robot_heading_rad
    
    def update_from_lidar(self, lidar_points: List[Dict]) -> None:
        """
        Update map from LiDAR scan
        
        Args:
            lidar_points: List of LiDAR points with 'angle' and 'distance_cm'
        """
        with self._lock:
            robot_grid_x, robot_grid_y = self.world_to_grid(self._robot_x_m, self._robot_y_m)
            
            for point in lidar_points:
                # Get point data
                angle_deg = point['angle']
                distance_cm = point['distance_cm']
                
                # Convert to world frame (angle relative to robot heading)
                angle_world_rad = math.radians(angle_deg) + self._robot_heading_rad
                distance_m = distance_cm / 100.0
                
                # Calculate endpoint in world coordinates
                end_x_m = self._robot_x_m + distance_m * math.cos(angle_world_rad)
                end_y_m = self._robot_y_m + distance_m * math.sin(angle_world_rad)
                
                # Convert to grid
                end_grid_x, end_grid_y = self.world_to_grid(end_x_m, end_y_m)
                
                # Skip if endpoint is out of bounds
                if not self.is_valid_grid_pos(end_grid_x, end_grid_y):
                    continue
                
                # Mark endpoint as occupied
                self._grid[end_grid_y, end_grid_x] = min(100, self._grid[end_grid_y, end_grid_x] + 10)
                
                # Ray trace from robot to endpoint, marking cells as free
                self._bresenham_line(robot_grid_x, robot_grid_y, end_grid_x, end_grid_y)
    
    def _bresenham_line(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """
        Bresenham's line algorithm to mark cells along ray as free
        Stops before the endpoint
        """
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        
        x, y = x0, y0
        
        while True:
            # Stop before reaching endpoint
            if x == x1 and y == y1:
                break
            
            # Mark as free space (but don't overwrite occupied cells)
            if self.is_valid_grid_pos(x, y):
                if self._grid[y, x] < 51:  # Only update if not occupied
                    self._grid[y, x] = min(50, self._grid[y, x] + 5)
            
            # Bresenham step
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
    
    def get_map_data(self) -> Dict:
        """
        Get map data for visualization
        
        Returns:
            Dictionary with map grid and metadata
        """
        with self._lock:
            robot_grid_x, robot_grid_y = self.world_to_grid(self._robot_x_m, self._robot_y_m)
            
            # Convert grid to list for JSON serialization
            grid_list = self._grid.tolist()
            
            return {
                'width': self.grid_width,
                'height': self.grid_height,
                'resolution_cm': self.resolution_cm,
                'grid': grid_list,
                'robot_pos': {
                    'x': robot_grid_x,
                    'y': robot_grid_y,
                    'heading_rad': self._robot_heading_rad
                }
            }
    
    def get_occupancy_at(self, x_m: float, y_m: float) -> int:
        """
        Get occupancy value at world position
        
        Args:
            x_m: X position in meters
            y_m: Y position in meters
            
        Returns:
            Occupancy value (0=unknown, 1-50=free, 51-100=occupied)
        """
        grid_x, grid_y = self.world_to_grid(x_m, y_m)
        
        with self._lock:
            if self.is_valid_grid_pos(grid_x, grid_y):
                return int(self._grid[grid_y, grid_x])
            return 0
    
    def is_path_clear(self, x_m: float, y_m: float, radius_m: float = 0.3) -> bool:
        """
        Check if area around position is clear
        
        Args:
            x_m: X position in meters
            y_m: Y position in meters
            radius_m: Safety radius in meters
            
        Returns:
            True if area is clear/unknown
        """
        grid_x, grid_y = self.world_to_grid(x_m, y_m)
        radius_cells = int(radius_m / self.resolution_m)
        
        with self._lock:
            # Check area around position
            for dy in range(-radius_cells, radius_cells + 1):
                for dx in range(-radius_cells, radius_cells + 1):
                    check_x = grid_x + dx
                    check_y = grid_y + dy
                    
                    if not self.is_valid_grid_pos(check_x, check_y):
                        return False
                    
                    # If cell is occupied, path is blocked
                    if self._grid[check_y, check_x] > 50:
                        return False
            
            return True
    
    def reset_map(self) -> None:
        """Clear the map"""
        with self._lock:
            self._grid = np.zeros((self.grid_height, self.grid_width), dtype=np.uint8)
            logger.info("Map reset")
