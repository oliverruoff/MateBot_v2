import pigpio
import time
import math

WHEEL_DIAMETER_CM = 7.9
STEPS_PER_REV = 200
MICROSTEPS = 32
STEPS_PER_CM = (STEPS_PER_REV * MICROSTEPS) / (WHEEL_DIAMETER_CM * math.pi)

ENA_PIN = 26

MOTOR_PINS = {
    'FL': {'step': 9, 'dir': 11},
    'FR': {'step': 22, 'dir': 10},
    'BL': {'step': 13, 'dir': 19},
    'BR': {'step': 5, 'dir': 6}
}

DIR_FORWARD = 1
DIR_BACKWARD = 0

class MotorController:
    def __init__(self):
        try:
            self.pi = pigpio.pi()
            if not self.pi.connected:
                print("Failed to connect to pigpiod. Running in simulation mode.")
                self.simulation = True
            else:
                self.simulation = False
                self._initialize_pins()
        except Exception as e:
            print(f"Error initializing pigpio: {e}. Running in simulation mode.")
            self.simulation = True
            self.pi = None

        self.enabled = False
        self.base_speed = 1000

    def _initialize_pins(self):
        if self.simulation:
            return
        
        self.pi.set_mode(ENA_PIN, pigpio.OUTPUT)
        
        for motor, pins in MOTOR_PINS.items():
            self.pi.set_mode(pins['step'], pigpio.OUTPUT)
            self.pi.set_mode(pins['dir'], pigpio.OUTPUT)
            self.pi.write(pins['dir'], DIR_FORWARD)

    def enable(self):
        if self.simulation:
            print("Simulation: Motors enabled")
            self.enabled = True
            return
            
        self.pi.write(ENA_PIN, 0)
        self.enabled = True

    def disable(self):
        if self.simulation:
            print("Simulation: Motors disabled")
            self.enabled = False
            return
            
        self.pi.write(ENA_PIN, 1)
        self.enabled = False

    def _set_direction(self, motor, direction):
        if self.simulation:
            return
        dir_val = DIR_FORWARD if direction > 0 else DIR_BACKWARD
        self.pi.write(MOTOR_PINS[motor]['dir'], dir_val)

    def _move_motor(self, motor, steps, speed_hz=None):
        if self.simulation:
            print(f"Simulation: Motor {motor} moving {steps} steps")
            return
            
        if steps == 0:
            return
            
        dir_val = 1 if steps > 0 else 0
        self.pi.write(MOTOR_PINS[motor]['dir'], dir_val)
        
        steps = abs(steps)
        speed = speed_hz or self.base_speed
        self.pi.set_PWM_frequency(MOTOR_PINS[motor]['step'], speed)
        self.pi.set_PWM_dutycycle(MOTOR_PINS[motor]['step'], 128)
        
        delay = 1.0 / speed
        time.sleep(steps * delay)
        
        self.pi.set_PWM_dutycycle(MOTOR_PINS[motor]['step'], 0)

    def move_motors(self, fl_steps, fr_steps, bl_steps, br_steps, speed_hz=None):
        if not self.enabled:
            self.enable()
            
        speed = speed_hz or self.base_speed
        
        if self.simulation:
            print(f"Simulation: Moving FL:{fl_steps} FR:{fr_steps} BL:{bl_steps} BR:{br_steps} at {speed}Hz")
            time.sleep(0.5)
            return

        self._set_direction('FL', fl_steps)
        self._set_direction('FR', fr_steps)
        self._set_direction('BL', bl_steps)
        self._set_direction('BR', br_steps)
        
        steps = [abs(fl_steps), abs(fr_steps), abs(bl_steps), abs(br_steps)]
        max_steps = max(steps) if max(steps) > 0 else 1
        
        for motor, target_steps in zip(MOTOR_PINS.keys(), steps):
            if target_steps > 0:
                actual_steps = target_steps
                delay = actual_steps / speed
                self.pi.set_PWM_frequency(MOTOR_PINS[motor]['step'], speed)
                self.pi.set_PWM_dutycycle(MOTOR_PINS[motor]['step'], 128)
                time.sleep(delay)
        
        for motor in MOTOR_PINS.keys():
            self.pi.set_PWM_dutycycle(MOTOR_PINS[motor]['step'], 0)

    def move_distance(self, distance_cm, speed_hz=None):
        steps = int(distance_cm * STEPS_PER_CM)
        self.move_motors(steps, steps, steps, steps, speed_hz)

    def strafe_distance(self, distance_cm, speed_hz=None):
        steps = int(distance_cm * STEPS_PER_CM)
        self.move_motors(-steps, steps, steps, -steps, speed_hz)

    def rotate_angle(self, angle_deg, speed_hz=None):
        pass

    def stop(self):
        if self.simulation:
            print("Simulation: Motors stopped")
            return
            
        for motor in MOTOR_PINS.keys():
            self.pi.set_PWM_dutycycle(MOTOR_PINS[motor]['step'], 0)
        self.disable()

if __name__ == "__main__":
    m = MotorController()
    m.enable()
    print("Moving forward 10cm...")
    m.move_distance(10)
    print("Done")
