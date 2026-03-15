import random
from typing import List, Set, Optional
from src.spaces.lobby.playlistMode import PlaylistMode
from src.spaces.game.game import Game

class GamePlaylist:
    def __init__(self, mode: PlaylistMode = PlaylistMode.SEQUENTIAL):
        self.games: List[Game] = []
        self.games_played: Set[Game] = set()
        self.mode = mode
        self.current_index = 0

    def has_next(self) -> bool:
        return len(self.games_played) < len(self.games)

    def next_game(self) -> Optional[Game]:
        if not self.has_next():
            return None

        selected_game = None

        if self.mode == PlaylistMode.SEQUENTIAL:
            selected_game = self.games[self.current_index]
            self.current_index += 1
        
        elif self.mode == PlaylistMode.RANDOM:
            remaining = list(set(self.games) - self.games_played)
            selected_game = random.choice(remaining)
        
        if selected_game:
            self.games_played.add(selected_game)
        
        return selected_game

    def reset(self) -> None:
        self.games_played.clear()
        self.current_index = 0