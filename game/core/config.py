from dataclasses import dataclass

@dataclass(frozen=True)
class GameConfig:
    """Global configuration constants for the game."""
    SCREEN_WIDTH: int = 800
    SCREEN_HEIGHT: int = 600
    FPS: int = 60
    TITLE: str = "GOLAGULI - AI Simulation"
    TILE_SIZE: int = 32
    
    # Colors
    BLACK: tuple = (0, 0, 0)
    WHITE: tuple = (255, 255, 255)
    RED: tuple = (255, 0, 0)
    GREEN: tuple = (0, 255, 0)
    BLUE: tuple = (0, 0, 255)
