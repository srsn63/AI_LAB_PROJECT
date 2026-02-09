from dataclasses import dataclass
from typing import Dict, List, Callable

@dataclass
class TriangularSet:
    """Defines a triangular membership function."""
    low: float
    peak: float
    high: float

    def membership(self, x: float) -> float:
        if x <= self.low or x >= self.high:
            return 0.0
        elif x == self.peak:
            return 1.0
        elif x < self.peak:
            # Handle case where low == peak (e.g. at boundary 0)
            if self.peak == self.low:
                return 1.0
            return (x - self.low) / (self.peak - self.low)
        else:
            # Handle case where high == peak
            if self.high == self.peak:
                return 1.0
            return (self.high - x) / (self.high - self.peak)

class FuzzyVariable:
    """Represents a linguistic variable (e.g., 'Health') with fuzzy sets."""
    def __init__(self, name: str):
        self.name = name
        self.sets: Dict[str, TriangularSet] = {}

    def add_set(self, name: str, low: float, peak: float, high: float):
        self.sets[name] = TriangularSet(low, peak, high)

    def fuzzify(self, value: float) -> Dict[str, float]:
        """Returns membership degrees for all sets."""
        return {name: fset.membership(value) for name, fset in self.sets.items()}

class FuzzyLogic:
    """
    Fuzzy logic system for confidence-based decision making.
    """
    def __init__(self):
        # Input Variables
        self.health = FuzzyVariable("Health")
        # Extend boundaries to avoid 0.0 drop-off at edges
        self.health.add_set("LOW", -1, 0, 50)
        self.health.add_set("MEDIUM", 25, 50, 75)
        self.health.add_set("HIGH", 50, 100, 101)

        self.ammo = FuzzyVariable("Ammo")
        self.ammo.add_set("LOW", -1, 0, 5)
        self.ammo.add_set("MEDIUM", 2, 5, 10)
        self.ammo.add_set("HIGH", 5, 20, 21)
        
        # We can add more inputs like Distance, EnemyStrength, etc.

    def evaluate_confidence(self, health_val: float, ammo_val: float) -> float:
        """
        Evaluates 'Confidence' score (0.0 to 1.0) for engaging in combat.
        Rules:
        - If Health is HIGH and Ammo is HIGH -> Confidence is VERY HIGH
        - If Health is MEDIUM and Ammo is MEDIUM -> Confidence is MEDIUM
        - If Health is LOW or Ammo is LOW -> Confidence is LOW
        """
        # Fuzzify inputs
        h = self.health.fuzzify(health_val)
        a = self.ammo.fuzzify(ammo_val)

        # Rule Evaluation (Mamdani-style inference, simplified for scalar output)
        # We'll map linguistic outputs to scalar centroids or weights.
        # LOW_CONFIDENCE = 0.2
        # MEDIUM_CONFIDENCE = 0.5
        # HIGH_CONFIDENCE = 0.9

        # Rule 1: HIGH Health AND HIGH Ammo -> HIGH Confidence
        rule1_strength = min(h["HIGH"], a["HIGH"])
        
        # Rule 2: MEDIUM Health AND MEDIUM Ammo -> MEDIUM Confidence
        rule2_strength = min(h["MEDIUM"], a["MEDIUM"])
        
        # Rule 3: LOW Health OR LOW Ammo -> LOW Confidence
        rule3_strength = max(h["LOW"], a["LOW"])

        # Defuzzification (Weighted Average)
        numerator = (rule1_strength * 0.9) + (rule2_strength * 0.5) + (rule3_strength * 0.2)
        denominator = rule1_strength + rule2_strength + rule3_strength

        if denominator == 0:
            return 0.0
            
        return numerator / denominator
