import pygame
import sys
import random 
from player import Player
from tiles import Tiles

class Game:
    def __init__(self):
        #Initializing game 
        pygame.init()
        # In je __init__ methode:
        self.SPAWN_EVENT = pygame.USEREVENT + 1
        pygame.time.set_timer(self.SPAWN_EVENT, 1000) 

        #Init player
        self.player_one = Player(100,100)
        
        # Display 
        self.screen_width = 800
        self.screen_height = 600
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Platformer")
        
        # Fps control 
        self.clock = pygame.time.Clock()
        self.running = True

        #Set up sprite group and tiles group
        self.all_sprites = pygame.sprite.Group()
        self.all_sprites.add(self.player_one)
        self.tiles = pygame.sprite.Group()

        #Score system
        self.points = 0 
        self.font = pygame.font.SysFont("Arial",32)

    def run(self):
        while self.running:
            self.handle_events()  # Checking inputs 
            self.update()         # Movement/collision handling
            self.draw()           # Showing attributes
            self.clock.tick(60)   # 60 fps

    def handle_events(self): #Shutdown 
        for event in pygame.event.get():  
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == self.SPAWN_EVENT:
                self.spawn_tile()

    def update(self): 
   
        for tile in self.tiles.sprites(): 
            if tile.update(): 
                self.points += 1 
                print(f"Check Punten: {self.points}")
            
        
        self.player_one.update()



    def draw(self): #BACKGROUND 
        self.screen.fill((30, 30, 30)) 

        score_text = self.font.render(f"Score: {self.points}", True, (255, 255, 255))
        self.screen.blit(score_text, (10, 10))

        # Draw everything
        self.all_sprites.draw(self.screen)

        pygame.display.flip()

    def spawn_tile(self):
        random_x = random.randint(0, 760)

        new_tile = Tiles(random_x, -50) 
 
        self.all_sprites.add(new_tile)
        self.tiles.add(new_tile)

#Running the game 
if __name__ == "__main__":
    game = Game()
    game.run()
    pygame.quit()
    sys.exit()