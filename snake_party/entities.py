import pygame
import os


class Snake:
    def __init__(self, player, start_pos, keys, start_direction):
        self.player = player
        self.direction = start_direction
        self.body = [
            pygame.Vector2(start_pos),
            pygame.Vector2(start_pos - self.direction),
            pygame.Vector2(start_pos - (self.direction * 2))
        ]
        self.keys = keys
        self.ghost_timer = 0
        self.speed_timer = 0
        self.is_alive = True

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == self.keys['up'] and self.direction.y == 0:
                self.direction = pygame.Vector2(0, -20)
            elif event.key == self.keys['down'] and self.direction.y == 0:
                self.direction = pygame.Vector2(0, 20)
            elif event.key == self.keys['left'] and self.direction.x == 0:
                self.direction = pygame.Vector2(-20, 0)
            elif event.key == self.keys['right'] and self.direction.x == 0:
                self.direction = pygame.Vector2(20, 0)

    def move(self, grow=False):
        if not self.is_alive:
            return
        new_head = self.body[0] + self.direction
        self.body.insert(0, new_head)
        if not grow:
            self.body.pop()
        if self.ghost_timer > 0:
            self.ghost_timer -= 1

    def draw(self, screen):
        if self.ghost_timer > 0:
            if self.ghost_timer < 30 and self.ghost_timer % 4 < 2:
                color = self.player.color # Knipper effect
            else:
                color = (255, 255, 255)
        elif not self.is_alive:
            color = (100, 100, 100)
        else:
            color = getattr(self.player, 'color', (0, 255, 0))

        for segment in self.body:
            pygame.draw.rect(screen, color, (segment.x, segment.y, 18, 18))

    def double_length(self):
        new_segments = [pygame.Vector2(s) for s in self.body]
        self.body.extend(new_segments)

import random

# class Apple:
#     def __init__(self, grid_size, width, height):
#         self.grid_size = grid_size
#         self.pos = pygame.Vector2(
#             random.randint(0, (width // grid_size) - 1) * grid_size,
#             random.randint(0, (height // grid_size) - 1) * grid_size
#         )
        
#         # Bepaal het type appel met kansverdeling
#         kans = random.random()
#         if kans < 0.60:
#             self.type = "red"
#             self.color = (255, 0, 0)
#         elif kans < 0.75:
#             self.type = "gold"
#             self.color = (255, 215, 0)
#         elif kans < 0.90:
#             self.type = "white"
#             self.color = (255, 255, 255)
#         else:
#             self.type = "blue"
#             self.color = (0, 150, 255) # Mooi helder blauw

#     def draw(self, screen):
#         pygame.draw.rect(screen, self.color, (self.pos.x, self.pos.y, self.grid_size - 2, self.grid_size - 2))

class Apple:
    def __init__(self, grid_size, width, height):
        self.grid_size = grid_size
        self.pos = pygame.Vector2(
            random.randint(0, (width // grid_size) - 1) * grid_size,
            random.randint(0, (height // grid_size) - 1) * grid_size
        )
        
        # Bepaal het type appel met kansverdeling 
        kans = random.random()
        if kans < 0.70:
            self.type = "red"
            filename = 'red_apple.png'
        elif kans < 0.80:
            self.type = "gold"
            filename = 'golden_apple.png'
        elif kans < 0.90:
            self.type = "white"
            filename = 'white_apple.png'
        else:
            self.type = "blue"
            filename = 'blue_apple.png'
        
        # Laad de afbeelding
        try:
            script_dir = os.path.dirname(__file__)
            full_path = os.path.join(script_dir, filename)
            raw_image = pygame.image.load(full_path).convert_alpha()
            self.image = pygame.transform.scale(raw_image, (grid_size - 2, grid_size - 2))
        except pygame.error as e:
            print(f"Kon {filename} niet laden: {e}")
            self.type = "red"
            self.image = pygame.Surface((grid_size - 2, grid_size - 2))
            self.image.fill((255, 0, 0))

    def draw(self, screen):
        screen.blit(self.image, (self.pos.x + 1, self.pos.y + 1))