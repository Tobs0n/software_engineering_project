import pygame
from collections import namedtuple

UnitType = namedtuple("UnitType", ["color", "radius"])

# GOOMBA = UnitType(color=(139, 90, 43), radius=20)
# BUZZY_BEETLE = UnitType(color=(50, 50, 180), radius=15)


class Entity(pygame.sprite.Sprite):
    def __init__(self, x_speed, y_speed, x_position, y_position, color, size=20):
        """
        Initialize with a starting position, move speed, size and color
        """
        super().__init__()
        self.x_speed = x_speed
        self.y_speed = y_speed
        self.x_pos = x_position
        self.y_pos = y_position
        self.color = color
        self.radius = size

    def move(self, height):
        self.x_pos += self.x_speed
        self.y_pos += self.y_speed
        if self.y_pos + self.radius > height or self.y_pos - self.radius < 0:
            self.y_speed *= -1

    def is_offscreen(self, width):
        """
        Calculate if the entity is off the screen
        """
        return self.x_pos > width + self.radius or self.x_pos < -self.radius

    def draw(self, surface):
        """
        display the entity
        """
        pygame.draw.circle(surface, self.color, (int(self.x_pos), int(self.y_pos)), self.radius)

