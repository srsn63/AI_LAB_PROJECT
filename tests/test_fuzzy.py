import unittest
from game.agents.fuzzy import FuzzyLogic, TriangularSet

class TestFuzzyLogic(unittest.TestCase):
    def setUp(self):
        self.fuzzy = FuzzyLogic()

    def test_triangular_membership(self):
        # Set: Low=0, Peak=5, High=10
        t_set = TriangularSet(0, 5, 10)
        
        self.assertAlmostEqual(t_set.membership(0), 0.0)
        self.assertAlmostEqual(t_set.membership(5), 1.0)
        self.assertAlmostEqual(t_set.membership(10), 0.0)
        self.assertAlmostEqual(t_set.membership(2.5), 0.5)
        self.assertAlmostEqual(t_set.membership(7.5), 0.5)
        self.assertAlmostEqual(t_set.membership(-1), 0.0)
        self.assertAlmostEqual(t_set.membership(11), 0.0)

    def test_confidence_high(self):
        # High Health (100), High Ammo (20) -> Should be close to 0.9
        confidence = self.fuzzy.evaluate_confidence(100, 20)
        self.assertAlmostEqual(confidence, 0.9)

    def test_confidence_low(self):
        # Low Health (10), Low Ammo (0) -> Should be close to 0.2
        confidence = self.fuzzy.evaluate_confidence(10, 0)
        self.assertAlmostEqual(confidence, 0.2)

    def test_confidence_mixed(self):
        # Medium Health (50), Medium Ammo (5) -> Should be blended
        # Health 50 is Peak MEDIUM (1.0) and Low HIGH (0.0)
        # Ammo 5 is Peak MEDIUM (1.0) and Low HIGH (0.0)
        # Rule 2 triggers max strength 1.0 -> 0.5 output
        confidence = self.fuzzy.evaluate_confidence(50, 5)
        self.assertAlmostEqual(confidence, 0.5)

    def test_confidence_conflict(self):
        # High Health (100) but Low Ammo (0)
        # Rule 1 (High/High): min(1.0, 0.0) = 0.0
        # Rule 3 (Low/Low): max(0.0, 1.0) = 1.0
        # Result should be dominated by Rule 3 (Low Confidence = 0.2)
        confidence = self.fuzzy.evaluate_confidence(100, 0)
        self.assertAlmostEqual(confidence, 0.2)

    def test_output_ranges(self):
        # Test extreme and random inputs to ensure output is in [0, 1]
        test_cases = [
            (0, 0), (100, 20), (50, 5), (100, 0), (0, 20),
            (-10, -10), (200, 50), (float('inf'), float('inf'))
        ]
        for h, a in test_cases:
            confidence = self.fuzzy.evaluate_confidence(h, a)
            self.assertTrue(0.0 <= confidence <= 1.0, f"Confidence {confidence} out of range for health={h}, ammo={a}")

if __name__ == '__main__':
    unittest.main()
