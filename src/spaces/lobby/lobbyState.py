import enum

class LobbyState(enum.Enum):
    WAITING_FOR_PLAYERS = 1
    READY_TO_START = 2
    IN_GAME = 3
    GAME_ENDED = 4