import os
import random
import pygame
from ...abstract.game import Game
from ...engine.world_config import WorldConfig
from .dk_counting_extension import DKCountingExtension


class DKCountingGame(Game):
    """Donkey Kong counting minigame.

    This game is based on `counting game` folder's TimingGame implementation.

    - Authority (host) drives the state machine and scoring.
    - Peers send a single input ("press") when they want to stop the timer.
    - All game state is synced via get_sync_state / apply_sync_state.
    """

    # State timings (seconds)
    WELKOM_SECS = 8.0
    UITLEG_SECS = 8.0
    UITLEG2_SECS = 5.0
    BEREKENEN_SECS = 8.0

    def __init__(self):
        super().__init__()

        # [AUTHORITY] game state
        self.state: str = "BOSJES"
        self.state_start_time: int = 0
        self.target_time: int = 0
        self.start_ticks: int = 0
        self.results: dict[str, float] = {}

        # [LOCAL] cached rendering assets (same on all clients)
        self.images_data: dict = {}
        self.orig_text_box: dict = {}
        self.font: pygame.font.Font | None = None

        # [LOCAL] (per-frame)
        self._loaded_assets: bool = False

    # ── Abstract contract ─────────────────────────────────────────────────────

    def get_world_config(self) -> WorldConfig:
        return WorldConfig(gravity=0.0, has_physics=False, bounds=(0, 0, 1024, 768))

    def create_extension(self, player) -> DKCountingExtension:
        return DKCountingExtension(player)

    def setup(self):
        # Load assets once (works on both host and peers)
        self._load_assets()

        if self.is_authority:
            self.state = "BOSJES"
            self.state_start_time = pygame.time.get_ticks()
            self.target_time = random.randint(10, 30)
            self.start_ticks = 0
            self.results = {}
            for p in self.players:
                p.extension.reset()

            # Immediately sync initial state
            self._broadcast_state()

    def _load_assets(self):
        if self._loaded_assets:
            return
        self._loaded_assets = True

        # Assets are bundled in the local assets folder within the minigame package
        path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "assets")
        )

        filenames = [
            "Counter-verstopt-in-de-bosjes.png",
            "Counter-welkom.png",
            "Counter-spelregels-uitleggen.png",
            "Counter-aan-het-slapen.png",
            "Counter-tromgeroffel.png",
            "Counter-berekenen.png",
            "Counter-winnaar-bekend-maken.png",
        ]

        # Load font
        font_path = os.path.join(path, "Galindo-Regular.ttf")
        self.font = pygame.font.Font(font_path, 30)

        # Load images and scale to screen
        screen_w, screen_h = pygame.display.get_surface().get_size()
        for f in filenames:
            full_path = os.path.join(path, f)
            img = pygame.image.load(full_path).convert_alpha()
            orig_size = img.get_size()
            scale_x = screen_w / orig_size[0]
            scale_y = screen_h / orig_size[1]
            scale = min(scale_x, scale_y)
            final_size = (int(orig_size[0] * scale), int(orig_size[1] * scale))
            img = pygame.transform.smoothscale(img, final_size)
            self.images_data[f] = {
                "image": img,
                "pos": (screen_w // 2 - final_size[0] // 2, screen_h // 2 - final_size[1] // 2),
                "scale": scale,
                "orig_size": orig_size,
            }

        self.orig_text_box = {
            "Counter-verstopt-in-de-bosjes.png": {'top_left': (1500, 180), 'size': (1000, 220)},
            "Counter-welkom.png":               {'top_left': (1500, 180), 'size': (1000, 220)},
            "Counter-spelregels-uitleggen.png": {'top_left': (1500, 180), 'size': (1000, 225)},
            "Counter-aan-het-slapen.png":       {'top_left': (1500, 180), 'size': (1000, 200)},
            "Counter-tromgeroffel.png":         {'top_left': (1500, 180), 'size': (1000, 220)},
            "Counter-berekenen.png":           {'top_left': (1500, 180), 'size': (1000, 220)},
            "Counter-winnaar-bekend-maken.png": {'top_left': (1500, 180), 'size': (1000, 220)},
        }

    def _wrap_text(self, text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        words = text.split(" ")
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            current.append(word)
            test = " ".join(current)
            if font.size(test)[0] > max_width:
                current.pop()
                lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
        return lines

    # ── Game logic ────────────────────────────────────────────────────────────

    def update(self, events, dt):
        if self.is_authority:
            self._update_authority(events, dt)
        else:
            self._update_peer(events, dt)

    def _update_authority(self, events, dt):
        # State machine transitions
        now = pygame.time.get_ticks()
        elapsed = (now - self.state_start_time) / 1000.0

        if self.state == "BOSJES":
            # Wait for any player to press space
            for e in events:
                if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                    self._change_state("WELKOM")
                    break

        elif self.state == "WELKOM":
            if elapsed > self.WELKOM_SECS:
                self._change_state("UITLEG")

        elif self.state == "UITLEG":
            if elapsed > self.UITLEG_SECS:
                self._change_state("UITLEG2")

        elif self.state == "UITLEG2":
            if elapsed > self.UITLEG2_SECS:
                self._change_state("SLAPEN")
                self.start_ticks = pygame.time.get_ticks()
                for p in self.players:
                    p.extension.reset()
                self.results = {}

        elif self.state == "SLAPEN":
            # Host can press SPACE or ENTER to stop the timer
            for e in events:
                if e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self._register_press(self._local_player())

            if len(self.results) == len(self.players):
                self._change_state("BEREKENEN")

        elif self.state == "BEREKENEN":
            if elapsed > self.BEREKENEN_SECS:
                self._change_state("WINNAAR")

        elif self.state == "WINNAAR":
            # End game after a short display
            if elapsed > 8.0:
                self._done = True

        # Always broadcast authoritative state so peers stay in sync
        self._broadcast_state()

    def _update_peer(self, events, dt):
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_RETURN):
                self._send_input({"action": "press"})

    def _change_state(self, new_state: str):
        self.state = new_state
        self.state_start_time = pygame.time.get_ticks()

    def _local_player(self):
        for p in self.players:
            if p.is_host:
                return p
        return self.players[0] if self.players else None

    def _register_press(self, player):
        if not player or player.player_id in self.results:
            return

        # Compute diff in seconds between target and elapsed time
        now = pygame.time.get_ticks()
        diff = abs(self.target_time - (now - self.start_ticks) / 1000.0)
        self.results[player.player_id] = diff
        player.extension.diff = diff
        player.extension.pressed = True

    def on_input_received(self, player_id: str, data: dict) -> None:
        if not self.is_authority:
            return
        if self.state != "SLAPEN":
            return
        if data.get("action") != "press":
            return

        # Find player and register press
        for p in self.players:
            if p.player_id == player_id:
                self._register_press(p)
                break

    # ── Sync state ────────────────────────────────────────────────────────────

    def get_sync_state(self) -> dict:
        return {
            "state": self.state,
            "state_start_time": self.state_start_time,
            "target_time": self.target_time,
            "start_ticks": self.start_ticks,
            "results": self.results,
            "players": {p.player_id: p.extension.to_dict() for p in self.players},
        }

    def apply_sync_state(self, state):
        self.state = state.get("state", self.state)
        self.state_start_time = state.get("state_start_time", self.state_start_time)
        self.target_time = state.get("target_time", self.target_time)
        self.start_ticks = state.get("start_ticks", self.start_ticks)
        self.results = state.get("results", self.results)

        p_data = state.get("players", {})
        for p in self.players:
            if p.player_id in p_data:
                p.extension.from_dict(p_data[p.player_id])

    # ── Scoring / results ──────────────────────────────────────────────────────

    def get_results(self) -> dict[str, int]:
        # Reward best player with 3 stars, second with 2, third with 1
        sorted_players = sorted(self.results.items(), key=lambda kv: kv[1])
        ranks = {player_id: idx for idx, (player_id, _) in enumerate(sorted_players)}
        out: dict[str, int] = {}
        for p in self.players:
            rank = ranks.get(p.player_id, len(self.players) - 1)
            out[p.player_id] = max(0, 3 - rank)
        return out

    def get_keybindings(self) -> dict[str, str]:
        return {"SPACE / ENTER": "Press to stop the timer"}

    def render(self, surface):
        self._load_assets()

        img_map = {
            "BOSJES": "Counter-verstopt-in-de-bosjes.png",
            "WELKOM": "Counter-welkom.png",
            "UITLEG": "Counter-spelregels-uitleggen.png",
            "UITLEG2": "Counter-spelregels-uitleggen.png",
            "SLAPEN": "Counter-aan-het-slapen.png",
            "BEREKENEN": "Counter-tromgeroffel.png",
            "WINNAAR": "Counter-winnaar-bekend-maken.png",
        }

        current_img_key = img_map.get(self.state, "Counter-welkom.png")
        img_data = self.images_data[current_img_key]
        surface.blit(img_data["image"], img_data["pos"])

        current_text_box = self.orig_text_box.get(current_img_key)
        if current_text_box:
            scale = img_data["scale"]
            offset_x, offset_y = img_data["pos"]
            scr_x = offset_x + current_text_box["top_left"][0] * scale
            scr_y = offset_y + current_text_box["top_left"][1] * scale
            scr_w = current_text_box["size"][0] * scale
            scr_h = current_text_box["size"][1] * scale

            text_str = ""
            if self.state == "BOSJES":
                text_str = "Press SPACE to start the game and reveal your game-host."
            elif self.state == "WELKOM":
                namen = ", ".join(p.name for p in self.players)
                text_str = f"It's me Donkey Kong! Welcome {namen}. Let's play a simple game!"
            elif self.state == "UITLEG":
                text_str = "Count the target seconds in your head. Press SPACE at the perfect moment to win."
            elif self.state == "UITLEG2":
                text_str = f"The target seconds are: {self.target_time}. We begin in 3... 2... 1..."
            elif self.state == "SLAPEN":
                text_str = "COUNT NOW. ZZZzzzzzz..."
            elif self.state == "BEREKENEN":
                text_str = "Hmmm... very interesting. You were all close, but only one of you can win."
            elif self.state == "WINNAAR":
                leaderboard = self.get_leaderboard()
                lines = ["Scores:"]
                for i, (name, diff) in enumerate(leaderboard):
                    pos = i + 1
                    lines.append(f"{pos}. {name} ({self.target_time - diff:.2f}s)")
                text_str = " ".join(lines)

            wrapped = self._wrap_text(text_str, self.font, scr_w)
            line_spacing = -10
            total_height = len(wrapped) * self.font.get_height() + (len(wrapped) - 1) * line_spacing
            y_offset = (scr_h - total_height) // 2
            for line in wrapped:
                txt_surf = self.font.render(line, True, (0, 0, 0))
                centered_x = scr_x + (scr_w - txt_surf.get_width()) // 2
                surface.blit(txt_surf, (centered_x, scr_y + y_offset))
                y_offset += self.font.get_height() + line_spacing

    def get_leaderboard(self):
        return sorted(self.results.items(), key=lambda item: item[1])
