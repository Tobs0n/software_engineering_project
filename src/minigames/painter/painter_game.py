from __future__ import annotations
import pygame

from ...abstract.game import Game
from ...engine.world_config import WorldConfig
from ...engine.physics_body import PhysicsBody
from .painter_extension import PainterExtension

# ── Constants ─────────────────────────────────────────────────────────────────
CELL_SIZE   = 20          # pixels per grid cell
COLS        = 40          # 40 * 20 = 800 px wide
ROWS        = 30          # 30 * 20 = 600 px tall
PLAYER_SIZE = 18          # slightly smaller than a cell so movement feels precise
MOVE_SPEED  = 3           # pixels per frame
ROUND_TIME  = 45.0        # seconds
SYNC_EVERY  = 6           # broadcast authoritative state every N frames

# Spread starting positions across the four quadrants
_START_POSITIONS = [
    (60,  60),            # top-left
    (720, 520),           # bottom-right
    (720, 60),            # top-right
    (60,  520),           # bottom-left
]

# Subtle darkening applied to captured cells so the moving player stands out
_DARKEN = 70


class PainterGame(Game):
    """
    Territory – top-down grid painter.

    AUTHORITY MODEL SUMMARY
    ───────────────────────
    [AUTHORITY]  self._time_left      – host counts down, synced periodically
    [AUTHORITY]  self._done           – host decides when game ends
    [AUTHORITY]  self._grid           – 2-D list of player_id strings (or None)
    [AUTHORITY]  ext.cell_count       – derived from _grid, kept in sync

    [LOCAL]      body.position        – each client moves its own player freely
    [LOCAL]      body.velocity        – same
    """

    def __init__(self):
        super().__init__()
        self._font_lg: pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None

        self._time_left: float = ROUND_TIME           # [AUTHORITY]
        self._done:      bool  = False                 # [AUTHORITY]
        self._frame:     int   = 0
        self._grid: list[list[str | None]] = \
            [[None] * COLS for _ in range(ROWS)]       # [AUTHORITY]

    # ── Game contract ─────────────────────────────────────────────────────────

    def get_world_config(self) -> WorldConfig:
        return WorldConfig(
            gravity=0.0,
            has_physics=False,
            has_collisions=False,
            bounds=(0, 0, 800, 600),
            friction=1.0,
        )

    def get_keybindings(self) -> dict:
        return {"WASD": "Move"}

    def create_extension(self, player) -> PainterExtension:
        ext = PainterExtension(player)

        # Assign a start quadrant based on how many players exist so far
        idx      = len(self.players)
        sx, sy   = _START_POSITIONS[idx % len(_START_POSITIONS)]
        body     = PhysicsBody(sx, sy, PLAYER_SIZE, PLAYER_SIZE)
        body.owner = ext
        ext.body   = body
        return ext

    def setup(self) -> None:
        self._font_lg   = pygame.font.SysFont("monospace", 26, bold=True)
        self._font_sm   = pygame.font.SysFont("monospace", 14)
        self._time_left = ROUND_TIME
        self._done      = False
        self._frame     = 0
        self._grid      = [[None] * COLS for _ in range(ROWS)]

        for player in self.players:
            if player.extension:
                player.extension.reset()
            if player.extension and player.extension.body:
                self.engine.world.add_body(player.extension.body)

        if self.is_authority:
            self._broadcast_state()

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, events: list[pygame.event.Event], dt: float) -> None:
        if self._done:
            return

        self._frame += 1

        if self.is_authority:
            self._update_authority(events, dt)
        else:
            self._update_peer(events, dt)

    def _update_authority(self, events, dt: float) -> None:
        """[AUTHORITY] Full game logic – timer, movement, cell painting."""
        self._time_left -= dt
        if self._time_left <= 0:
            self._time_left = 0.0
            self._done = True
            self._broadcast_state()
            return

        self._apply_local_movement(self.players[0], events)
        self._move_all_players()
        self._paint_cells()          # [AUTHORITY] update grid ownership

        if self._frame % SYNC_EVERY == 0:
            self._broadcast_state()

    def _update_peer(self, events, dt: float) -> None:
        """[PEER] Read local input, apply locally for responsiveness, send to authority."""
        local = self._local_player()
        if not local or not local.extension or not local.extension.body:
            return

        body   = local.extension.body
        keys   = pygame.key.get_pressed()
        bounds = self.engine.world.config.bounds

        dx = (-MOVE_SPEED if keys[pygame.K_a] else 0) + \
             ( MOVE_SPEED if keys[pygame.K_d] else 0)
        dy = (-MOVE_SPEED if keys[pygame.K_w] else 0) + \
             ( MOVE_SPEED if keys[pygame.K_s] else 0)

        body.position.x = max(bounds[0], min(bounds[2] - PLAYER_SIZE, body.position.x + dx))
        body.position.y = max(bounds[1], min(bounds[3] - PLAYER_SIZE, body.position.y + dy))

        if dx != 0 or dy != 0:
            self._send_input({"action": "move", "dx": dx, "dy": dy})

    # ── on_input_received — authority applies peer inputs ─────────────────────

    def on_input_received(self, player_id: str, input_data: dict) -> None:
        """[AUTHORITY] Move a peer's body based on their reported input."""
        player = self._player_by_id(player_id)
        if not player or not player.extension or not player.extension.body:
            return

        if input_data.get("action") == "move":
            body   = player.extension.body
            dx     = input_data.get("dx", 0)
            dy     = input_data.get("dy", 0)
            bounds = self.engine.world.config.bounds
            body.position.x = max(bounds[0], min(bounds[2] - PLAYER_SIZE, body.position.x + dx))
            body.position.y = max(bounds[1], min(bounds[3] - PLAYER_SIZE, body.position.y + dy))

    # ── Sync state (authority → peers) ───────────────────────────────────────

    def get_sync_state(self) -> dict:
        """
        [AUTHORITY] Snapshot all authority-owned values.
        The grid is flattened to a 1-D list for easy serialisation.
        """
        return {
            "time_left": self._time_left,
            "done":      self._done,
            "grid":      [cell for row in self._grid for cell in row],
            "players": {
                p.player_id: {"cell_count": p.extension.cell_count}
                for p in self.players if p.extension
            },
        }

    def apply_sync_state(self, state: dict) -> None:
        """[PEER] Overwrite local copies with authoritative values."""
        self._time_left = state.get("time_left", self._time_left)
        self._done      = state.get("done",      self._done)

        flat = state.get("grid", [])
        if len(flat) == ROWS * COLS:
            for r in range(ROWS):
                for c in range(COLS):
                    self._grid[r][c] = flat[r * COLS + c]

        for player in self.players:
            pdata = state.get("players", {}).get(player.player_id)
            if pdata and player.extension:
                player.extension.cell_count = pdata["cell_count"]

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface) -> None:
        surface.fill((18, 18, 36))

        color_map: dict[str, tuple] = {p.player_id: p.color for p in self.players}

        # Draw captured cells
        for r in range(ROWS):
            for c in range(COLS):
                pid = self._grid[r][c]
                if pid and pid in color_map:
                    base = color_map[pid]
                    dark = tuple(max(0, v - _DARKEN) for v in base[:3])
                    pygame.draw.rect(
                        surface, dark,
                        pygame.Rect(c * CELL_SIZE, r * CELL_SIZE, CELL_SIZE, CELL_SIZE),
                    )

        # Subtle grid lines
        grid_col = (28, 28, 52)
        for c in range(COLS + 1):
            pygame.draw.line(surface, grid_col, (c * CELL_SIZE, 0), (c * CELL_SIZE, 600))
        for r in range(ROWS + 1):
            pygame.draw.line(surface, grid_col, (0, r * CELL_SIZE), (800, r * CELL_SIZE))

        # Draw players on top
        for player in self.players:
            ext  = player.extension
            body = ext.body if ext else None
            if not ext or not body:
                continue

            rect = body.get_world_rect()
            pygame.draw.rect(surface, player.color,      rect, border_radius=6)
            pygame.draw.rect(surface, (255, 255, 255),   rect, 2, border_radius=6)

            name_lbl = self._font_sm.render(player.name, True, (230, 230, 230))
            surface.blit(name_lbl, (
                rect.centerx - name_lbl.get_width() // 2,
                rect.y - 18,
            ))

        # ── HUD ──────────────────────────────────────────────────────────────
        # Timer (centre-top)
        t_col = (255, 60, 60) if self._time_left < 10 else (220, 220, 255)
        t_lbl = self._font_lg.render(f"{max(0, int(self._time_left))}s", True, t_col)
        surface.blit(t_lbl, (400 - t_lbl.get_width() // 2, 8))

        # Score bar at the bottom: one coloured segment per player, width ∝ cell_count
        total_cells = ROWS * COLS
        bar_rect    = pygame.Rect(0, 592, 800, 8)
        pygame.draw.rect(surface, (30, 30, 55), bar_rect)

        bar_x = 0
        for player in self.players:
            count = player.extension.cell_count if player.extension else 0
            w     = int(800 * count / total_cells)
            if w > 0:
                pygame.draw.rect(surface, player.color,
                                 pygame.Rect(bar_x, 592, w, 8))
            bar_x += w

        # Per-player cell count (top-left, one line each)
        score_x = 8
        for player in self.players:
            count = player.extension.cell_count if player.extension else 0
            lbl   = self._font_sm.render(
                f"{player.name}: {count}", True, player.color
            )
            surface.blit(lbl, (score_x, 10))
            score_x += lbl.get_width() + 16

        if self._done:
            self._render_end_overlay(surface)

    # ── Results & lifecycle ───────────────────────────────────────────────────

    def get_results(self) -> dict:
        """Higher cell_count = better score."""
        return {
            p.player_id: p.extension.cell_count if p.extension else 0
            for p in self.players
        }

    def teardown(self) -> None:
        pass

    # ── Private helpers ───────────────────────────────────────────────────────

    def _paint_cells(self) -> None:
        """
        [AUTHORITY] Colour the grid cell under each player's centre.
        Adjusts cell_count for both the previous owner and the new owner.
        """
        for player in self.players:
            if not player.extension or not player.extension.body:
                continue

            body = player.extension.body
            col  = max(0, min(COLS - 1, int(body.position.x // CELL_SIZE)))
            row  = max(0, min(ROWS - 1, int(body.position.y // CELL_SIZE)))

            current_owner = self._grid[row][col]
            if current_owner == player.player_id:
                continue                            # already ours – nothing to do

            # Decrement old owner's count
            if current_owner is not None:
                old_player = self._player_by_id(current_owner)
                if old_player and old_player.extension:
                    old_player.extension.cell_count = max(
                        0, old_player.extension.cell_count - 1
                    )

            self._grid[row][col]          = player.player_id
            player.extension.cell_count  += 1

    def _apply_local_movement(self, player, events) -> None:
        """Authority reads its own (first) player's keyboard directly."""
        if not player or not player.extension or not player.extension.body:
            return
        body = player.extension.body
        keys = pygame.key.get_pressed()
        body.velocity = pygame.Vector2(
            (-MOVE_SPEED if keys[pygame.K_a] else 0) + (MOVE_SPEED if keys[pygame.K_d] else 0),
            (-MOVE_SPEED if keys[pygame.K_w] else 0) + (MOVE_SPEED if keys[pygame.K_s] else 0),
        )

    def _move_all_players(self) -> None:
        bounds = self.engine.world.config.bounds
        for player in self.players:
            if not player.extension or not player.extension.body:
                continue
            body = player.extension.body
            body.position   += body.velocity
            body.position.x  = max(bounds[0], min(bounds[2] - PLAYER_SIZE, body.position.x))
            body.position.y  = max(bounds[1], min(bounds[3] - PLAYER_SIZE, body.position.y))

    def _render_end_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface((800, 600), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        winner = max(
            self.players,
            key=lambda p: p.extension.cell_count if p.extension else 0,
        )
        lbl = self._font_lg.render(f"{winner.name} WINT!", True, winner.color)
        surface.blit(lbl, (400 - lbl.get_width() // 2, 275))

        sub = self._font_sm.render(
            f"{winner.extension.cell_count} vakjes veroverd", True, (200, 200, 200)
        )
        surface.blit(sub, (400 - sub.get_width() // 2, 315))

    def _local_player(self):
        return self.players[0] if self.players else None

    def _player_by_id(self, player_id: str):
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None
