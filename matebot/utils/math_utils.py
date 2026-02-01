"""
Mathematical utilities for robotics calculations
"""

import numpy as np
from typing import Tuple


def normalize_angle(angle: float) -> float:
    """
    Normalize angle to [-pi, pi]
    
    Args:
        angle: Angle in radians
        
    Returns:
        Normalized angle in range [-pi, pi]
    """
    while angle > np.pi:
        angle -= 2 * np.pi
    while angle < -np.pi:
        angle += 2 * np.pi
    return angle


def angle_difference(angle1: float, angle2: float) -> float:
    """
    Compute the smallest difference between two angles
    
    Args:
        angle1: First angle in radians
        angle2: Second angle in radians
        
    Returns:
        Angle difference in range [-pi, pi]
    """
    diff = angle1 - angle2
    return normalize_angle(diff)


def rotation_matrix_2d(theta: float) -> np.ndarray:
    """
    Create 2D rotation matrix
    
    Args:
        theta: Rotation angle in radians
        
    Returns:
        2x2 rotation matrix
    """
    c = np.cos(theta)
    s = np.sin(theta)
    return np.array([[c, -s], [s, c]])


def transform_point(point: Tuple[float, float], pose: Tuple[float, float, float]) -> Tuple[float, float]:
    """
    Transform a point from robot frame to world frame
    
    Args:
        point: Point (x, y) in robot frame
        pose: Robot pose (x, y, theta) in world frame
        
    Returns:
        Point (x, y) in world frame
    """
    px, py = point
    x, y, theta = pose
    
    # Rotate
    rot = rotation_matrix_2d(theta)
    rotated = rot @ np.array([px, py])
    
    # Translate
    return (rotated[0] + x, rotated[1] + y)


def inverse_transform_point(point: Tuple[float, float], pose: Tuple[float, float, float]) -> Tuple[float, float]:
    """
    Transform a point from world frame to robot frame
    
    Args:
        point: Point (x, y) in world frame
        pose: Robot pose (x, y, theta) in world frame
        
    Returns:
        Point (x, y) in robot frame
    """
    px, py = point
    x, y, theta = pose
    
    # Translate
    translated = np.array([px - x, py - y])
    
    # Rotate (inverse rotation)
    rot = rotation_matrix_2d(-theta)
    rotated = rot @ translated
    
    return (rotated[0], rotated[1])


def distance_2d(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """
    Calculate Euclidean distance between two 2D points
    
    Args:
        p1: First point (x, y)
        p2: Second point (x, y)
        
    Returns:
        Distance in meters
    """
    return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def clamp(value: float, min_value: float, max_value: float) -> float:
    """
    Clamp value between min and max
    
    Args:
        value: Value to clamp
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        
    Returns:
        Clamped value
    """
    return max(min_value, min(max_value, value))


def linear_interpolation(start: float, end: float, t: float) -> float:
    """
    Linear interpolation between start and end
    
    Args:
        start: Start value
        end: End value
        t: Interpolation parameter [0, 1]
        
    Returns:
        Interpolated value
    """
    return start + (end - start) * clamp(t, 0.0, 1.0)


def world_to_grid(x: float, y: float, resolution: float, origin: Tuple[float, float]) -> Tuple[int, int]:
    """
    Convert world coordinates to grid cell indices
    
    Args:
        x: X coordinate in meters
        y: Y coordinate in meters
        resolution: Grid resolution in meters/cell
        origin: Grid origin (x, y) in meters
        
    Returns:
        Grid indices (row, col)
    """
    col = int((x - origin[0]) / resolution)
    row = int((y - origin[1]) / resolution)
    return (row, col)


def grid_to_world(row: int, col: int, resolution: float, origin: Tuple[float, float]) -> Tuple[float, float]:
    """
    Convert grid cell indices to world coordinates (cell center)
    
    Args:
        row: Grid row index
        col: Grid column index
        resolution: Grid resolution in meters/cell
        origin: Grid origin (x, y) in meters
        
    Returns:
        World coordinates (x, y) in meters
    """
    x = origin[0] + (col + 0.5) * resolution
    y = origin[1] + (row + 0.5) * resolution
    return (x, y)


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> list:
    """
    Bresenham's line algorithm for ray tracing on grid
    
    Args:
        x0, y0: Start point
        x1, y1: End point
        
    Returns:
        List of (x, y) points along the line
    """
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    
    x, y = x0, y0
    
    while True:
        points.append((x, y))
        
        if x == x1 and y == y1:
            break
        
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    
    return points
