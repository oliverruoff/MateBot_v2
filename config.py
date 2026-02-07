import os

# Hardware Pins (BCM)
MOTOR_SLEEP_PIN = 26

FRONT_LEFT_STEP = 9
FRONT_LEFT_DIR = 11

FRONT_RIGHT_STEP = 22
FRONT_RIGHT_DIR = 10

BACK_LEFT_STEP = 13
BACK_LEFT_DIR = 19

BACK_RIGHT_STEP = 5
BACK_RIGHT_DIR = 6

# Robot Dimensions / Physical Constants
WHEEL_RADIUS = 0.05  # 50mm
ROBOT_WIDTH = 0.3    # Distance between wheels (left-right)
ROBOT_LENGTH = 0.3   # Distance between wheels (front-back)

# Navigation Constants
MAP_RESOLUTION = 0.05  # 5cm per pixel
MAP_SIZE_PIXELS = 400  # 20m x 20m map
OBSTACLE_INFLATION = 0.2 # 20cm

# Process Cycles
MOTION_CYCLE_HZ = 50
NAV_CYCLE_HZ = 10

# Files
LOCATIONS_FILE = os.path.join(os.path.dirname(__file__), "locations.json")
MAP_SAVE_FILE = os.path.join(os.path.dirname(__file__), "map.bin")

# Simulation
SIMULATION_MODE = os.environ.get("MATEBOT_SIM", "0") == "1"
