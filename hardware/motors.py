import time
import threading
import pigpio
import toml
import sys

class RobotMover:
    def __init__(self, config_path="config.toml"):
        print(f"RobotMover: Initializing with {config_path}", file=sys.stderr)
        try:
            with open(config_path, "r") as f:
                self.config = toml.load(f)
            
            self.pins = self.config["motors"]
            self.active_low = self.pins.get("active_low", True)
            
            # Convert delay to frequency
            self.target_frequency = 8000 
            self.current_frequency = 0
            self.current_command = None
            
            self.pi = pigpio.pi()
            if not self.pi.connected:
                print("ERROR: Could not connect to pigpiod daemon!", file=sys.stderr)
                raise Exception("pigpiod not running")
            
            # Setup pins
            self.pi.set_mode(self.pins["sleep_pin"], pigpio.OUTPUT)
            self.motor_keys = ["fl", "fr", "bl", "br"]
            
            for key in self.motor_keys:
                self.pi.set_mode(self.pins[key]["dir"], pigpio.OUTPUT)
                self.pi.set_mode(self.pins[key]["step"], pigpio.OUTPUT)
                self.pi.set_PWM_dutycycle(self.pins[key]["step"], 0)
                
            self.activate()
            
            # Ramping thread
            self.running = True
            self.ramp_thread = threading.Thread(target=self._ramping_loop, daemon=True)
            self.ramp_thread.start()
            
            print("RobotMover: Hardware PWM with Ramping initialized.", file=sys.stderr)
            
        except Exception as e:
            print(f"RobotMover INIT ERROR: {e}", file=sys.stderr)
            raise

    def activate(self):
        state = 0 if self.active_low else 1
        self.pi.write(self.pins["sleep_pin"], state)
        time.sleep(0.1)

    def deactivate(self):
        state = 1 if self.active_low else 0
        self.pi.write(self.pins["sleep_pin"], state)

    def set_delay(self, new_delay):
        try:
            new_freq = int(1.0 / (float(new_delay) * 2))
            self.target_frequency = min(max(new_freq, 100), 15000)
            print(f"RobotMover: Target frequency updated to {self.target_frequency}Hz", file=sys.stderr)
        except:
            pass

    def set_command(self, command):
        if command == self.current_command:
            return
            
        if not command or command == "stop":
            self.current_command = None
            return

        # Set directions immediately
        if command == "forward": self._set_dirs(0, 1, 0, 1)
        elif command == "backward": self._set_dirs(1, 0, 1, 0)
        elif command == "left": self._set_dirs(1, 1, 1, 1)
        elif command == "right": self._set_dirs(0, 0, 0, 0)
        elif command == "strafe_left": self._set_dirs(1, 1, 0, 0)
        elif command == "strafe_right": self._set_dirs(0, 0, 1, 1)
        
        self.current_command = command

    def _set_dirs(self, fl, fr, bl, br):
        self.pi.write(self.pins["fl"]["dir"], fl)
        self.pi.write(self.pins["fr"]["dir"], fr)
        self.pi.write(self.pins["bl"]["dir"], bl)
        self.pi.write(self.pins["br"]["dir"], br)

    def _apply_frequency(self, freq):
        for key in self.motor_keys:
            pin = self.pins[key]["step"]
            if freq > 0:
                self.pi.set_PWM_frequency(pin, freq)
                self.pi.set_PWM_dutycycle(pin, 128) # 50% duty
            else:
                self.pi.set_PWM_dutycycle(pin, 0)

    def _ramping_loop(self):
        """ Gradually increase/decrease frequency for smoothness """
        accel_step = 400 
        while self.running:
            target = self.target_frequency if self.current_command else 0
            if self.current_frequency != target:
                if self.current_frequency < target:
                    self.current_frequency = min(self.current_frequency + accel_step, target)
                else:
                    self.current_frequency = max(self.current_frequency - (accel_step * 2), target)
                self._apply_frequency(self.current_frequency)
            time.sleep(0.02)

    def cleanup(self):
        self.running = False
        self._apply_frequency(0)
        self.deactivate()
        if hasattr(self, 'pi'):
            self.pi.stop()
