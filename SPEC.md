# Technical Specification: MateBot v2 "Pure Python" Edition

| Metadata | Details |
| :--- | :--- |
| Project Name | MateBot v2 |
| Version | 4.3 (Structured & OS Updated) |
| Mission Profile | Domestic Transport Assistant (Multi-tier Cargo) |
| Target Hardware | Raspberry Pi 4B (4GB+ RAM recommended) |
| OS | Raspberry Pi OS (Raspbian) |
| Language | Python 3.11+ |
| Core Stack | multiprocessing, pigpio, BreezySLAM, FastAPI, NumPy |
| Architecture | Multi-Process (No ROS) |

---

## 1. System Overview & Mission

MateBot v2 moves away from ROS to an optimized "Pure Python" architecture.

Unlike standard vacuum robots, MateBot is designed as a heavy-duty domestic transport assistant. It features a larger chassis with multiple storage compartments (shelves) to transport items (e.g., laundry, groceries, tools) between specific rooms in a household.

### 1.1 The User Workflow (The "Use Case")

The system is designed around three distinct operational modes handled via the Web Interface:

1. **Mapping Mode (Setup Phase):**
   - **Action:** User manually drives the robot via a Virtual Joystick in the Web UI.
   - **System:** The Lidar scans the environment, and BreezySLAM builds a static occupancy grid map.
   - **Result:** A raw map file is saved to disk.

2. **Annotation Mode (Configuration Phase):**
   - **Action:** The user views the generated map in the Web Browser.
   - **Interaction:** The user clicks on a specific point on the map (e.g., in front of the sofa) and assigns a label (e.g., "Living Room").
   - **System:** The backend converts pixel coordinates to world coordinates ($x, y$) and saves them into a `locations.json` database.

3. **Service Mode (Transport Phase):**
   - **Action:** User loads items into the robot's cargo shelf.
   - **Command:** User selects "Kitchen" from a dropdown menu in the Web UI.
   - **System:** The robot plans a path using A* and navigates autonomously to the stored coordinate.

---

## 2. Software Architecture

To bypass the Python Global Interpreter Lock (GIL) and ensure motor timing stability, the system uses three synchronized, independent system processes.

### 2.1 The Process Model

1. **Process A (Hardware & Motion):**
   - **Priority:** Real-time / High.
   - **Responsibility:** Stepper motor pulse generation, Odometry tracking, Safety checks.
   - **Cycle Time:** Fixed 50Hz (20ms).

2. **Process B (SLAM & Navigation):**
   - **Priority:** Computation / Medium.
   - **Responsibility:** Lidar ingestion, Map updates, Pathfinding (A*), Trajectory calculation.
   - **Cycle Time:** Variable (depends on Lidar scan rate, approx. 10Hz).

3. **Process C (User Interface):**
   - **Priority:** I/O / Low.
   - **Responsibility:** Web Server (FastAPI), Map Streaming, API endpoints.
   - **Cycle Time:** Event-driven.

### 2.2 Inter-Process Communication (IPC)

- **SharedMemory_Map:** A shared bytearray storing the live grid map (Writable by B, Readable by C).
- **Queue_Command:** A FIFO queue for sending navigation goals from Web to Nav.
- **Queue_Motors:** A FIFO queue for sending velocity targets (v, omega) from Nav to Motors.

---

## 3. Hardware

- **Chassis:** Custom transport frame with >2kg payload
- **Motors:** 4x NEMA 17 Stepper Motors (High torque)
- **Drivers:** DRV8825 (1/32 Microstepping for smooth motion)
- **Lidar:** LD19 or LD06 (USB)
- **Power:** 3S or 4S LiPo Battery (with buck converter for Pi).

---

## 4. Implementation Phasing

### Phase 1: Standalone Operation (Current)

- **Goal:** A fully functional robot controllable exclusively via the hosted Web UI.
- **Requirements:**
  - [ ] Manual Driving (Joystick)
  - [ ] Live Mapping Visualization
  - [ ] Point of Interest (POI) Manager: Click-to-save locations
  - [ ] Autonomous Navigation to saved POIs
- **Constraint:** No external API integrations.

### Phase 2: Smart Home Integration (Future Scope)

- **Goal:** Headless integration into Home Assistant (HA).
- **Requirements:**
  - [ ] REST API endpoints for HA to poll position
  - [ ] MQTT Bridge for status updates (Battery, Status)
  - [ ] API Trigger: `POST /api/go_to` with body `{ "location": "Kitchen" }`
- **Note:** The architecture in Phase 1 must define the data structures (JSON) cleanly so Phase 2 is just an "Add-on".

---

## 5. Component Details

### 5.1 Process A: Motion Control (Critical Safety)

**Library:** `pigpio`

