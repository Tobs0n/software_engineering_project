from __future__ import annotations
import time

from ...abstract.player_game_extension import PlayerGameExtension
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...abstract.player import Player


class BombExtension(PlayerGameExtension):
    """
    Tracks lives, bomb ownership, and throw cooldown for the Hot Potato game.
    """

    THROW_COOLDOWN = 1.0   # seconds before the holder can throw again

    def __init__(self, player: Player):
        super().__init__(player)
        self.lives:          int   = 3
        self.has_bomb:       bool  = False
        self._last_throw:    float = 0.0

    # ── Bomb mechanics ────────────────────────────────────────────────────────

    def can_throw(self) -> bool:
        return self.has_bomb and (time.time() - self._last_throw) >= self.THROW_COOLDOWN

    def throw_bomb(self) -> None:
        """Remove the bomb from this player; caller must give it to someone else."""
        self.has_bomb    = False
        self._last_throw = time.time()

    def receive_bomb(self) -> None:
        self.has_bomb = True

    def lose_life(self) -> None:
        self.lives = max(0, self.lives - 1)

    # ── PlayerGameExtension ───────────────────────────────────────────────────

    def reset(self) -> None:
        self.lives       = 3
        self.has_bomb    = False
        self._last_throw = 0.0

    def to_dict(self) -> dict:
        return {"lives": self.lives, "has_bomb": self.has_bomb}

    def from_dict(self, data: dict) -> None:
        self.lives    = data.get("lives",    self.lives)
        self.has_bomb = data.get("has_bomb", self.has_bomb)
