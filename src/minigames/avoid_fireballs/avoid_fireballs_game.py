from __future__ import annotations
import random
import pygame

from ...abstract.game import Game
from ...engine.world_config import WorldConfig
from ...engine.physics_body import PhysicsBody
from .avoid_fireballs_extension import BombExtension

# ── Constants ─────────────────────────────────────────────────────────────────
PLAYER_SIZE  = 46
MOVE_SPEED   = 4
ROUND_TIME   = 45.0
SYNC_EVERY   = 6   # broadcast authoritative state every N frames


class BombGame(Game):
    """
    Hot Potato - top-down arena.

    AUTHORITY MODEL SUMMARY
    ───────────────────────
    [AUTHORITY]  self._time_left     - host counts down, synced every SYNC_EVERY frames
    [AUTHORITY]  self._done          - host decides when game ends
    [AUTHORITY]  ext.has_bomb        - only host assigns/transfers bomb
    [AUTHORITY]  ext.lives           - only host subtracts lives

    [LOCAL]      body.position       - each client moves its own player freely
    [LOCAL]      body.velocity       - same
    [LOCAL]      ext._last_throw     - cooldown timer; peer trusts authority for result

    [SHARED]     player.color/name   - set once at game start, never changes
    """

    def __init__(self):
        super().__init__()
        self._font_lg: pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None

        self._time_left: float = ROUND_TIME   # [AUTHORITY]
        self._done:      bool  = False         # [AUTHORITY]
        self._frame:     int   = 0             # frame counter for periodic sync

    # ── Game contract ─────────────────────────────────────────────────────────

    def get_world_config(self) -> WorldConfig:
        return WorldConfig(
            gravity=0.0,
            has_physics=False,
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
        self._frame     = 0

        for player in self.players:
            if player.extension and player.extension.body:
                self.engine.world.add_body(player.extension.body)

        # [AUTHORITY] picks who starts with the bomb
        if self.is_authority and self.players:
            random.choice(self.players).extension.receive_bomb()
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
        """
        [AUTHORITY] Full game logic - timers, collision resolution, bomb transfer.
        """
        # [AUTHORITY] Count down the timer
        self._time_left -= dt
        if self._time_left <= 0:
            self._explode()
            return

        # Read local (host) player input directly
        self._apply_local_movement(self.players[0], events)
        self._move_all_players()

        # [AUTHORITY] Periodic state broadcast so peers stay up to date
        if self._frame % SYNC_EVERY == 0:
            self._broadcast_state()

    def _update_peer(self, events, dt: float) -> None:
        """
        [PEER] Read local input and send to authority. Never touch game logic.
        """
        local = self._local_player()
        if not local or not local.extension or not local.extension.body:
            return

        body = local.extension.body
        ext  = local.extension
        keys = pygame.key.get_pressed()

        dx, dy = 0, 0
        if keys[pygame.K_a]: dx = -MOVE_SPEED
        if keys[pygame.K_d]: dx =  MOVE_SPEED
        if keys[pygame.K_w]: dy = -MOVE_SPEED
        if keys[pygame.K_s]: dy =  MOVE_SPEED

        # Apply movement locally for responsive feel
        body.velocity.x = dx
        body.velocity.y = dy
        bounds = self.engine.world.config.bounds
        body.position.x = max(bounds[0], min(bounds[2] - PLAYER_SIZE, body.position.x + dx))
        body.position.y = max(bounds[1], min(bounds[3] - PLAYER_SIZE, body.position.y + dy))

        # Send movement so authority can update remote player positions
        if dx != 0 or dy != 0:
            self._send_input({"action": "move", "dx": dx, "dy": dy})

        # Request a bomb throw — authority decides if it succeeds
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if ext.has_bomb:
                    self._send_input({"action": "throw"})

    # ── on_input_received — authority applies peer inputs ─────────────────────

    def on_input_received(self, player_id: str, input_data: dict) -> None:
        """[AUTHORITY] Apply a peer's input to their body or extension."""
        player = self._player_by_id(player_id)
        if not player or not player.extension or not player.extension.body:
            return

        action = input_data.get("action")

        if action == "move":
            body   = player.extension.body
            dx     = input_data.get("dx", 0)
            dy     = input_data.get("dy", 0)
            bounds = self.engine.world.config.bounds
            body.position.x = max(bounds[0], min(bounds[2] - PLAYER_SIZE, body.position.x + dx))
            body.position.y = max(bounds[1], min(bounds[3] - PLAYER_SIZE, body.position.y + dy))

        elif action == "throw":
            # [AUTHORITY] Validate and execute the throw
            ext = player.extension
            if ext.can_throw():
                target = self._nearest_other(player)
                if target:
                    ext.throw_bomb()
                    target.extension.receive_bomb()
                    self._broadcast_state()   # immediate sync on state change

    # ── Collision — authority only ────────────────────────────────────────────

    def on_collision(self, a: PhysicsBody, b: PhysicsBody) -> None:
        """[AUTHORITY] Transfer bomb on body contact."""
        if not self.is_authority:
            return
        ea: BombExtension = a.owner
        eb: BombExtension = b.owner
        if not (ea and eb):
            return
        if ea.has_bomb and not eb.has_bomb:
            ea.throw_bomb()
            eb.receive_bomb()
            self._broadcast_state()
        elif eb.has_bomb and not ea.has_bomb:
            eb.throw_bomb()
            ea.receive_bomb()
            self._broadcast_state()

    # ── Sync state (authority → peers) ───────────────────────────────────────

    def get_sync_state(self) -> dict:
        """
        [AUTHORITY] Snapshot all [AUTHORITY]-tagged values.
        Positions are [LOCAL] so they are NOT included here.
        """
        return {
            "time_left": self._time_left,
            "done":      self._done,
            "players":   {
                p.player_id: {
                    "has_bomb": p.extension.has_bomb,
                    "lives":    p.extension.lives,
                }
                for p in self.players if p.extension
            },
        }

    def apply_sync_state(self, state: dict) -> None:
        """[PEER] Apply authoritative state received from the host."""
        self._time_left = state.get("time_left", self._time_left)
        self._done      = state.get("done",      self._done)

        player_states = state.get("players", {})
        for player in self.players:
            pdata = player_states.get(player.player_id)
            if pdata and player.extension:
                player.extension.has_bomb = pdata["has_bomb"]
                player.extension.lives    = pdata["lives"]

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface) -> None:
        surface.fill((18, 18, 36))
        pygame.draw.rect(surface, (50, 50, 100),
                         pygame.Rect(0, 0, 800, 600), 4)

        for player in self.players:
            ext  = player.extension
            body = ext.body if ext else None
            if not ext or not body:
                continue
            rect = body.get_world_rect()

            pygame.draw.rect(surface, player.color, rect, border_radius=10)
            pygame.draw.rect(surface, (255, 255, 255), rect, 2, border_radius=10)

            if ext.has_bomb:
                cx, cy = rect.centerx, rect.centery
                pygame.draw.circle(surface, (30, 30, 30),   (cx, cy), 18)
                pygame.draw.circle(surface, (255, 100, 20), (cx, cy), 18, 3)
                fuse_col = (255, 80, 80) if self._time_left < 10 else (255, 215, 0)
                pygame.draw.line(surface, fuse_col,
                                 (cx, cy - 18), (cx + 8, cy - 28), 3)

            lbl = self._font_sm.render(player.name, True, (230, 230, 230))
            surface.blit(lbl, (rect.centerx - lbl.get_width() // 2, rect.y - 22))

            for i in range(ext.lives):
                pygame.draw.circle(
                    surface, (220, 50, 70),
                    (rect.x + i * 16, rect.bottom + 10), 6,
                )

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

    # ── Private helpers ───────────────────────────────────────────────────────

    def _apply_local_movement(self, player, events) -> None:
        """Authority reads its own player's keyboard directly."""
        if not player or not player.extension or not player.extension.body:
            return
        ext  = player.extension
        body = ext.body
        keys = pygame.key.get_pressed()

        dx = (-MOVE_SPEED if keys[pygame.K_a] else 0) + \
             ( MOVE_SPEED if keys[pygame.K_d] else 0)
        dy = (-MOVE_SPEED if keys[pygame.K_w] else 0) + \
             ( MOVE_SPEED if keys[pygame.K_s] else 0)
        body.velocity = pygame.Vector2(dx, dy)

        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if ext.can_throw():
                    target = self._nearest_other(player)
                    if target:
                        ext.throw_bomb()
                        target.extension.receive_bomb()
                        self._broadcast_state()

    def _move_all_players(self) -> None:
        bounds = self.engine.world.config.bounds
        for player in self.players:
            if not player.extension or not player.extension.body:
                continue
            body = player.extension.body
            body.position += body.velocity
            body.position.x = max(bounds[0], min(bounds[2] - PLAYER_SIZE, body.position.x))
            body.position.y = max(bounds[1], min(bounds[3] - PLAYER_SIZE, body.position.y))

    def _explode(self) -> None:
        for player in self.players:
            if player.extension and player.extension.has_bomb:
                player.extension.lose_life()
                player.extension.has_bomb = False
        self._done = True
        self._broadcast_state()

    def _nearest_other(self, source):
        if not source.extension:
            return None
        pos    = source.extension.body.position
        others = [p for p in self.players if p is not source and p.extension]
        if not others:
            return None
        return min(others, key=lambda p: pos.distance_to(p.extension.body.position))

    def _local_player(self):
        return self.players[0] if self.players else None

    def _player_by_id(self, player_id: str):
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None

    def _render_end_overlay(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface((800, 600), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))
        lbl = self._font_lg.render("BOOM!", True, (255, 80, 40))
        surface.blit(lbl, (400 - lbl.get_width() // 2, 260))
