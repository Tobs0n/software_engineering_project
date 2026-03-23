import pygame 
import os

class Player(pygame.sprite.Sprite):
    def __init__(self, x, y, player_num, controls): #coordinaten, player nummer, controls
        super().__init__()
        # Grootte speler
        self.sprite_path = os.path.dirname(__file__)
        self.sprites_dir = os.path.join(self.sprite_path, "sprites", f"player_{player_num}", f"p_{player_num}.png")
        self.image = pygame.image.load(self.sprites_dir).convert_alpha()
        self.rect = self.image.get_rect(topleft=(x,y))  #"hitbox" van de spelers
        self.controls = controls
        self.player_num = player_num
        #Snelheid van de movement
        self.speed = 5
        self.lives = 3

    def update(self):
        self.move()
        

    def move(self):
        # Haal alle ingedrukte toetsen op
        keys = pygame.key.get_pressed()
        if keys[self.controls['left']]:
            self.rect.x -= self.speed
        if keys[self.controls['right']]:
            self.rect.x += self.speed
        if keys[self.controls['up']]:
            self.rect.y -= self.speed
        if keys[self.controls['down']]:
            self.rect.y += self.speed

        screen_rect = pygame.display.get_surface().get_rect()
        self.rect.clamp_ip(screen_rect)