import sys
from game.core.engine import Game
from game.rendering.renderer import GameRenderer

def main():
    """
    Entry point for the GOLAGULI AI Simulation.
    """
    try:
        renderer = GameRenderer()
        game_engine = Game(renderer=renderer)
        game_engine.run_simulation(max_ticks=None)
    except Exception as e:
        print(f"Critical Error: {e}")
        sys.exit(1)
    finally:
        if 'renderer' in locals():
            renderer.quit()
        sys.exit(0)

if __name__ == "__main__":
    main()
