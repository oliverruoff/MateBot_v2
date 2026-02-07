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
        if not self.simulation:
            self.pi = pigpio.pi()
            if not self.pi.connected:
                print("Failed to connect to pigpiod. Switching to simulation mode.")
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
        self.pi.write(config.MOTOR_SLEEP_PIN, pigpio.HIGH if enabled else pigpio.LOW)

    def set_speeds(self, fl, fr, bl, br):
        """Set motor speeds in pulses per second (Hz)"""
        if self.simulation:
            # print(f"SIM: Motors FL:{fl} FR:{fr} BL:{bl} BR:{br}")
            return

        self._set_motor_hw(config.FRONT_LEFT_STEP, config.FRONT_LEFT_DIR, fl)
        self._set_motor_hw(config.FRONT_RIGHT_STEP, config.FRONT_RIGHT_DIR, fr)
        self._set_motor_hw(config.BACK_LEFT_STEP, config.BACK_LEFT_DIR, bl)
        self._set_motor_hw(config.BACK_RIGHT_STEP, config.BACK_RIGHT_DIR, br)

    def _set_motor_hw(self, step_pin, dir_pin, speed):
        direction = pigpio.HIGH if speed >= 0 else pigpio.LOW
        self.pi.write(dir_pin, direction)
        abs_speed = int(abs(speed))
        if abs_speed > 0:
            self.pi.set_PWM_frequency(step_pin, abs_speed)
            self.pi.set_PWM_dutycycle(step_pin, 128)
        else:
            self.pi.set_PWM_dutycycle(step_pin, 0)

    def stop(self):
        self.set_speeds(0, 0, 0, 0)
        self.set_enabled(False)

class MecanumKinematics:
    def __init__(self):
        # Parameters for Mecanum drive
        self.lx = config.ROBOT_LENGTH / 2
        self.ly = config.ROBOT_WIDTH / 2
        self.r = config.WHEEL_RADIUS
        self.steps_per_rev = 200 * 16 # 1.8 deg * 1/16 microstepping

    def inverse_kinematics(self, vx, vy, omega):
        """Convert robot velocity (m/s, rad/s) to motor speeds (steps/s)"""
        # vx: forward, vy: strafe right, omega: rotation CCW
        fl = (vx - vy - (self.lx + self.ly) * omega) / self.r
        fr = (vx + vy + (self.lx + self.ly) * omega) / self.r
        bl = (vx + vy - (self.lx + self.ly) * omega) / self.r
        br = (vx - vy + (self.lx + self.ly) * omega) / self.r
        
        # Convert rad/s of wheel to steps/s
        scale = self.steps_per_rev / (2 * 3.14159)
        return fl * scale, fr * scale, bl * scale, br * scale
