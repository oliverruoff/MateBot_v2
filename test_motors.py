#!/usr/bin/env python3
"""
Motor Test Script for MateBot v2

This script tests the motor control system with various movements.
Run this on the Raspberry Pi to verify motor functionality.

Usage:
    python test_motors.py

Controls:
    w - Forward
    s - Backward
    a - Strafe left
    d - Strafe right
    q - Rotate left
    e - Rotate right
    x - Stop
    ESC or Ctrl+C - Exit
"""

import sys
import time
import termios
import tty
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from matebot.core.config_loader import get_config
from matebot.hardware.motors import MotorController
from matebot.control.motion_controller import MotionController
from matebot.utils.logger import setup_logging
from loguru import logger


def get_key():
    """Get single keypress from terminal"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def print_menu():
    """Print control menu"""
    print("\n" + "="*60)
    print("MateBot v2 - Motor Test")
    print("="*60)
    print("\nControls:")
    print("  W - Move Forward")
    print("  S - Move Backward")
    print("  A - Strafe Left")
    print("  D - Strafe Right")
    print("  Q - Rotate Left")
    print("  E - Rotate Right")
    print("  X - Stop")
    print("  ESC or Ctrl+C - Exit")
    print("\nSpeed:")
    print("  1 - Slow (0.15 m/s)")
    print("  2 - Medium (0.30 m/s)")
    print("  3 - Fast (0.50 m/s)")
    print("="*60)
    print("\nPress any key to start...")


def test_sequence(motion_ctrl: MotionController):
    """
    Run automated test sequence
    """
    print("\n" + "="*60)
    print("Running Automated Test Sequence")
    print("="*60)
    
    test_speed = 0.2  # m/s
    test_duration = 2.0  # seconds
    
    tests = [
        ("Forward", lambda: motion_ctrl.move_forward(test_speed)),
        ("Backward", lambda: motion_ctrl.move_backward(test_speed)),
        ("Strafe Left", lambda: motion_ctrl.strafe_left(test_speed)),
        ("Strafe Right", lambda: motion_ctrl.strafe_right(test_speed)),
        ("Rotate Left", lambda: motion_ctrl.rotate_left(0.5)),
        ("Rotate Right", lambda: motion_ctrl.rotate_right(0.5)),
    ]
    
    for test_name, test_func in tests:
        print(f"\n[{test_name}]")
        print(f"  Moving for {test_duration} seconds...")
        test_func()
        time.sleep(test_duration)
        
        print("  Stopping...")
        motion_ctrl.stop_motion()
        time.sleep(1.0)
    
    print("\n" + "="*60)
    print("Test sequence completed!")
    print("="*60)


def manual_control(motion_ctrl: MotionController):
    """
    Interactive manual control mode
    """
    print_menu()
    get_key()  # Wait for keypress to start
    
    print("\n\nManual control active. Press keys to move...")
    print("(Current speed will be displayed)\n")
    
    speed = 0.30  # Default medium speed
    rotation_speed = 0.5  # rad/s
    
    try:
        while True:
            key = get_key().lower()
            
            # Speed control
            if key == '1':
                speed = 0.15
                print(f"Speed: SLOW ({speed} m/s)")
                continue
            elif key == '2':
                speed = 0.30
                print(f"Speed: MEDIUM ({speed} m/s)")
                continue
            elif key == '3':
                speed = 0.50
                print(f"Speed: FAST ({speed} m/s)")
                continue
            
            # Movement commands
            if key == 'w':
                print(f"Moving FORWARD at {speed} m/s")
                motion_ctrl.move_forward(speed)
            elif key == 's':
                print(f"Moving BACKWARD at {speed} m/s")
                motion_ctrl.move_backward(speed)
            elif key == 'a':
                print(f"Strafing LEFT at {speed} m/s")
                motion_ctrl.strafe_left(speed)
            elif key == 'd':
                print(f"Strafing RIGHT at {speed} m/s")
                motion_ctrl.strafe_right(speed)
            elif key == 'q':
                print(f"Rotating LEFT at {rotation_speed} rad/s")
                motion_ctrl.rotate_left(rotation_speed)
            elif key == 'e':
                print(f"Rotating RIGHT at {rotation_speed} rad/s")
                motion_ctrl.rotate_right(rotation_speed)
            elif key == 'x':
                print("STOP")
                motion_ctrl.stop_motion()
            elif key == '\x1b':  # ESC key
                print("\nExiting...")
                break
            elif key == '\x03':  # Ctrl+C
                break
            
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        motion_ctrl.stop_motion()


def main():
    """Main test function"""
    print("\n" + "="*60)
    print("MateBot v2 - Motor Control Test")
    print("="*60 + "\n")
    
    # Setup logging
    setup_logging(log_level="INFO", log_to_file=False)
    
    # Load configuration
    print("Loading configuration...")
    config = get_config()
    
    # Check if pigpiod is running
    try:
        import pigpio
        pi = pigpio.pi()
        if not pi.connected:
            print("\n" + "!"*60)
            print("ERROR: pigpiod daemon is not running!")
            print("Please start it with: sudo pigpiod")
            print("!"*60 + "\n")
            return
        pi.stop()
    except ImportError:
        print("\nWARNING: pigpio not installed - running in simulation mode")
    
    # Initialize motor controller
    print("Initializing motor controller...")
    motor_ctrl = MotorController(config['hardware']['motors'])
    
    # Initialize motion controller
    print("Initializing motion controller...")
    motion_ctrl = MotionController(motor_ctrl, config)
    
    # Start control loop
    print("Starting motion control loop...")
    motion_ctrl.start()
    
    print("\n✓ Motor controller ready!\n")
    
    # Ask user what to do
    print("Select test mode:")
    print("  1 - Automated test sequence")
    print("  2 - Manual control mode")
    print("\nChoice: ", end='', flush=True)
    
    choice = get_key()
    print(choice)
    
    try:
        if choice == '1':
            test_sequence(motion_ctrl)
        elif choice == '2':
            manual_control(motion_ctrl)
        else:
            print("Invalid choice. Starting manual control...")
            manual_control(motion_ctrl)
    
    except Exception as e:
        logger.error(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n\nCleaning up...")
        motion_ctrl.cleanup()
        print("Done!")


if __name__ == "__main__":
    main()
