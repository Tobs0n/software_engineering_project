"""
goomba_game.py
==============
Implements the 'Goomba Counter' mini-game.

Players watch a stream of coloured circles cross the screen and count how
many are Goombas (the brown circle).  At the end of the round the player
whose count is closest to the true number wins 3 points; everyone else
scores 0.

Authority model
---------------
All authoritative state (timer, entity positions, correct count, player
counters) lives on the host and is broadcast to peers every few frames.
Peers only send lightweight "increment" input messages when the player
presses SPACE.
"""

from __future__ import annotations

import random

import pygame

from ...abstract.game import Game
from ...engine.world_config import WorldConfig
from .goomba_player_extension import GoombaExtension

# ── Constants ─────────────────────────────────────────────────────────────────

ROUND_TIME = 45.0
"""Total duration of a round in seconds."""

SYNC_EVERY = 2
"""Broadcast the authoritative game state every this many frames.

At 60 fps this results in roughly 30 state updates per second, which keeps
bandwidth low while still feeling responsive to peers."""

SPAWN_INTERVAL = 45
"""Number of frames between entity spawns (~0.75 s at 60 fps)."""

SPAWN_STOP = 2700
"""Frame number after which no new entities are spawned (45 s × 60 fps)."""

GOOMBA = {"color": (139, 90, 43), "radius": 20, "is_goomba": True, "bounce_chance": 0.3}
"""Template dict for the Goomba entity — the entity players must count.

- ``color``        : brownish RGB colour used when rendering.
- ``radius``       : circle radius in pixels.
- ``is_goomba``    : flag used to increment ``_correct_count`` on spawn.
- ``bounce_chance``: probability (0–1) that the entity reverses direction
  instead of despawning when it leaves the screen.
"""

DISTRACTORS = [
    {"color": (50,  50, 180), "radius": 15, "is_goomba": False, "bounce_chance": 0.7},
    {"color": (100, 10,  30), "radius": 30, "is_goomba": False, "bounce_chance": 0.7},
    {"color": (135, 61, 0), "radius": 12, "is_goomba": False, "bounce_chance": 0.7},
]
"""List of distractor entity templates (Buzzy Beetle and two extras).

Distractors look different from Goombas and have a higher ``bounce_chance``
so they tend to stay on screen longer, making counting harder.
"""

DISTRACTOR_SLOTS_START = 1
"""Minimum number of distractor slots in the spawn pool at the start."""

DISTRACTOR_SLOTS_END = 6
"""Maximum number of distractor slots in the spawn pool at the end.

The number of distractor slots scales linearly from ``DISTRACTOR_SLOTS_START``
to ``DISTRACTOR_SLOTS_END`` over the course of the round, making the game
progressively harder.
"""


