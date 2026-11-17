# MateBot v2 Hardware Specifications

## Current measured setup (2026-11-15)

The active software is documented in `navigation/README.md`; configuration is
`navigation/config/robot.yaml`. Owner-measured outside dimensions: **41 cm long,
30 cm wide**, **31 cm wheelbase**, **21 cm track width**. The LD19 is centered,
**14 cm above ground**. Current camera/gyro comparisons use native LiDAR angle
sign +1 and `lidar_yaw = +pi/2`; the earlier negative-yaw convention mirrored
left/right. The cable exit alone did not establish the forward direction.

Earlier raised-wheel observations led to **FL/FR/BL/BR direction multipliers
`[-1, 1, -1, 1]`**. The current controller uses continuous hardware-timed pigpio
PWM with a watchdog. Owner observation now reports only BR rotating reliably;
body displacement does not prove all four motors are working. Normal-speed
four-wheel driving and arrival remain unverified. Motor/wheel and
microstep values below are nominal values from the prior documentation, not a new
measurement of floor travel. No wheel encoders or cliff sensors are confirmed.

This document details the hardware components, wiring configuration, and specific usage guidelines for the MateBot v2.

## 🧠 Core Controller
* **Mainboard:** **Raspberry Pi 4 Model B**
* **Processor:** Quad-core Cortex-A72 (ARM v8) 64-bit SoC @ 1.5GHz
* **Operating System:** Raspberry Pi OS (64-bit)
* **Required Services:** `pigpiod` (must be running for hardware PWM support)

## 🏎️ Locomotion: Omni-Directional Drive
* **Wheels:** **4-Wheel Mecanum (Omni Wheels)**
* **Wheel Diameter:** **79mm**
* **Kinematics:** Allows for X-translation (forward/back), Y-translation (strafing), and Rotation (yaw) simultaneously.
* **Motors:** Documented as 4x **NEMA 23**, nominal 1.8° per full step. NEMA size does not identify winding current or inductance; exact nameplate model remains unknown.
* **Drivers:** Documented as **TB6600 modules**; exact manufacturer/version and input circuitry are not confirmed.
* **Microstepping:** Software assumes **1/32**; this is not an independently verified motor-angle measurement.
* **Historical, model-dependent DIP assumptions:**
    * **Microstep (S1, S2, S3):** `OFF, OFF, OFF` (1/32 Step)
    * **Current (S4, S5, S6):** Reported `OFF, OFF, ON`. The previous 3.5 A claim was unsupported. DFRobot's V1.2 table assigns this combination 2.8 A; use the actual module's table, not that example, to establish current.

### Motor Pinout (BCM Numbering)
| Motor | Pin Function | BCM Pin | Physical Pin |
| :--- | :--- | :--- | :--- |
| **Global Control** | Enable (ENA) | 26 | 37 |
| **Front Left** | Step (PUL) | 9 | 21 |
| | Direction (DIR) | 11 | 23 |
| **Front Right** | Step (PUL) | 22 | 15 |
| | Direction (DIR) | 10 | 19 |
| **Back Left** | Step (PUL) | 13 | 33 |
| | Direction (DIR) | 19 | 35 |
| **Back Right** | Step (PUL) | 5 | 29 |
| | Direction (DIR) | 6 | 31 |

---

## ⚙️ Motor Usage Guide & Lessons Learned

Getting the stepper motors to run reliably on a Raspberry Pi required a specific hardware-software orchestration. 

### The Correct Way to Drive the Motors:
1.  **Use a timed STEP clock:** DMA-timed PWM and correctly timed finite pulse trains are both valid STEP/DIR approaches. Python sleep loops are not a reliable high-rate clock. A different pulse-generation API alone is not evidence of a physical fix.
2.  **The `pigpio` Strategy:** * We use the `pigpio` daemon to handle hardware-timed pulses.
    * **Frequency Control:** Instead of manual bit-banging, we use `pi.set_PWM_frequency(step_pin, frequency_hz)`.
    * **Duty Cycle:** Set to `128` (50%) to generate the clock signal.
3.  **The Enable Pin:** All drivers share BCM 26 connected to `ENA`.
    * *Note for TB6600:* Check logic level. Often leaving ENA disconnected is "Enabled". If wired, ensure correct HIGH/LOW logic (usually Active Low for enabling on some clones, Active High on others).
4.  **Direction Calibration:** Every motor's orientation may vary. Use the `direction_multiplier: 1` or `-1` in `config.yaml` to calibrate forward/backward without rewiring.

### Electrical requirements still to verify

Pi 4 GPIO electrical capabilities differ from older Pi models: the official
BCM2711 table specifies 4 mA default / 8 mA maximum drive-strength settings.
The pigpio value named 16 mA must not be treated as a confirmed 16 mA Pi 4
source-current capability. Readback clocks do not measure voltage or current at
an optocoupler. See the [official GPIO documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html).

For comparison, the [DFRobot module manual](https://dfimg.dfrobot.com/nobody/wiki/0bcc0b661ce7750ff7d0134bfc3e88b3.pdf)
calls for 8–15 mA optocoupler input drive and describes 5 V signal wiring. Other
modules sold under TB6600 have different input specifications. This makes a
direct-GPIO interface worth checking; it does not prove that this robot needs a
specific replacement or wiring change. Do not connect 5 V directly to Pi GPIO.

Research, channel-isolation controls and the verification matrix are documented
in [navigation/MOTOR_INVESTIGATION.md](navigation/MOTOR_INVESTIGATION.md).

---

## 📡 Sensors

### 1. LiDAR (Environment Mapping)
* **Model:** LD19 (LDROBOT)
* **Interface:** USB (via UART bridge)
* **Logic:** Continuous 360° scan at 10Hz. Angle 0 is aligned with the robot's front (X-axis).

### 2. IMU (Orientation)
* **Model:** MPU6050
* **Interface:** I2C (Bus 1)
* **Address:** 0x68
* **Pins:** SDA (BCM 2), SCL (BCM 3)
* **Usage:** Crucial for heading correction during rotation to compensate for Mecanum wheel slip.

### 3. Camera (Visual Support)
* **Model:** Pi Camera Module
* **Interface:** CSI
* **Note:** Mounted physically upside down; software compensates with a 180° transform.

## 💡 Semantic Usage Hints
* **Development:** Use `Simulation Mode` (automatically triggered if `pigpio` is missing) to test SLAM logic on a PC.
* **Calibration:** If the robot strafes left when it should strafe right, check the motor `dir_pin` assignments in `config.yaml`.
* **Performance:** Always ensure `sudo pigpiod` is running on boot, or the motors will not respond.
