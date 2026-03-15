from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from ..engine.game_engine import GameEngine
    from ..engine.world_config import WorldConfig
    from ..engine.physics_body import PhysicsBody
    from .player import Player
    from .player_game_extension import PlayerGameExtension


class Game(ABC):
    """
    Abstract base for every minigame.

    Lifecycle:
        1. GameEngine calls game.create_extension(player) for every player
           and attaches the extension to the player.
        2. GameEngine calls game.setup() — spawn bodies, load assets.
        3. Each frame: game.update(events) → world.step() → game.render()
        4. When the game signals it is over, GameEngine calls game.teardown()
           and collects results via game.get_results().
    """

    def __init__(self):
        self.engine:  GameEngine | None = None  # injected by GameEngine
        self.players: list[Player]      = []    # injected by GameEngine

    # ── Abstract contract ─────────────────────────────────────────────────────

    @abstractmethod
    def setup(self) -> None:
        """Initialise all game objects, spawn bodies, load fonts/images."""

    @abstractmethod
    def update(self, events: list[pygame.event.Event], dt: float) -> None:
        """Process input and advance game logic for one frame. dt is in seconds."""

    @abstractmethod
    def render(self, surface: pygame.Surface) -> None:
        """Draw everything onto the given surface."""

    @abstractmethod
    def get_results(self) -> dict[str, int]:
        """Return {player_id: points_this_round} after the game ends."""

    @abstractmethod
    def get_keybindings(self) -> dict[str, str]:
        """Return {key_label: action_description} for the controls overlay."""

    @abstractmethod
    def get_world_config(self) -> WorldConfig:
        """Return the WorldConfig this game requires (gravity, bounds, …)."""

    @abstractmethod
    def create_extension(self, player: Player) -> PlayerGameExtension:
        """Instantiate and return the correct PlayerGameExtension for a player."""

    # ── Optional overrides ────────────────────────────────────────────────────

    def on_collision(self, a: PhysicsBody, b: PhysicsBody) -> None:
        """Called by World.resolve_collisions() when two bodies overlap."""

    def teardown(self) -> None:
        """Clean up any resources before the game is unloaded."""

    # ── Convenience ───────────────────────────────────────────────────────────

    @property
    def is_over(self) -> bool:
        """Subclasses set self._done = True to signal end of game."""
        return getattr(self, "_done", False)
