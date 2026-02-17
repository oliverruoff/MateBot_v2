import threading
import time
from src.hardware.motors import MotorController
from src.hardware.imu import IMUHandler

class Robot:
    def __init__(self):
        self.motors = MotorController()
        self.imu = IMUHandler()
        self.is_moving = False
        self.stop_flag = threading.Event()
        self.current_task = None

    def _validate_heading(self, target_heading, tolerance=2.0):
        current_heading = self.imu.get_yaw()
        return abs(current_heading - target_heading) < tolerance

    def move_forward(self, speed=None):
        self.motors.enable()
        self.motors.move_distance(1, speed)

    def move_backward(self, speed=None):
        self.motors.enable()
        self.motors.move_distance(-1, speed)

    def strafe_left(self, speed=None):
        self.motors.enable()
        self.motors.strafe_distance(-1, speed)

    def strafe_right(self, speed=None):
        self.motors.enable()
        self.motors.strafe_distance(1, speed)

    def rotate_left(self, speed=None):
        self.motors.enable()
        self.motors.move_motors(100, -100, 100, -100, speed)

    def rotate_right(self, speed=None):
        self.motors.enable()
        self.motors.move_motors(-100, 100, -100, 100, speed)

    def stop(self):
        self.stop_flag.set()
        self.motors.stop()
        self.is_moving = False

    def move_precise(self, distance_cm, direction='forward', speed=1000):
        self.stop_flag.clear()
        self.is_moving = True
        
        if direction not in ['forward', 'backward', 'left', 'right']:
            self.is_moving = False
            return {'success': False, 'error': 'Invalid direction'}
        
        target_heading = self.imu.get_yaw()
        
        def movement_task():
            steps = int(abs(distance_cm) * 57.32)
            
            if direction == 'forward':
                self.motors.move_motors(steps, steps, steps, steps, speed)
            elif direction == 'backward':
                self.motors.move_motors(-steps, -steps, -steps, -steps, speed)
            elif direction == 'left':
                self.motors.move_motors(-steps, steps, steps, -steps, speed)
            elif direction == 'right':
                self.motors.move_motors(steps, -steps, -steps, steps, speed)
            
            self.is_moving = False
        
        thread = threading.Thread(target=movement_task)
        thread.start()
        
        return {'success': True, 'message': f'Moving {direction} {distance_cm}cm'}

    def turn_precise(self, angle, direction='left', speed=1000):
        self.stop_flag.clear()
        self.is_moving = True
        
        if direction not in ['left', 'right']:
            self.is_moving = False
            return {'success': False, 'error': 'Invalid direction'}
        
        self.imu.reset_yaw()
        
        target_angle = abs(angle)
        direction_multiplier = 1 if direction == 'left' else -1
        
        def rotation_task():
            current_yaw = 0
            while abs(current_yaw) < target_angle and not self.stop_flag.is_set():
                self.motors.enable()
                self.motors.move_motors(
                    -100 * direction_multiplier,
                    100 * direction_multiplier,
                    -100 * direction_multiplier,
                    100 * direction_multiplier,
                    speed
                )
                time.sleep(0.05)
                current_yaw = abs(self.imu.get_yaw())
            
            self.motors.stop()
            self.is_moving = False
        
        thread = threading.Thread(target=rotation_task)
        thread.start()
        
        return {'success': True, 'message': f'Turning {direction} {angle} degrees'}

    def get_status(self):
        return {
            'moving': self.is_moving,
            'heading': self.imu.get_yaw()
        }

robot_instance = None

def get_robot():
    global robot_instance
    if robot_instance is None:
        robot_instance = Robot()
    return robot_instance
