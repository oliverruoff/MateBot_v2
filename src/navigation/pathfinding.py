import numpy as np
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder
import config

class PathPlanner:
    def __init__(self):
        self.finder = AStarFinder()

    def plan(self, current_pose, target_pose, map_data):
        """
        current_pose, target_pose: (x, y) in world coordinates
        map_data: 2D numpy array
        Returns: list of (x, y) waypoints
        """
        # Convert world to grid
        start_node = (int(current_pose[0] / config.MAP_RESOLUTION), 
                      int(current_pose[1] / config.MAP_RESOLUTION))
        end_node = (int(target_pose[0] / config.MAP_RESOLUTION), 
                    int(target_pose[1] / config.MAP_RESOLUTION))
        
        # TODO: Implement real A* with pathfinding library
        # For now, just return a straight line as stub
        return [current_pose, target_pose]

class PurePursuitController:
    def __init__(self):
        self.lookahead = 0.2 # 20cm

    def get_velocity(self, current_pose, path):
        """
        current_pose: (x, y, theta)
        path: list of (x, y)
        Returns: (vx, vy, omega)
        """
        if not path or len(path) < 2:
            return 0, 0, 0
            
        # TODO: Implement real Pure Pursuit logic
        # For now, just a stub that moves towards the next point
        target = path[-1]
        dx = target[0] - current_pose[0]
        dy = target[1] - current_pose[1]
        
        # Very basic proportional control
        vx = 0.1 if abs(dx) > 0.05 else 0
        vy = 0.1 if abs(dy) > 0.05 else 0
        
        return vx, vy, 0
