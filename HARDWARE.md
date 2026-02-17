# MateBot v2 Hardware Specifications

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
* **Motors:** 4x Stepper Motors (**NEMA 23**, 1.8° per full step)
* **Drivers:** 4x **TB6600 Stepper Drivers**
* **Microstepping:** Configured to **1/32** for high precision / smooth motion.
* **Driver Configuration (DIP Switches):**
    * **Microstep (S1, S2, S3):** `OFF, OFF, OFF` (1/32 Step)
    * **Current (S4, S5, S6):** `OFF, OFF, ON` (~3.5A Peak / 3.3A RMS)

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
1.  **Hardware PWM is Mandatory:** Using software-timed loops for high-frequency stepping (e.g., 1/32 microstepping requires double the frequency of 1/16) leads to jitter and stalled motors.
2.  **The `pigpio` Strategy:** * We use the `pigpio` daemon to handle hardware-timed pulses.
    * **Frequency Control:** Instead of manual bit-banging, we use `pi.set_PWM_frequency(step_pin, frequency_hz)`.
    * **Duty Cycle:** Set to `128` (50%) to generate the clock signal.
3.  **The Enable Pin:** All drivers share BCM 26 connected to `ENA`.
    * *Note for TB6600:* Check logic level. Often leaving ENA disconnected is "Enabled". If wired, ensure correct HIGH/LOW logic (usually Active Low for enabling on some clones, Active High on others).
4.  **Direction Calibration:** Every motor's orientation may vary. Use the `direction_multiplier: 1` or `-1` in `config.yaml` to calibrate forward/backward without rewiring.

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