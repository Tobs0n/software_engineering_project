import socket
import threading
import queue

from .messages import MsgType, pack, unpack


class Client:
    """
    Connects to the Server over TCP.
    Network recv runs on a background daemon thread and pushes messages
    into `self.inbox` (a thread-safe Queue).
    The pygame main loop calls `client.poll()` each frame to drain that queue.
    """

    def __init__(self):
        self._sock: socket.socket | None = None
        self._running = False
        self.inbox: queue.Queue[tuple[MsgType, dict]] = queue.Queue()

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self, host: str, port: int):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((host, port))
        self._running = True
        t = threading.Thread(target=self._recv_loop, daemon=True)
        t.start()
        print(f"[Client] Connected to {host}:{port}")

    def disconnect(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    # ── Send helpers ──────────────────────────────────────────────────────────

    def send(self, msg_type: MsgType, payload: dict = None):
        if not self._sock:
            return
        try:
            self._sock.sendall(pack(msg_type, payload or {}))
        except Exception as e:
            print(f"[Client] Send error: {e}")

    def create_lobby(self, name: str, color: tuple):
        self.send(MsgType.CREATE_LOBBY, {"name": name, "color": list(color)})

    def join_lobby(self, code: str, name: str, color: tuple):
        self.send(MsgType.JOIN_LOBBY, {"code": code.upper(), "name": name, "color": list(color)})

    def start_game(self):
        self.send(MsgType.START_GAME, {})

    def send_input(self, input_data: dict):
        self.send(MsgType.INPUT, input_data)

    # ── Polling (called from main thread) ────────────────────────────────────

    def poll(self) -> list[tuple[MsgType, dict]]:
        """Drain the inbox and return all pending (MsgType, payload) pairs."""
        messages = []
        while not self.inbox.empty():
            try:
                messages.append(self.inbox.get_nowait())
            except queue.Empty:
                break
        return messages

    # ── Background recv loop ──────────────────────────────────────────────────

    def _recv_loop(self):
        buf = ""
        try:
            while self._running:
                data = self._sock.recv(4096).decode("utf-8")
                if not data:
                    break
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            msg_type, payload = unpack(line)
                            self.inbox.put((msg_type, payload))
                        except Exception as e:
                            print(f"[Client] Parse error: {e}")
        except Exception as e:
            if self._running:
                print(f"[Client] Recv error: {e}")
        finally:
            print("[Client] Disconnected from server.")
