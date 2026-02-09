import logging
import random
from abc import ABC, abstractmethod
from typing import Dict, Optional, Type, TYPE_CHECKING

# Import specific systems (avoid circular imports if possible, or use inside methods)
from game.agents.minimax import Minimax, CombatState, CombatAgentState
from game.systems.economy import ResourceType, UpgradeType

if TYPE_CHECKING:
    from game.agents.base_agent import BaseAgent
    from game.world.map import World

# Setup logger
logger = logging.getLogger("FSM")
# logging.basicConfig(level=logging.INFO) # Disable global config by default

class State(ABC):
    """
    Abstract base class for all FSM states.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    def enter(self, agent: "BaseAgent") -> None:
        """Called when entering the state."""
        pass

    @abstractmethod
    def execute(self, agent: "BaseAgent", world_state: "World") -> Optional[str]:
        """
        Execute state logic.
        Returns the name of the next state if a transition is needed, else None.
        """
        pass

    def exit(self, agent: "BaseAgent") -> None:
        """Called when exiting the state."""
        pass


class FightState(State):
    name = "FIGHT"
    
    def __init__(self, minimax: Optional[Minimax] = None, depth: int = 1):
        self.minimax = minimax or Minimax(aggression=0.8) # Default aggression
        self.depth = depth

    def enter(self, agent):
        # Adjust aggression based on confidence?
        # For now, just reset
        pass

    def execute(self, agent, world_state) -> Optional[str]:
        # 1. Check Vital Transitions
        if agent.health < 20: # Lowered threshold to keep fighting longer
            return "FLEE"
        if agent.ammo <= 0:
            return "SCAVENGE" # Go find ammo/scrap
        
        # 2. Execute Combat Logic (Minimax)
        target = None
        min_dist = float('inf')
        
        potential_targets = getattr(world_state, 'agents', [])
        for other in potential_targets:
            if other.id != agent.id and other.health > 0:
                dist = abs(agent.x - other.x) + abs(agent.y - other.y)
                if dist < min_dist:
                    min_dist = dist
                    target = other
        
        if target:
            # If target is too far, stop fighting and scavenge
            if min_dist > 12: # Increased chase range
                return "SCAVENGE"

            # Construct Combat State
            c_agent = CombatAgentState(agent.x, agent.y, agent.health, agent.ammo)
            c_opp = CombatAgentState(target.x, target.y, target.health, target.ammo)
            state = CombatState(c_agent, c_opp)
            
            # Run Minimax
            move, score = self.minimax.get_best_move(state, depth=self.depth)
            
            # Apply Move (Simplified: Agent updates position directly or shoots)
            # In a real engine, we'd emit a Command. Here we modify agent state directly for Phase 9 demo.
            if move == "ATTACK":
                agent.ammo -= 1
                target.health -= 10
                print(f"[Agent {agent.id}] Action: ATTACK Agent {target.id} | Score: {score:.2f}")
            elif move.startswith("MOVE"):
                old_pos = (agent.x, agent.y)
                if move == "MOVE_LEFT":
                    agent.x -= 1
                elif move == "MOVE_RIGHT":
                    agent.x += 1
                elif move == "MOVE_UP":
                    agent.y -= 1
                elif move == "MOVE_DOWN":
                    agent.y += 1
                print(f"[Agent {agent.id}] Action: {move} to ({agent.x}, {agent.y}) | Combat Score: {score:.2f}")
                
        else:
            # No enemies? Go back to scavenging
            return "SCAVENGE"

        return None

    def exit(self, agent):
        pass


class FleeState(State):
    name = "FLEE"

    def enter(self, agent):
        pass

    def execute(self, agent, world_state) -> Optional[str]:
        if agent.health > 70:
            return "SCAVENGE"
            
        # Flee Logic: Move towards corners or away from enemies
        if not agent.path:
            # Plan path to safety (e.g., center of map or a corner)
            w, h = 20, 15
            world = getattr(world_state, 'world', None)
            if world:
                w, h = world.width, world.height
            
            # Simple safety: pick a corner furthest from center
            targets = [(0,0), (w-1, 0), (0, h-1), (w-1, h-1)]
            target = random.choice(targets)
            
            if world:
                agent.plan_path(target, world)
            
        return None

    def exit(self, agent):
        agent.path = [] # Clear path on exit


class ScavengeState(State):
    name = "SCAVENGE"

    def enter(self, agent):
        pass

    def execute(self, agent, world_state) -> Optional[str]:
        # 1. Transitions
        if agent.health < 30:
            return "EAT"
        if agent.inventory.get("scrap", 0) >= 15: # Increased threshold slightly
            return "UPGRADE"
            
        # Check for nearby enemies to initiate FIGHT
        potential_targets = getattr(world_state, 'agents', [])
        for other in potential_targets:
            if other.id != agent.id and other.health > 0:
                dist = abs(agent.x - other.x) + abs(agent.y - other.y)
                if dist < 8:
                    return "FIGHT"
            
        # 2. Logic: Move to nearest resource
        if not agent.path:
            world = getattr(world_state, 'world', None)
            if world and world.resources:
                # Find nearest resource
                nearest = None
                min_dist = float('inf')
                for res in world.resources:
                    dist = abs(agent.x - res.x) + abs(agent.y - res.y)
                    if dist < min_dist:
                        min_dist = dist
                        nearest = res
                
                if nearest:
                    agent.plan_path((nearest.x, nearest.y), world)
            else:
                # Wander if no resources
                import random
                w, h = 20, 15
                if world:
                    w, h = world.width, world.height
                rx, ry = random.randint(0, w-1), random.randint(0, h-1)
                if world:
                    agent.plan_path((rx, ry), world)

        # 3. Resource collection check
        world = getattr(world_state, 'world', None)
        if world:
            for i, res in enumerate(world.resources):
                if res.x == agent.x and res.y == agent.y:
                    # Collect!
                    from game.systems.economy import ResourceType
                    res_type = ResourceType(res.type)
                    world_state.economy.collect_resource(agent, res_type, res.amount)
                    print(f"[Agent {agent.id}] Collected: {res.amount} {res.type} at ({res.x}, {res.y})")
                    world.resources.pop(i)
                    agent.path = [] # Target reached/gone
                    break
                
        return None

    def exit(self, agent):
        pass


class EatState(State):
    name = "EAT"

    def enter(self, agent):
        pass

    def execute(self, agent, world_state) -> Optional[str]:
        # Try to eat
        if hasattr(world_state, 'economy'):
            success = world_state.economy.consume_item(agent, ResourceType.FOOD, 1)
            if not success:
                # No food? Go scavenge
                return "SCAVENGE"
            else:
                print(f"[Agent {agent.id}] EATING: Health is now {agent.health:.1f}")
        
        # Go back to scavenging after eating (or if we can't eat anymore)
        return "SCAVENGE"

    def exit(self, agent):
        pass


class UpgradeState(State):
    name = "UPGRADE"

    def enter(self, agent):
        pass

    def execute(self, agent, world_state) -> Optional[str]:
        if hasattr(world_state, 'economy'):
             # Try buy health upgrade or weapon damage
             upgrades_to_check = [UpgradeType.MAX_HEALTH, UpgradeType.WEAPON_DMG]
             bought_anything = False
             
             for utype in upgrades_to_check:
                 upgrade = world_state.economy.get_affordable_upgrade(agent, utype)
                 if upgrade:
                     if world_state.economy.purchase_upgrade(agent, upgrade):
                         print(f"[Agent {agent.id}] PURCHASED Upgrade: {upgrade.name} (Level {upgrade.level})")
                         bought_anything = True
                         break # Buy one at a time to prevent double-spending in one tick
             
             # If we can't afford anything or already have all upgrades, go back to scavenging
             if not bought_anything:
                 # Check if we still have enough scrap to potentially buy something later
                 # If we have scrap but get_affordable_upgrade returned None, it means 
                 # we either already have all upgrades or the current ones are too expensive.
                 return "SCAVENGE"
        
        # Always return to scavenge after trying to upgrade to avoid getting stuck
        return "SCAVENGE"

    def exit(self, agent):
        pass


class FiniteStateMachine:
    """
    Finite State Machine controller.
    """
    def __init__(self, agent: "BaseAgent", minimax: Optional[Minimax] = None):
        self.agent = agent
        self.states: Dict[str, State] = {
            "FIGHT": FightState(minimax),
            "FLEE": FleeState(),
            "SCAVENGE": ScavengeState(),
            "EAT": EatState(),
            "UPGRADE": UpgradeState(),
        }
        self.current_state: Optional[State] = None

    def set_state(self, state_name: str) -> None:
        if state_name not in self.states:
            logger.error(f"State {state_name} not found.")
            return

        new_state = self.states[state_name]
        
        if self.current_state:
            self.current_state.exit(self.agent)
            old_name = self.current_state.name
        else:
            old_name = "None"

        self.current_state = new_state
        self.current_state.enter(self.agent)
        logger.info(f"Agent {self.agent.id} transition: {old_name} -> {new_state.name}")

    def update(self, world_state) -> None:
        if not self.current_state:
            return
        
        next_state_name = self.current_state.execute(self.agent, world_state)
        if next_state_name:
            self.transition(next_state_name)

    def transition(self, state_name: str):
        self.set_state(state_name)
