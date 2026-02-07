# MateBot v2

Domestic Transport Assistant with Pure Python architecture.

## Architecture
- **Process A (Motion):** Handles high-frequency stepper pulse generation (via pigpio) and ramping.
- **Process B (Navigation):** Handles Lidar data, SLAM (BreezySLAM), and A* Pathfinding.
- **Process C (Web UI):** FastAPI server providing a control dashboard and API.

## Installation
1. Install system dependencies:
   ```bash
   sudo apt update
   sudo apt install python3-pip pigpio
   sudo systemctl enable pigpiod
   sudo systemctl start pigpiod
   ```
2. Install Python requirements:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
Run the main entry point:
```bash
python3 main.py
```
Access the UI at `http://<pi-ip>:8000`.

## Simulation Mode
To run without physical hardware:
```bash
MATEBOT_SIM=1 python3 main.py
```

## Directory Structure
- `src/hardware/`: Low-level drivers (Motors, Lidar).
- `src/navigation/`: SLAM and Pathfinding logic.
- `src/utils/`: Shared memory and common helpers.
- `web/`: FastAPI server and frontend assets.
