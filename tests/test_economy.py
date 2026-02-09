import unittest
from game.systems.economy import EconomySystem, ResourceType, UpgradeType

class MockAgent:
    def __init__(self, scrap=0, food=0, health=50.0):
        self.inventory = {"scrap": scrap, "food": food}
        self.health = health
        self.ammo = 0

class TestEconomy(unittest.TestCase):
    def setUp(self):
        self.economy = EconomySystem()

    def test_collect_scrap(self):
        agent = MockAgent(scrap=0)
        self.economy.collect_resource(agent, ResourceType.SCRAP, 10)
        self.assertEqual(agent.inventory["scrap"], 10)

    def test_consume_food_heals(self):
        agent = MockAgent(food=2, health=50.0)
        # Consume 1 food -> +10 health
        success = self.economy.consume_item(agent, ResourceType.FOOD, 1)
        
        self.assertTrue(success)
        self.assertEqual(agent.inventory["food"], 1)
        self.assertEqual(agent.health, 60.0)

    def test_consume_food_fails_if_empty(self):
        agent = MockAgent(food=0)
        success = self.economy.consume_item(agent, ResourceType.FOOD, 1)
        self.assertFalse(success)

    def test_purchase_upgrade_success(self):
        # "Leather Armor" costs 15
        agent = MockAgent(scrap=20, health=100.0)
        
        upgrade = self.economy.get_affordable_upgrade(agent, UpgradeType.MAX_HEALTH)
        self.assertIsNotNone(upgrade)
        self.assertEqual(upgrade.name, "Leather Armor")
        
        purchased = self.economy.purchase_upgrade(agent, upgrade)
        
        self.assertTrue(purchased)
        self.assertEqual(agent.inventory["scrap"], 5) # 20 - 15
        self.assertIn("upgrade_Leather Armor", agent.inventory)
        self.assertEqual(agent.health, 120.0) # +20 buff

    def test_purchase_upgrade_insufficient_funds(self):
        agent = MockAgent(scrap=5)
        upgrade = self.economy.get_affordable_upgrade(agent, UpgradeType.MAX_HEALTH)
        # Should be None because can't afford
        self.assertIsNone(upgrade)

if __name__ == '__main__':
    unittest.main()
