from __future__ import annotations

from ...abstract.player_game_extension import PlayerGameExtension
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...abstract.player import Player


class GoombaExtension(PlayerGameExtension):
    """
    Tracks goomba counter.
    """

    def __init__(self, player: Player):
        super().__init__(player)
        self.goombacounter:  int   = 0

    # ── Game mechanics ────────────────────────────────────────────────────────

    def increment(self):
        """
        Used when a player 'counts' an entity
        """
        self.goombacounter += 1   

    # ── PlayerGameExtension ───────────────────────────────────────────────────

    def reset(self) -> None:
        self.goombacounter = 0
    
    def to_dict(self) -> dict:
        return {"counter": self.goombacounter}

    def from_dict(self, data: dict) -> None:
        self.goombacounter = data.get("counter", self.goombacounter)