"""
Low-level stepper motor controller using pigpio for DRV8825/A4988 drivers
"""

import time
import threading
from typing import Optional
from loguru import logger

try:
    import pigpio
    import RPi.GPIO as GPIO
    HARDWARE_AVAILABLE = True
except ImportError:
    logger.warning("pigpio or RPi.GPIO not available - running in simulation mode")
    HARDWARE_AVAILABLE = False
    pigpio = None
    GPIO = None


class StepperMotor:
    """
    Single stepper motor controller for DRV8825/A4988 driver
    Uses pigpio for hardware PWM support
    """
    
    def __init__(self, dir_pin: int, step_pin: int, sleep_pin: int,
                 steps_per_rev: int = 200, microsteps: int = 16,
                 direction_multiplier: int = 1,
                 gpio_mode = None):
        """
        Initialize stepper motor
        
        Args:
            dir_pin: GPIO pin for direction control
            step_pin: GPIO pin for step pulses
            sleep_pin: GPIO pin for sleep/enable
            steps_per_rev: Steps per revolution (typically 200 for 1.8° motors)
            microsteps: Microstepping setting (1, 2, 4, 8, 16, 32)
            direction_multiplier: 1 or -1 to flip direction
        """
        self.dir_pin = dir_pin
        self.step_pin = step_pin
        self.sleep_pin = sleep_pin
        self.steps_per_rev = steps_per_rev
        self.microsteps = microsteps
        self.direction_multiplier = direction_multiplier
        
        self.total_steps_per_rev = steps_per_rev * microsteps
        
        # Current state
        self.is_active = False
        self.current_frequency = 0
        self.step_count = 0
        
        if HARDWARE_AVAILABLE:
            # Initialize pigpio
            self.pi = pigpio.pi()
            if not self.pi.connected:
                raise RuntimeError("Failed to connect to pigpio daemon. Run: sudo pigpiod")
            
            # Initialize GPIO for DIR and SLEEP
            if gpio_mode:
                GPIO.setmode(gpio_mode)
            GPIO.setup(self.dir_pin, GPIO.OUT)
            GPIO.setup(self.sleep_pin, GPIO.OUT)
            
            # Set initial states
            GPIO.output(self.dir_pin, GPIO.LOW)
            GPIO.output(self.sleep_pin, GPIO.LOW)  # Motors disabled by default
            
            logger.info(f"Stepper motor initialized: DIR={dir_pin}, STEP={step_pin}, SLEEP={sleep_pin}")
        else:
            self.pi = None
            logger.warning(f"Stepper motor initialized in SIMULATION mode")
    
    def activate(self) -> None:
        """Enable motor (holding torque on)"""
        if HARDWARE_AVAILABLE:
            GPIO.output(self.sleep_pin, GPIO.HIGH)
        self.is_active = True
    
    def deactivate(self) -> None:
        """Disable motor (holding torque off, saves power)"""
        if HARDWARE_AVAILABLE:
            GPIO.output(self.sleep_pin, GPIO.LOW)
            if self.pi:
                self.pi.set_PWM_dutycycle(self.step_pin, 0)
        self.is_active = False
        self.current_frequency = 0
    
    def set_direction(self, clockwise: bool) -> None:
        """
        Set rotation direction
        
        Args:
            clockwise: True for clockwise, False for counter-clockwise
        """
        if HARDWARE_AVAILABLE:
            # Apply direction multiplier for calibration
            actual_direction = clockwise if self.direction_multiplier > 0 else not clockwise
            GPIO.output(self.dir_pin, GPIO.HIGH if actual_direction else GPIO.LOW)
    
    def set_speed_rads(self, angular_velocity: float) -> None:
        """
        Set motor speed using angular velocity
        
        Args:
            angular_velocity: Speed in radians/second
        """
        # Convert rad/s to steps/s
        steps_per_second = abs(angular_velocity) * self.total_steps_per_rev / (2 * 3.14159)
        
        # Set direction based on sign
        self.set_direction(angular_velocity >= 0)
        
        # Set PWM frequency
        self._set_step_frequency(int(steps_per_second))
    
    def _set_step_frequency(self, frequency_hz: int) -> None:
        """
        Set step pulse frequency using hardware PWM
        
        Args:
            frequency_hz: Step frequency in Hz (steps per second)
        """
        if not HARDWARE_AVAILABLE or not self.pi:
            return
        
        if frequency_hz <= 0:
            # Stop motor
            self.pi.set_PWM_dutycycle(self.step_pin, 0)
            self.current_frequency = 0
            self.is_active = False
            return
        
        # Ensure motor is active
        if not self.is_active:
            self.activate()
        
        # Limit frequency to safe range (0-8000 Hz)
        frequency_hz = min(frequency_hz, 8000)
        
        # Set PWM: 50% duty cycle, specified frequency
        self.pi.set_PWM_frequency(self.step_pin, frequency_hz)
        self.pi.set_PWM_dutycycle(self.step_pin, 128)  # 50% duty cycle
        
        self.current_frequency = frequency_hz
    
    def stop(self) -> None:
        """Stop motor immediately"""
        self._set_step_frequency(0)
    
    def get_angular_velocity(self) -> float:
        """
        Get current angular velocity in rad/s
        
        Returns:
            Current angular velocity
        """
        if self.current_frequency == 0:
            return 0.0
        
        return (self.current_frequency * 2 * 3.14159) / self.total_steps_per_rev
    
    def cleanup(self) -> None:
        """Clean up resources"""
        if HARDWARE_AVAILABLE:
            self.stop()
            self.deactivate()
            if self.pi:
                self.pi.stop()


