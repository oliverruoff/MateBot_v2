"""
Manual mapping mode for MateBot v2 with Batch Performance Optimization.
"""

import time
import threading
from typing import Optional, List, Tuple
from loguru import logger

class ManualMapper:
    def __init__(self, lidar, mapper, motor_controller=None, odometry=None, imu=None):
        self.lidar = lidar
        self.mapper = mapper
        self.motor_controller = motor_controller
        self.odometry = odometry
        self.imu = imu
        self._mapping = False
        self._mapping_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._control_lock = threading.Lock()
        self.update_interval = 0.1  
        self._min_dist_update = 0.02 
        self._min_rot_update = 0.01  
        self._last_update_pose = (-1000.0, -1000.0, -1000.0)
        self._force_update = False

    def start_mapping(self) -> bool:
        with self._control_lock:
            if self._mapping: return False
            if not self.lidar.available: return False
            self._mapping = True
            self._stop_event.clear()
            self._force_update = True
            self._mapping_thread = threading.Thread(target=self._mapping_loop, daemon=True)
            self._mapping_thread.start()
            return True

    def stop_mapping(self, save_map: bool = True) -> None:
        with self._control_lock:
            if not self._mapping: return
            self._mapping = False
            self._stop_event.set()
        if self._mapping_thread: self._mapping_thread.join(timeout=2.0)
        logger.info("Manual mapping stopped")

    def reset_mapping_state(self) -> None:
        with self._control_lock:
            self._last_update_pose = (-1000.0, -1000.0, -1000.0)
            self._force_update = True

    def is_mapping(self) -> bool:
        with self._control_lock: return self._mapping

    def _mapping_loop(self) -> None:
        logger.info("Mapping loop started (Batch Mode)")
        while self._mapping and not self._stop_event.is_set():
            try:
                gyro_data = self.imu.get_data() if self.imu else None
                step_counts = self.motor_controller.get_step_counts() if self.motor_controller else None
                
                if self.odometry and step_counts:
                    x, y, heading = self.odometry.update(step_counts, gyro_data)
                    self.mapper.update_robot_pose(x, y, heading)
                    lx, ly, lh = self._last_update_pose
                    dist_sq = (x-lx)**2 + (y-ly)**2
                    rot_diff = abs((heading - lh + 3.14) % 6.28 - 3.14)
                    if not (dist_sq >= self._min_dist_update**2 or rot_diff >= self._min_rot_update or self._force_update):
                        time.sleep(0.05); continue
                    self._last_update_pose = (x, y, heading); self._force_update = False

                lidar_data = self.lidar.get_scan()
                if not lidar_data:
                    time.sleep(0.05); continue

                # BUILD BATCH
                batch: List[Tuple[float, float, float, float, float]] = []
                for pt in lidar_data:
                    ts = pt.get('timestamp')
                    angle, dist = pt['angle'], pt['distance_cm']
                    if ts and self.odometry:
                        px, py, ph = self.odometry.get_pose_at(ts)
                        batch.append((px, py, ph, angle, dist))
                    else:
                        cx, cy, ch = self.mapper.get_robot_pose()
                        batch.append((cx, cy, ch, angle, dist))
                
                # SEND BATCH
                if batch:
                    self.mapper.add_lidar_points_batch(batch)
                
                if self._stop_event.wait(self.update_interval): break
            except Exception as e:
                logger.error(f"Mapping error: {e}"); time.sleep(0.1)
