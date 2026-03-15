from enum import Enum

class NetworkMessage(Enum):
    CREATE_LOBBY = 1
    JOIN_LOBBY = 2
    PLAYER_UPDATE = 3
    GAME_START = 4
    GAME_STATE = 5
    GAME_END = 6
    INPUT = 7
    LOBBY_STATE = 8