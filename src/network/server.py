import socket
import threading
import uuid
import random
import string

from .messages import MsgType, pack, unpack
from ..session.lobby import Lobby
from ..abstract.player import Player


class Server:
    """
    Listens for TCP connections.  Each connected socket maps to one Player.
    All game coordination (lobby creation, join, start) runs here.
    Actual game simulation runs on each client independently — the server
    only synchronises lobby state and relays player inputs.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 5555):
        self.host = host
        self.port = port
        self._lobbies: dict[str, Lobby] = {}          # code  -> Lobby
        self._clients: dict[socket.socket, Player] = {} # sock -> Player
        self._sock: socket.socket | None = None
        self._running = False

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(32)
        self._running = True
        print(f"[Server] Listening on {self.host}:{self.port}")

        while self._running:
            try:
                conn, addr = self._sock.accept()
                print(f"[Server] New connection from {addr}")
                t = threading.Thread(
                    target=self._handle_client, args=(conn,), daemon=True
                )
                t.start()
            except OSError:
                break

    def stop(self):
        self._running = False
        if self._sock:
            self._sock.close()

    # ── Per-client receive loop ───────────────────────────────────────────────

    def _handle_client(self, conn: socket.socket):
        buf = ""
        try:
            while self._running:
                chunk = conn.recv(4096).decode("utf-8")
                if not chunk:
                    break
                buf += chunk
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            msg_type, payload = unpack(line)
                            self._dispatch(conn, msg_type, payload)
                        except Exception as e:
                            print(f"[Server] Parse error: {e} — raw: {line!r}")
        except Exception as e:
            print(f"[Server] Client error: {e}")
        finally:
            self._on_disconnect(conn)

    # ── Message dispatch ──────────────────────────────────────────────────────

    def _dispatch(self, conn: socket.socket, msg_type: MsgType, payload: dict):
        if   msg_type == MsgType.CREATE_LOBBY: self._on_create_lobby(conn, payload)
        elif msg_type == MsgType.JOIN_LOBBY:   self._on_join_lobby(conn, payload)
        elif msg_type == MsgType.START_GAME:   self._on_start_game(conn)
        elif msg_type == MsgType.INPUT:        self._on_input(conn, payload)
        elif msg_type == MsgType.GAME_STATE:   self._on_game_state(conn, payload)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_create_lobby(self, conn: socket.socket, payload: dict):
        player = self._make_player(payload, is_host=True)
        self._clients[conn] = player

        code  = self._gen_code()
        lobby = Lobby(code)
        lobby.add_player(player)
        self._lobbies[code] = lobby

        self._send(conn, MsgType.LOBBY_STATE, lobby.to_dict())
        print(f"[Server] Lobby {code} created by {player.name}")

    def _on_join_lobby(self, conn: socket.socket, payload: dict):
        code = payload.get("code", "").strip().upper()
        if code not in self._lobbies:
            self._send(conn, MsgType.ERROR, {"message": f"Lobby '{code}' not found."})
            return

        lobby  = self._lobbies[code]
        player = self._make_player(payload, is_host=False)
        self._clients[conn] = player
        lobby.add_player(player)

        # Notify everyone in the lobby of the updated player list
        self._broadcast(lobby, MsgType.LOBBY_STATE, lobby.to_dict())
        print(f"[Server] {player.name} joined lobby {code}")

    def _on_start_game(self, conn: socket.socket):
        lobby = self._lobby_of(conn)
        if lobby is None:
            return
        player = self._clients.get(conn)
        if not (player and player.is_host):
            self._send(conn, MsgType.ERROR, {"message": "Only the host can start."})
            return

        # Pick next game from lobby playlist (or default to bomb)
        game_key = "bomb"
        if lobby.playlist and lobby.playlist.has_next():
            game_obj = lobby.playlist.next()
            game_key = type(game_obj).__name__.lower().replace("game", "")

        self._broadcast(lobby, MsgType.GAME_START, {
            "game":    game_key,
            "players": [p.to_dict() for p in lobby.players],
        })
        print(f"[Server] Lobby {lobby.code} starting '{game_key}'")

    def _on_input(self, conn: socket.socket, payload: dict):
        """Relay input from one client to all others in the same lobby."""
        lobby  = self._lobby_of(conn)
        player = self._clients.get(conn)
        if lobby is None or player is None:
            return
        payload["player_id"] = player.player_id
        for c, p in list(self._clients.items()):
            if c != conn and p in lobby.players:
                self._send(c, MsgType.INPUT, payload)

    def _on_game_state(self, conn: socket.socket, payload: dict):
        """
        Relay authoritative game state from the host to all other clients.
        Only the host should ever send GAME_STATE — non-hosts send INPUT only.
        The server does not validate this; it trusts the sender is the host.
        """
        lobby = self._lobby_of(conn)
        if lobby is None:
            return
        for c, p in list(self._clients.items()):
            if c != conn and p in lobby.players:
                self._send(c, MsgType.GAME_STATE, payload)

    def _on_disconnect(self, conn: socket.socket):
        player = self._clients.pop(conn, None)
        if player:
            for lobby in list(self._lobbies.values()):
                if player in lobby.players:
                    lobby.remove_player(player)
                    if not lobby.players:
                        del self._lobbies[lobby.code]
                    else:
                        self._broadcast(lobby, MsgType.LOBBY_STATE, lobby.to_dict())
                    break
        try:
            conn.close()
        except Exception:
            pass
        print(f"[Server] Client disconnected: {player.name if player else 'unknown'}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _broadcast(self, lobby: Lobby, msg_type: MsgType, payload: dict):
        for conn, player in list(self._clients.items()):
            if player in lobby.players:
                self._send(conn, msg_type, payload)

    def _send(self, conn: socket.socket, msg_type: MsgType, payload: dict):
        try:
            conn.sendall(pack(msg_type, payload))
        except Exception as e:
            print(f"[Server] Send error: {e}")

    def _lobby_of(self, conn: socket.socket) -> Lobby | None:
        player = self._clients.get(conn)
        if not player:
            return None
        for lobby in self._lobbies.values():
            if player in lobby.players:
                return lobby
        return None

    @staticmethod
    def _make_player(payload: dict, is_host: bool) -> Player:
        name  = payload.get("name", "Player")[:16]
        color = tuple(payload.get("color", [200, 200, 200]))
        p = Player(name, color)
        p.player_id = str(uuid.uuid4())[:8]
        p.is_host   = is_host
        return p

    @staticmethod
    def _gen_code(length: int = 5) -> str:
        return "".join(random.choices(string.ascii_uppercase, k=length))
