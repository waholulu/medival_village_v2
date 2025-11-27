import numpy as np
from dataclasses import dataclass

# Layer Indices
LAYER_TERRAIN = 0
LAYER_MOISTURE = 1
LAYER_MOVE_COST = 2
LAYER_OCCUPIED_BY = 3
LAYER_ZONE = 4
NUM_LAYERS = 5

# Terrain IDs
TERRAIN_GRASS = 0
TERRAIN_DIRT = 1
TERRAIN_WATER = 2
TERRAIN_STONE = 3

# Zone IDs
ZONE_NONE = 0
ZONE_STOCKPILE = 1
ZONE_FARM = 2
ZONE_RESIDENTIAL = 3

@dataclass
class GridConfig:
    width: int
    height: int
    chunk_size: int = 16

class Grid:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        
        # Create 3D array: (width, height, layers)
        # Using int16 to save memory, assuming IDs won't exceed 32k
        self.data = np.zeros((width, height, NUM_LAYERS), dtype=np.int16)
        
        # Initialize default terrain (Grass)
        self.data[:, :, LAYER_TERRAIN] = TERRAIN_GRASS
        # Default move cost
        self.data[:, :, LAYER_MOVE_COST] = 1
        
    def set_terrain(self, x: int, y: int, terrain_id: int):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.data[x, y, LAYER_TERRAIN] = terrain_id
            # Update move cost based on terrain (simplified)
            if terrain_id == TERRAIN_WATER:
                self.data[x, y, LAYER_MOVE_COST] = 255 # Impassable
            else:
                self.data[x, y, LAYER_MOVE_COST] = 1

    def get_terrain(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.data[x, y, LAYER_TERRAIN]
        return -1

    def is_walkable(self, x: int, y: int) -> bool:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.data[x, y, LAYER_MOVE_COST] < 255
        return False

    def set_zone(self, x: int, y: int, zone_id: int):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.data[x, y, LAYER_ZONE] = zone_id

    def get_zone(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.data[x, y, LAYER_ZONE]
        return 0

