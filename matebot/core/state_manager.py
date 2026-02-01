"""
Robot state management and operating modes
"""

from enum import Enum
from typing import Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import threading
from loguru import logger


class RobotMode(Enum):
    """Robot operating modes"""
    IDLE = "idle"
    MANUAL = "manual"
    MAPPING = "mapping"
    NAVIGATION = "navigation"
    TASK_EXECUTION = "task_execution"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class Pose2D:
    """2D pose representation (x, y, theta)"""
    x: float = 0.0  # meters
    y: float = 0.0  # meters
    theta: float = 0.0  # radians
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def to_tuple(self) -> Tuple[float, float, float]:
        """Return as tuple (x, y, theta)"""
        return (self.x, self.y, self.theta)
    
    def __str__(self) -> str:
        return f"Pose2D(x={self.x:.3f}, y={self.y:.3f}, θ={self.theta:.3f})"


@dataclass
class Velocity2D:
    """2D velocity command"""
    vx: float = 0.0  # m/s (forward/backward)
    vy: float = 0.0  # m/s (strafe left/right)
    omega: float = 0.0  # rad/s (rotation)
    
    def is_zero(self) -> bool:
        """Check if velocity is zero"""
        return abs(self.vx) < 1e-6 and abs(self.vy) < 1e-6 and abs(self.omega) < 1e-6
    
    def __str__(self) -> str:
        return f"Velocity(vx={self.vx:.3f}, vy={self.vy:.3f}, ω={self.omega:.3f})"


@dataclass
class RobotStatus:
    """Current robot status information"""
    mode: RobotMode = RobotMode.IDLE
    pose: Pose2D = field(default_factory=Pose2D)
    velocity: Velocity2D = field(default_factory=Velocity2D)
    battery_voltage: float = 12.6  # volts
    is_moving: bool = False
    is_localized: bool = False
    has_map: bool = False
    current_task: Optional[str] = None
    errors: list = field(default_factory=list)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "mode": self.mode.value,
            "pose": {
                "x": self.pose.x,
                "y": self.pose.y,
                "theta": self.pose.theta
            },
            "velocity": {
                "vx": self.velocity.vx,
                "vy": self.velocity.vy,
                "omega": self.velocity.omega
            },
            "battery_voltage": self.battery_voltage,
            "is_moving": self.is_moving,
            "is_localized": self.is_localized,
            "has_map": self.has_map,
            "current_task": self.current_task,
            "errors": self.errors,
            "timestamp": self.timestamp
        }


class StateManager:
    """Thread-safe robot state manager"""
    
    def __init__(self):
        self._status = RobotStatus()
        self._lock = threading.RLock()
        self._mode_change_callbacks = []
        logger.info("State manager initialized")
    
    def get_status(self) -> RobotStatus:
        """Get current robot status (thread-safe copy)"""
        with self._lock:
            # Return a copy to prevent external modifications
            return RobotStatus(
                mode=self._status.mode,
                pose=Pose2D(self._status.pose.x, self._status.pose.y, self._status.pose.theta),
                velocity=Velocity2D(self._status.velocity.vx, self._status.velocity.vy, self._status.velocity.omega),
                battery_voltage=self._status.battery_voltage,
                is_moving=self._status.is_moving,
                is_localized=self._status.is_localized,
                has_map=self._status.has_map,
                current_task=self._status.current_task,
                errors=self._status.errors.copy(),
                timestamp=datetime.now().timestamp()
            )
    
    def set_mode(self, mode: RobotMode) -> bool:
        """
        Set robot operating mode
        
        Returns:
            bool: True if mode changed successfully
        """
        with self._lock:
            if self._status.mode != mode:
                old_mode = self._status.mode
                self._status.mode = mode
                logger.info(f"Mode changed: {old_mode.value} → {mode.value}")
                
                # Notify callbacks
                for callback in self._mode_change_callbacks:
                    try:
                        callback(old_mode, mode)
                    except Exception as e:
                        logger.error(f"Mode change callback error: {e}")
                
                return True
            return False
    
    def get_mode(self) -> RobotMode:
        """Get current operating mode"""
        with self._lock:
            return self._status.mode
    
    def update_pose(self, x: float = None, y: float = None, theta: float = None) -> None:
        """Update robot pose"""
        with self._lock:
            if x is not None:
                self._status.pose.x = x
            if y is not None:
                self._status.pose.y = y
            if theta is not None:
                self._status.pose.theta = theta
            self._status.pose.timestamp = datetime.now().timestamp()
    
    def get_pose(self) -> Pose2D:
        """Get current pose"""
        with self._lock:
            return Pose2D(self._status.pose.x, self._status.pose.y, self._status.pose.theta)
    
    def update_velocity(self, vx: float = None, vy: float = None, omega: float = None) -> None:
        """Update current velocity"""
        with self._lock:
            if vx is not None:
                self._status.velocity.vx = vx
            if vy is not None:
                self._status.velocity.vy = vy
            if omega is not None:
                self._status.velocity.omega = omega
            
            # Update is_moving flag
            self._status.is_moving = not self._status.velocity.is_zero()
    
    def get_velocity(self) -> Velocity2D:
        """Get current velocity"""
        with self._lock:
            return Velocity2D(
                self._status.velocity.vx,
                self._status.velocity.vy,
                self._status.velocity.omega
            )
    
    def set_battery_voltage(self, voltage: float) -> None:
        """Update battery voltage"""
        with self._lock:
            self._status.battery_voltage = voltage
    
    def get_battery_voltage(self) -> float:
        """Get battery voltage"""
        with self._lock:
            return self._status.battery_voltage
    
    def set_localized(self, localized: bool) -> None:
        """Set localization status"""
        with self._lock:
            self._status.is_localized = localized
    
    def set_has_map(self, has_map: bool) -> None:
        """Set map availability status"""
        with self._lock:
            self._status.has_map = has_map
    
    def set_current_task(self, task_name: Optional[str]) -> None:
        """Set currently executing task"""
        with self._lock:
            self._status.current_task = task_name
    
    def add_error(self, error: str) -> None:
        """Add error to error list"""
        with self._lock:
            self._status.errors.append({
                "message": error,
                "timestamp": datetime.now().isoformat()
            })
            logger.error(f"Robot error: {error}")
    
    def clear_errors(self) -> None:
        """Clear all errors"""
        with self._lock:
            self._status.errors.clear()
    
    def register_mode_change_callback(self, callback) -> None:
        """Register callback for mode changes"""
        self._mode_change_callbacks.append(callback)
        logger.debug(f"Registered mode change callback: {callback.__name__}")
    
    def emergency_stop(self) -> None:
        """Trigger emergency stop"""
        with self._lock:
            self._status.mode = RobotMode.EMERGENCY_STOP
            self._status.velocity = Velocity2D()
            self._status.is_moving = False
            logger.critical("EMERGENCY STOP ACTIVATED")
