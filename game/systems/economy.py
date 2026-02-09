from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

class ResourceType(Enum):
    SCRAP = "scrap"
    FOOD = "food"
    AMMO = "ammo"

class UpgradeType(Enum):
    WEAPON_DMG = "weapon_damage"
    MAX_HEALTH = "max_health"
    SPEED = "speed"

@dataclass
class Upgrade:
    name: str
    type: UpgradeType
    cost: int
    value: float  # The amount it increases the stat by
    level: int = 1

class EconomySystem:
    """
    Manages resource generation, consumption, and trading/scavenging logic.
    """
    def __init__(self):
        # Define available upgrades
        self.available_upgrades = {
            UpgradeType.WEAPON_DMG: [
                Upgrade("Sharpened Blade", UpgradeType.WEAPON_DMG, cost=10, value=5.0, level=1),
                Upgrade("Titanium Edge", UpgradeType.WEAPON_DMG, cost=25, value=10.0, level=2),
            ],
            UpgradeType.MAX_HEALTH: [
                Upgrade("Leather Armor", UpgradeType.MAX_HEALTH, cost=15, value=20.0, level=1),
                Upgrade("Kevlar Vest", UpgradeType.MAX_HEALTH, cost=30, value=50.0, level=2),
            ]
        }

    def collect_resource(self, agent, resource: ResourceType, amount: int):
        """Adds resource to agent inventory."""
        current = agent.inventory.get(resource.value, 0)
        agent.inventory[resource.value] = current + amount

    def consume_item(self, agent, resource: ResourceType, amount: int) -> bool:
        """Attempts to consume a resource. Returns True if successful."""
        current = agent.inventory.get(resource.value, 0)
        if current >= amount:
            agent.inventory[resource.value] = current - amount
            
            # Effect application
            if resource == ResourceType.FOOD:
                agent.health = min(100.0, agent.health + (amount * 10)) # 1 Food = 10 Health
            elif resource == ResourceType.AMMO:
                agent.ammo += amount # Logic usually handles ammo differently, but for consistency
                
            return True
        return False

    def get_affordable_upgrade(self, agent, upgrade_type: UpgradeType) -> Optional[Upgrade]:
        """Checks if agent can afford the next level upgrade."""
        # Simplified: Just gets the first level for now, or next if we tracked levels
        # Assuming agent stores current upgrade level in inventory or separate dict
        # For Phase 8, we'll just check if they have ANY upgrade of this type
        
        # This logic would be more complex in a full persistent system
        upgrades = self.available_upgrades.get(upgrade_type, [])
        for upg in upgrades:
            # Check if already owned (mock check)
            if f"upgrade_{upg.name}" in agent.inventory:
                continue
                
            if agent.inventory.get("scrap", 0) >= upg.cost:
                return upg
        return None

    def purchase_upgrade(self, agent, upgrade: Upgrade) -> bool:
        """Executes purchase."""
        if agent.inventory.get("scrap", 0) >= upgrade.cost:
            agent.inventory["scrap"] -= upgrade.cost
            agent.inventory[f"upgrade_{upgrade.name}"] = 1
            
            # Apply Stat Buff
            if upgrade.type == UpgradeType.MAX_HEALTH:
                # Heals and boosts cap (conceptually)
                agent.health += upgrade.value 
            # Weapon damage would modify an agent attribute 'damage_modifier'
            
            return True
        return False
