import time
import threading
import config

try:
    import pigpio
    PIGPIO_AVAILABLE = True
except ImportError:
    PIGPIO_AVAILABLE = False

class MotorController:
    def __init__(self):
        self.simulation = not PIGPIO_AVAILABLE or config.SIMULATION_MODE
        
        # Use single frequency for all motors (like main branch)
        self.target_frequency = 0
        self.current_frequency = 0
        self.accel_step = 400  # Hz per step
        self.max_frequency = 8000
        self.test_frequency = None  # Allow override from web UI
        
        if not self.simulation:
            self.pi = pigpio.pi()
            if not self.pi.connected:
                self.simulation = True
        
        if not self.simulation:
            # Setup all pins
            self.pi.set_mode(config.MOTOR_SLEEP_PIN, pigpio.OUTPUT)
            for pin in [config.FRONT_LEFT_DIR, config.FRONT_RIGHT_DIR,
                       config.BACK_LEFT_DIR, config.BACK_RIGHT_DIR]:
                self.pi.set_mode(pin, pigpio.OUTPUT)
            
            for pin in [config.FRONT_LEFT_STEP, config.FRONT_RIGHT_STEP,
                       config.BACK_LEFT_STEP, config.BACK_RIGHT_STEP]:
                self.pi.set_mode(pin, pigpio.OUTPUT)
                self.pi.set_PWM_dutycycle(pin, 0)
            
            # Enable motors
            self._enable()
            
            # Start ramping thread
            self.running = True
            self.ramp_thread = threading.Thread(target=self._ramping_loop, daemon=True)
            self.ramp_thread.start()
        else:
            print("MotorController running in SIMULATION mode.")

    def _enable(self):
        if not self.simulation:
            # Active low: 0 = enabled
            self.pi.write(config.MOTOR_SLEEP_PIN, pigpio.LOW)
            time.sleep(0.1)

    def _disable(self):
        if not self.simulation:
            self.pi.write(config.MOTOR_SLEEP_PIN, pigpio.HIGH)

    def _set_dirs(self, fl, fr, bl, br):
        """Set direction pins (0 or 1)"""
        if not self.simulation:
            # Right side inverted
            self.pi.write(config.FRONT_LEFT_DIR, fl)
            self.pi.write(config.FRONT_RIGHT_DIR, 1-fr)  # Inverted
            self.pi.write(config.BACK_LEFT_DIR, bl)
            self.pi.write(config.BACK_RIGHT_DIR, 1-br)   # Inverted

    def _apply_frequency(self, freq):
        """Apply same frequency to all motors"""
        if self.simulation:
            return
        
        for pin in [config.FRONT_LEFT_STEP, config.FRONT_RIGHT_STEP,
                   config.BACK_LEFT_STEP, config.BACK_RIGHT_STEP]:
            if freq > 0:
                self.pi.set_PWM_frequency(pin, int(freq))
                self.pi.set_PWM_dutycycle(pin, 128)
            else:
                self.pi.set_PWM_dutycycle(pin, 0)

    def _ramping_loop(self):
        """Background thread for smooth ramping"""
        while self.running:
            if self.current_frequency != self.target_frequency:
                if self.current_frequency < self.target_frequency:
                    self.current_frequency = min(self.current_frequency + self.accel_step, 
                                                self.target_frequency)
                else:
                    self.current_frequency = max(self.current_frequency - (self.accel_step * 2), 
                                                self.target_frequency)
                self._apply_frequency(self.current_frequency)
            time.sleep(0.02)  # 50Hz update rate

    def set_speeds(self, fl, fr, bl, br):
        """Set motor speeds - use max speed as frequency, set directions individually"""
        # Find max speed
        max_speed = max(abs(fl), abs(fr), abs(bl), abs(br))
        
        if max_speed < 10:
            # Stop
            self.target_frequency = 0
            return
        
        # Calculate normalized directions (0 or 1)
        dir_fl = 1 if fl > 0 else 0
        dir_fr = 1 if fr > 0 else 0
        dir_bl = 1 if bl > 0 else 0
        dir_br = 1 if br > 0 else 0
        
        # Set directions
        self._set_dirs(dir_fl, dir_fr, dir_bl, dir_br)
        
        # Use test frequency if set, otherwise calculate from speed
        if self.test_frequency is not None:
            self.target_frequency = self.test_frequency
        else:
            target_freq = min(max_speed, self.max_frequency)
            self.target_frequency = max(target_freq, 100)

    def set_enabled(self, enabled):
        if enabled:
            self._enable()
        else:
            self._disable()

    def update_ramping(self):
        """Ramping handled in background thread"""
        pass

    def stop(self):
        self.target_frequency = 0
        self.current_frequency = 0
        self.test_frequency = None
        self._apply_frequency(0)
        self._disable()

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