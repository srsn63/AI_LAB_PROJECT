import unittest

from game.world.map import World, TerrainType


class TestWorldMap(unittest.TestCase):
    def test_generate_creates_grid_with_correct_dimensions(self) -> None:
        world = World(width=10, height=8)
        world.generate(seed=42)
        self.assertEqual(len(world.grid), 8)
        self.assertTrue(all(len(row) == 10 for row in world.grid))

    def test_generate_is_deterministic_with_seed(self) -> None:
        world_a = World(width=10, height=10)
        world_b = World(width=10, height=10)
        world_a.generate(seed=123)
        world_b.generate(seed=123)

        terrains_a = [[tile.terrain for tile in row] for row in world_a.grid]
        terrains_b = [[tile.terrain for tile in row] for row in world_b.grid]

        self.assertEqual(terrains_a, terrains_b)

    def test_neighbors_center_cell(self) -> None:
        world = World(width=3, height=3)
        world.generate(seed=1)
        neighbors = set(world.get_neighbors(1, 1))
        expected = {(0, 1), (2, 1), (1, 0), (1, 2)}
        self.assertEqual(neighbors, expected)

    def test_neighbors_edge_cell(self) -> None:
        world = World(width=3, height=3)
        world.generate(seed=1)
        neighbors = set(world.get_neighbors(0, 0))
        expected = {(1, 0), (0, 1)}
        self.assertEqual(neighbors, expected)

    def test_get_cost_matches_tile(self) -> None:
        world = World(width=2, height=2)
        world.generate(seed=7)
        x, y = 1, 1
        tile = world.grid[y][x]
        self.assertEqual(tile.cost, world.get_cost(x, y))

    def test_varied_terrain_distribution(self) -> None:
        world = World(width=20, height=20)
        world.generate(seed=99)
        terrains = {tile.terrain for row in world.grid for tile in row}
        self.assertGreater(len(terrains), 1)


if __name__ == "__main__":
    unittest.main()

