from __future__ import annotations
from ...abstract.player_game_extension import PlayerGameExtension
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...abstract.player import Player


class DKCountingExtension(PlayerGameExtension):
    """Per-player state for the Donkey Kong counting minigame."""

    def __init__(self, player: Player):
        super().__init__(player)
        self.pressed: bool = False        # [LOCAL] has this client pressed their button
        self.diff: float = 0.0            # [AUTHORITY] timing error (seconds)

    def reset(self) -> None:
        self.pressed = False
        self.diff = 0.0

    def to_dict(self) -> dict:
        return {
            "pressed": self.pressed,
            "diff": self.diff,
        }

    def from_dict(self, data: dict) -> None:
        self.pressed = data.get("pressed", self.pressed)
        self.diff = data.get("diff", self.diff)
