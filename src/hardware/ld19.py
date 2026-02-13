import serial
import threading
import time
import struct
from typing import Optional, List, Tuple, Dict
import sys

class LD19:
    HEADER = 0x54
    POINT_PER_PACK = 12
    
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 230400):
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.available = False
        self._current_scan: Dict[float, float] = {}  # angle: distance
        self._lock = threading.Lock()
        self._running = False
        self._read_thread: Optional[threading.Thread] = None
        self._initialize()
    
    def _initialize(self) -> None:
        try:
            self.ser = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=1.0)
            self.available = True
            sys.stderr.write(f"LD19: Initialized on {self.port}\n")
        except Exception as e:
            sys.stderr.write(f"LD19: Init Error {e}\n")
            self.available = False
    
    def _read_loop(self) -> None:
        while self._running:
            try:
                byte = self.ser.read(1)
                if not byte or byte[0] != self.HEADER: continue
                
                packet = byte + self.ser.read(46)
                if len(packet) < 47: continue
                
                start_angle = struct.unpack('<H', packet[4:6])[0] / 100.0
                end_angle = struct.unpack('<H', packet[42:44])[0] / 100.0
                
                if end_angle < start_angle: end_angle += 360.0
                step = (end_angle - start_angle) / (self.POINT_PER_PACK - 1)
                
                with self._lock:
                    for i in range(self.POINT_PER_PACK):
                        offset = 6 + (i * 3)
                        dist = struct.unpack('<H', packet[offset:offset+2])[0]
                        conf = packet[offset+2]
                        if dist > 0 and conf > 10:
                            angle = (start_angle + i * step) % 360.0
                            self._current_scan[angle] = dist / 1000.0 # to meters
            except Exception as e:
                time.sleep(0.1)
    
    def start(self):
        if self.available and not self._running:
            self._running = True
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            sys.stderr.write("LD19: Scanning started\n")

    def get_scan(self) -> List[Tuple[float, float]]:
        with self._lock:
            scan = list(self._current_scan.items())
            # Clear scan for next rotation to avoid ghosting
            self._current_scan = {}
            return scan

    def stop(self):
        self._running = False
