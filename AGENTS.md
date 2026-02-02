# Agent Guidelines for MateBot v2

This file provides essential guidelines for AI coding agents working on the MateBot v2 autonomous robotics platform.

## Project Overview

**Language**: Python 3.12+
**Platform**: Raspberry Pi 4B with stepper motors, LiDAR, IMU, and camera
**Architecture**: Layered architecture (Hardware → Core → Control → Application)
**Status**: Phase 1 (Hardware Integration) - 85% complete (SLAM & Autonomous Exploration implemented)

## Build/Test Commands

### Environment Setup
```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Start pigpio daemon (required for hardware PWM on Raspberry Pi)
sudo pigpiod
```

### Running the Application
```bash
# Run main application (FastAPI - planned)
python -m matebot.api.app

# Run legacy Flask web server
python app.py

# Run motor test script (manual/automated testing)
python test_motors.py
```

### Testing
```bash
# Run all tests (when test suite exists)
pytest tests/

# Run specific test file
pytest tests/test_motors.py

# Run specific test function
pytest tests/test_motors.py::test_forward_motion

# Run with verbose output
pytest -v tests/

# Run with coverage
pytest --cov=matebot tests/
```

### Code Quality
```bash
# Format code with black
black matebot/

# Check formatting without changes
black --check matebot/

# Format specific file
black matebot/control/motion_controller.py
```

### Hardware Testing
```bash
# Test motors interactively
python test_motors.py
# Controls: WASD for movement, QE for rotation, 1/2/3 for speed, X/ESC to stop

# Test I2C devices (IMU)
sudo i2cdetect -y 1
# Should show device at 0x68 (MPU6050) or 0x28 (BNO055)

# Test LiDAR connection
ls /dev/ttyUSB*
```

## Code Style Guidelines

### Import Organization
```python
# 1. Standard library imports (alphabetical)
import sys
import time
import threading
from pathlib import Path
from typing import Tuple, Optional, Dict, List

# 2. Third-party imports (alphabetical)
import numpy as np
from loguru import logger
import yaml

# 3. Local imports (absolute paths from project root)
from matebot.core.config_loader import get_config
from matebot.hardware.motors import MotorController
from matebot.control.kinematics import OmniWheelKinematics
```

**Rules**:
- Use **absolute imports** from project root (e.g., `from matebot.core...`)
- Avoid relative imports (e.g., `from ..core import ...`)
- Group imports in 3 sections: stdlib → third-party → local
- Never use wildcard imports (`from module import *`)

### Naming Conventions (PEP 8)

```python
# Files and modules
# snake_case.py
motion_controller.py
config_loader.py

# Classes
# PascalCase
class MotorController:
class StateManager:
class OmniWheelKinematics:

# Functions and methods
# snake_case
def get_config():
def set_velocity():
def emergency_stop():

# Constants
# UPPER_SNAKE_CASE
HARDWARE_AVAILABLE = True
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT = 5.0

# Private members (prefix with _)
self._lock
self._control_loop()
self._velocity_lock

# Parameters and variables
# snake_case
wheel_base = 0.25
max_speed = 0.5
current_velocity = Velocity2D()
```

### Type Hints

**Always use type hints** for function parameters and return values:

```python
def set_velocity(self, vx: float = 0.0, vy: float = 0.0, omega: float = 0.0) -> None:
    """Set desired robot velocity"""
    pass

def get_config(config_path: Optional[str] = None) -> ConfigLoader:
    """Load configuration"""
    pass

def inverse_kinematics(self, vx: float, vy: float, omega: float) -> Tuple[float, float, float, float]:
    """Convert robot velocity to wheel speeds"""
    pass
```

### Documentation Style

Use **Google-style docstrings**:

```python
def set_velocity(self, vx: float = 0.0, vy: float = 0.0, omega: float = 0.0) -> None:
    """
    Set desired robot velocity
    
    Args:
        vx: Linear velocity forward/backward (m/s)
        vy: Linear velocity left/right (m/s)
        omega: Angular velocity (rad/s)
    
    Returns:
        None
    
    Raises:
        ValueError: If velocities exceed hardware limits
    """
```

## Error Handling Patterns

### Pattern 1: Try-Except with Logging
```python
try:
    self.pi = pigpio.pi()
    if not self.pi.connected:
        raise RuntimeError("Failed to connect to pigpio daemon")
except ImportError:
    logger.warning("pigpio not available - running in simulation mode")
    HARDWARE_AVAILABLE = False
except Exception as e:
    logger.error(f"Error initializing motor: {e}")
    raise
```

