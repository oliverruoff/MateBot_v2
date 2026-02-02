"""
LD19 360° LiDAR driver for MateBot v2
WayPonDEV FHL-LD19 360 Degree 2D Lidar Distance Sensor
"""

import serial
import threading
import time
import struct
from typing import Optional, List, Tuple, Dict
from loguru import logger
from collections import deque

# Hardware availability flag
try:
    import serial
    HARDWARE_AVAILABLE = True
except ImportError:
    logger.warning("pyserial not available - LD19 running in simulation mode")
    HARDWARE_AVAILABLE = False


class LD19:
    """
    Driver for LD19 360° scanning LiDAR sensor
    
    The LD19 sends continuous scan data packets containing:
    - Multiple measurement points per packet
    - Distance and angle information
    - Signal quality/confidence values
    """
    
    # LD19 Protocol Constants
    HEADER = 0x54
    POINT_PER_PACK = 12
    
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 230400):
        """
        Initialize LD19 sensor
        
        Args:
            port: Serial port path (default: /dev/ttyUSB0)
            baudrate: Communication baud rate (default: 230400)
        """
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.available = False
        
        # Scan data storage - store full 360° scans
        self._current_scan: Dict[float, Tuple[float, int]] = {}  # angle: (distance, confidence)
        self._lock = threading.Lock()
        self._scan_complete = False
        
        # Continuous reading thread
        self._running = False
        self._read_thread: Optional[threading.Thread] = None
        
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize serial connection"""
        if not HARDWARE_AVAILABLE:
            logger.warning("LD19: Running in simulation mode")
            self.available = False
            return
        
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            self.available = True
            logger.info(f"LD19 initialized on {self.port} at {self.baudrate} baud")
        except serial.SerialException as e:
            logger.error(f"Failed to initialize LD19: {e}")
            self.available = False
        except Exception as e:
            logger.error(f"Unexpected error initializing LD19: {e}")
            self.available = False
    
    def _parse_packet(self, packet: bytes) -> Optional[List[Dict]]:
        """
        Parse LD19 data packet
        
        LD19 Packet Format (47 bytes):
        - Header: 0x54 (1 byte)
        - Ver_len: version and point count (1 byte)
        - Speed: rotation speed in deg/s (2 bytes, little-endian)
        - Start Angle: starting angle * 100 (2 bytes, little-endian)
        - Data: 12 measurement points, each 3 bytes (36 bytes total)
          - Distance: mm (2 bytes, little-endian)
          - Confidence: signal quality (1 byte)
        - End Angle: ending angle * 100 (2 bytes, little-endian)
        - Timestamp: milliseconds (2 bytes, little-endian)
        - CRC: checksum (1 byte)
        
        Returns:
            List of measurement dicts or None if invalid
        """
        if len(packet) != 47:
            return None
        
        # Verify header
        if packet[0] != self.HEADER:
            return None
        
        # Parse header
        ver_len = packet[1]
        speed_raw = struct.unpack('<H', packet[2:4])[0]
        start_angle_raw = struct.unpack('<H', packet[4:6])[0]
        end_angle_raw = struct.unpack('<H', packet[42:44])[0]
        timestamp = struct.unpack('<H', packet[44:46])[0]
        crc = packet[46]
        
        # Calculate CRC (simple XOR checksum)
        calc_crc = 0
        for b in packet[:-1]:
            calc_crc ^= b
        
        if calc_crc != crc:
            logger.debug(f"LD19: CRC mismatch (got {crc}, expected {calc_crc})")
            # Continue anyway, CRC errors are common with LD19
        
        # Convert angles from centidegrees to degrees
        start_angle = start_angle_raw / 100.0
        end_angle = end_angle_raw / 100.0
        speed = speed_raw / 100.0  # deg/s
        
        # Handle angle wraparound
        if end_angle < start_angle:
            end_angle += 360.0
        
        # Parse measurement points
        points = []
        angle_step = (end_angle - start_angle) / self.POINT_PER_PACK if self.POINT_PER_PACK > 1 else 0
        
        for i in range(self.POINT_PER_PACK):
            offset = 6 + (i * 3)
            distance_raw = struct.unpack('<H', packet[offset:offset+2])[0]
            confidence = packet[offset+2]
            
            # Calculate angle for this point
            angle = start_angle + (i * angle_step)
            angle = angle % 360.0  # Normalize to 0-360
            
            # Distance is in mm, convert to cm
            distance_cm = distance_raw / 10.0
            
            # Filter out invalid measurements
            if distance_cm > 0 and confidence > 0:
                points.append({
                    'angle': angle,
                    'distance_cm': distance_cm,
                    'distance_m': distance_cm / 100.0,
                    'confidence': confidence
                })
        
        return points
    
    def _read_packet(self) -> Optional[bytes]:
        """Read one complete packet from serial"""
        if not self.ser:
            return None
        
        # Find packet header
        while True:
            byte = self.ser.read(1)
            if len(byte) == 0:
                return None
            if byte[0] == self.HEADER:
                # Found header, read rest of packet
                rest = self.ser.read(46)  # 47 - 1 (header already read)
                if len(rest) == 46:
                    return byte + rest
                return None
    
    def get_scan(self) -> List[Dict]:
        """
        Get current 360° scan data
        
        Returns:
            List of measurement points with angle, distance, confidence
        """
        with self._lock:
            # Convert dict to sorted list
            points = []
            for angle, (distance, confidence) in sorted(self._current_scan.items()):
                points.append({
                    'angle': angle,
                    'distance_cm': distance,
                    'distance_m': distance / 100.0,
                    'confidence': confidence
                })
            return points
    
    def get_data(self) -> Dict:
        """
        Get scan data as dictionary
        
        Returns:
            Dictionary with scan points and metadata
        """
        points = self.get_scan()
        return {
            'points': points,
            'point_count': len(points),
            'available': self.available
        }
    
    def start_continuous_reading(self) -> None:
        """Start continuous reading in background thread"""
        if self._running:
            logger.warning("LD19: Continuous reading already running")
            return
        
        self._running = True
        self._read_thread = threading.Thread(
            target=self._read_loop,
            daemon=True
        )
        self._read_thread.start()
        logger.info("LD19: Started continuous reading")
    
    def stop_continuous_reading(self) -> None:
        """Stop continuous reading"""
        if not self._running:
            return
        
        self._running = False
        if self._read_thread:
            self._read_thread.join(timeout=2.0)
        logger.info("LD19: Stopped continuous reading")
    
    def _read_loop(self) -> None:
        """Background reading loop"""
        last_angle = 0
        
        while self._running:
            try:
                # Read packet
                packet = self._read_packet()
                if packet is None:
                    continue
                
                # Parse packet
                points = self._parse_packet(packet)
                if points is None:
                    continue
                
                # Update scan data
                with self._lock:
                    for point in points:
                        angle = point['angle']
                        distance = point['distance_cm']
                        confidence = point['confidence']
                        
                        # Store in current scan
                        self._current_scan[angle] = (distance, confidence)
                        
                        # Detect new scan cycle (angle wrapped around)
                        if angle < last_angle and last_angle > 300:
                            # Started new scan, clear old data
                            # Keep recent points for smoother visualization
                            if len(self._current_scan) > 500:
                                # Remove oldest 25% of points
                                angles_to_remove = sorted(self._current_scan.keys())[:len(self._current_scan)//4]
                                for a in angles_to_remove:
                                    del self._current_scan[a]
                        
                        last_angle = angle
                
            except Exception as e:
                logger.error(f"Error in LD19 read loop: {e}")
                time.sleep(0.1)
    
    def cleanup(self) -> None:
        """Clean up resources"""
        logger.info("Cleaning up LD19")
        self.stop_continuous_reading()
        
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info("LD19 serial port closed")
