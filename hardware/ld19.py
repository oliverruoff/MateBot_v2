"""
LD19 360° LiDAR driver for MateBot v2
"""

import serial
import threading
import time
import struct
import random
from typing import Optional, List, Tuple, Dict
from loguru import logger

try:
    import serial
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False


class LD19:
    HEADER = 0x54
    POINT_PER_PACK = 12
    POINT_RETENTION_MS = 500  
    ANGLE_OFFSET = 90.0        
    MIN_DISTANCE_CM = 45.0    # Blind zone
    
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 230400):
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.available = False
        self._current_scan: Dict[float, Tuple[float, int, float]] = {}
        self._lock = threading.Lock()
        self._rotation_speed_deg_s = 3600.0
        self._last_speed_update = time.time()
        self._running = False
        self._read_thread: Optional[threading.Thread] = None
        self._initialize()
    
    def _initialize(self) -> None:
        if not HARDWARE_AVAILABLE:
            self.available = False
            return
        try:
            self.ser = serial.Serial(
                port=self.port, baudrate=self.baudrate, timeout=1.0,
                parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS
            )
            self.available = True
            logger.info(f"LD19 initialized on {self.port}")
        except Exception as e:
            logger.error(f"Failed to initialize LD19: {e}")
            self.available = False
    
    def _parse_packet(self, packet: bytes) -> Optional[List[Dict]]:
        if len(packet) != 47 or packet[0] != self.HEADER:
            return None
        
        speed_raw = struct.unpack('<H', packet[2:4])[0]
        start_angle_raw = struct.unpack('<H', packet[4:6])[0]
        end_angle_raw = struct.unpack('<H', packet[42:44])[0]
        
        start_angle = start_angle_raw / 100.0
        end_angle = end_angle_raw / 100.0
        if end_angle < start_angle: end_angle += 360.0
        
        points = []
        angle_step = (end_angle - start_angle) / self.POINT_PER_PACK if self.POINT_PER_PACK > 1 else 0
        current_time = time.time()
        
        for i in range(self.POINT_PER_PACK):
            offset = 6 + (i * 3)
            distance_raw = struct.unpack('<H', packet[offset:offset+2])[0]
            confidence = packet[offset+2]
            
            # Use raw angle + offset (standard CCW)
            raw_angle = start_angle + (i * angle_step)
            angle = (raw_angle + self.ANGLE_OFFSET) % 360.0
            
            distance_cm = distance_raw / 10.0
            
            if distance_cm > self.MIN_DISTANCE_CM and distance_cm < 1200.0 and confidence > 100:
                points.append({
                    'angle': angle,
                    'distance_cm': distance_cm,
                    'confidence': confidence,
                    'timestamp': current_time
                })
        return points
    
    def _read_packet(self) -> Optional[bytes]:
        if not self.ser: return None
        while True:
            byte = self.ser.read(1)
            if len(byte) == 0: return None
            if byte[0] == self.HEADER:
                rest = self.ser.read(46)
                if len(rest) == 46: return byte + rest
                return None
    
    def _remove_old_points(self) -> None:
        current_time = time.time()
        cutoff = current_time - (self.POINT_RETENTION_MS / 1000.0)
        expired = [a for a, (_, _, ts) in self._current_scan.items() if ts < cutoff]
        for a in expired: del self._current_scan[a]
    
    def get_scan(self) -> List[Dict]:
        with self._lock:
            self._remove_old_points()
            return [{'angle': a, 'distance_cm': d, 'confidence': c, 'timestamp': ts} 
                    for a, (d, c, ts) in sorted(self._current_scan.items())]
    
    def get_data(self) -> Dict:
        points = self.get_scan()
        return {'points': points, 'point_count': len(points), 'available': self.available}
    
    def start_continuous_reading(self) -> None:
        if self._running: return
        self._running = True
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()
    
    def stop_continuous_reading(self) -> None:
        self._running = False
        if self._read_thread: self._read_thread.join(timeout=2.0)
    
    def _read_loop(self) -> None:
        last_cleanup = time.time()
        while self._running:
            try:
                packet = self._read_packet()
                if not packet: continue
                points = self._parse_packet(packet)
                if not points: continue
                now = time.time()
                with self._lock:
                    for p in points:
                        self._current_scan[p['angle']] = (p['distance_cm'], p['confidence'], p['timestamp'])
                    if now - last_cleanup > 0.1:
                        self._remove_old_points()
                        last_cleanup = now
            except Exception as e:
                time.sleep(0.1)
    
    def cleanup(self) -> None:
        self.stop_continuous_reading()
        if self.ser: self.ser.close()
