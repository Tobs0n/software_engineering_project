from __future__ import annotations
from typing import TYPE_CHECKING

from .lobby_state import LobbyState
from .playlist import GamePlaylist

if TYPE_CHECKING:
    from ..abstract.player import Player
    from ..engine.game_engine import GameEngine


class Lobby:
    """
    A game session.  One player creates it (host), others join by code.
    Owns the GameEngine and GamePlaylist for its lifetime.
    """

    def __init__(self, code: str):
        self.code:     str               = code
        self.players:  list[Player]      = []
        self.engine:   GameEngine | None = None   # set by main_client after creation
        self.playlist: GamePlaylist | None = None
        self.state:    LobbyState        = LobbyState.WAITING

    # ── Player management ─────────────────────────────────────────────────────

    def add_player(self, player: Player) -> None:
        self.players.append(player)

    def remove_player(self, player: Player) -> None:
        if player in self.players:
            self.players.remove(player)

    def get_host(self) -> Player | None:
        for p in self.players:
            if p.is_host:
                return p
        return self.players[0] if self.players else None

    # ── Round management ──────────────────────────────────────────────────────

    def award_stars(self, results: dict[str, int]) -> None:
        """Add per-round points to each player's running star total."""
        for player in self.players:
            player.stars += results.get(player.player_id, 0)

    # ── Serialisation (for network broadcast) ────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "code":    self.code,
            "state":   self.state.value,
            "players": [p.to_dict() for p in self.players],
        }

    def __repr__(self) -> str:
        return f"Lobby({self.code!r}, players={len(self.players)}, state={self.state.name})"
