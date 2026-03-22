from __future__ import annotations
import random
import pygame

from ...abstract.game import Game
from ...engine.world_config import WorldConfig
from ...engine.physics_body import PhysicsBody
from .avoid_fireballs_extension import FireBallExtension

# ── Constants ─────────────────────────────────────────────────────────────────
PLAYER_SIZE  = 46
MOVE_SPEED   = 4
TILE_SIZE    = 20
TILE_SPEED   = 100  # pixels per second
SPAWN_INTERVAL = 1.0  # seconds


class avoid_fireballs_game(Game):
    """
    Game where players avoid falling fireballs 
    """

    def __init__(self):
        super().__init__()
        self._font_lg: pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None

        self._tiles: list[PhysicsBody] = []
        self._spawn_timer: float = 0.0
        self._done: bool = False
        self._frame: int = 0

    # ── Game contract ─────────────────────────────────────────────────────────

    def get_world_config(self) -> WorldConfig:
        return WorldConfig(
            gravity=0.0,
            has_physics=False,
            has_collisions=True,
            bounds=(0, 0, 800, 600),
            friction=1.0,
        )

   

    def create_extension(self, player) -> FireBallExtension:
        ext  = FireBallExtension(player)
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
        self._tiles     = []
        self._spawn_timer = 0.0
        self._done      = False
        self._frame     = 0

        for player in self.players:
            if player.extension and player.extension.body:
                self.engine.world.add_body(player.extension.body)

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
        [AUTHORITY] Full game logic - timers, collision resolution, tile spawning.
        """
        # Spawn tiles
        self._spawn_timer += dt
        if self._spawn_timer >= SPAWN_INTERVAL:
            self._spawn_timer = 0.0
            self._spawn_tile()

        # Move tiles
        for tile in self._tiles[:]:
            tile.position.y += TILE_SPEED * dt
            if tile.position.y > 600:
                self._tiles.remove(tile)
                self.engine.world.remove_body(tile)

        # Read local (host) player input directly
        self._apply_local_movement(self.players[0], events)
        self._move_all_players()

        # Check for game over
        alive_players = [p for p in self.players if p.extension and p.extension.is_alive]
        if len(alive_players) <= 1:
            self._done = True

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

    # ── Collision — authority only ────────────────────────────────────────────

    def on_collision(self, a: PhysicsBody, b: PhysicsBody) -> None:
        """[AUTHORITY] Handle player-tile collisions."""
        if not self.is_authority:
            return
        # Check if one is player and one is tile
        ext_a = getattr(a, 'owner', None)
        ext_b = getattr(b, 'owner', None)
        if isinstance(ext_a, FireBallExtension) and b in self._tiles:
            ext_a.lose_life()
            self._tiles.remove(b)
            self.engine.world.remove_body(b)
        elif isinstance(ext_b, FireBallExtension) and a in self._tiles:
            ext_b.lose_life()
            self._tiles.remove(a)
            self.engine.world.remove_body(a)

    # ── Sync state (authority → peers) ───────────────────────────────────────

    def get_sync_state(self) -> dict:
        """
        [AUTHORITY] Snapshot all [AUTHORITY]-tagged values.
        """
        return {
            "done": self._done,
            "tiles": [(t.position.x, t.position.y) for t in self._tiles],
            "players": {
                p.player_id: {
                    "lives": p.extension.lives if p.extension else 0,
                    "score": getattr(p.extension, "score", 0),
                }
                for p in self.players if p.extension
            },
        }

    def apply_sync_state(self, state: dict) -> None:
        """[PEER] Apply authoritative state received from the host."""
        self._done = state.get("done", self._done)

        # Update tiles
        tile_positions = state.get("tiles", [])
        # Remove extra tiles
        while len(self._tiles) > len(tile_positions):
            tile = self._tiles.pop()
            self.engine.world.remove_body(tile)
        # Add missing tiles or update positions
        for i, (x, y) in enumerate(tile_positions):
            if i < len(self._tiles):
                self._tiles[i].position.x = x
                self._tiles[i].position.y = y
            else:
                tile = PhysicsBody(x, y, TILE_SIZE, TILE_SIZE)
                self._tiles.append(tile)
                self.engine.world.add_body(tile)

        player_states = state.get("players", {})
        for player in self.players:
            pdata = player_states.get(player.player_id)
            if pdata and player.extension:
                player.extension.lives = pdata.get("lives", player.extension.lives)
                if hasattr(player.extension, "score"):
                    player.extension.score = pdata.get("score", player.extension.score)

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface) -> None:
        surface.fill((18, 18, 36))
        pygame.draw.rect(surface, (50, 50, 100),
                         pygame.Rect(0, 0, 800, 600), 4)

        # Draw tiles
        for tile in self._tiles:
            rect = tile.get_world_rect()
            pygame.draw.rect(surface, (255, 100, 20), rect, border_radius=5)
            pygame.draw.rect(surface, (255, 200, 50), rect, 2, border_radius=5)

        for player in self.players:
            ext  = player.extension
            body = ext.body if ext else None
            if not ext or not body:
                continue
            rect = body.get_world_rect()

            pygame.draw.rect(surface, player.color, rect, border_radius=10)
            pygame.draw.rect(surface, (255, 255, 255), rect, 2, border_radius=10)

            lbl = self._font_sm.render(player.name, True, (230, 230, 230))
            surface.blit(lbl, (rect.centerx - lbl.get_width() // 2, rect.y - 22))

            for i in range(ext.lives):
                pygame.draw.circle(
                    surface, (220, 50, 70),
                    (rect.x + i * 16, rect.bottom + 10), 6,
                )

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

    def _spawn_tile(self) -> None:
        x = random.randint(0, 800 - TILE_SIZE)
        tile = PhysicsBody(x, -TILE_SIZE, TILE_SIZE, TILE_SIZE)
        self._tiles.append(tile)
        self.engine.world.add_body(tile)

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

    def _move_all_players(self) -> None:
        bounds = self.engine.world.config.bounds
        for player in self.players:
            if not player.extension or not player.extension.body:
                continue
            body = player.extension.body
            body.position += body.velocity
            body.position.x = max(bounds[0], min(bounds[2] - PLAYER_SIZE, body.position.x))
            body.position.y = max(bounds[1], min(bounds[3] - PLAYER_SIZE, body.position.y))

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
        alive = [p for p in self.players if p.extension and p.extension.is_alive]
        if len(alive) == 1:
            winner = alive[0].name
            lbl = self._font_lg.render(f"{winner} wins!", True, (255, 215, 0))
        else:
            lbl = self._font_lg.render("No winner", True, (255, 215, 0))
        surface.blit(lbl, (400 - lbl.get_width() // 2, 260))
