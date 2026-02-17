import sys
import time

sys.path.insert(0, '/home/matebot/develop/MateBot_v2/src')

from hardware.motors import MotorController
from hardware.imu import IMUHandler

def test_rotation():
    motor = MotorController()
    imu = IMUHandler()
    
    print("Enabling motors...")
    motor.enable()
    time.sleep(0.5)
    
    imu.reset_yaw()
    time.sleep(0.5)
    
    print("\n=== Testing ROTATE LEFT ===")
    start_heading = imu.get_yaw()
    print(f"Start heading: {start_heading:.2f}°")
    
    # Rotate left: FL and BL backward, FR and BR forward
    speed = 1000
    motor.move_motors(-2000, 2000, -2000, 2000, speed)
    
    time.sleep(1.0)
    left_heading = imu.get_yaw()
    left_change = left_heading - start_heading
    print(f"End heading: {left_heading:.2f}°")
    print(f"Heading change: {left_change:.2f}°")
    
    time.sleep(0.5)
    
    print("\n=== Testing ROTATE RIGHT ===")
    start_heading = imu.get_yaw()
    print(f"Start heading: {start_heading:.2f}°")
    
    # Rotate right: FL and BL forward, FR and BR backward
    motor.move_motors(2000, -2000, 2000, -2000, speed)
    
    time.sleep(1.0)
    right_heading = imu.get_yaw()
    right_change = right_heading - start_heading
    print(f"End heading: {right_heading:.2f}°")
    print(f"Heading change: {right_change:.2f}°")
    
    print("\n=== SUMMARY ===")
    print(f"Rotate LEFT resulted in heading change: {left_change:+.2f}°")
    print(f"Rotate RIGHT resulted in heading change: {right_change:+.2f}°")
    
    if left_change < 0:
        print("\nWARNING: 'LEFT' rotation resulted in NEGATIVE heading change (turning right)")
    else:
        print("\n'LEFT' rotation correctly resulted in positive heading change")
        
    if right_change > 0:
        print("WARNING: 'RIGHT' rotation resulted in POSITIVE heading change (turning left)")
    else:
        print("'RIGHT' rotation correctly resulted in negative heading change")
    
    motor.disable()

if __name__ == "__main__":
    test_rotation()
