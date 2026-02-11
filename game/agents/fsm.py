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
        agent.path = []
        agent._path_index = 0
        agent._fight_repath_ticks = 0
        agent._fight_target_pos = None

    def execute(self, agent, world_state) -> Optional[str]:
        if agent.health <= 20:
            return "FLEE"
        if agent.ammo <= 0:
            return "SCAVENGE"

        def chebyshev(ax, ay, bx, by):
            return max(abs(ax - bx), abs(ay - by))

        world = getattr(world_state, "world", None)
        potential_targets = [
            o for o in getattr(world_state, "agents", [])
            if getattr(o, "id", None) != agent.id and getattr(o, "health", 0) > 0
        ]
        if not potential_targets:
            return "SCAVENGE"

        target = min(
            potential_targets,
            key=lambda o: (chebyshev(agent.x, agent.y, o.x, o.y), getattr(o, "health", 0)),
        )
        dist = chebyshev(agent.x, agent.y, target.x, target.y)

        attack_range = 5

        if dist <= attack_range:
            c_agent = CombatAgentState(agent.x, agent.y, agent.health, agent.ammo)
            c_opp = CombatAgentState(target.x, target.y, target.health, target.ammo)
            state = CombatState(c_agent, c_opp)

            move, score = self.minimax.get_best_move(state, depth=self.depth)

            if move == "ATTACK":
                agent._pending_attack_target_id = target.id
                agent.ammo -= 1
                print(f"[Agent {agent.id}] Action: ATTACK Agent {target.id} | Score: {score:.2f}")

                if hasattr(world_state, "economy"):
                    damage = 10 + agent.upgrades.get(UpgradeType.WEAPON_DMG, 0) * 5
                    target.health -= damage
                    if target.health <= 0:
                        print(f"[Local] Agent {target.id} was killed by Agent {agent.id}")
            else:
                dx, dy = 0, 0
                if move == "MOVE_LEFT":
                    dx = -1
                elif move == "MOVE_RIGHT":
                    dx = 1
                elif move == "MOVE_UP":
                    dy = -1
                elif move == "MOVE_DOWN":
                    dy = 1

                if dx != 0 or dy != 0:
                    nx, ny = agent.x + dx, agent.y + dy
                    if world is None or world.is_walkable(nx, ny):
                        agent.set_path([(nx, ny)])
            return None

        agent._fight_repath_ticks = getattr(agent, "_fight_repath_ticks", 0) + 1
        target_pos = (target.x, target.y)

        repath = (
            world is not None
            and (
                not agent.path
                or agent._path_index >= len(agent.path)
                or getattr(agent, "_fight_target_pos", None) != target_pos
                or agent._fight_repath_ticks >= 4
            )
        )

        if repath and world is not None:
            agent._fight_repath_ticks = 0
            agent._fight_target_pos = target_pos

            best_tile = None
            best_dist = float("inf")
            for ty in range(max(0, target.y - attack_range), min(world.height, target.y + attack_range + 1)):
                for tx in range(max(0, target.x - attack_range), min(world.width, target.x + attack_range + 1)):
                    if chebyshev(tx, ty, target.x, target.y) > attack_range:
                        continue
                    if not world.is_walkable(tx, ty):
                        continue
                    d = abs(agent.x - tx) + abs(agent.y - ty)
                    if d < best_dist:
                        best_dist = d
                        best_tile = (tx, ty)

            if best_tile:
                agent.path = []
                agent.plan_path(best_tile, world)
                # Fallback if path planning failed for best_tile
                if not agent.path or len(agent.path) < 2:
                     best_tile = None # Trigger random fallback below
            
            if not best_tile:
                neighbors = [n for n in world.get_neighbors(agent.x, agent.y) if world.is_walkable(*n)]
                if neighbors:
                    neighbors.sort(key=lambda p: chebyshev(p[0], p[1], target.x, target.y))
                    agent.set_path([neighbors[0]])

        return None

    def exit(self, agent):
        agent.path = []
        agent._path_index = 0
        for attr in ("_fight_repath_ticks", "_fight_target_pos", "_pending_attack_target_id"):
            if hasattr(agent, attr):
                delattr(agent, attr)


