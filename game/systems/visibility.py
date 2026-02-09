from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import math
import random

from game.agents.fuzzy import FuzzyLogic

# Type alias
Coord = Tuple[int, int]

@dataclass
class TargetEstimate:
    """Represents a probabilistic belief about a target's location."""
    estimated_pos: Coord
    confidence: float  # 0.0 to 1.0 (Fuzzy output)
    last_seen_time: float

class VisibilitySystem:
    """
    Handles probabilistic visibility, fog of war, and sensor data.
    """
    def __init__(self):
        self.fuzzy = FuzzyLogic()
        # Map: observer_id -> {target_id -> TargetEstimate}
        self.beliefs: Dict[int, Dict[int, TargetEstimate]] = {}

    def calculate_visibility_confidence(
        self, 
        observer_pos: Coord, 
        target_pos: Coord, 
        world_map=None
    ) -> float:
        """
        Calculates raw visibility score based on distance and line-of-sight.
        Returns 0.0 to 1.0.
        """
        dx = observer_pos[0] - target_pos[0]
        dy = observer_pos[1] - target_pos[1]
        dist = math.sqrt(dx*dx + dy*dy)
        
        # Simple distance decay model
        # Max visibility range = 15 tiles
        max_range = 15.0
        if dist > max_range:
            return 0.0
            
        # Line of sight check could go here (raycasting on world_map)
        
        # Linear drop-off
        base_vis = 1.0 - (dist / max_range)
        return max(0.0, base_vis)

    def update_belief(
        self, 
        observer_id: int, 
        observer_pos: Coord,
        target_id: int, 
        target_pos: Coord,
        current_time: float,
        health_ctx: float, # Context for fuzzy logic (observer health)
        ammo_ctx: float    # Context for fuzzy logic (observer ammo)
    ) -> TargetEstimate:
        """
        Updates the observer's belief about a target using Fuzzy Logic.
        """
        if observer_id not in self.beliefs:
            self.beliefs[observer_id] = {}
            
        # 1. Physical Visibility
        vis_score = self.calculate_visibility_confidence(observer_pos, target_pos)
        
        # 2. Fuzzy Confidence Evaluation
        # We combine physical visibility with agent's internal state (Health/Ammo)
        # to determine "Combat Confidence" which acts as a filter for perception accuracy.
        # High confidence -> Sharp senses (trusts vision)
        # Low confidence -> Panic/Haze (reduced accuracy)
        
        internal_confidence = self.fuzzy.evaluate_confidence(health_ctx, ammo_ctx)
        
        # Final tracking confidence is a blend
        # If I can't see them (vis=0), confidence drops rapidly
        if vis_score <= 0.01:
            # Decay existing belief if present
            current_belief = self.beliefs[observer_id].get(target_id)
            if current_belief:
                # Confidence decays over time
                new_conf = max(0.0, current_belief.confidence - 0.1)
                self.beliefs[observer_id][target_id].confidence = new_conf
                return self.beliefs[observer_id][target_id]
            else:
                return TargetEstimate((0,0), 0.0, current_time)

        # If visible, confidence is boosted by internal state
        final_confidence = (vis_score * 0.7) + (internal_confidence * 0.3)
        final_confidence = min(1.0, max(0.0, final_confidence))
        
        # 3. Position Uncertainty
        # Low confidence adds noise to the estimated position
        if final_confidence > 0.8:
            # Exact estimation
            est_x, est_y = target_pos
        else:
            # Add noise inversely proportional to confidence
            noise_range = int((1.0 - final_confidence) * 5) # Up to 5 tiles error
            noise_x = random.randint(-noise_range, noise_range)
            noise_y = random.randint(-noise_range, noise_range)
            est_x = target_pos[0] + noise_x
            est_y = target_pos[1] + noise_y
            
        estimate = TargetEstimate(
            estimated_pos=(est_x, est_y),
            confidence=final_confidence,
            last_seen_time=current_time
        )
        self.beliefs[observer_id][target_id] = estimate
        return estimate

    def get_targeting_strategy(self, estimate: TargetEstimate) -> str:
        """
        Determines targeting behavior based on confidence.
        """
        if estimate.confidence > 0.8:
            return "EXACT_TARGETING"
        elif estimate.confidence > 0.4:
            return "SUPPRESSION_FIRE" # Spray area
        else:
            return "SEARCH_MODE" # Don't shoot, look
