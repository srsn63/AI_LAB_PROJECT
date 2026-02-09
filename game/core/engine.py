import time
import random
from typing import Optional, List, Dict
from game.core.config import GameConfig
from game.world.map import World
from game.agents.base_agent import BaseAgent
from game.systems.economy import EconomySystem

class Game:
    """
    Core game engine that manages the game loop and high-level state.
    """
    def __init__(self, renderer=None, headless=False, seed=None):
        self.config = GameConfig()
        self.is_running = False
        self.game_over = False
        self.renderer = renderer
        self.headless = headless
        self.seed = seed or random.randint(0, 1000000)
        
        self.last_time = time.time()
        self.dt = 0.0
        self.accumulator = 0.0
        self.fixed_dt = 1.0 / 60.0 # 60 Hz simulation
        
        # Systems
        self.world: Optional[World] = None
        self.economy: Optional[EconomySystem] = None
        self.agents: List[BaseAgent] = []
        
        # Metrics
        self.metrics = {
            "ticks": 0,
            "agent_states": {}, # {agent_id: {state_name: count}}
            "agent_lifetimes": {}, # {agent_id: ticks}
            "winner": None
        }

    def setup(self):
        """Initialize game resources."""
        if not self.headless:
            print(f"Initializing Game Engine (Seed: {self.seed})...")
        
        random.seed(self.seed)
        
        # 1. Create World
        tiles_x = self.config.SCREEN_WIDTH // self.config.TILE_SIZE
        tiles_y = self.config.SCREEN_HEIGHT // self.config.TILE_SIZE
        self.world = World(width=tiles_x, height=tiles_y)
        self.world.generate(seed=self.seed)
        
        # 2. Initialize Economy
        self.economy = EconomySystem()
        
        # 3. Create Agents
        self._spawn_agents()

    def _spawn_agents(self):
        self.agents = []
        # Agent 1 (Hero) - Start in corners
        agent1 = BaseAgent(id=1, x=2, y=2, health=100.0, ammo=20)
        self.agents.append(agent1)
        
        # Agent 2 (Enemy/Rival) - Start in corners
        agent2 = BaseAgent(id=2, x=18, y=12, health=100.0, ammo=20)
        self.agents.append(agent2)
        
        # Initialize metrics for agents
        for agent in self.agents:
            self.metrics["agent_states"][agent.id] = {}
            self.metrics["agent_lifetimes"][agent.id] = 0

    def get_agent(self, agent_id: int) -> Optional[BaseAgent]:
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None

    def handle_input(self):
        """Process input events."""
        if self.renderer:
            for event in self.renderer.get_events():
                if event.type == "QUIT":
                    self.is_running = False

    def update(self, dt: float):
        """
        Update game state.
        :param dt: Delta time in seconds.
        """
        self.accumulator += dt
        
        while self.accumulator >= self.fixed_dt:
            self._fixed_update()
            self.accumulator -= self.fixed_dt
            self.metrics["ticks"] += 1
            
            # Check for win condition
            alive_agents = [a for a in self.agents if a.health > 0]
            if len(alive_agents) <= 1:
                if alive_agents:
                    self.metrics["winner"] = alive_agents[0].id
                
                if self.headless:
                    self.is_running = False
                    break
                else:
                    self.game_over = True

    def _fixed_update(self):
        """Logic update at a fixed rate."""
        if self.game_over:
            return

        for agent in self.agents:
            if agent.health <= 0:
                continue
                
            # Update metrics
            state_name = agent.fsm.current_state.name if agent.fsm.current_state else "None"
            self.metrics["agent_states"][agent.id][state_name] = \
                self.metrics["agent_states"][agent.id].get(state_name, 0) + 1
            self.metrics["agent_lifetimes"][agent.id] += 1
            
            # Update agent
            agent.update(self)

    def render(self):
        """Render the current state."""
        if self.renderer:
            self.renderer.render(self)

    def run_simulation(self, max_ticks=10000):
        """Start the main game loop."""
        if not self.agents:
            self.setup()
            
        self.is_running = True
        
        if not self.headless:
            print("Game Loop Started.")
            while self.is_running:
                if max_ticks and self.metrics["ticks"] >= max_ticks:
                    self.is_running = False
                    break
                    
                current_time = time.time()
                frame_time = current_time - self.last_time
                self.last_time = current_time
                
                self.handle_input()
                self.update(frame_time)
                self.render()
                
                if self.renderer:
                    self.renderer.tick(self.config.FPS)
        else:
            # Headless mode: run as fast as possible
            while self.is_running:
                if max_ticks and self.metrics["ticks"] >= max_ticks:
                    self.is_running = False
                    break
                
                self._fixed_update()
                self.metrics["ticks"] += 1
                
                # Check for win condition
                alive_agents = [a for a in self.agents if a.health > 0]
                if len(alive_agents) <= 1:
                    if alive_agents:
                        self.metrics["winner"] = alive_agents[0].id
                    self.is_running = False
                    break

        if not self.headless:
            print("Game Loop Ended.")
        
        return self.metrics
