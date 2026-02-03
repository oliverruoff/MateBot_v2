"""
Dynamic Infinite Occupancy Grid Mapper for MateBot v2
Optimized for performance with Batch Updates.
"""

import numpy as np
import threading
import time
import math
import os
from pathlib import Path
from typing import Tuple, List, Dict, Optional, Set
from loguru import logger
from PIL import Image

class OccupancyGridMapper:
    def __init__(self, 
                 chunk_size: int = 200, 
                 resolution_cm: float = 5.0,
                 active_window: int = 3,
                 map_dir: str = "map_data"):
        self.chunk_size = chunk_size
        self.resolution_cm = resolution_cm
        self.resolution_m = resolution_cm / 100.0
        self.active_window = active_window
        self.map_dir = Path(map_dir)
        self.chunk_dir = self.map_dir / "chunks"
        self.chunk_dir.mkdir(parents=True, exist_ok=True)
        
        self.chunk_width = chunk_size
        self.chunk_height = chunk_size
        
        self._chunks: Dict[Tuple[int, int], np.ndarray] = {}
        
        self._robot_x_m = 0.0
        self._robot_y_m = 0.0
        self._robot_heading_rad = 0.0
        
        self._lock = threading.Lock()
        
        # TUNED WEIGHTS: Hard to occupy, very easy to clear
        self._occ_hit = 2       
        self._occ_miss = 8      
        self._occ_miss_near = 12 
        
        logger.info(f"Batch-Optimized Mapper initialized")

    def world_to_grid(self, x_m: float, y_m: float) -> Tuple[int, int]:
        return math.floor(x_m / self.resolution_m), math.floor(y_m / self.resolution_m)

    def _get_chunk_coords(self, grid_x: int, grid_y: int) -> Tuple[int, int]:
        return grid_x // self.chunk_size, grid_y // self.chunk_size

    def _get_local_coords(self, grid_x: int, grid_y: int) -> Tuple[int, int]:
        return grid_x % self.chunk_size, grid_y % self.chunk_size

    def _ensure_chunk_exists(self, cx: int, cy: int, create: bool = True) -> bool:
        """Checks memory, then disk. Optionally creates new chunk."""
        if (cx, cy) in self._chunks: return True
        
        chunk_file = self.chunk_dir / f"chunk_{cx}_{cy}.npy"
        if chunk_file.exists():
            try:
                self._chunks[(cx, cy)] = np.load(chunk_file)
                return True
            except Exception as e:
                logger.error(f"Error loading chunk ({cx}, {cy}): {e}")
        
        if create:
            self._chunks[(cx, cy)] = np.zeros((self.chunk_height, self.chunk_width), dtype=np.uint8)
            return True
        return False

    def _save_chunk_to_disk(self, cx: int, cy: int) -> None:
        if (cx, cy) not in self._chunks: return
        chunk_file = self.chunk_dir / f"chunk_{cx}_{cy}.npy"
        try: np.save(chunk_file, self._chunks[(cx, cy)])
        except Exception as e: logger.error(f"Error saving chunk: {e}")

    def _update_active_chunks(self) -> None:
        gx, gy = self.world_to_grid(self._robot_x_m, self._robot_y_m)
        cx, cy = self._get_chunk_coords(gx, gy)
        radius = self.active_window // 2
        active_set = {(cx + dx, cy + dy) for dx in range(-radius, radius + 1) for dy in range(-radius, radius + 1)}
        
        with self._lock:
            to_unload = [c for c in self._chunks if c not in active_set]
            for c in to_unload:
                self._save_chunk_to_disk(*c)
                del self._chunks[c]
            for c in active_set: 
                self._ensure_chunk_exists(c[0], c[1], create=True)

    def update_robot_pose(self, x_m: float, y_m: float, heading_rad: float) -> None:
        self._robot_x_m = x_m
        self._robot_y_m = y_m
        self._robot_heading_rad = heading_rad
        self._update_active_chunks()

    def get_robot_pose(self) -> Tuple[float, float, float]:
        return self._robot_x_m, self._robot_y_m, self._robot_heading_rad

    def add_lidar_points_batch(self, points: List[Tuple[float, float, float, float, float]]) -> None:
        """Process a whole scan with a single lock acquisition (High Performance)"""
        with self._lock:
            for rx, ry, rh, angle, dist in points:
                angle_rad = math.radians(angle) + rh
                dist_m = dist / 100.0
                
                start_gx, start_gy = self.world_to_grid(rx, ry)
                end_gx, end_gy = self.world_to_grid(rx + dist_m * math.cos(angle_rad), ry + dist_m * math.sin(angle_rad))
                
                # 1. Mark endpoint
                ecx, ecy = self._get_chunk_coords(end_gx, end_gy)
                if self._ensure_chunk_exists(ecx, ecy, create=True):
                    elx, ely = self._get_local_coords(end_gx, end_gy)
                    curr = self._chunks[(ecx, ecy)][ely, elx]
                    if curr < 100:
                        self._chunks[(ecx, ecy)][ely, elx] = min(100, curr + self._occ_hit)
                
                # 2. Raytrace (Optimized: only updates loaded chunks)
                self._bresenham_line(start_gx, start_gy, end_gx, end_gy, dist)

    def _bresenham_line(self, x0: int, y0: int, x1: int, y1: int, dist_cm: float) -> None:
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx - dy
        x, y = x0, y0
        
        clearing_strength = self._occ_miss_near if dist_cm < 100.0 else self._occ_miss
        
        while True:
            if x == x1 and y == y1: break
            
            cx, cy = self._get_chunk_coords(x, y)
            # OPTIMIZATION: Only update if chunk is already in memory
            if (cx, cy) in self._chunks:
                lx, ly = self._get_local_coords(x, y)
                val = self._chunks[(cx, cy)][ly, lx]
                if val == 0: val = 50 
                self._chunks[(cx, cy)][ly, lx] = max(1, val - clearing_strength)
            
            e2 = 2 * err
            if e2 > -dy: err -= dy; x += sx
            if e2 < dx: err += dx; y += sy

    def get_map_data(self, window_chunks: int = 3) -> Dict:
        with self._lock:
            gx, gy = self.world_to_grid(self._robot_x_m, self._robot_y_m)
            cx, cy = self._get_chunk_coords(gx, gy)
            radius = window_chunks // 2
            min_cx, min_cy = cx - radius, cy - radius
            full_s = window_chunks * self.chunk_size
            stitched = np.zeros((full_s, full_s), dtype=np.uint8)
            
            for dy in range(window_chunks):
                for dx in range(window_chunks):
                    cur_cx, cur_cy = min_cx + dx, min_cy + dy
                    if self._ensure_chunk_exists(cur_cx, cur_cy, create=False):
                        stitched[dy*self.chunk_size:(dy+1)*self.chunk_size, 
                                 dx*self.chunk_size:(dx+1)*self.chunk_size] = self._chunks[(cur_cx, cur_cy)]
            
            return {
                'width': full_s, 'height': full_s, 'grid': stitched.tolist(),
                'robot_x_grid': gx - (min_cx * self.chunk_size), 'robot_y_grid': gy - (min_cy * self.chunk_size),
                'robot_heading': math.degrees(self._robot_heading_rad),
                'chunk_info': {'center_chunk': [int(cx), int(cy)], 'window_size': int(window_chunks), 'chunk_size': int(self.chunk_size)}
            }

    def reset_map(self) -> None:
        with self._lock:
            self._chunks.clear()
            for f in self.chunk_dir.glob("chunk_*.npy"):
                try: f.unlink()
                except: pass

    def get_map_stats(self) -> Dict:
        with self._lock:
            disk_chunks = len(list(self.chunk_dir.glob("chunk_*.npy")))
            total_chunks = max(disk_chunks, len(self._chunks))
            return {
                'total_chunks': int(total_chunks), 'loaded_chunks': int(len(self._chunks)),
                'coverage_area_m2': float(total_chunks * (self.chunk_size * self.resolution_m) ** 2),
                'memory_mb': float(len(self._chunks) * self.chunk_size**2 / (1024**2))
            }

    def export_png(self, filename: str) -> bool:
        try:
            map_data = self.get_map_data()
            grid = np.array(map_data['grid'], dtype=np.uint8)
            Image.fromarray(grid).transpose(Image.FLIP_TOP_BOTTOM).save(filename)
            return True
        except: return False
