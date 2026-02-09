import pygame
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

    def render(self, game_state):
        """
        Render the current game state.
        :param game_state: The Game object or specific state data.
        """
        self.screen.fill(self.config.BLACK)

        if getattr(game_state, "world", None) is not None and game_state.world.grid:
            self._render_world(game_state)
            
        if getattr(game_state, "agents", None):
            self._render_agents(game_state)

        # UI Overlay
        fps_text = f"FPS: {int(self.clock.get_fps())}"
        surface = self.font.render(fps_text, True, self.config.WHITE)
        self.screen.blit(surface, (10, 10))

        pygame.display.flip()

    def _render_world(self, game_state) -> None:
        tile_size = self.config.TILE_SIZE
        world = game_state.world

        for y, row in enumerate(world.grid):
            for x, tile in enumerate(row):
                if tile.terrain.value == "floor":
                    color = (40, 40, 40)
                elif tile.terrain.value == "water":
                    color = (0, 0, 120)
                else:
                    color = (90, 90, 90)

                rect = pygame.Rect(x * tile_size, y * tile_size, tile_size, tile_size)
                pygame.draw.rect(self.screen, color, rect)

    def _render_agents(self, game_state) -> None:
        tile_size = self.config.TILE_SIZE
        
        for agent in game_state.agents:
            # Draw Agent Body
            rect = pygame.Rect(agent.x * tile_size + 4, agent.y * tile_size + 4, tile_size - 8, tile_size - 8)
            pygame.draw.rect(self.screen, self.config.GREEN, rect)
            
            # Draw Health Bar
            health_pct = max(0.0, agent.health / 100.0)
            bar_w = tile_size - 4
            bar_h = 4
            pygame.draw.rect(self.screen, self.config.RED, (agent.x * tile_size + 2, agent.y * tile_size - 6, bar_w, bar_h))
            pygame.draw.rect(self.screen, self.config.GREEN, (agent.x * tile_size + 2, agent.y * tile_size - 6, bar_w * health_pct, bar_h))
            
            # Draw Debug Info (State)
            if hasattr(agent, 'fsm') and agent.fsm.current_state:
                state_text = agent.fsm.current_state.name
                text_surf = self.small_font.render(state_text, True, self.config.WHITE)
                self.screen.blit(text_surf, (agent.x * tile_size, agent.y * tile_size + tile_size))

    def tick(self, fps: int):
        """Wait to maintain FPS."""
        self.clock.tick(fps)

    def quit(self):
        pygame.quit()
