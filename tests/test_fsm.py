import unittest
from game.agents.base_agent import BaseAgent
from game.agents.fsm import FightState, FleeState, ScavengeState

class MockWorld:
    pass

class TestFSM(unittest.TestCase):
    def setUp(self):
        self.agent = BaseAgent(id=1, x=0, y=0)
        self.world = MockWorld()

    def test_initial_state(self):
        # Default state is SCAVENGE
        self.assertIsInstance(self.agent.fsm.current_state, ScavengeState)

    def test_transition_low_health_scavenge_to_eat(self):
        # SCAVENGE -> EAT if health < 30
        self.agent.fsm.set_state("SCAVENGE")
        self.agent.health = 20
        self.agent.update(self.world)
        self.assertEqual(self.agent.fsm.current_state.name, "EAT")

    def test_transition_fight_to_flee(self):
        # FIGHT -> FLEE if health < 30
        self.agent.fsm.set_state("FIGHT")
        self.agent.health = 20
        self.agent.update(self.world)
        self.assertEqual(self.agent.fsm.current_state.name, "FLEE")

    def test_transition_scavenge_to_upgrade(self):
        # SCAVENGE -> UPGRADE if scrap > 10
        self.agent.fsm.set_state("SCAVENGE")
        self.agent.inventory["scrap"] = 15
        self.agent.update(self.world)
        self.assertEqual(self.agent.fsm.current_state.name, "UPGRADE")

    def test_invalid_state(self):
        # Should log error but not crash or change state unexpectedly
        current = self.agent.fsm.current_state
        self.agent.fsm.set_state("INVALID_STATE")
        self.assertEqual(self.agent.fsm.current_state, current)

if __name__ == '__main__':
    unittest.main()
