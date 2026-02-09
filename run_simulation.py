import csv
import time
import cProfile
import pstats
import logging
from game.core.engine import Game
from game.agents.minimax import Minimax

# Disable FSM logging for simulation speed
logging.getLogger("FSM").setLevel(logging.WARNING)

def run_matches(num_matches=100, export_path="simulation_results.csv"):
    results = []
    start_time = time.time()
    
    print(f"Starting {num_matches} automated matches...")
    
    for i in range(num_matches):
        # Unique seed for each match
        seed = 1000 + i
        game = Game(headless=True, seed=seed)
        game.setup()
        
        # Pluggable AI Configuration
        # Match 1-50: Balanced vs Balanced
        # Match 51-75: Aggressive vs Defensive
        # Match 76-100: Deep Search vs Shallow Search
        
        a1 = game.get_agent(1)
        a2 = game.get_agent(2)
        
        a1_config = {"aggression": 0.5, "depth": 1}
        a2_config = {"aggression": 0.5, "depth": 1}
        
        if 50 <= i < 75:
            a1_config["aggression"] = 0.9 # Aggressive
            a2_config["aggression"] = 0.2 # Defensive
        elif i >= 75:
            a1_config["depth"] = 2 # Deeper search
            a2_config["depth"] = 1 # Shallow search

        # Apply configurations
        if a1:
            a1.minimax = Minimax(aggression=a1_config["aggression"])
            a1.fsm.states["FIGHT"].minimax = a1.minimax
            a1.fsm.states["FIGHT"].depth = a1_config["depth"] # Need to add depth support to FightState
        if a2:
            a2.minimax = Minimax(aggression=a2_config["aggression"])
            a2.fsm.states["FIGHT"].minimax = a2.minimax
            a2.fsm.states["FIGHT"].depth = a2_config["depth"]

        metrics = game.run_simulation(max_ticks=2000)
        
        # Process metrics
        match_data = {
            "match_id": i + 1,
            "seed": seed,
            "winner": metrics["winner"],
            "ticks": metrics["ticks"],
            "a1_aggression": a1_config["aggression"],
            "a1_depth": a1_config["depth"],
            "a2_aggression": a2_config["aggression"],
            "a2_depth": a2_config["depth"],
        }
        
        # Flatten state frequencies for CSV
        for agent_id, states in metrics["agent_states"].items():
            for state_name, count in states.items():
                match_data[f"agent{agent_id}_{state_name}_freq"] = round(count / metrics["ticks"], 3)
        
        results.append(match_data)
        
        if (i + 1) % 10 == 0:
            print(f"Completed {i + 1}/{num_matches} matches...")

    end_time = time.time()
    print(f"Finished simulation in {end_time - start_time:.2f} seconds.")

    # Export to CSV
    if results:
        keys = results[0].keys()
        with open(export_path, 'w', newline='') as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(results)
        print(f"Results exported to {export_path}")

    # Summary Stats
    winners = [r["winner"] for r in results]
    win_rate_1 = winners.count(1) / num_matches
    win_rate_2 = winners.count(2) / num_matches
    avg_ticks = sum(r["ticks"] for r in results) / num_matches
    
    print("\n--- Summary ---")
    print(f"Agent 1 Win Rate: {win_rate_1:.2%}")
    print(f"Agent 2 Win Rate: {win_rate_2:.2%}")
    print(f"Draws/Timeout: {(num_matches - winners.count(1) - winners.count(2)) / num_matches:.2%}")
    print(f"Average Match Length: {avg_ticks:.1f} ticks")

if __name__ == "__main__":
    # Run with profiling
    profiler = cProfile.Profile()
    profiler.enable()
    
    run_matches(100) # Full run
    
    profiler.disable()
    stats = pstats.Stats(profiler).sort_stats('cumtime')
    stats.print_stats(20) # Show top 20 functions
