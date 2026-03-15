import pygame 

class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        # Grootte speler
        self.image = pygame.Surface((40, 40))
        self.rect = self.image.get_rect(topleft=(x,y))  #"hitbox" van de speler1
        self.image.fill("red") #kleur 
        
        # De positie en hitbox
        self.rect = self.image.get_rect(topleft=(x, y))
        
        #Snelheid van de movement
        self.speed = 5

    def update(self):
        self.move()
        

    def move(self):
        # Haal alle ingedrukte toetsen op
        keys = pygame.key.get_pressed()
        
        # Beweeg in 4 richtingen
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.rect.x -= self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.rect.x += self.speed
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.rect.y -= self.speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.rect.y += self.speed