"""
painter_game.py
===============
Implements the 'Painter' mini-game.

Players move freely across a grid and paint cells in their colour.  Cells can
be stolen by walking over them.  Two powerups add variety:

- **Brush** (green pickup) – paints a 3×3 area around the player for a few
  seconds instead of just the single cell underfoot.
- **Bomb** (orange pickup) – detonates on SPACE, painting a circular blast
  radius around the player.

At the end of the round the player who has painted the most cells wins.

Authority model
---------------
``[AUTHORITY]``  ``_time_left``, ``_done``, ``_grid``, ``_pickups``,
                 ``_spawn_timer`` – all mutable game state lives on the host.
``[AUTHORITY]``  ``ext.cell_count``, ``ext.brush_timer``, ``ext.has_bomb``
                 – player-specific game state is also owned by the host.
``[LOCAL]``      ``body.position`` / ``body.velocity`` – each client moves
                 its own character locally for responsive input; the host
                 receives position updates via "move" messages and uses them
                 for painting and pickup detection.
"""

from __future__ import annotations

import random
import math

import pygame

from ...abstract.game import Game
from ...engine.world_config import WorldConfig
from ...engine.physics_body import PhysicsBody
from .painter_extension import PainterExtension

# ── Constants ─────────────────────────────────────────────────────────────────

CELL_SIZE = 20
"""Width and height of a single grid cell in pixels."""

COLS = 40
"""Number of grid columns (40 × 20 px = 800 px wide)."""

ROWS = 30
"""Number of grid rows (30 × 20 px = 600 px tall)."""

PLAYER_SIZE = 18
"""Width and height of each player's square hitbox in pixels."""

MOVE_SPEED = 3
"""Pixels per frame each player moves when a direction key is held."""

ROUND_TIME = 45.0
"""Total round duration in seconds."""

SYNC_EVERY = 2
"""Broadcast authoritative state every this many frames (~30 updates/s at 60 fps)."""

_START_X = 800 // 2 - PLAYER_SIZE // 2
"""Horizontal starting position for all players (horizontally centred)."""

_START_Y = 300 - PLAYER_SIZE // 2
"""Vertical starting position for all players (vertically centred)."""

_DARKEN = 70
"""Amount subtracted from each RGB channel when rendering a captured cell,
giving it a darker tint compared to the player's bright colour."""

_BAR_H = 8
"""Height in pixels of each player's score bar at the bottom of the screen."""

_BAR_MARGIN = 2
"""Vertical gap in pixels between score bars."""

# ── Powerup settings ──────────────────────────────────────────────────────────

BRUSH_DURATION = 3.0
"""Seconds the wide-brush powerup stays active after being picked up."""

BRUSH_RADIUS = 1
"""Cell radius of the wide brush — results in a 3×3 painting area."""

BOMB_RADIUS = 4
"""Circular blast radius of the bomb powerup, measured in cells."""

MAX_POWERUPS = 3
"""Maximum number of pickups that can exist on the field simultaneously."""

SPAWN_INTERVAL = 6.0
"""Seconds between pickup spawn attempts."""

POWERUP_BRUSH = "brush"
"""String identifier for the brush powerup type."""

POWERUP_BOMB = "bomb"
"""String identifier for the bomb powerup type."""

_BRUSH_COL = (80, 220, 120)
"""Render colour (green) for brush pickup tiles."""

_BOMB_COL = (255, 120, 40)
"""Render colour (orange) for bomb pickup tiles and the 'bomb ready' dot."""


