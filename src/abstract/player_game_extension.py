from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..engine.physics_body import PhysicsBody
    from .player import Player


class PlayerGameExtension(ABC):
    """
    Per-game data attached to a Player for the duration of one minigame.
    Holds the player's PhysicsBody so the World can simulate it.
    Each Game subclass creates its own Extension subclass via create_extension().
    """

    def __init__(self, player: Player):
        self.player: Player            = player
        self.body:   PhysicsBody | None = None   # assigned by Game.setup()

    @abstractmethod
    def reset(self) -> None:
        """Restore all game-specific state to initial values."""

    @abstractmethod
    def to_dict(self) -> dict:
        """Serialise game-specific state (for network sync)."""

    @abstractmethod
    def from_dict(self, data: dict) -> None:
        """Update state from a deserialised dict."""
