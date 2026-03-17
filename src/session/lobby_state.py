from enum import Enum


class LobbyState(Enum):
    WAITING       = "WAITING"        # in menu, accepting joins
    GAME_RUNNING  = "GAME_RUNNING"   # minigame in progress
    BETWEEN_GAMES = "BETWEEN_GAMES"  # results screen, before next game
    FINISHED      = "FINISHED"       # all rounds played, final scoreboard
