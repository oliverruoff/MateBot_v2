import numpy as np
from multiprocessing import shared_memory
import config

class MapSharedMemory:
    def __init__(self, create=False):
        self.size = config.MAP_SIZE_PIXELS * config.MAP_SIZE_PIXELS
        self.name = "matebot_map"
        
        if create:
            try:
                # Cleanup existing if any
                existing = shared_memory.SharedMemory(name=self.name)
                existing.close()
                existing.unlink()
            except FileNotFoundError:
                pass
            self.shm = shared_memory.SharedMemory(name=self.name, create=True, size=self.size)
        else:
            self.shm = shared_memory.SharedMemory(name=self.name)
            
        self.map_array = np.ndarray((config.MAP_SIZE_PIXELS, config.MAP_SIZE_PIXELS), 
                                    dtype=np.uint8, buffer=self.shm.buf)

    def update_map(self, new_data):
        self.map_array[:] = new_data

    def get_map(self):
        return self.map_array.copy()

    def close(self):
        self.shm.close()
        
    def unlink(self):
        self.shm.unlink()
