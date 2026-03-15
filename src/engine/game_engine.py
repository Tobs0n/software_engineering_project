from __future__ import annotations
import pygame

from .world import World
from .world_config import WorldConfig
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..abstract.game import Game
    from ..abstract.player import Player


class GameEngine:
    """
    Drives the per-frame game loop.

    dt comes FROM the App's clock — the engine never calls clock.tick() itself.
    This prevents the bug where an idle engine clock accumulates time while on
    the controls/lobby screen, then dumps a huge dt on the first game frame.

    Usage (from main_client.py):
        engine.load_game(game_instance, players)
        # each pygame frame:
        still_running = engine.tick(events, dt)   # dt from App.clock.tick()
    """

    def __init__(self, screen: pygame.Surface):
        self.screen:     pygame.Surface = screen
        self.world:      World | None   = None
        self.game:       Game | None    = None
        self.is_running: bool           = False
        self.last_dt:    float          = 0.0   # last frame dt, readable by games

    # ── Game loading / swapping ───────────────────────────────────────────────

    def load_game(self, game: Game, players: list[Player]) -> None:
        """Tear down any current game, wire up the new one, and call setup()."""
        if self.game is not None:
            self._teardown()

        self.game         = game
        self.game.engine  = self
        self.game.players = players

        config     = self.game.get_world_config()
        self.world = World(config)
        self.world.add_collision_callback(self.game.on_collision)

        # Create per-player game extensions and attach them
        for player in players:
            ext = self.game.create_extension(player)
            player.set_extension(ext)

        self.game.setup()
        self.is_running = True

    def swap_game(self, game: Game, players: list[Player]) -> None:
        """Hot-swap to a new minigame (used by Lobby between rounds)."""
        self.load_game(game, players)

    # ── Per-frame tick (called from main loop) ────────────────────────────────

    def tick(self, events: list[pygame.event.Event], dt: float) -> bool:
        """
        Process one frame.  dt is provided by the caller (App.clock).
        Returns False once the current game is over.
        The caller is responsible for calling pygame.display.flip().
        """
        if not self.is_running:
            return False

        # Cap dt to 100ms so a lag spike never skips through an entire timer.
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

    # ── Internal ──────────────────────────────────────────────────────────────

    def _teardown(self) -> None:
        if self.game:
            self.game.teardown()
        if self.world:
            self.world.clear()
        self.game  = None
        self.world = None
