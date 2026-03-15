from __future__ import annotations
import random
import pygame

from ...abstract.game import Game
from ...engine.world_config import WorldConfig
from ...engine.physics_body import PhysicsBody
from .bomb_extension import BombExtension

PLAYER_SIZE = 46
MOVE_SPEED  = 4
ROUND_TIME  = 45.0     # seconds


class BombGame(Game):
    """
    Hot Potato — top-down arena.
    One player holds the bomb.  Press SPACE to throw it to the nearest player.
    Walking into another player also passes the bomb.
    When the timer hits 0, the bomb explodes and the holder loses a life.
    Player with the most lives remaining wins.
    """

    def __init__(self):
        super().__init__()
        self._font_lg: pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None
        self._time_left: float = ROUND_TIME
        self._done: bool = False

    # ── Game contract ─────────────────────────────────────────────────────────

    def get_world_config(self) -> WorldConfig:
        return WorldConfig(
            gravity=0.0,
            has_physics=False,    # we drive movement directly
            has_collisions=True,
            bounds=(0, 0, 800, 600),
            friction=1.0,
        )

    def get_keybindings(self) -> dict:
        return {
            "WASD":  "Move",
            "SPACE": "Throw bomb to nearest player",
        }

    def create_extension(self, player) -> BombExtension:
        ext  = BombExtension(player)
        body = PhysicsBody(
            random.randint(80, 720),
            random.randint(80, 520),
            PLAYER_SIZE, PLAYER_SIZE,
        )
        body.owner = ext
        ext.body   = body
        return ext

    def setup(self) -> None:
        self._font_lg   = pygame.font.SysFont("monospace", 28, bold=True)
        self._font_sm   = pygame.font.SysFont("monospace", 17)
        self._time_left = ROUND_TIME
        self._done      = False

        for player in self.players:
            if player.extension and player.extension.body:
                self.engine.world.add_body(player.extension.body)

        # Random player starts with the bomb
        if self.players:
            random.choice(self.players).extension.receive_bomb()

    def update(self, events: list[pygame.event.Event], dt: float) -> None:
        if self._done:
            return

        self._time_left -= dt

        if self._time_left <= 0:
            self._explode()
            return

        self._handle_local_input(events)
        self._move_all_players()

    def render(self, surface: pygame.Surface) -> None:
        surface.fill((18, 18, 36))

        # Arena border
        pygame.draw.rect(surface, (50, 50, 100),
                         pygame.Rect(0, 0, 800, 600), 4)

        for player in self.players:
            ext  = player.extension
            body = ext.body
            if not ext or not body:
                continue
            rect = body.get_world_rect()

            # Player body
            pygame.draw.rect(surface, player.color, rect, border_radius=10)
            pygame.draw.rect(surface, (255, 255, 255), rect, 2, border_radius=10)

            # Bomb
            if ext.has_bomb:
                cx, cy = rect.centerx, rect.centery
                pygame.draw.circle(surface, (30, 30, 30),   (cx, cy), 18)
                pygame.draw.circle(surface, (255, 100, 20), (cx, cy), 18, 3)
                fuse_col = (255, 80, 80) if self._time_left < 10 else (255, 215, 0)
                pygame.draw.line(surface, fuse_col,
                                 (cx, cy - 18), (cx + 8, cy - 28), 3)

            # Name tag
            lbl = self._font_sm.render(player.name, True, (230, 230, 230))
            surface.blit(lbl, (rect.centerx - lbl.get_width() // 2, rect.y - 22))

            # Lives (hearts)
            for i in range(ext.lives):
                pygame.draw.circle(
                    surface, (220, 50, 70),
                    (rect.x + i * 16, rect.bottom + 10), 6,
                )

        # Timer
        t_col = (255, 60, 60) if self._time_left < 10 else (220, 220, 255)
        t_lbl = self._font_lg.render(f"{max(0, int(self._time_left))}s", True, t_col)
        surface.blit(t_lbl, (400 - t_lbl.get_width() // 2, 12))

        if self._done:
            self._render_end_overlay(surface)

    def get_results(self) -> dict:
        return {
            p.player_id: p.extension.lives if p.extension else 0
            for p in self.players
        }

    def teardown(self) -> None:
        pass

    # ── Collision callback ────────────────────────────────────────────────────

    def on_collision(self, a: PhysicsBody, b: PhysicsBody) -> None:
        ea: BombExtension = a.owner
        eb: BombExtension = b.owner
        if not (ea and eb):
            return
        # Pass bomb on contact
        if ea.has_bomb and not eb.has_bomb:
            ea.throw_bomb()
            eb.receive_bomb()
        elif eb.has_bomb and not ea.has_bomb:
            eb.throw_bomb()
            ea.receive_bomb()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _handle_local_input(self, events: list[pygame.event.Event]) -> None:
        local = self.players[0] if self.players else None
        if not local or not local.extension or not local.extension.body:
            return

        ext  = local.extension
        body = ext.body
        keys = pygame.key.get_pressed()

        vel = pygame.Vector2(0, 0)
        if keys[pygame.K_a]: vel.x -= MOVE_SPEED
        if keys[pygame.K_d]: vel.x += MOVE_SPEED
        if keys[pygame.K_w]: vel.y -= MOVE_SPEED
        if keys[pygame.K_s]: vel.y += MOVE_SPEED
        body.velocity = vel

        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if ext.can_throw():
                    target = self._nearest_other(local)
                    if target:
                        ext.throw_bomb()
                        target.extension.receive_bomb()

    def _move_all_players(self) -> None:
        bounds = self.engine.world.config.bounds
        for player in self.players:
            if not player.extension or not player.extension.body:
                continue
            body = player.extension.body
            body.position += body.velocity

            # Clamp to world bounds
            body.position.x = max(bounds[0], min(bounds[2] - PLAYER_SIZE, body.position.x))
            body.position.y = max(bounds[1], min(bounds[3] - PLAYER_SIZE, body.position.y))

    def _explode(self) -> None:
        for player in self.players:
            if player.extension and player.extension.has_bomb:
                player.extension.lose_life()
                player.extension.has_bomb = False
        self._done = True

    def _nearest_other(self, source):
        if not source.extension:
            return None
        pos    = source.extension.body.position
        others = [p for p in self.players if p is not source and p.extension]
        if not others:
            return None
        return min(others, key=lambda p: pos.distance_to(p.extension.body.position))

    def _render_end_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface((800, 600), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))
        lbl = self._font_lg.render("BOOM!", True, (255, 80, 40))
        surface.blit(lbl, (400 - lbl.get_width() // 2, 260))
