# Motor Test - Quick Start Guide

## Testing the Motors on Raspberry Pi

Follow these steps to test your motors on the Raspberry Pi.

### 1. Prerequisites

Make sure your Raspberry Pi has:
- Python 3.7 or higher
- GPIO enabled
- Internet connection (for initial setup)

### 2. Setup on Raspberry Pi

```bash
# SSH into your Raspberry Pi
ssh pi@your-raspberry-pi-ip

# Navigate to your project
cd ~/Documents/develop/MateBot_v2

# Or clone if not already there
# cd ~/Documents/develop
# git clone <your-repo-url> MateBot_v2
# cd MateBot_v2

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Start pigpio daemon (required for hardware PWM)
sudo pigpiod
```

### 3. Verify Hardware Connections

Make sure your motors are connected according to the config:

```
Front Left Motor:
  - DIR:  GPIO 11
  - STEP: GPIO 9

Front Right Motor:
  - DIR:  GPIO 10
  - STEP: GPIO 22

Back Left Motor:
  - DIR:  GPIO 19
  - STEP: GPIO 13

Back Right Motor:
  - DIR:  GPIO 6
  - STEP: GPIO 5

Sleep (All Motors):
  - SLEEP: GPIO 26
```

**Power Supply:**
- Make sure your motor drivers are powered (12V recommended)
- Raspberry Pi GPIO only provides control signals, not power

### 4. Run the Motor Test

```bash
# Make sure venv is activated
source venv/bin/activate

# Run the test script
python test_motors.py
```

### 5. Test Modes

The script offers two modes:

#### Automated Test Sequence
- Tests all 6 movement directions automatically
- Each movement runs for 2 seconds
- Good for initial verification

#### Manual Control Mode
- Interactive keyboard control
- Controls:
  - **W** - Forward
  - **S** - Backward
  - **A** - Strafe Left
  - **D** - Strafe Right
  - **Q** - Rotate Left
  - **E** - Rotate Right
  - **X** - Stop
  - **1/2/3** - Change speed (slow/medium/fast)
  - **ESC** - Exit

### 6. Expected Behavior

When working correctly:
- **Forward (W)**: Robot moves straight forward
- **Backward (S)**: Robot moves straight backward
- **Strafe Left (A)**: Robot slides sideways to the left
- **Strafe Right (D)**: Robot slides sideways to the right
- **Rotate Left (Q)**: Robot rotates counter-clockwise in place
- **Rotate Right (E)**: Robot rotates clockwise in place

### 7. Troubleshooting

#### Motors Not Moving

```bash
# Check if pigpiod is running
pigs hwver
# If error, start it:
sudo pigpiod

# Check GPIO permissions
sudo usermod -a -G gpio $USER
# Logout and login again
```

#### Wrong Direction

If a motor spins the wrong way:
1. Edit `config/config.yaml`
2. Find the motor under `hardware.motors`
3. Change `direction_multiplier` from `1` to `-1` (or vice versa)

Example:
```yaml
hardware:
  motors:
    front_left:
      dir_pin: 11
      step_pin: 9
      direction_multiplier: -1  # Changed from 1 to -1
```

#### Motors Spinning Too Fast/Slow

Adjust speed in the test or in config:
```yaml
robot:
  max_linear_speed: 0.5  # Reduce this value
  max_angular_speed: 1.0  # Reduce this value
```

#### Permission Errors

```bash
# Add user to required groups
sudo usermod -a -G gpio,i2c,spi $USER

# For USB devices (LiDAR)
sudo usermod -a -G dialout $USER

# Logout and login for changes to take effect
```

#### Import Errors

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### 8. Next Steps After Testing

Once motors are working:

1. **Calibrate Directions**
   - Note which motors need direction_multiplier flipped
   - Update config.yaml accordingly

2. **Test IMU (Gyro)**
   - We'll create an IMU test script next

3. **Test LiDAR**
   - Then integrate LiDAR sensor

4. **Full Integration**
   - Combine everything with SLAM

### 9. Stopping the Test

- Press **ESC** or **Ctrl+C** in the test
- The script will automatically:
  - Stop all motors
  - Clean up GPIO
  - Exit safely

### 10. Auto-start pigpiod on Boot (Optional)

To avoid manually starting pigpiod each time:

```bash
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
```

---

## Common Issues

### "No module named 'pigpio'"
```bash
# Make sure venv is activated
source venv/bin/activate
pip install pigpio
```

### "pigpio daemon not running"
```bash
sudo pigpiod
```

### Motors vibrate but don't move
- Check power supply to motor drivers
- Verify motor connections
- Check if microstepping is configured correctly on drivers

### Robot moves in unexpected direction
- This is normal! Use direction_multiplier to calibrate
- Each robot may need different settings

---

## Safety Notes

⚠️ **Important Safety Reminders:**

1. **Clear Space**: Test in an open area
2. **Power**: Be ready to cut power or press ESC
3. **Cables**: Make sure cables won't get caught in wheels
4. **First Test**: Start with slow speed (press '1')
5. **Emergency Stop**: Press 'X' or ESC to stop immediately

---

## Need Help?

If you encounter issues:
1. Check the logs in `logs/matebot.log`
2. Run with debug logging: Edit `test_motors.py` and change log level to "DEBUG"
3. Verify hardware connections against config.yaml
4. Check that pigpiod is running: `pigs hwver`

Happy testing! 🤖
