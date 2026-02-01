"""
High-level motion controller combining kinematics and motor control
"""

import time
import threading
from typing import Optional, Tuple
from loguru import logger

from matebot.control.kinematics import OmniWheelKinematics
from matebot.hardware.motors import MotorController
from matebot.core.state_manager import Velocity2D


class MotionController:
    """
    High-level motion controller for omni-directional robot
    
    Handles velocity commands and converts them to motor speeds
    """
    
    def __init__(self, motor_controller: MotorController, config: dict):
        """
        Initialize motion controller
        
        Args:
            motor_controller: Low-level motor controller
            config: Robot configuration dictionary
        """
        self.motor_controller = motor_controller
        self.config = config
        
        # Initialize kinematics
        wheel_base = config['robot']['wheel_base']
        wheel_radius = config['robot']['wheel_radius']
        self.kinematics = OmniWheelKinematics(wheel_base, wheel_radius)
        
        # Motion limits
        self.max_linear_speed = config['robot']['max_linear_speed']
        self.max_angular_speed = config['robot']['max_angular_speed']
        
        # Maximum wheel speed (rad/s)
        self.max_wheel_speed = self.max_linear_speed / wheel_radius
        
        # Current commanded velocity
        self.current_velocity = Velocity2D()
        self._velocity_lock = threading.Lock()
        
        # Control loop
        self._running = False
        self._control_thread: Optional[threading.Thread] = None
        self._control_rate_hz = 50  # 50 Hz control loop
        
        logger.info(f"Motion controller initialized (max_linear={self.max_linear_speed}m/s, max_angular={self.max_angular_speed}rad/s)")
    
    def start(self) -> None:
        """Start motion control loop"""
        if self._running:
            logger.warning("Motion controller already running")
            return
        
        self._running = True
        self._control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self._control_thread.start()
        logger.info("Motion control loop started")
    
    def stop(self) -> None:
        """Stop motion control loop"""
        if not self._running:
            return
        
        self._running = False
        if self._control_thread:
            self._control_thread.join(timeout=1.0)
        
        self.motor_controller.stop_all()
        logger.info("Motion control loop stopped")
    
    def set_velocity(self, vx: float = 0.0, vy: float = 0.0, omega: float = 0.0) -> None:
        """
        Set desired robot velocity
        
        Args:
            vx: Linear velocity forward/backward (m/s)
            vy: Linear velocity left/right (m/s)
            omega: Angular velocity (rad/s)
        """
        # Clamp to limits
        vx = max(-self.max_linear_speed, min(self.max_linear_speed, vx))
        vy = max(-self.max_linear_speed, min(self.max_linear_speed, vy))
        omega = max(-self.max_angular_speed, min(self.max_angular_speed, omega))
        
        with self._velocity_lock:
            self.current_velocity.vx = vx
            self.current_velocity.vy = vy
            self.current_velocity.omega = omega
        
        logger.debug(f"Velocity command: vx={vx:.3f}, vy={vy:.3f}, ω={omega:.3f}")
    
    def get_velocity(self) -> Velocity2D:
        """Get current velocity command"""
        with self._velocity_lock:
            return Velocity2D(
                vx=self.current_velocity.vx,
                vy=self.current_velocity.vy,
                omega=self.current_velocity.omega
            )
    
    def emergency_stop(self) -> None:
        """Immediate emergency stop"""
        with self._velocity_lock:
            self.current_velocity = Velocity2D()
        self.motor_controller.stop_all()
        logger.critical("Emergency stop executed")
    
    def _control_loop(self) -> None:
        """Main control loop running in separate thread"""
        dt = 1.0 / self._control_rate_hz
        
        while self._running:
            loop_start = time.time()
            
            try:
                # Get current velocity command
                with self._velocity_lock:
                    vx = self.current_velocity.vx
                    vy = self.current_velocity.vy
                    omega = self.current_velocity.omega
                
                # Convert to wheel velocities using inverse kinematics
                vfl, vfr, vbl, vbr = self.kinematics.inverse_kinematics(vx, vy, omega)
                
                # Limit wheel speeds
                vfl, vfr, vbl, vbr = self.kinematics.limit_wheel_speeds(
                    vfl, vfr, vbl, vbr, self.max_wheel_speed
                )
                
                # Send to motors
                self.motor_controller.set_wheel_speeds(vfl, vfr, vbl, vbr)
                
            except Exception as e:
                logger.error(f"Error in control loop: {e}")
                self.motor_controller.stop_all()
            
            # Maintain loop rate
            elapsed = time.time() - loop_start
            sleep_time = dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def move_forward(self, speed: float = 0.3) -> None:
        """Convenience: Move forward"""
        self.set_velocity(vx=speed, vy=0, omega=0)
    
    def move_backward(self, speed: float = 0.3) -> None:
        """Convenience: Move backward"""
        self.set_velocity(vx=-speed, vy=0, omega=0)
    
    def strafe_left(self, speed: float = 0.3) -> None:
        """Convenience: Strafe left"""
        self.set_velocity(vx=0, vy=speed, omega=0)
    
    def strafe_right(self, speed: float = 0.3) -> None:
        """Convenience: Strafe right"""
        self.set_velocity(vx=0, vy=-speed, omega=0)
    
    def rotate_left(self, speed: float = 0.5) -> None:
        """Convenience: Rotate counter-clockwise"""
        self.set_velocity(vx=0, vy=0, omega=speed)
    
    def rotate_right(self, speed: float = 0.5) -> None:
        """Convenience: Rotate clockwise"""
        self.set_velocity(vx=0, vy=0, omega=-speed)
    
    def stop_motion(self) -> None:
        """Convenience: Stop all motion"""
        self.set_velocity(vx=0, vy=0, omega=0)
    
    def cleanup(self) -> None:
        """Clean up resources"""
        self.stop()
        self.motor_controller.cleanup()
