import pygame

from ..constants import W, GAME_REGISTRY
from ..ui_helpers import draw_rect_button


class GameSelectionScreen:
    """Host picks which minigames go into the playlist before starting."""

    _LABELS: dict[str, str] = {
        "bomb":            "💣  Bomb Pass",
        "dkcounting":      "🦍  DK Counting",
        "snake":           "🐍  Snake",
        "avoid_fireballs": "🔥  Avoid Fireballs",
        "pong":            "🏓  Ping-Pong",
        "goomba_counting": "👾  Goomba Counting",
    }

    def __init__(self, font_lg: pygame.font.Font, font_sm: pygame.font.Font) -> None:
        self.font_lg  = font_lg
        self.font_sm  = font_sm
        # All games ticked by default
        self.selected: dict[str, bool] = {k: True for k in GAME_REGISTRY}
        self.action: str | None = None   # "confirm"

        keys = list(GAME_REGISTRY)
        self._boxes: dict[str, pygame.Rect] = {
            k: pygame.Rect(200, 150 + i * 52, 22, 22)
            for i, k in enumerate(keys)
        }
        self.btn_confirm = pygame.Rect(300, 510, 200, 48)
        self.btn_all     = pygame.Rect(100, 510, 130, 48)

    # ── input ─────────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN:
            return
        pos = event.pos

        # Toggle individual rows (wide hit-area covers label too)
        for key, box in self._boxes.items():
            row_rect = pygame.Rect(box.x - 8, box.y - 12, 420, 46)
            if row_rect.collidepoint(pos):
                self.selected[key] = not self.selected[key]
                return

        # "All / None" toggle button
        if self.btn_all.collidepoint(pos):
            new_val = not all(self.selected.values())
            self.selected = {k: new_val for k in self.selected}
            return

        # Confirm button — requires ≥1 selection
        if self.btn_confirm.collidepoint(pos) and any(self.selected.values()):
            self.action = "confirm"

    # ── helpers ───────────────────────────────────────────────────────────────

    def get_selected_classes(self) -> list[type]:
        return [cls for k, cls in GAME_REGISTRY.items() if self.selected[k]]

    # ── draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 12, 30))

        title = self.font_lg.render("Select Minigames", True, (200, 200, 255))
        surface.blit(title, title.get_rect(centerx=W // 2, y=55))

        sub = self.font_sm.render("(host only — choose which games to play)", True, (80, 90, 120))
        surface.blit(sub, sub.get_rect(centerx=W // 2, y=102))

        for key, box in self._boxes.items():
            checked = self.selected[key]

            # Checkbox fill
            fill   = (50, 180, 100) if checked else (20, 24, 48)
            border = (90, 210, 130) if checked else (60, 80, 120)
            pygame.draw.rect(surface, fill,   box, border_radius=4)
            pygame.draw.rect(surface, border, box, 2, border_radius=4)

            # Checkmark
            if checked:
                cx, cy = box.centerx, box.centery
                pygame.draw.line(surface, (255, 255, 255),
                                 (cx - 5, cy),     (cx - 1, cy + 4), 2)
                pygame.draw.line(surface, (255, 255, 255),
                                 (cx - 1, cy + 4), (cx + 6, cy - 4), 2)

            # Label
            label_text = self._LABELS.get(key, key.replace("_", " ").title())
            color = (210, 225, 245) if checked else (80, 95, 120)
            lbl = self.font_sm.render(label_text, True, color)
            surface.blit(lbl, (box.right + 18,
                               box.y + (box.height - lbl.get_height()) // 2))

        # Buttons
        mx, my = pygame.mouse.get_pos()
        all_on = all(self.selected.values())
        draw_rect_button(surface, self.btn_all,
                         "None" if all_on else "All",
                         self.font_sm, self.btn_all.collidepoint(mx, my))

        if any(self.selected.values()):
            draw_rect_button(surface, self.btn_confirm, "▶  Start!",
                             self.font_sm, self.btn_confirm.collidepoint(mx, my))
        else:
            # Grey-out disabled state
            pygame.draw.rect(surface, (35, 42, 68), self.btn_confirm, border_radius=8)
            pygame.draw.rect(surface, (55, 65, 95), self.btn_confirm, 2, border_radius=8)
            lbl = self.font_sm.render("▶  Start!", True, (70, 80, 110))
            surface.blit(lbl, lbl.get_rect(center=self.btn_confirm.center))

            warn = self.font_sm.render("Select at least one game", True, (200, 80, 80))
            surface.blit(warn, warn.get_rect(centerx=W // 2, y=470))

        count = sum(self.selected.values())
        info = self.font_sm.render(
            f"{count} game{'s' if count != 1 else ''} selected",
            True, (100, 115, 150))
        surface.blit(info, info.get_rect(centerx=W // 2, y=572))