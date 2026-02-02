"""
Autonomous exploration controller for MateBot v2
Explores environment while avoiding obstacles using LiDAR
"""

import time
import threading
import random
import math
from typing import Optional, List, Dict
from loguru import logger


class ExplorationController:
    """
    Autonomous exploration with obstacle avoidance
    
    Strategy:
    1. Move forward while checking for obstacles
    2. If obstacle detected, rotate to find clear path
    3. Continue exploring until stopped
    """
    
    def __init__(self, motor_controller, lidar, mapper):
        """
        Initialize exploration controller
        
        Args:
            motor_controller: Robot motor controller
            lidar: LiDAR sensor
            mapper: SLAM mapper
        """
        self.motor_controller = motor_controller
        self.lidar = lidar
        self.mapper = mapper
        
        # Exploration state
        self._exploring = False
        self._exploration_thread: Optional[threading.Thread] = None
        
        # Safety parameters
        self.min_obstacle_distance_cm = 40  # Stop if obstacle within 40cm
        self.safe_distance_cm = 60  # Prefer paths with > 60cm clearance
        self.rotation_check_angle = 45  # Degrees to check on each side
        
        # Movement speeds
        self.forward_speed = 0.2  # m/s
        self.rotation_speed = 0.3  # rad/s
        
        logger.info("Exploration controller initialized")
    
    def start_exploration(self) -> bool:
        """
        Start autonomous exploration
        
        Returns:
            True if started successfully
        """
        if self._exploring:
            logger.warning("Exploration already running")
            return False
        
        if not self.lidar.available:
            logger.error("Cannot start exploration: LiDAR not available")
            return False
        
        self._exploring = True
        self._exploration_thread = threading.Thread(
            target=self._exploration_loop,
            daemon=True
        )
        self._exploration_thread.start()
        logger.info("Exploration started")
        return True
    
    def stop_exploration(self) -> None:
        """Stop autonomous exploration"""
        if not self._exploring:
            return
        
        self._exploring = False
        if self._exploration_thread:
            self._exploration_thread.join(timeout=2.0)
        
        # Stop robot
        self.motor_controller.set_command(None)
        logger.info("Exploration stopped")
    
    def is_exploring(self) -> bool:
        """Check if currently exploring"""
        return self._exploring
    
    def _get_closest_obstacle_in_sector(self, 
                                        center_angle: float, 
                                        sector_width: float) -> float:
        """
        Get distance to closest obstacle in angular sector
        
        Args:
            center_angle: Center angle of sector (degrees, 0=forward)
            sector_width: Width of sector in degrees
            
        Returns:
            Distance in cm to closest obstacle (9999 if no obstacle)
        """
        scan = self.lidar.get_scan()
        if not scan:
            return 9999.0
        
        min_distance = 9999.0
        half_width = sector_width / 2.0
        
        for point in scan:
            angle = point['angle']
            distance = point['distance_cm']
            
            # Normalize angle difference
            angle_diff = abs((angle - center_angle + 180) % 360 - 180)
            
            if angle_diff <= half_width:
                min_distance = min(min_distance, distance)
        
        return min_distance
    
    def _check_forward_clear(self) -> bool:
        """
        Check if path forward is clear
        
        Returns:
            True if safe to move forward
        """
        # Check front sector (±30 degrees)
        front_distance = self._get_closest_obstacle_in_sector(0, 60)
        
        return front_distance > self.min_obstacle_distance_cm
    
    def _find_best_direction(self) -> Optional[str]:
        """
        Find best direction to turn
        
        Returns:
            'left', 'right', or None if stuck
        """
        # Check multiple directions
        directions = {
            'front': self._get_closest_obstacle_in_sector(0, 60),
            'left': self._get_closest_obstacle_in_sector(270, 60),
            'right': self._get_closest_obstacle_in_sector(90, 60),
            'left_45': self._get_closest_obstacle_in_sector(315, 45),
            'right_45': self._get_closest_obstacle_in_sector(45, 45),
        }
        
        logger.debug(f"Obstacle distances: {directions}")
        
        # Find direction with most clearance
        best_direction = None
        best_distance = 0
        
        for direction, distance in directions.items():
            if distance > best_distance:
                best_distance = distance
                best_direction = direction
        
        # If all directions are blocked, we're stuck
        if best_distance < self.min_obstacle_distance_cm:
            logger.warning("Robot appears stuck - all directions blocked")
            return None
        
        # Map to motor command
        if 'left' in best_direction:
            return 'left'
        elif 'right' in best_direction:
            return 'right'
        else:
            return None  # Front is clear
    
    def _exploration_loop(self) -> None:
        """Main exploration loop"""
        logger.info("Exploration loop started")
        
        stuck_counter = 0
        last_map_update = time.time()
        
        while self._exploring:
            try:
                # Update map from LiDAR
                if time.time() - last_map_update > 0.5:  # Update map every 500ms
                    lidar_data = self.lidar.get_scan()
                    if lidar_data:
                        self.mapper.update_from_lidar(lidar_data)
                    last_map_update = time.time()
                
                # Check if forward path is clear
                if self._check_forward_clear():
                    # Move forward
                    self.motor_controller.set_command('forward')
                    stuck_counter = 0
                    time.sleep(0.5)
                else:
                    # Obstacle detected, find best direction
                    logger.info("Obstacle detected, finding new direction")
                    self.motor_controller.set_command(None)
                    time.sleep(0.2)
                    
                    best_dir = self._find_best_direction()
                    
                    if best_dir is None:
                        # Stuck! Try backing up
                        stuck_counter += 1
                        if stuck_counter > 3:
                            logger.error("Robot stuck for too long, stopping exploration")
                            self.stop_exploration()
                            break
                        
                        logger.warning("No clear path, backing up")
                        self.motor_controller.set_command('backward')
                        time.sleep(0.5)
                        self.motor_controller.set_command(None)
                        
                        # Random rotation to try new direction
                        rotate_dir = random.choice(['left', 'right'])
                        self.motor_controller.set_command(rotate_dir)
                        time.sleep(0.8)
                        self.motor_controller.set_command(None)
                    else:
                        # Rotate towards clear path
                        logger.info(f"Rotating {best_dir}")
                        self.motor_controller.set_command(best_dir)
                        time.sleep(0.6)
                        self.motor_controller.set_command(None)
                        stuck_counter = 0
                
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in exploration loop: {e}")
                time.sleep(0.5)
        
        # Stop robot when exploration ends
        self.motor_controller.set_command(None)
        logger.info("Exploration loop ended")
