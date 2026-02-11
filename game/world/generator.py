import random
import math
from typing import List, Tuple, Set
from game.world.map import TerrainType, Tile, TERRAIN_COSTS

class MapGenerator:
    """
    Structured procedural generation using Perlin-like noise and Cellular Automata.
    """
    def __init__(self, width: int, height: int, seed: int = None):
        self.width = width
        self.height = height
        self.seed = seed or random.randint(0, 1000000)
        self.rng = random.Random(self.seed)

    def generate(self) -> Tuple[List[List[Tile]], List]:
        # Stage 1: Generate elevation map (simple gradient noise)
        elevation = self._generate_noise_map(octaves=2, persistence=0.5)
        
        # Stage 2: Initial terrain assignment based on elevation
        grid_types = self._initial_terrain_assignment(elevation)
        
        # Stage 3: Apply Cellular Automata to carve caves in rock/wall areas
        grid_types = self._apply_cellular_automata(grid_types, iterations=5)
        
        # Stage 4: Ensure connectivity using flood fill
        grid_types = self._ensure_connectivity(grid_types)
        
        # Stage 5: Final tile conversion
        final_grid = self._finalize_grid(grid_types)
        
        # Stage 6: Place clustered resources
        resources = self._place_resources(final_grid)
        
        return final_grid, resources

    def _place_resources(self, grid: List[List[Tile]]) -> List:
        from game.world.map import ResourceEntity
        resources = []
        
        # Mid-risk areas for scrap (GRASS, ROCK)
        # Low-risk areas for food (MUD, FLOOR)
        # Randomly distributed
        for y in range(self.height):
            for x in range(self.width):
                tile = grid[y][x]
                if tile.terrain == TerrainType.WALL or tile.terrain == TerrainType.WATER:
                    continue
                
                roll = self.rng.random()
                if tile.terrain in [TerrainType.GRASS, TerrainType.ROCK]:
                    if roll < 0.08:
                        resources.append(ResourceEntity(x, y, "scrap", self.rng.randint(2, 5)))
                elif tile.terrain in [TerrainType.MUD, TerrainType.FLOOR]:
                    if roll < 0.05:
                        resources.append(ResourceEntity(x, y, "food", 1))
                    elif roll < 0.08:
                        resources.append(ResourceEntity(x, y, "ammo", self.rng.randint(5, 10)))
                        
        return resources

    def _generate_noise_map(self, octaves: int, persistence: float) -> List[List[float]]:
        noise_map = [[0.0 for _ in range(self.width)] for _ in range(self.height)]
        
        for o in range(octaves):
            frequency = 2 ** o
            amplitude = persistence ** o
            
            # Simple value noise implementation
            grid_w = max(2, self.width // (frequency + 1))
            grid_h = max(2, self.height // (frequency + 1))
            
            points = {}
            for gy in range(frequency + 2):
                for gx in range(frequency + 2):
                    points[(gx, gy)] = self.rng.random()
            
            for y in range(self.height):
                for x in range(self.width):
                    tx = (x / self.width) * frequency
                    ty = (y / self.height) * frequency
                    
                    gx0, gy0 = int(tx), int(ty)
                    gx1, gy1 = gx0 + 1, gy0 + 1
                    
                    frac_x = tx - gx0
                    frac_y = ty - gy0
                    
                    # Bilinear interpolation
                    v00 = points[(gx0, gy0)]
                    v10 = points[(gx1, gy0)]
                    v01 = points[(gx0, gy1)]
                    v11 = points[(gx1, gy1)]
                    
                    v0 = v00 * (1 - frac_x) + v10 * frac_x
                    v1 = v01 * (1 - frac_x) + v11 * frac_x
                    val = v0 * (1 - frac_y) + v1 * frac_y
                    
                    noise_map[y][x] += val * amplitude
                    
        # Normalize
        min_v = min(min(row) for row in noise_map)
        max_v = max(max(row) for row in noise_map)
        if max_v > min_v:
            noise_map = [[(v - min_v) / (max_v - min_v) for v in row] for row in noise_map]
            
        return noise_map

    def _initial_terrain_assignment(self, elevation: List[List[float]]) -> List[List[TerrainType]]:
        grid = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                v = elevation[y][x]
                if v < 0.2:
                    terrain = TerrainType.WATER
                elif v < 0.4:
                    terrain = TerrainType.MUD
                elif v < 0.7:
                    terrain = TerrainType.GRASS
                elif v < 0.85:
                    terrain = TerrainType.FLOOR
                else:
                    # Potential wall/rock area for CA
                    terrain = TerrainType.WALL if self.rng.random() < 0.45 else TerrainType.FLOOR
                row.append(terrain)
            grid.append(row)
        return grid

    def _apply_cellular_automata(self, grid: List[List[TerrainType]], iterations: int) -> List[List[TerrainType]]:
        current_grid = grid
        for _ in range(iterations):
            next_grid = [row[:] for row in current_grid]
            for y in range(self.height):
                for x in range(self.width):
                    # Only apply CA to "solid" terrain types
                    wall_count = 0
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            if dx == 0 and dy == 0: continue
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < self.width and 0 <= ny < self.height:
                                if current_grid[ny][nx] in [TerrainType.WALL, TerrainType.ROCK]:
                                    wall_count += 1
                            else:
                                # Borders count as walls
                                wall_count += 1
                    
                    if wall_count >= 5:
                        next_grid[y][x] = TerrainType.WALL
                    else:
                        # If it was a wall but now has few neighbors, make it floor/rock
                        if current_grid[y][x] == TerrainType.WALL:
                            next_grid[y][x] = TerrainType.ROCK if self.rng.random() < 0.5 else TerrainType.FLOOR
            current_grid = next_grid
        return current_grid

    def _ensure_connectivity(self, grid: List[List[TerrainType]]) -> List[List[TerrainType]]:
        # Find all walkable regions using flood fill
        walkable_set = set()
        for y in range(self.height):
            for x in range(self.width):
                if grid[y][x] != TerrainType.WALL:
                    walkable_set.add((x, y))
        
        if not walkable_set:
            return grid # Should not happen

        regions = []
        visited = set()
        
        for start_pos in walkable_set:
            if start_pos in visited: continue
            
            region = set()
            stack = [start_pos]
            while stack:
                curr = stack.pop()
                if curr in visited: continue
                visited.add(curr)
                region.add(curr)
                
                cx, cy = curr
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) in walkable_set and (nx, ny) not in visited:
                        stack.append((nx, ny))
            regions.append(region)
            
        if not regions: return grid
        
        # Keep only the largest region, turn others to walls
        largest_region = max(regions, key=len)
        for y in range(self.height):
            for x in range(self.width):
                if (x, y) not in largest_region:
                    grid[y][x] = TerrainType.WALL
                    
        return grid

    def _finalize_grid(self, grid: List[List[TerrainType]]) -> List[List[Tile]]:
        final_grid = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                terrain = grid[y][x]
                cost = TERRAIN_COSTS[terrain]
                row.append(Tile(terrain=terrain, cost=cost))
            final_grid.append(row)
        return final_grid

    def get_balanced_spawns(self, grid: List[List[Tile]], count: int = 2) -> List[Tuple[int, int]]:
        """Find walkable points that are far apart."""
        walkable = []
        for y in range(self.height):
            for x in range(self.width):
                if grid[y][x].terrain != TerrainType.WALL:
                    walkable.append((x, y))
        
        if len(walkable) < count:
            return [(0, 0)] * count # Fallback
            
        # Greedy distance maximization
        spawns = [self.rng.choice(walkable)]
        while len(spawns) < count:
            best_pos = None
            max_min_dist = -1
            
            # Sample some candidates
            candidates = self.rng.sample(walkable, min(20, len(walkable)))
            for cand in candidates:
                min_dist = min(abs(cand[0] - s[0]) + abs(cand[1] - s[1]) for s in spawns)
                if min_dist > max_min_dist:
                    max_min_dist = min_dist
                    best_pos = cand
            spawns.append(best_pos)
            
        return spawns
