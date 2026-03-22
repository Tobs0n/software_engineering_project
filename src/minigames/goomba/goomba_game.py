from __future__ import annotations
import random
import pygame

from ...abstract.game import Game
from ...engine.world_config import WorldConfig
from .goomba_player_extension import GoombaExtension

# ── Constants ─────────────────────────────────────────────────────────────────
ROUND_TIME      = 45.0
SYNC_EVERY      = 2    # broadcast authoritative state every N frames (~30 updates/s at 60fps)
SPAWN_INTERVAL  = 45   # frames between spawns (~0.75s at 60fps)
SPAWN_STOP      = 2700 # stop spawning after this many frames (45s * 60fps)

GOOMBA      = {"color": (139, 90, 43),  "radius": 20, "is_goomba": True,  "bounce_chance": 0.3}
DISTRACTORS = [
    {"color": (50,  50, 180), "radius": 15, "is_goomba": False, "bounce_chance": 0.7},  # Buzzy Beetle
    {"color": (100, 10,  30), "radius": 30, "is_goomba": False, "bounce_chance": 0.7},  # Extra distractor
    {"color": (20, 160,  80), "radius": 12, "is_goomba": False, "bounce_chance": 0.7},  # Extra distractor
]

DISTRACTOR_SLOTS_START = 1
DISTRACTOR_SLOTS_END   = 6


class GoombaGame(Game):
    """
    Goomba Counter — players count how many Goombas cross the screen.
    At the end, the player whose count is closest to the real number wins.

    AUTHORITY MODEL SUMMARY
    ───────────────────────
    [AUTHORITY]  self._time_left      - host counts down, synced every SYNC_EVERY frames
    [AUTHORITY]  self._done           - host decides when game ends
    [AUTHORITY]  self._entities       - host spawns/moves all entities, synced every frame
    [AUTHORITY]  self._correct_count  - number of Goombas actually spawned
    [AUTHORITY]  ext.goombacounter    - incremented by authority when it receives "increment" input

    [LOCAL]      nothing; players don't move in this game

    [SHARED]     player.color / name  - set once at game start, never changes
    """

    def __init__(self):
        super().__init__()
        self._font_lg: pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None

        self._time_left:       float      = ROUND_TIME
        self._done:            bool       = False
        self._showing_results: bool       = False
        self._results_timer:   float      = 8.0
        self._frame:           int        = 0
        self._entities:        list[dict] = []
        self._correct_count:   int        = 0

    # ── Game contract ─────────────────────────────────────────────────────────

    def get_world_config(self) -> WorldConfig:
        return WorldConfig(
            gravity=0.0,
            has_physics=False,
            has_collisions=False,
            bounds=(0, 0, 800, 600),
        )

    def get_keybindings(self) -> dict:
        return {"SPACE": "Count +1"}

    def create_extension(self, player) -> GoombaExtension:
        return GoombaExtension(player)

    def setup(self) -> None:
        self._font_lg         = pygame.font.SysFont("monospace", 28, bold=True)
        self._font_sm         = pygame.font.SysFont("monospace", 17)
        self._time_left       = ROUND_TIME
        self._done            = False
        self._showing_results = False
        self._results_timer   = 8.0
        self._frame           = 0
        self._entities        = []
        self._correct_count   = 0

        if self.is_authority:
            self._broadcast_state()

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, events: list[pygame.event.Event], dt: float) -> None:
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

    def _update_authority(self, events, dt: float) -> None:
        self._time_left -= dt
        if self._time_left <= 0:
            self._end_game()
            return

        if self._frame % SPAWN_INTERVAL == 0 and self._frame <= SPAWN_STOP:
            self._spawn_entity()

        self._move_entities()

        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                host = self.players[0]
                if host.extension:
                    host.extension.increment()

        if self._frame % SYNC_EVERY == 0:
            self._broadcast_state()

    def _update_peer(self, events) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                self._send_input({"action": "increment"})

    # ── on_input_received ─────────────────────────────────────────────────────

    def on_input_received(self, player_id: str, input_data: dict) -> None:
        if input_data.get("action") == "increment":
            player = self._player_by_id(player_id)
            if player and player.extension:
                player.extension.increment()

    # ── Sync ──────────────────────────────────────────────────────────────────

    def get_sync_state(self) -> dict:
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
        surface.fill((18, 18, 36))
        pygame.draw.rect(surface, (50, 50, 100), pygame.Rect(0, 0, 800, 600), 4)

        for e in self._entities:
            pygame.draw.circle(
                surface, e["color"],
                (int(e["x"]), int(e["y"])), e["radius"],
            )

        w, h = surface.get_size()
        positions = [
            (0,       h - 40),
            (w - 200, h - 40),
            (0,       30),
            (w - 200, 30),
        ]
        local_id = self.players[0].player_id if self.players else None
        for i, player in enumerate(self.players[:4]):
            if not player.extension:
                continue
            x, y = positions[i]
            if player.player_id == local_id:
                label = f"{player.name}: {player.extension.goombacounter}"
                color = player.color
            else:
                label = player.name
                color = (130, 130, 130)
            lbl = self._font_sm.render(label, True, color)
            surface.blit(lbl, (x, y))

        t_col = (255, 60, 60) if self._time_left < 10 else (220, 220, 255)
        t_lbl = self._font_lg.render(f"{max(0, int(self._time_left))}s", True, t_col)
        surface.blit(t_lbl, (400 - t_lbl.get_width() // 2, 12))

        if self._showing_results:
            self._render_end_overlay(surface)

    # ── Results ───────────────────────────────────────────────────────────────

    def get_results(self) -> dict[str, int]:
        diffs = {
            p.player_id: abs(
                (p.extension.goombacounter if p.extension else 0) - self._correct_count
            )
            for p in self.players
        }
        best = min(diffs.values(), default=0)
        return {pid: (3 if diff == best else 0) for pid, diff in diffs.items()}

    def teardown(self) -> None:
        pass

    # ── Private helpers ───────────────────────────────────────────────────────

    def _spawn_entity(self) -> None:
        elapsed = ROUND_TIME - self._time_left
        t = min(elapsed / ROUND_TIME, 1.0)
        distractor_slots = int(
            DISTRACTOR_SLOTS_START + t * (DISTRACTOR_SLOTS_END - DISTRACTOR_SLOTS_START)
        )

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
        })

    def _move_entities(self) -> None:
        """[AUTHORITY] Advance every entity and remove those that leave the screen."""
        to_remove = []
        for e in self._entities:
            e["x"] += e["vx"]
            e["y"] += e["vy"]

            # Bounce off top/bottom
            if e["y"] + e["radius"] > 600 or e["y"] - e["radius"] < 0:
                e["vy"] *= -1

            # Offscreen check — bounce chance differs per entity type
            if e["x"] > 800 + e["radius"] or e["x"] < -e["radius"]:
                if random.random() < e.get("bounce_chance", 0.5):
                    e["vx"] *= -1
                else:
                    to_remove.append(e)

        for e in to_remove:
            self._entities.remove(e)

    def _end_game(self) -> None:
        self._time_left       = 0
        self._showing_results = True
        self._results_timer   = 8.0
        self._broadcast_state()

    def _player_by_id(self, player_id: str):
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None

    def _render_end_overlay(self, surface: pygame.Surface) -> None:
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