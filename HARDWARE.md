# MateBot v2 Hardware Specifications

This document details the hardware components and wiring configuration for the MateBot v2 autonomous SLAM robot.

## 🧠 Core Controller
*   **Model:** Raspberry Pi 4 Model B
*   **OS:** Raspberry Pi OS (64-bit)
*   **Primary Software:** Python 3.12, FastAPI, pigpio daemon

## 🏎️ Locomotion & Actuators
*   **Configuration:** 4-Wheel Mecanum (Omnidirectional)
*   **Motors:** 4x Stepper Motors (NEMA 17, 1.8°/step)
*   **Drivers:** 4x DRV8825 or A4988 Stepper Drivers
*   **Microstepping:** 1/16 (Configured in `config.yaml`)

### Motor Pinout (BCM Numbering)
| Motor | Pin Function | BCM Pin |
| :--- | :--- | :--- |
| **Global** | Sleep / Enable | 26 |
| **Front Left** | Step | 9 |
| | Direction | 11 |
| **Front Right** | Step | 22 |
| | Direction | 10 |
| **Back Left** | Step | 13 |
| | Direction | 19 |
| **Back Right** | Step | 5 |
| | Direction | 6 |

## 📡 Sensors

### 1. LiDAR (Distance Sensing)
*   **Model:** LD19 (LDROBOT)
*   **Type:** 360° Time-of-Flight (ToF)
*   **Connection:** USB (via UART bridge)
*   **Default Port:** `/dev/ttyUSB0`
*   **Baudrate:** 230400 bps

### 2. IMU (Inertial Measurement)
*   **Model:** MPU6050
*   **Function:** 3-Axis Gyroscope & 3-Axis Accelerometer
*   **Connection:** I2C (Bus 1)
*   **I2C Address:** 0x68
*   **Wiring:**
    *   SDA: BCM 2 (Physical Pin 3)
    *   SCL: BCM 3 (Physical Pin 5)

### 3. Camera (Visual)
*   **Model:** Raspberry Pi Camera Module (v2/v3 compatible)
*   **Connection:** CSI Ribbon Cable
*   **Resolution:** 640x480 (configured for streaming)
*   **Orientation:** Mounted 180° rotated (corrected in `hardware/camera.py`)

## ⚡ Power System (Recommended)
*   **Battery:** 3S Li-Po (11.1V Nominal, 12.6V Max)
*   **Logic Power:** 5V/3A buck converter for Raspberry Pi
*   **Motor Power:** Direct battery voltage (12V range) to DRV8825 VMOT
*   **Safety:** Emergency stop via software logic (tilt detection & distance thresholds)
