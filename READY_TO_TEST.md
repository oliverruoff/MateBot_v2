# Ready to Test! 🚀

## What We've Built

You now have a complete motor control system ready to test on your Raspberry Pi!

### Implemented Components

✅ **Omni Wheel Kinematics** (`matebot/control/kinematics.py`)
- Converts robot velocities (vx, vy, omega) into individual wheel speeds
- Handles inverse/forward kinematics for mecanum wheels
- Automatic speed limiting to prevent motor damage

✅ **Low-Level Motor Controller** (`matebot/hardware/motors.py`)
- Controls 4 stepper motors using pigpio (hardware PWM)
- Individual motor control with direction, speed, activation
- Thread-safe operations
- Simulation mode for development without hardware

✅ **High-Level Motion Controller** (`matebot/control/motion_controller.py`)
- Combines kinematics + motor control
- Smooth velocity control (50 Hz control loop)
- Convenience functions: forward, backward, strafe, rotate
- Emergency stop functionality

✅ **Test Script** (`test_motors.py`)
- Interactive manual control mode (WASD keys)
- Automated test sequence
- Variable speed control
- Safe shutdown

✅ **Configuration System** (`config/config.yaml`)
- Centralized hardware configuration
- Easy motor pin mapping
- Adjustable speed limits and parameters

✅ **Documentation**
- Complete setup guide (MOTOR_TEST_GUIDE.md)
- Troubleshooting section
- Safety reminders

---

## How to Test (Quick Reference)

### On Raspberry Pi:

```bash
# 1. Navigate to project
cd ~/Documents/develop/MateBot_v2

# 2. Pull latest code
git pull

# 3. Setup (first time only)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo pigpiod

# 4. Run test
python test_motors.py
```

### Controls in Manual Mode:
- **W/S** - Forward/Backward
- **A/D** - Strafe Left/Right  
- **Q/E** - Rotate Left/Right
- **X** - Stop
- **1/2/3** - Slow/Medium/Fast speed
- **ESC** - Exit

---

## What Happens Next

### Immediate Next Steps (After Motor Test):

1. **Calibrate Motor Directions**
   - Some motors might spin backwards
   - Easy fix: change `direction_multiplier` in config.yaml

2. **Test IMU (Gyro)**
   - Read orientation data from MPU6050
   - Use for rotation feedback

3. **Test LiDAR**
   - Get distance scans
   - Verify sensor data

4. **Integrate All Sensors**
   - Combine motors + IMU + LiDAR
   - Basic sensor fusion

5. **Implement SLAM**
   - Build maps while driving
   - Localize robot position

6. **Build Web Interface**
   - Control from browser
   - Live camera feed
   - Map visualization

---

## File Structure Created

```
MateBot_v2/
├── test_motors.py              # ← START HERE
├── MOTOR_TEST_GUIDE.md         # ← READ THIS
├── requirements.txt            # Updated with pigpio
├── config/
│   └── config.yaml             # Hardware configuration
├── matebot/
│   ├── core/
│   │   ├── config_loader.py    # Config management
│   │   └── state_manager.py    # Robot state
│   ├── control/
│   │   ├── kinematics.py       # Omni wheel math
│   │   └── motion_controller.py # High-level control
│   ├── hardware/
│   │   └── motors.py           # Motor drivers
│   └── utils/
│       ├── logger.py           # Logging setup
│       └── math_utils.py       # Math helpers
```

---

## Expected Test Results

### ✅ Successful Test Looks Like:
- Motors respond to commands within 100ms
- Robot moves smoothly in all 6 directions:
  - Forward/backward
  - Strafe left/right
  - Rotate left/right
- Can stop immediately with 'X'
- No grinding or jerking movements

### ⚠️ Common First-Time Issues:
- **Motor spins wrong way**: Change direction_multiplier
- **Motors don't move**: Check pigpiod running, check power
- **Jerky movement**: Normal with steppers, can tune if needed
- **Import errors**: Activate venv, install requirements

---

## Safety Checklist Before Testing

- [ ] Clear 2-meter radius around robot
- [ ] Power supply connected and adequate (12V recommended)
- [ ] All motor wires properly connected
- [ ] Know where emergency stop is (press 'X' or ESC)
- [ ] Start with slow speed (press '1')
- [ ] Have physical access to robot in case of issues

---

## Technical Details

### Motor Control Architecture:

```
User Command (WASD)
    ↓
MotionController.set_velocity(vx, vy, omega)
    ↓
Kinematics.inverse_kinematics()
    ↓
Individual wheel speeds (rad/s)
    ↓
MotorController.set_wheel_speeds()
    ↓
StepperMotor.set_speed_rads()
    ↓
pigpio hardware PWM
    ↓
GPIO pins (STEP pulses)
    ↓
Motor drivers (DRV8825)
    ↓
Physical motors spin!
```

### Control Loop:
- Runs at 50 Hz (every 20ms)
- Thread-safe velocity updates
- Smooth acceleration/deceleration
- Emergency stop preempts all commands

---

## Need Help?

**Check these first:**
1. `MOTOR_TEST_GUIDE.md` - Complete troubleshooting guide
2. `logs/matebot.log` - Detailed error logs
3. `config/config.yaml` - Verify pin assignments

**Common Commands:**
```bash
# Check if pigpiod is running
pigs hwver

# Restart pigpiod
sudo killall pigpiod
sudo pigpiod

# View logs in real-time
tail -f logs/matebot.log

# Test GPIO access
gpio readall
```

---

## What's Different from Old MateBot

### Improvements:
- ✨ **Hardware PWM** (pigpio) instead of software delays = smoother
- ✨ **Proper kinematics** instead of trial-and-error directions
- ✨ **Velocity control** instead of distance-based movements
- ✨ **Thread-safe** control loop
- ✨ **Configuration-driven** - no hardcoded values
- ✨ **Modular architecture** - easy to extend
- ✨ **Better error handling** and logging

### Migration Note:
Your old motor configurations are preserved in the config.yaml with the same GPIO pins!

---

## After Testing Works

Once motors are confirmed working, we'll add:

1. **IMU Integration** - For rotation feedback
2. **LiDAR Integration** - For mapping
3. **SLAM System** - Mapping + Localization
4. **Web Interface** - Remote control
5. **Navigation** - Autonomous movement
6. **Tasks** - Location-based automation

Each component will have its own test script for step-by-step verification.

---

## Quick Deployment to Raspberry Pi

```bash
# On your PC (Windows):
cd C:\Users\olive\Documents\develop\MateBot_v2
git add .
git commit -m "Add motor control system"
git push

# On Raspberry Pi:
cd ~/Documents/develop/MateBot_v2
git pull
source venv/bin/activate
pip install -r requirements.txt
python test_motors.py
```

---

**You're all set! Push to git, pull on the Pi, and test those motors! 🤖**

Let me know how it goes - if any motors spin the wrong way or if you need to tune anything!
