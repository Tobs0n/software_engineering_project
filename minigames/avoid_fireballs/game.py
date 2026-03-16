import pygame
import sys
import random 
import os
from player import Player
from tiles import Tiles

class Game:
    def __init__(self):
        #Initializing game 
        pygame.init()
        self.current_path = os.path.dirname(__file__)
        bg_path = os.path.join(self.current_path, "sprites", "background", "bg.png")

        # In je __init__ methode:
        self.SPAWN_EVENT = pygame.USEREVENT + 1
        pygame.time.set_timer(self.SPAWN_EVENT, 1000) 

        # Display 
        self.screen_width = 800
        self.screen_height = 600
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))

        try:
            self.background = pygame.image.load(bg_path).convert()
            self.background = pygame.transform.scale(self.background, (800, 600))
        except pygame.error as e:
            print(f"Fout bij laden achtergrond: {e}")
            # Fallback kleur als de png ontbreekt
            self.background = pygame.Surface((800, 600))
            self.background.fill((30, 30, 30))

        pygame.display.set_caption("Platformer")
        

        #Init player
        
        p1_controls = {
            'left': pygame.K_a,
            'right': pygame.K_d,
            'up': pygame.K_w,
            'down': pygame.K_s
        }


        p2_controls = {
            'left': pygame.K_LEFT,
            'right': pygame.K_RIGHT,
            'up': pygame.K_UP,
            'down': pygame.K_DOWN
        }
        
        self.player_one = Player(100, 100, 1, p1_controls)
        self.player_two = Player(100, 100, 2, p2_controls)
        
        
        # Fps control 
        self.clock = pygame.time.Clock()
        self.running = True

        #Set up sprite group and tiles group
        self.all_sprites = pygame.sprite.Group()
        self.all_sprites.add(self.player_one)
        self.all_sprites.add(self.player_two)
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
        self.player_two.update()



    def draw(self): #BACKGROUND 
        self.screen.fill((30, 30, 30)) 
        self.screen.blit(self.background, (0, 0))

        score_text = self.font.render(f"Score: {self.points}", True, (255, 255, 255))
        self.screen.blit(score_text, (10, 10))

        middle_x = self.screen_width //2 
        pygame.draw.line(self.screen, (0,0,0), (middle_x, 0), (middle_x, self.screen_height), 5)

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