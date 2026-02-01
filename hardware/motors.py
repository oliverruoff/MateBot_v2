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
            self.delay = float(self.config["robot"]["speed_delay"])
            self.active_low = self.pins.get("active_low", False)
            self.current_command = None
            self.lock = threading.Lock()
            
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
                self.pi.write(self.pins[key]["step"], 0)
                
            self.activate()
            
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            print("RobotMover: Ready.", file=sys.stderr)
            
        except Exception as e:
            print(f"RobotMover INIT ERROR: {e}", file=sys.stderr)
            raise

    def activate(self):
        state = 0 if self.active_low else 1
        self.pi.write(self.pins["sleep_pin"], state)
        print(f"RobotMover: Motors ENABLED (Sleep Pin {self.pins['sleep_pin']} = {state})", file=sys.stderr)
        time.sleep(0.5)

    def deactivate(self):
        state = 1 if self.active_low else 0
        self.pi.write(self.pins["sleep_pin"], state)
        print(f"RobotMover: Motors DISABLED (Sleep Pin {self.pins['sleep_pin']} = {state})", file=sys.stderr)

    def set_delay(self, new_delay):
        with self.lock:
            self.delay = float(new_delay)

    def set_command(self, command):
        with self.lock:
            self.current_command = command

    def _step_all(self, fl_dir, fr_dir, bl_dir, br_dir):
        self.pi.write(self.pins["fl"]["dir"], fl_dir)
        self.pi.write(self.pins["fr"]["dir"], fr_dir)
        self.pi.write(self.pins["bl"]["dir"], bl_dir)
        self.pi.write(self.pins["br"]["dir"], br_dir)
        
        time.sleep(0.00001) 
        
        # Increased pulse width to 30us for reliability
        self.pi.gpio_trigger(self.pins["fl"]["step"], 30, 1)
        self.pi.gpio_trigger(self.pins["fr"]["step"], 30, 1)
        self.pi.gpio_trigger(self.pins["bl"]["step"], 30, 1)
        self.pi.gpio_trigger(self.pins["br"]["step"], 30, 1)

    def _loop(self):
        while True:
            with self.lock:
                cmd = self.current_command
                delay = self.delay
            
            if cmd:
                if cmd == "forward": self._step_all(0, 1, 0, 1)
                elif cmd == "backward": self._step_all(1, 0, 1, 0)
                elif cmd == "left": self._step_all(1, 1, 1, 1)
                elif cmd == "right": self._step_all(0, 0, 0, 0)
                elif cmd == "strafe_left": self._step_all(1, 1, 0, 0)
                elif cmd == "strafe_right": self._step_all(0, 0, 1, 1)
                time.sleep(delay)
            else:
                time.sleep(0.01)

    def cleanup(self):
        self.deactivate()
        if hasattr(self, 'pi'):
            self.pi.stop()
