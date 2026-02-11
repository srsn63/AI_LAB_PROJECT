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
        if agent.health <= 20: # Lowered threshold to keep fighting longer
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
            # In networked mode, NetworkedAgent will detect these changes, revert them locally,
            # and send the request to the server.
            
            if move == "ATTACK":
                agent.ammo -= 1
                # We don't update target health locally in networked mode
                # The server will handle it and update us via state
                print(f"[Agent {agent.id}] Action: ATTACK Agent {target.id} | Score: {score:.2f}")
            elif move.startswith("MOVE"):
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
        agent.path = []
        agent._path_index = 0

    def execute(self, agent, world_state) -> Optional[str]:
        if agent.health > 70:
            return "SCAVENGE"

        world = getattr(world_state, "world", None)
        if not world:
            return None

        threats = []
        for other in getattr(world_state, "agents", []):
            if getattr(other, "id", None) == agent.id:
                continue
            if getattr(other, "health", 0) <= 0:
                continue
            if getattr(other, "x", None) is None or getattr(other, "y", None) is None:
                continue
            threats.append(other)

        def min_threat_dist(pos):
            if not threats:
                return 10**9
            px, py = pos
            return min(abs(px - t.x) + abs(py - t.y) for t in threats)

        def nearest_walkable(pos):
            tx, ty = pos
            if world.is_walkable(tx, ty):
                return (tx, ty)
            max_r = max(world.width, world.height)
            for r in range(1, max_r):
                for dx in range(-r, r + 1):
                    for dy in (-r, r):
                        nx, ny = tx + dx, ty + dy
                        if world.is_walkable(nx, ny):
                            return (nx, ny)
                for dy in range(-r + 1, r):
                    for dx in (-r, r):
                        nx, ny = tx + dx, ty + dy
                        if world.is_walkable(nx, ny):
                            return (nx, ny)
            return None

        is_path_finished = not agent.path or agent._path_index >= len(agent.path)
        if is_path_finished:
            bases = [
                (0, 0),
                (world.width - 1, 0),
                (0, world.height - 1),
                (world.width - 1, world.height - 1),
                (world.width // 2, world.height // 2),
            ]

            candidates = []
            for base in bases:
                p = nearest_walkable(base)
                if p:
                    candidates.append(p)

            for _ in range(40):
                rx = random.randint(0, world.width - 1)
                ry = random.randint(0, world.height - 1)
                if world.is_walkable(rx, ry):
                    candidates.append((rx, ry))

            candidates = [p for p in candidates if p != (agent.x, agent.y)]
            candidates.sort(key=lambda p: (min_threat_dist(p), random.random()), reverse=True)

            planned = False
            for target in candidates[:25]:
                agent.plan_path(target, world)
                if agent.path and len(agent.path) >= 2:
                    planned = True
                    break
                agent.path = []
                agent._path_index = 0

            if not planned:
                neighbors = getattr(world, "get_neighbors", lambda x, y: [])(agent.x, agent.y)
                if neighbors:
                    best = max(neighbors, key=min_threat_dist)
                    agent.set_path([best])

        return None

    def exit(self, agent):
        agent.path = []
        agent._path_index = 0


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
        # Fix: Check if path is finished or empty
        is_path_finished = not agent.path or agent._path_index >= len(agent.path)
        
        if is_path_finished:
            world = getattr(world_state, 'world', None)
            if world and world.resources:
                # Find nearest resource that IS NOT the one we are currently on
                nearest = None
                min_dist = float('inf')
                for res in world.resources:
                    # Skip if we are already on this resource
                    if res.x == agent.x and res.y == agent.y:
                        continue
                        
                    dist = abs(agent.x - res.x) + abs(agent.y - res.y)
                    if dist < min_dist:
                        min_dist = dist
                        nearest = res
                
                if nearest:
                    # Clear old path before planning new one
                    agent.path = []
                    agent.plan_path((nearest.x, nearest.y), world)
                else:
                    # If we are only seeing the resource we are on, just stay here
                    # and wait for it to be collected.
                    pass
            else:
                # Wander if no resources
                import random
                w, h = 20, 15
                if world:
                    w, h = world.width, world.height
                rx, ry = random.randint(0, w-1), random.randint(0, h-1)
                if world:
                    agent.path = []
                    agent.plan_path((rx, ry), world)

        # 3. Resource collection check
        world = getattr(world_state, 'world', None)
        if world:
            # We check if we are on a resource. 
            # In networked mode, the server handles collection, 
            # but we still want to clear the path locally if we reached it.
            for i, res in enumerate(world.resources):
                if res.x == agent.x and res.y == agent.y:
                    # If not networked, collect immediately
                    if hasattr(world_state, 'economy'):
                        from game.systems.economy import ResourceType
                        res_type = ResourceType(res.type)
                        world_state.economy.collect_resource(agent, res_type, res.amount)
                        print(f"[Agent {agent.id}] Collected: {res.amount} {res.type} at ({res.x}, {res.y})")
                        world.resources.pop(i)
                    
                    # Clear path regardless (we reached the target)
                    agent.path = []
                    agent._path_index = 0
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
        else:
            # Networked mode: The NetworkedAgent.update will detect the state is "EAT"
            # and send the action. We just need to check if we have food locally.
            if agent.inventory.get("food", 0) <= 0:
                return "SCAVENGE"
        
        # Go back to scavenging after eating
        return "SCAVENGE"

    def exit(self, agent):
        pass


class UpgradeState(State):
    name = "UPGRADE"

    def enter(self, agent):
        pass

    def execute(self, agent, world_state) -> Optional[str]:
        if hasattr(world_state, 'economy'):
             # Local/Singleplayer logic
             upgrades_to_check = [UpgradeType.MAX_HEALTH, UpgradeType.WEAPON_DMG]
             bought_anything = False
             
             for utype in upgrades_to_check:
                 upgrade = world_state.economy.get_affordable_upgrade(agent, utype)
                 if upgrade:
                     if world_state.economy.purchase_upgrade(agent, upgrade):
                         print(f"[Agent {agent.id}] PURCHASED Upgrade: {upgrade.name} (Level {upgrade.level})")
                         bought_anything = True
                         break
             
             if not bought_anything:
                 return "SCAVENGE"
        else:
            # Networked logic: set intent for NetworkedAgent to pick up
            # Choose an upgrade based on some heuristic
            if agent.health < agent.max_health:
                agent.pending_upgrade_type = "MAX_HEALTH"
            else:
                agent.pending_upgrade_type = "WEAPON_DMG"
        
        # Always return to scavenge after trying to upgrade
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
