import pygame
import sys
from player import Player

class Game:
    def __init__(self):
        #Initializing game 
        pygame.init()

        #Init player
        self.player_one = Player(100,100)
        
        # Display 
        self.screen_width = 800
        self.screen_height = 600
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("My Platformer")
        
        # Fps control 
        self.clock = pygame.time.Clock()
        self.running = True

        #Set up sprite group and tiles group
        self.all_sprites = pygame.sprite.Group()
        self.all_sprites.add(self.player_one)
        self.tiles = pygame.sprite.Group()

    def run(self):
        """The Main Game Loop"""
        while self.running:
            self.handle_events()  # Checking inputs 
            self.update()         # Movement/collision handling
            self.draw()           # Showing attributes
            self.clock.tick(60)   # 60 fps

    def handle_events(self): #Shutdown 
        for event in pygame.event.get():  
            if event.type == pygame.QUIT:
                self.running = False

    def update(self): 
        # Movement of objects
        self.all_sprites.update()

    def draw(self): #BACKGROUND 
        self.screen.fill((30, 30, 30)) 
        # Draw everything
        self.all_sprites.draw(self.screen)
        pygame.display.flip()

#Running the game 
if __name__ == "__main__":
    game = Game()
    game.run()
    pygame.quit()
    sys.exit()