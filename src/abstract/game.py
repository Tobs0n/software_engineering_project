from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable

import pygame

if TYPE_CHECKING:
    from ..engine.game_engine import GameEngine
    from ..engine.world_config import WorldConfig
    from ..engine.physics_body import PhysicsBody
    from .player import Player
    from .player_game_extension import PlayerGameExtension


# ══════════════════════════════════════════════════════════════════════════════
#  AUTHORITY MODEL — read this before writing a minigame
# ══════════════════════════════════════════════════════════════════════════════
#
#  MiniParty uses a HOST-AUTHORITATIVE model, NOT a server-simulation model.
#  The TCP server is only a relay — it never touches game objects.
#  One client (the host) owns the true game state and broadcasts it.
#
#  ┌─────────────────────────────────────────────────────────────────────────┐
#  │  AUTHORITY  (host client, self.is_authority == True)                    │
#  │  ─────────────────────────────────────────────────────────────────────  │
#  │  • Runs ALL game logic: timers, scoring, collision outcomes, RNG        │
#  │  • Reads its own keyboard input directly                                │
#  │  • Receives INPUT messages from peers and applies them to their bodies  │
#  │  • After every state change, calls self._broadcast_state()              │
#  │    → GameEngine forwards the call to the network client                 │
#  │    → Server relays it to every other client in the lobby                │
#  │                                                                         │
#  │  PEER  (non-host client, self.is_authority == False)                    │
#  │  ─────────────────────────────────────────────────────────────────────  │
#  │  • Reads its own keyboard input and sends it as INPUT messages          │
#  │  • NEVER modifies authoritative state (e.g. bomb owner, lives)         │
#  │  • Receives GAME_STATE messages → apply_sync_state() updates local view │
#  │  • Renders whatever state it last received from the authority           │
#  └─────────────────────────────────────────────────────────────────────────┘
#
#  MARKING CONVENTION IN YOUR GAME CODE
#  ─────────────────────────────────────
#  Mark every attribute in your Game and Extension classes with one of:
#
#    # [AUTHORITY]  — only the host writes this; peers receive it via sync
#    # [LOCAL]      — each client owns its own copy; never synced
#    # [SHARED]     — identical on all clients; derived from authoritative state
#
#  Example (BombGame):
#    self._time_left   # [AUTHORITY]  host counts down, synced every frame
#    self._done        # [AUTHORITY]  host decides when game ends
#    ext.has_bomb      # [AUTHORITY]  host owns bomb assignment
#    ext.lives         # [AUTHORITY]  host subtracts lives
#    body.position     # [LOCAL]      each client moves its own player
#    body.velocity     # [LOCAL]      same
#
#  HOW TO BROADCAST
#  ─────────────────
#  In your Game subclass, call:
#      self._broadcast_state()
#  whenever authoritative state changes (on throw, on collision, on timer tick).
#  Implement get_sync_state() to return the dict that gets sent.
#  Implement apply_sync_state(state) to apply a received dict.
#
# ══════════════════════════════════════════════════════════════════════════════


class Game(ABC):
    """
    Abstract base for every minigame.

    Lifecycle:
        1. GameEngine sets game.is_authority based on whether the local
           player is the lobby host.
        2. GameEngine calls game.create_extension(player) for every player
           and attaches the extension to the player.
        3. GameEngine calls game.setup().
        4. Each frame:
               authority:  game.update(events, dt)  ->  _broadcast_state()
               peer:       game.update(events, dt)  ->  sends INPUT messages
        5. On GAME_STATE received:  game.apply_sync_state(state)
        6. GameEngine calls game.teardown() and game.get_results().
    """

    def __init__(self):
        self.engine:         GameEngine | None          = None
        self.players:        list[Player]               = []
        self.is_authority:   bool                       = False
        # Set by GameEngine — authority uses it to push state, peers to send input
        self._sync_callback: Callable[[dict], None] | None = None
        self._done: bool = False

    # ── Abstract contract ─────────────────────────────────────────────────────

    @abstractmethod
    def setup(self) -> None:
        """Initialise all game objects, spawn bodies, load fonts/images."""

    @abstractmethod
    def update(self, events: list[pygame.event.Event], dt: float) -> None:
        """
        Process one frame.
        Authority: run game logic, call self._broadcast_state() on changes.
        Peer:      read local input, call self._send_input({...}).
        """

    @abstractmethod
    def render(self, surface: pygame.Surface) -> None:
        """Draw everything. Runs on every client regardless of authority."""

    @abstractmethod
    def get_results(self) -> dict[str, int]:
        """Return {player_id: points_this_round}. Called by authority only."""

    @abstractmethod
    def get_keybindings(self) -> dict[str, str]:
        """Return {key_label: action_description} for the controls overlay."""

    @abstractmethod
    def get_world_config(self) -> WorldConfig:
        """Return the WorldConfig this game requires."""

    @abstractmethod
    def create_extension(self, player: Player) -> PlayerGameExtension:
        """Instantiate and return the correct PlayerGameExtension for a player."""

    @abstractmethod
    def get_sync_state(self) -> dict:
        """
        [AUTHORITY only]
        Return a dict of all [AUTHORITY]-tagged state that peers need.
        Only include game-logic values (timer, lives, bomb owner, scores).
        Never include positions/velocities — those are [LOCAL] per client.
        Called automatically by _broadcast_state().
        """

    @abstractmethod
    def apply_sync_state(self, state: dict) -> None:
        """
        [PEER only]
        Apply a state dict received from the authority.
        Update all [AUTHORITY]-tagged values from the dict.
        Never call this on the authority client.
        """

    # ── Optional overrides ────────────────────────────────────────────────────

    def on_collision(self, a: PhysicsBody, b: PhysicsBody) -> None:
        """
        [AUTHORITY only]
        Called by World when two bodies overlap.
        Guard with `if not self.is_authority: return` at the top.
        """

    def on_input_received(self, player_id: str, input_data: dict) -> None:
        """
        [AUTHORITY only]
        Called when a peer INPUT message arrives.
        Apply the input to that player's body or extension state.
        """

    def teardown(self) -> None:
        """Clean up before the game is unloaded."""

    # ── Helpers (call these from your subclass) ───────────────────────────────

    def _broadcast_state(self) -> None:
        """
        Push current authoritative state to all peers.
        Call this after every change to [AUTHORITY]-tagged state.
        No-op when is_authority is False.
        """
        if self.is_authority and self._sync_callback:
            self._sync_callback({"_type": "state", **self.get_sync_state()})

    def _send_input(self, input_data: dict) -> None:
        """
        Send a local input event to the authority.
        No-op when is_authority is True (authority applies input directly).
        """
        if not self.is_authority and self._sync_callback:
            self._sync_callback({"_type": "input", **input_data})

    @property
    def is_over(self) -> bool:
        return self._done
