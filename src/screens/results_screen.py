import pygame

from src.constants import W
from src.abstract.player import Player


class ResultsScreen:
    """End-of-round star tally — shown for 5 seconds then continues."""

    def __init__(self, font_lg: pygame.font.Font, font_sm: pygame.font.Font) -> None:
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