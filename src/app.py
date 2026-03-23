from __future__ import annotations
import random
import sys

import pygame

from network.client import Client
from network.messages import MsgType
from session.lobby import Lobby
from session.playlist import GamePlaylist, PlaylistMode
from engine.game_engine import GameEngine
from abstract.player import Player
from minigames.snake.snake_game import SnakeGame

from constants import W, H, FPS, COLORS, GAME_REGISTRY
from screens import MenuScreen, LobbyScreen, GameSelectionScreen, ResultsScreen


class App:
    def __init__(self, server_host: str, server_port: int) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("MiniParty")
        self.clock = pygame.time.Clock()

        self.font_lg = pygame.font.SysFont("monospace", 32, bold=True)
        self.font_sm = pygame.font.SysFont("monospace", 18)

        self.client    = Client()
        self.my_color  = random.choice(COLORS)
        self.my_player: Player | None       = None
        self.lobby:     Lobby  | None       = None
        self.playlist:  GamePlaylist | None = None   # built after host confirms selection
        self.engine:    GameEngine          = GameEngine(self.screen)
        self.engine.set_sync_callback(self._on_sync_out)
        self._is_host: bool = False   # set when lobby state arrives

        self._state = "menu"   # menu | lobby | selection | controls | game | results | gameover

        self.menu_screen      = MenuScreen(self.font_lg, self.font_sm, self.my_color)
        self.lobby_screen     = LobbyScreen(self.font_lg, self.font_sm)
        self.selection_screen = GameSelectionScreen(self.font_lg, self.font_sm)
        self.results_screen   = ResultsScreen(self.font_lg, self.font_sm)
        self._controls_game:  type | None = None
        self._controls_timer  = 4.0

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
            self.lobby = Lobby(payload["code"])

        self.lobby.code  = payload["code"]
        players_data     = payload.get("players", [])

        self.lobby.players = [Player.from_dict(d) for d in players_data]

        if self.my_player is None and self.lobby.players:
            for p in self.lobby.players:
                if p.name == self.menu_screen.name_text.strip():
                    self.my_player = p
                    break

        self.lobby_screen.code    = self.lobby.code
        self.lobby_screen.players = players_data
        self.lobby_screen.is_host = any(
            d.get("is_host") and d.get("name") == self.menu_screen.name_text.strip()
            for d in players_data
        )
        self._is_host = self.lobby_screen.is_host
        if self._state == "menu":
            self._state = "lobby"

    def _on_game_start(self, payload: dict) -> None:
        game_key     = payload.get("game", "bomb").lower()
        players_data = payload.get("players", [])

        players = [Player.from_dict(d) for d in players_data]

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
        if self._state == "game":
            self.engine.apply_network_state(payload)

    def _on_input(self, payload: dict) -> None:
        if self._state == "game":
            player_id = payload.pop("player_id", "")
            self.engine.apply_network_input(player_id, payload)

    def _on_sync_out(self, data: dict) -> None:
        msg_type_tag = data.pop("_type", "state")
        if msg_type_tag == "state":
            self.client.send(MsgType.GAME_STATE, data)
        else:
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
                self.lobby_screen.action = None
                if self._is_host:
                    self.selection_screen.action = None
                    self._state = "selection"
                # Non-hosts do nothing — they wait for GAME_START from server

        elif self._state == "selection":
            for e in events:
                self.selection_screen.handle_event(e)
            if self.selection_screen.action == "confirm":
                self.selection_screen.action = None
                selected = self.selection_screen.get_selected_classes()
                self.playlist = GamePlaylist(
                    games=selected,
                    mode=PlaylistMode.RANDOM_NO_REPEAT,
                    max_rounds=len(selected),
                )
                self.client.start_game()
                self._state = "lobby"   # wait for GAME_START broadcast from server

        elif self._state == "controls":
            self._controls_timer -= dt
            if self._controls_timer <= 0:
                self._state = "game"
                self._first_game_frame = True

        elif self._state == "game":
            safe_dt = 0.016 if getattr(self, "_first_game_frame", False) else dt
            self._first_game_frame = False
            still_running = self.engine.tick(events, safe_dt)
            if not still_running:
                if self.engine.game and self.lobby:
                    results = self.engine.game.get_results()
                    for p in (self.engine.game.players or []):
                        pts = results.get(p.player_id, 0)
                        p.stars += pts
                        for lp in self.lobby.players:
                            if lp.player_id == p.player_id:
                                lp.stars = p.stars
                self.results_screen.players = self.engine.game.players if self.engine.game else []
                self.results_screen._timer  = 5.0
                self._state = "results"

        elif self._state == "results":
            done = self.results_screen.update(dt)
            if done:
                if self.playlist and self.playlist.has_next():
                    self._state = "lobby"
                else:
                    self._state = "gameover"

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self, events: list[pygame.event.Event]) -> None:
        if self._state == "menu":
            self.menu_screen.draw(self.screen)

        elif self._state == "lobby":
            self.lobby_screen.draw(self.screen)

        elif self._state == "selection":
            self.selection_screen.draw(self.screen)

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