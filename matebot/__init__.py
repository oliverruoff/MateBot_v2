"""
MateBot v2 - SLAM-Enabled Autonomous Robot Platform
"""

__version__ = "2.0.0"
__author__ = "MateBot Team"

from .core.robot import MateBot
from .core.state_manager import RobotState, RobotMode

__all__ = ["MateBot", "RobotState", "RobotMode"]
