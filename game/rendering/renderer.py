import pygame
import traceback
import sys
from game.core.config import GameConfig

class GameRenderer:
    """
    Handles all rendering using Pygame.
    Decoupled from core logic - receives state to draw.
    """
    def __init__(self):
        self.config = GameConfig()
        pygame.init()
        self.screen = pygame.display.set_mode((self.config.SCREEN_WIDTH, self.config.SCREEN_HEIGHT))
        pygame.display.set_caption(self.config.TITLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 18)
        self.small_font = pygame.font.SysFont("Arial", 12)

    def get_events(self):
        """
        Polls pygame events and converts them to a generic format if needed.
        For now, returns raw pygame events (or wrappers).
        """
        events = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # We return a simple object or struct that Core understands, 
                # or just the pygame event if we accept loose coupling here.
                # To be strictly clean, we should map to internal events.
                # For Phase 1, we'll just return an object with a 'type' attribute.
                class QuitEvent:
                    type = "QUIT"
                events.append(QuitEvent())
            # Add other input mappings here
        return events

    def render(self, game_state, local_agent_id=1):
        """
        Main render call.
        :param game_state: The current game state object.
        :param local_agent_id: The ID of the agent whose perspective we are viewing.
        """
        try:
            self.screen.fill(self.config.BLACK)

            # Check for world existence before rendering world related layers
            has_world = getattr(game_state, "world", None) is not None and game_state.world.grid
            has_agents = getattr(game_state, "agents", None) is not None

            if has_world:
                self._render_world(game_state)
                self._render_resources(game_state)
                
            # Draw Fog of War (Confidence Visualization) - depends on both world and agents
            if has_world and has_agents:
                self._render_fog_of_war(game_state, local_agent_id)

            if has_agents:
                self._render_agents(game_state)

            self._render_ui(game_state, local_agent_id)

            pygame.display.flip()
        except Exception as e:
            print(f"Renderer Error: {e}")
            import traceback
            traceback.print_exc()

    def _render_ui(self, game_state, local_agent_id):
        # UI Overlay
        fps_text = f"FPS: {int(self.clock.get_fps())}"
        surface = self.font.render(fps_text, True, self.config.WHITE)
        self.screen.blit(surface, (10, 10))

        # Safely check for agents
        agents = getattr(game_state, "agents", [])
        
        # Find local agent
        local_agent = None
        for agent in agents:
            if agent.id == local_agent_id:
                local_agent = agent
                break
        
        if local_agent:
            # Draw health and inventory
            ui_y = self.config.SCREEN_HEIGHT - 40
            health_text = f"HP: {int(local_agent.health)}"
            # Use getattr because ProxyAgent might not have inventory
            inv = getattr(local_agent, 'inventory', {})
            scrap = inv.get("scrap", 0)
            food = inv.get("food", 0)
            ammo = getattr(local_agent, 'ammo', 0)
            
            ui_text = f"ID: {local_agent_id} | {health_text} | Scrap: {scrap} | Food: {food} | Ammo: {ammo}"
            surface = self.font.render(ui_text, True, self.config.WHITE)
            self.screen.blit(surface, (10, ui_y))

    def _render_resources(self, game_state) -> None:
        tile_size = self.config.TILE_SIZE
        world = game_state.world
        
        for res in world.resources:
            color = (255, 255, 0) # Default Yellow
            if res.type == "food":
                color = (255, 100, 100) # Pinkish Red
            elif res.type == "ammo":
                color = (100, 255, 255) # Cyan
            elif res.type == "scrap":
                color = (200, 200, 200) # Silver
                
            center_x = res.x * tile_size + tile_size // 2
            center_y = res.y * tile_size + tile_size // 2
            
            # Draw small diamond/cross for resource
            pygame.draw.rect(self.screen, color, (center_x - 2, center_y - 2, 4, 4))
            pygame.draw.rect(self.screen, (255, 255, 255), (center_x - 2, center_y - 2, 4, 4), 1)

    def _render_fog_of_war(self, game_state, local_agent_id) -> None:
        """Visualizes agent visibility/confidence."""
        # Find the local agent
        hero = next((a for a in game_state.agents if a.id == local_agent_id), None)
        if not hero:
            return

        tile_size = self.config.TILE_SIZE
        width = game_state.world.width
        height = game_state.world.height

        # Create a transparent fog surface
        fog_surf = pygame.Surface((self.config.SCREEN_WIDTH, self.config.SCREEN_HEIGHT), pygame.SRCALPHA)
        fog_surf.fill((0, 0, 0, 150)) # Default semi-transparent black

        # Draw "light" around the hero
        hero_x = hero.x * tile_size + tile_size // 2
        hero_y = hero.y * tile_size + tile_size // 2
        
        # Max visibility range from VisibilitySystem (15 tiles)
        view_radius = 12 * tile_size 
        
        # Simple radial gradient for light
        for r in range(view_radius, 0, -tile_size):
            alpha = int(150 * (r / view_radius))
            pygame.draw.circle(fog_surf, (0, 0, 0, alpha), (hero_x, hero_y), r)

        self.screen.blit(fog_surf, (0, 0))

    def _render_world(self, game_state) -> None:
        tile_size = self.config.TILE_SIZE
        world = game_state.world

        # Terrain colors (more natural gradients)
        TERRAIN_COLORS = {
            "floor": (50, 50, 55),      # Dark Gray
            "water": (30, 60, 100),     # Deep Blue
            "wall": (20, 20, 25),       # Near Black
            "mud": (80, 60, 40),        # Brown
            "grass": (40, 90, 40),      # Forest Green
            "rock": (100, 100, 110),    # Slate Gray
        }

        for y, row in enumerate(world.grid):
            for x, tile in enumerate(row):
                color = TERRAIN_COLORS.get(tile.terrain.value, (255, 0, 255))
                
                rect = pygame.Rect(x * tile_size, y * tile_size, tile_size, tile_size)
                pygame.draw.rect(self.screen, color, rect)
                
                # Add a subtle grid/border in debug mode if needed
                # pygame.draw.rect(self.screen, (30, 30, 30), rect, 1)

    def _render_agents(self, game_state) -> None:
        tile_size = self.config.TILE_SIZE
        
        for agent in game_state.agents:
            if agent.health <= 0: continue

            # Draw Agent Body (Diamond/Circle for more personality)
            center_x = agent.x * tile_size + tile_size // 2
            center_y = agent.y * tile_size + tile_size // 2
            
            # Draw shadow
            pygame.draw.circle(self.screen, (20, 20, 20), (center_x + 2, center_y + 2), tile_size // 3)
            
            # Agent color based on ID
            color = (50, 200, 50) if agent.id == 1 else (200, 50, 50)
            pygame.draw.circle(self.screen, color, (center_x, center_y), tile_size // 3)
            pygame.draw.circle(self.screen, (255, 255, 255), (center_x, center_y), tile_size // 3, 2)
            
            # Draw Health Bar (Cleaner)
            max_hp = getattr(agent, 'max_health', 100.0)
            health_pct = max(0.0, min(1.0, agent.health / max_hp))
            bar_w = tile_size - 8
            bar_h = 3
            bar_x = agent.x * tile_size + 4
            bar_y = agent.y * tile_size - 4
            
            pygame.draw.rect(self.screen, (40, 0, 0), (bar_x, bar_y, bar_w, bar_h))
            pygame.draw.rect(self.screen, (0, 255, 0), (bar_x, bar_y, int(bar_w * health_pct), bar_h))
            
            # Draw Debug Info (State)
            if hasattr(agent, 'fsm') and agent.fsm.current_state:
                state_text = agent.fsm.current_state.name
                text_surf = self.small_font.render(state_text, True, (220, 220, 220))
                text_rect = text_surf.get_rect(center=(center_x, agent.y * tile_size + tile_size + 8))
                self.screen.blit(text_surf, text_rect)

    def tick(self, fps: int):
        """Wait to maintain FPS."""
        self.clock.tick(fps)

    def quit(self):
        pygame.quit()
