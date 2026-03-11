import pygame 
import random

class Tiles(pygame.sprite.Sprite): 
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((40, 40))
        self.image.fill("green")
        self.rect = self.image.get_rect(topleft=(x, y))
        self.speed = 3

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > 600:
            self.kill() 

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                
            # Check of de timer afgaat
            if event.type == self.spawn_timer:
                # Kies een random X positie
                random_x = random.randint(0, 760) 
                # Maak de nieuwe tegel aan
                new_tile = Tiles(random_x, -50) # Start boven het scherm
              
                self.tiles.add(new_tile)
                
                self.all_sprites.add(new_tile)

            