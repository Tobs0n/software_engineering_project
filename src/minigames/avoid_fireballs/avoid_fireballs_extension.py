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

    MAX_LIVES = 3
    SCORE_PER_SECOND = 10

    def __init__(self, player: Player):
        super().__init__(player)
        self.lives: int = self.MAX_LIVES
        self.score: int = 0
        self.has_bomb: bool = False  # compatibility with existing BombGame code paths

    # ── Game mechanics ────────────────────────────────────────────────────────

    @property
    def is_alive(self) -> bool:
        """Returns True while the player has at least one life."""
        return self.lives > 0

    def lose_life(self) -> None:
        """Called when player is hit by a fireball."""
        self.lives = max(0, self.lives - 1)

    def add_score(self, points: int) -> None:
        """Called periodically to track survival time or achievement."""
        if points > 0:
            self.score += points

    def award_survival_tick(self, seconds: float = 1.0) -> None:
        """Award score for surviving time in the minigame."""
        if self.is_alive:
            self.score += int(round(seconds * self.SCORE_PER_SECOND))

    # ── PlayerGameExtension ───────────────────────────────────────────────────

    def reset(self) -> None:
        """Restore to initial state."""
        self.lives = self.MAX_LIVES
        self.score = 0

    def to_dict(self) -> dict:
        """Serialize for network sync."""
        return {"lives": self.lives, "score": self.score}

    def from_dict(self, data: dict) -> None:
        """Deserialize from network."""
        self.lives = data.get("lives", self.lives)
        self.score = data.get("score", self.score)
