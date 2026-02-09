import unittest
from game.agents.minimax import Minimax, CombatState, CombatAgentState

class TestMinimax(unittest.TestCase):
    def setUp(self):
        self.minimax = Minimax(aggression=0.8) # Aggressive

    def test_aggressive_agent_attacks(self):
        # Scenario: Agent has ammo, opponent is close. Agent should ATTACK.
        agent = CombatAgentState(x=0, y=0, health=100, ammo=5)
        opponent = CombatAgentState(x=1, y=0, health=50, ammo=0)
        state = CombatState(agent, opponent)
        
        move, score = self.minimax.get_best_move(state, depth=1)
        
        self.assertEqual(move, "ATTACK")
        # Attacking increases health diff (100 - 40 = 60) vs (100 - 50 = 50)
        # Ammo decreases by 1, but health weight (1.8) > ammo weight (0.5)

    def test_agent_flees_if_low_health(self):
        # Scenario: Agent has low health, opponent high health. 
        # But wait, minimax assumes optimal opponent play.
        # If agent is low, running away might increase distance score.
        # Since aggression is 0.8, distance is penalized (-dist). 
        # So high aggression agent might actually NOT flee easily unless health is weighted very high.
        
        # Let's test a DEFENSIVE agent
        defensive_ai = Minimax(aggression=0.2)
        
        agent = CombatAgentState(x=0, y=0, health=10, ammo=0) # No ammo, dying
        opponent = CombatAgentState(x=2, y=0, health=100, ammo=5)
        state = CombatState(agent, opponent)
        
        move, score = defensive_ai.get_best_move(state, depth=1)
        
        # Defensive agent rewards distance.
        # MOVE_LEFT (-1, 0) -> distance becomes 3. (2 - -1 = 3)
        # MOVE_RIGHT (1, 0) -> distance becomes 1.
        # Should pick MOVE_LEFT (or UP/DOWN to increase distance).
        
        self.assertIn(move, ["MOVE_LEFT", "MOVE_UP", "MOVE_DOWN"])
        self.assertNotEqual(move, "MOVE_RIGHT")

    def test_determinism(self):
        agent = CombatAgentState(x=5, y=5, health=80, ammo=2)
        opponent = CombatAgentState(x=6, y=6, health=70, ammo=2)
        state = CombatState(agent, opponent)
        
        move1, score1 = self.minimax.get_best_move(state, depth=2)
        move2, score2 = self.minimax.get_best_move(state, depth=2)
        
        self.assertEqual(move1, move2)
        self.assertEqual(score1, score2)

    def test_performance_profiling(self):
        agent = CombatAgentState(x=0, y=0, health=100, ammo=5)
        opponent = CombatAgentState(x=2, y=2, health=100, ammo=5)
        state = CombatState(agent, opponent)
        
        self.minimax.get_best_move(state, depth=2)
        
        # Check if profiling data was populated
        self.assertGreater(self.minimax.profiling_data["calls"], 0)
        self.assertGreater(self.minimax.profiling_data["time_ms"], 0)

    def test_evaluation_stability(self):
        # Evaluation should be stable for small changes in state
        agent1 = CombatAgentState(x=0, y=0, health=100, ammo=5)
        opp1 = CombatAgentState(x=1, y=1, health=100, ammo=5)
        score1 = self.minimax.evaluate(CombatState(agent1, opp1))
        
        # Slightly better health for agent
        agent2 = CombatAgentState(x=0, y=0, health=101, ammo=5)
        score2 = self.minimax.evaluate(CombatState(agent2, opp1))
        
        self.assertGreater(score2, score1, "Higher health should result in higher score")
        
        # Slightly further away (defensive AI should like this, aggressive should dislike)
        opp2 = CombatAgentState(x=2, y=2, health=100, ammo=5)
        score3 = self.minimax.evaluate(CombatState(agent1, opp2))
        
        # Our minimax uses aggression to weight distance
        # score += self.aggression * (-dist) -> more distance = lower score for aggressive AI
        self.assertLess(score3, score1, "Greater distance should result in lower score for aggressive AI")

if __name__ == '__main__':
    unittest.main()