class PainterGame(Game):
    """Top-down grid painter mini-game with powerups.

    Each player moves around a grid using WASD and automatically paints every
    cell they stand on.  Cells can be re-claimed by walking over them.  Two
    powerups add variety — the brush enlarges the painted area to 3×3 cells,
    while the bomb instantly claims a circular area when detonated with SPACE.

    The player with the most painted cells when the timer expires wins.

    Authority model summary
    -----------------------
    ``[AUTHORITY]``  ``_time_left`` / ``_done`` / ``_grid`` / ``_pickups`` /
                     ``_spawn_timer`` — all mutable game state.
    ``[AUTHORITY]``  ``ext.cell_count`` / ``ext.brush_timer`` /
                     ``ext.has_bomb`` — per-player game state.
    ``[LOCAL]``      ``body.position`` / ``body.velocity`` — each client moves
                     its own character locally; position is sent to the host
                     via "move" input messages.
    """

    def __init__(self) -> None:
        """Initialise all instance variables to safe defaults.

        Fonts and grid data are fully initialised in :meth:`setup`.
        """
        super().__init__()

        self._font_lg:   pygame.font.Font | None = None
        """Large monospace font used for the countdown timer."""

        self._font_sm:   pygame.font.Font | None = None
        """Small monospace font used for score bar labels."""

        self._font_icon: pygame.font.Font | None = None
        """Tiny bold font used to draw the 'B' / 'X' icon on pickup tiles."""

        self._time_left: float = ROUND_TIME
        """Seconds remaining in the round. Counts down on the host."""

        self._done: bool = False
        """``True`` once time runs out and the engine should end the game."""

        self._frame: int = 0
        """Frame counter used to schedule periodic state broadcasts."""

        self._grid: list[list[str | None]] = [[None] * COLS for _ in range(ROWS)]
        """2-D grid of player IDs (or ``None`` for unpainted cells).

        Indexed as ``_grid[row][col]``.  Owned by the host and synced to
        peers every ``SYNC_EVERY`` frames as a flattened list.
        """

        self._pickups: list[dict] = []
        """List of active pickup dicts, each with keys ``type``, ``col``, ``row``."""

        self._spawn_timer: float = SPAWN_INTERVAL
        """Seconds until the next pickup spawn attempt."""

    # ── Game contract ─────────────────────────────────────────────────────────

    def get_world_config(self) -> WorldConfig:
        """Return the physics / world configuration for this game.

        Physics and collisions are disabled — player movement and boundary
        clamping are handled manually each frame.  Friction is set to 1 so
        velocities do not decay between frames.
        """
        return WorldConfig(
            gravity=0.0, has_physics=False, has_collisions=False,
            bounds=(0, 0, 800, 600), friction=1.0,
        )

    def get_keybindings(self) -> dict:
        """Return human-readable keybinding hints for the HUD."""
        return {"WASD": "Move to color the grid", "SPACE": "Detonate bomb powerup"}

    def create_extension(self, player) -> PainterExtension:
        """Create a :class:`PainterExtension` and attach a physics body to it.

        The body is added to the world in :meth:`setup` once the world
        has been fully initialised.

        Args:
            player: The player object this extension belongs to.

        Returns:
            A fully initialised :class:`PainterExtension` with a body.
        """
        ext        = PainterExtension(player)
        body       = PhysicsBody(_START_X, _START_Y, PLAYER_SIZE, PLAYER_SIZE)
        body.owner = ext
        ext.body   = body
        return ext

    def setup(self) -> None:
        """Reset all game state and register physics bodies for a new round.

        Called by the engine before the first frame.  Each player's extension
        is reset to starting values and their physics body is added to the
        world.  The host broadcasts the initial state so all peers start in
        sync.
        """
        self._font_lg   = pygame.font.SysFont("monospace", 26, bold=True)
        self._font_sm   = pygame.font.SysFont("monospace", 14)
        self._font_icon = pygame.font.SysFont("monospace", 11, bold=True)
        self._time_left  = ROUND_TIME
        self._done       = False
        self._frame      = 0
        self._grid       = [[None] * COLS for _ in range(ROWS)]
        self._pickups    = []
        self._spawn_timer = SPAWN_INTERVAL

        for player in self.players:
            if player.extension:
                player.extension.reset()
            if player.extension and player.extension.body:
                self.engine.world.add_body(player.extension.body)

        if self.is_authority:
            self._broadcast_state()

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, events: list[pygame.event.Event], dt: float) -> None:
        """Advance the game by one frame.

        Delegates to the authority or peer update path.  Returns immediately
        if the game is already over.

        Args:
            events: Pygame events collected this frame.
            dt:     Elapsed time in seconds since the last frame.
        """
        if self._done:
            return
        self._frame += 1
        if self.is_authority:
            self._update_authority(events, dt)
        else:
            self._update_peer(events, dt)

    def _update_authority(self, events: list[pygame.event.Event], dt: float) -> None:
        """Run all host-side game logic for the current frame.

        Responsibilities:
        - Count down the round timer and set ``_done`` on expiry.
        - Tick brush timers for all players.
        - Attempt to spawn a new pickup when ``_spawn_timer`` expires.
        - Apply movement for the local (host) player.
        - Check for bomb detonation by the local player.
        - Move all players and clamp their positions to the play area.
        - Check whether any player has walked over a pickup.
        - Paint cells under every player's position (respecting brush radius).
        - Periodically broadcast the full state to peers.

        Args:
            events: Pygame events collected this frame.
            dt:     Elapsed time in seconds since the last frame.
        """
        self._time_left -= dt
        if self._time_left <= 0:
            self._time_left = 0.0
            self._done = True
            self._broadcast_state()
            return

        # Tick brush timers down to zero for every player.
        for player in self.players:
            if player.extension and player.extension.brush_timer > 0:
                player.extension.brush_timer = max(0.0, player.extension.brush_timer - dt)

        # Attempt a pickup spawn once the timer expires.
        self._spawn_timer -= dt
        if self._spawn_timer <= 0:
            self._spawn_timer = SPAWN_INTERVAL
            self._try_spawn_pickup()

        self._apply_local_movement(self._local_player(), events)
        self._check_local_bomb(self._local_player(), events)
        self._move_all_players()
        self._check_pickups()
        self._paint_cells()

        if self._frame % SYNC_EVERY == 0:
            self._broadcast_state()

    def _update_peer(self, events: list[pygame.event.Event], dt: float) -> None:
        """Handle input and local movement for non-host players.

        Peers move their own character locally for instant feedback, then send
        the new position to the host via a "move" input message.  Bomb
        detonation is sent as a separate "use_bomb" message.

        Args:
            events: Pygame events collected this frame.
            dt:     Elapsed time in seconds since the last frame.
        """
        local = self._local_player()
        if not local or not local.extension or not local.extension.body:
            return

        body   = local.extension.body
        keys   = pygame.key.get_pressed()
        bounds = self.engine.world.config.bounds

        dx = (-MOVE_SPEED if keys[pygame.K_a] else 0) + (MOVE_SPEED if keys[pygame.K_d] else 0)
        dy = (-MOVE_SPEED if keys[pygame.K_w] else 0) + (MOVE_SPEED if keys[pygame.K_s] else 0)

        body.position.x = max(bounds[0], min(bounds[2] - PLAYER_SIZE, body.position.x + dx))
        body.position.y = max(bounds[1], min(self._play_bottom(),      body.position.y + dy))

        # Only send a message when the player is actually moving.
        if dx != 0 or dy != 0:
            self._send_input({"action": "move", "x": body.position.x, "y": body.position.y})

        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if local.extension.has_bomb:
                    self._send_input({"action": "use_bomb"})

    # ── on_input_received ─────────────────────────────────────────────────────

    def on_input_received(self, player_id: str, input_data: dict) -> None:
        """Process an input message sent by a peer to the host.

        Supported actions:

        - ``"move"`` — update the peer's body position on the host, clamped
          to the play area bounds.
        - ``"use_bomb"`` — detonate the player's bomb if they have one, then
          immediately broadcast the updated state.

        Args:
            player_id:  ID of the player who sent the message.
            input_data: Dict payload containing ``"action"`` and optional
                        ``"x"`` / ``"y"`` fields.
        """
        player = self._player_by_id(player_id)
        if not player or not player.extension or not player.extension.body:
            return

        action = input_data.get("action")

        if action == "move":
            body   = player.extension.body
            bounds = self.engine.world.config.bounds
            body.position.x = max(bounds[0], min(bounds[2] - PLAYER_SIZE, input_data.get("x", body.position.x)))
            body.position.y = max(bounds[1], min(self._play_bottom(),      input_data.get("y", body.position.y)))

        elif action == "use_bomb":
            if player.extension.has_bomb:
                self._detonate_bomb(player)
                self._broadcast_state()

    # ── Sync ──────────────────────────────────────────────────────────────────

    def get_sync_state(self) -> dict:
        """Serialise the full authoritative game state into a dict.

        The grid is flattened to a 1-D list to keep the payload simple.
        Player bodies' positions are included so peers can render other
        players at the correct location.

        Returns:
            A JSON-serialisable dict with timer values, the flat grid, all
            pickups, and per-player extension and position data.
        """
        return {
            "time_left": self._time_left,
            "done":      self._done,
            "grid":      [cell for row in self._grid for cell in row],
            "pickups":   list(self._pickups),
            "players": {
                p.player_id: {
                    "cell_count":  p.extension.cell_count,
                    "brush_timer": p.extension.brush_timer,
                    "has_bomb":    p.extension.has_bomb,
                    "x": p.extension.body.position.x if p.extension.body else 0,
                    "y": p.extension.body.position.y if p.extension.body else 0,
                }
                for p in self.players if p.extension
            },
        }

    def apply_sync_state(self, state: dict) -> None:
        """Overwrite local state with the authoritative state from the host.

        The flat grid list is re-assembled into the 2-D ``_grid`` structure.
        Position updates from the sync are applied to all players **except**
        the local one, whose position is driven locally to avoid jitter.

        Args:
            state: Dict previously produced by :meth:`get_sync_state`.
        """
        self._time_left = state.get("time_left", self._time_left)
        self._done      = state.get("done",      self._done)
        self._pickups   = state.get("pickups",   self._pickups)

        # Re-assemble the flat grid list into the 2-D structure.
        flat = state.get("grid", [])
        if len(flat) == ROWS * COLS:
            for r in range(ROWS):
                for c in range(COLS):
                    self._grid[r][c] = flat[r * COLS + c]

        for player in self.players:
            pdata = state.get("players", {}).get(player.player_id)
            if pdata and player.extension:
                player.extension.cell_count  = pdata["cell_count"]
                player.extension.brush_timer = pdata["brush_timer"]
                player.extension.has_bomb    = pdata["has_bomb"]
                # Only update position for remote players — local player
                # moves its own body to avoid rubber-banding.
                if player.player_id != getattr(self, "local_player_id", None):
                    if player.extension.body:
                        player.extension.body.position.x = pdata.get("x", player.extension.body.position.x)
                        player.extension.body.position.y = pdata.get("y", player.extension.body.position.y)

    # ── Render ────────────────────────────────────────────────────────────────

    def _bar_area_height(self) -> int:
        """Return the total pixel height reserved for the score bar strip.

        Height scales with the number of players so each bar has equal space.

        Returns:
            Total height in pixels occupied by all score bars plus margins.
        """
        n = len(self.players)
        return n * (_BAR_H + _BAR_MARGIN) + _BAR_MARGIN

    def render(self, surface: pygame.Surface) -> None:
        """Draw the complete game frame onto *surface*.

        Drawing order:
        1. Dark background fill.
        2. Captured (painted) cells with a darkened version of the owner's colour.
        3. Grid lines.
        4. Pickup tiles with an icon letter.
        5. Player characters, brush glow, and bomb indicators.
        6. Countdown timer centred at the top.
        7. Score bars along the bottom edge.

        The grid area is clipped to prevent players or other elements from
        drawing into the score bar strip.

        Args:
            surface: The pygame Surface to draw onto (typically the window).
        """
        surface.fill((18, 18, 36))
        color_map   = {p.player_id: p.color for p in self.players}
        grid_bottom = 600 - self._bar_area_height()

        # Clip rendering to the grid area so nothing bleeds into the score bars.
        surface.set_clip(pygame.Rect(0, 0, 800, grid_bottom))

        # Painted cells — rendered as a darkened version of the owner's colour.
        for r in range(ROWS):
            for c in range(COLS):
                pid = self._grid[r][c]
                if pid and pid in color_map:
                    base = color_map[pid]
                    dark = tuple(max(0, v - _DARKEN) for v in base[:3])
                    pygame.draw.rect(surface, dark,
                                     pygame.Rect(c * CELL_SIZE, r * CELL_SIZE, CELL_SIZE, CELL_SIZE))

        # Vertical and horizontal grid lines.
        grid_col = (28, 28, 52)
        for c in range(COLS + 1):
            pygame.draw.line(surface, grid_col, (c * CELL_SIZE, 0), (c * CELL_SIZE, grid_bottom))
        for r in range(ROWS + 1):
            y = r * CELL_SIZE
            if y > grid_bottom:
                break
            pygame.draw.line(surface, grid_col, (0, y), (800, y))

        # Pickup tiles with a coloured background and a single-letter icon.
        for pickup in self._pickups:
            px    = pickup["col"] * CELL_SIZE
            py    = pickup["row"] * CELL_SIZE
            ptype = pickup["type"]
            col   = _BRUSH_COL if ptype == POWERUP_BRUSH else _BOMB_COL
            pygame.draw.rect(surface, col,
                             pygame.Rect(px + 1, py + 1, CELL_SIZE - 2, CELL_SIZE - 2),
                             border_radius=4)
            icon = "B" if ptype == POWERUP_BRUSH else "X"
            lbl  = self._font_icon.render(icon, True, (20, 20, 20))
            surface.blit(lbl, (px + CELL_SIZE // 2 - lbl.get_width() // 2,
                                py + CELL_SIZE // 2 - lbl.get_height() // 2))

        # Players — square body with a white outline, optional brush glow, and
        # an orange dot in the top-right corner when a bomb is held.
        for player in self.players:
            ext  = player.extension
            body = ext.body if ext else None
            if not ext or not body:
                continue
            rect = body.get_world_rect()

            # Semi-transparent glow shows the 3×3 area the brush will paint.
            if ext.brush_timer > 0:
                cx = int((body.position.x + PLAYER_SIZE // 2) // CELL_SIZE)
                cy = int((body.position.y + PLAYER_SIZE // 2) // CELL_SIZE)
                for dr in range(-BRUSH_RADIUS, BRUSH_RADIUS + 1):
                    for dc in range(-BRUSH_RADIUS, BRUSH_RADIUS + 1):
                        gr, gc = cy + dr, cx + dc
                        if 0 <= gr < ROWS and 0 <= gc < COLS:
                            glow = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                            glow.fill((*player.color[:3], 70))
                            surface.blit(glow, (gc * CELL_SIZE, gr * CELL_SIZE))

            pygame.draw.rect(surface, player.color,    rect, border_radius=6)
            pygame.draw.rect(surface, (255, 255, 255), rect, 2, border_radius=6)

            # Small orange dot signals that a bomb is ready to use.
            if ext.has_bomb:
                pygame.draw.circle(surface, _BOMB_COL, (rect.right - 4, rect.top + 4), 4)

            name_lbl = self._font_sm.render(player.name, True, (230, 230, 230))
            surface.blit(name_lbl, (rect.centerx - name_lbl.get_width() // 2, rect.y - 18))

        surface.set_clip(None)

        # Countdown timer — turns red in the final 10 seconds.
        t_col = (255, 60, 60) if self._time_left < 10 else (220, 220, 255)
        t_lbl = self._font_lg.render(f"{max(0, int(self._time_left))}s", True, t_col)
        surface.blit(t_lbl, (400 - t_lbl.get_width() // 2, 8))

        # Score bars — one per player, stacked at the bottom of the screen.
        total_cells = ROWS * COLS
        for i, player in enumerate(self.players):
            count = player.extension.cell_count if player.extension else 0
            pct   = count / total_cells if total_cells else 0
            bar_y = grid_bottom + _BAR_MARGIN + i * (_BAR_H + _BAR_MARGIN)
            pygame.draw.rect(surface, (30, 30, 55), pygame.Rect(0, bar_y, 800, _BAR_H))
            fill_w = int(800 * pct)
            if fill_w > 0:
                pygame.draw.rect(surface, player.color, pygame.Rect(0, bar_y, fill_w, _BAR_H))
            lbl = self._font_sm.render(f"{player.name}  {pct * 100:.1f}%", True, (230, 230, 230))
            surface.blit(lbl, (6, bar_y + (_BAR_H - lbl.get_height()) // 2))

    # ── Results & lifecycle ───────────────────────────────────────────────────

    def get_results(self) -> dict:
        """Return the final scores as a dict mapping player ID to cell count.

        Raw cell counts are returned rather than win/loss points so the lobby
        can determine ranking relative to other games in the session.

        Returns:
            Dict of ``player_id`` → ``cell_count``.
        """
        return {p.player_id: p.extension.cell_count if p.extension else 0
                for p in self.players}

    def teardown(self) -> None:
        """Clean up resources when the game is unloaded.

        Currently a no-op.  Provided for compatibility with the
        :class:`Game` interface.
        """
        pass

    # ── Powerup helpers [AUTHORITY] ───────────────────────────────────────────

    def _try_spawn_pickup(self) -> None:
        """Attempt to place a new pickup on the grid if the cap allows it.

        Chooses a random type and a random empty cell that is not occupied by
        an existing pickup or a player.  Retries up to 30 times before giving
        up to avoid infinite loops on a very crowded grid.

        Called by ``[AUTHORITY]`` only.
        """
        if len(self._pickups) >= MAX_POWERUPS:
            return
        ptype    = random.choice([POWERUP_BRUSH, POWERUP_BOMB])
        # Build a set of cells that must not be used for the spawn.
        occupied = {(p["col"], p["row"]) for p in self._pickups}
        for player in self.players:
            if player.extension and player.extension.body:
                c = int((player.extension.body.position.x + PLAYER_SIZE // 2) // CELL_SIZE)
                r = int((player.extension.body.position.y + PLAYER_SIZE // 2) // CELL_SIZE)
                occupied.add((c, r))
        max_row = max(2, int(self._play_bottom() // CELL_SIZE) - 2)
        for _ in range(30):
            c = random.randint(2, COLS - 3)
            r = random.randint(2, max_row)
            if (c, r) not in occupied:
                self._pickups.append({"type": ptype, "col": c, "row": r})
                return

    def _check_pickups(self) -> None:
        """Test whether any player is standing on a pickup and apply it.

        A pickup is consumed (removed from the list) the moment any player
        steps into the same grid cell.  Only the first player to reach a
        cell collects it.

        Called by ``[AUTHORITY]`` only.
        """
        remaining = []
        for pickup in self._pickups:
            picked = False
            for player in self.players:
                if not player.extension or not player.extension.body:
                    continue
                c = int((player.extension.body.position.x + PLAYER_SIZE // 2) // CELL_SIZE)
                r = int((player.extension.body.position.y + PLAYER_SIZE // 2) // CELL_SIZE)
                if c == pickup["col"] and r == pickup["row"]:
                    self._apply_pickup(player, pickup["type"])
                    picked = True
                    break
            if not picked:
                remaining.append(pickup)
        self._pickups = remaining

    def _apply_pickup(self, player, ptype: str) -> None:
        """Grant *player* the effect of the given pickup type.

        - ``POWERUP_BRUSH`` resets the player's brush timer to
          ``BRUSH_DURATION``.
        - ``POWERUP_BOMB`` sets ``has_bomb`` to ``True``.

        Args:
            player: The player who collected the pickup.
            ptype:  The pickup type string (``"brush"`` or ``"bomb"``).
        """
        if ptype == POWERUP_BRUSH:
            player.extension.brush_timer = BRUSH_DURATION
        elif ptype == POWERUP_BOMB:
            player.extension.has_bomb = True

    def _check_local_bomb(self, player, events: list[pygame.event.Event]) -> None:
        """Check whether the local (host) player has pressed SPACE to detonate.

        Only called on the host — peer bomb detonations arrive via
        :meth:`on_input_received`.

        Args:
            player: The local player object.
            events: Pygame events collected this frame.
        """
        if not player or not player.extension:
            return
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if player.extension.has_bomb:
                    self._detonate_bomb(player)

    def _detonate_bomb(self, player) -> None:
        """Claim all cells within ``BOMB_RADIUS`` cells of *player*'s position.

        Uses Euclidean distance so the blast area is circular rather than
        square.  Consumes the player's bomb immediately, before painting.

        Called by ``[AUTHORITY]`` only.

        Args:
            player: The player detonating their bomb.
        """
        if not player.extension or not player.extension.body:
            return
        player.extension.has_bomb = False
        cx = int((player.extension.body.position.x + PLAYER_SIZE // 2) // CELL_SIZE)
        cy = int((player.extension.body.position.y + PLAYER_SIZE // 2) // CELL_SIZE)
        for dr in range(-BOMB_RADIUS, BOMB_RADIUS + 1):
            for dc in range(-BOMB_RADIUS, BOMB_RADIUS + 1):
                if math.sqrt(dr * dr + dc * dc) <= BOMB_RADIUS:
                    gc, gr = cx + dc, cy + dr
                    if 0 <= gr < ROWS and 0 <= gc < COLS:
                        self._set_cell(gc, gr, player)

    # ── Grid helpers ──────────────────────────────────────────────────────────

    def _set_cell(self, col: int, row: int, player) -> None:
        """Assign a single grid cell to *player*, updating cell counts.

        If the cell is already owned by *player*, nothing happens.  If it is
        owned by another player, that player's count is decremented before
        the new owner's count is incremented.

        Called by ``[AUTHORITY]`` only.

        Args:
            col:    Column index of the target cell.
            row:    Row index of the target cell.
            player: The player claiming the cell.
        """
        current = self._grid[row][col]
        if current == player.player_id:
            return
        if current is not None:
            old = self._player_by_id(current)
            if old and old.extension:
                old.extension.cell_count = max(0, old.extension.cell_count - 1)
        self._grid[row][col]         = player.player_id
        player.extension.cell_count += 1

    def _paint_cells(self) -> None:
        """Paint cells under every player according to their current brush size.

        If a player's ``brush_timer`` is active, all cells within
        ``BRUSH_RADIUS`` cells of the player's centre are painted.
        Otherwise only the single cell directly under the player is painted.

        Called by ``[AUTHORITY]`` only.
        """
        for player in self.players:
            if not player.extension or not player.extension.body:
                continue
            cx     = int((player.extension.body.position.x + PLAYER_SIZE // 2) // CELL_SIZE)
            cy     = int((player.extension.body.position.y + PLAYER_SIZE // 2) // CELL_SIZE)
            radius = BRUSH_RADIUS if player.extension.brush_timer > 0 else 0
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    gc, gr = cx + dc, cy + dr
                    if 0 <= gr < ROWS and 0 <= gc < COLS:
                        self._set_cell(gc, gr, player)

    # ── Movement helpers ──────────────────────────────────────────────────────

    def _apply_local_movement(self, player, events: list[pygame.event.Event]) -> None:
        """Read WASD keys and set the velocity on the local (host) player's body.

        Velocity is applied by :meth:`_move_all_players` in the same frame.

        Args:
            player: The local player object (``None``-safe).
            events: Pygame events collected this frame (unused here; kept for
                    a consistent signature with peer movement).
        """
        if not player or not player.extension or not player.extension.body:
            return
        body = player.extension.body
        keys = pygame.key.get_pressed()
        body.velocity = pygame.Vector2(
            (-MOVE_SPEED if keys[pygame.K_a] else 0) + (MOVE_SPEED if keys[pygame.K_d] else 0),
            (-MOVE_SPEED if keys[pygame.K_w] else 0) + (MOVE_SPEED if keys[pygame.K_s] else 0),
        )

    def _move_all_players(self) -> None:
        """Advance every player's position by their current velocity.

        Clamps each player to the play area after movement so they cannot
        leave the grid or overlap the score bar strip at the bottom.

        Called by ``[AUTHORITY]`` only.
        """
        bounds = self.engine.world.config.bounds
        for player in self.players:
            if not player.extension or not player.extension.body:
                continue
            body = player.extension.body
            body.position   += body.velocity
            body.position.x  = max(bounds[0], min(bounds[2] - PLAYER_SIZE, body.position.x))
            body.position.y  = max(bounds[1], min(self._play_bottom(),      body.position.y))

    def _play_bottom(self) -> int:
        """Return the lowest Y coordinate a player may occupy.

        Derived from the screen height minus the score bar area minus the
        player size so players never overlap the score bars.

        Returns:
            Maximum allowed ``body.position.y`` value in pixels.
        """
        return 600 - self._bar_area_height() - PLAYER_SIZE

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _local_player(self):
        """Return the player object that belongs to this client.

        Uses ``local_player_id`` if set; falls back to ``players[0]`` on the
        host where the attribute may not yet be populated.

        Returns:
            The local player object, or ``None`` if no players exist.
        """
        local_id = getattr(self, "local_player_id", None)
        if local_id:
            for p in self.players:
                if p.player_id == local_id:
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