class FleeState(State):
    name = "FLEE"

    def enter(self, agent):
        agent.path = []
        agent._path_index = 0
        agent._flee_ticks = 0

    def execute(self, agent, world_state) -> Optional[str]:
        if agent.health > 70:
            return "SCAVENGE"

        agent._flee_ticks = getattr(agent, "_flee_ticks", 0) + 1

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

        if agent._flee_ticks >= 3:
            current_dist = min_threat_dist((agent.x, agent.y))
            if not threats or current_dist >= 10:
                if agent.health < 60 and agent.inventory.get("food", 0) > 0:
                    return "EAT"
                return "SCAVENGE"

        if agent._flee_ticks >= 30:
            return "SCAVENGE"

        is_path_finished = not agent.path or agent._path_index >= len(agent.path)
        if is_path_finished:
            candidates = []
            if threats:
                vx = sum(agent.x - t.x for t in threats)
                vy = sum(agent.y - t.y for t in threats)
                if vx == 0 and vy == 0:
                    vx = random.choice([-1, 1])
                    vy = random.choice([-1, 1])
                step_x = 0 if vx == 0 else (1 if vx > 0 else -1)
                step_y = 0 if vy == 0 else (1 if vy > 0 else -1)
                for dist in (5, 8, 12, 16):
                    tx = max(0, min(world.width - 1, agent.x + step_x * dist + random.randint(-2, 2)))
                    ty = max(0, min(world.height - 1, agent.y + step_y * dist + random.randint(-2, 2)))
                    candidates.append((tx, ty))

            for _ in range(18):
                candidates.append((random.randint(0, world.width - 1), random.randint(0, world.height - 1)))

            candidates = [c for c in candidates if c != (agent.x, agent.y)]
            candidates = list(dict.fromkeys(candidates))

            planned = False
            for target in candidates:
                if not world.is_walkable(*target):
                    continue
                agent.plan_path(target, world)
                if agent.path and len(agent.path) >= 2:
                    planned = True
                    break
                agent.path = []
                agent._path_index = 0

            if not planned:
                # Fallback if path planning failed or no best tile
                print(f"[Agent {agent.id}] Flee path failed. Picking random neighbor.")
                neighbors = [n for n in world.get_neighbors(agent.x, agent.y) if world.is_walkable(*n)]
                if neighbors:
                    target = random.choice(neighbors)
                    agent.plan_path(target, world)


        return None

    def exit(self, agent):
        agent.path = []
        agent._path_index = 0
        if hasattr(agent, "_flee_ticks"):
            delattr(agent, "_flee_ticks")


