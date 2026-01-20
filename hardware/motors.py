import time
import threading
import RPi.GPIO as GPIO
import toml

class RobotMover:
    def __init__(self, config_path="config.toml"):
        with open(config_path, "r") as f:
            self.config = toml.load(f)
        
        self.pins = self.config["motors"]
        self.delay = self.config["robot"]["speed_delay"]
        self.running = False
        self.current_command = None
        self.lock = threading.Lock()

        # GPIO Setup
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Setup all pins
        all_pins = [self.pins["sleep_pin"]]
        for key in ["fl", "fr", "bl", "br"]:
            all_pins.append(self.pins[key]["dir"])
            all_pins.append(self.pins[key]["step"])
        
        GPIO.setup(all_pins, GPIO.OUT)
        
        # Motoren aktivieren (Sleep Pin HIGH = Wach)
        GPIO.output(self.pins["sleep_pin"], GPIO.HIGH)

        # Thread starten
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def set_command(self, command):
        """ Setzt den aktuellen Bewegungsbefehl """
        with self.lock:
            self.current_command = command

    def _step(self, motor_key, direction):
        """ Hilfsfunktion für einen Schritt """
        pin_dir = self.pins[motor_key]["dir"]
        pin_step = self.pins[motor_key]["step"]
        
        # 1 = Vorwärts (je nach Verkabelung ggf. anpassen!), 0 = Rückwärts
        # Hier Annahme: 1 ist "Standard", wir invertieren je nach Bedarf
        GPIO.output(pin_dir, direction)
        GPIO.output(pin_step, GPIO.HIGH)
        # Kurzer Puls
        time.sleep(0.000001) 
        GPIO.output(pin_step, GPIO.LOW)

    def _loop(self):
        while True:
            cmd = None
            with self.lock:
                cmd = self.current_command
            
            if cmd:
                # Logik für Omni-Wheels (Mecanum)
                # 1 = CW, 0 = CCW (Muss ggf. probiert werden, je nach Motor-Wiring!)
                
                if cmd == "forward":
                    self._step("fl", 0) # Links meist invertiert
                    self._step("fr", 1)
                    self._step("bl", 0)
                    self._step("br", 1)

                elif cmd == "backward":
                    self._step("fl", 1)
                    self._step("fr", 0)
                    self._step("bl", 1)
                    self._step("br", 0)

                elif cmd == "left": # Rotation auf der Stelle
                    self._step("fl", 1)
                    self._step("fr", 1)
                    self._step("bl", 1)
                    self._step("br", 1)

                elif cmd == "right": # Rotation auf der Stelle
                    self._step("fl", 0)
                    self._step("fr", 0)
                    self._step("bl", 0)
                    self._step("br", 0)

                elif cmd == "strafe_left": # Seitwärts links
                    self._step("fl", 1) # Rückwärts
                    self._step("fr", 1) # Vorwärts
                    self._step("bl", 0) # Vorwärts
                    self._step("br", 0) # Rückwärts

                elif cmd == "strafe_right": # Seitwärts rechts
                    self._step("fl", 0) # Vorwärts
                    self._step("fr", 0) # Rückwärts
                    self._step("bl", 1) # Rückwärts
                    self._step("br", 1) # Vorwärts
                
                time.sleep(self.delay)
            else:
                # CPU schonen wenn nichts passiert
                time.sleep(0.05)

    def cleanup(self):
        GPIO.output(self.pins["sleep_pin"], GPIO.LOW) # Motoren aus
        GPIO.cleanup()