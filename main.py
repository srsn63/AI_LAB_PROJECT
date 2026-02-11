import sys
import time
import json
import pygame
import asyncio
import traceback
from typing import Dict, Any, List, Optional

from game.core.config import GameConfig
from game.rendering.renderer import GameRenderer
from game.core.network import NetworkClient
from game.agents.network_agent import NetworkedAgent
from game.world.map import World, Tile, TerrainType, TERRAIN_COSTS

class ProxyTile:
    def __init__(self, terrain_value):
        self.terrain = TerrainType(terrain_value)
        self.cost = TERRAIN_COSTS.get(self.terrain, 1.0)

class ProxyWorld:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        # Use simple objects that mimic the Tile class
        self.grid = [[ProxyTile("floor") for _ in range(width)] for _ in range(height)]
        self.resources = []
        self.agents = []

    def update_from_server(self, visible_tiles, visible_resources):
        for t in visible_tiles:
            self.grid[t["y"]][t["x"]] = ProxyTile(t["type"])
            
        # Update resources (only those we see)
        self.resources = []
        for r in visible_resources:
            self.resources.append(ProxyResource(r))

    def is_walkable(self, x, y):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        if self.grid[y][x].terrain == TerrainType.WALL:
            return False
        # Check if occupied by any agent (treat as obstacle)
        for agent in self.agents:
            if getattr(agent, 'health', 0) > 0 and agent.x == x and agent.y == y:
                return False
        return True

    def get_neighbors(self, x, y):
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if self.is_walkable(nx, ny):
                neighbors.append((nx, ny))
        return neighbors

    def get_cost(self, x, y):
        return self.grid[y][x].cost

    def get_resource_at(self, x, y):
        for res in self.resources:
            if res.x == x and res.y == y:
                return res
        return None

class ProxyAgent:
    def __init__(self, d):
        self.id = d["id"]
        self.x = d["x"]
        self.y = d["y"]
        self.health = d["health"]
        self.ammo = d.get("ammo", 0)

class ProxyResource:
    def __init__(self, data):
        self.x = data["x"]
        self.y = data["y"]
        self.type = data["type"]
        self.amount = data["amount"]

class ProxyGameState:
    def __init__(self):
        self.world = None
        self.agents = []
        self.ticks = 0

def main():
    config = GameConfig()
    renderer = GameRenderer()
    client = NetworkClient()
    
    game_state = ProxyGameState()
    local_agent: Optional[NetworkedAgent] = None
    
    def on_server_message(data):
        nonlocal local_agent, game_state
        try:
            msg_type = data.get("type")
            if not msg_type:
                return
                
            if msg_type == "init":
                print(f"--- INIT RECEIVED for Agent {data['agent_id']} ---")
                # Re-initialize local state with server map
                map_data = data["map"]
                game_state.world = ProxyWorld(map_data["width"], map_data["height"])
                
                # Fill proxy world with initial map data
                print(f"Building proxy world {map_data['width']}x{map_data['height']}...")
                for y, row in enumerate(map_data["grid"]):
                    for x, terrain in enumerate(row):
                        game_state.world.grid[y][x] = ProxyTile(terrain)
                
                # Create the local agent representation
                spawn = data["spawn"]
                local_agent = NetworkedAgent(
                    id=data["agent_id"], 
                    x=spawn["x"], 
                    y=spawn["y"],
                    health=100.0,
                    ammo=20
                )
                print(f"Local agent {local_agent.id} created at {spawn}")
                
            elif msg_type == "update":
                if not local_agent: 
                    return
                
                server_state = data["state"]
                game_state.ticks = data["tick"]
                
                # 1. Update local agent stats from server
                local_agent.update_from_server(server_state)
                
                # 2. Update visible world
                game_state.world.update_from_server(
                    server_state["tiles"], 
                    server_state["resources"]
                )
                
                # 3. Update other agents (proxy objects for rendering)
                game_state.agents = [local_agent]
                for other_data in server_state["others"]:
                    game_state.agents.append(ProxyAgent(other_data))
                
                # Sync agents to world for pathfinding collision detection
                if game_state.world:
                    game_state.world.agents = game_state.agents

                # 4. Run AI Logic (Client Side!)
                action_packet = local_agent.update(game_state)
                
                # 5. Send action back to server
                if action_packet:
                    # Only send if there's an actual action or position change
                    if action_packet.get("action") or action_packet.get("position"):
                        client.send_action(action_packet)
                    else:
                        # Send heartbeat/empty action occasionally?
                        pass
                    
            elif msg_type == "game_over":
                print(f"Game Over! Winner: Agent {data['winner']}")
        except Exception as e:
            print(f"Error in on_server_message: {e}")
            import traceback
            traceback.print_exc()
            # Maybe show on screen?

    client.add_callback(on_server_message)
    client.start()

    print("Pygame main loop starting...")
    running = True
    loop_count = 0
    try:
        while running:
            loop_count += 1
            # if loop_count % 100 == 0:
            #     print(f"Loop iteration {loop_count}, running={running}")
            
            # Handle Pygame events
            try:
                events = pygame.event.get()
                for event in events:
                    if event.type == pygame.QUIT:
                        print("QUIT event detected")
                        running = False
            except Exception as e:
                print(f"Event Loop Error: {e}")
                traceback.print_exc()
            
            # Render current known state
            try:
                if game_state.world and local_agent:
                    renderer.render(game_state, local_agent_id=local_agent.id)
                else:
                    # Basic clear screen if not initialized
                    if loop_count % 100 == 0:
                        print("Rendering black screen (not initialized)")
                    renderer.screen.fill((0,0,0))
                    # Show waiting text centered on game area
                    wait_font = pygame.font.SysFont("Consolas", 18)
                    wait_txt = wait_font.render("Connecting to server...", True, (80, 160, 255))
                    renderer.screen.blit(wait_txt,
                        (renderer.screen.get_width() // 2 - wait_txt.get_width() // 2,
                         renderer.screen.get_height() // 2 - wait_txt.get_height() // 2))
                    pygame.display.flip()
            except Exception as e:
                print(f"Render Loop Error: {e}")
                traceback.print_exc()
            
            try:
                renderer.tick(config.FPS)
            except Exception as e:
                print(f"Tick Error: {e}")
                traceback.print_exc()
            
    except BaseException as e:
        print(f"Main Loop Outer Error (BaseException): {type(e).__name__}: {e}")
        if not isinstance(e, SystemExit):
            traceback.print_exc()
    finally:
        print(f"Cleaning up and exiting... (loop_count={loop_count}, running={running})")
        try:
            renderer.quit()
        except:
            pass
        sys.exit(0)

if __name__ == "__main__":
    main()
