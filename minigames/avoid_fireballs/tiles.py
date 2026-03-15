import pygame 
import random
import os 

class Tiles(pygame.sprite.Sprite): 
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((40, 40))
        # self.image.fill("green")
        self.rect = self.image.get_rect(topleft=(x, y))
        self.speed = 1
        self.score = 0

        self.frames = []

         # Animatie variabelen
        self.current_frame = 0
        self.animation_speed = 0.15 # Hoe hoger, hoe trager de animatie
        
        if self.frames:
            self.image = self.frames[0]
            self.rect = self.image.get_rect(topleft=(x, y))
        
       

     

        self.current_path = os.path.dirname(__file__)

        self.sprites_dir = os.path.join(self.current_path, "sprites", "fireball")

       

        for i in range(7):
            self.path = os.path.join(self.sprites_dir, f"sprite_{i}.png")
            if os.path.exists(self.path): 
                img = pygame.image.load(self.path).convert_alpha()
                self.frames.append(img)

       
          
        

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > 600:
            self.kill()
            return True
    
        # 1. Animatie logica
        if self.frames:
            self.current_frame += self.animation_speed
            if self.current_frame >= len(self.frames):
                self.current_frame = 0
            self.image = self.frames[int(self.current_frame)]

        # 2. Beweging
        self.rect.y += self.speed
        if self.rect.top > 600:
            self.kill()
            return True
        return False
            


            


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

            