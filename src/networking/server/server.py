import socket
import select
import json
import threading
import random
import string
from src.spaces.lobby.lobby import Lobby
from src.networking.networkMessages import NetworkMessage

class Server:
    def __init__(self):
        self._lobbies = dict()  # {code: Lobby}
        self._clients = dict()  # {socket: lobby_code}
        self._running = False
        self.MAX_PLAYERS = 4

    def start(self, host, port):
        self.main_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.main_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.main_socket.bind((host, port))
        self.main_socket.listen(self.MAX_PLAYERS)
        self.main_socket.setblocking(False)
        self._running = True
        
        # Runs in background so the Host can still use their own Pygame window
        threading.Thread(target=self._server_loop, daemon=True).start()
        print(f"P2P Server started on {host}:{port}")

    def _server_loop(self):
        while self._running:
            inputs = [self.main_socket] + list(self._clients.keys())
            readable, _, _ = select.select(inputs, [], [], 0.1)
            
            for sock in readable:
                if sock is self.main_socket:
                    self.handle_connect(sock)
                else:
                    self._receive(sock)

    def _receive(self, sock):
        try:
            data = sock.recv(4096).decode('utf-8')
            if data:
                self.handle_message(sock, json.loads(data))
            else:
                self.handle_disconnect(sock)
        except:
            self.handle_disconnect(sock)

    def handle_connect(self, sock):
        if len(self._clients) >= self.MAX_PLAYERS:
            temp_sock, _ = sock.accept()
            temp_sock.close() # Reject if full
            return

        client_sock, addr = sock.accept()
        client_sock.setblocking(False)
        self._clients[client_sock] = None 

    def handle_disconnect(self, sock):
        code = self._clients.pop(sock, None)
        sock.close()

    def handle_message(self, sock, message):
        m_type = message.get("type")
        data = message.get("data", {})

        if m_type == NetworkMessage.CREATE_LOBBY.value:
            # 1. Create the lobby
            lobby = self._create_lobby(sock)
            # 2. Add the Host as the first player
            self._register_player(sock, lobby, data)
            # 3. Tell everyone (the host) the new state
            self.broadcast_state(lobby)
        
        elif m_type == NetworkMessage.JOIN_LOBBY.value:
            lobby = self._join_lobby(sock, data.get("code"))
            if lobby:
                self._register_player(sock, lobby, data)
                self.broadcast_state(lobby)

    def broadcast(self, lobby, message):
        payload = json.dumps(message).encode('utf-8')
        for sock, code in self._clients.items():
            if code == lobby._code:
                sock.sendall(payload)

    def broadcast_state(self, lobby):
        # Syncs the Lobby object data across all 4 connected peers
        state = {
            "type": NetworkMessage.LOBBY_STATE.value,
            "data": {
                "code": lobby._code,
                "player_count": len(self._clients),
                "state": lobby.state.value if lobby.state else None
            }
        }
        self.broadcast(lobby, state)

    def _create_lobby(self, sock) -> Lobby:
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
        lobby = Lobby(code)
        self._lobbies[code] = lobby
        self._clients[sock] = code
        return lobby

    def _join_lobby(self, sock, code: str) -> Lobby:
        if code in self._lobbies:
            self._clients[sock] = code
            return self._lobbies[code]

    def _register_player(self, sock, lobby, data):
        """Helper to turn raw network data into a player in the lobby object"""
        player_info = {
            "name": data.get("name", "Unknown"),
            "color": data.get("color", (255, 255, 255)),
            "id": id(sock) # Unique ID based on socket memory address
        }
        lobby.players.append(player_info)

    def broadcast_state(self, lobby):
        state = {
            "type": NetworkMessage.LOBBY_STATE.value,
            "data": {
                "code": lobby._code,
                "players": lobby.players, # List of dicts
                "state": lobby.state.value if lobby.state else 1
            }
        }
        self.broadcast(lobby, state)

        return None