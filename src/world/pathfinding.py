import heapq
import math
from typing import List, Tuple, Optional, Set
from src.world.grid import Grid, LAYER_MOVE_COST

def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    return math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)

def find_path(grid: Grid, start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
    """
    A* Pathfinding.
    Returns a list of (x, y) tuples from start to end.
    Returns empty list if no path found.
    """
    if not grid.is_walkable(end[0], end[1]):
        return []

    start_node = start
    end_node = end

    open_set: List[Tuple[float, Tuple[int, int]]] = []
    heapq.heappush(open_set, (0, start_node))
    
    came_from = {}
    g_score = {start_node: 0.0}
    f_score = {start_node: heuristic(start_node, end_node)}
    
    open_set_hash = {start_node} # Keep track of what's in heap for faster lookup

    while open_set:
        current = heapq.heappop(open_set)[1]
        open_set_hash.remove(current)

        if current == end_node:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            # path.append(start) # Optional: include start? Usually we want steps *after* start
            path.reverse()
            return path

        neighbors = []
        x, y = current
        # 4-way movement
        candidates = [
            (x+1, y), (x-1, y), (x, y+1), (x, y-1)
        ]
        
        # Check bounds and walkability
        for nx, ny in candidates:
            if 0 <= nx < grid.width and 0 <= ny < grid.height:
                # Get move cost from grid layer
                cost = grid.data[nx, ny, LAYER_MOVE_COST]
                if cost < 255: # 255 is impassable
                    neighbors.append(((nx, ny), float(cost)))

        for neighbor, cost in neighbors:
            tentative_g_score = g_score[current] + cost
            
            if tentative_g_score < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(neighbor, end_node)
                
                if neighbor not in open_set_hash:
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))
                    open_set_hash.add(neighbor)
                    
    return []

