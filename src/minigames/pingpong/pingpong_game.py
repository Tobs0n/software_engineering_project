"""
pingpong_game.py
================
Implements the 'Ping Pong' mini-game.

Two to four players compete in a classic pong-style match with team support.
The only control is SPACE, which toggles each player's paddle direction
between moving up and moving down.  Teammates share a side of the field and
their paddles are staggered horizontally so they do not overlap.

Team assignment
---------------
- 2 players: left = [0],    right = [1]
- 3 players: left = [0],    right = [1, 2]
- 4 players: left = [0, 1], right = [2, 3]

The first team to reach ``SCORE_TO_WIN`` points wins the match.

Authority model
---------------
``[AUTHORITY]``  Ball state (``_ball_x``, ``_ball_y``, ``_ball_vx``,
                 ``_ball_vy``, ``_ball_speed``, ``_ball_trail``) — the host
                 owns and simulates the ball; peers receive its position each
                 sync frame.
``[AUTHORITY]``  ``_scores``, ``_phase``, ``_phase_timer``, ``_anim_timer``,
                 ``_last_scorer``, ``_done`` — all round/game state.
``[LOCAL]``      ``ext.paddle_y``, ``ext.paddle_dir`` — each client moves its
                 own paddle locally; the host receives "keydown" events and
                 applies them authoritatively.
``[SHARED]``     ``ext.paddle_x``, ``ext.paddle_height``, ``ext.start_dir``,
                 ``player.color``, ``player.name`` — set once at setup and
                 never changed.
"""

from __future__ import annotations

import random

import pygame

from ...abstract.game import Game
from ...engine.world_config import WorldConfig
from .pingpong_extension import PingPongExtension

# ── Constants ──────────────────────────────────────────────────────────────────

WIDTH, HEIGHT = 800, 600
"""Dimensions of the game window in pixels."""

FIELD_TOP = 60
"""Y coordinate of the top boundary of the play field."""

FIELD_BOTTOM = 540
"""Y coordinate of the bottom boundary of the play field."""

FIELD_HEIGHT = FIELD_BOTTOM - FIELD_TOP
"""Total play field height in pixels."""

PADDLE_W = 12
"""Width of each paddle in pixels."""

PADDLE_H = 110
"""Full paddle height used in 2-player mode (one paddle per side)."""

PADDLE_SPEED = 6
"""Pixels per frame each paddle moves in its current direction."""

PADDLE_OFFSET = 40
"""Horizontal distance from the screen edge to the nearest paddle."""

PADDLE_STAGGER = 60
"""Horizontal offset between the two paddles on the same side in 4-player mode."""

PADDLE_H_4P = int(PADDLE_H * 2 / 3)
"""Shorter paddle height used when two players share a side (4-player mode)."""

BALL_SIZE = 12
"""Radius of the ball in pixels."""

BALL_SPEED_INIT = 4
"""Initial ball speed in pixels per frame at the start of each round."""

BALL_SPEED_MAX = 12
"""Maximum ball speed cap — the ball accelerates with every paddle hit."""

BALL_ACCEL = 0.3
"""Speed increase per paddle hit."""

SCORE_TO_WIN = 3
"""Number of points a team must reach to win the match."""

ANIM_DURATION = 90
"""Frames the 'POINT!' scoring animation is shown before the next round starts."""

FADE_FRAMES = 60
"""Frames of the fade-in phase at the start of each round."""

PADDLE_FRAMES = 40
"""Frames of the paddle startup animation before the ball is launched."""

LAUNCH_FRAMES = 20
"""Frames of the ball launch animation (ring + 'GO!' flash)."""

SYNC_EVERY = 2
"""Broadcast authoritative state every this many frames (~30 updates/s at 60 fps)."""

TRAIL_MAX = 30
"""Maximum number of trail positions kept at full ball speed."""


