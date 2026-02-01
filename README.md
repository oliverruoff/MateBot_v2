# MateBot v2 - SLAM-Enabled Autonomous Robot

A comprehensive autonomous robotics platform built on Raspberry Pi 4B with SLAM capabilities, web-based control interface, and intelligent navigation.

## Features

- **SLAM Mapping**: Real-time environment mapping using LiDAR and camera
- **Autonomous Navigation**: Click-to-navigate on learned maps
- **Web Interface**: Modern, responsive control interface with live video
- **Remote Control**: Manual control with real-time telemetry
- **Task Automation**: Execute location-based tasks
- **Omni-Directional Movement**: 4-wheel mecanum/omni wheel configuration

## Hardware Requirements

### Core Components
- Raspberry Pi 4B (4GB+ recommended)
- 4x Stepper Motors with DRV8825/A4988 drivers
- 4x Omni wheels (mecanum configuration)
- Raspberry Pi Camera Module
- Power supply (12V recommended)

### Required Sensors
- **LiDAR**: RPLIDAR A1/A2 or YDLidar X4
- **IMU**: MPU6050 or BNO055 (I2C)

### Optional
- Wheel encoders for improved odometry
- Battery voltage monitor

## Project Structure

```
MateBot_v2/
├── matebot/                  # Main Python package
│   ├── core/                 # Core robot logic
│   │   ├── robot.py          # Main robot coordinator
│   │   ├── state_manager.py  # State management
│   │   └── config_loader.py  # Configuration
│   │
│   ├── hardware/             # Hardware drivers
│   │   ├── motors.py         # Motor control
│   │   ├── camera.py         # Camera interface
│   │   ├── lidar.py          # LiDAR driver
│   │   ├── imu.py            # IMU driver
│   │   └── odometry.py       # Odometry tracking
│   │
│   ├── slam/                 # SLAM system
│   │   ├── slam_engine.py    # SLAM coordinator
│   │   ├── mapper.py         # Occupancy grid mapping
│   │   ├── localizer.py      # Particle filter localization
│   │   └── map_serializer.py # Map save/load
│   │
│   ├── navigation/           # Navigation system
│   │   ├── path_planner.py   # A* path planning
│   │   ├── pure_pursuit.py   # Path following
│   │   └── location_manager.py # Named locations
│   │
│   ├── control/              # Motion control
│   │   ├── motor_controller.py # Motor control
│   │   ├── kinematics.py     # Omni wheel kinematics
│   │   └── pid_controller.py # PID control
│   │
│   ├── vision/               # Computer vision
│   │   ├── camera_streamer.py # Video streaming
│   │   └── feature_detector.py # Visual features
│   │
│   ├── api/                  # Web API
│   │   ├── app.py            # FastAPI application
│   │   ├── routes/           # API endpoints
│   │   └── websocket/        # WebSocket handlers
│   │
│   ├── tasks/                # Task automation
│   │   ├── task_executor.py  # Task execution
│   │   └── task_definitions.py # Task library
│   │
│   └── utils/                # Utilities
│       ├── logger.py         # Logging setup
│       └── math_utils.py     # Math helpers
│
├── config/                   # Configuration files
│   └── config.yaml           # Main configuration
│
├── frontend/                 # Web interface
│   ├── src/
│   │   ├── components/       # React/Vue components
│   │   └── services/         # API services
│   └── public/
│
├── maps/                     # Saved maps
├── data/                     # Runtime data
│   ├── locations.db          # Location database
│   └── tasks/                # Task definitions
│
├── logs/                     # Log files
│
├── requirements.txt          # Python dependencies
├── SYSTEM_DESIGN.md          # Detailed system design
└── README.md                 # This file
```

## Installation

### 1. Hardware Setup

#### Motor Connections (BCM GPIO)
```
Front Left:   DIR=11, STEP=9
Front Right:  DIR=10, STEP=22
Back Left:    DIR=19, STEP=13
Back Right:   DIR=6,  STEP=5
Sleep (All):  GPIO=26
```

#### LiDAR (RPLIDAR A1)
- Connect via USB adapter to any USB port
- Or connect via UART (TX→GPIO14, RX→GPIO15)

#### IMU (MPU6050)
- VCC → 3.3V (Pin 1)
- GND → Ground (Pin 6)
- SDA → GPIO 2 (Pin 3)
- SCL → GPIO 3 (Pin 5)

### 2. Software Installation

```bash
# Clone repository
cd ~/Documents/develop
cd MateBot_v2

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Raspberry Pi

# Install dependencies
pip install -r requirements.txt

# Install system dependencies for LiDAR
sudo apt-get update
sudo apt-get install -y python3-dev libudev-dev

# Enable I2C for IMU
sudo raspi-config
# Interface Options → I2C → Enable
```

### 3. Configuration

Edit `config/config.yaml` to match your hardware setup:

```yaml
hardware:
  lidar:
    type: "rplidar_a1"  # or "ydlidar_x4"
    port: "/dev/ttyUSB0"
  
  imu:
    type: "mpu6050"  # or "bno055"
    i2c_address: 0x68
```

### 4. Permission Setup

```bash
# Add user to dialout group for serial/USB access
sudo usermod -a -G dialout $USER
sudo usermod -a -G i2c $USER
sudo usermod -a -G gpio $USER

# Logout and login for changes to take effect
```

## Usage

### Running the Robot

```bash
# Activate virtual environment
source venv/bin/activate

# Start the robot server
python -m matebot.api.app

# Access web interface
# Open browser to: http://raspberry-pi-ip:8000
```

### Operating Modes

