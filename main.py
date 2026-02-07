import multiprocessing
import time
import signal
import sys
import os

import config
from src.utils.shared_mem import MapSharedMemory
from src.hardware.motors import MotorController, MecanumKinematics
from src.hardware.lidar import LidarSensor
from src.navigation.slam import SlamProcessor
from src.navigation.pathfinding import PathPlanner, PurePursuitController
from web.server import run_server

def process_a_motion(queue_motors):
    """Process A: Hardware & Motion (50Hz)"""
    print("Process A (Motion) started.")
    motors = MotorController()
    kinematics = MecanumKinematics()
    
    last_command_time = time.time()
    current_vx, current_vy, current_omega = 0.0, 0.0, 0.0
    
    try:
        while True:
            # Get latest command from queue
            try:
                # Check for multiple commands and take the last one
                while not queue_motors.empty():
                    current_vx, current_vy, current_omega = queue_motors.get_nowait()
                    last_command_time = time.time()
                    motors.set_enabled(True)
            except Exception:
                pass
            
            # Dead man's switch
            if time.time() - last_command_time > 1.0:
                current_vx, current_vy, current_omega = 0, 0, 0
                motors.stop()
            
            # Calculate wheel speeds
            fl, fr, bl, br = kinematics.inverse_kinematics(current_vx, current_vy, current_omega)
            motors.set_speeds(fl, fr, bl, br)
            
            time.sleep(1.0 / config.MOTION_CYCLE_HZ)
    except KeyboardInterrupt:
        motors.stop()

def process_b_nav(queue_motors, queue_command):
    """Process B: SLAM & Navigation (10Hz)"""
    print("Process B (Navigation) started.")
    lidar = LidarSensor()
    slam = SlamProcessor()
    planner = PathPlanner()
    controller = PurePursuitController()
    shm_map = MapSharedMemory(create=False) # Created by main
    
    lidar.start()
    
    try:
        while True:
            # 1. SLAM update
            scan = lidar.get_scan()
            x, y, theta = slam.update(scan)
            
            # 2. Update Shared Memory Map
            shm_map.update_map(slam.get_map())
            
            # 3. Handle Commands
            try:
                if not queue_command.empty():
                    cmd = queue_command.get_nowait()
                    # Handle navigate commands etc.
            except Exception:
                pass
                
            # 4. Path following (Stub: just pass manual joystick if any)
            # In a real system, we'd calculate vx, vy, omega here for autonomous navigation
            
            time.sleep(1.0 / config.NAV_CYCLE_HZ)
    except KeyboardInterrupt:
        lidar.stop()

def process_c_web(queue_motors, queue_command):
    """Process C: User Interface"""
    print("Process C (Web UI) started.")
    run_server(queue_motors, queue_command)

def main():
    # Initialize Shared Memory
    shm_map = MapSharedMemory(create=True)
    
    # IPC Queues
    queue_motors = multiprocessing.Queue()
    queue_command = multiprocessing.Queue()
    
    # Processes
    p_a = multiprocessing.Process(target=process_a_motion, args=(queue_motors,))
    p_b = multiprocessing.Process(target=process_b_nav, args=(queue_motors, queue_command))
    p_c = multiprocessing.Process(target=process_c_web, args=(queue_motors, queue_command))
    
    def signal_handler(sig, frame):
        print("\nShutting down MateBot v2...")
        p_a.terminate()
        p_b.terminate()
        p_c.terminate()
        shm_map.unlink()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    p_a.start()
    p_b.start()
    p_c.start()
    
    p_a.join()
    p_b.join()
    p_c.join()

if __name__ == "__main__":
    main()
