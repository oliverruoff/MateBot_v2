"""
TF-Luna LiDAR driver for MateBot v2
Supports USB connection via CP2102 UART bridge
"""

import serial
import threading
import time
from typing import Optional, Tuple
from loguru import logger

# Hardware availability flag
try:
    import serial
    HARDWARE_AVAILABLE = True
except ImportError:
    logger.warning("pyserial not available - TF-Luna running in simulation mode")
    HARDWARE_AVAILABLE = False


class TFLuna:
    """
    Driver for TF-Luna mini LiDAR sensor
    
    The TF-Luna communicates via UART at 115200 baud and sends
    9-byte data frames containing distance, signal strength, and temperature.
    """
    
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200):
        """
        Initialize TF-Luna sensor
        
        Args:
            port: Serial port path (default: /dev/ttyUSB0)
            baudrate: Communication baud rate (default: 115200)
        """
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.available = False
        
        # Latest reading cache
        self._last_distance = 0
        self._last_strength = 0
        self._last_temperature = 0.0
        self._lock = threading.Lock()
        
        # Continuous reading thread
        self._running = False
        self._read_thread: Optional[threading.Thread] = None
        
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize serial connection"""
        if not HARDWARE_AVAILABLE:
            logger.warning("TF-Luna: Running in simulation mode")
            self.available = False
            return
        
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0
            )
            self.available = True
            logger.info(f"TF-Luna initialized on {self.port} at {self.baudrate} baud")
        except serial.SerialException as e:
            logger.error(f"Failed to initialize TF-Luna: {e}")
            self.available = False
        except Exception as e:
            logger.error(f"Unexpected error initializing TF-Luna: {e}")
            self.available = False
    
    def read_tfluna_data(self) -> Tuple[int, int, float]:
        """
        Read sensor data (blocking)
        
        Returns:
            Tuple of (distance_cm, signal_strength, temperature_celsius)
        """
        if not self.available or self.ser is None:
            # Return simulation data
            return (100, 100, 25.0)
        
        try:
            # Wait for at least 9 bytes
            while self.ser.in_waiting < 9:
                time.sleep(0.001)
            
            # Read 9 bytes
            bytes_serial = self.ser.read(9)
            
            # Clear buffer
            self.ser.reset_input_buffer()
            
            # Validate frame header
            if len(bytes_serial) < 9:
                logger.warning("TF-Luna: Incomplete data frame")
                return self._get_cached_data()
            
            # Parse data
            # Bytes 0-1: Frame header (0x59 0x59)
            # Bytes 2-3: Distance (low byte, high byte)
            # Bytes 4-5: Signal strength (low byte, high byte)
            # Bytes 6-7: Temperature (low byte, high byte)
            # Byte 8: Checksum
            
            distance = bytes_serial[2] + bytes_serial[3] * 256
            strength = bytes_serial[4] + bytes_serial[5] * 256
            temp_raw = bytes_serial[6] + bytes_serial[7] * 256
            temperature = (temp_raw / 8.0) - 256.0
            
            # Update cache
            with self._lock:
                self._last_distance = distance
                self._last_strength = strength
                self._last_temperature = temperature
            
            return distance, strength, temperature
            
        except serial.SerialException as e:
            logger.error(f"TF-Luna serial error: {e}")
            return self._get_cached_data()
        except Exception as e:
            logger.error(f"TF-Luna read error: {e}")
            return self._get_cached_data()
    
    def read_distance(self) -> int:
        """
        Read only distance value
        
        Returns:
            Distance in centimeters
        """
        distance, _, _ = self.read_tfluna_data()
        return distance
    
    def _get_cached_data(self) -> Tuple[int, int, float]:
        """Get last successfully read data"""
        with self._lock:
            return (self._last_distance, self._last_strength, self._last_temperature)
    
    def get_data(self) -> dict:
        """
        Get latest sensor data as dictionary
        
        Returns:
            Dictionary with distance, strength, and temperature
        """
        distance, strength, temperature = self._get_cached_data()
        return {
            "distance_cm": distance,
            "distance_m": distance / 100.0,
            "signal_strength": strength,
            "temperature_c": round(temperature, 1),
            "available": self.available
        }
    
    def start_continuous_reading(self, rate_hz: float = 10.0) -> None:
        """
        Start continuous reading in background thread
        
        Args:
            rate_hz: Reading rate in Hz (default: 10 Hz)
        """
        if self._running:
            logger.warning("TF-Luna: Continuous reading already running")
            return
        
        self._running = True
        self._read_thread = threading.Thread(
            target=self._read_loop,
            args=(rate_hz,),
            daemon=True
        )
        self._read_thread.start()
        logger.info(f"TF-Luna: Started continuous reading at {rate_hz} Hz")
    
    def stop_continuous_reading(self) -> None:
        """Stop continuous reading"""
        if not self._running:
            return
        
        self._running = False
        if self._read_thread:
            self._read_thread.join(timeout=1.0)
        logger.info("TF-Luna: Stopped continuous reading")
    
    def _read_loop(self, rate_hz: float) -> None:
        """Background reading loop"""
        dt = 1.0 / rate_hz
        
        while self._running:
            loop_start = time.time()
            
            try:
                # Read data (updates cache)
                self.read_tfluna_data()
            except Exception as e:
                logger.error(f"Error in TF-Luna read loop: {e}")
            
            # Maintain loop rate
            elapsed = time.time() - loop_start
            sleep_time = dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def cleanup(self) -> None:
        """Clean up resources"""
        logger.info("Cleaning up TF-Luna")
        self.stop_continuous_reading()
        
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info("TF-Luna serial port closed")
