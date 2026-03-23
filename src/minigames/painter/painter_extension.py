from __future__ import annotations

from ...abstract.player_game_extension import PlayerGameExtension
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...abstract.player import Player


class PainterExtension(PlayerGameExtension):
    """
    Tracks cell count and powerup state for the Painter game.

    Powerups (all [AUTHORITY]-managed):
      brush_timer   > 0  →  player paints a 3×3 area instead of 1 cell
      has_bomb      True →  player is holding a bomb; press SPACE to detonate
    """

    def __init__(self, player: Player):
        super().__init__(player)
        self.cell_count:  int   = 0     # [AUTHORITY]
        self.brush_timer: float = 0.0   # [AUTHORITY] seconds of 3×3 brush remaining
        self.has_bomb:    bool  = False  # [AUTHORITY] bomb ready to use

    # ── PlayerGameExtension ───────────────────────────────────────────────────

    def reset(self) -> None:
        self.cell_count  = 0
        self.brush_timer = 0.0
        self.has_bomb    = False

    def to_dict(self) -> dict:
        return {
            "cell_count":  self.cell_count,
            "brush_timer": self.brush_timer,
            "has_bomb":    self.has_bomb,
        }

    def from_dict(self, data: dict) -> None:
        self.cell_count  = data.get("cell_count",  self.cell_count)
        self.brush_timer = data.get("brush_timer", self.brush_timer)
        self.has_bomb    = data.get("has_bomb",    self.has_bomb)