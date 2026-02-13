import multiprocessing
import time
import signal
import sys
import os

import config
from src.utils.shared_mem import MapSharedMemory
from src.hardware.motors import MotorController, MecanumKinematics
from src.hardware.lidar import LidarSensor
from src.hardware.mpu import MPU6050
from src.navigation.slam import SlamProcessor
from web.server import run_server

DEBUG_FILE = "/home/matebot/develop/MateBot_v2/debug.log"

def log_debug(msg):
    try:
        with open(DEBUG_FILE, "a") as f:
            f.write(f"[{time.ctime()}] {msg}\n")
    except:
        pass

def process_a_motion(queue_motors):
    log_debug("MOTION: Process Starting")
    try:
        motors = MotorController()
        kinematics = MecanumKinematics()
        imu = MPU6050()
        log_debug("MOTION: Hardware initialized")
        
        last_command_time = time.time()
        current_vx, current_vy, current_omega = 0.0, 0.0, 0.0
        
        while True:
            # Check queue
            while not queue_motors.empty():
                cmd = queue_motors.get()
                if len(cmd) >= 4:
                    current_vx, current_vy, current_omega, freq = cmd
                    motors.test_frequency = freq  # Set test frequency
                else:
                    current_vx, current_vy, current_omega = cmd[:3]
                last_command_time = time.time()
                motors.set_enabled(True)
                log_debug(f"MOTION: CMD {current_vx}, {current_omega}, freq={motors.test_frequency}")
            
            # Timeout
            if time.time() - last_command_time > 1.0:
                current_vx, current_vy, current_omega = 0, 0, 0
            
            # Update motors
            fl, fr, bl, br = kinematics.inverse_kinematics(current_vx, current_vy, current_omega)
            motors.set_speeds(fl, fr, bl, br)
            motors.update_ramping()
            
            # Verify movement
            if abs(current_vx) > 0.01 or abs(current_omega) > 0.01:
                if int(time.time() * 2) % 2 == 0:
                    data = imu.get_data()
                    log_debug(f"VERIFY: vx={current_vx:.1f} | GyroZ={data['gyro']['z']:.2f}")
            
            time.sleep(1.0 / config.MOTION_CYCLE_HZ)
    except Exception as e:
        log_debug(f"MOTION: ERROR {e}")
    finally:
        log_debug("MOTION: Process Stopping")

def process_b_nav(queue_motors, queue_command):
    log_debug("NAV: Process Starting")
    try:
        lidar = LidarSensor() 
        slam = SlamProcessor()
        shm_map = MapSharedMemory(create=False)
        lidar.start()
        while True:
            # Check for commands (like reset map)
            try:
                while not queue_command.empty():
                    cmd = queue_command.get_nowait()
                    if cmd.get("action") == "reset_map":
                        log_debug("NAV: Resetting Map")
                        slam.reset_map()
            except Exception:
                pass

            scan = lidar.get_scan()
            slam.update(scan)
            shm_map.update_map(slam.get_map())
            time.sleep(1.0 / config.NAV_CYCLE_HZ)
    except Exception as e:
        log_debug(f"NAV: ERROR {e}")

def process_c_web(queue_motors, queue_command):
    log_debug("WEB: Process Starting")
    run_server(queue_motors, queue_command)

def main():
    if os.path.exists(DEBUG_FILE): os.remove(DEBUG_FILE)
    shm_map = MapSharedMemory(create=True)
    
    manager = multiprocessing.Manager()
    queue_motors = manager.Queue()
    queue_command = manager.Queue()
    
    p_a = multiprocessing.Process(target=process_a_motion, args=(queue_motors,))
    p_b = multiprocessing.Process(target=process_b_nav, args=(queue_motors, queue_command))
    p_c = multiprocessing.Process(target=process_c_web, args=(queue_motors, queue_command))
    
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    p_a.start()
    p_b.start()
    p_c.start()
    
    p_a.join()
    p_b.join()
    p_c.join()

if __name__ == "__main__":
    main()
