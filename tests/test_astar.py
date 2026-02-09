import unittest

from game.agents.astar import AStar, PathfindingMap


class GridMap(PathfindingMap):
    def __init__(self, grid):
        self.grid = grid
        self.height = len(grid)
        self.width = len(grid[0]) if self.height > 0 else 0

    def get_neighbors(self, x, y):
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx = x + dx
            ny = y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                if self.grid[ny][nx] == 0:
                    neighbors.append((nx, ny))
        return neighbors

    def get_cost(self, x, y):
        return 1.0


class TestAStar(unittest.TestCase):
    def test_finds_shortest_path_on_simple_grid(self):
        grid = [
            [0, 0, 0, 0],
            [0, 1, 1, 0],
            [0, 0, 0, 0],
        ]
        nav_map = GridMap(grid)
        astar = AStar()

        start = (0, 0)
        goal = (3, 2)

        path = astar.find_path(start, goal, nav_map)

        self.assertEqual(path[0], start)
        self.assertEqual(path[-1], goal)
        self.assertEqual(len(path) - 1, 5)

    def test_no_path_found(self):
        grid = [
            [0, 1, 0],
            [1, 1, 1],
            [0, 1, 0],
        ]
        nav_map = GridMap(grid)
        astar = AStar()
        
        path = astar.find_path((0, 0), (2, 2), nav_map)
        self.assertEqual(path, [])

    def test_start_equals_goal(self):
        grid = [[0]]
        nav_map = GridMap(grid)
        astar = AStar()
        
        path = astar.find_path((0, 0), (0, 0), nav_map)
        self.assertEqual(path, [(0, 0)])


if __name__ == "__main__":
    unittest.main()

