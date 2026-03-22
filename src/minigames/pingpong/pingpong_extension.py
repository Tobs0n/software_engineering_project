from __future__ import annotations
from ...abstract.player_game_extension import PlayerGameExtension
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...abstract.player import Player


class PingPongExtension(PlayerGameExtension):
    """
    Tracks paddle state for one player.

    [LOCAL]     paddle_y, paddle_dir  — each client moves its own paddle
    [SHARED]    paddle_x, paddle_height, start_dir  — set once by game setup
    """

    def __init__(self, player: Player):
        super().__init__(player)

        # Set by PingPongGame.setup() based on player index and player_count
        self.paddle_x:      float = 0.0
        self.paddle_height: int   = 0
        self.start_dir:     int   = 1    # -1 up, 1 down

        # [LOCAL] movement state
        self.paddle_y:   float = 0.0
        self.paddle_dir: int   = 1

    # ── Paddle logic ──────────────────────────────────────────────────────────

    def reset_position(self, field_top: int, field_height: int) -> None:
        self.paddle_y   = field_top + field_height // 2 - self.paddle_height // 2
        self.paddle_dir = self.start_dir

    def on_keydown(self, field_top: int, field_bottom: int) -> None:
        at_top    = self.paddle_y <= field_top
        at_bottom = self.paddle_y + self.paddle_height >= field_bottom

        if at_top:
            self.paddle_dir = 1
        elif at_bottom:
            self.paddle_dir = -1
        elif self.paddle_dir == 0:
            self.paddle_dir = -1
        elif self.paddle_dir == -1:
            self.paddle_dir = 1
        else:
            self.paddle_dir = -1

    def update(self, speed: int, field_top: int, field_bottom: int) -> None:
        self.paddle_y += self.paddle_dir * speed
        if self.paddle_y <= field_top:
            self.paddle_y   = field_top
            self.paddle_dir = 0
        if self.paddle_y + self.paddle_height >= field_bottom:
            self.paddle_y   = field_bottom - self.paddle_height
            self.paddle_dir = 0

    # ── PlayerGameExtension ───────────────────────────────────────────────────

    def reset(self) -> None:
        self.paddle_dir = self.start_dir

    def to_dict(self) -> dict:
        return {
            "paddle_y":   self.paddle_y,
            "paddle_dir": self.paddle_dir,
        }

    def from_dict(self, data: dict) -> None:
        self.paddle_y   = data.get("paddle_y",   self.paddle_y)
        self.paddle_dir = data.get("paddle_dir",  self.paddle_dir)
