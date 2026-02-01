import time
import threading
import pigpio
import toml
import sys

# Motor directions based on original MateBot logic
# 0 = CCW, 1 = CW (Assuming same wiring)
# Forward: FL=CCW(0), FR=CW(1), BL=CCW(0), BR=CW(1)

class RobotMover:
    def __init__(self, config_path="config.toml"):
        print(f"RobotMover: Initializing with {config_path}", file=sys.stderr)
        try:
            with open(config_path, "r") as f:
                self.config = toml.load(f)
            
            self.pins = self.config["motors"]
            # Default frequency: for 0.0005 delay it was ~1000Hz.
            self.default_frequency = 2000 
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
                # Ensure no PWM at start
                self.pi.set_PWM_dutycycle(self.pins[key]["step"], 0)
                
            # Optional Microstepping pins (if present in config)
            self.m_pins = []
            for m in ["m0", "m1", "m2"]:
                if m in self.pins:
                    pin = self.pins[m]
                    self.pi.set_mode(pin, pigpio.OUTPUT)
                    self.m_pins.append(pin)

            # Activate motors
            self.activate()
            print("RobotMover: Initialization complete with Hardware PWM support!", file=sys.stderr)
            
        except Exception as e:
            print(f"RobotMover INIT ERROR: {e}", file=sys.stderr)
            raise

    def activate(self):
        self.pi.write(self.pins["sleep_pin"], 1)
        time.sleep(0.1) # Wait for drivers to wake up

    def deactivate(self):
        self.pi.write(self.pins["sleep_pin"], 0)

    def set_command(self, command, frequency=None):
        """ Sets movement using Hardware PWM """
        if frequency is None:
            frequency = self.default_frequency

        if command == self.current_command and command is not None:
            return

        self.current_command = command
        print(f"RobotMover: Executing '{command}' at {frequency}Hz", file=sys.stderr)

        if not command or command == "stop":
            self._stop_all()
            return

        # Directions (based on Robot.py in original MateBot)
        if command == "forward":
            self._set_motor("fl", 0, frequency)
            self._set_motor("fr", 1, frequency)
            self._set_motor("bl", 0, frequency)
            self._set_motor("br", 1, frequency)
        elif command == "backward":
            self._set_motor("fl", 1, frequency)
            self._set_motor("fr", 0, frequency)
            self._set_motor("bl", 1, frequency)
            self._set_motor("br", 0, frequency)
        elif command == "left":
            self._set_motor("fl", 1, frequency)
            self._set_motor("fr", 1, frequency)
            self._set_motor("bl", 1, frequency)
            self._set_motor("br", 1, frequency)
        elif command == "right":
            self._set_motor("fl", 0, frequency)
            self._set_motor("fr", 0, frequency)
            self._set_motor("bl", 0, frequency)
            self._set_motor("br", 0, frequency)
        elif command == "strafe_left":
            self._set_motor("fl", 1, frequency)
            self._set_motor("fr", 1, frequency)
            self._set_motor("bl", 0, frequency)
            self._set_motor("br", 0, frequency)
        elif command == "strafe_right":
            self._set_motor("fl", 0, frequency)
            self._set_motor("fr", 0, frequency)
            self._set_motor("bl", 1, frequency)
            self._set_motor("br", 1, frequency)

    def _set_motor(self, key, direction, frequency):
        p = self.pins[key]
        self.pi.write(p["dir"], direction)
        self.pi.set_PWM_frequency(p["step"], frequency)
        self.pi.set_PWM_dutycycle(p["step"], 128) # 50% duty cycle

    def _stop_all(self):
        for key in self.motor_keys:
            self.pi.set_PWM_dutycycle(self.pins[key]["step"], 0)

    def set_delay(self, delay):
        """ Convert delay to frequency and update """
        freq = int(1.0 / (float(delay) * 2))
        self.default_frequency = freq
        if self.current_command and self.current_command != "stop":
            cmd = self.current_command
            self.current_command = None 
            self.set_command(cmd, freq)

    def cleanup(self):
        self._stop_all()
        self.deactivate()
        if hasattr(self, 'pi'):
            self.pi.stop()