### Pattern 2: Graceful Degradation (Simulation Mode)
```python
try:
    import pigpio
    HARDWARE_AVAILABLE = True
except ImportError:
    logger.warning("Hardware not available - simulation mode")
    HARDWARE_AVAILABLE = False
    pigpio = None

# Later in code:
if HARDWARE_AVAILABLE:
    self.pi.set_PWM_frequency(pin, freq)
else:
    pass  # Simulation mode - no-op
```

### Pattern 3: Thread-Safe Error Handling
```python
def _control_loop(self) -> None:
    while self._running:
        try:
            # Critical operations
            vx, vy, omega = self.get_velocity()
            self.motor_controller.set_speeds(vx, vy, omega)
        except Exception as e:
            logger.error(f"Error in control loop: {e}")
            self.motor_controller.stop_all()  # Safe fallback
```

### Pattern 4: Resource Cleanup
```python
def cleanup(self) -> None:
    """Clean up resources"""
    logger.info("Cleaning up motor controller")
    for motor in self.motors.values():
        motor.cleanup()
    if HARDWARE_AVAILABLE and hasattr(self, 'pi'):
        self.pi.stop()
```

### Pattern 5: Context Managers for Locks
```python
def get_status(self) -> RobotStatus:
    with self._lock:  # Automatic acquisition/release
        return copy(self._status)
```

## Configuration

### Main Config: `config/config.yaml`
```yaml
robot:
  wheel_base: 0.25          # meters
  wheel_radius: 0.05        # meters
  max_linear_speed: 0.5     # m/s
  max_angular_speed: 1.0    # rad/s

hardware:
  motors:
    front_left:
      dir_pin: 11
      step_pin: 9
      direction_multiplier: 1  # ±1 for calibration
```

### Loading Config
```python
from matebot.core.config_loader import get_config

config = get_config('config/config.yaml')
wheel_base = config['robot']['wheel_base']
```

## Design Patterns

### Singleton Pattern (Configuration)
```python
_config_instance = None

def get_config(config_path: str = None) -> ConfigLoader:
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader(config_path)
    return _config_instance
```

### Thread-Safe State Management
```python
class StateManager:
    def __init__(self):
        self._status = RobotStatus()
        self._lock = threading.RLock()  # Reentrant lock
    
    def get_status(self) -> RobotStatus:
        with self._lock:
            return copy(self._status)  # Return copy to prevent external modifications
```

### Hardware Abstraction
Modules should support both real hardware and simulation mode:
```python
if HARDWARE_AVAILABLE:
    # Real hardware operations
    self.pi.set_PWM_dutycycle(pin, duty)
else:
    # Simulation mode
    logger.debug(f"[SIM] Would set pin {pin} to duty {duty}")
```

## Important Notes for Agents

1. **Hardware Safety**: Always implement emergency stop functionality and safe cleanup
2. **Thread Safety**: Use locks when accessing shared state from multiple threads
3. **Logging**: Use `loguru.logger` for all logging (not `print()`)
4. **No Tests Yet**: The test suite is planned but not implemented; use manual testing scripts
5. **Absolute Imports**: Always use absolute imports from `matebot.*`
6. **Type Hints**: Always include type hints for parameters and return values
7. **Docstrings**: All public functions/classes must have Google-style docstrings
8. **Black Formatting**: Run `black matebot/` before committing code
9. **Configuration**: Use YAML config files, never hardcode hardware parameters
10. **Coordinate System**: vx=forward/back, vy=left/right, omega=rotation (CCW positive)

## File References

When referencing code locations, use the format `file_path:line_number`:
```
Motor initialization happens in matebot/hardware/motors.py:45
The control loop runs at 50Hz as defined in matebot/control/motion_controller.py:52
```

## Common Tasks

### Adding a New Hardware Driver
1. Create file in `matebot/hardware/`
2. Implement simulation mode fallback
3. Add configuration to `config/config.yaml`
4. Add cleanup method
5. Test with and without hardware

### Adding a New Control Mode
1. Add mode to `RobotMode` enum in state manager
2. Implement control logic in appropriate layer
3. Update motion controller if needed
4. Add API endpoint in `matebot/api/`

### Debugging Hardware Issues
1. Check logs in `logs/matebot.log`
2. Verify pigpio daemon is running: `sudo pigpiod`
3. Test I2C devices: `sudo i2cdetect -y 1`
4. Test GPIO pins: Check wiring against `config/config.yaml`
5. Run in simulation mode to isolate software issues

