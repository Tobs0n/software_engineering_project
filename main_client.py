"""
Run one instance per player.

    python main_client.py
    python main_client.py --host 192.168.1.5 --port 5555
"""
from __future__ import annotations
import sys
import argparse
import random
import pygame

from src.network.client import Client
from src.network.messages import MsgType
from src.session.lobby import Lobby
from src.session.playlist import GamePlaylist, PlaylistMode
from src.session.lobby_state import LobbyState
from src.engine.game_engine import GameEngine
from src.abstract.player import Player
from src.minigames.bomb.bomb_game import BombGame
from src.minigames.snake.snake_game import SnakeGame


# ── Registry: add new minigames here ─────────────────────────────────────────
GAME_REGISTRY: dict[str, type] = {
    # "bomb":        BombGame,
    # "bombgame":       BombGame,
    "snake":       SnakeGame,
}


W, H   = 800, 600
FPS    = 60
COLORS = [
    (255, 80,  80),
    (80,  160, 255),
    (80,  220, 100),
    (255, 200, 50),
    (200, 80,  220),
    (255, 140, 30),
]


# ── Tiny UI helpers ───────────────────────────────────────────────────────────

def draw_rect_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    font: pygame.font.Font,
    hover: bool = False,
) -> None:
    color  = (80, 130, 200) if hover else (50, 90, 160)
    border = (160, 200, 255) if hover else (100, 140, 220)
    pygame.draw.rect(surface, color,  rect, border_radius=8)
    pygame.draw.rect(surface, border, rect, 2, border_radius=8)
    lbl = font.render(text, True, (240, 240, 255))
    surface.blit(lbl, lbl.get_rect(center=rect.center))