- **Ramping:** Implements trapezoidal velocity ramping. If the robot accelerates too fast, the heavy cargo might cause it to tip or lose steps.
- **Max Accel:** $0.3 m/s^2$ (Conservative for payload).
- **Dead Man's Switch:** If no command is received for >1.0s, motors perform a hard stop.

### 5.2 Process B: SLAM & Pathfinding

**Library:** `BreezySLAM` (Mapping), `pathfinding` (A*)

- **Map Resolution:** 5cm per pixel (0.05m).
- **Obstacle Inflation:** Before running A*, walls are "thickened" by the robot's radius + 5cm buffer to ensure the chassis doesn't scrape walls.
- **Navigation Logic:**
  1. Get Target $(x, y)$
  2. Plan Path (A* on static map)
  3. Follow Path (Pure Pursuit controller)

### 5.3 Process C: Web Interface

**Library:** `FastAPI`, `Uvicorn`

- **Map Rendering:** Client-side (JavaScript) rendering of raw binary map data on HTML5 Canvas.
- **POI Database (`locations.json`):**

```json
{
  "locations": [
    {
      "id": "loc_001",
      "name": "Kitchen Counter",
      "x": 4.5,
      "y": 1.2,
      "theta": 1.57,
      "created_at": "2023-10-27T10:00:00"
    }
  ]
}
```

---

## 6. Project Structure & Code Organization

The project must adhere to a strict directory structure to ensure separation of concerns between backend logic, API endpoints, and frontend resources.

### 6.1 Directory Tree

```text
MateBot_v2/
├── README.md                 # ALWAYS UP TO DATE (Install steps, API usage)
├── requirements.txt          # Python dependencies
├── main.py                   # Entry Point (Starts Processes A, B, C)
├── config.py                 # Global constants (Pins, Dimensions)
├── src/                      # CORE PYTHON LOGIC (No API code here)
│   ├── __init__.py
│   ├── hardware/
│   │   ├── motors.py         # Stepper control & Ramping logic
│   │   └── lidar.py          # Serial data decoding
│   ├── navigation/
│   │   ├── slam.py           # BreezySLAM wrapper
│   │   └── pathfinding.py    # A* and Pure Pursuit logic
│   └── utils/
│       └── shared_mem.py     # Shared Memory management
└── web/                      # WEB INTERFACE (Process C)
    ├── server.py             # FastAPI App & Endpoints ONLY
    └── static/               # FRONTEND ASSETS
        ├── html/
        │   └── index.html    # Semantic HTML structure ONLY (No inline JS/CSS)
        ├── css/
        │   ├── main.css      # Layout & Global Styles
        │   └── components.css
        └── js/
            ├── app.js        # Main logic & WebSocket handling
            ├── map_render.js # Canvas drawing logic
            └── joystick.js   # Input handling
```

### 6.2 Separation of Concerns Rules

- **Python (Backend) `src/`:** Contains pure logic (business logic). These files must not depend on FastAPI. They should be testable in isolation.
- **`web/server.py`:** Contains only FastAPI routing, WebSocket handling, and API definitions. It imports logic from `src/`. It does not contain motor driving code directly.

---

## 7. Frontend Asset Rules (Phase 1)

**Web (Frontend)**

- **HTML (`web/static/html/`):** Contains strictly semantic HTML5 markup.
  - **Forbidden:** No `<script>...</script>` blocks with logic.
  - **Forbidden:** No `<style>...</style>` blocks.
  - Must link to external assets via standard `<link>` and `<script src="...">` tags.

- **CSS (`web/static/css/`):** Contains all styling rules.
  - No inline styles in HTML.

- **JavaScript (`web/static/js/`):** Contains all client-side logic.
  - Responsible for DOM manipulation, WebSocket communication, and Canvas drawing.

---

## 8. API Specification (Internal for Phase 1)

Although Phase 2 brings full external APIs, Phase 1 requires internal endpoints for the Web UI.

- `GET /api/map` — Returns map status/metadata
- `POST /api/poi` — Save current location as POI
  - Payload: `{ "name": "Kitchen" }`
- `GET /api/poi` — List all saved POIs
- `POST /api/navigate` — Command robot to move
  - Payload: `{ "target_id": "loc_001" }`

---

## 9. Constraints & Mitigations

- **Coordinate Systems:**
  - **Lidar Offset:** Transform points from $P_{lidar}$ to $P_{center}$ before mapping.

- **Startup/Shutdown:**
  - **Startup:** `pigpiod` must be running before Python script starts.
  - **Shutdown:** Must catch SIGINT to safely stop motors (disable drivers) and unlink Shared Memory.

- **Data Persistence:**
  - Map and POI JSON must be saved to disk periodically or upon specific "Save" actions in the UI.
