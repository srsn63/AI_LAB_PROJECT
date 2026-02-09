import unittest
from game.systems.visibility import VisibilitySystem

class TestVisibility(unittest.TestCase):
    def setUp(self):
        self.vis_system = VisibilitySystem()

    def test_visibility_high_close_range(self):
        # Observer at (0,0), Target at (1,1) -> Very close
        # Health 100, Ammo 20 -> High internal confidence
        
        estimate = self.vis_system.update_belief(
            observer_id=1,
            observer_pos=(0, 0),
            target_id=2,
            target_pos=(1, 1),
            current_time=100.0,
            health_ctx=100,
            ammo_ctx=20
        )
        
        # Should be high confidence
        self.assertGreater(estimate.confidence, 0.8)
        # Should be exact position
        self.assertEqual(estimate.estimated_pos, (1, 1))
        # Strategy should be EXACT
        strategy = self.vis_system.get_targeting_strategy(estimate)
        self.assertEqual(strategy, "EXACT_TARGETING")

    def test_visibility_low_long_range_panic(self):
        # Observer at (0,0), Target at (14,14) -> Distance ~19.8 (> 15 range)
        # Health 10, Ammo 0 -> Low internal confidence
        
        # Wait, if distance > 15, vis_score is 0.
        # So confidence should be 0 unless there was a previous belief.
        
        estimate = self.vis_system.update_belief(
            observer_id=1,
            observer_pos=(0, 0),
            target_id=2,
            target_pos=(14, 14),
            current_time=100.0,
            health_ctx=10,
            ammo_ctx=0
        )
        
        self.assertEqual(estimate.confidence, 0.0)
        strategy = self.vis_system.get_targeting_strategy(estimate)
        self.assertEqual(strategy, "SEARCH_MODE")

    def test_visibility_medium_haze(self):
        # Observer at (0,0), Target at (5,0) -> Distance 5 (1/3 max range) -> vis ~0.66
        # Health 50, Ammo 5 -> Medium internal confidence ~0.5
        # Final ~ (0.66*0.7) + (0.5*0.3) = 0.46 + 0.15 = 0.61
        
        estimate = self.vis_system.update_belief(
            observer_id=1,
            observer_pos=(0, 0),
            target_id=2,
            target_pos=(5, 0),
            current_time=100.0,
            health_ctx=50,
            ammo_ctx=5
        )
        
        self.assertTrue(0.4 < estimate.confidence < 0.8)
        strategy = self.vis_system.get_targeting_strategy(estimate)
        self.assertEqual(strategy, "SUPPRESSION_FIRE")
        
        # Position might be noisy
        # We can't strictly assert not equal because random noise might be 0,
        # but statistically it likely varies.

if __name__ == '__main__':
    unittest.main()
