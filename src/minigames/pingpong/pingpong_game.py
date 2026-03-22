from __future__ import annotations
import random
import pygame

from ...abstract.game import Game
from ...engine.world_config import WorldConfig
from .pingpong_extension import PingPongExtension

# ── Constants ──────────────────────────────────────────────────────────────────
WIDTH, HEIGHT   = 800, 600

FIELD_TOP       = 60
FIELD_BOTTOM    = 540
FIELD_HEIGHT    = FIELD_BOTTOM - FIELD_TOP

PADDLE_W        = 12
PADDLE_H        = 110
PADDLE_SPEED    = 6
PADDLE_OFFSET   = 40
PADDLE_STAGGER  = 60
PADDLE_H_4P     = int(PADDLE_H * 2 / 3)

BALL_SIZE       = 12
BALL_SPEED_INIT = 4
BALL_SPEED_MAX  = 12
BALL_ACCEL      = 0.3

SCORE_TO_WIN    = 3

ANIM_DURATION   = 90
FADE_FRAMES     = 60
PADDLE_FRAMES   = 40
LAUNCH_FRAMES   = 20

SYNC_EVERY      = 2


class PingpongGame(Game):
    """
    Ping Pong — 2, 3 or 4 players with team support.
    Every player uses only SPACE to toggle their paddle direction.

    AUTHORITY MODEL SUMMARY
    ───────────────────────
    [AUTHORITY]  self._ball_*         - ball position/velocity, managed by host
    [AUTHORITY]  self._ball_speed     - current ball speed
    [AUTHORITY]  self._scores         - team scores [left, right]
    [AUTHORITY]  self._phase          - current game phase
    [AUTHORITY]  self._phase_timer    - frame counter within phase
    [AUTHORITY]  self._anim_timer     - score animation countdown
    [AUTHORITY]  self._last_scorer    - 0=left, 1=right
    [AUTHORITY]  self._done           - game over flag

    [LOCAL]      ext.paddle_y         - each client moves its own paddle
    [LOCAL]      ext.paddle_dir       - same

    [SHARED]     ext.paddle_x         - set once at setup, never changes
    [SHARED]     ext.paddle_height    - same
    [SHARED]     ext.start_dir        - same
    [SHARED]     player.color / name  - same

    TEAM ASSIGNMENT
    ───────────────
    2 players: left=[0],   right=[1]
    3 players: left=[0],   right=[1, 2]
    4 players: left=[0,1], right=[2, 3]
    """

    def __init__(self):
        super().__init__()
        self._font_lg: pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None

        # [AUTHORITY] ball state
        self._ball_x:     float = WIDTH  // 2
        self._ball_y:     float = FIELD_TOP + FIELD_HEIGHT // 2
        self._ball_vx:    float = BALL_SPEED_INIT
        self._ball_vy:    float = BALL_SPEED_INIT * 0.5
        self._ball_speed: float = BALL_SPEED_INIT

        # [AUTHORITY] game state
        self._scores:      list  = [0, 0]
        self._phase:       str   = "fade_in"
        self._phase_timer: int   = 0
        self._anim_timer:  int   = 0
        self._last_scorer: int   = 0
        self._done:        bool  = False
        self._frame:       int   = 0

        # team membership — set in setup()
        self._left_indices:  list[int] = []
        self._right_indices: list[int] = []

    # ── Game contract ─────────────────────────────────────────────────────────

    def get_world_config(self) -> WorldConfig:
        return WorldConfig(
            gravity=0.0,
            has_physics=False,
            has_collisions=False,
            bounds=(0, 0, WIDTH, HEIGHT),
        )

    def get_keybindings(self) -> dict:
        return {"SPACE": "Toggle paddle direction"}

    def create_extension(self, player) -> PingPongExtension:
        return PingPongExtension(player)

    def setup(self) -> None:
        self._font_lg = pygame.font.SysFont("monospace", 28, bold=True)
        self._font_sm = pygame.font.SysFont("monospace", 18)

        n = len(self.players)
        assert n in (2, 3, 4)

        # Team assignment
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
        """Assign paddle_x, paddle_height, start_dir to each extension."""
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

        for i, idx in enumerate(self._right_indices):
            ext = self.players[idx].extension
            if len(self._right_indices) == 1:
                ext.paddle_height = PADDLE_H
                ext.paddle_x      = float(WIDTH - PADDLE_OFFSET - PADDLE_W)
                ext.start_dir     = 1
            else:
                ext.paddle_height = PADDLE_H_4P
                count = len(self._right_indices)
                ext.paddle_x  = float(WIDTH - PADDLE_OFFSET - PADDLE_W - (count - 1 - i) * PADDLE_STAGGER)
                ext.start_dir = -1 if i == 0 else 1
            ext.key = pygame.K_SPACE
            ext.reset_position(FIELD_TOP, FIELD_HEIGHT)

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, events: list[pygame.event.Event], dt: float) -> None:
        if self._done:
            return

        self._frame += 1

        if self.is_authority:
            self._update_authority(events)
        else:
            self._update_peer(events)

    def _update_authority(self, events) -> None:
        # Handle local (host = player 0) SPACE input
        if self._anim_timer == 0 and self._phase == "playing":
            for event in events:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    self.players[0].extension.on_keydown(FIELD_TOP, FIELD_BOTTOM)

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

    def _update_peer(self, events) -> None:
        """[PEER] Send SPACE to authority; move own paddle locally for responsiveness."""
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

    # ── on_input_received ─────────────────────────────────────────────────────

    def on_input_received(self, player_id: str, input_data: dict) -> None:
        """[AUTHORITY] Apply peer SPACE press to their paddle."""
        if input_data.get("action") != "keydown":
            return
        if self._anim_timer > 0 or self._phase != "playing":
            return
        player = self._player_by_id(player_id)
        if player and player.extension:
            player.extension.on_keydown(FIELD_TOP, FIELD_BOTTOM)

    # ── Sync state ────────────────────────────────────────────────────────────

    def get_sync_state(self) -> dict:
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
            if pdata and player.extension and player.player_id != local_id:
                player.extension.from_dict(pdata)

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface) -> None:
        surface.fill((18, 18, 36))

        pygame.draw.line(surface, (80, 80, 120), (0, FIELD_TOP),    (WIDTH, FIELD_TOP),    2)
        pygame.draw.line(surface, (80, 80, 120), (0, FIELD_BOTTOM), (WIDTH, FIELD_BOTTOM), 2)

        for y in range(FIELD_TOP, FIELD_BOTTOM, 20):
            pygame.draw.rect(surface, (50, 50, 80),
                             pygame.Rect(WIDTH//2 - 2, y, 4, 12))

        # Paddles
        for player in self.players:
            ext = player.extension
            pygame.draw.rect(surface, player.color,
                             pygame.Rect(int(ext.paddle_x), int(ext.paddle_y),
                                         PADDLE_W, ext.paddle_height),
                             border_radius=4)

        # Ball
        if self._anim_timer == 0:
            bx, by = int(self._ball_x), int(self._ball_y)

            if self._phase == "playing":
                pygame.draw.circle(surface, (232, 142, 16), (bx, by), BALL_SIZE)

            elif self._phase in ("fade_in", "paddle_start", "ball_launch"):
                alpha = int(255 * self._phase_timer / FADE_FRAMES) if self._phase == "fade_in" else 255
                bs = pygame.Surface((BALL_SIZE * 2, BALL_SIZE * 2), pygame.SRCALPHA)
                pygame.draw.circle(bs, (232, 142, 16, alpha), (BALL_SIZE, BALL_SIZE), BALL_SIZE)
                surface.blit(bs, (bx - BALL_SIZE, by - BALL_SIZE))

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

        # Scores
        lc = self._team_color(self._left_indices)
        rc = self._team_color(self._right_indices)
        s1 = self._font_lg.render(str(self._scores[0]), True, lc)
        s2 = self._font_lg.render(str(self._scores[1]), True, rc)
        surface.blit(s1, (WIDTH//2 - 60 - s1.get_width(), 16))
        surface.blit(s2, (WIDTH//2 + 60, 16))

        # Controls hint
        hint = self._font_sm.render("SPACE — toggle direction", True, (70, 70, 100))
        surface.blit(hint, (WIDTH//2 - hint.get_width()//2, HEIGHT - 28))

        # Score animation
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
        pass

    # ── Private helpers ───────────────────────────────────────────────────────

    def _update_all_paddles(self) -> None:
        for player in self.players:
            player.extension.update(PADDLE_SPEED, FIELD_TOP, FIELD_BOTTOM)

    def _update_ball(self) -> None:
        self._ball_x += self._ball_vx
        self._ball_y += self._ball_vy

        if self._ball_y - BALL_SIZE <= FIELD_TOP:
            self._ball_y  = FIELD_TOP + BALL_SIZE
            self._ball_vy = abs(self._ball_vy)
        if self._ball_y + BALL_SIZE >= FIELD_BOTTOM:
            self._ball_y  = FIELD_BOTTOM - BALL_SIZE
            self._ball_vy = -abs(self._ball_vy)

    def _check_collisions(self) -> None:
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
                    factor           = self._ball_speed / (self._ball_vx**2 + self._ball_vy**2) ** 0.5
                    self._ball_vx   *= factor
                    self._ball_vy   *= factor
                    return

    def _check_scoring(self) -> None:
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

    def _start_round(self, direction: int) -> None:
        for player in self.players:
            player.extension.reset_position(FIELD_TOP, FIELD_HEIGHT)
        self._reset_ball(direction)
        self._phase       = "fade_in"
        self._phase_timer = 0

    def _reset_ball(self, direction: int) -> None:
        self._ball_x     = float(WIDTH  // 2)
        self._ball_y     = float(FIELD_TOP + FIELD_HEIGHT // 2)
        self._ball_vx    = BALL_SPEED_INIT * direction
        self._ball_vy    = random.choice([-1, 1]) * random.uniform(
            BALL_SPEED_INIT * 0.3, BALL_SPEED_INIT * 0.8
        )
        self._ball_speed = BALL_SPEED_INIT

    def _team_color(self, indices: list[int]) -> tuple:
        colors = [self.players[i].color for i in indices]
        if len(colors) == 1:
            return colors[0]
        return tuple((colors[0][c] + colors[1][c]) // 2 for c in range(3))

    def _local_player(self):
        return self.players[0] if self.players else None

    def _player_by_id(self, player_id: str):
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None
