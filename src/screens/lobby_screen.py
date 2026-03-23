import pygame

from src.constants import W
from src.ui_helpers import draw_rect_button


class LobbyScreen:
    """Waiting room — shows player list, host sees Start button."""

    def __init__(self, font_lg: pygame.font.Font, font_sm: pygame.font.Font) -> None:
        self.font_lg   = font_lg
        self.font_sm   = font_sm
        self.players:  list[dict] = []
        self.code:     str        = ""
        self.is_host:  bool       = False
        self.btn_start = pygame.Rect(300, 500, 200, 50)
        self.action    = None

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