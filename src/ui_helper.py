import pygame


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
    lbl = font.render(text + ("|" if active else ""), True, (230, 230, 255))
    surface.blit(lbl, (rect.x + 10, rect.y + (rect.height - lbl.get_height()) // 2))
    if label:
        hint = font.render(label, True, (130, 140, 160))
        surface.blit(hint, (rect.x, rect.y - 22))