import socket
import json
import threading
from src.networking.networkMessages import NetworkMessage

class Client:
    def __init__(self, socket_instance=None):
        self._socket = socket_instance
        self.player = None
        self.lobby = None
        self.screen = None 
        self._running = False

    def connect(self, host, port):
        if not self._socket:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._socket.connect((host, port))
            self._socket.setblocking(False)
            self._running = True
            threading.Thread(target=self.run, daemon=True).start()
            return True
        except:
            return False

    def send_message(self, m_type, data=None):
        if self._socket:
            msg = {"type": m_type.value, "data": data or {}}
            self._socket.sendall(json.dumps(msg).encode('utf-8'))

    def create_lobby(self):
        self.send_message(NetworkMessage.CREATE_LOBBY)

    def join_lobby(self, code: str):
        self.send_message(NetworkMessage.JOIN_LOBBY, {"code": code})

    def handle_message(self, message):
        """
        Processes incoming messages from the Server and updates the local 
        Client state (Lobby, Player, etc.) to keep things in sync.
        """
        msg_type_val = message.get("type")
        data = message.get("data", {})

        # Update Lobby State / Sync Data
        if msg_type_val == NetworkMessage.LOBBY_STATE.value:
            from src.spaces.lobby.lobby import Lobby
            
            if not self.lobby or self.lobby._code != data.get("code"):
                self.lobby = Lobby(data.get("code"))
            
            # This now receives the list of DICTS (name/color) from the server
            self.lobby.players = data.get("players", [])            
            print(f"[Client] Sync complete. Lobby {self.lobby._code} has {len(self.lobby.players)} players.")

        # Handle Game Start
        elif msg_type_val == NetworkMessage.GAME_START.value:
            if self.lobby:
                self.lobby.start_next_game()
                print("[Client] Game started by host.")

        # Handle specific Game State updates (Positions, scores, etc.)
        elif msg_type_val == NetworkMessage.GAME_STATE.value:
            if self.lobby and self.lobby.engine:
                # This is where you'd pass raw data into your game engine
                # e.g., self.lobby.engine.update_from_network(data)
                pass

        # 4. Handle Disconnects or Errors
        elif "error" in data:
            print(f"[Client Error] {data['error']}")

    def run(self):
        while self._running:
            try:
                data = self._socket.recv(4096).decode('utf-8')
                if data:
                    self.handle_message(json.loads(data))
            except (BlockingIOError, socket.error):
                continue