class GoombaGame(Game):
    """Goomba Counter mini-game.

    Players count how many Goombas (brown circles) cross the screen during a
    45-second round.  At the end, the player whose submitted count is closest
    to the real number wins.

    Pressing **SPACE** increments the local player's Goomba counter by one.

    Authority model summary
    -----------------------
    ``[AUTHORITY]``  ``self._time_left``     – host counts down; synced every
                                               ``SYNC_EVERY`` frames.
    ``[AUTHORITY]``  ``self._done``          – host decides when the game ends.
    ``[AUTHORITY]``  ``self._entities``      – host spawns and moves all
                                               entities; synced every frame.
    ``[AUTHORITY]``  ``self._correct_count`` – incremented each time a Goomba
                                               is spawned.
    ``[AUTHORITY]``  ``ext.goombacounter``   – incremented by the authority
                                               when it receives an "increment"
                                               input from any peer.
    ``[LOCAL]``      *(nothing)* – players have no local position in this game.
    ``[SHARED]``     ``player.color`` / ``player.name`` – set once at game
                                               start and never changes.
    """

    def __init__(self) -> None:
        """Initialise all instance variables to safe defaults.

        The actual game values are reset in :meth:`setup`, which is called by
        the engine before every round.
        """
        super().__init__()

        self._font_lg: pygame.font.Font | None = None
        """Large monospace font used for the timer and results overlay."""

        self._font_sm: pygame.font.Font | None = None
        """Small monospace font used for player score labels."""

        self._time_left: float = ROUND_TIME
        """Seconds remaining in the current round. Counts down on the host."""

        self._done: bool = False
        """``True`` once the results screen timer has expired and the engine
        should transition away from this game."""

        self._showing_results: bool = False
        """``True`` while the end-of-round results overlay is visible."""

        self._results_timer: float = 8.0
        """Seconds the results screen is shown before ``_done`` is set."""

        self._frame: int = 0
        """Frame counter used to schedule spawns and periodic state syncs."""

        self._entities: list[dict] = []
        """List of active entity dicts (both Goombas and distractors).

        Each dict contains at minimum: ``x``, ``y``, ``vx``, ``vy``,
        ``color``, ``radius``, ``bounce_chance``, ``is_goomba``, and
        optionally ``flash_timer``.
        """

        self._correct_count: int = 0
        """The true number of Goombas that have been spawned this round.
        Peers discover this value when the results overlay is shown.
        """

    # ── Game contract ─────────────────────────────────────────────────────────

    def get_world_config(self) -> WorldConfig:
        """Return the physics / world configuration for this game.

        Gravity and physics are disabled because entities are moved manually
        each frame by :meth:`_move_entities`.  Collisions are also off because
        entities never interact with each other or with players.
        """
        return WorldConfig(
            gravity=0.0,
            has_physics=False,
            has_collisions=False,
            bounds=(0, 0, 800, 600),
        )

    def get_keybindings(self) -> dict:
        """Return the human-readable keybinding hints shown in the HUD."""
        return {"SPACE": "Goomba count +1 (brown dot)"}

    def create_extension(self, player) -> GoombaExtension:
        """Create and return a :class:`GoombaExtension` for *player*.

        Called by the engine once per player when the game is set up.
        The extension stores the player's personal Goomba counter.
        """
        return GoombaExtension(player)

    def setup(self) -> None:
        """Reset all game state and prepare for a new round.

        Called by the engine before the first frame of every round.
        The host broadcasts the initial state so peers start in sync.
        """
        self._font_lg = pygame.font.SysFont("monospace", 28, bold=True)
        self._font_sm = pygame.font.SysFont("monospace", 17)
        self._time_left = ROUND_TIME
        self._done = False
        self._showing_results = False
        self._results_timer = 8.0
        self._frame = 0
        self._entities = []
        self._correct_count = 0

        if self.is_authority:
            self._broadcast_state()

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, events: list[pygame.event.Event], dt: float) -> None:
        """Advance the game by one frame.

        Delegates to the appropriate authority or peer update path.
        During the results screen only the host's countdown to ``_done``
        is processed; all other logic is skipped.

        Args:
            events: Pygame events collected this frame.
            dt:     Elapsed time in seconds since the last frame.
        """
        if self._showing_results:
            if self.is_authority:
                self._results_timer -= dt
                if self._results_timer <= 0:
                    self._done = True
                    self._broadcast_state()
            return

        if self._done:
            return

        self._frame += 1

        if self.is_authority:
            self._update_authority(events, dt)
        else:
            self._update_peer(events)

    def _update_authority(self, events: list[pygame.event.Event], dt: float) -> None:
        """Run all host-side game logic for the current frame.

        Responsibilities:
        - Count down the round timer and trigger :meth:`_end_game` on expiry.
        - Spawn new entities at regular intervals.
        - Move all existing entities.
        - Handle the host player's SPACE key press locally (no round-trip).
        - Periodically broadcast the authoritative state to all peers.

        Args:
            events: Pygame events collected this frame.
            dt:     Elapsed time in seconds since the last frame.
        """
        self._time_left -= dt
        if self._time_left <= 0:
            self._end_game()
            return

        if self._frame % SPAWN_INTERVAL == 0 and self._frame <= SPAWN_STOP:
            self._spawn_entity()

        self._move_entities()

        # The host player presses SPACE locally — no network round-trip needed.
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                host = self.players[0]
                if host.extension:
                    host.extension.increment()

        if self._frame % SYNC_EVERY == 0:
            self._broadcast_state()

    def _update_peer(self, events: list[pygame.event.Event]) -> None:
        """Handle input for non-host players.

        Peers cannot modify game state directly.  When SPACE is pressed they
        send an "increment" message to the host, which then updates the
        counter and includes the new value in the next sync broadcast.

        Args:
            events: Pygame events collected this frame.
        """
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                self._send_input({"action": "increment"})

    # ── on_input_received ─────────────────────────────────────────────────────

    def on_input_received(self, player_id: str, input_data: dict) -> None:
        """Process an input message sent by a peer.

        Currently only the ``"increment"`` action is supported, which
        increments the Goomba counter of the player identified by
        *player_id*.

        Args:
            player_id:  ID of the player who sent the input.
            input_data: Dict payload; must contain ``"action": "increment"``
                        to have any effect.
        """
        if input_data.get("action") == "increment":
            player = self._player_by_id(player_id)
            if player and player.extension:
                player.extension.increment()

    # ── Sync ──────────────────────────────────────────────────────────────────

    def get_sync_state(self) -> dict:
        """Serialise the full authoritative game state into a dict.

        Called by the engine on the host before each broadcast.  The returned
        dict is passed to :meth:`apply_sync_state` on every peer.

        Returns:
            A JSON-serialisable dict containing timer values, entity list, and
            each player's current Goomba counter.
        """
        return {
            "time_left":       self._time_left,
            "done":            self._done,
            "showing_results": self._showing_results,
            "results_timer":   self._results_timer,
            "correct_count":   self._correct_count,
            "entities":        self._entities,
            "players": {
                p.player_id: {"counter": p.extension.goombacounter}
                for p in self.players if p.extension
            },
        }

    def apply_sync_state(self, state: dict) -> None:
        """Overwrite local state with the authoritative state received from the host.

        Uses ``dict.get`` with fallback defaults so that partial updates do
        not reset unmentioned fields.

        Args:
            state: Dict previously produced by :meth:`get_sync_state` on the
                   host.
        """
        self._time_left       = state.get("time_left",       self._time_left)
        self._done            = state.get("done",            self._done)
        self._showing_results = state.get("showing_results", self._showing_results)
        self._results_timer   = state.get("results_timer",   self._results_timer)
        self._correct_count   = state.get("correct_count",   self._correct_count)
        self._entities        = state.get("entities",        self._entities)

        for player in self.players:
            pdata = state.get("players", {}).get(player.player_id)
            if pdata and player.extension:
                player.extension.goombacounter = pdata["counter"]

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface) -> None:
        """Draw the entire game frame onto *surface*.

        Drawing order:
        1. Dark background fill and border.
        2. All active entities (Goombas and distractors).
        3. Player score labels in the four corners.
        4. Countdown timer centred at the top.
        5. Results overlay (when ``_showing_results`` is ``True``).

        Args:
            surface: The pygame Surface to draw onto (typically the window).
        """
        surface.fill((18, 18, 36))
        pygame.draw.rect(surface, (50, 50, 100), pygame.Rect(0, 0, 800, 600), 4)

        # Draw entities — darken colour while the flash timer is active.
        for e in self._entities:
            col = e["color"]
            if e.get("flash_timer", 0) > 0:
                col = tuple(max(0, v - 80) for v in col)
            pygame.draw.circle(
                surface, col,
                (int(e["x"]), int(e["y"])), e["radius"],
            )

        # Draw per-player score labels in corner positions.
        w, h = surface.get_size()
        positions = [
            (0,       h - 40),
            (w - 200, h - 40),
            (0,       30),
            (w - 200, 30),
        ]
        local_id = self.local_player_id if self.players else None
        for i, player in enumerate(self.players[:4]):
            if not player.extension:
                continue
            x, y = positions[i]
            # Show the counter for the local player; only the name for others.
            if player.player_id == local_id:
                label = f"{player.name}: {player.extension.goombacounter}"
                color = player.color
            else:
                label = player.name
                color = (130, 130, 130)
            lbl = self._font_sm.render(label, True, color)
            surface.blit(lbl, (x, y))

        # Draw the countdown timer; turn red in the final 10 seconds.
        t_col = (255, 60, 60) if self._time_left < 10 else (220, 220, 255)
        t_lbl = self._font_lg.render(f"{max(0, int(self._time_left))}s", True, t_col)
        surface.blit(t_lbl, (400 - t_lbl.get_width() // 2, 12))

        if self._showing_results:
            self._render_end_overlay(surface)

    # ── Results ───────────────────────────────────────────────────────────────

    def get_results(self) -> dict[str, int]:
        """Calculate and return the final scores for all players.

        The player(s) with the smallest absolute difference between their
        submitted count and the true Goomba count receive 3 points.
        All other players receive 0 points.

        Returns:
            A dict mapping ``player_id`` → score (3 or 0).
        """
        diffs = {
            p.player_id: abs(
                (p.extension.goombacounter if p.extension else 0) - self._correct_count
            )
            for p in self.players
        }
        best = min(diffs.values(), default=0)
        return {pid: (3 if diff == best else 0) for pid, diff in diffs.items()}

    def teardown(self) -> None:
        """Clean up resources when the game is unloaded.

        Currently a no-op — pygame fonts are garbage-collected automatically.
        Provided for compatibility with the :class:`Game` interface.
        """
        pass

    # ── Private helpers ───────────────────────────────────────────────────────

    def _spawn_entity(self) -> None:
        """Spawn one new entity (Goomba or distractor) and add it to the scene.

        The spawn pool always contains two Goomba slots.  The number of
        distractor slots grows linearly from ``DISTRACTOR_SLOTS_START`` to
        ``DISTRACTOR_SLOTS_END`` as the round progresses, making the game
        harder over time.

        The entity enters from a randomly chosen side of the screen at a
        random vertical position with randomised horizontal and vertical
        velocities.  If the spawned entity is a Goomba, ``_correct_count``
        is incremented immediately.

        Called by ``[AUTHORITY]`` only.
        """
        elapsed = ROUND_TIME - self._time_left
        t = min(elapsed / ROUND_TIME, 1.0)

        # Scale distractor slots linearly with elapsed time.
        distractor_slots = int(
            DISTRACTOR_SLOTS_START + t * (DISTRACTOR_SLOTS_END - DISTRACTOR_SLOTS_START)
        )

        # Build the pool: 2× Goomba + N distractors, then pick one at random.
        pool = [GOOMBA, GOOMBA] + [random.choice(DISTRACTORS) for _ in range(distractor_slots)]
        unit = random.choice(pool)

        side = random.choice(["left", "right"])
        y    = random.randint(50, 550)
        vy   = random.uniform(-2, 2)

        if side == "left":
            x, vx = -unit["radius"], random.uniform(4, 10)
        else:
            x, vx = 800 + unit["radius"], random.uniform(-4, -10)

        if unit["is_goomba"]:
            self._correct_count += 1

        self._entities.append({
            "x": x, "y": y,
            "vx": vx, "vy": vy,
            "color":         unit["color"],
            "radius":        unit["radius"],
            "bounce_chance": unit["bounce_chance"],
            "is_goomba":     unit["is_goomba"],
        })

    def _move_entities(self) -> None:
        """Advance every entity by its velocity and handle boundary behaviour.

        For each entity:
        - Apply ``vx`` / ``vy`` to position.
        - Decrement ``flash_timer`` if active.
        - Reverse ``vy`` when hitting the top or bottom edge.
        - When the entity leaves the left or right edge, either reverse
          direction (based on ``bounce_chance``) or remove it from the scene.
          Goombas that bounce have their ``flash_timer`` set briefly so they
          visually darken as a cue.

        Called by ``[AUTHORITY]`` only.
        """
        to_remove = []
        for e in self._entities:
            e["x"] += e["vx"]
            e["y"] += e["vy"]

            if e.get("flash_timer", 0) > 0:
                e["flash_timer"] -= 1

            # Bounce off the top and bottom walls.
            if e["y"] + e["radius"] > 600 or e["y"] - e["radius"] < 0:
                e["vy"] *= -1

            # Handle leaving the left or right edge.
            if e["x"] > 800 + e["radius"] or e["x"] < -e["radius"]:
                if random.random() < e.get("bounce_chance", 0.5):
                    e["vx"] *= -1
                    if e.get("is_goomba"):
                        e["flash_timer"] = 14  # ~0.23 s at 60 fps
                else:
                    to_remove.append(e)

        for e in to_remove:
            self._entities.remove(e)

    def _end_game(self) -> None:
        """Transition from active gameplay to the results screen.

        Clamps the timer to zero, activates the results overlay, resets the
        countdown for the overlay, and broadcasts the final state so all
        peers switch simultaneously.

        Called by ``[AUTHORITY]`` only.
        """
        self._time_left       = 0
        self._showing_results = True
        self._results_timer   = 8.0
        self._broadcast_state()

    def _player_by_id(self, player_id: str):
        """Look up a player object by their unique player ID.

        Args:
            player_id: The ID string to search for.

        Returns:
            The matching player object, or ``None`` if not found.
        """
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None

    def _render_end_overlay(self, surface: pygame.Surface) -> None:
        """Draw the semi-transparent results overlay on top of the game scene.

        Layout (top to bottom):
        - "RESULTS" header.
        - True Goomba count.
        - Horizontal separator.
        - Ranked list of players with their submitted count and the
          signed difference from the correct answer.  The winner row has a
          green background highlight.
        - Countdown to the next screen at the bottom.

        Args:
            surface: The pygame Surface to draw onto (same surface as
                     :meth:`render`).
        """
        # Semi-transparent dark background.
        overlay = pygame.Surface((800, 600), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surface.blit(overlay, (0, 0))

        title = self._font_lg.render("RESULTS", True, (255, 215, 0))
        surface.blit(title, (400 - title.get_width() // 2, 60))

        answer_lbl = self._font_lg.render(
            f"Goombas: {self._correct_count}", True, (139, 90, 43)
        )
        surface.blit(answer_lbl, (400 - answer_lbl.get_width() // 2, 110))

        pygame.draw.line(surface, (80, 80, 120), (150, 155), (650, 155), 2)

        # Sort players by closeness to the correct count (ascending diff).
        ranking = sorted(
            self.players,
            key=lambda p: abs(
                (p.extension.goombacounter if p.extension else 0) - self._correct_count
            ),
        )
        best_diff = abs(
            (ranking[0].extension.goombacounter if ranking[0].extension else 0)
            - self._correct_count
        )

        y = 175
        for rank, player in enumerate(ranking):
            count     = player.extension.goombacounter if player.extension else 0
            diff      = abs(count - self._correct_count)
            is_winner = diff == best_diff

            # Highlight the winner row with a green rectangle.
            if is_winner:
                pygame.draw.rect(
                    surface, (40, 80, 40),
                    pygame.Rect(140, y - 4, 520, 42), border_radius=6,
                )

            rank_col = (255, 215, 0) if is_winner else (160, 160, 160)
            rank_lbl = self._font_lg.render(f"#{rank + 1}", True, rank_col)
            surface.blit(rank_lbl, (160, y))

            name_lbl = self._font_lg.render(player.name, True, player.color)
            surface.blit(name_lbl, (220, y))

            count_lbl = self._font_lg.render(str(count), True, (230, 230, 230))
            surface.blit(count_lbl, (500, y))

            # Show a tick for a perfect answer; otherwise show the signed delta.
            if diff == 0:
                diff_str = "✓"
                diff_col = (0, 255, 120)
            else:
                diff_str = f"{'+' if count > self._correct_count else ''}{count - self._correct_count}"
                diff_col = (255, 100, 100)
            diff_lbl = self._font_sm.render(diff_str, True, diff_col)
            surface.blit(diff_lbl, (580, y + 6))

            y += 52

        countdown = self._font_sm.render(
            f"Next screen in {max(0, int(self._results_timer))}s",
            True, (140, 140, 140),
        )
        surface.blit(countdown, (400 - countdown.get_width() // 2, 555))