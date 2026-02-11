from typing import List, Tuple, Dict, Any, Optional
from game.agents.base_agent import BaseAgent
from game.agents.astar import Coord

class NetworkedAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_action = None
        self.requested_move = None
        self._stuck_ticks = 0

    def update_from_server(self, server_data: Dict[str, Any]):
        """Update local state with authoritative data from server."""
        self_data = server_data["self"]
        old_pos = (self.x, self.y)
        old_inventory = self.inventory.copy() if self.inventory else {}
        
        self.x = self_data["x"]
        self.y = self_data["y"]
        self.health = self_data["health"]
        if "max_health" in self_data:
            self.max_health = self_data["max_health"]
        self.ammo = self_data["ammo"]
        self.inventory = self_data["inventory"]
        
        if (self.x, self.y) == old_pos:
            self._stuck_ticks += 1
        else:
            self._stuck_ticks = 0
        if self._stuck_ticks >= 3 and self.path:
            self.path = []
            self._path_index = 0
            self._stuck_ticks = 0

        # Log collection
        for res_type, amount in self.inventory.items():
            old_amount = old_inventory.get(res_type, 0)
            if amount > old_amount:
                print(f"[Agent {self.id}] Confirmed Collection: +{amount - old_amount} {res_type} (Total: {amount})")
        
        # If we were on a path and moved to the expected next spot, increment index
        if self.path and self._path_index < len(self.path):
            if (self.x, self.y) == self.path[self._path_index]:
                self._path_index += 1
                print(f"[Agent {self.id}] Moved to confirmed position ({self.x}, {self.y})")
            elif (self.x, self.y) != old_pos:
                # We moved but not to where we expected? Reset path.
                print(f"[Agent {self.id}] Position mismatch (Expected {self.path[self._path_index]}, Got {self.x}, {self.y}). Resetting path.")
                self.path = []
                self._path_index = 0

    def update(self, world_state) -> Optional[Dict[str, Any]]:
        """
        Run AI logic and return the requested action.
        """
        # Save state before FSM update
        old_ammo = self.ammo
        old_health = self.health
        old_pos = (self.x, self.y)
        
        # Run FSM
        self.fsm.update(world_state)
        
        # Determine requested action and movement
        action = None
        move_to = None
        target_id = None
        
        # 1. Detect if FSM/Minimax performed an ATTACK
        if self.ammo < old_ammo:
            action = "ATTACK"
            self.ammo = old_ammo
            
            others = world_state.agents if hasattr(world_state, 'agents') else []
            if others:
                others = [o for o in others if o.id != self.id]
                if others:
                    others.sort(key=lambda o: abs(o.x - self.x) + abs(o.y - self.y))
                    target_id = others[0].id
            print(f"[Agent {self.id}] AI requested ATTACK on {target_id}")

        # 2. Detect if FSM/Minimax performed a MOVE (direct modification)
        if (self.x, self.y) != old_pos:
            move_to = (self.x, self.y)
            self.x, self.y = old_pos
            print(f"[Agent {self.id}] AI requested direct MOVE to {move_to}")
            
        # 3. Check for other state-based actions
        current_state = self.fsm.current_state.name if self.fsm.current_state else "None"
        if not action and not move_to:
            if current_state == "FLEE":
                if not self.path or self._path_index >= len(self.path):
                    self.path = []
                    self._path_index = 0
                    print(f"[Agent {self.id}] FLEE state: path exhausted, will replan")
            elif current_state == "SCAVENGE":
                world = getattr(world_state, 'world', None)
                if world:
                    res = world.get_resource_at(self.x, self.y)
                    if res:
                        action = "SCAVENGE"
            elif current_state == "EAT":
                action = "EAT"
                print(f"[Agent {self.id}] AI requested EAT")
            elif current_state == "UPGRADE":
                action = "UPGRADE"
                self.pending_upgrade_type = getattr(self, "pending_upgrade_type", "MAX_HEALTH")
                print(f"[Agent {self.id}] AI requested UPGRADE: {self.pending_upgrade_type}")

        # 4. Handle movement from path if no other move was detected
        if not move_to and not action and self.path:
            if self._path_index < len(self.path):
                if (self.x, self.y) == self.path[self._path_index]:
                    self._path_index += 1
                
                if self._path_index < len(self.path):
                    move_to = self.path[self._path_index]
            
        # Build the action packet
        packet = {
            "type": "action",
            "agent_id": self.id,
            "action": action,
            "position": move_to,
        }
        
        if action == "ATTACK":
            packet["target_id"] = target_id
        elif action == "UPGRADE":
            packet["upgrade_type"] = getattr(self, "pending_upgrade_type", "MAX_HEALTH")
            
        return packet
