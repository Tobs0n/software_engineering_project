from __future__ import annotations
import time
from ...abstract.player_game_extension import PlayerGameExtension
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...abstract.player import Player

class SnakeExtension(PlayerGameExtension):
    def __init__(self, player: Player):
        super().__init__(player)
        self.body: list[list[int]] = [] # Lijst van [x, y] coördinaten
        self.direction = [20, 0]
        self.is_alive = True
        self.ghost_timer = 0.0
        self.speed_timer = 0.0

    def reset(self):
        self.body = []
        self.is_alive = True
        self.ghost_timer = 0.0
        self.speed_timer = 0.0
        self.direction = [20, 0]

    def to_dict(self) -> dict:
        return {
            "body": self.body,
            "is_alive": self.is_alive,
            "ghost": self.ghost_timer > 0,
            "speed": self.speed_timer > 0,
            "dir": self.direction
        }

    def from_dict(self, data: dict):
        self.body = data.get("body", self.body)
        self.is_alive = data.get("is_alive", self.is_alive)
        self.direction = data.get("dir", self.direction)
        # Timers worden door de host beheerd, we syncen alleen de status voor de kleur
        self._is_ghost_active = data.get("ghost", False)
        self._is_speed_active = data.get("speed", False)