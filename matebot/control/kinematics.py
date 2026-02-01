"""
Omni-directional wheel kinematics for mecanum/omni wheel configuration
"""

import numpy as np
from typing import Tuple
from loguru import logger


class OmniWheelKinematics:
    """
    Inverse kinematics for 4-wheel omni-directional robot
    
    Converts desired robot velocities (vx, vy, omega) into individual wheel speeds
    for a mecanum/omni wheel configuration.
    """
    
    def __init__(self, wheel_base: float, wheel_radius: float):
        """
        Initialize kinematics
        
        Args:
            wheel_base: Distance between wheels (meters)
            wheel_radius: Radius of wheels (meters)
        """
        self.wheel_base = wheel_base
        self.wheel_radius = wheel_radius
        
        # Distance from robot center to wheel (diagonal)
        self.lx = wheel_base / 2.0
        self.ly = wheel_base / 2.0
        
        logger.info(f"Omni kinematics initialized (wheel_base={wheel_base}m, wheel_radius={wheel_radius}m)")
    
    def inverse_kinematics(self, vx: float, vy: float, omega: float) -> Tuple[float, float, float, float]:
        """
        Convert robot velocities to wheel velocities
        
        Args:
            vx: Linear velocity in X direction (forward/backward) [m/s]
            vy: Linear velocity in Y direction (strafe left/right) [m/s]
            omega: Angular velocity (rotation) [rad/s]
            
        Returns:
            Tuple of wheel velocities (FL, FR, BL, BR) in rad/s
            
        Mecanum/Omni wheel configuration:
            FL --- FR
             |  ^  |
             |  |  |  (Forward is up)
            BL --- BR
        """
        # Mecanum wheel inverse kinematics matrix
        # Each wheel contributes to vx, vy, and rotation
        
        # Front Left wheel
        vfl = (vx - vy - (self.lx + self.ly) * omega) / self.wheel_radius
        
        # Front Right wheel
        vfr = (vx + vy + (self.lx + self.ly) * omega) / self.wheel_radius
        
        # Back Left wheel
        vbl = (vx + vy - (self.lx + self.ly) * omega) / self.wheel_radius
        
        # Back Right wheel
        vbr = (vx - vy + (self.lx + self.ly) * omega) / self.wheel_radius
        
        return (vfl, vfr, vbl, vbr)
    
    def forward_kinematics(self, vfl: float, vfr: float, vbl: float, vbr: float) -> Tuple[float, float, float]:
        """
        Convert wheel velocities back to robot velocities (for odometry)
        
        Args:
            vfl, vfr, vbl, vbr: Wheel velocities in rad/s
            
        Returns:
            Tuple (vx, vy, omega) in m/s, m/s, rad/s
        """
        # Forward kinematics matrix (inverse of above)
        vx = self.wheel_radius * (vfl + vfr + vbl + vbr) / 4.0
        vy = self.wheel_radius * (-vfl + vfr + vbl - vbr) / 4.0
        omega = self.wheel_radius * (-vfl + vfr - vbl + vbr) / (4.0 * (self.lx + self.ly))
        
        return (vx, vy, omega)
    
    def limit_wheel_speeds(self, vfl: float, vfr: float, vbl: float, vbr: float, 
                          max_speed: float) -> Tuple[float, float, float, float]:
        """
        Limit wheel speeds while maintaining direction ratios
        
        Args:
            vfl, vfr, vbl, vbr: Desired wheel velocities
            max_speed: Maximum allowed wheel speed (rad/s)
            
        Returns:
            Scaled wheel velocities
        """
        # Find maximum absolute velocity
        max_vel = max(abs(vfl), abs(vfr), abs(vbl), abs(vbr))
        
        if max_vel > max_speed:
            # Scale all velocities proportionally
            scale = max_speed / max_vel
            return (vfl * scale, vfr * scale, vbl * scale, vbr * scale)
        
        return (vfl, vfr, vbl, vbr)