#### 1. Manual Control Mode
- Direct remote control via web interface
- Use virtual joystick or arrow keys
- View live camera feed
- Monitor telemetry (position, battery, etc.)

#### 2. Learning/Mapping Mode
- Drive robot around to map environment
- LiDAR scans build occupancy grid
- Add named locations (kitchen, living room, etc.)
- Save map for later use

#### 3. Navigation Mode
- Load previously created map
- Click on map to set destination
- Robot navigates autonomously
- Avoids obstacles dynamically

#### 4. Task Automation Mode
- Execute predefined tasks
- Example: "Carry to Kitchen"
  - Navigate to living room
  - Wait for object to be loaded
  - Navigate to kitchen
  - Return home

## API Documentation

### REST Endpoints

```
GET  /api/status              # Robot status
POST /api/control/manual      # Manual control
POST /api/control/stop        # Emergency stop

GET  /api/map                 # Get current map
POST /api/map/save            # Save map
GET  /api/map/locations       # List locations
POST /api/map/locations       # Add location

POST /api/navigate            # Start navigation
GET  /api/navigate/status     # Navigation status
POST /api/navigate/cancel     # Cancel navigation

GET  /api/tasks               # List tasks
POST /api/tasks/execute       # Execute task
```

### WebSocket Events

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://robot-ip:8000/ws');

// Send manual control command
ws.send(JSON.stringify({
  type: 'manual_control',
  data: {vx: 0.5, vy: 0, omega: 0}
}));

// Receive telemetry updates (10 Hz)
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'telemetry') {
    console.log('Position:', msg.data.pose);
    console.log('Battery:', msg.data.battery_voltage);
  }
};
```

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black matebot/
```

### Adding New Tasks

Create task definition in `data/tasks/my_task.json`:

```json
{
  "task_id": "my_task",
  "name": "My Custom Task",
  "steps": [
    {"action": "navigate", "target": "location_1"},
    {"action": "wait", "duration": 5},
    {"action": "navigate", "target": "location_2"}
  ]
}
```

## Troubleshooting

### LiDAR Not Detected

```bash
# Check USB devices
ls /dev/ttyUSB*

# Check permissions
sudo chmod 666 /dev/ttyUSB0

# Test LiDAR manually
python -c "from rplidar import RPLidar; lidar = RPLidar('/dev/ttyUSB0'); print(next(lidar.iter_scans()))"
```

### IMU Not Responding

```bash
# Check I2C devices
sudo i2cdetect -y 1

# Should show device at 0x68 (MPU6050) or 0x28 (BNO055)
```

### Motor Not Moving

- Verify GPIO connections
- Check SLEEP pin is HIGH (GPIO 26)
- Verify power supply to motor drivers
- Check motor driver microstepping configuration

### Camera Issues

```bash
# Test camera
libcamera-hello

# Check if camera is enabled
sudo raspi-config
# Interface Options → Camera → Enable
```

## Performance Tuning

### SLAM Parameters

Edit `config/config.yaml`:

```yaml
slam:
  map_resolution: 0.05  # Smaller = more detailed, slower
  particle_count: 500   # More = accurate, slower
  update_frequency: 10  # Hz
```

### Navigation Parameters

```yaml
navigation:
  goal_tolerance_position: 0.15  # meters
  lookahead_distance: 0.5        # meters
  max_linear_velocity: 0.3       # m/s
```

## Safety Features

- **Emergency Stop**: Immediately halt all motors
- **Watchdog Timer**: Auto-stop if no commands received
- **Battery Monitor**: Return home on low battery
- **Collision Avoidance**: Stop before obstacles
- **Tilt Detection**: Emergency stop on excessive tilt
- **Stuck Detection**: Retry or abort if stuck

## Implementation Roadmap

### Phase 1: Hardware Integration ✅
- [x] Project structure
- [x] Configuration system
- [x] State management
- [ ] Hardware drivers (motors, LiDAR, IMU)

### Phase 2: Motion Control (In Progress)
- [ ] Omni wheel kinematics
- [ ] Motor controller with PID
- [ ] Odometry tracking
- [ ] Manual control mode

### Phase 3: SLAM (Planned)
- [ ] Occupancy grid mapper
- [ ] Particle filter localization
- [ ] Sensor fusion
- [ ] Map saving/loading

### Phase 4: Web Interface (Planned)
- [ ] FastAPI backend
- [ ] React/Vue frontend
- [ ] Video streaming
- [ ] Real-time telemetry

### Phase 5: Navigation (Planned)
- [ ] A* path planner
- [ ] Pure pursuit controller
- [ ] Obstacle avoidance
- [ ] Click-to-navigate UI

### Phase 6: Task Automation (Planned)
- [ ] Task definition system
- [ ] Task executor
- [ ] Location management
- [ ] Task scheduling

## Contributing

Contributions are welcome! Please follow these guidelines:
1. Fork the repository
2. Create a feature branch
3. Follow code style (black formatter)
4. Add tests for new features
5. Submit pull request

## License

MIT License - See LICENSE file for details

## References

- [SLAM Overview](https://en.wikipedia.org/wiki/Simultaneous_localization_and_mapping)
- [Particle Filter Localization](https://en.wikipedia.org/wiki/Monte_Carlo_localization)
- [A* Pathfinding](https://en.wikipedia.org/wiki/A*_search_algorithm)
- [Pure Pursuit Algorithm](https://www.ri.cmu.edu/pub_files/pub3/coulter_r_craig_1992_1/coulter_r_craig_1992_1.pdf)

## Support

For issues and questions:
- Create an issue on GitHub
- Check SYSTEM_DESIGN.md for detailed architecture

---

**MateBot v2** - Built with ❤️ for autonomous robotics