class PingpongGame(Game):
    """Ping Pong mini-game supporting 2, 3, or 4 players with teams.

    Players press SPACE to toggle their paddle between moving up and moving
    down.  The ball accelerates with each hit and bounces off the top and
    bottom walls.  A point is scored when the ball exits through the left or
    right edge.  The first team to ``SCORE_TO_WIN`` points wins.

    The ball grows a motion trail whose length scales with current speed,
    giving players a visual cue of how fast the ball is moving.

    Authority model summary
    -----------------------
    ``[AUTHORITY]``  All ball state, scores, phase, and game-over flag.
    ``[LOCAL]``      ``ext.paddle_y`` / ``ext.paddle_dir`` — each client
                     controls its own paddle and sends "keydown" messages.
    ``[SHARED]``     Paddle positions, heights, and directions set at setup.

    Team assignment
    ---------------
    2p: left=[0], right=[1] |
    3p: left=[0], right=[1,2] |
    4p: left=[0,1], right=[2,3]
    """

    def __init__(self) -> None:
        """Initialise all instance variables to safe defaults.

        Ball state, scores, and team indices are fully configured in
        :meth:`setup` via :meth:`_configure_paddles` and
        :meth:`_reset_ball`.
        """
        super().__init__()

        self._font_lg: pygame.font.Font | None = None
        """Large monospace font used for the score display."""

        self._font_sm: pygame.font.Font | None = None
        """Small monospace font used for the control hint at the bottom."""

        # ── [AUTHORITY] ball state ────────────────────────────────────────────
        self._ball_x:     float = WIDTH  // 2
        """Current horizontal position of the ball's centre in pixels."""

        self._ball_y:     float = FIELD_TOP + FIELD_HEIGHT // 2
        """Current vertical position of the ball's centre in pixels."""

        self._ball_vx:    float = BALL_SPEED_INIT
        """Horizontal component of the ball's velocity (pixels per frame)."""

        self._ball_vy:    float = BALL_SPEED_INIT * 0.5
        """Vertical component of the ball's velocity (pixels per frame)."""

        self._ball_speed: float = BALL_SPEED_INIT
        """Current scalar speed of the ball; increases with each paddle hit."""

        self._ball_trail: list[tuple[float, float]] = []
        """Recent ball positions used to render the motion trail.

        Built and trimmed each frame in :meth:`render`; length proportional
        to how far above ``BALL_SPEED_INIT`` the current speed is.
        """

        self._ball_bounced: bool = False
        """``True`` once the ball has bounced off a wall, enabling the trail."""

        # ── [AUTHORITY] game state ────────────────────────────────────────────
        self._scores:      list = [0, 0]
        """Team scores as ``[left_score, right_score]``."""

        self._phase:       str  = "fade_in"
        """Current round phase.

        Valid values: ``"fade_in"``, ``"paddle_start"``, ``"ball_launch"``,
        ``"playing"``.
        """

        self._phase_timer: int  = 0
        """Frame counter within the current phase; resets on phase transition."""

        self._anim_timer:  int  = 0
        """Frames remaining in the 'POINT!' scoring animation.

        While > 0, the ball is hidden and input is ignored.
        """

        self._last_scorer: int  = 0
        """Index (0 = left, 1 = right) of the team that scored last."""

        self._done:        bool = False
        """``True`` once a team has reached ``SCORE_TO_WIN`` points."""

        self._frame:       int  = 0
        """Frame counter used to schedule periodic state broadcasts."""

        # Team membership — populated in setup().
        self._left_indices:  list[int] = []
        """Indices into ``self.players`` for the left-side team."""

        self._right_indices: list[int] = []
        """Indices into ``self.players`` for the right-side team."""

        # Set by App before load_game() so each client knows its local player.
        self.local_player_id: str = ""
        """Player ID of the player running on this client machine."""

    # ── Game contract ─────────────────────────────────────────────────────────

    def get_world_config(self) -> WorldConfig:
        """Return the physics / world configuration for this game.

        Physics and collisions are fully disabled; everything is simulated
        manually so the host has precise control over the ball and paddles.
        """
        return WorldConfig(
            gravity=0.0,
            has_physics=False,
            has_collisions=False,
            bounds=(0, 0, WIDTH, HEIGHT),
        )

    def get_keybindings(self) -> dict:
        """Return human-readable keybinding hints for the HUD."""
        return {"SPACE": "Toggle paddle direction"}

    def create_extension(self, player) -> PingPongExtension:
        """Create and return a :class:`PingPongExtension` for *player*.

        Paddle geometry is configured later in :meth:`_configure_paddles`
        once the team layout is known.

        Args:
            player: The player object this extension belongs to.
        """
        return PingPongExtension(player)

    def setup(self) -> None:
        """Assign teams, configure paddle geometry, and reset ball and scores.

        Asserts that the player count is 2, 3, or 4 — other counts are not
        supported.  The host broadcasts the initial state so all peers start
        in sync.
        """
        self._font_lg = pygame.font.SysFont("monospace", 28, bold=True)
        self._font_sm = pygame.font.SysFont("monospace", 18)

        n = len(self.players)
        assert n in (2, 3, 4)

        if n == 2:
            self._left_indices  = [0]
            self._right_indices = [1]
        elif n == 3:
            self._left_indices  = [0]
            self._right_indices = [1, 2]
        else:
            self._left_indices  = [0, 1]
            self._right_indices = [2, 3]

        self._configure_paddles()
        self._reset_ball(direction=1)
        self._phase       = "fade_in"
        self._phase_timer = 0
        self._anim_timer  = 0
        self._scores      = [0, 0]
        self._done        = False
        self._frame       = 0

        if self.is_authority:
            self._broadcast_state()

    # ── Paddle configuration ──────────────────────────────────────────────────

    def _configure_paddles(self) -> None:
        """Set the geometry and initial direction for every player's paddle.

        In single-paddle mode (one player per side) the paddle is centred at
        the standard ``PADDLE_OFFSET`` from the edge.  In two-paddle mode the
        paddles are shorter and staggered horizontally by ``PADDLE_STAGGER``
        so they can pass the ball to each other.

        Called once during :meth:`setup`.
        """
        # Left side
        for i, idx in enumerate(self._left_indices):
            ext = self.players[idx].extension
            if len(self._left_indices) == 1:
                ext.paddle_height = PADDLE_H
                ext.paddle_x      = float(PADDLE_OFFSET)
                ext.start_dir     = 1
            else:
                ext.paddle_height = PADDLE_H_4P
                ext.paddle_x      = float(PADDLE_OFFSET + i * PADDLE_STAGGER)
                ext.start_dir     = -1 if i == 0 else 1
            ext.key = pygame.K_SPACE
            ext.reset_position(FIELD_TOP, FIELD_HEIGHT)

        # Right side
        for i, idx in enumerate(self._right_indices):
            ext = self.players[idx].extension
            if len(self._right_indices) == 1:
                ext.paddle_height = PADDLE_H
                ext.paddle_x      = float(WIDTH - PADDLE_OFFSET - PADDLE_W)
                ext.start_dir     = 1
            else:
                ext.paddle_height = PADDLE_H_4P
                count             = len(self._right_indices)
                ext.paddle_x      = float(WIDTH - PADDLE_OFFSET - PADDLE_W - (count - 1 - i) * PADDLE_STAGGER)
                ext.start_dir     = -1 if i == 0 else 1
            ext.key = pygame.K_SPACE
            ext.reset_position(FIELD_TOP, FIELD_HEIGHT)

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, events: list[pygame.event.Event], dt: float) -> None:
        """Advance the game by one frame.

        Returns immediately if the game is already over.  Delegates to the
        authority or peer update path based on ``self.is_authority``.

        Args:
            events: Pygame events collected this frame.
            dt:     Elapsed time in seconds since the last frame (unused by
                    this game — all movement is frame-based, not time-based).
        """
        if self._done:
            return

        self._frame += 1

        if self.is_authority:
            self._update_authority(events)
        else:
            self._update_peer(events)

    def _update_authority(self, events: list[pygame.event.Event]) -> None:
        """Run all host-side game logic for the current frame.

        Phase state machine:

        1. **anim_timer > 0** — Scoring animation plays; input blocked; ball
           hidden.  When it expires, :meth:`_start_round` is called.
        2. **fade_in** — Field fades in over ``FADE_FRAMES`` frames.
        3. **paddle_start** — Paddles animate to their starting positions over
           ``PADDLE_FRAMES`` frames.
        4. **ball_launch** — Launch ring / 'GO!' animation plays over
           ``LAUNCH_FRAMES`` frames.
        5. **playing** — Normal gameplay; ball moves, collisions and scoring
           are checked.

        The host also handles the local player's SPACE key directly without a
        network round-trip and broadcasts the full state every ``SYNC_EVERY``
        frames.

        Args:
            events: Pygame events collected this frame.
        """
        # Handle local host player's paddle input during normal gameplay.
        if self._anim_timer == 0 and self._phase == "playing":
            local = self._local_player()
            if local:
                for event in events:
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                        local.extension.on_keydown(FIELD_TOP, FIELD_BOTTOM)

        # Scoring animation countdown.
        if self._anim_timer > 0:
            self._anim_timer -= 1
            if self._anim_timer == 0:
                self._start_round(direction=1 if self._last_scorer == 0 else -1)

        elif self._phase == "fade_in":
            self._phase_timer += 1
            if self._phase_timer >= FADE_FRAMES:
                self._phase       = "paddle_start"
                self._phase_timer = 0

        elif self._phase == "paddle_start":
            self._update_all_paddles()
            self._phase_timer += 1
            if self._phase_timer >= PADDLE_FRAMES:
                self._phase       = "ball_launch"
                self._phase_timer = 0

        elif self._phase == "ball_launch":
            self._update_all_paddles()
            self._phase_timer += 1
            if self._phase_timer >= LAUNCH_FRAMES:
                self._phase = "playing"

        else:  # playing
            self._update_all_paddles()
            self._update_ball()
            self._check_collisions()
            self._check_scoring()

        if self._frame % SYNC_EVERY == 0:
            self._broadcast_state()

    def _update_peer(self, events: list[pygame.event.Event]) -> None:
        """Handle input and local paddle movement for non-host players.

        The local paddle is moved every frame for immediate visual feedback.
        When SPACE is pressed the action is also sent to the host via a
        "keydown" input message so the host can update its authoritative
        paddle state and include it in the next broadcast.

        Args:
            events: Pygame events collected this frame.
        """
        local = self._local_player()
        if not local:
            return
        ext = local.extension
        if self._anim_timer == 0 and self._phase == "playing":
            for event in events:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    ext.on_keydown(FIELD_TOP, FIELD_BOTTOM)
                    self._send_input({"action": "keydown"})
            ext.update(PADDLE_SPEED, FIELD_TOP, FIELD_BOTTOM)
        elif self._phase in ("paddle_start", "ball_launch"):
            ext.update(PADDLE_SPEED, FIELD_TOP, FIELD_BOTTOM)

    # ── on_input_received ─────────────────────────────────────────────────────

    def on_input_received(self, player_id: str, input_data: dict) -> None:
        """Process a "keydown" message sent by a peer.

        Only the ``"keydown"`` action is supported.  Input is ignored during
        the scoring animation or outside the ``"playing"`` phase to prevent
        players from toggling direction at an illegitimate moment.

        Args:
            player_id:  ID of the player who pressed SPACE.
            input_data: Dict payload; must contain ``"action": "keydown"``.
        """
        if input_data.get("action") != "keydown":
            return
        if self._anim_timer > 0 or self._phase != "playing":
            return
        player = self._player_by_id(player_id)
        if player and player.extension:
            player.extension.on_keydown(FIELD_TOP, FIELD_BOTTOM)

    # ── Sync ──────────────────────────────────────────────────────────────────

    def get_sync_state(self) -> dict:
        """Serialise the full authoritative game state into a dict.

        Ball state, phase info, scores, and every player's paddle state are
        included.  The trail is intentionally omitted — it is reconstructed
        locally in :meth:`render`.

        Returns:
            A JSON-serialisable dict with all state needed by peers.
        """
        return {
            "ball_x":      self._ball_x,
            "ball_y":      self._ball_y,
            "ball_vx":     self._ball_vx,
            "ball_vy":     self._ball_vy,
            "ball_speed":  self._ball_speed,
            "scores":      self._scores,
            "phase":       self._phase,
            "phase_timer": self._phase_timer,
            "anim_timer":  self._anim_timer,
            "last_scorer": self._last_scorer,
            "done":        self._done,
            "paddles": {
                p.player_id: p.extension.to_dict()
                for p in self.players if p.extension
            },
        }

    def apply_sync_state(self, state: dict) -> None:
        """Overwrite local state with the authoritative state from the host.

        For the local player's paddle, only ``paddle_y`` is synced so that
        local direction changes remain responsive without being overwritten
        mid-press.  All other players' paddle state is applied in full.

        Args:
            state: Dict previously produced by :meth:`get_sync_state`.
        """
        self._ball_x      = state.get("ball_x",      self._ball_x)
        self._ball_y      = state.get("ball_y",      self._ball_y)
        self._ball_vx     = state.get("ball_vx",     self._ball_vx)
        self._ball_vy     = state.get("ball_vy",     self._ball_vy)
        self._ball_speed  = state.get("ball_speed",  self._ball_speed)
        self._scores      = state.get("scores",      self._scores)
        self._phase       = state.get("phase",       self._phase)
        self._phase_timer = state.get("phase_timer", self._phase_timer)
        self._anim_timer  = state.get("anim_timer",  self._anim_timer)
        self._last_scorer = state.get("last_scorer", self._last_scorer)
        self._done        = state.get("done",        self._done)

        local_id = self._local_player().player_id if self._local_player() else None
        for player in self.players:
            pdata = state.get("paddles", {}).get(player.player_id)
            if pdata and player.extension:
                if player.player_id != local_id:
                    # Remote player: apply full paddle state from the host.
                    player.extension.from_dict(pdata)
                else:
                    # Local player: only sync vertical position to avoid
                    # overwriting the direction the player just toggled.
                    player.extension.paddle_y = pdata.get("paddle_y", player.extension.paddle_y)

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface) -> None:
        """Draw the complete game frame onto *surface*.

        Drawing order:
        1. Dark background.
        2. Top and bottom field boundary lines.
        3. Dashed centre line.
        4. All paddles.
        5. Ball motion trail (only once the ball has bounced; length scales
           with speed).
        6. Ball itself — colour, size, and transparency vary by phase.
        7. Score labels.
        8. Control hint at the bottom.
        9. 'POINT!' scoring flash (while ``_anim_timer`` > 0).
        10. End-of-game overlay when ``_done`` is ``True``.

        Args:
            surface: The pygame Surface to draw onto (typically the window).
        """
        surface.fill((18, 18, 36))

        # Field boundary lines.
        pygame.draw.line(surface, (80, 80, 120), (0, FIELD_TOP),    (WIDTH, FIELD_TOP),    2)
        pygame.draw.line(surface, (80, 80, 120), (0, FIELD_BOTTOM), (WIDTH, FIELD_BOTTOM), 2)

        # Dashed centre line — alternating segments every 20 px.
        for y in range(FIELD_TOP, FIELD_BOTTOM, 20):
            pygame.draw.rect(surface, (50, 50, 80),
                             pygame.Rect(WIDTH//2 - 2, y, 4, 12))

        # Paddles — drawn for all players as coloured rectangles.
        for player in self.players:
            ext = player.extension
            pygame.draw.rect(surface, player.color,
                             pygame.Rect(int(ext.paddle_x), int(ext.paddle_y),
                                         PADDLE_W, ext.paddle_height),
                             border_radius=4)

        # Ball trail — built here so it is identical on every client.
        if self._anim_timer == 0 and self._phase == "playing":
            if self._ball_bounced:
                self._ball_trail.append((self._ball_x, self._ball_y))
                speed_ratio = max(0.0, (self._ball_speed - BALL_SPEED_INIT) / (BALL_SPEED_MAX - BALL_SPEED_INIT))
                max_len     = int(speed_ratio * TRAIL_MAX)
                if len(self._ball_trail) > max_len:
                    self._ball_trail = self._ball_trail[-max_len:]

            trail_len = len(self._ball_trail)
            for i, (tx, ty) in enumerate(self._ball_trail):
                # Older positions are more transparent and smaller.
                progress = (i + 1) / max(trail_len, 1)
                alpha    = int(180 * progress)
                radius   = max(2, int(BALL_SIZE * 0.6 * progress))
                ts = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(ts, (232, 142, 16, alpha), (radius, radius), radius)
                surface.blit(ts, (int(tx) - radius, int(ty) - radius))
        else:
            self._ball_trail = []

        # Ball — rendered differently per phase.
        if self._anim_timer == 0:
            bx, by = int(self._ball_x), int(self._ball_y)

            if self._phase == "playing":
                # Fully opaque during normal play.
                pygame.draw.circle(surface, (232, 142, 16), (bx, by), BALL_SIZE)

            elif self._phase in ("fade_in", "paddle_start", "ball_launch"):
                # Fade in from transparent during fade_in; fully opaque after.
                alpha = int(255 * self._phase_timer / FADE_FRAMES) if self._phase == "fade_in" else 255
                bs = pygame.Surface((BALL_SIZE * 2, BALL_SIZE * 2), pygame.SRCALPHA)
                pygame.draw.circle(bs, (232, 142, 16, alpha), (BALL_SIZE, BALL_SIZE), BALL_SIZE)
                surface.blit(bs, (bx - BALL_SIZE, by - BALL_SIZE))

                # Expanding ring and 'GO!' flash during ball_launch.
                if self._phase == "ball_launch":
                    progress  = self._phase_timer / LAUNCH_FRAMES
                    ring_r    = int(BALL_SIZE + 30 * progress)
                    ring_surf = pygame.Surface((ring_r * 2, ring_r * 2), pygame.SRCALPHA)
                    pygame.draw.circle(ring_surf, (240, 240, 240, int(200 * (1 - progress))),
                                       (ring_r, ring_r), ring_r, 3)
                    surface.blit(ring_surf, (bx - ring_r, by - ring_r))

                    fade_go   = 1.0 - progress
                    flash_col = (232, 142, 16)
                    flash     = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                    flash.fill((*flash_col, int(60 * fade_go)))
                    surface.blit(flash, (0, 0))
                    pt_font = pygame.font.SysFont("monospace", int(70 + 20 * fade_go), bold=True)
                    pt_lbl  = pt_font.render("GO!", True, flash_col)
                    pt_lbl.set_alpha(int(255 * min(fade_go * 2, 1.0)))
                    surface.blit(pt_lbl, (WIDTH//2 - pt_lbl.get_width()//2,
                                          FIELD_TOP + FIELD_HEIGHT//2 - pt_lbl.get_height()//2 - 100))

        # Team score labels — coloured to match the average team colour.
        lc = self._team_color(self._left_indices)
        rc = self._team_color(self._right_indices)
        s1 = self._font_lg.render(str(self._scores[0]), True, lc)
        s2 = self._font_lg.render(str(self._scores[1]), True, rc)
        surface.blit(s1, (WIDTH//2 - 60 - s1.get_width(), 16))
        surface.blit(s2, (WIDTH//2 + 60, 16))

        hint = self._font_sm.render("SPACE — toggle direction", True, (70, 70, 100))
        surface.blit(hint, (WIDTH//2 - hint.get_width()//2, HEIGHT - 28))

        # Scoring animation — semi-transparent flash on the scoring team's side.
        if self._anim_timer > 0:
            fade      = self._anim_timer / ANIM_DURATION
            flash_col = lc if self._last_scorer == 0 else rc
            flash     = pygame.Surface((WIDTH // 2, HEIGHT), pygame.SRCALPHA)
            flash.fill((*flash_col, int(80 * fade)))
            surface.blit(flash, (0 if self._last_scorer == 0 else WIDTH // 2, 0))
            pt_font = pygame.font.SysFont("monospace", int(36 + 20 * fade), bold=True)
            pt_lbl  = pt_font.render("POINT!", True, flash_col)
            pt_lbl.set_alpha(int(255 * min(fade * 2, 1.0)))
            surface.blit(pt_lbl, (WIDTH//2 - pt_lbl.get_width()//2,
                                   FIELD_TOP + FIELD_HEIGHT//2 - pt_lbl.get_height()//2))

        if self._done:
            self._render_end_overlay(surface)

    def _render_end_overlay(self, surface: pygame.Surface) -> None:
        """Draw the end-of-game winner overlay on top of the game scene.

        Shows a semi-transparent black background and a centred winner label
        coloured to match the winning team.  The label adapts to player count
        — 'Player N' for a 2-player game, 'Team N' otherwise.

        Args:
            surface: The pygame Surface to draw onto.
        """
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        winner = 0 if self._scores[0] > self._scores[1] else 1
        color  = self._team_color(self._left_indices if winner == 0 else self._right_indices)
        n      = len(self.players)
        name   = ("Player 1" if n == 2 else "Team 1") if winner == 0 \
                 else ("Player 2" if n == 2 else "Team 2")

        lbl = self._font_lg.render(f"{name} wins!", True, color)
        surface.blit(lbl, (WIDTH//2 - lbl.get_width()//2, HEIGHT//2 - 20))

    # ── Results ───────────────────────────────────────────────────────────────

    def get_results(self) -> dict[str, int]:
        """Return final scores for all players.

        All players on the winning team receive 3 points; all players on the
        losing team receive 0.

        Returns:
            Dict of ``player_id`` → score (3 or 0).
        """
        winner_team = 0 if self._scores[0] >= self._scores[1] else 1
        winners = self._left_indices if winner_team == 0 else self._right_indices
        losers  = self._right_indices if winner_team == 0 else self._left_indices
        results = {}
        for idx in winners:
            results[self.players[idx].player_id] = 3
        for idx in losers:
            results[self.players[idx].player_id] = 0
        return results

    def teardown(self) -> None:
        """Clean up resources when the game is unloaded.

        Currently a no-op.  Provided for compatibility with the
        :class:`Game` interface.
        """
        pass

    # ── Private helpers ───────────────────────────────────────────────────────

    def _update_all_paddles(self) -> None:
        """Advance every player's paddle by one frame.

        Calls ``extension.update`` for all players, which moves ``paddle_y``
        in the current direction and clamps it to the field boundaries.

        Called by ``[AUTHORITY]`` only.
        """
        for player in self.players:
            player.extension.update(PADDLE_SPEED, FIELD_TOP, FIELD_BOTTOM)

    def _update_ball(self) -> None:
        """Advance the ball position and bounce it off the top and bottom walls.

        Horizontal movement is not clamped here — leaving the left or right
        edge is handled as a scoring event in :meth:`_check_scoring`.

        Called by ``[AUTHORITY]`` only.
        """
        self._ball_x += self._ball_vx
        self._ball_y += self._ball_vy

        if self._ball_y - BALL_SIZE <= FIELD_TOP:
            self._ball_y   = FIELD_TOP + BALL_SIZE
            self._ball_vy  = abs(self._ball_vy)
            self._ball_bounced = True
        if self._ball_y + BALL_SIZE >= FIELD_BOTTOM:
            self._ball_y   = FIELD_BOTTOM - BALL_SIZE
            self._ball_vy  = -abs(self._ball_vy)
            self._ball_bounced = True

    def _check_collisions(self) -> None:
        """Test the ball against every paddle and handle hits.

        On a hit:
        - Vertical exit angle is determined by where the ball hits the paddle
          (centre = straight; edge = steeper).
        - Horizontal direction is forced away from the side that was hit.
        - Ball speed increases by ``BALL_ACCEL``, capped at ``BALL_SPEED_MAX``.
        - Velocity is re-normalised to the new speed.

        Returns early after the first collision to avoid double-bouncing.

        Called by ``[AUTHORITY]`` only.
        """
        ball_rect = pygame.Rect(
            int(self._ball_x) - BALL_SIZE, int(self._ball_y) - BALL_SIZE,
            BALL_SIZE * 2, BALL_SIZE * 2,
        )
        for side, indices in [("left", self._left_indices), ("right", self._right_indices)]:
            for idx in indices:
                ext   = self.players[idx].extension
                prect = pygame.Rect(int(ext.paddle_x), int(ext.paddle_y),
                                    PADDLE_W, ext.paddle_height)
                if ball_rect.colliderect(prect):
                    hit_pos          = (self._ball_y - ext.paddle_y) / ext.paddle_height
                    self._ball_vy    = (hit_pos - 0.5) * 2 * self._ball_speed * 0.8
                    self._ball_vx    = abs(self._ball_vx) if side == "left" else -abs(self._ball_vx)
                    self._ball_speed = min(self._ball_speed + BALL_ACCEL, BALL_SPEED_MAX)
                    # Re-normalise to the new scalar speed.
                    factor           = self._ball_speed / (self._ball_vx**2 + self._ball_vy**2) ** 0.5
                    self._ball_vx   *= factor
                    self._ball_vy   *= factor
                    return

    def _check_scoring(self) -> None:
        """Check whether the ball has exited through the left or right edge.

        Awards a point to the opposing team, triggers the scoring animation,
        and sets ``_done`` if the winning score has been reached.  The state
        is broadcast immediately on a score so all peers see the flash at the
        same moment.

        Called by ``[AUTHORITY]`` only.
        """
        scored = -1
        if self._ball_x < 0:
            self._scores[1] += 1
            scored = 1
        if self._ball_x > WIDTH:
            self._scores[0] += 1
            scored = 0
        if scored >= 0:
            self._last_scorer = scored
            self._anim_timer  = ANIM_DURATION
            if max(self._scores) >= SCORE_TO_WIN:
                self._done = True
            self._broadcast_state()

    def _start_round(self, direction: int = 1) -> None:
        """Reset paddles and ball for a new round after a score.

        The ball is served toward the team that conceded (i.e. away from the
        team that scored), controlled by the *direction* argument.

        Args:
            direction: ``1`` to serve right, ``-1`` to serve left.
        """
        for player in self.players:
            player.extension.reset_position(FIELD_TOP, FIELD_HEIGHT)
        self._reset_ball(direction=direction)
        self._phase       = "fade_in"
        self._phase_timer = 0

    def _reset_ball(self, direction: int = 1) -> None:
        """Place the ball at the centre of the field with a fresh velocity.

        The vertical component is randomised within a range so no two serves
        are identical.  The trail and bounce flag are cleared.

        Args:
            direction: ``1`` = moving right, ``-1`` = moving left.
        """
        self._ball_x       = float(WIDTH  // 2)
        self._ball_y       = float(FIELD_TOP + FIELD_HEIGHT // 2)
        self._ball_vx      = BALL_SPEED_INIT * direction
        self._ball_vy      = random.choice([-1, 1]) * random.uniform(
            BALL_SPEED_INIT * 0.3, BALL_SPEED_INIT * 0.8
        )
        self._ball_speed   = BALL_SPEED_INIT
        self._ball_trail   = []
        self._ball_bounced = False

    def _team_color(self, indices: list[int]) -> tuple:
        """Return the display colour for a team.

        For a single-player team the player's own colour is returned.  For a
        two-player team the per-channel average of both players' colours is
        returned, giving a blended colour that represents the team.

        Args:
            indices: List of player indices (into ``self.players``) for the
                     team.

        Returns:
            An RGB colour tuple.
        """
        colors = [self.players[i].color for i in indices]
        if len(colors) == 1:
            return colors[0]
        return tuple((colors[0][c] + colors[1][c]) // 2 for c in range(3))

    def _local_player(self):
        """Return the player object that belongs to this client.

        Iterates over ``self.players`` and matches against ``local_player_id``.
        Falls back to ``players[0]`` when the attribute is not yet set (e.g.
        before the first sync on the host).

        Returns:
            The local player object, or ``None`` if no players exist.
        """
        for p in self.players:
            if p.player_id == self.local_player_id:
                return p
        return self.players[0] if self.players else None

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