from __future__ import annotations
import random
import math
import pygame

from ...abstract.game import Game
from ...engine.world_config import WorldConfig
from ...engine.physics_body import PhysicsBody
from .painter_extension import PainterExtension

# ── Constants ─────────────────────────────────────────────────────────────────
CELL_SIZE   = 20
COLS        = 40          # 40 * 20 = 800 px wide
ROWS        = 30          # 30 * 20 = 600 px tall
PLAYER_SIZE = 18
MOVE_SPEED  = 3
ROUND_TIME  = 45.0
SYNC_EVERY  = 2

_START_X = 800 // 2 - PLAYER_SIZE // 2
_START_Y = 300 - PLAYER_SIZE // 2

_DARKEN     = 70
_BAR_H      = 8
_BAR_MARGIN = 2

# ── Powerup settings ──────────────────────────────────────────────────────────
BRUSH_DURATION = 3.0   # seconds the 3×3 brush stays active
BRUSH_RADIUS   = 1     # cells around centre  →  3×3 area
BOMB_RADIUS    = 4     # circular explosion radius in cells
MAX_POWERUPS   = 3     # max pickups on the field simultaneously
SPAWN_INTERVAL = 6.0   # seconds between spawn attempts

POWERUP_BRUSH = "brush"
POWERUP_BOMB  = "bomb"

_BRUSH_COL = (80,  220, 120)   # green pickup
_BOMB_COL  = (255, 120,  40)   # orange pickup


