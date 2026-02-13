import time
import config

try:
    import pigpio
    PIGPIO_AVAILABLE = True
except ImportError:
    PIGPIO_AVAILABLE = False

class MotorController:
    def __init__(self):
        self.simulation = not PIGPIO_AVAILABLE or config.SIMULATION_MODE
        
        # Ramping state
        self.current_speeds = [0.0, 0.0, 0.0, 0.0] # FL, FR, BL, BR
        self.target_speeds = [0.0, 0.0, 0.0, 0.0]
        self.accel_limit = 20000.0 # Match main branch's aggressiveness
        self.dt = 1.0 / config.MOTION_CYCLE_HZ
        
        if not self.simulation:
            self.pi = pigpio.pi()
            if not self.pi.connected:
                self.simulation = True
        
        if not self.simulation:
            self.pins = {
                'sleep': config.MOTOR_SLEEP_PIN,
                'fl_step': config.FRONT_LEFT_STEP, 'fl_dir': config.FRONT_LEFT_DIR,
                'fr_step': config.FRONT_RIGHT_STEP, 'fr_dir': config.FRONT_RIGHT_DIR,
                'bl_step': config.BACK_LEFT_STEP, 'bl_dir': config.BACK_LEFT_DIR,
                'br_step': config.BACK_RIGHT_STEP, 'br_dir': config.BACK_RIGHT_DIR,
            }
            for pin in self.pins.values():
                self.pi.set_mode(pin, pigpio.OUTPUT)
            
            self.set_enabled(False) 
        else:
            print("MotorController running in SIMULATION mode.")

    def set_enabled(self, enabled):
        if self.simulation: return
        # Active-Low: 0 = Enable, 1 = Sleep
        state = pigpio.LOW if enabled else pigpio.HIGH
        self.pi.write(config.MOTOR_SLEEP_PIN, state)

    def update_ramping(self):
        """Called at MOTION_CYCLE_HZ to update current speeds towards targets"""
        for i in range(4):
            diff = self.target_speeds[i] - self.current_speeds[i]
            max_change = self.accel_limit * self.dt
            
            if abs(diff) < max_change:
                self.current_speeds[i] = self.target_speeds[i]
            else:
                self.current_speeds[i] += max_change if diff > 0 else -max_change
                
        if not self.simulation:
            self._apply_hw_speeds()

    def set_speeds(self, fl, fr, bl, br):
        """Set target speeds in pulses per second (Hz)"""
        self.target_speeds = [fl, fr, bl, br]

    def _apply_hw_speeds(self):
        # Left side: speed > 0 is Forward (LOW)
        # Right side: speed > 0 is Forward (HIGH)
        self._set_motor_hw(config.FRONT_LEFT_STEP, config.FRONT_LEFT_DIR, self.current_speeds[0], invert=False)
        self._set_motor_hw(config.FRONT_RIGHT_STEP, config.FRONT_RIGHT_DIR, self.current_speeds[1], invert=True)
        self._set_motor_hw(config.BACK_LEFT_STEP, config.BACK_LEFT_DIR, self.current_speeds[2], invert=False)
        self._set_motor_hw(config.BACK_RIGHT_STEP, config.BACK_RIGHT_DIR, self.current_speeds[3], invert=True)

    def _set_motor_hw(self, step_pin, dir_pin, speed, invert=False):
        if not invert:
            direction = pigpio.LOW if speed >= 0 else pigpio.HIGH
        else:
            direction = pigpio.HIGH if speed >= 0 else pigpio.LOW
            
        self.pi.write(dir_pin, direction)
        abs_speed = int(abs(speed))
        if abs_speed > 20: 
            self.pi.set_PWM_frequency(step_pin, abs_speed)
            self.pi.set_PWM_dutycycle(step_pin, 128)
        else:
            self.pi.set_PWM_dutycycle(step_pin, 0)

    def stop(self):
        self.target_speeds = [0.0, 0.0, 0.0, 0.0]

class MecanumKinematics:
    def __init__(self):
        self.lx = config.ROBOT_LENGTH / 2
        self.ly = config.ROBOT_WIDTH / 2
        self.r = config.WHEEL_RADIUS
        self.steps_per_rev = 200 * 16

    def inverse_kinematics(self, vx, vy, omega):
        fl = (vx - vy - (self.lx + self.ly) * omega) / self.r
        fr = (vx + vy + (self.lx + self.ly) * omega) / self.r
        bl = (vx + vy - (self.lx + self.ly) * omega) / self.r
        br = (vx - vy + (self.lx + self.ly) * omega) / self.r
        
        scale = self.steps_per_rev / (2 * 3.14159)
        return fl * scale, fr * scale, bl * scale, br * scale
