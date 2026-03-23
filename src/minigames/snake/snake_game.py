import random
import pygame
from ...abstract.game import Game
from ...engine.world_config import WorldConfig
from .snake_extension import SnakeExtension


class SnakeGame(Game):
    GRID_SIZE = 20
    MOVE_DELAY = 0.15
    SYNC_EVERY = 0
    GROW_INTERVAL = 2000

    def __init__(self):
        super().__init__()
        self.apples = []
        self.move_timer = 0.0
        self.done = False
        self.last_growth_time = 0.0
        self.floating_messages = []
        self.frame = 0

    def get_world_config(self) -> WorldConfig:
        return WorldConfig(gravity=0.0, has_physics=False, bounds=(0, 0, 800, 600))

    def create_extension(self, player) -> SnakeExtension:
        return SnakeExtension(player)

    def setup(self):
        starts = [[100, 100], [700, 100], [100, 500], [700, 500]]
        dirs = [[20, 0], [-20, 0], [20, 0], [-20, 0]]

        for i, p in enumerate(self.players):
            if i < len(starts):
                ext = p.extension
                ext.reset()
                sp = starts[i]
                ext.direction = dirs[i]
                ext.body = [sp, [sp[0] - ext.direction[0], sp[1]], [sp[0] - ext.direction[0] * 2, sp[1]]]

        if self.is_authority:
            self._spawn_apple()
            self.last_growth_time = pygame.time.get_ticks() if hasattr(pygame, 'time') else 0
            self._broadcast_state()

    def _spawn_apple(self):
        kans = random.random()
        if kans < 0.70:
            apple_type = "red"
        elif kans < 0.80:
            apple_type = "gold"
        elif kans < 0.90:
            apple_type = "white"
        else:
            apple_type = "blue"

        new_apple = {
            "pos": [random.randint(0, 39) * 20, random.randint(0, 29) * 20],
            "type": apple_type
        }
        self.apples.append(new_apple)

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, events: list, dt: float):
        if self.is_authority:
            self._update_authority(events, dt)
        else:
            self._update_peer(events, dt)

    def _update_authority(self, events, dt):
        if self.done:
            return

        # Authority reads its OWN player's input directly (players[0] is host)
        self._apply_local_input(events)

        current_time = pygame.time.get_ticks() if hasattr(pygame, 'time') else 0
        should_grow = False
        if current_time - self.last_growth_time >= self.GROW_INTERVAL:
            should_grow = True
            self.last_growth_time = current_time

        self.move_timer += dt
        if self.move_timer >= self.MOVE_DELAY:
            self._process_movement(should_grow)
            self.move_timer = 0
            self.frame += 1
            if self.frame % int(self.SYNC_EVERY / self.MOVE_DELAY + 1) == 0:
                self._broadcast_state()

    def _apply_local_input(self, events):
        """Authority reads its own (host) player's keyboard directly."""
        if not self.players:
            return
        ext = self.players[0].extension
        for event in events:
            if event.type == pygame.KEYDOWN:
                new_dir = None
                if event.key == pygame.K_w and ext.direction[1] == 0:
                    new_dir = [0, -20]
                elif event.key == pygame.K_s and ext.direction[1] == 0:
                    new_dir = [0, 20]
                elif event.key == pygame.K_a and ext.direction[0] == 0:
                    new_dir = [-20, 0]
                elif event.key == pygame.K_d and ext.direction[0] == 0:
                    new_dir = [20, 0]
                if new_dir:
                    ext.direction = new_dir

    def _update_peer(self, events, dt):
        """Peer reads local input and sends it to authority. Never touches game logic."""
        if not self.players:
            return
        ext = self.players[0].extension
        for event in events:
            if event.type == pygame.KEYDOWN:
                new_dir = None
                if event.key == pygame.K_w and ext.direction[1] == 0:
                    new_dir = [0, -20]
                elif event.key == pygame.K_s and ext.direction[1] == 0:
                    new_dir = [0, 20]
                elif event.key == pygame.K_a and ext.direction[0] == 0:
                    new_dir = [-20, 0]
                elif event.key == pygame.K_d and ext.direction[0] == 0:
                    new_dir = [20, 0]
                if new_dir:
                    # Optimistically update local direction for responsive feel
                    ext.direction = new_dir
                    # Send to authority so it applies it to the canonical state
                    self._send_input({"action": "turn", "dir": new_dir})

    # ── Authority applies peer input ──────────────────────────────────────────

    def on_input_received(self, player_id, data):
        """[AUTHORITY] Apply a peer's turn request to their snake."""
        if data.get("action") != "turn":
            return

        for p in self.players:
            if p.player_id == player_id:
                ext = p.extension
                new_dir = data["dir"]
                # Prevent 180-degree reversal
                if new_dir[0] != -ext.direction[0] or new_dir[1] != -ext.direction[1]:
                    ext.direction = new_dir
                break

    # ── Game logic (authority only) ───────────────────────────────────────────

    def _process_movement(self, should_grow):
        for p in self.players:
            ext = p.extension
            if not ext.is_alive:
                continue

            if ext.ghost_timer > 0:
                ext.ghost_timer -= 1
            if ext.speed_timer > 0:
                ext.speed_timer -= 1

            moves = 2 if ext.speed_timer > 0 else 1
            for _ in range(moves):
                head = [ext.body[0][0] + ext.direction[0], ext.body[0][1] + ext.direction[1]]
                ext.body.insert(0, head)

                ate = False
                for a in self.apples[:]:
                    if head == a["pos"]:
                        self._apply_powerup(ext, a["type"])
                        self.apples.remove(a)
                        self._spawn_apple()
                        ate = True
                        break

                if not ate and not should_grow:
                    ext.body.pop()

        # Collision detection
        for p in self.players:
            ext = p.extension
            if not ext.is_alive:
                continue
            head = ext.body[0]

            # Wall collision
            if head[0] < 0 or head[0] >= 800 or head[1] < 0 or head[1] >= 600:
                ext.is_alive = False
                continue

            # Body collision (skip if ghost)
            if ext.ghost_timer <= 0:
                for other in self.players:
                    for i, seg in enumerate(other.extension.body):
                        if p == other and i == 0:
                            continue
                        if head == seg:
                            ext.is_alive = False
                            break
                    if not ext.is_alive:
                        break

        alive_count = sum(1 for p in self.players if p.extension.is_alive)
        if alive_count <= 1 and len(self.players) > 1:
            self._done = True

    def _apply_powerup(self, ext, apple_type):
        if apple_type == "gold":
            new_segments = [list(s) for s in ext.body]
            ext.body.extend(new_segments)
        elif apple_type == "white":
            ext.ghost_timer = 80
        elif apple_type == "blue":
            ext.speed_timer = 30

    # ── Sync state ────────────────────────────────────────────────────────────

    def get_sync_state(self) -> dict:
        return {
            "apples": self.apples,
            "players": {p.player_id: p.extension.to_dict() for p in self.players},
            "floating_messages": self.floating_messages,
            "done": self.done,
            "last_growth_time": self.last_growth_time,
        }

    def apply_sync_state(self, state):
        self.apples = state.get("apples", [])
        self.floating_messages = state.get("floating_messages", [])
        self.done = state.get("done", False)
        self.last_growth_time = state.get("last_growth_time", self.last_growth_time)
        p_data = state.get("players", {})
        for p in self.players:
            if p.player_id in p_data:
                p.extension.from_dict(p_data[p.player_id])

    # ── Results / keybindings ─────────────────────────────────────────────────

    def get_results(self) -> dict[str, int]:
        results = {}
        survivors = [p for p in self.players if p.extension.is_alive]
        for p in self.players:
            results[p.player_id] = len(survivors) if p in survivors else 0
        return results

    def get_keybindings(self) -> dict[str, str]:
        return {"WASD": "Steer your snake"}

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, surface):
        surface.fill((20, 20, 20))

        for x in range(0, 800, self.GRID_SIZE):
            pygame.draw.line(surface, (40, 40, 40), (x, 0), (x, 600))
        for y in range(0, 600, self.GRID_SIZE):
            pygame.draw.line(surface, (40, 40, 40), (0, y), (800, y))

        for a in self.apples:
            if a["type"] == "red":
                color = (255, 0, 0)
            elif a["type"] == "gold":
                color = (255, 215, 0)
            elif a["type"] == "white":
                color = (255, 255, 255)
            else:
                color = (0, 150, 255)
            pygame.draw.rect(surface, color, (a["pos"][0] + 1, a["pos"][1] + 1, 18, 18))

        for p in self.players:
            ext = p.extension
            if not ext.body:
                continue

            if ext.ghost_timer > 0:
                if ext.ghost_timer < 30 and ext.ghost_timer % 4 < 2:
                    color = p.color
                else:
                    color = (255, 255, 255)
            elif not ext.is_alive:
                color = (100, 100, 100)
            else:
                color = p.color

            for seg in ext.body:
                pygame.draw.rect(surface, color, (seg[0], seg[1], 18, 18))

        font = pygame.font.SysFont(None, 36)
        current_time = pygame.time.get_ticks() if hasattr(pygame, 'time') else 0
        time_left = max(0, (self.GROW_INTERVAL - (current_time - self.last_growth_time)) // 1000)
        timer_text = font.render(f"Groei over: {time_left + 1}s", True, (255, 255, 255))
        surface.blit(timer_text, (400 - 50, 10))