def draw_input_box(
    surface: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    font: pygame.font.Font,
    active: bool,
    label: str = "",
) -> None:
    border = (120, 180, 255) if active else (80, 100, 140)
    pygame.draw.rect(surface, (20, 25, 50), rect, border_radius=6)
    pygame.draw.rect(surface, border,       rect, 2, border_radius=6)
    lbl  = font.render(text + ("|" if active else ""), True, (230, 230, 255))
    surface.blit(lbl, (rect.x + 10, rect.y + (rect.height - lbl.get_height()) // 2))
    if label:
        hint = font.render(label, True, (130, 140, 160))
        surface.blit(hint, (rect.x, rect.y - 22))


# ── Screens ───────────────────────────────────────────────────────────────────

class MenuScreen:
    """Name entry + Create / Join buttons."""

    def __init__(self, font_lg, font_sm, my_color):
        self.font_lg    = font_lg
        self.font_sm    = font_sm
        self.my_color   = my_color
        self.name_text  = ""
        self.code_text  = ""
        self.active     = "name"   # which input is focused

        self.rect_name  = pygame.Rect(220, 160, 360, 44)
        self.rect_code  = pygame.Rect(220, 260, 360, 44)
        self.btn_create = pygame.Rect(160, 360, 200, 50)
        self.btn_join   = pygame.Rect(440, 360, 200, 50)

        self.action     = None   # "create" | "join" | None
        self.error      = ""

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect_name.collidepoint(event.pos): self.active = "name"
            elif self.rect_code.collidepoint(event.pos): self.active = "code"
            elif self.btn_create.collidepoint(event.pos) and self.name_text.strip():
                self.action = "create"
            elif self.btn_join.collidepoint(event.pos) and self.name_text.strip() and self.code_text.strip():
                self.action = "join"

        if event.type == pygame.KEYDOWN:
            target = "name" if self.active == "name" else "code"
            if event.key == pygame.K_BACKSPACE:
                if target == "name":  self.name_text = self.name_text[:-1]
                else:                 self.code_text = self.code_text[:-1]
            elif event.key == pygame.K_TAB:
                self.active = "code" if self.active == "name" else "name"
            elif event.key == pygame.K_RETURN:
                if self.name_text.strip() and self.code_text.strip():
                    self.action = "join"
                elif self.name_text.strip():
                    self.action = "create"
            elif event.unicode.isprintable():
                if target == "name" and len(self.name_text) < 16:
                    self.name_text += event.unicode
                elif target == "code" and len(self.code_text) < 5:
                    self.code_text += event.unicode.upper()

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 12, 30))
        title = self.font_lg.render("🎮  MiniParty", True, (200, 200, 255))
        surface.blit(title, title.get_rect(centerx=W // 2, y=60))

        mx, my = pygame.mouse.get_pos()
        draw_input_box(surface, self.rect_name, self.name_text, self.font_sm,
                       self.active == "name", "Your name")
        draw_input_box(surface, self.rect_code, self.code_text, self.font_sm,
                       self.active == "code", "Lobby code  (leave blank to create)")

        draw_rect_button(surface, self.btn_create, "Create lobby",
                         self.font_sm, self.btn_create.collidepoint(mx, my))
        draw_rect_button(surface, self.btn_join,   "Join lobby",
                         self.font_sm, self.btn_join.collidepoint(mx, my))

        if self.error:
            err = self.font_sm.render(self.error, True, (255, 90, 90))
            surface.blit(err, err.get_rect(centerx=W // 2, y=440))

        # Color swatch
        pygame.draw.circle(surface, self.my_color, (W // 2, 510), 18)
        hint = self.font_sm.render("your colour", True, (100, 110, 140))
        surface.blit(hint, hint.get_rect(centerx=W // 2, y=536))


class LobbyScreen:
    """Waiting room — shows player list, host sees Start button."""

    def __init__(self, font_lg, font_sm):
        self.font_lg    = font_lg
        self.font_sm    = font_sm
        self.players:   list[dict] = []
        self.code:      str        = ""
        self.is_host:   bool       = False
        self.btn_start  = pygame.Rect(300, 500, 200, 50)
        self.action     = None

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.is_host and self.btn_start.collidepoint(event.pos):
                self.action = "start"

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 12, 30))
        code_lbl = self.font_lg.render(f"Lobby  {self.code}", True, (160, 210, 255))
        surface.blit(code_lbl, code_lbl.get_rect(centerx=W // 2, y=40))

        hint = self.font_sm.render("Share this code with friends", True, (90, 100, 130))
        surface.blit(hint, hint.get_rect(centerx=W // 2, y=90))

        for i, pdata in enumerate(self.players):
            color = tuple(pdata.get("color", [200, 200, 200]))
            name  = pdata.get("name", "?")
            stars = pdata.get("stars", 0)
            host  = "  👑" if pdata.get("is_host") else ""
            pygame.draw.circle(surface, color, (160, 160 + i * 52), 16)
            row = self.font_sm.render(f"{name}{host}   ★ {stars}", True, color)
            surface.blit(row, (190, 152 + i * 52))

        if self.is_host:
            mx, my = pygame.mouse.get_pos()
            draw_rect_button(surface, self.btn_start, "▶  Start game",
                             self.font_sm, self.btn_start.collidepoint(mx, my))
        else:
            w8 = self.font_sm.render("Waiting for host to start …", True, (120, 130, 160))
            surface.blit(w8, w8.get_rect(centerx=W // 2, y=520))


class ResultsScreen:
    """End-of-round star tally — shown for 5 seconds then continues."""

    def __init__(self, font_lg, font_sm):
        self.font_lg  = font_lg
        self.font_sm  = font_sm
        self.players: list[Player] = []
        self._timer   = 5.0

    def update(self, dt: float) -> bool:
        """Returns True when it's time to move on."""
        self._timer -= dt
        return self._timer <= 0

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 12, 30))
        title = self.font_lg.render("Round over!", True, (255, 220, 60))
        surface.blit(title, title.get_rect(centerx=W // 2, y=80))

        ranked = sorted(self.players, key=lambda p: p.stars, reverse=True)
        for i, player in enumerate(ranked):
            color = player.color
            row   = self.font_sm.render(
                f"#{i+1}   {player.name}   ★ {player.stars}", True, color)
            surface.blit(row, row.get_rect(centerx=W // 2, y=180 + i * 50))

        secs = self.font_sm.render(
            f"Next game in {max(0, int(self._timer))}s …", True, (100, 110, 140))
        surface.blit(secs, secs.get_rect(centerx=W // 2, y=520))


# ── Main app ──────────────────────────────────────────────────────────────────

class App:
    def __init__(self, server_host: str, server_port: int):
        pygame.init()
        self.screen    = pygame.display.set_mode((W, H))
        pygame.display.set_caption("MiniParty")
        self.clock     = pygame.time.Clock()

        self.font_lg   = pygame.font.SysFont("monospace", 32, bold=True)
        self.font_sm   = pygame.font.SysFont("monospace", 18)

        self.client    = Client()
        self.my_color  = random.choice(COLORS)
        self.my_player: Player | None = None
        self.lobby:     Lobby | None  = None
        self.engine:    GameEngine    = GameEngine(self.screen)
        self.engine.set_sync_callback(self._on_sync_out)
        self._is_host: bool = False   # set when lobby state arrives

        self._state = "menu"   # menu | lobby | controls | game | results | gameover

        self.menu_screen    = MenuScreen(self.font_lg, self.font_sm, self.my_color)
        self.lobby_screen   = LobbyScreen(self.font_lg, self.font_sm)
        self.results_screen = ResultsScreen(self.font_lg, self.font_sm)
        self._controls_game: type | None = None
        self._controls_timer = 4.0

        self.playlist = GamePlaylist(
            games=[BombGame],
            mode=PlaylistMode.RANDOM_NO_REPEAT,
            max_rounds=6,
        )

        self.client.connect(server_host, server_port)

    def run(self) -> None:
        while True:
            dt     = self.clock.tick(FPS) / 1000.0
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            self._process_network()
            self._update(events, dt)
            self._draw(events)
            pygame.display.flip()

    # ── Network message processing ────────────────────────────────────────────

    def _process_network(self) -> None:
        for msg_type, payload in self.client.poll():
            if   msg_type == MsgType.LOBBY_STATE: self._on_lobby_state(payload)
            elif msg_type == MsgType.GAME_START:  self._on_game_start(payload)
            elif msg_type == MsgType.GAME_STATE:  self._on_game_state(payload)
            elif msg_type == MsgType.INPUT:       self._on_input(payload)
            elif msg_type == MsgType.ERROR:
                self.menu_screen.error = payload.get("message", "Error")

    def _on_lobby_state(self, payload: dict) -> None:
        if self.lobby is None:
            from src.session.lobby import Lobby
            self.lobby = Lobby(payload["code"])

        self.lobby.code = payload["code"]
        players_data    = payload.get("players", [])

        # Rebuild player list from server data
        self.lobby.players = [Player.from_dict(d) for d in players_data]

        # Find our local Player object (match by name + is_host heuristic)
        if self.my_player is None and self.lobby.players:
            # The server assigns us as the first player with our name
            for p in self.lobby.players:
                if p.name == self.menu_screen.name_text.strip():
                    self.my_player = p
                    break

        self.lobby_screen.code     = self.lobby.code
        self.lobby_screen.players  = players_data
        self.lobby_screen.is_host  = any(
            d.get("is_host") and d.get("name") == self.menu_screen.name_text.strip()
            for d in players_data
        )
        self._is_host = self.lobby_screen.is_host
        if self._state == "menu":
            self._state = "lobby"

    def _on_game_start(self, payload: dict) -> None:
        game_key     = payload.get("game", "bomb").lower()
        players_data = payload.get("players", [])

        # Rebuild players with server-assigned IDs
        players = [Player.from_dict(d) for d in players_data]

        # Identify our player
        my_name = self.menu_screen.name_text.strip()
        for p in players:
            if p.name == my_name:
                self.my_player = p
                break

        # Put our player first so the engine assigns local input to us
        players.sort(key=lambda p: (0 if p.name == my_name else 1))

        game_cls = GAME_REGISTRY.get(game_key, SnakeGame)
        game     = game_cls()
        self.engine.load_game(game, players, is_authority=self._is_host)

        self._controls_game  = game_cls
        self._controls_timer = 4.0
        self._state          = "controls"

    def _on_game_state(self, payload: dict) -> None:
        """
        [PEER] Received from authority via server relay.
        Forward to engine which calls game.apply_sync_state().
        Only meaningful while a game is running.
        """
        if self._state == "game":
            self.engine.apply_network_state(payload)

    def _on_input(self, payload: dict) -> None:
        """
        [AUTHORITY] A peer's input arrived via server relay.
        Forward to engine which calls game.on_input_received().
        """
        if self._state == "game":
            player_id = payload.pop("player_id", "")
            self.engine.apply_network_input(player_id, payload)

    def _on_sync_out(self, data: dict) -> None:
        """
        Called by Game._broadcast_state() (authority) and Game._send_input() (peer).
        The Game base class tags the dict with _type='state' or _type='input'.
        We route to the correct network message accordingly.
        """
        msg_type_tag = data.pop("_type", "state")
        if msg_type_tag == "state":
            # Authority pushing state to all peers
            self.client.send(MsgType.GAME_STATE, data)
        else:
            # Peer sending input to authority
            self.client.send(MsgType.INPUT, data)

    # ── Per-frame update ──────────────────────────────────────────────────────

    def _update(self, events: list[pygame.event.Event], dt: float) -> None:
        if self._state == "menu":
            for e in events:
                self.menu_screen.handle_event(e)
            if self.menu_screen.action == "create":
                self.client.create_lobby(
                    self.menu_screen.name_text.strip(), self.my_color)
                self.menu_screen.action = None
            elif self.menu_screen.action == "join":
                self.client.join_lobby(
                    self.menu_screen.code_text.strip(),
                    self.menu_screen.name_text.strip(),
                    self.my_color,
                )
                self.menu_screen.action = None

        elif self._state == "lobby":
            for e in events:
                self.lobby_screen.handle_event(e)
            if self.lobby_screen.action == "start":
                self.client.start_game()
                self.lobby_screen.action = None

        elif self._state == "controls":
            self._controls_timer -= dt
            if self._controls_timer <= 0:
                self._state = "game"
                self._first_game_frame = True   # flag: cap dt on entry

        elif self._state == "game":
            # Cap dt on the first frame to avoid the transition spike
            safe_dt = 0.016 if getattr(self, "_first_game_frame", False) else dt
            self._first_game_frame = False
            still_running = self.engine.tick(events, safe_dt)
            if not still_running:
                # Collect results, award stars
                if self.engine.game and self.lobby:
                    results = self.engine.game.get_results()
                    # Sync stars back to lobby players
                    for p in (self.engine.game.players or []):
                        pts = results.get(p.player_id, 0)
                        p.stars += pts
                        if self.lobby:
                            for lp in self.lobby.players:
                                if lp.player_id == p.player_id:
                                    lp.stars = p.stars
                self.results_screen.players = self.engine.game.players if self.engine.game else []
                self.results_screen._timer  = 5.0
                self._state = "results"

        elif self._state == "results":
            done = self.results_screen.update(dt)
            if done:
                if self.playlist.has_next():
                    self._state = "lobby"
                else:
                    self._state = "gameover"

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self, events: list[pygame.event.Event]) -> None:
        if self._state == "menu":
            self.menu_screen.draw(self.screen)

        elif self._state == "lobby":
            self.lobby_screen.draw(self.screen)

        elif self._state == "controls":
            self._draw_controls()

        elif self._state == "game":
            pass   # engine.tick() already rendered

        elif self._state == "results":
            self.results_screen.draw(self.screen)

        elif self._state == "gameover":
            self._draw_gameover()

    def _draw_controls(self) -> None:
        self.screen.fill((8, 10, 24))
        title = self.font_lg.render("Controls", True, (200, 200, 255))
        self.screen.blit(title, title.get_rect(centerx=W // 2, y=80))

        if self.engine.game:
            bindings = self.engine.game.get_keybindings()
            for i, (key, action) in enumerate(bindings.items()):
                row = self.font_sm.render(f"{key:>12}   {action}", True, (190, 200, 220))
                self.screen.blit(row, row.get_rect(centerx=W // 2, y=200 + i * 42))

        secs = self.font_sm.render(
            f"Starting in {max(0, int(self._controls_timer))}s …", True, (90, 100, 130))
        self.screen.blit(secs, secs.get_rect(centerx=W // 2, y=520))

    def _draw_gameover(self) -> None:
        self.screen.fill((8, 10, 24))
        title = self.font_lg.render("Game Over!", True, (255, 200, 50))
        self.screen.blit(title, title.get_rect(centerx=W // 2, y=80))

        players = []
        if self.engine.game:
            players = self.engine.game.players or []
        elif self.lobby:
            players = self.lobby.players

        ranked = sorted(players, key=lambda p: p.stars, reverse=True)
        for i, player in enumerate(ranked):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"
            row   = self.font_sm.render(
                f"{medal}  {player.name}   ★ {player.stars}", True, player.color)
            self.screen.blit(row, row.get_rect(centerx=W // 2, y=200 + i * 52))

        hint = self.font_sm.render("Close the window to exit.", True, (80, 90, 110))
        self.screen.blit(hint, hint.get_rect(centerx=W // 2, y=540))


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MiniParty Client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()

    App(args.host, args.port).run()


if __name__ == "__main__":
    main()