class MotorController:
    """
    Controls all 4 stepper motors for omni-wheel robot
    """
    
    def __init__(self, config: dict):
        """
        Initialize motor controller from configuration
        
        Args:
            config: Motor configuration dictionary
        """
        self.config = config
        
        # Set GPIO mode once
        if HARDWARE_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
        
        # Get shared sleep pin
        sleep_pin = config['sleep_pin']
        steps_per_rev = config['steps_per_rev']
        microsteps = config['microsteps']
        
        # Initialize motors
        self.motors = {
            'front_left': StepperMotor(
                dir_pin=config['front_left']['dir_pin'],
                step_pin=config['front_left']['step_pin'],
                sleep_pin=sleep_pin,
                steps_per_rev=steps_per_rev,
                microsteps=microsteps,
                direction_multiplier=config['front_left'].get('direction_multiplier', 1),
                gpio_mode=GPIO.BCM if HARDWARE_AVAILABLE else None
            ),
            'front_right': StepperMotor(
                dir_pin=config['front_right']['dir_pin'],
                step_pin=config['front_right']['step_pin'],
                sleep_pin=sleep_pin,
                steps_per_rev=steps_per_rev,
                microsteps=microsteps,
                direction_multiplier=config['front_right'].get('direction_multiplier', 1),
                gpio_mode=GPIO.BCM if HARDWARE_AVAILABLE else None
            ),
            'back_left': StepperMotor(
                dir_pin=config['back_left']['dir_pin'],
                step_pin=config['back_left']['step_pin'],
                sleep_pin=sleep_pin,
                steps_per_rev=steps_per_rev,
                microsteps=microsteps,
                direction_multiplier=config['back_left'].get('direction_multiplier', 1),
                gpio_mode=GPIO.BCM if HARDWARE_AVAILABLE else None
            ),
            'back_right': StepperMotor(
                dir_pin=config['back_right']['dir_pin'],
                step_pin=config['back_right']['step_pin'],
                sleep_pin=sleep_pin,
                steps_per_rev=steps_per_rev,
                microsteps=microsteps,
                direction_multiplier=config['back_right'].get('direction_multiplier', 1),
                gpio_mode=GPIO.BCM if HARDWARE_AVAILABLE else None
            )
        }
        
        self._lock = threading.Lock()
        logger.info("Motor controller initialized with 4 motors")
    
    def set_wheel_speeds(self, vfl: float, vfr: float, vbl: float, vbr: float) -> None:
        """
        Set individual wheel speeds
        
        Args:
            vfl, vfr, vbl, vbr: Wheel angular velocities in rad/s
        """
        with self._lock:
            self.motors['front_left'].set_speed_rads(vfl)
            self.motors['front_right'].set_speed_rads(vfr)
            self.motors['back_left'].set_speed_rads(vbl)
            self.motors['back_right'].set_speed_rads(vbr)
    
    def stop_all(self) -> None:
        """Emergency stop all motors"""
        with self._lock:
            for motor in self.motors.values():
                motor.stop()
        logger.warning("All motors stopped")
    
    def activate_all(self) -> None:
        """Enable all motors"""
        with self._lock:
            for motor in self.motors.values():
                motor.activate()
    
    def deactivate_all(self) -> None:
        """Disable all motors"""
        with self._lock:
            for motor in self.motors.values():
                motor.deactivate()
    
    def get_wheel_velocities(self) -> dict:
        """
        Get current wheel velocities
        
        Returns:
            Dictionary with wheel velocities
        """
        with self._lock:
            return {
                'front_left': self.motors['front_left'].get_angular_velocity(),
                'front_right': self.motors['front_right'].get_angular_velocity(),
                'back_left': self.motors['back_left'].get_angular_velocity(),
                'back_right': self.motors['back_right'].get_angular_velocity()
            }
    
    def cleanup(self) -> None:
        """Clean up all motors"""
        logger.info("Cleaning up motor controller")
        for motor in self.motors.values():
            motor.cleanup()
        if HARDWARE_AVAILABLE:
            GPIO.cleanup()
