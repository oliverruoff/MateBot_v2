# Technical Specification: MateBot v2 "Pure Python" Edition

| Metadata | Details |
| :--- | :--- |
| **Version** | 4.1 (Revised) |
| **Target Hardware** | Raspberry Pi 4B (4GB+ recommended) |
| **OS** | Raspberry Pi OS (64-bit Bookworm) |
| **Language** | Python 3.11+ |
| **Core Libraries** | `pigpio`, `BreezySLAM`, `FastAPI`, `NumPy`, `pathfinding` |
| **Architecture** | Multi-Process (No ROS) |

---

## 1. System Overview
MateBot v2 moves away from ROS to a "Pure Python" architecture to reduce overhead and complexity. It utilizes Python's `multiprocessing` module to bypass the Global Interpreter Lock (GIL), creating three synchronized independent loops.

### The "Synchronized" Three-Process Model
1.  **Process A (Hardware & Motion):** High-priority motor control, odometry tracking, and safety enforcement.
2.  **Process B (SLAM & Vision):** Lidar ingestion, Simultaneous Localization and Mapping (SLAM), and path planning.
3.  **Process C (Web Interface):** User interaction, command ingestion, and map visualization streaming.

### Inter-Process Communication (IPC)
* **`SharedMemory_Map`:** A shared bytearray storing the live grid map (Writable by Process B, Readable by Process C).
* **`SharedValue_Odom`:** A struct containing `(x, y, theta, timestamp)` to ensure SLAM syncs with the correct movement moment.
* **`Queue_Command`:** A FIFO queue for sending velocity targets `(v_x, v_y, \omega)` from Web to Motors.

---

## 2. Hardware Layer
* **Motors:** 4x NEMA 17 Stepper Motors.
* **Drivers:** DRV8825 (Microstepping: 1/16 or 1/32 recommended).
* **Lidar:** LD19 (or LD06) connected via USB/Serial.
* **System Daemon:** The `pigpiod` daemon must be active.
    * *Command:* `sudo pigpiod -s 2` (2 microsecond sample rate for smooth pulses).

---

## 3. Software Components

### 3.1 Process A: The Motor Controller (Critical Safety)
**Library:** `pigpio`
**Objective:** Drive motors smoothly while maintaining accurate open-loop odometry.

#### Key Features:
1.  **Trapezoidal Velocity Ramping:**
    * To prevent stepper stall and wheel slip, velocity inputs must be ramped.
    * Acceleration Limit: Fixed constant (e.g., $0.5 m/s^2$).
    * *Logic:* Never apply `target_velocity` directly. Increment `current_velocity` towards target by `accel * dt`.
    

2.  **Safety Heartbeat (Dead Man's Switch):**
    * The loop monitors the timestamp of the last received command.
    * **Constraint:** If `(current_time - last_cmd_time) > 1.0s`, force all velocities to 0.

3.  **Timestamped Odometry:**
    * Update position based on *actual* ramped velocity, not target velocity.
    * $x_{new} = x_{old} + (v_x \cdot \cos(\theta) - v_y \cdot \sin(\theta)) \cdot dt$
    * **Output:** Write `(x, y, theta, time.time())` to IPC Shared Memory.

### 3.2 Process B: SLAM & Navigation
**Library:** `BreezySLAM` (CoreSLAM wrapper), `pathfinding`
**Objective:** Build a map and calculate paths.

#### SLAM Logic:
1.  **Ingest Lidar:** Read 360-point scan from serial port. Record `scan_timestamp`.
2.  **Fetch Odom:** Read `SharedValue_Odom`.
3.  **Synchronization Check:**
    * Calculate `latency = abs(scan_timestamp - odom_timestamp)`.
    * If `latency > 100ms`: Warn and extrapolate odometry to match scan time.
4.  **Update:** `slam.update(scan, pose_guess)`.
5.  **Map Write:** Update `SharedMemory_Map` with raw pixel data.

#### Navigation Logic (A*):
1.  **Downsampling:** Create a secondary "Navigation Grid" (10cm per pixel) from the main SLAM map (1cm per pixel) to reduce A* compute time.
2.  **Obstacle Inflation:** Dilate all wall pixels by `robot_radius` so the path planner treats walls as "thicker" (preventing collisions).
3.  **Algorithm:** Run A* on the Navigation Grid.
4.  **Execution:** Use "Pure Pursuit" to drive towards the calculated path nodes.

### 3.3 Process C: Web Interface
**Library:** `FastAPI`, `Uvicorn`
**Objective:** Low-latency control and visualization.

#### Map Streaming (Client-Side Rendering):
* **Server Side:** DO NOT compress images (PNG/JPG). Read `SharedMemory_Map` and send the raw binary `bytearray` (Gzip compressed) via WebSocket every 500ms.
* **Client Side:** JavaScript reads the binary stream and renders pixels directly onto an HTML5 `<canvas>`.
* **Benefit:** Reduces CPU load on the Raspberry Pi by ~30%.

---

## 4. Implementation Constraints & Mitigations

### 4.1 Coordinate Systems
* **Lidar Offset:** The Lidar is likely not at the exact center of rotation.
* **Math:** Points must be transformed:
    $$P_{global} = P_{robot} + R(\theta) \cdot P_{offset}$$

### 4.2 Startup & Shutdown
* **Startup:** `main.py` must initialize `pigpiod` connection first.
* **Shutdown:** A global signal handler (SIGINT/Ctrl+C) is required.
    * **Must Do:** Send "Disable" signal to motor drivers (cut current) to prevent motor overheating when idle.
    * **Must Do:** Unlink Shared Memory to prevent memory leaks in the OS.

### 4.3 Loop Closure
* **Limitation:** BreezySLAM is a particle filter but lacks global loop closure (graph optimization).
* **Mitigation:** The robot must be driven slowly during the initial mapping phase to ensure the particle filter does not diverge.

---

## 5. Development Roadmap

1.  **Step 1: Motors & Physics** (`motors.py`)
    * Implement ramping class.
    * Verify odometry math.
2.  **Step 2: Lidar Driver** (`lidar.py`)
    * Decode binary packets from LD19.
3.  **Step 3: SLAM Integration** (`slam_process.py`)
    * Feed Lidar + Odom into BreezySLAM.
4.  **Step 4: Web UI** (`server.py`)
    * Implement WebSocket binary streaming.