class ScavengeState(State):
    name = "SCAVENGE"

    def enter(self, agent):
        pass

    def execute(self, agent, world_state) -> Optional[str]:
        low_health = agent.health < 30
        has_food = agent.inventory.get("food", 0) > 0
        if low_health and has_food:
            return "EAT"
        if agent.inventory.get("scrap", 0) >= 15:
            return "UPGRADE"

        def chebyshev(ax, ay, bx, by):
            return max(abs(ax - bx), abs(ay - by))

        potential_targets = getattr(world_state, "agents", [])
        for other in potential_targets:
            if getattr(other, "id", None) != agent.id and getattr(other, "health", 0) > 0:
                dist = chebyshev(agent.x, agent.y, other.x, other.y)
                if dist <= 7 and agent.health > 40 and agent.ammo > 0:
                    return "FIGHT"

        agent._scavenge_ticks = getattr(agent, "_scavenge_ticks", 0) + 1
            
        is_path_finished = not agent.path or agent._path_index >= len(agent.path)
        is_stuck = getattr(agent, "_stuck_ticks", 0) > 2
        
        if is_path_finished or is_stuck or (getattr(agent, "_scavenge_ticks", 0) % 4 == 0):
            world = getattr(world_state, 'world', None)
            
            if is_stuck and world:
                print(f"[Agent {agent.id}] Stuck in SCAVENGE. Moving randomly.")
                neighbors = [n for n in world.get_neighbors(agent.x, agent.y) if world.is_walkable(*n)]
                if neighbors:
                    target = random.choice(neighbors)
                    agent.path = []
                    agent.plan_path(target, world)
                return None

            if world and world.resources:
                nearest = None
                best_score = float("-inf")
                min_dist = float('inf')
                for res in world.resources:
                    if res.x == agent.x and res.y == agent.y:
                        continue
                        
                    dist = abs(agent.x - res.x) + abs(agent.y - res.y)
                    desire = 0.0
                    if res.type == "food":
                        if low_health and not has_food:
                            desire += 12.0
                        if agent.health < 50:
                            desire += 6.0
                        elif agent.health < 80:
                            desire += 3.0
                        else:
                            desire += 0.5
                    if res.type == "ammo":
                        if agent.ammo < 3:
                            desire += 6.0
                        elif agent.ammo < 15:
                            desire += 2.0
                        else:
                            desire += 0.5
                    if res.type == "scrap":
                        desire += 1.0
                    score = desire * 10.0 - dist
                    if score > best_score:
                        best_score = score
                        min_dist = dist
                        nearest = res
                
                if nearest:
                    # Clear old path before planning new one
                    agent.path = []
                    agent.plan_path((nearest.x, nearest.y), world)
                    
                    # Fix for "Halted" bug: If path is invalid/empty, try next resource
                    if not agent.path or len(agent.path) < 2:
                        print(f"[Agent {agent.id}] Path to nearest resource failed. Retrying...")
                        # Remove this resource from consideration locally by temporarily setting distance to inf
                        # Actually, just try the next best score?
                        # Re-sort resources by score and try until one works
                        
                        scored_resources = []
                        for res in world.resources:
                            if res.x == agent.x and res.y == agent.y: continue
                            
                            dist = abs(agent.x - res.x) + abs(agent.y - res.y)
                            desire = 0.0
                            if res.type == "food":
                                if low_health and not has_food: desire += 12.0
                                if agent.health < 50: desire += 6.0
                                elif agent.health < 80: desire += 3.0
                                else: desire += 0.5
                            if res.type == "ammo":
                                if agent.ammo < 3: desire += 6.0
                                elif agent.ammo < 15: desire += 2.0
                                else: desire += 0.5
                            if res.type == "scrap": desire += 1.0
                            score = desire * 10.0 - dist
                            scored_resources.append((score, res))
                        
                        scored_resources.sort(key=lambda x: x[0], reverse=True)
                        
                        found_path = False
                        for score, res in scored_resources:
                            agent.path = []
                            agent.plan_path((res.x, res.y), world)
                            if agent.path and len(agent.path) >= 2:
                                agent._scavenge_goal = (res.x, res.y, res.type)
                                found_path = True
                                break
                        
                        if not found_path:
                            # Total failure to path to any resource? Wander.
                            nearest = None # Trigger wander block below
                    else:
                        agent._scavenge_goal = (nearest.x, nearest.y, nearest.type)
                
                if not nearest:
                    w, h = world.width, world.height
                    planned = False
                    for _ in range(8):
                        rx, ry = random.randint(0, w - 1), random.randint(0, h - 1)
                        agent.path = []
                        agent.plan_path((rx, ry), world)
                        if agent.path and len(agent.path) >= 2:
                            planned = True
                            break
                    if not planned:
                        neighbors = [n for n in world.get_neighbors(agent.x, agent.y) if world.is_walkable(*n)]
                        if neighbors:
                            agent.set_path([random.choice(neighbors)])
            else:
                # Wander if no resources
                w, h = 20, 15
                if world:
                    w, h = world.width, world.height
                if world:
                    planned = False
                    for _ in range(8):
                        rx, ry = random.randint(0, w - 1), random.randint(0, h - 1)
                        agent.path = []
                        agent.plan_path((rx, ry), world)
                        if agent.path and len(agent.path) >= 2:
                            planned = True
                            break
                    if not planned:
                        neighbors = [n for n in world.get_neighbors(agent.x, agent.y) if world.is_walkable(*n)]
                        if neighbors:
                            agent.set_path([random.choice(neighbors)])

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
                    if hasattr(agent, "_scavenge_goal"):
                        delattr(agent, "_scavenge_goal")
                    break
                
        return None

    def exit(self, agent):
        for attr in ("_scavenge_ticks", "_scavenge_goal"):
            if hasattr(agent, attr):
                delattr(agent, attr)


class EatState(State):
    name = "EAT"

    def enter(self, agent):
        pass

    def execute(self, agent, world_state) -> Optional[str]:
        target_health = 60

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

        if agent.health < target_health and agent.inventory.get("food", 0) > 0:
            return None

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
