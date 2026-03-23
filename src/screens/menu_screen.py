import pygame

from src.constants import W
from src.ui_helpers import draw_rect_button, draw_input_box


class MenuScreen:
    """Name entry + Create / Join buttons."""

    def __init__(self, font_lg: pygame.font.Font, font_sm: pygame.font.Font, my_color: tuple) -> None:
        self.font_lg   = font_lg
        self.font_sm   = font_sm
        self.my_color  = my_color
        self.name_text = ""
        self.code_text = ""
        self.active    = "name"   # which input is focused

        self.rect_name  = pygame.Rect(220, 160, 360, 44)
        self.rect_code  = pygame.Rect(220, 260, 360, 44)
        self.btn_create = pygame.Rect(160, 360, 200, 50)
        self.btn_join   = pygame.Rect(440, 360, 200, 50)

        self.action = None   # "create" | "join" | None
        self.error  = ""

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect_name.collidepoint(event.pos):
                self.active = "name"
            elif self.rect_code.collidepoint(event.pos):
                self.active = "code"
            elif self.btn_create.collidepoint(event.pos) and self.name_text.strip():
                self.action = "create"
            elif (self.btn_join.collidepoint(event.pos)
                  and self.name_text.strip()
                  and self.code_text.strip()):
                self.action = "join"

        if event.type == pygame.KEYDOWN:
            target = "name" if self.active == "name" else "code"
            if event.key == pygame.K_BACKSPACE:
                if target == "name": self.name_text = self.name_text[:-1]
                else:                self.code_text = self.code_text[:-1]
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