from typing import List, Tuple, Optional
import numpy as np
from src.world.grid import Grid, ZONE_NONE

class ZoneManager:
    def __init__(self, grid: Grid):
        self.grid = grid
        # Cache for zone locations to avoid scanning the whole grid
        # dict[zone_type] -> set of (x, y)
        self.zone_cache = {}

    def mark_zone(self, x: int, y: int, zone_type: int):
        current_zone = self.grid.get_zone(x, y)
        if current_zone == zone_type:
            return

        # Remove from old cache
        if current_zone != ZONE_NONE:
            if current_zone in self.zone_cache:
                self.zone_cache[current_zone].discard((x, y))

        # Set new zone
        self.grid.set_zone(x, y, zone_type)
        
        # Add to new cache
        if zone_type != ZONE_NONE:
            if zone_type not in self.zone_cache:
                self.zone_cache[zone_type] = set()
            self.zone_cache[zone_type].add((x, y))

    def get_nearest_zone_tile(self, start_pos: Tuple[int, int], zone_type: int) -> Optional[Tuple[int, int]]:
        """Find the nearest tile of a specific zone type."""
        if zone_type not in self.zone_cache or not self.zone_cache[zone_type]:
            return None

        best_pos = None
        min_dist = float('inf')
        
        sx, sy = start_pos
        
        # Simple scan of cached locations
        # For large numbers of zone tiles, a spatial index (KDTree) would be better,
        # but for now iterating over a set is fine.
        for zx, zy in self.zone_cache[zone_type]:
            dist = abs(zx - sx) + abs(zy - sy) # Manhattan distance
            if dist < min_dist:
                min_dist = dist
                best_pos = (zx, zy)
                
        return best_pos

