from __future__ import annotations
import time

from ...abstract.player_game_extension import PlayerGameExtension
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...abstract.player import Player


class FireBallExtension(PlayerGameExtension):
    """
    Tracks lives and score for the Avoid Fireballs minigame.
    Players start with 3 lives and lose one each time hit by a fireball.
    """

    def __init__(self, player: Player):
        super().__init__(player)
        self.lives: int = 3
        self.score: int = 0

    # ── Game mechanics ────────────────────────────────────────────────────────

    def lose_life(self) -> None:
        """Called when player is hit by a fireball."""
        self.lives = max(0, self.lives - 1)

    def add_score(self, points: int) -> None:
        """Called periodically to track survival time or achievement."""
        self.score += points

    # ── PlayerGameExtension ───────────────────────────────────────────────────

    def reset(self) -> None:
        """Restore to initial state."""
        self.lives = 3
        self.score = 0

    def to_dict(self) -> dict:
        """Serialize for network sync."""
        return {"lives": self.lives, "score": self.score}

    def from_dict(self, data: dict) -> None:
        """Deserialize from network."""
        self.lives = data.get("lives", self.lives)
        self.score = data.get("score", self.score)