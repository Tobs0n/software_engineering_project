from __future__ import annotations
import random
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..abstract.game import Game


class PlaylistMode(Enum):
    SEQUENTIAL        = "SEQUENTIAL"         # play in order, wrapping
    RANDOM            = "RANDOM"             # pure random each round
    RANDOM_NO_REPEAT  = "RANDOM_NO_REPEAT"   # random but never two in a row


class GamePlaylist:
    """
    Manages which Game class comes next.
    Stores *classes* (not instances) — call next() to get a fresh instance.
    """

    def __init__(
        self,
        games:      list,                          # list[type[Game]]
        mode:       PlaylistMode = PlaylistMode.RANDOM_NO_REPEAT,
        max_rounds: int = 5,
    ):
        if not games:
            raise ValueError("GamePlaylist requires at least one game class.")
        self.games:         list            = games
        self.mode:          PlaylistMode    = mode
        self.max_rounds:    int             = max_rounds
        self.rounds_played: int             = 0
        self._index:        int             = 0
        self._last_cls                      = None

    # ── Iteration ─────────────────────────────────────────────────────────────

    def has_next(self) -> bool:
        return self.rounds_played < self.max_rounds

    def next(self) -> Game:
        """Return a new instance of the next game in the playlist."""
        cls = self._pick()
        self._last_cls   = cls
        self.rounds_played += 1
        return cls()

    def reset(self) -> None:
        self.rounds_played = 0
        self._index        = 0
        self._last_cls     = None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _pick(self):
        if self.mode == PlaylistMode.SEQUENTIAL:
            cls = self.games[self._index % len(self.games)]
            self._index += 1
            return cls

        if self.mode == PlaylistMode.RANDOM:
            return random.choice(self.games)

        # RANDOM_NO_REPEAT
        pool = [g for g in self.games if g is not self._last_cls]
        if not pool:          # only one game registered
            pool = self.games
        return random.choice(pool)
