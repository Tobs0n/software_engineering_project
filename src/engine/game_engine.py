from __future__ import annotations
import pygame
from typing import Callable

from .world import World
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..abstract.game import Game
    from ..abstract.player import Player


class GameEngine:
    """
    Drives the per-frame game loop.

    dt comes FROM the App's clock — the engine never calls clock.tick() itself.

    sync_callback is wired by the App:
      - For the authority (host):  calls client.send(GAME_STATE, state)
      - For a peer:                calls client.send_input(data)
    The Game base class routes _broadcast_state() and _send_input() through
    this single callback; the App decides what to do with each.
    """

    def __init__(self, screen: pygame.Surface):
        self.screen:        pygame.Surface                     = screen
        self.world:         World | None                       = None
        self.game:          Game | None                        = None
        self.is_running:    bool                               = False
        self.last_dt:       float                              = 0.0
        self._sync_cb:      Callable[[dict], None] | None      = None

    # ── Wiring ────────────────────────────────────────────────────────────────

    def set_sync_callback(self, cb: Callable[[dict], None]) -> None:
        """
        App calls this once after creating the engine.
        cb receives whatever the Game passes to _broadcast_state / _send_input.
        """
        self._sync_cb = cb

    # ── Game loading / swapping ───────────────────────────────────────────────

    def load_game(self, game: Game, players: list[Player],
                  is_authority: bool = False) -> None:
        if self.game is not None:
            self._teardown()

        self.game              = game
        self.game.engine       = self
        self.game.players      = players
        self.game.is_authority = is_authority
        self.game._sync_callback = self._sync_cb

        config     = self.game.get_world_config()
        self.world = World(config)
        self.world.add_collision_callback(self.game.on_collision)

        for player in players:
            ext = self.game.create_extension(player)
            player.set_extension(ext)

        self.game.setup()
        self.is_running = True

    def swap_game(self, game: Game, players: list[Player],
                  is_authority: bool = False) -> None:
        self.load_game(game, players, is_authority)

    # ── Per-frame tick ────────────────────────────────────────────────────────

    def tick(self, events: list[pygame.event.Event], dt: float) -> bool:
        if not self.is_running:
            return False

        self.last_dt = min(dt, 0.1)

        self.game.update(events, self.last_dt)

        if self.world:
            self.world.step(self.last_dt)

        self.game.render(self.screen)

        if self.game.is_over:
            self.is_running = False
            return False

        return True

    def stop(self) -> None:
        self.is_running = False

    # ── Network state passthrough ─────────────────────────────────────────────

    def apply_network_state(self, state: dict) -> None:
        """Called by App when a GAME_STATE message arrives from the authority."""
        if self.game and not self.game.is_authority:
            self.game.apply_sync_state(state)

    def apply_network_input(self, player_id: str, input_data: dict) -> None:
        """Called by App when an INPUT message arrives (authority only)."""
        if self.game and self.game.is_authority:
            self.game.on_input_received(player_id, input_data)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _teardown(self) -> None:
        if self.game:
            self.game.teardown()
        if self.world:
            self.world.clear()
        self.game  = None
        self.world = None
