import pygame
from collections import namedtuple

UnitType = namedtuple("UnitType", ["color", "radius"])

GOOMBA = UnitType(color=(139, 90, 43), radius=20)
BUZZY_BEETLE = UnitType(color=(50, 50, 180), radius=15)


class Entity(pygame.sprite.Sprite):
    def __init__(self, speed, position, color, size=20):
        super().__init__()
        self.speed = speed
        self.pos = position
        self.color = color
        self.radius = size

    def move(self):
        self.pos += self.speed

    def is_offscreen(self, width):
        return self.pos.x > width + self.radius

    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.pos.x), int(self.pos.y)), self.radius)

