# Agent Guidelines for MateBot v2

This document provides essential instructions for AI agents working in this repository. 

## Project Overview
- **Core**: Autonomous SLAM robot (Raspberry Pi 4B, Mecanum wheels, LD19 LiDAR, MPU6050 IMU).
- **Stack**: Python 3.12, FastAPI (App), Flask (Legacy Web UI), NumPy, pigpio.
- **Orientation**: REP 103 Standard (X forward, Y left, Z up, CCW positive rotation).
- **Status**: Infinite dynamic SLAM mapping implemented with batch processing optimizations.

## 🛠 Build & Test Commands

### Local Environment
```bash
source venv/bin/activate         # Linux
venv\Scripts\activate            # Windows
pip install -r requirements.txt   # Sync dependencies
black matebot/                   # Format code before commit
pytest tests/                    # Run all tests
pytest tests/test_file.py::test_func # Run single test
```

### Remote Hardware Testing (Raspberry Pi)
Agents MUST test changes on hardware using SSH MCP.
```bash
# 1. Connect: ssh matebot@matebot.local (pwd: m4t3b0t!-)
# 2. Start pigpio daemon: sudo pigpiod
# 3. Restart server: sudo fuser -k 5000/tcp; ./start_server.sh
# 4. Tail logs: tail -f app.log
```

## 📐 Code Style & Conventions

### 1. Imports
Follow 3-group alphabetical order:
1. Standard library (`math`, `time`, `threading`)
2. Third-party (`numpy`, `loguru`, `fastapi`)
3. Local absolute imports (`from matebot.core...`)
- **NEVER** use relative imports or wildcards (`import *`).

### 2. Naming & Structure
- **Modules/Packages**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/Vars**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private Members**: Prefix with `_` (e.g., `self._lock`).

### 3. Type Hints & Docs
- **Required**: Type hints for ALL function parameters and return values.
- **Required**: Google-style docstrings for ALL public classes and methods.
```python
def add_point(self, x: float, y: float) -> bool:
    """Adds a coordinate to the mapper.
    Args:
        x: World X in meters.
        y: World Y in meters.
    Returns:
        True if successfully added.
    """
```

### 4. Error Handling
- Use `loguru.logger` for all logging.
- Implement **Graceful Degradation**: Always provide a simulation/no-op fallback if `pigpio` or hardware is unavailable.
- Critical loops must have a `try-except` block to prevent thread death.

### 5. Concurrency & Performance
- **Thread Safety**: Use `threading.Lock` or `threading.RLock` for shared state (Map, Pose).
- **Batch Processing**: When updating heavy structures like the SLAM grid, use batch updates to minimize lock contention.
- **Non-blocking**: Avoid long `sleep()` calls in main control loops.

## 🤖 Common Agent Tasks

### Adding Hardware Drivers
1. Create `hardware/driver_name.py`.
2. Implement simulation mode.
3. Update `config/config.yaml`.
4. Register in `app.py` or `state_manager.py`.

### Modifying SLAM Logic
- Grid resolution is 5cm.
- Mapper uses a chunked system (10m x 10m chunks) for infinite exploration.
- Use `matebot/slam/mapper.py` for grid logic and `manual_mapper.py` for loop orchestration.

## 📐 Coordinate Systems (REP 103)
- **Robot Frame**: 
  - X: Forward (+)
  - Y: Left (+)
  - Z: Up (+)
- **Angular**: Counter-Clockwise (CCW) is positive. 0 radians is facing North/Forward.
- **Map Frame**: 2D Grid where (0,0) is the start pose.

## 💾 Design Patterns
- **Singleton**: Used for configuration and state managers.
- **Observer**: Used for telemetry and status updates.
- **Batching**: Crucial for high-frequency data (LiDAR) to avoid thread lock starvation.
- **Abstraction Layer**: Hardware drivers must expose a consistent interface regardless of whether the physical device is connected.

## ⚠️ Important Rules
1. **Safety First**: Always implement emergency stop triggers when modifying motor control.
2. **Path Resolution**: Use absolute paths for all file operations (`os.path.join` with project root).
3. **Black Formatting**: Run `black` on all modified files before pushing.
4. **No Reverts**: Do not revert architectural changes (like the Chunked Mapper) unless requested.
5. **No Chitchat**: Keep responses concise and tool-focused.
