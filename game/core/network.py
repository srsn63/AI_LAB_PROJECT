import asyncio
import json
import websockets
import threading
import traceback
import sys
from typing import List, Callable

class NetworkClient:
    def __init__(self, host="127.0.0.1", port=8888):
        self.uri = f"ws://{host}:{port}"
        self.websocket = None
        self.agent_id = None
        self.is_connected = False
        self.on_message_callbacks = []
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        
    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        
    def start(self):
        self.thread.start()
        asyncio.run_coroutine_threadsafe(self.connect(), self.loop)
        
    async def connect(self):
        try:
            print(f"Attempting to connect to {self.uri}...")
            self.websocket = await websockets.connect(self.uri)
            self.is_connected = True
            print(f"Connected to server at {self.uri}")
            async for message in self.websocket:
                try:
                    # print(f"Received message: {message[:100]}...") # Debug log
                    data = json.loads(message)
                    for callback in self.on_message_callbacks:
                        callback(data)
                except Exception as e:
                    print(f"Error handling message: {e}")
                    import traceback
                    traceback.print_exc()
        except Exception as e:
            print(f"Connection error: {e}")
            import traceback
            traceback.print_exc()
            self.is_connected = False

    def send_action(self, action_data):
        if self.is_connected:
            asyncio.run_coroutine_threadsafe(
                self.websocket.send(json.dumps(action_data)), 
                self.loop
            )

    def add_callback(self, callback: Callable):
        self.on_message_callbacks.append(callback)
