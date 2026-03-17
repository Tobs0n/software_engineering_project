from enum import Enum
import json


class MsgType(str, Enum):
    # Client -> Server
    CREATE_LOBBY = "CREATE_LOBBY"
    JOIN_LOBBY   = "JOIN_LOBBY"
    START_GAME   = "START_GAME"
    INPUT        = "INPUT"

    # Server -> Client
    LOBBY_STATE  = "LOBBY_STATE"
    GAME_START   = "GAME_START"
    GAME_STATE   = "GAME_STATE"
    GAME_END     = "GAME_END"
    ERROR        = "ERROR"


def pack(msg_type: MsgType, payload: dict = None) -> bytes:
    """Serialise a message to a newline-terminated JSON bytes object."""
    data = {"type": msg_type.value, "payload": payload or {}}
    return (json.dumps(data) + "\n").encode("utf-8")


def unpack(raw: str) -> tuple[MsgType, dict]:
    """Deserialise a newline-stripped JSON string back to (MsgType, payload)."""
    data = json.loads(raw.strip())
    return MsgType(data["type"]), data.get("payload", {})
