import asyncio
import json
import random
import time
from typing import Dict, List, Set, Optional
import websockets
from game.core.config import GameConfig
from game.world.map import World, ResourceEntity
from game.world.generator import MapGenerator
from game.systems.economy import EconomySystem, ResourceType, UpgradeType
from game.agents.base_agent import BaseAgent

class GameServer:
    def __init__(self, host="127.0.0.1", port=8888):
        self.host = host
        self.port = port
        self.config = GameConfig()
        self.world: Optional[World] = None
        self.economy = EconomySystem()
        self.agents: Dict[int, BaseAgent] = {}
        self.clients: Dict[int, websockets.WebSocketServerProtocol] = {}
        self.agent_positions: Dict[int, tuple] = {}
        self.game_over = False
        self.game_started = False
        self.winner = None
        self.ticks = 0
        self.seed = random.randint(0, 1000000)
        
        # Game state tracking
        self.max_agents = 2 # Back to 2
        self.connected_agents = 0
        self._last_drop_tick = 0
        self._drop_cooldown_ticks = 25
        self._min_world_resources = 6
        self._drop_spawn_radius = 7
        
    def _maybe_spawn_drops(self) -> None:
        if not self.world:
            return
        if not self.game_started:
            return
        if self.ticks - self._last_drop_tick < self._drop_cooldown_ticks:
            return
        
        total_resources = len(self.world.resources)
        food_count = 0
        for r in self.world.resources:
            if r.type == "food":
                food_count += 1
        
        spawn_count = 0
        if total_resources == 0:
            spawn_count = 12
        elif total_resources < self._min_world_resources:
            spawn_count = self._min_world_resources - total_resources
        
        if food_count == 0:
            spawn_count = max(spawn_count, 2)
        
        if spawn_count <= 0:
            return
        
        alive_agents = [a for a in self.agents.values() if a.health > 0]
        if not alive_agents:
            return
        
        occupied = {(a.x, a.y) for a in alive_agents}
        existing = {(r.x, r.y) for r in self.world.resources}
        
        def choose_type() -> str:
            low_hp = any(a.health < 40 for a in alive_agents)
            low_ammo = any(a.ammo < 3 for a in alive_agents)
            roll = random.random()
            if low_hp and roll < 0.55:
                return "food"
            if low_ammo and roll < 0.35:
                return "ammo"
            return "scrap" if roll < 0.7 else "food"
        
        spawned = 0
        for _ in range(spawn_count):
            center = random.choice(alive_agents)
            chosen = None
            
            for _ in range(50):
                dx = random.randint(-self._drop_spawn_radius, self._drop_spawn_radius)
                dy = random.randint(-self._drop_spawn_radius, self._drop_spawn_radius)
                x = center.x + dx
                y = center.y + dy
                if not (0 <= x < self.world.width and 0 <= y < self.world.height):
                    continue
                if not self.world.is_walkable(x, y):
                    continue
                if (x, y) in occupied or (x, y) in existing:
                    continue
                chosen = (x, y)
                break
            
            if not chosen:
                for _ in range(200):
                    x = random.randint(0, self.world.width - 1)
                    y = random.randint(0, self.world.height - 1)
                    if not self.world.is_walkable(x, y):
                        continue
                    if (x, y) in occupied or (x, y) in existing:
                        continue
                    chosen = (x, y)
                    break
            
            if not chosen:
                continue
            
            r_type = choose_type()
            if r_type == "food":
                amount = 1
            elif r_type == "ammo":
                amount = random.randint(5, 10)
            else:
                amount = random.randint(2, 5)
            
            x, y = chosen
            self.world.resources.append(ResourceEntity(x, y, r_type, amount))
            existing.add((x, y))
            spawned += 1
        
        if spawned > 0:
            self._last_drop_tick = self.ticks
            print(f"[Server] Spawned {spawned} drops (world resources: {len(self.world.resources)})")
        
    async def start(self):
        print(f"Starting Game Server on {self.host}:{self.port} (Seed: {self.seed})...")
        random.seed(self.seed)
        
        # Generate World
        tiles_x = self.config.SCREEN_WIDTH // self.config.TILE_SIZE
        tiles_y = self.config.SCREEN_HEIGHT // self.config.TILE_SIZE
        self.world = World(width=tiles_x, height=tiles_y)
        self.world.generate(seed=self.seed)
        
        # Get balanced spawns
        generator = MapGenerator(self.world.width, self.world.height, seed=self.seed)
        self.spawn_points = generator.get_balanced_spawns(self.world.grid, count=self.max_agents)
        
        async with websockets.serve(self.handler, self.host, self.port):
            print("Server is listening...")
            await self.game_loop()

    async def handler(self, websocket):
        # Assign unique agent ID
        agent_id = 1
        while agent_id in self.clients:
            agent_id += 1
            
        if agent_id > self.max_agents:
            print(f"Server full. Rejecting Agent {agent_id}")
            await websocket.send(json.dumps({"type": "error", "message": "Server full"}))
            return

        print(f"Agent {agent_id} connecting...")
        
        # Initialize agent on server
        # Ensure we don't index out of bounds if max_agents > spawns
        spawn_idx = (agent_id - 1) % len(self.spawn_points)
        spawn = self.spawn_points[spawn_idx]
        agent = BaseAgent(id=agent_id, x=spawn[0], y=spawn[1], health=100.0, ammo=20)
        
        # CRITICAL: Set agent BEFORE adding to clients to avoid race condition in game_loop
        self.agents[agent_id] = agent
        self.clients[agent_id] = websocket
        self.connected_agents += 1
        
        print(f"Agent {agent_id} initialized at {spawn}. Total connected: {self.connected_agents}")

        # Send initial config
        init_packet = {
            "type": "init",
            "agent_id": agent_id,
            "spawn": {"x": spawn[0], "y": spawn[1]},
            "map": {
                "width": self.world.width,
                "height": self.world.height,
                "grid": [[t.terrain.value for t in row] for row in self.world.grid]
            },
            "config": {
                "vision_radius": 8,
                "fps": 5
            }
        }
        await websocket.send(json.dumps(init_packet))
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if data["type"] == "action":
                        print(f"Action from Agent {agent_id}: {data}")
                        self.process_action(agent_id, data)
                except Exception as e:
                    print(f"Error processing message from Agent {agent_id}: {e}")
        except websockets.ConnectionClosed:
            print(f"Agent {agent_id} disconnected.")
        except Exception as e:
            print(f"Unexpected error in handler for Agent {agent_id}: {e}")
        finally:
            # Handle disconnection
            if agent_id in self.clients:
                del self.clients[agent_id]
            if agent_id in self.agents:
                del self.agents[agent_id]
            self.connected_agents -= 1
            print(f"Cleaned up Agent {agent_id}. Remaining: {self.connected_agents}")

    def process_action(self, agent_id, data):
        agent = self.agents.get(agent_id)
        if not agent:
            print(f"[Server] Action from unknown agent {agent_id}")
            return
        if agent.health <= 0:
            print(f"[Server] Action from dead agent {agent_id}")
            return
            
        action = data.get("action")
        target_pos = data.get("position") # Client-proposed position
        
        # 1. Movement validation (allow diagonal: max(dx, dy) <= 1)
        if target_pos:
            tx, ty = target_pos[0], target_pos[1]
            dx = abs(tx - agent.x)
            dy = abs(ty - agent.y)
            # Allow max 1 tile move per tick
            if max(dx, dy) <= 1:
                if self.world.is_walkable(tx, ty):
                    # Check if another agent is there
                    occupied = False
                    for other_id, other in self.agents.items():
                        if other_id != agent_id and other.x == tx and other.y == ty and other.health > 0:
                            occupied = True
                            break
                    
                    if not occupied:
                        if (agent.x, agent.y) != (tx, ty):
                            # print(f"[Server] Agent {agent_id} moved to ({tx}, {ty})")
                            agent.x, agent.y = tx, ty
                    else:
                        print(f"[Server] Agent {agent_id} move to ({tx}, {ty}) BLOCKED: Occupied")
                else:
                    print(f"[Server] Agent {agent_id} move to ({tx}, {ty}) BLOCKED: Not walkable ({self.world.grid[ty][tx].terrain})")
            else:
                print(f"[Server] Agent {agent_id} move to ({tx}, {ty}) BLOCKED: Too far (dx={dx}, dy={dy})")
                
        # 2. Scavenge validation
        if action == "SCAVENGE":
            res = self.world.get_resource_at(agent.x, agent.y)
            if res:
                agent.inventory[res.type] = agent.inventory.get(res.type, 0) + res.amount
                # Also give some ammo/health if it's food/ammo
                if res.type == "food":
                    agent.health = min(100.0, agent.health + 5)
                elif res.type == "ammo":
                    agent.ammo += 10
                    
                self.world.resources.remove(res)
                print(f"[Server] Agent {agent_id} collected {res.amount} {res.type} at ({agent.x}, {agent.y})")
            else:
                # No resource here, maybe it was already taken
                pass
                
        # 3. Combat validation (handled via health reduction)
        if action == "ATTACK":
            target_id = data.get("target_id")
            target = self.agents.get(target_id)
            if target and target.health > 0:
                dist = max(abs(agent.x - target.x), abs(agent.y - target.y))
                if dist <= 5 and agent.ammo > 0: # Combat range and ammo check
                    agent.ammo -= 1
                    damage = 10 + agent.upgrades.get(UpgradeType.WEAPON_DMG, 0) * 5
                    target.health -= damage
                    print(f"[Server] Agent {agent_id} attacked Agent {target_id} for {damage} damage. Target HP: {target.health}")
                    if target.health <= 0:
                        print(f"[Server] Agent {target_id} was killed by Agent {agent_id}")

        # 4. Economy validation (UPGRADE/EAT)
        if action == "EAT":
            if agent.inventory.get("food", 0) >= 1:
                agent.inventory["food"] -= 1
                agent.health = min(agent.max_health, agent.health + 20)
                print(f"[Server] Agent {agent_id} ate food. Health: {agent.health}")
                
        if action == "UPGRADE":
            upgrade_type_str = data.get("upgrade_type")
            if upgrade_type_str:
                try:
                    u_type = UpgradeType[upgrade_type_str]
                    cost = self.economy.get_upgrade_cost(agent, u_type)
                    if cost is not None and agent.inventory.get("scrap", 0) >= cost:
                        agent.inventory["scrap"] -= cost
                        upgraded = self.economy.apply_upgrade(agent, u_type)
                        if upgraded:
                            print(f"[Server] Agent {agent_id} upgraded {upgrade_type_str} to level {agent.upgrades[u_type]}")
                except Exception as e:
                    print(f"[Server] Upgrade error for Agent {agent_id}: {e}")

    async def game_loop(self):
        print("Game loop started.")
        while not self.game_over:
            if self.connected_agents >= 1: # Start if at least one agent is connected
                if not self.game_started and self.connected_agents >= 2:
                    self.game_started = True
                if self.ticks % 50 == 0:
                    print(f"Game tick {self.ticks}, connected: {self.connected_agents}")
                # Run one tick of game logic every 200ms (5Hz)
                await asyncio.sleep(0.2)
                self.ticks += 1
                self._maybe_spawn_drops()
                
                # Update visibility and send state to each client
                disconnected_agents = []
                # Use a copy of clients to avoid issues if items are added/removed
                client_items = list(self.clients.items())
                for agent_id, websocket in client_items:
                    try:
                        # Safety check: ensure agent exists
                        if agent_id not in self.agents:
                            continue
                            
                        agent = self.agents[agent_id]
                        if agent.health <= 0:
                            continue
                            
                        state = self.get_visible_state(agent_id)
                        await websocket.send(json.dumps({
                            "type": "update",
                            "tick": self.ticks,
                            "state": state
                        }))
                    except websockets.ConnectionClosed:
                        disconnected_agents.append(agent_id)
                    except Exception as e:
                        print(f"Error updating/sending to Agent {agent_id}: {e}")
                        import traceback
                        traceback.print_exc()
                        disconnected_agents.append(agent_id)
                
                # Cleanup disconnected clients
                for agent_id in disconnected_agents:
                    print(f"Cleaning up disconnected Agent {agent_id}")
                    del self.clients[agent_id]
                    self.connected_agents -= 1
                
                # Check for game over
                alive = [a for a in self.agents.values() if a.health > 0]
                if self.game_started and len(alive) <= 1:
                    self.game_over = True
                    if alive:
                        self.winner = alive[0].id
                    print(f"Game Over! Winner: Agent {self.winner}")
                    
                    # Notify clients
                    for websocket in self.clients.values():
                        await websocket.send(json.dumps({
                            "type": "game_over",
                            "winner": self.winner
                        }))
            else:
                await asyncio.sleep(1.0) # Wait for connections

    def get_visible_state(self, agent_id):
        agent = self.agents[agent_id]
        radius = 8 # Visible radius
        
        visible_tiles = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                tx, ty = agent.x + dx, agent.y + dy
                if 0 <= tx < self.world.width and 0 <= ty < self.world.height:
                    tile = self.world.grid[ty][tx]
                    visible_tiles.append({
                        "x": tx, "y": ty, "type": tile.terrain.value
                    })
                    
        visible_resources = []
        for res in self.world.resources:
            if abs(res.x - agent.x) <= radius and abs(res.y - agent.y) <= radius:
                visible_resources.append({
                    "x": res.x, "y": res.y, "type": res.type, "amount": res.amount
                })
                
        other_agents = []
        for other_id, other in self.agents.items():
            if other_id != agent_id and other.health > 0:
                if abs(other.x - agent.x) <= radius and abs(other.y - agent.y) <= radius:
                    other_agents.append({
                        "id": other_id,
                        "x": other.x,
                        "y": other.y,
                        "health": other.health,
                        "ammo": other.ammo
                    })
                    
        return {
            "self": {
                "x": agent.x, "y": agent.y, 
                "health": agent.health, 
                "max_health": agent.max_health,
                "ammo": agent.ammo,
                "inventory": agent.inventory
            },
            "tiles": visible_tiles,
            "resources": visible_resources,
            "others": other_agents
        }

if __name__ == "__main__":
    server = GameServer()
    asyncio.run(server.start())