class PainterGame(Game):
    """
    Painter – top-down grid painter with powerups.

    AUTHORITY MODEL SUMMARY
    ───────────────────────
    [AUTHORITY]  _time_left, _done, _grid, _pickups, _spawn_timer
    [AUTHORITY]  ext.cell_count, ext.brush_timer, ext.has_bomb
    [LOCAL]      body.position / velocity
    """

    def __init__(self):
        super().__init__()
        self._font_lg:   pygame.font.Font | None = None
        self._font_sm:   pygame.font.Font | None = None
        self._font_icon: pygame.font.Font | None = None

        self._time_left:   float = ROUND_TIME
        self._done:        bool  = False
        self._frame:       int   = 0
        self._grid: list[list[str | None]] = [[None] * COLS for _ in range(ROWS)]
        self._pickups:     list[dict] = []   # {"type", "col", "row"}
        self._spawn_timer: float      = SPAWN_INTERVAL

    # ── Game contract ─────────────────────────────────────────────────────────

    def get_world_config(self) -> WorldConfig:
        return WorldConfig(
            gravity=0.0, has_physics=False, has_collisions=False,
            bounds=(0, 0, 800, 600), friction=1.0,
        )

    def get_keybindings(self) -> dict:
        return {"WASD": "Move", "SPACE": "Detonate bomb powerup"}

    def create_extension(self, player) -> PainterExtension:
        ext        = PainterExtension(player)
        body       = PhysicsBody(_START_X, _START_Y, PLAYER_SIZE, PLAYER_SIZE)
        body.owner = ext
        ext.body   = body
        return ext

    def setup(self) -> None:
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
        if self._done:
            return
        self._frame += 1
        if self.is_authority:
            self._update_authority(events, dt)
        else:
            self._update_peer(events, dt)

    def _update_authority(self, events, dt: float) -> None:
        self._time_left -= dt
        if self._time_left <= 0:
            self._time_left = 0.0
            self._done = True
            self._broadcast_state()
            return

        # Tick brush timers
        for player in self.players:
            if player.extension and player.extension.brush_timer > 0:
                player.extension.brush_timer = max(0.0, player.extension.brush_timer - dt)

        # Spawn pickups
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

    def _update_peer(self, events, dt: float) -> None:
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

        if dx != 0 or dy != 0:
            self._send_input({"action": "move", "x": body.position.x, "y": body.position.y})

        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if local.extension.has_bomb:
                    self._send_input({"action": "use_bomb"})

    # ── on_input_received ─────────────────────────────────────────────────────

    def on_input_received(self, player_id: str, input_data: dict) -> None:
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
        self._time_left = state.get("time_left", self._time_left)
        self._done      = state.get("done",      self._done)
        self._pickups   = state.get("pickups",   self._pickups)

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
                if player.player_id != getattr(self, "local_player_id", None):
                    if player.extension.body:
                        player.extension.body.position.x = pdata.get("x", player.extension.body.position.x)
                        player.extension.body.position.y = pdata.get("y", player.extension.body.position.y)

    # ── Render ────────────────────────────────────────────────────────────────

    def _bar_area_height(self) -> int:
        n = len(self.players)
        return n * (_BAR_H + _BAR_MARGIN) + _BAR_MARGIN

    def render(self, surface: pygame.Surface) -> None:
        surface.fill((18, 18, 36))
        color_map   = {p.player_id: p.color for p in self.players}
        grid_bottom = 600 - self._bar_area_height()

        surface.set_clip(pygame.Rect(0, 0, 800, grid_bottom))

        # Captured cells
        for r in range(ROWS):
            for c in range(COLS):
                pid = self._grid[r][c]
                if pid and pid in color_map:
                    base = color_map[pid]
                    dark = tuple(max(0, v - _DARKEN) for v in base[:3])
                    pygame.draw.rect(surface, dark,
                                     pygame.Rect(c * CELL_SIZE, r * CELL_SIZE, CELL_SIZE, CELL_SIZE))

        # Grid lines
        grid_col = (28, 28, 52)
        for c in range(COLS + 1):
            pygame.draw.line(surface, grid_col, (c * CELL_SIZE, 0), (c * CELL_SIZE, grid_bottom))
        for r in range(ROWS + 1):
            y = r * CELL_SIZE
            if y > grid_bottom:
                break
            pygame.draw.line(surface, grid_col, (0, y), (800, y))

        # Pickups
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

        # Players
        for player in self.players:
            ext  = player.extension
            body = ext.body if ext else None
            if not ext or not body:
                continue
            rect = body.get_world_rect()

            # Brush glow: show the 3×3 area that will be painted
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

            # Orange dot = bomb ready
            if ext.has_bomb:
                pygame.draw.circle(surface, _BOMB_COL, (rect.right - 4, rect.top + 4), 4)

            name_lbl = self._font_sm.render(player.name, True, (230, 230, 230))
            surface.blit(name_lbl, (rect.centerx - name_lbl.get_width() // 2, rect.y - 18))

        surface.set_clip(None)

        # Timer
        t_col = (255, 60, 60) if self._time_left < 10 else (220, 220, 255)
        t_lbl = self._font_lg.render(f"{max(0, int(self._time_left))}s", True, t_col)
        surface.blit(t_lbl, (400 - t_lbl.get_width() // 2, 8))

        # Score bars
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
        return {p.player_id: p.extension.cell_count if p.extension else 0
                for p in self.players}

    def teardown(self) -> None:
        pass

    # ── Powerup helpers [AUTHORITY] ───────────────────────────────────────────

    def _try_spawn_pickup(self) -> None:
        if len(self._pickups) >= MAX_POWERUPS:
            return
        ptype     = random.choice([POWERUP_BRUSH, POWERUP_BOMB])
        occupied  = {(p["col"], p["row"]) for p in self._pickups}
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
        if ptype == POWERUP_BRUSH:
            player.extension.brush_timer = BRUSH_DURATION
        elif ptype == POWERUP_BOMB:
            player.extension.has_bomb = True

    def _check_local_bomb(self, player, events) -> None:
        if not player or not player.extension:
            return
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if player.extension.has_bomb:
                    self._detonate_bomb(player)

    def _detonate_bomb(self, player) -> None:
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

    def _apply_local_movement(self, player, events) -> None:
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
            body.position.y  = max(bounds[1], min(self._play_bottom(),      body.position.y))

    def _play_bottom(self) -> int:
        return 600 - self._bar_area_height() - PLAYER_SIZE

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _local_player(self):
        local_id = getattr(self, "local_player_id", None)
        if local_id:
            for p in self.players:
                if p.player_id == local_id:
                    return p
        return self.players[0] if self.players else None

    def _player_by_id(self, player_id: str):
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None