## SLAM and Navigation

### Occupancy Grid Mapping
The robot builds a 2D occupancy grid map using LiDAR data:
- **Location**: `matebot/slam/mapper.py`
- **Grid size**: Default 10m x 10m, 5cm resolution
- **States**: 0=Unknown, 1-50=Free, 51-100=Occupied
- **Update Frequency**: ~2Hz (via `ExplorationController`)

### Autonomous Exploration
Autonomous navigation with obstacle avoidance:
- **Location**: `matebot/navigation/explorer.py`
- **Obstacle Check**: Checks 60° sector in front of the robot
- **Safety**: `min_obstacle_distance_cm` (default 40cm)
- **Stuck Detection**: Backs up and rotates if blocked

## Testing Changes on Raspberry Pi Hardware

### SSH Connection

You can connect to the physical Raspberry Pi to test code changes on real hardware using the SSH MCP tools.

**Connection Details:**
- **Hostname**: `matebot.local`
- **Username**: `matebot`
- **Password**: Ask the user before first connection attempt
- **Project Location**: `~/develop/MateBot_v2`

### Workflow for Testing Changes

1. **Connect via SSH**
   ```python
   # Use SSH MCP to connect
   # hostname: matebot.local
   # username: matebot
   # password: (request from user)
   ```

2. **Navigate to Project**
   ```bash
   cd ~/develop/MateBot_v2
   ```

3. **Update Code on Raspberry Pi**
   - Use SSH file write tools to push your changes
   - Or have the user git pull if changes are committed

4. **Test the Changes**
   ```bash
   # Activate virtual environment
   source venv/bin/activate
   
   # Ensure pigpio daemon is running
   sudo pigpiod
   
   # Run specific tests
   python test_motors.py
   
   # Or restart the Flask server
   # First, kill existing server if running
   pkill -f "python app.py"
   
   # Start fresh
   python app.py
   ```

5. **Verify Hardware Functionality**
   ```bash
   # Check server status
   sudo lsof -i :5000
   
   # Test telemetry endpoint
   curl http://localhost:5000/telemetry
   
   # Check logs
   tail -f app.log
   
   # Verify motors respond (if safe to test)
   # Access web interface at http://matebot.local:5000
   ```

6. **Check System Status**
   ```bash
   # View running processes
   ps aux | grep python
   
   # Check pigpio daemon
   ps aux | grep pigpiod
   
   # View system resources
   htop  # or: top
   
   # Check GPIO status (if needed)
   gpio readall
   ```

### Important Testing Notes

- **Hardware Safety**: Always ensure the robot is in a safe position before testing motor movements
- **Emergency Stop**: Be ready to kill the process if motors behave unexpectedly: `pkill -f "python app.py"`
- **Daemon Check**: Always verify `pigpiod` is running before motor tests
- **Log Monitoring**: Keep `tail -f app.log` running in a separate terminal to catch errors
- **Incremental Testing**: Test one change at a time on hardware
- **Backup Config**: Before modifying `config.toml` or `config/config.yaml`, make a backup
- **Non-Destructive**: Prefer reading and monitoring over making changes unless explicitly asked

### Example Testing Session

```bash
# 1. Connect and verify environment
ssh matebot@matebot.local
cd ~/develop/MateBot_v2
source venv/bin/activate

# 2. Check current status
sudo lsof -i :5000  # Is server running?
ps aux | grep pigpiod  # Is daemon running?

# 3. Start necessary services
sudo pigpiod  # Start if not running

# 4. Test code changes
python test_motors.py  # Interactive testing

# 5. Or restart web server
pkill -f "python app.py"  # Stop existing
python app.py  # Start fresh

# 6. Monitor and verify
# In another terminal:
tail -f app.log
curl http://localhost:5000/telemetry

# 7. Cleanup when done
# Ctrl+C to stop app.py (if running in foreground)
```

### When to Use SSH Testing

- **Hardware-Specific Features**: Testing motor control, IMU, camera, or GPIO
- **Real-Time Performance**: Verifying control loop timing and responsiveness
- **Integration Testing**: Ensuring all hardware components work together
- **Production Validation**: Final testing before deployment
- **Debugging Hardware Issues**: Investigating sensor readings or motor behavior

### When NOT to Use SSH Testing

- **Pure Python Logic**: Unit tests for math, kinematics, etc. (run locally)
- **Code Style/Formatting**: Use local `black` and linters
- **Documentation Changes**: Review locally
- **Initial Development**: Write and test logic locally first, then verify on hardware
