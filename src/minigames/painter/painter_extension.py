from __future__ import annotations

from ...abstract.player_game_extension import PlayerGameExtension
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...abstract.player import Player


class PainterExtension(PlayerGameExtension):
    """
    Tracks how many grid cells this player currently owns.
    The grid itself is [AUTHORITY]-managed inside TerritoryGame.
    """

    def __init__(self, player: Player):
        super().__init__(player)
        self.cell_count: int = 0   # [AUTHORITY] updated by TerritoryGame._paint_cells

    # ── PlayerGameExtension ───────────────────────────────────────────────────

    def reset(self) -> None:
        self.cell_count = 0

    def to_dict(self) -> dict:
        return {"cell_count": self.cell_count}

    def from_dict(self, data: dict) -> None:
        self.cell_count = data.get("cell_count", self.cell_count)
