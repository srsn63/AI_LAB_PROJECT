import math
import time
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from copy import deepcopy

# Type aliases
Coord = Tuple[int, int]

@dataclass
class CombatAgentState:
    x: int
    y: int
    health: float
    ammo: int

@dataclass
class CombatState:
    agent: CombatAgentState
    opponent: CombatAgentState
    distance: float = 0.0
    
    def __post_init__(self):
        self.distance = math.sqrt(
            (self.agent.x - self.opponent.x)**2 + 
            (self.agent.y - self.opponent.y)**2
        )

class Minimax:
    """
    Minimax algorithm with Alpha-Beta pruning for combat decisions.
    """
    def __init__(self, aggression: float = 0.5):
        """
        :param aggression: 0.0 (Defensive) to 1.0 (Aggressive).
        """
        self.aggression = aggression
        self.profiling_data = {"calls": 0, "time_ms": 0.0}

    def get_best_move(self, state: CombatState, depth: int) -> Tuple[str, float]:
        """
        Returns the best move (action_name) and its score.
        """
        start_time = time.perf_counter()
        self.profiling_data["calls"] = 0
        
        # We maximize for 'agent', minimize for 'opponent'
        best_score = -float('inf')
        best_move = None
        
        # Get all possible moves for the maximizing player (Agent)
        moves = self._get_possible_moves(state, is_maximizing=True)
        
        alpha = -float('inf')
        beta = float('inf')
        
        for move_name, next_state in moves:
            score = self._minimax(next_state, depth - 1, alpha, beta, False)
            if score > best_score:
                best_score = score
                best_move = move_name
            alpha = max(alpha, score)
            if beta <= alpha:
                break
        
        end_time = time.perf_counter()
        self.profiling_data["time_ms"] = (end_time - start_time) * 1000.0
        
        return best_move, best_score

    def _minimax(self, state: CombatState, depth: int, alpha: float, beta: float, is_maximizing: bool) -> float:
        self.profiling_data["calls"] += 1
        
        if depth == 0 or state.agent.health <= 0 or state.opponent.health <= 0:
            return self.evaluate(state)

        if is_maximizing:
            max_eval = -float('inf')
            for _, next_state in self._get_possible_moves(state, True):
                eval_score = self._minimax(next_state, depth - 1, alpha, beta, False)
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = float('inf')
            for _, next_state in self._get_possible_moves(state, False):
                eval_score = self._minimax(next_state, depth - 1, alpha, beta, True)
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
            return min_eval

    def evaluate(self, state: CombatState) -> float:
        """
        Evaluation function weighted by:
        - Health difference
        - Ammo difference
        - Positional advantage (Distance)
        - Personality aggression
        """
        # 1. Health Differential
        health_diff = state.agent.health - state.opponent.health
        
        # 2. Ammo Differential
        ammo_diff = state.agent.ammo - state.opponent.ammo
        
        # 3. Positional Advantage (Distance)
        # Aggressive -> Closer is better (minimize distance)
        # Defensive -> Further is better (maximize distance)
        # We normalize distance effect. 
        # Let's say optimal close range is 0, max range is ~20.
        dist = state.distance
        if self.aggression > 0.5:
            # Penalize distance
            dist_score = -dist
        else:
            # Reward distance (up to a point, say 10 units)
            dist_score = dist
            
        # Weights
        w_health = 1.0 + self.aggression  # Aggressive cares more about health diff (killing)
        w_ammo = 0.5
        w_dist = 0.2
        
        score = (health_diff * w_health) + (ammo_diff * w_ammo) + (dist_score * w_dist)
        return score

    def _get_possible_moves(self, state: CombatState, is_maximizing: bool) -> List[Tuple[str, CombatState]]:
        """
        Generates next states based on simple movement/attack actions.
        Simplified combat model:
        - MOVE_U/D/L/R (1 step)
        - ATTACK (reduces opponent health if ammo > 0)
        """
        moves = []
        
        # Who is moving?
        actor = state.agent if is_maximizing else state.opponent
        other = state.opponent if is_maximizing else state.agent
        
        # Possible Actions
        directions = [
            ("MOVE_UP", 0, -1),
            ("MOVE_DOWN", 0, 1),
            ("MOVE_LEFT", -1, 0),
            ("MOVE_RIGHT", 1, 0)
        ]
        
        # 1. Movement
        for name, dx, dy in directions:
            new_actor = deepcopy(actor)
            new_actor.x += dx
            new_actor.y += dy
            
            # Create new state
            if is_maximizing:
                new_state = CombatState(new_actor, deepcopy(other))
            else:
                new_state = CombatState(deepcopy(other), new_actor)
            
            moves.append((name, new_state))
            
        # 2. Attack (if ammo available)
        if actor.ammo > 0:
            new_actor = deepcopy(actor)
            new_other = deepcopy(other)
            
            new_actor.ammo -= 1
            # Simplified damage model: 10 damage fixed
            new_other.health -= 10 
            
            if is_maximizing:
                new_state = CombatState(new_actor, new_other)
            else:
                new_state = CombatState(new_other, new_actor)
                
            moves.append(("ATTACK", new_state))
            
        return moves
